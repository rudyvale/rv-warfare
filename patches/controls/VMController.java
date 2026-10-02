package com.norwood.mcheli.vm;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import net.java.games.input.Controller;
import net.java.games.input.ControllerEnvironment;
import net.java.games.input.Component;

public final class VMController {
    public static final String[] ACTIONS = {"roll", "pitch", "yaw", "throttle"};
    public static final String[] BUTTONS = {"fire", "aim", "weapon", "brake", "exit", "mode", "reload", "weaponMode", "zoom"};
    public static final VMController INSTANCE = new VMController();
    public final Properties profile = new Properties();
    public final double[] values = new double[4];
    public final Map<String, Boolean> buttons = new HashMap<String, Boolean>();
    public Controller device;
    public Controller[] devices = new Controller[0];
    public boolean connected;
    public boolean armed;
    public String status = "Контроллер выключен";
    private long fileTime = -2, nextLoad, nextScan, previousPoll;
    private Path file = Paths.get("config", "vm-controller.properties");

    public synchronized void setRoot(Path root) { file = root.resolve("config/vm-controller.properties"); load(); }
    public synchronized void load() {
        profile.clear();
        try { if (Files.exists(file)) try (InputStream in = Files.newInputStream(file)) { profile.load(in); } }
        catch (IOException e) { VMReflect.error("controller profile", e); }
        try { fileTime = Files.exists(file) ? Files.getLastModifiedTime(file).toMillis() : -1; } catch (IOException ignored) { }
        armed = false; Arrays.fill(values, 0); device = null; nextScan = 0;
    }
    public synchronized void save() throws IOException {
        Files.createDirectories(file.toAbsolutePath().getParent());
        Path temp = file.resolveSibling(file.getFileName() + ".tmp");
        try (OutputStream out = Files.newOutputStream(temp)) { profile.store(out, "VM controller"); }
        try { Files.move(temp, file, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING); }
        catch (AtomicMoveNotSupportedException ignored) { Files.move(temp, file, StandardCopyOption.REPLACE_EXISTING); }
        fileTime = Files.getLastModifiedTime(file).toMillis(); armed = false;
    }
    public boolean enabled() { return Boolean.parseBoolean(profile.getProperty("enabled", "false")); }
    public boolean gamepad() { return profile.getProperty("kind", "radio").equals("gamepad"); }
    public boolean acro() { return profile.getProperty("flight", "angle").equals("acro"); }
    public double setting(String name, double fallback) {
        try { double v = Double.parseDouble(profile.getProperty(name)); return Double.isFinite(v) ? v : fallback; }
        catch (Exception ignored) { return fallback; }
    }
    public static String identity(Controller controller) {
        StringBuilder b = new StringBuilder(controller.getName()).append('|').append(controller.getType());
        for (Component c : controller.getComponents()) b.append('|').append(c.getIdentifier()).append(':').append(c.isAnalog());
        return b.toString();
    }
    public synchronized Controller[] scan() {
        try {
            ControllerEnvironment environment;
            Class<?> cls = Class.forName("net.java.games.input.DirectAndRawInputEnvironmentPlugin");
            environment = (ControllerEnvironment) cls.newInstance();
            ArrayList<Controller> list = new ArrayList<Controller>();
            for (Controller c : environment.getControllers()) {
                if (c.getType() == Controller.Type.MOUSE || c.getType() == Controller.Type.KEYBOARD) continue;
                int axes = 0;
                for (Component component : c.getComponents()) if (component.isAnalog() && !component.isRelative()) axes++;
                if (axes >= 2) list.add(c);
            }
            devices = list.toArray(new Controller[0]);
            device = null;
            for (Controller c : devices) if (identity(c).equals(profile.getProperty("device"))) { device = c; break; }
            nextScan = System.currentTimeMillis() + 5000;
        } catch (Throwable error) { status = "Не удалось прочитать USB-контроллеры"; VMReflect.error("controller scan", error); }
        return devices;
    }
    public Component component(String key) {
        if (device == null || key == null) return null;
        Component[] all = device.getComponents();
        try { int i = Integer.parseInt(key); return i >= 0 && i < all.length ? all[i] : null; }
        catch (NumberFormatException ignored) { return null; }
    }
    public double raw(String action) {
        Component c = component(profile.getProperty(action + ".axis"));
        return c == null ? 0 : c.getPollData();
    }
    public boolean mappingValid() {
        Set<String> selected = new HashSet<String>();
        for (String action : ACTIONS) {
            String id = profile.getProperty(action + ".axis");
            Component c = component(id);
            if (c == null || !c.isAnalog() || c.isRelative() || !selected.add(id)) return false;
            double low = setting(action + ".min", 0), high = setting(action + ".max", 0), center = setting(action + ".center", 0);
            if (high - low < 0.16 || center - low < 0.08 || high - center < 0.08) return false;
        }
        return true;
    }
    public synchronized void poll(boolean focus) {
        long now = System.currentTimeMillis();
        if (now > nextLoad) {
            nextLoad = now + 1000;
            try { long t = Files.exists(file) ? Files.getLastModifiedTime(file).toMillis() : -1; if (t != fileTime) load(); }
            catch (IOException ignored) { }
        }
        if (enabled() && device == null && now > nextScan) scan();
        if (device != null && !device.poll()) { device = null; armed = false; }
        boolean valid = enabled() && device != null && mappingValid();
        connected = valid;
        if (!valid || !focus) {
            Arrays.fill(values, 0); buttons.clear(); armed = false;
            status = !enabled() ? "Контроллер выключен" : !focus ? "Пауза: газ сброшен" : "Нет устройства / нужна калибровка";
            previousPoll = now; return;
        }
        double dt = previousPoll == 0 ? 0.02 : Math.min(0.1, Math.max(0, (now - previousPoll) / 1000.0));
        previousPoll = now;
        double[] target = new double[4];
        for (int i = 0; i < ACTIONS.length; i++) {
            String a = ACTIONS[i];
            boolean invert = Boolean.parseBoolean(profile.getProperty(a + ".invert", "false"));
            target[i] = i == 3 && !gamepad()
                    ? VMControlMath.throttle(raw(a), setting(a + ".min", -1), setting(a + ".max", 1), invert)
                    : VMControlMath.axis(raw(a), setting(a + ".min", -1), setting(a + ".center", 0), setting(a + ".max", 1), invert, setting("deadzone", gamepad() ? 0.08 : 0.035), setting("expo", 0.35));
        }
        if (!armed) {
            if (gamepad() ? Math.abs(target[3]) < 0.08 : target[3] < 0.06) armed = true;
            else { Arrays.fill(values, 0); buttons.clear(); status = "Для включения убери газ"; return; }
        }
        if(!gamepad())target[3]=VMControlMath.throttleCurve(target[3],setting("throttleExpo",0));
        for (int i = 0; i < 4; i++) values[i] = VMControlMath.smooth(values[i], target[i], dt, VMControlMath.clamp(setting(i==3?"throttleSmoothing":"smoothing",0.07),.005,.2));
        for (String action : BUTTONS) {
            String binding = profile.getProperty("button." + action, "");
            String[] parts = binding.split(":");
            Component c = component(parts.length == 0 ? null : parts[0]);
            boolean down = false;
            if (c != null) {
                double raw = c.getPollData();
                down = parts.length > 1 && parts[1].equals("-") ? raw < -0.55 : raw > 0.55;
            }
            buttons.put(action, down);
        }
        status = device.getName() + (acro() ? " · ACRO" : " · Стабилизация");
    }
    public boolean down(String action) { return Boolean.TRUE.equals(buttons.get(action)); }

