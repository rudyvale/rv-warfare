package com.norwood.mcheli.uav;

import java.io.*;
import java.lang.reflect.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;

public final class WarfareOwnerAuth {
    private static final Map<String, Object> pending = new ConcurrentHashMap<String, Object>();
    private static final Map<Object, LoginCheck> logins = new ConcurrentHashMap<Object, LoginCheck>();
    private static final class LoginCheck {
        final Object manager;
        final Object profile;
        final String nickname;
        final long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(8);
        volatile boolean finished;
        volatile boolean verified;
        LoginCheck(Object manager, Object profile, String nickname) {
            this.manager = manager;
            this.profile = profile;
            this.nickname = nickname;
        }
    }
    private static final ThreadPoolExecutor workers = new ThreadPoolExecutor(1, 1, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<Runnable>(8), new ThreadFactory() {
        public Thread newThread(Runnable task) {
            Thread thread = new Thread(task, "RV owner check");
            thread.setDaemon(true);
            return thread;
        }
    }, new ThreadPoolExecutor.AbortPolicy());

    private static Object call(Object target, String[] names, Object... arguments) throws Exception {
        for (Method method : target.getClass().getMethods()) {
            if (!Arrays.asList(names).contains(method.getName()) || method.getParameterTypes().length != arguments.length) continue;
            Class<?>[] types = method.getParameterTypes();
            boolean matches = true;
            for (int index = 0; index < types.length; index++) {
                Object value = arguments[index];
                if (value == null) continue;
                if (types[index].isPrimitive()) {
                    if (types[index] == boolean.class && !(value instanceof Boolean)) matches = false;
                    else if (types[index] != boolean.class && !(value instanceof Number)) matches = false;
                } else if (!types[index].isInstance(value)) matches = false;
            }
            if (matches) return method.invoke(target, arguments);
        }
        throw new NoSuchMethodException(target.getClass().getName() + "." + names[0]);
    }

    private static Object field(Object target, String... names) throws Exception {
        for (Class<?> type = target.getClass(); type != null; type = type.getSuperclass()) {
            for (String name : names) {
                try {
                    Field field = type.getDeclaredField(name);
                    field.setAccessible(true);
                    return field.get(target);
                } catch (NoSuchFieldException ignored) {
                }
            }
        }
        throw new NoSuchFieldException(names[0]);
    }

    private static Object network(Object player) throws Exception {
        Object handler = field(player, "connection", "field_71135_a");
        return field(handler, "netManager", "field_147371_a");
    }

    private static void tag(Object player, boolean verified) throws Exception {
        call(player, new String[]{verified ? "addTag" : "removeTag", verified ? "func_184211_a" : "func_184197_b"}, "v_owner");
    }

    private static void disconnect(Object player) {
        try {
            Class<?> text = Class.forName("net.minecraft.util.text.TextComponentString");
            Object message = text.getConstructor(String.class).newInstance("Owner verification failed. Join from the host launcher.");
            call(field(player, "connection", "field_71135_a"), new String[]{"disconnect", "func_194028_b"}, message);
        } catch (Throwable ignored) {
        }
    }

    private static void schedule(Object server, Runnable task) throws Exception {
        for (Method method : server.getClass().getMethods()) {
            if (method.getParameterTypes().length == 1 && method.getParameterTypes()[0] == Runnable.class && method.getReturnType().getName().contains("ListenableFuture")) {
                method.invoke(server, task);
                return;
            }
        }
        throw new NoSuchMethodException("Server task queue");
    }

