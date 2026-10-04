import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class RVLauncherSelfTest {
    public static final class MockChild {
        public static void main(String[] args) throws Exception {
            System.out.println("READY");
            System.out.flush();
            BufferedReader input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
            String line;
            while ((line = input.readLine()) != null) if ("stop".equals(line)) { System.out.println("SAVED"); System.out.flush(); return; }
        }
    }

    public static void main(String[] args) throws Exception {
        testDestinations();
        testClientAndServerCommands();
        testProfilePersistence();
        testInviteValidation();
        testSafeArchives();
        testExistingConfigurationPreserved();
        testCurrentServerReadinessLog();
        testGracefulChildProcess();
        if (args.length > 0) testPackageResources(Paths.get(args[0]));
        System.out.println("RVLauncherSelfTest passed");
    }

    private static void testDestinations() {
        RVLauncher.Destination direct = RVLauncher.validateDestination("direct", "127.0.0.1:25570", 25565);
        check("127.0.0.1".equals(direct.target) && direct.port == 25570, "direct address parsing");
        RVLauncher.Destination porthole = RVLauncher.validateDestination("porthole", "abcd12", 25565);
        check("ABCD12".equals(porthole.target) && porthole.porthole(), "Porthole code parsing");
        check(RVLauncher.validLobby("lobby:0") == false && RVLauncher.validLobby("lobby:9223372036854775807"), "lobby id bounds");
        expect(IllegalArgumentException.class, () -> RVLauncher.validateDestination("direct", "http://example.com/path", 25565));
        expect(IllegalArgumentException.class, () -> RVLauncher.validateDestination("porthole", "lobby:9223372036854775808", 25565));
        expect(IllegalArgumentException.class, () -> RVLauncher.validateDestination("porthole", "lobby:0", 25565));
        expect(IllegalArgumentException.class, () -> RVLauncher.validateDestination("invalid", "", 25565));
    }

    private static void testClientAndServerCommands() throws Exception {
        Path root = Files.createTempDirectory("rv-launcher-command-");
        Path java = root.resolve("runtime/bin/java");
        RVLauncher.InstallerFiles manifest = new RVLauncher.InstallerFiles();
        manifest.mainClass = "net.minecraft.launchwrapper.Launch";
        manifest.assetIndex = "1.12";
        manifest.classpath = Arrays.asList("libraries/forge.jar", "libraries/lwjgl.jar");
        List<String> local = RVLauncher.clientCommand(java, root.resolve("game"), manifest, "Player_1", 4096, null, 25565);
        check(!local.contains("--server") && !local.contains("--port"), "local mode must not select a server");
        check(local.contains("-XstartOnFirstThread") && local.contains("--tweakClass") && local.contains("net.minecraftforge.fml.common.launcher.FMLTweaker"), "macOS Forge client arguments");
        List<String> remote = RVLauncher.clientCommand(java, root.resolve("game"), manifest, "Player_1", 4096, "127.0.0.1", 25565);
        check(remote.contains("--server") && remote.contains("127.0.0.1") && remote.contains("--port"), "explicit destination arguments");
        check(RVLauncher.offlineUuid("Player_1").equals(RVLauncher.offlineUuid("Player_1")), "stable offline identity");
        List<String> server = RVLauncher.serverCommand(java, root.resolve("game"), root.resolve("host"), manifest, "minecraft_server.1.12.2.jar", "net.minecraftforge.fml.relauncher.ServerLaunchWrapper", 4096);
        check(server.contains("net.minecraftforge.fml.common.launcher.FMLServerTweaker") && server.contains("--gameDir") && server.contains("nogui"), "Forge server arguments");
        check(!join(server).contains("--server"), "server launch has no client target argument");
        delete(root);
    }

    private static void testProfilePersistence() throws Exception {
        Path root = Files.createTempDirectory("rv-launcher-profile-");
        RVLauncher.ProfileStore store = new RVLauncher.ProfileStore(root.resolve("launcher.properties"));
        RVLauncher.Profile initial = store.load();
        initial.friends = RVLauncher.validateDestination("porthole", "a1b2c3", 25571);
        initial.nickname = "Pilot_7";
        store.save(initial, "friends");
        RVLauncher.Profile changedButCancelled = store.load();
        changedButCancelled.owner = RVLauncher.validateDestination("direct", "game.example.net:25575", 25565);
        RVLauncher.Profile beforeExplicitSave = store.load();
        check(beforeExplicitSave.owner.empty(), "unsaved edits are not persisted");
        store.save(changedButCancelled, "owner");
        RVLauncher.Profile reloaded = store.load();
        check("A1B2C3".equals(reloaded.friends.target) && reloaded.friends.port == 25571, "Friends profile persists independently");
        check("game.example.net".equals(reloaded.owner.target) && reloaded.owner.port == 25575, "Owner profile persists independently");
        check("Pilot_7".equals(reloaded.nickname), "common profile persists");
        delete(root);
    }

    private static void testInviteValidation() throws Exception {
        Path root = Files.createTempDirectory("rv-launcher-invite-");
        Path invite = root.resolve("test.rvinvite");
        Files.write(invite, ("{\"schema\":1,\"product\":\"RV\",\"transport\":\"porthole\",\"target\":\"RV7AB1\",\"port\":25565,\"version\":\"2.0.4\"}").getBytes(StandardCharsets.UTF_8));
        RVLauncher.Destination destination = RVLauncher.readInvite(invite);
        check(destination.porthole() && "RV7AB1".equals(destination.target), "invite destination");
        expect(java.io.IOException.class, () -> RVLauncher.readInvite(invite, "2.0.3"));
        Files.write(invite, ("{\"schema\":1,\"product\":\"RV\",\"transport\":\"porthole\",\"target\":\"RV7AB1\",\"port\":25565,\"version\":\"2.0.4\",\"peerTarget\":\"peer:12345678901234567\"}").getBytes(StandardCharsets.UTF_8));
        expect(java.io.IOException.class, () -> RVLauncher.readInvite(invite));
        delete(root);
    }

    private static void testSafeArchives() throws Exception {
        Path root = Files.createTempDirectory("rv-launcher-zip-");
        Path good = root.resolve("good.zip");
        zip(good, "config/test.cfg", "ok".getBytes(StandardCharsets.UTF_8));
        Path output = root.resolve("out");
        RVLauncher.SafeZip.extract(good, output, (name, target) -> true, 1048576, 1048576, new RVLauncher.CancelToken());
        check("ok".equals(new String(Files.readAllBytes(output.resolve("config/test.cfg")), StandardCharsets.UTF_8)), "safe extraction");
        Path traversal = root.resolve("traversal.zip");
        zip(traversal, "../escape", new byte[]{1});
        expect(java.io.IOException.class, () -> RVLauncher.SafeZip.inspect(traversal, 1048576, 1048576));
        Path symlink = root.resolve("symlink.zip");
        zip(symlink, "linked", new byte[]{1});
        makeUnixSymlink(symlink);
        expect(java.io.IOException.class, () -> RVLauncher.SafeZip.inspect(symlink, 1048576, 1048576));
        Path bomb = root.resolve("bomb.zip");
        byte[] repetitive = new byte[2 * 1024 * 1024];
        zip(bomb, "large.bin", repetitive);
        expect(java.io.IOException.class, () -> RVLauncher.SafeZip.inspect(bomb, 1048576, 4 * 1024 * 1024));
        delete(root);
    }

    private static void testGracefulChildProcess() throws Exception {
        String javaName = System.getProperty("java.home") + java.io.File.separator + "bin" + java.io.File.separator + (System.getProperty("os.name").toLowerCase().contains("win") ? "java.exe" : "java");
        List<String> command = Arrays.asList(javaName, "-cp", System.getProperty("java.class.path"), "RVLauncherSelfTest$MockChild");
        Process child = new ProcessBuilder(command).redirectErrorStream(true).start();
        BufferedReader output = new BufferedReader(new InputStreamReader(child.getInputStream(), StandardCharsets.UTF_8));
        check("READY".equals(output.readLine()), "mock server starts");
        Writer input = new OutputStreamWriter(child.getOutputStream(), StandardCharsets.UTF_8);
        input.write("stop\n");
        input.flush();
        check("SAVED".equals(output.readLine()), "graceful stop reaches child stdin");
        check(child.waitFor(5, java.util.concurrent.TimeUnit.SECONDS) && child.exitValue() == 0, "child process exits cleanly");
    }

    private static void testPackageResources(Path resources) throws Exception {
        RVLauncher.PackageBundle bundle = new RVLauncher.PackageBundle(resources);
        java.util.Set<String> serverMods = RVLauncher.requiredServerModPaths(bundle);
        check(serverMods.contains("mods/IAV-1.1.11-1.12.2.jar") && serverMods.contains("mods/VEB-1.1.11-1.12.2.jar"), "server content packs");
        check(serverMods.contains("mods/mcheli-ce-1.5.1-rv.jar") && serverMods.contains("mods/elegant-networking-1.12-3.14.jar"), "server dependencies");
        check(!serverMods.contains("mods/AmbientSounds_v3.1.7_mc1.12.2.jar") && !serverMods.contains("mods/jei_1.12.2-4.16.1.302.jar"), "client-only mods excluded");
    }

    private static void zip(Path path, String name, byte[] data) throws Exception {
        try (ZipOutputStream out = new ZipOutputStream(Files.newOutputStream(path))) {
            out.putNextEntry(new ZipEntry(name));
            out.write(data);
            out.closeEntry();
        }
    }

    private static void makeUnixSymlink(Path path) throws Exception {
        byte[] bytes = Files.readAllBytes(path);
        for (int i = 0; i + 46 < bytes.length; i++) if ((bytes[i] & 255) == 0x50 && (bytes[i + 1] & 255) == 0x4b && (bytes[i + 2] & 255) == 1 && (bytes[i + 3] & 255) == 2) {
            bytes[i + 4] = 20;
            bytes[i + 5] = 3;
            bytes[i + 38] = 0;
            bytes[i + 39] = 0;
            bytes[i + 40] = (byte) 0xff;
            bytes[i + 41] = (byte) 0xa1;
            Files.write(path, bytes);
            return;
        }
        throw new AssertionError("central directory was not found");
    }

    private static void testCurrentServerReadinessLog() throws Exception {
        Path root = Files.createTempDirectory("rv-server-readiness-");
        Path log = root.resolve("latest.log");
        long started = System.currentTimeMillis();
        Files.write(log, "[Server thread/INFO]: Done (5.0s)!\n".getBytes(StandardCharsets.UTF_8));
        Files.setLastModifiedTime(log, java.nio.file.attribute.FileTime.fromMillis(started - 10000));
        check(!RVLauncher.serverLogReady(log, started), "previous server readiness does not count");
        Files.write(log, "[Server thread/INFO]: Preparing level world\n".getBytes(StandardCharsets.UTF_8));
        Files.setLastModifiedTime(log, java.nio.file.attribute.FileTime.fromMillis(started + 100));
        check(!RVLauncher.serverLogReady(log, started), "world must finish loading");
        Files.write(log, "[Server thread/INFO]: Done (5.0s)!\n".getBytes(StandardCharsets.UTF_8));
        Files.setLastModifiedTime(log, java.nio.file.attribute.FileTime.fromMillis(started + 100));
        check(RVLauncher.serverLogReady(log, started), "current Forge log confirms readiness");
        delete(root);
    }

    private static void testExistingConfigurationPreserved() throws Exception {
        Path root = Files.createTempDirectory("rv-existing-config-");
        Path archive = root.resolve("payload.zip");
        Path game = root.resolve("game");
        Files.createDirectories(game.resolve("config"));
        Files.createDirectories(game.resolve("ModularWarfare"));
        Files.write(game.resolve("config/mcheli.cfg"), "player settings".getBytes(StandardCharsets.UTF_8));
        Files.write(game.resolve("ModularWarfare/mod_config.json"), "player weapons".getBytes(StandardCharsets.UTF_8));
        try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(archive))) {
            for (String name : Arrays.asList("config/mcheli.cfg", "config/firstaid.cfg", "ModularWarfare/mod_config.json")) {
                zip.putNextEntry(new ZipEntry(name));
                zip.write("package defaults".getBytes(StandardCharsets.UTF_8));
                zip.closeEntry();
            }
        }
        for (int play = 0; play < 2; play++) {
            RVLauncher.SafeZip.extract(archive, game,
                    (relative, target) -> !Files.exists(target) || !RVLauncher.preserveExistingConfiguration(relative),
                    1024 * 1024, 1024 * 1024, new RVLauncher.CancelToken());
            check(new String(Files.readAllBytes(game.resolve("config/mcheli.cfg")), StandardCharsets.UTF_8).equals("player settings"), "existing game configuration survives each Play");
            check(new String(Files.readAllBytes(game.resolve("ModularWarfare/mod_config.json")), StandardCharsets.UTF_8).equals("player weapons"), "existing weapon configuration survives each Play");
            check(new String(Files.readAllBytes(game.resolve("config/firstaid.cfg")), StandardCharsets.UTF_8).equals("package defaults"), "missing configuration installed");
        }
        delete(root);
    }

    private static void expect(Class<? extends Throwable> type, Throwing action) {
        try { action.run(); }
        catch (Throwable error) { if (type.isInstance(error)) return; throw new AssertionError("Unexpected failure type: " + error, error); }
        throw new AssertionError("Expected " + type.getName());
    }

    private static void check(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }

    private static String join(List<String> values) { StringBuilder result = new StringBuilder(); for (String value : values) result.append(value).append(' '); return result.toString(); }

    private static void delete(Path root) throws Exception {
        if (!Files.exists(root)) return;
        List<Path> paths = new ArrayList<Path>();
        try (java.util.stream.Stream<Path> walk = Files.walk(root)) { walk.forEach(paths::add); }
        paths.sort((left, right) -> right.getNameCount() - left.getNameCount());
        for (Path path : paths) Files.deleteIfExists(path);
    }

    interface Throwing { void run() throws Exception; }
}