    public boolean calibrated() {
        Set<String> axes=new HashSet<String>();
        for(String a:ACTIONS){String axis=profile.getProperty(a+".axis");if(axis==null||!axes.add(axis)||setting(a+".center",0)-setting(a+".min",0)<.08||setting(a+".max",0)-setting(a+".center",0)<.08)return false;}
        return true;
    }
    public void report(Path path,String outcome)throws IOException {
        scan();Map<String,Object> result=new LinkedHashMap<String,Object>();result.put("schema",1);result.put("outcome",outcome);
        ArrayList<Map<String,Object>> found=new ArrayList<Map<String,Object>>();
        for(Controller c:devices){Map<String,Object> d=new LinkedHashMap<String,Object>();int axes=0;for(Component component:c.getComponents())if(component.isAnalog()&&!component.isRelative())axes++;d.put("id",identity(c));d.put("name",c.getName());d.put("kind",c.getType()==Controller.Type.GAMEPAD?"gamepad":"radio");d.put("axisCount",axes);found.add(d);}
        result.put("devices",found);Map<String,Object> p=new LinkedHashMap<String,Object>();p.put("enabled",enabled());p.put("kind",gamepad()?"gamepad":"radio");p.put("device",profile.getProperty("device",""));p.put("calibrated",calibrated());p.put("connected",device!=null&&device.poll()&&mappingValid());result.put("profile",p);result.put("inputMode",enabled()?(gamepad()?"gamepad":"radio"):profile.getProperty("keyboardFlight","easy"));
        Path absolute=path.toAbsolutePath();Files.createDirectories(absolute.getParent());Path temp=absolute.resolveSibling(absolute.getFileName()+".tmp");Files.write(temp,new com.google.gson.GsonBuilder().setPrettyPrinting().create().toJson(result).getBytes(java.nio.charset.StandardCharsets.UTF_8));
        try{Files.move(temp,absolute,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}catch(AtomicMoveNotSupportedException e){Files.move(temp,absolute,StandardCopyOption.REPLACE_EXISTING);}
    }

    public static void main(String[] args) {
        VMController controller = new VMController();
        controller.setRoot(args.length>0?Paths.get(args[0]):Paths.get("."));
        if(args.length>2){try{if(args[1].equals("--keyboard")){controller.profile.setProperty("enabled","false");controller.profile.setProperty("keyboardFlight","easy");controller.save();}controller.report(Paths.get(args[2]),args[1].equals("--keyboard")?"saved":"probed");}catch(Exception e){VMReflect.error("controller report",e);System.exit(1);}return;}
        for (Controller c : controller.scan()) System.out.println(c.getName() + " | " + c.getType() + " | " + c.getComponents().length + " inputs");
        if (controller.devices.length == 0) System.out.println("No joystick connected");
    }
}