    private static boolean check(File root, File script, int port, String nickname) {
        Process process = null;
        try {
            String windows = System.getenv("SystemRoot");
            if (windows == null) return false;
            File shell = new File(windows, "System32/WindowsPowerShell/v1.0/powershell.exe");
            ProcessBuilder builder = new ProcessBuilder(shell.getAbsolutePath(), "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", script.getAbsolutePath(), "-LocalPort", Integer.toString(port), "-Nickname", nickname);
            builder.directory(root);
            builder.redirectErrorStream(true);
            process = builder.start();
            if (!process.waitFor(6, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                return false;
            }
            if (process.exitValue() != 0) return false;
            BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), "UTF-8"));
            try {
                String value = reader.readLine();
                return value != null && value.trim().equals("true") && reader.readLine() == null;
            } finally {
                reader.close();
            }
        } catch (Throwable ignored) {
            if (process != null) process.destroyForcibly();
            return false;
        }
    }

    private static void denyLogin(Object handler) {
        System.out.println("[RV owner] login denied before player admission");
        try {
            Class<?> text = Class.forName("net.minecraft.util.text.TextComponentString");
            Object message = text.getConstructor(String.class).newInstance("This nickname is reserved for the host. Use your own nickname or the host launcher.");
            try {
                call(handler, new String[]{"disconnect", "func_194026_b"}, message);
            } catch (NoSuchMethodException missing) {
                call(field(handler, "networkManager", "field_147333_a"), new String[]{"closeChannel", "func_150718_a"}, message);
            }
        } catch (Throwable error) {
            System.out.println("[RV owner] login rejection failed: " + error.getClass().getSimpleName());
        }
    }

    public static boolean allowLogin(final Object handler) {
        try {
            long now = System.nanoTime();
            for (Map.Entry<Object, LoginCheck> entry : logins.entrySet()) {
                LoginCheck old = entry.getValue();
                if (now >= old.deadline && logins.remove(entry.getKey(), old)) {
                    denyLogin(entry.getKey());
                    if (entry.getKey() == handler) return false;
                }
            }
            final Object manager = field(handler, "networkManager", "field_147333_a");
            if (!Boolean.TRUE.equals(call(manager, new String[]{"isChannelOpen", "func_150724_d"}))) {
                logins.remove(handler);
                return false;
            }
            final Object profile = field(handler, "loginGameProfile", "field_147337_i");
            final String incoming = (String)call(profile, new String[]{"getName"});
            LoginCheck current = logins.get(handler);
            if (current != null) {
                if (current.manager != manager || current.profile != profile || !current.nickname.equals(incoming)) {
                    logins.remove(handler, current);
                    denyLogin(handler);
                    return false;
                }
                if (!current.finished) return false;
                logins.remove(handler, current);
                if (!current.verified) denyLogin(handler);
                return current.verified;
            }
            final File root = new File(".").getCanonicalFile();
            File policy = new File(root, "vm-owner.properties");
            if (!policy.exists()) return true;
            Properties settings = new Properties();
            FileInputStream input = new FileInputStream(policy);
            try { settings.load(input); } finally { input.close(); }
            final String nickname = settings.getProperty("nickname", "");
            if (!nickname.matches("[A-Za-z0-9_]{3,16}")) {
                denyLogin(handler);
                return false;
            }
            if (!nickname.equalsIgnoreCase(incoming)) return true;
            final File script = new File(root, settings.getProperty("script", "Check-OwnerConnection.ps1")).getCanonicalFile();
            SocketAddress address = (SocketAddress)call(manager, new String[]{"getRemoteAddress", "func_74430_c"});
            if (!nickname.equals(incoming) || !script.getParentFile().equals(root) || !script.isFile() || !(address instanceof InetSocketAddress)) {
                denyLogin(handler);
                return false;
            }
            InetSocketAddress remote = (InetSocketAddress)address;
            if (remote.getAddress() == null || !remote.getAddress().isLoopbackAddress() || logins.size() >= 9) {
                denyLogin(handler);
                return false;
            }
            final int port = remote.getPort();
            final LoginCheck request = new LoginCheck(manager, profile, incoming);
            if (logins.putIfAbsent(handler, request) != null) return false;
            try {
                workers.execute(new Runnable() {
                    public void run() {
                        if (System.nanoTime() >= request.deadline || logins.get(handler) != request) return;
                        boolean verified = check(root, script, port, nickname);
                        try {
                            if (logins.get(handler) != request || !Boolean.TRUE.equals(call(manager, new String[]{"isChannelOpen", "func_150724_d"}))) {
                                logins.remove(handler, request);
                                return;
                            }
                            request.verified = verified && System.nanoTime() < request.deadline;
                            request.finished = true;
                        } catch (Throwable error) {
                            request.verified = false;
                            request.finished = true;
                        }
                    }
                });
            } catch (RejectedExecutionException full) {
                logins.remove(handler, request);
                denyLogin(handler);
            }
            return false;
        } catch (Throwable error) {
            logins.remove(handler);
            denyLogin(handler);
            System.out.println("[RV owner] login verification failed: " + error.getClass().getSimpleName());
            return false;
        }
    }

    public static void onJoin(Object event) {
        Object player = null;
        try {
            Object entity = call(event, new String[]{"getEntity"});
            if (!Class.forName("net.minecraft.entity.player.EntityPlayerMP").isInstance(entity)) return;
            player = entity;
            final Object connectedPlayer = player;
            final Object server = call(player, new String[]{"getServer", "func_184102_h"});
            if (server == null) return;
            final Object list = call(server, new String[]{"getPlayerList", "func_184103_al"});
            final Object profile = call(player, new String[]{"getGameProfile", "func_146103_bH"});
            final Object uuid = call(profile, new String[]{"getId"});
            final String key = uuid.toString();
            File root = new File(".").getCanonicalFile();
            File policy = new File(root, "vm-owner.properties");
            if (!policy.exists()) {
                boolean operator = Boolean.TRUE.equals(call(player, new String[]{"canUseCommand", "func_70003_b"}, 2, "time"));
                tag(player, operator);
                return;
            }
            tag(player, false);
            call(list, new String[]{"removeOp", "func_152610_b"}, profile);
            Properties settings = new Properties();
            FileInputStream input = new FileInputStream(policy);
            try { settings.load(input); } finally { input.close(); }
            final String nickname = settings.getProperty("nickname", "");
            if (!nickname.matches("[A-Za-z0-9_]{3,16}") || !nickname.equals(call(profile, new String[]{"getName"}))) return;
            final File script = new File(root, settings.getProperty("script", "Check-OwnerConnection.ps1")).getCanonicalFile();
            if (!script.getParentFile().equals(root) || !script.isFile()) return;
            Object manager = network(player);
            SocketAddress address = (SocketAddress)call(manager, new String[]{"getRemoteAddress", "func_74430_c"});
            if (!(address instanceof InetSocketAddress)) return;
            InetSocketAddress remote = (InetSocketAddress)address;
            if (remote.getAddress() == null || !remote.getAddress().isLoopbackAddress()) return;
            final int port = remote.getPort();
            final File directory = root;
            pending.put(key, connectedPlayer);
            workers.execute(new Runnable() {
                public void run() {
                    final boolean verified = check(directory, script, port, nickname);
                    try {
                        schedule(server, new Runnable() {
                            public void run() {
                                try {
                                    if (pending.get(key) != connectedPlayer) return;
                                    Object active = call(list, new String[]{"getPlayerByUUID", "func_177451_a"}, uuid);
                                    if (active != connectedPlayer || !Boolean.TRUE.equals(call(network(connectedPlayer), new String[]{"isChannelOpen", "func_150724_d"}))) return;
                                    pending.remove(key, connectedPlayer);
                                    if (verified) {
                                        call(list, new String[]{"addOp", "func_152605_a"}, profile);
                                        tag(connectedPlayer, true);
                                    }
                                    System.out.println("[RV owner] " + (verified ? "verified local session" : "operator denied"));
                                } catch (Throwable error) {
                                    try {
                                        call(list, new String[]{"removeOp", "func_152610_b"}, profile);
                                    } catch (Throwable denied) {
                                        disconnect(connectedPlayer);
                                    }
                                    tagSafely(connectedPlayer);
                                    pending.remove(key, connectedPlayer);
                                    System.out.println("[RV owner] callback failed: " + error.getClass().getSimpleName());
                                }
                            }
                        });
                    } catch (Throwable error) {
                        pending.remove(key, connectedPlayer);
                        System.out.println("[RV owner] queue failed: " + error.getClass().getSimpleName());
                    }
                }
            });
        } catch (Throwable error) {
            if (player != null) {
                tagSafely(player);
                disconnect(player);
            }
            System.out.println("[RV owner] verification failed: " + error.getClass().getSimpleName());
        }
    }

    private static void tagSafely(Object player) {
        try { tag(player, false); } catch (Throwable ignored) { }
    }
}
