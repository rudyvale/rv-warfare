import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.annotations.SerializedName;
import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.awt.event.WindowAdapter;
import java.awt.event.WindowEvent;
import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.io.Reader;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLConnection;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Properties;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CancellationException;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipInputStream;
import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JComboBox;
import javax.swing.JFileChooser;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JSpinner;
import javax.swing.JTabbedPane;
import javax.swing.JTextField;
import javax.swing.SpinnerNumberModel;
import javax.swing.SwingUtilities;
import javax.swing.SwingWorker;
import javax.swing.UIManager;

public final class RVLauncher extends JFrame {
    private static final long serialVersionUID = 1L;
    static final Gson JSON = new Gson();
    static final int PORT = 25565;
    static final int MAX_DOWNLOAD_BYTES = 536870912;
    static final long MAX_PAYLOAD_ARCHIVE = 3221225472L;
    static final String PORTHOLE_APP_ID = "4963920";
    static final String EXPECTED_GAME_VERSION = "1.12.2";
    static final String EXPECTED_PLAY_TWEAKER = "net.minecraftforge.fml.common.launcher.FMLTweaker";
    private static final Pattern USERNAME = Pattern.compile("^[A-Za-z0-9_]{1,16}$");
    private static final Pattern SHA1 = Pattern.compile("^[0-9a-fA-F]{40}$");
    private static final Pattern SHA256 = Pattern.compile("^[0-9a-fA-F]{64}$");
    private final AppPaths paths;
    private final PackageBundle bundle;
    private final ProfileStore store;
    private Profile profile;
    private final JComboBox<String> languageBox = new JComboBox<String>(new String[]{"Русский", "English"});
    private final JTextField nickname = new JTextField(18);
    private final JTextField friendTarget = new JTextField(22);
    private final JTextField ownerTarget = new JTextField(22);
    private final JComboBox<String> friendTransport = new JComboBox<String>();
    private final JComboBox<String> ownerTransport = new JComboBox<String>();
    private final JSpinner friendPort = new JSpinner(new SpinnerNumberModel(PORT, 1, 65535, 1));
    private final JSpinner ownerPort = new JSpinner(new SpinnerNumberModel(PORT, 1, 65535, 1));
    private final JSpinner hostPort = new JSpinner(new SpinnerNumberModel(PORT, 1, 65535, 1));
    private final JSpinner memoryMb = new JSpinner(new SpinnerNumberModel(4096, 1024, 12288, 512));
    private final JTabbedPane tabs = new JTabbedPane();
    private final JLabel status = new JLabel(" ");
    private final JButton localPlay = new JButton();
    private final JButton friendPlay = new JButton();
    private final JButton ownerPlay = new JButton();
    private final JButton hostStart = new JButton();
    private final JButton hostStop = new JButton();
    private final JButton hostJoin = new JButton();
    private final JButton hostShare = new JButton();
    private final JButton friendImport = new JButton();
    private final JButton ownerImport = new JButton();
    private final JButton save = new JButton();
    private final JButton cancel = new JButton();
    private final JPanel content = new JPanel(new BorderLayout(8, 8));
    private final JLabel nicknameLabel = new JLabel();
    private final JLabel memoryLabel = new JLabel();
    private final JLabel friendTargetLabel = new JLabel();
    private final JLabel friendTransportLabel = new JLabel();
    private final JLabel friendPortLabel = new JLabel();
    private final JLabel ownerTargetLabel = new JLabel();
    private final JLabel ownerTransportLabel = new JLabel();
    private final JLabel ownerPortLabel = new JLabel();
    private final JLabel hostPortLabel = new JLabel();
    private final JLabel localNote = new JLabel();
    private final JLabel hostNote = new JLabel();
    private final JLabel friendNote = new JLabel();
    private final JLabel ownerNote = new JLabel();
    private final JPanel commonPanel = new JPanel(new GridBagLayout());
    private volatile Process gameProcess;
    private volatile Process hostProcess;
    private volatile Process tunnelProcess;
    private volatile String hostPortholeCode = "";
    private volatile AtomicBoolean cancelWork = new AtomicBoolean(false);
    private volatile SwingWorker<?, ?> worker;
    private volatile boolean gameRunning;
    private volatile boolean hostRunning;
    private volatile boolean hostStopping;
    private volatile boolean closeAfterWork;
    private FileChannel instanceChannel;
    private FileLock instanceLock;

    static final class AppPaths {
        final Path resources;
        final Path support;
        final Path game;
        final Path host;
        final Path cache;

        AppPaths(Path resources, Path home) {
            this.resources = resources.toAbsolutePath().normalize();
            this.support = home.toAbsolutePath().normalize().resolve("Library/Application Support/RV-1.12.2");
            this.game = support.resolve("client");
            this.host = support.resolve("host");
            this.cache = support.resolve("cache");
        }
    }

    static final class MacPackage {
        int schema;
        String version;
        String gameplayVersion;
        String runtimePlatform;
        String javaVersion;
        String payloadSha256;
        String worldTemplateSha256;
        String serverMainClass;
        List<String> allowedDownloadHosts;
        ServerDownload server;
    }

    static final class ServerDownload {
        String path;
        String url;
        String sha1;
        long size;
    }

    static final class InstallerFiles {
        String mainClass;
        String assetIndex;
        List<DownloadFile> files = new ArrayList<DownloadFile>();
        List<String> classpath = new ArrayList<String>();
    }

    static final class DownloadFile {
        String path;
        String url;
        String sha1;
        @SerializedName("native") boolean nativeFile;
    }

    static final class PackageManifest {
        String version;
        List<ArchiveDigest> archives = new ArrayList<ArchiveDigest>();
        List<ManagedFile> managedFiles = new ArrayList<ManagedFile>();
        List<String> managedModPatterns = new ArrayList<String>();
    }

    static final class ArchiveDigest {
        String path;
        String sha256;
    }

    static final class ManagedFile {
        String path;
        String sha256;
        boolean preserveIfExists;
        boolean existingOnly;
    }

    static final class VendorCatalog {
        int schema;
        String state;
        List<VendorFile> files = new ArrayList<VendorFile>();
    }

    static final class VendorFile {
        String id;
        String path;
        String kind;
        String side;
        String delivery;
        long size;
        String sha256;
        List<String> officialUrls = new ArrayList<String>();
        List<String> expectedModIds = new ArrayList<String>();
        Map<String, String> fml = new LinkedHashMap<String, String>();
    }

    static final class ManagedMods {
        int schema;
        List<ManagedMod> mods = new ArrayList<ManagedMod>();
    }

    static final class ManagedMod {
        String id;
        String path;
        String side;
        String sha256;
        List<String> expectedModIds = new ArrayList<String>();
        Map<String, String> fml = new LinkedHashMap<String, String>();
    }

    static final class ReleaseMetadata {
        String version;
        String vendorCatalogSha256;
        String managedModsSha256;
        Map<String, String> requiredMods = new LinkedHashMap<String, String>();
        Map<String, String> clientRequiredMods = new LinkedHashMap<String, String>();
    }

    static final class PackageBundle {
        final Path resources;
        final MacPackage mac;
        final InstallerFiles installer;
        final PackageManifest manifest;
        final VendorCatalog vendors;
        final ManagedMods managedMods;
        final ReleaseMetadata release;

        PackageBundle(Path resources) throws IOException {
            this.resources = resources.toAbsolutePath().normalize();
            if (Files.isSymbolicLink(this.resources) || !Files.isDirectory(this.resources, LinkOption.NOFOLLOW_LINKS)) throw new IOException("Mac app resources folder is missing or unsafe.");
            this.mac = readJson(this.resources.resolve("macos-package.json"), MacPackage.class, 65536);
            this.installer = readJson(this.resources.resolve("installer-files.json"), InstallerFiles.class, 1048576);
            this.manifest = readJson(this.resources.resolve("package-manifest.json"), PackageManifest.class, 262144);
            this.vendors = readJson(this.resources.resolve("vendor-catalog.json"), VendorCatalog.class, 1048576);
            this.managedMods = readJson(this.resources.resolve("rv-managed-mods.json"), ManagedMods.class, 262144);
            this.release = readJson(this.resources.resolve("release.json"), ReleaseMetadata.class, 65536);
            validateMetadata();
        }

        void validateMetadata() throws IOException {
            if (mac.schema != 1 || !validVersion(mac.version) || !validVersion(mac.gameplayVersion)) throw new IOException("Invalid Mac package version.");
            if (!"mac-x64".equals(mac.runtimePlatform) || mac.javaVersion == null || !mac.javaVersion.matches("1\\.8\\.0_504(?:-b01)?")) throw new IOException("This Mac package requires the pinned Java 8 runtime.");
            if (!validHex(mac.payloadSha256, 64) || mac.worldTemplateSha256 != null && !validHex(mac.worldTemplateSha256, 64)) throw new IOException("Invalid package checksum metadata.");
            if (!"net.minecraft.launchwrapper.Launch".equals(installer.mainClass) || installer.assetIndex == null || installer.assetIndex.isEmpty()) throw new IOException("Invalid Minecraft launch metadata.");
            if (!"net.minecraftforge.fml.relauncher.ServerLaunchWrapper".equals(mac.serverMainClass)) throw new IOException("Invalid Forge server launch metadata.");
            if (mac.server == null || mac.server.path == null || !validRelative(mac.server.path) || !validHex(mac.server.sha1, 40) || mac.server.size < 1 || mac.server.size > 1073741824L) throw new IOException("Invalid server download metadata.");
            if (installer.files == null || installer.files.size() < 1 || installer.files.size() > 20000 || installer.classpath == null || installer.classpath.size() < 1 || installer.classpath.size() > 4096) throw new IOException("Invalid Minecraft file list.");
            if (manifest.managedFiles == null || manifest.managedFiles.size() < 1 || manifest.managedFiles.size() > 20000 || !mac.version.equals(manifest.version) || !mac.version.equals(release.version)) throw new IOException("Mac package and gameplay versions do not match.");
            if (vendors.schema != 1 || vendors.files == null || vendors.files.isEmpty() || vendors.files.size() > 512 || managedMods.schema != 1 || managedMods.mods == null || managedMods.mods.isEmpty() || managedMods.mods.size() > 256 || release.requiredMods == null || release.requiredMods.isEmpty() || release.requiredMods.size() > 256) throw new IOException("Mod compatibility metadata is incomplete.");
            for (Map.Entry<String, String> required : release.requiredMods.entrySet()) if (required.getKey() == null || !required.getKey().matches("^[a-z0-9_.-]{1,128}$") || required.getValue() == null || required.getValue().length() > 128) throw new IOException("Invalid required mod identity.");
            if (!validHex(release.vendorCatalogSha256, 64) || !validHex(release.managedModsSha256, 64)) throw new IOException("Pinned mod catalog hashes are missing.");
            if (!release.vendorCatalogSha256.equalsIgnoreCase(sha256(resources.resolve("vendor-catalog.json"))) || !release.managedModsSha256.equalsIgnoreCase(sha256(resources.resolve("rv-managed-mods.json")))) throw new IOException("Pinned mod catalog files do not match release metadata.");
            if (mac.allowedDownloadHosts == null || mac.allowedDownloadHosts.isEmpty() || mac.allowedDownloadHosts.size() > 64) throw new IOException("Approved download hosts are missing.");
            Set<String> hosts = new HashSet<String>();
            for (String host : mac.allowedDownloadHosts) {
                if (host == null || !host.matches("(?i)^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$") || host.contains("..") || !hosts.add(host.toLowerCase(Locale.ROOT))) throw new IOException("Invalid approved download host.");
            }
            validateDownloadUri(mac.server.url, hosts);
            if (!validHex(mac.payloadSha256, 64) || mac.worldTemplateSha256 != null && !validHex(mac.worldTemplateSha256, 64)) throw new IOException("Invalid package archive hashes.");
            Set<String> files = new HashSet<String>();
            Set<String> nativeFiles = new HashSet<String>();
            for (DownloadFile file : installer.files) {
                validateDownloadFile(file, hosts);
                String lowerPath = file.path.toLowerCase(Locale.ROOT);
                if (lowerPath.endsWith(".dll") || lowerPath.endsWith(".exe") || lowerPath.contains("natives-windows")) throw new IOException("Windows-only files are not allowed in the Mac download list.");
                if (file.nativeFile && !lowerPath.contains("natives-osx")) throw new IOException("A Mac native library has an invalid classifier.");
                String key = file.path.toLowerCase(Locale.ROOT);
                if (!files.add(key)) throw new IOException("Duplicate Minecraft download path.");
                if (file.nativeFile) nativeFiles.add(file.path);
            }
            Set<String> classpath = new HashSet<String>();
            for (String entry : installer.classpath) {
                if (!validRelative(entry) || !files.contains(entry.toLowerCase(Locale.ROOT)) || !classpath.add(entry.toLowerCase(Locale.ROOT))) throw new IOException("Invalid Minecraft classpath entry.");
            }
            boolean assetIndex = false;
            for (DownloadFile file : installer.files) if (file.path.equals("assets/indexes/" + installer.assetIndex + ".json")) assetIndex = true;
            if (!assetIndex) throw new IOException("Minecraft asset index is not pinned in the download list.");
            for (ManagedFile entry : manifest.managedFiles) {
                if (entry == null || !validRelative(entry.path) || !validHex(entry.sha256, 64)) throw new IOException("Invalid managed package entry.");
            }
            Set<String> managedPaths = new HashSet<String>();
            for (ManagedFile entry : manifest.managedFiles) if (!managedPaths.add(entry.path.toLowerCase(Locale.ROOT))) throw new IOException("Duplicate managed package path.");
            Set<String> vendorPaths = new HashSet<String>();
            for (VendorFile vendor : vendors.files) {
                if (vendor == null || vendor.id == null || !vendor.id.matches("^[a-z0-9_.-]{1,128}$") || !validRelative(vendor.path) || !validHex(vendor.sha256, 64) || vendor.size < 0 || vendor.size > 1073741824L || vendor.officialUrls == null || vendor.officialUrls.size() > 16 || vendor.expectedModIds == null) throw new IOException("Invalid vendor catalog entry.");
                if (!("client".equals(vendor.side) || "server".equals(vendor.side) || "both".equals(vendor.side)) || !("bundle".equals(vendor.delivery) || "official-download".equals(vendor.delivery) || "manual".equals(vendor.delivery))) throw new IOException("Invalid vendor compatibility policy.");
                if ("official-download".equals(vendor.delivery) && vendor.officialUrls.isEmpty()) throw new IOException("Official vendor download URL is missing.");
                if (!vendorPaths.add(vendor.path.toLowerCase(Locale.ROOT))) throw new IOException("Duplicate vendor path.");
                if (!managedPaths.contains(vendor.path.toLowerCase(Locale.ROOT))) throw new IOException("Vendor file is not pinned by the package manifest.");
                for (String url : vendor.officialUrls) validateDownloadUri(url, hosts);
            }
            if (!Files.isRegularFile(resources.resolve("payload.zip"), LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(resources.resolve("payload.zip"))) throw new IOException("Mac package payload is missing.");
            if (mac.worldTemplateSha256 != null && (!Files.isRegularFile(resources.resolve("world-template.zip"), LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(resources.resolve("world-template.zip")))) throw new IOException("Mac world template is missing.");
            boolean payloadPinned = false;
            if (manifest.archives == null) throw new IOException("Gameplay archive pins are missing.");
            for (ArchiveDigest archive : manifest.archives) if ("payload.zip".equals(archive.path) && mac.payloadSha256.equalsIgnoreCase(archive.sha256)) payloadPinned = true;
            if (!payloadPinned) throw new IOException("Payload digest does not match the gameplay manifest.");
            if (manifest.archives == null || !mac.payloadSha256.equalsIgnoreCase(sha256(resources.resolve("payload.zip")))) throw new IOException("Payload archive does not match its digest.");
            if (mac.worldTemplateSha256 != null && !mac.worldTemplateSha256.equalsIgnoreCase(sha256(resources.resolve("world-template.zip")))) throw new IOException("World template does not match its digest.");
        }
    }

    static final class Destination {
        final String mode;
        final String target;
        final int port;

        Destination(String mode, String target, int port) {
            this.mode = mode;
            this.target = target;
            this.port = port;
        }

        boolean porthole() { return "porthole".equals(mode); }
        boolean empty() { return target == null || target.trim().isEmpty(); }
    }

    static final class Profile {
        String language = "ru";
        String nickname = "Player";
        int memoryMb = 4096;
        Destination friends = new Destination("direct", "", PORT);
        Destination owner = new Destination("direct", "", PORT);
        int hostPort = PORT;

        Profile copy() {
            Profile p = new Profile();
            p.language = language;
            p.nickname = nickname;
            p.memoryMb = memoryMb;
            p.friends = new Destination(friends.mode, friends.target, friends.port);
            p.owner = new Destination(owner.mode, owner.target, owner.port);
            p.hostPort = hostPort;
            return p;
        }
    }

    static final class ProfileStore {
        final Path path;

        ProfileStore(Path path) { this.path = path.toAbsolutePath().normalize(); }

        Profile load() throws IOException {
            Profile p = new Profile();
            Properties values = new Properties();
            if (Files.exists(path, LinkOption.NOFOLLOW_LINKS)) {
                if (Files.isSymbolicLink(path) || !Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS) || Files.size(path) > 65536) throw new IOException("Invalid launcher settings file.");
                try (InputStream in = Files.newInputStream(path)) { values.load(in); }
            }
            p.language = "en".equals(values.getProperty("language", "ru")) ? "en" : "ru";
            p.nickname = validNickname(values.getProperty("nickname", "Player"));
            p.memoryMb = clamp(parseInt(values.getProperty("memoryMb"), 4096), 1024, 12288);
            p.friends = loadDestination(values, "friends");
            p.owner = loadDestination(values, "owner");
            p.hostPort = clamp(parseInt(values.getProperty("host.port"), PORT), 1, 65535);
            return p;
        }

        void save(Profile p, String scope) throws IOException {
            Properties values = new Properties();
            if (Files.exists(path, LinkOption.NOFOLLOW_LINKS)) {
                if (Files.isSymbolicLink(path) || !Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS) || Files.size(path) > 65536) throw new IOException("Invalid launcher settings file.");
                try (InputStream in = Files.newInputStream(path)) { values.load(in); }
            }
            values.setProperty("language", "en".equals(p.language) ? "en" : "ru");
            values.setProperty("nickname", validNickname(p.nickname));
            values.setProperty("memoryMb", Integer.toString(clamp(p.memoryMb, 1024, 12288)));
            if ("friends".equals(scope) || "all".equals(scope)) saveDestination(values, "friends", p.friends);
            if ("owner".equals(scope) || "all".equals(scope)) saveDestination(values, "owner", p.owner);
            if ("host".equals(scope) || "all".equals(scope)) values.setProperty("host.port", Integer.toString(clamp(p.hostPort, 1, 65535)));
            Path parent = path.getParent();
            if (parent != null) Files.createDirectories(parent);
            Path temp = path.resolveSibling(path.getFileName().toString() + "." + UUID.randomUUID().toString() + ".tmp");
            try {
                try (OutputStream out = Files.newOutputStream(temp, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
                    values.store(out, "RV Launcher");
                }
                moveAtomic(temp, path);
            } finally { Files.deleteIfExists(temp); }
        }

        private static Destination loadDestination(Properties p, String key) {
            String mode = "porthole".equals(p.getProperty(key + ".mode")) ? "porthole" : "direct";
            String target = p.getProperty(key + ".target", "");
            int port = clamp(parseInt(p.getProperty(key + ".port"), PORT), 1, 65535);
            try { return validateDestination(mode, target, port); }
            catch (IllegalArgumentException ignored) { return new Destination("direct", "", PORT); }
        }

        private static void saveDestination(Properties p, String key, Destination d) throws IOException {
            try { d = validateDestination(d.mode, d.target, d.port); }
            catch (IllegalArgumentException error) { throw new IOException("Invalid " + key + " destination.", error); }
            p.setProperty(key + ".mode", d.mode);
            p.setProperty(key + ".target", d.target);
            p.setProperty(key + ".port", Integer.toString(d.port));
        }
    }

    static final class CancelToken {
        final AtomicBoolean cancelled = new AtomicBoolean(false);
        void check() { if (cancelled.get() || Thread.currentThread().isInterrupted()) throw new CancellationException(); }
    }

    static final class Tunnel {
        final Process process;
        final int localPort;
        final Path stderr;
        Tunnel(Process process, int localPort, Path stderr) { this.process = process; this.localPort = localPort; this.stderr = stderr; }
    }

    static final class ModIdentity {
        final Set<String> ids = new LinkedHashSet<String>();
        final Map<String, String> versions = new LinkedHashMap<String, String>();
    }

    private RVLauncher(AppPaths paths, PackageBundle bundle, ProfileStore store, Profile profile) {
        super("RV Warfare");
        this.paths = paths;
        this.bundle = bundle;
        this.store = store;
        this.profile = profile.copy();
        createInterface();
    }

    @Override public void dispose() {
        try { if (instanceLock != null && instanceLock.isValid()) instanceLock.release(); } catch (IOException ignored) { }
        try { if (instanceChannel != null && instanceChannel.isOpen()) instanceChannel.close(); } catch (IOException ignored) { }
        super.dispose();
    }

    public static void main(String[] args) {
        try { UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName()); } catch (Exception ignored) { }
        try {
            Path resources = resourceDirectory(args);
            Path home = Paths.get(System.getProperty("user.home"));
            AppPaths paths = new AppPaths(resources, home);
            ensureNoSymlinkPath(home, paths.support);
            Files.createDirectories(paths.support);
            Path lockPath = paths.support.resolve("launcher.lock");
            ensureNoSymlinkPath(paths.support, lockPath);
            FileChannel channel = FileChannel.open(lockPath, StandardOpenOption.CREATE, StandardOpenOption.WRITE);
            FileLock lock = channel.tryLock();
            if (lock == null) throw new IOException("RV is already running.");
            PackageBundle bundle = new PackageBundle(resources);
            ProfileStore store = new ProfileStore(paths.support.resolve("launcher.properties"));
            Profile profile = store.load();
            SwingUtilities.invokeLater(() -> {
                RVLauncher app = new RVLauncher(paths, bundle, store, profile);
                app.instanceChannel = channel;
                app.instanceLock = lock;
                app.setVisible(true);
            });
        } catch (Exception error) {
            String message = error.getMessage() == null ? "RV could not start." : error.getMessage();
            JOptionPane.showMessageDialog(null, message, "RV Warfare", JOptionPane.ERROR_MESSAGE);
        }
    }

    static Path resourceDirectory(String[] args) throws Exception {
        for (int i = 0; i + 1 < args.length; i++) if ("--resources".equals(args[i])) return Paths.get(args[i + 1]).toAbsolutePath().normalize();
        URI uri = RVLauncher.class.getProtectionDomain().getCodeSource().getLocation().toURI();
        Path location = Paths.get(uri).toAbsolutePath().normalize();
        return Files.isDirectory(location, LinkOption.NOFOLLOW_LINKS) ? location : location.getParent();
    }

    static int parseInt(String value, int fallback) {
        try { return Integer.parseInt(value); } catch (Exception ignored) { return fallback; }
    }

    static int clamp(int value, int low, int high) { return Math.max(low, Math.min(high, value)); }

    static boolean validHex(String value, int length) {
        return value != null && value.length() == length && (length == 40 ? SHA1.matcher(value).matches() : SHA256.matcher(value).matches());
    }

    static boolean validVersion(String value) {
        return value != null && value.length() <= 64 && value.matches("^[0-9]+\\.[0-9]+\\.[0-9]+(?:-[0-9A-Za-z.-]+)?$");
    }

    static String validNickname(String value) {
        String candidate = value == null ? "" : value.trim();
        if (!USERNAME.matcher(candidate).matches()) throw new IllegalArgumentException("Use a Minecraft name with 1 to 16 letters, digits or underscores.");
        return candidate;
    }

    static boolean validRelative(String value) {
        if (value == null || value.isEmpty() || value.length() > 1024 || value.startsWith("/") || value.startsWith("\\") || value.indexOf('\\') >= 0 || value.indexOf(':') >= 0 || value.indexOf('\0') >= 0) return false;
        String[] segments = value.split("/", -1);
        for (String segment : segments) if (segment.isEmpty() || ".".equals(segment) || "..".equals(segment)) return false;
        Path path = Paths.get(value);
        return !path.isAbsolute() && !path.normalize().startsWith("..");
    }

    static Path resolveInside(Path root, String relative) throws IOException {
        if (!validRelative(relative)) throw new IOException("Unsafe path in package: " + relative);
        Path base = root.toAbsolutePath().normalize();
        Path target = base.resolve(relative.replace('/', File.separatorChar)).normalize();
        if (!target.startsWith(base)) throw new IOException("Package path escapes its install folder.");
        ensureNoSymlinkPath(base, target);
        return target;
    }

    static void ensureNoSymlinkPath(Path root, Path target) throws IOException {
        Path base = root.toAbsolutePath().normalize();
        Path destination = target.toAbsolutePath().normalize();
        if (!destination.startsWith(base)) throw new IOException("Path escapes its owner directory.");
        Path current = base;
        if (Files.exists(current, LinkOption.NOFOLLOW_LINKS) && Files.isSymbolicLink(current)) throw new IOException("Symbolic links are not allowed in managed paths.");
        Path relative = base.relativize(destination);
        for (Path component : relative) {
            current = current.resolve(component);
            if (Files.exists(current, LinkOption.NOFOLLOW_LINKS) && Files.isSymbolicLink(current)) throw new IOException("Symbolic links are not allowed in managed paths.");
        }
    }

    static Destination validateDestination(String mode, String target, int port) {
        if (port < 1 || port > 65535) throw new IllegalArgumentException("Port must be between 1 and 65535.");
        String type = mode == null ? "" : mode.trim().toLowerCase(Locale.ROOT);
        if (!"direct".equals(type) && !"porthole".equals(type)) throw new IllegalArgumentException("Choose Direct or Porthole.");
        String value = target == null ? "" : target.trim();
        if (value.isEmpty()) return new Destination(type, "", port);
        if ("porthole".equals(type)) {
            if (value.matches("(?i)^[a-z0-9]{4,16}$")) value = value.toUpperCase(Locale.ROOT);
            else if (value.matches("^peer:[0-9]{17}$") && !value.substring(5).matches("0{17}")) { }
            else if (validLobby(value)) { }
            else throw new IllegalArgumentException("Enter a Porthole code, peer ID or lobby ID.");
            return new Destination(type, value, port);
        }
        if (!"direct".equals(type)) throw new IllegalArgumentException("Choose Direct or Porthole.");
        String host = value;
        int selectedPort = port;
        if (value.startsWith("[")) {
            int close = value.indexOf(']');
            if (close < 0) throw new IllegalArgumentException("Invalid server address.");
            host = value.substring(1, close);
            if (close + 1 < value.length()) {
                if (value.charAt(close + 1) != ':') throw new IllegalArgumentException("Invalid server address.");
                selectedPort = parsePort(value.substring(close + 2));
            }
            if (!host.matches("^[0-9A-Fa-f:.%]+$") || host.indexOf(':') < 0) throw new IllegalArgumentException("Invalid IPv6 address.");
            try { if (!(java.net.InetAddress.getByName(host) instanceof java.net.Inet6Address)) throw new IllegalArgumentException("Invalid IPv6 address."); }
            catch (IOException error) { throw new IllegalArgumentException("Invalid IPv6 address.", error); }
        } else {
            int colon = value.lastIndexOf(':');
            if (colon > 0 && value.indexOf(':') == colon) {
                String suffix = value.substring(colon + 1);
                if (suffix.matches("^[0-9]+$")) { selectedPort = parsePort(suffix); host = value.substring(0, colon); }
            }
            if (!validHost(host)) throw new IllegalArgumentException("Enter an IP address or hostname without a URL path.");
        }
        return new Destination("direct", host, selectedPort);
    }

    static int parsePort(String value) {
        try {
            int result = Integer.parseInt(value);
            if (result < 1 || result > 65535) throw new NumberFormatException();
            return result;
        } catch (Exception error) { throw new IllegalArgumentException("Port must be between 1 and 65535."); }
    }

    static boolean validLobby(String value) {
        if (value == null || !value.matches("^lobby:[0-9]{1,19}$")) return false;
        try { return Long.parseLong(value.substring(6)) > 0; }
        catch (NumberFormatException ignored) { return false; }
    }

    static boolean validHost(String value) {
        if (value == null || value.length() > 253) return false;
        if (value.matches("^[0-9]{1,3}(?:\\.[0-9]{1,3}){3}$")) {
            for (String part : value.split("\\.")) if (Integer.parseInt(part) > 255) return false;
            return true;
        }
        if (value.matches("^[0-9.]+$")) return false;
        if (!value.matches("(?i)^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")) return false;
        for (String label : value.split("\\.")) if (label.length() > 63 || label.isEmpty() || !label.matches("(?i)^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")) return false;
        return true;
    }

    static Destination readInvite(Path invite) throws IOException {
        return readInvite(invite, null);
    }

    static Destination readInvite(Path invite, String expectedVersion) throws IOException {
        if (Files.isSymbolicLink(invite) || !Files.isRegularFile(invite, LinkOption.NOFOLLOW_LINKS) || Files.size(invite) > 4096) throw new IOException("Invalid or oversized RV invitation.");
        byte[] bytes = Files.readAllBytes(invite);
        String text;
        try { text = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString(); }
        catch (CharacterCodingException error) { throw new IOException("Invitation is not valid UTF-8.", error); }
        JsonElement element;
        try { element = new JsonParser().parse(text); } catch (RuntimeException error) { throw new IOException("Invalid RV invitation.", error); }
        if (!element.isJsonObject()) throw new IOException("Invalid RV invitation.");
        JsonObject object = element.getAsJsonObject();
        Set<String> allowed = new HashSet<String>(Arrays.asList("schema", "product", "transport", "target", "port", "version", "label"));
        for (Map.Entry<String, JsonElement> entry : object.entrySet()) if (!allowed.contains(entry.getKey())) throw new IOException("Invitation has unsupported fields.");
        if (!object.has("schema") || jsonInteger(object, "schema") != 1 || !jsonString(object, "product").equals("RV") || !jsonString(object, "transport").equals("porthole")) throw new IOException("Invitation does not belong to RV.");
        String version = jsonString(object, "version");
        if (!validVersion(version)) throw new IOException("Invitation contains an invalid RV version.");
        if (expectedVersion != null && !expectedVersion.equals(version)) throw new IOException("Invitation requires a different RV package version.");
        if (object.has("label") && (jsonString(object, "label").length() > 64 || jsonString(object, "label").matches("(?s).*[\\x00-\\x1f\\x7f].*"))) throw new IOException("Invitation label is invalid.");
        try { return validateDestination("porthole", jsonString(object, "target"), jsonInteger(object, "port")); }
        catch (RuntimeException error) { throw new IOException("Invitation target is invalid.", error); }
    }

    static int jsonInteger(JsonObject object, String key) throws IOException {
        JsonElement value = object.get(key);
        if (value == null || !value.isJsonPrimitive() || !value.getAsJsonPrimitive().isNumber()) throw new IOException("Invitation is missing a numeric " + key + ".");
        try { return value.getAsBigDecimal().intValueExact(); }
        catch (ArithmeticException | NumberFormatException error) { throw new IOException("Invitation has an invalid " + key + ".", error); }
    }

    static String jsonString(JsonObject object, String key) throws IOException {
        JsonElement value = object.get(key);
        if (value == null || !value.isJsonPrimitive() || !value.getAsJsonPrimitive().isString()) throw new IOException("Invitation is missing " + key + ".");
        return value.getAsString();
    }

    static void validateDownloadFile(DownloadFile file, Set<String> hosts) throws IOException {
        if (file == null || !validRelative(file.path) || !validHex(file.sha1, 40)) throw new IOException("Invalid Minecraft download entry.");
        validateDownloadUri(file.url, hosts);
    }

    static URI validateDownloadUri(String value, Set<String> hosts) throws IOException {
        try {
            if (value == null || value.length() > 4096) throw new IOException("Invalid download URL.");
            URI uri = URI.create(value);
            String host = uri.getHost();
            if (!"https".equalsIgnoreCase(uri.getScheme()) || host == null || uri.getUserInfo() != null || (uri.getPort() != -1 && uri.getPort() != 443) || !hosts.contains(host.toLowerCase(Locale.ROOT))) throw new IOException("Download URL is outside the approved HTTPS origins.");
            return uri;
        } catch (IllegalArgumentException error) { throw new IOException("Invalid download URL.", error); }
    }

    static String sha256(Path path) throws IOException { return digest(path, "SHA-256"); }
    static String sha1(Path path) throws IOException { return digest(path, "SHA-1"); }

    static String digest(Path path, String algorithm) throws IOException {
        try {
            MessageDigest md = MessageDigest.getInstance(algorithm);
            try (InputStream in = new DigestInputStream(Files.newInputStream(path), md)) {
                byte[] buffer = new byte[65536];
                while (in.read(buffer) >= 0) { }
            }
            return hex(md.digest());
        } catch (NoSuchAlgorithmException error) { throw new IOException(error); }
    }

    static String hex(byte[] data) {
        StringBuilder result = new StringBuilder(data.length * 2);
        for (byte value : data) result.append(String.format(Locale.ROOT, "%02x", value & 255));
        return result.toString();
    }

    static void moveAtomic(Path source, Path target) throws IOException {
        try { Files.move(source, target, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING); }
        catch (AtomicMoveNotSupportedException error) { Files.move(source, target, StandardCopyOption.REPLACE_EXISTING); }
    }

    static <T> T readJson(Path path, Class<T> type, long maxBytes) throws IOException {
        if (Files.isSymbolicLink(path) || !Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS) || Files.size(path) > maxBytes) throw new IOException("Package metadata is missing or invalid: " + path.getFileName());
        try (Reader reader = new InputStreamReader(Files.newInputStream(path), StandardCharsets.UTF_8)) {
            return JSON.fromJson(reader, type);
        } catch (RuntimeException error) { throw new IOException("Package metadata could not be read: " + path.getFileName(), error); }
    }

    interface Task { void run(CancelToken token) throws Exception; }

    private void createInterface() {
        setDefaultCloseOperation(DO_NOTHING_ON_CLOSE);
        setMinimumSize(new Dimension(700, 480));
        setPreferredSize(new Dimension(800, 560));
        content.setBorder(BorderFactory.createEmptyBorder(12, 14, 10, 14));
        commonPanel.setBorder(BorderFactory.createTitledBorder(""));
        GridBagConstraints common = new GridBagConstraints();
        common.insets = new Insets(4, 5, 4, 8);
        common.anchor = GridBagConstraints.WEST;
        common.gridx = 0;
        common.gridy = 0;
        commonPanel.add(nicknameLabel, common);
        common.gridx = 1;
        common.fill = GridBagConstraints.HORIZONTAL;
        common.weightx = 1;
        commonPanel.add(nickname, common);
        common.gridx = 2;
        common.fill = GridBagConstraints.NONE;
        common.weightx = 0;
        commonPanel.add(memoryLabel, common);
        common.gridx = 3;
        common.fill = GridBagConstraints.HORIZONTAL;
        common.weightx = 0.2;
        commonPanel.add(memoryMb, common);
        common.gridx = 4;
        common.fill = GridBagConstraints.NONE;
        common.weightx = 0;
        commonPanel.add(languageBox, common);
        friendTransport.addItem("Direct");
        friendTransport.addItem("Porthole");
        ownerTransport.addItem("Direct");
        ownerTransport.addItem("Porthole");
        content.add(commonPanel, BorderLayout.NORTH);
        JPanel local = new JPanel(new GridBagLayout());
        addRow(local, 0, localNote, new JLabel(""));
        addRow(local, 1, new JLabel(""), localPlay);
        JPanel friends = new JPanel(new GridBagLayout());
        addRow(friends, 0, friendTransportLabel, friendTransport);
        addRow(friends, 1, friendTargetLabel, friendTarget);
        addRow(friends, 2, friendPortLabel, friendPort);
        addRow(friends, 3, friendNote, friendImport);
        addRow(friends, 4, new JLabel(""), friendPlay);
        JPanel owners = new JPanel(new GridBagLayout());
        addRow(owners, 0, ownerTransportLabel, ownerTransport);
        addRow(owners, 1, ownerTargetLabel, ownerTarget);
        addRow(owners, 2, ownerPortLabel, ownerPort);
        addRow(owners, 3, ownerNote, ownerImport);
        addRow(owners, 4, new JLabel(""), ownerPlay);
        JPanel host = new JPanel(new GridBagLayout());
        addRow(host, 0, hostPortLabel, hostPort);
        addRow(host, 1, hostNote, new JLabel(""));
        addRow(host, 2, new JLabel(""), hostStart);
        addRow(host, 3, new JLabel(""), hostStop);
        addRow(host, 4, new JLabel(""), hostJoin);
        addRow(host, 5, new JLabel(""), hostShare);
        tabs.addTab("", local);
        tabs.addTab("", friends);
        tabs.addTab("", owners);
        tabs.addTab("", host);
        content.add(tabs, BorderLayout.CENTER);
        JPanel bottom = new JPanel(new BorderLayout(8, 4));
        JPanel controls = new JPanel(new FlowLayout(FlowLayout.RIGHT, 6, 0));
        controls.add(cancel);
        controls.add(status);
        controls.add(save);
        bottom.add(controls, BorderLayout.EAST);
        content.add(bottom, BorderLayout.SOUTH);
        setContentPane(content);
        syncFields(profile);
        refreshLanguage();
        languageBox.addActionListener(event -> {
            profile.language = languageBox.getSelectedIndex() == 1 ? "en" : "ru";
            refreshLanguage();
        });
        save.addActionListener(event -> saveFromUi());
        cancel.addActionListener(event -> {
            if (worker != null && !worker.isDone()) {
                cancelWork.set(true);
                setStatus("ru".equals(profile.language) ? "Отменяем операцию…" : "Cancelling operation…");
            }
        });
        localPlay.addActionListener(event -> startPlay("common", null));
        friendPlay.addActionListener(event -> startPlay("friends", null));
        ownerPlay.addActionListener(event -> startPlay("owner", null));
        friendImport.addActionListener(event -> importInvite(friendTarget, friendTransport, friendPort));
        ownerImport.addActionListener(event -> importInvite(ownerTarget, ownerTransport, ownerPort));
        hostStart.addActionListener(event -> startHostFromUi());
        hostStop.addActionListener(event -> runWorker("Stopping server…", token -> stopHost(token)));
        hostJoin.addActionListener(event -> joinHostedServer());
        hostShare.addActionListener(event -> {
            if (!hostPortholeCode.isEmpty()) copyPortholeCode();
            else runWorker("Opening Porthole…", token -> startHostPorthole(token));
        });
        addWindowListener(new WindowAdapter() {
            @Override public void windowClosing(WindowEvent event) { closeRequested(); }
        });
        pack();
        setLocationRelativeTo(null);
        updateButtons();
    }

    private static void addRow(JPanel panel, int row, java.awt.Component label, java.awt.Component field) {
        GridBagConstraints left = new GridBagConstraints();
        left.gridx = 0;
        left.gridy = row;
        left.insets = new Insets(8, 12, 8, 12);
        left.anchor = GridBagConstraints.WEST;
        left.fill = GridBagConstraints.HORIZONTAL;
        left.weightx = 0.25;
        panel.add(label, left);
        GridBagConstraints right = new GridBagConstraints();
        right.gridx = 1;
        right.gridy = row;
        right.insets = new Insets(8, 12, 8, 12);
        right.anchor = GridBagConstraints.WEST;
        right.fill = GridBagConstraints.HORIZONTAL;
        right.weightx = 1;
        panel.add(field, right);
    }

    private void refreshLanguage() {
        boolean ru = "ru".equals(profile.language);
        int friendMode = friendTransport.getSelectedIndex();
        int ownerMode = ownerTransport.getSelectedIndex();
        commonPanel.setBorder(BorderFactory.createTitledBorder(ru ? "Профиль игрока" : "Player profile"));
        nicknameLabel.setText(ru ? "Ник" : "Nickname");
        memoryLabel.setText(ru ? "Память, МБ" : "Memory, MB");
        tabs.setTitleAt(0, ru ? "Одиночная игра" : "Local");
        tabs.setTitleAt(1, ru ? "Друзья" : "Friends");
        tabs.setTitleAt(2, ru ? "Владелец" : "Owner");
        tabs.setTitleAt(3, ru ? "Мой сервер" : "Host my server");
        localNote.setText(ru ? "Запустить одиночную игру на этой сборке." : "Play locally with this RV pack.");
        localPlay.setText(ru ? "Играть" : "Play");
        friendTargetLabel.setText(ru ? "Код Porthole или IP / домен" : "Porthole code or IP / hostname");
        friendTransportLabel.setText(ru ? "Способ подключения" : "Connection type");
        friendTransport.removeAllItems();
        friendTransport.addItem(ru ? "Прямой адрес" : "Direct");
        friendTransport.addItem("Porthole");
        friendTransport.setSelectedIndex(friendMode >= 0 ? friendMode : "porthole".equals(profile.friends.mode) ? 1 : 0);
        friendPortLabel.setText(ru ? "Порт сервера" : "Server port");
        friendNote.setText(ru ? "Отдельный адрес для друзей." : "Saved separately for Friends.");
        friendImport.setText(ru ? "Импорт .rvinvite" : "Import .rvinvite");
        friendPlay.setText(ru ? "Играть с друзьями" : "Play with friends");
        ownerTargetLabel.setText(ru ? "Код Porthole или IP / домен" : "Porthole code or IP / hostname");
        ownerTransportLabel.setText(ru ? "Способ подключения" : "Connection type");
        ownerTransport.removeAllItems();
        ownerTransport.addItem(ru ? "Прямой адрес" : "Direct");
        ownerTransport.addItem("Porthole");
        ownerTransport.setSelectedIndex(ownerMode >= 0 ? ownerMode : "porthole".equals(profile.owner.mode) ? 1 : 0);
        ownerPortLabel.setText(ru ? "Порт сервера" : "Server port");
        ownerNote.setText(ru ? "Адрес владельца хранится отдельно." : "Owner destination is stored separately.");
        ownerImport.setText(ru ? "Импорт .rvinvite" : "Import .rvinvite");
        ownerPlay.setText(ru ? "Играть у владельца" : "Play at owner’s server");
        hostPortLabel.setText(ru ? "Порт собственного сервера" : "Your server port");
        hostNote.setText(ru ? "Свой мир и сервер. Porthole запускается только по кнопке." : "Own server and world. Porthole starts only when requested.");
        hostStart.setText(ru ? "Запустить сервер" : "Start server");
        hostStop.setText(ru ? "Остановить и сохранить мир" : "Stop and save world");
        hostJoin.setText(ru ? "Играть на своём сервере" : "Join my server");
        hostShare.setText(ru ? "Поделиться через Porthole" : "Share with Porthole");
        save.setText(ru ? "Сохранить настройки" : "Save settings");
        cancel.setText(ru ? "Отмена" : "Cancel");
        languageBox.setToolTipText(ru ? "Язык" : "Language");
        setTitle(ru ? "RV Warfare — запуск игры" : "RV Warfare — Game launcher");
        updateButtons();
    }

    private void syncFields(Profile value) {
        nickname.setText(value.nickname);
        memoryMb.setValue(clamp(value.memoryMb, 1024, 12288));
        friendTarget.setText(value.friends.target);
        friendPort.setValue(value.friends.port);
        friendTransport.setSelectedIndex(value.friends.porthole() ? 1 : 0);
        ownerTarget.setText(value.owner.target);
        ownerPort.setValue(value.owner.port);
        ownerTransport.setSelectedIndex(value.owner.porthole() ? 1 : 0);
        hostPort.setValue(value.hostPort);
        languageBox.setSelectedIndex("en".equals(value.language) ? 1 : 0);
    }

    private Profile profileFromUi(String scope) {
        Profile next = profile.copy();
        next.language = languageBox.getSelectedIndex() == 1 ? "en" : "ru";
        next.nickname = validNickname(nickname.getText());
        next.memoryMb = clamp(((Number) memoryMb.getValue()).intValue(), 1024, 12288);
        if ("friends".equals(scope) || "all".equals(scope)) next.friends = readDestinationUi(friendTransport, friendTarget, friendPort);
        if ("owner".equals(scope) || "all".equals(scope)) next.owner = readDestinationUi(ownerTransport, ownerTarget, ownerPort);
        if ("host".equals(scope) || "all".equals(scope)) next.hostPort = clamp(((Number) hostPort.getValue()).intValue(), 1, 65535);
        return next;
    }

    static Destination readDestinationUi(JComboBox<String> mode, JTextField target, JSpinner port) {
        return validateDestination(mode.getSelectedIndex() == 1 ? "porthole" : "direct", target.getText(), ((Number) port.getValue()).intValue());
    }

    private void saveFromUi() {
        try {
            Profile next = profileFromUi("all");
            store.save(next, "all");
            profile = next;
            setStatus(next.language.equals("ru") ? "Настройки сохранены." : "Settings saved.");
        } catch (Exception error) { showError(error); }
    }

    private void importInvite(JTextField target, JComboBox<String> mode, JSpinner port) {
        JFileChooser chooser = new JFileChooser();
        chooser.setFileFilter(new javax.swing.filechooser.FileNameExtensionFilter("RV invitation (*.rvinvite)", "rvinvite"));
        if (chooser.showOpenDialog(this) != JFileChooser.APPROVE_OPTION) return;
        try {
            Destination invite = readInvite(chooser.getSelectedFile().toPath(), bundle.mac.version);
            target.setText(invite.target);
            mode.setSelectedIndex(1);
            port.setValue(invite.port);
            setStatus("ru".equals(profile.language) ? "Приглашение загружено. Нажми «Сохранить настройки» или «Играть»." : "Invitation loaded. Save settings or Play to keep it.");
        } catch (Exception error) { showError(error); }
    }

    private void startPlay(String scope, Destination destination) {
        final Profile next;
        final Destination selected;
        try {
            next = profileFromUi(scope);
            selected = "friends".equals(scope) && destination == null ? readDestinationUi(friendTransport, friendTarget, friendPort) :
                    "owner".equals(scope) && destination == null ? readDestinationUi(ownerTransport, ownerTarget, ownerPort) : destination;
            if (selected != null) {
                if (selected.empty()) throw new IllegalArgumentException("ru".equals(next.language) ? "Сначала укажи адрес сервера." : "Enter the server destination first.");
                if ("friends".equals(scope)) next.friends = selected;
                if ("owner".equals(scope)) next.owner = selected;
            }
            if (gameRunning) throw new IllegalStateException("ru".equals(next.language) ? "Игра уже запущена." : "The game is already running.");
        } catch (Exception error) { showError(error); return; }
        runWorker("ru".equals(next.language) ? "Подготовка игры…" : "Preparing game…", token -> launchClient(token, next, scope, selected));
    }

    private void startHostFromUi() {
        final Profile next;
        try {
            next = profileFromUi("host");
            if (hostRunning) throw new IllegalStateException("ru".equals(next.language) ? "Сервер уже запущен." : "The server is already running.");
            if (!acceptEula(next.language)) return;
        } catch (Exception error) { showError(error); return; }
        runWorker("ru".equals(next.language) ? "Подготовка сервера…" : "Preparing server…", token -> launchHost(token, next));
    }

    private void joinHostedServer() {
        try { startPlay("common", new Destination("direct", "127.0.0.1", readServerPort(paths.host.resolve("server.properties")))); }
        catch (Exception error) { showError(error); }
    }

    private boolean acceptEula(String language) {
        Path file = paths.host.resolve("eula.txt");
        if (Files.isRegularFile(file, LinkOption.NOFOLLOW_LINKS) && !Files.isSymbolicLink(file)) {
            try { if (Files.readAllLines(file, StandardCharsets.UTF_8).contains("eula=true")) return true; }
            catch (IOException ignored) { }
        }
        int answer = JOptionPane.showConfirmDialog(this,
                "ru".equals(language) ? "Для запуска сервера нужно принять Minecraft EULA. Согласен с https://aka.ms/MinecraftEULA?" : "Starting the server requires accepting the Minecraft EULA. Do you agree to https://aka.ms/MinecraftEULA?",
                "Minecraft EULA", JOptionPane.YES_NO_OPTION, JOptionPane.QUESTION_MESSAGE);
        return answer == JOptionPane.YES_OPTION;
    }

    private void runWorker(String message, Task action) {
        if (worker != null && !worker.isDone()) return;
        final CancelToken token = new CancelToken();
        cancelWork = token.cancelled;
        setStatus(message);
        SwingWorker<Void, String> next = new SwingWorker<Void, String>() {
            @Override protected Void doInBackground() throws Exception { action.run(token); return null; }
            @Override protected void done() {
                worker = null;
                try { get(); }
                catch (InterruptedException error) { Thread.currentThread().interrupt(); showError(error); }
                catch (ExecutionException error) { Throwable cause = error.getCause(); if (!(cause instanceof CancellationException)) showError(cause); }
                finally {
                    updateButtons();
                    if (closeAfterWork) {
                        closeAfterWork = false;
                        if (hostRunning || gameRunning) closeRequested(); else dispose();
                    }
                }
            }
        };
        worker = next;
        updateButtons();
        next.execute();
    }

    private void setStatus(String value) {
        SwingUtilities.invokeLater(() -> status.setText(value == null || value.isEmpty() ? " " : value));
    }

    private void showError(Throwable error) {
        String message = error == null || error.getMessage() == null ? ("ru".equals(profile.language) ? "Операция не выполнена." : "The operation failed.") : error.getMessage();
        SwingUtilities.invokeLater(() -> JOptionPane.showMessageDialog(this, message, "RV Warfare", JOptionPane.ERROR_MESSAGE));
    }

    private void updateButtons() {
        if (!SwingUtilities.isEventDispatchThread()) { SwingUtilities.invokeLater(this::updateButtons); return; }
        boolean busy = worker != null && !worker.isDone();
        if (!hostPortholeCode.isEmpty() && (tunnelProcess == null || !tunnelProcess.isAlive())) {
            hostPortholeCode = "";
            tunnelProcess = null;
        }
        localPlay.setEnabled(!busy && !gameRunning);
        friendPlay.setEnabled(!busy && !gameRunning);
        ownerPlay.setEnabled(!busy && !gameRunning);
        hostJoin.setEnabled(!busy && hostRunning && !gameRunning);
        hostStart.setEnabled(!busy && !hostRunning);
        hostStop.setEnabled(!busy && hostRunning && !hostStopping);
        hostShare.setEnabled(!busy && hostRunning && (tunnelProcess == null || !hostPortholeCode.isEmpty()));
        if (!hostPortholeCode.isEmpty()) hostShare.setText("ru".equals(profile.language) ? "Копировать код Porthole" : "Copy Porthole code");
        else hostShare.setText("ru".equals(profile.language) ? "Поделиться через Porthole" : "Share with Porthole");
        save.setEnabled(!busy);
        cancel.setEnabled(busy);
        hostPort.setEnabled(!busy && !hostRunning);
    }

    private void closeRequested() {
        if (worker != null && !worker.isDone()) {
            int answer = JOptionPane.showConfirmDialog(this,
                    "ru".equals(profile.language) ? "Отменить текущую операцию перед выходом?" : "Cancel the current operation before quitting?",
                    "RV Warfare", JOptionPane.YES_NO_OPTION, JOptionPane.QUESTION_MESSAGE);
            if (answer == JOptionPane.YES_OPTION) {
                closeAfterWork = true;
                cancelWork.set(true);
            }
            return;
        }
        if (hostRunning) {
            int answer = JOptionPane.showConfirmDialog(this,
                    "ru".equals(profile.language) ? "Остановить сервер и сохранить мир перед выходом?" : "Stop the server and save the world before quitting?",
                    "RV Warfare", JOptionPane.YES_NO_CANCEL_OPTION, JOptionPane.QUESTION_MESSAGE);
            if (answer != JOptionPane.YES_OPTION) return;
            closeAfterWork = true;
            runWorker("ru".equals(profile.language) ? "Сохраняем мир…" : "Saving world…", token -> stopHost(token));
            return;
        }
        if (gameRunning) {
            JOptionPane.showMessageDialog(this, "ru".equals(profile.language) ? "Сначала закрой игру, затем выйди из RV." : "Close the game before quitting RV.");
            return;
        }
        dispose();
    }

    private static void writeAtomic(Path target, byte[] bytes) throws IOException {
        Path parent = target.getParent();
        if (parent != null) Files.createDirectories(parent);
        Path temp = target.resolveSibling(target.getFileName().toString() + "." + UUID.randomUUID().toString() + ".tmp");
        try {
            try (OutputStream out = Files.newOutputStream(temp, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) { out.write(bytes); }
            moveAtomic(temp, target);
        } finally { Files.deleteIfExists(temp); }
    }

    private void launchClient(CancelToken token, Profile next, String scope, Destination destination) throws Exception {
        installClient(token, true);
        token.check();
        Path java = javaExecutable();
        Tunnel tunnel = null;
        String server = null;
        int port = PORT;
        if (destination != null) {
            port = destination.port;
            if (destination.porthole()) {
                tunnel = startTunnel(token, destination, next.language);
                tunnelProcess = tunnel.process;
                server = "127.0.0.1";
                port = tunnel.localPort;
            } else server = destination.target;
        }
        try {
            token.check();
            List<String> command = clientCommand(java, paths.game, bundle.installer, next.nickname, next.memoryMb, server, port);
            Path log = paths.support.resolve("client-launch.log");
            ProcessBuilder builder = new ProcessBuilder(command);
            builder.directory(paths.game.toFile());
            builder.redirectErrorStream(true);
            builder.redirectOutput(log.toFile());
            Process process = builder.start();
            gameProcess = process;
            gameRunning = true;
            Tunnel ownedTunnel = tunnel;
            Thread watcher = new Thread(() -> {
                try { process.waitFor(); }
                catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
                finally {
                    if (ownedTunnel != null) stopOwned(ownedTunnel.process);
                    if (ownedTunnel != null && tunnelProcess == ownedTunnel.process) tunnelProcess = null;
                    if (gameProcess == process) { gameProcess = null; gameRunning = false; updateButtons(); }
                }
            }, "RV-game-watch");
            watcher.setDaemon(true);
            watcher.start();
            if (!process.waitFor(750, TimeUnit.MILLISECONDS) || process.isAlive()) {
                store.save(next, scope);
                profile = next;
                setStatus("ru".equals(next.language) ? "Игра запущена." : "Game started.");
                updateButtons();
                return;
            }
            gameRunning = false;
            gameProcess = null;
            if (tunnel != null) stopOwned(tunnel.process);
            throw new IOException("ru".equals(next.language) ? "Minecraft сразу завершился. Подробности: " + log : "Minecraft exited during startup. Details: " + log);
        } catch (Exception error) {
            if (tunnel != null && !gameRunning) {
                stopOwned(tunnel.process);
                if (tunnelProcess == tunnel.process) tunnelProcess = null;
            }
            throw error;
        }
    }

    static List<String> clientCommand(Path java, Path game, InstallerFiles installer, String username, int memoryMb, String server, int port) throws IOException {
        if (installer == null || installer.classpath == null || installer.classpath.isEmpty()) throw new IOException("Minecraft classpath is empty.");
        List<String> args = new ArrayList<String>();
        args.add(java.toAbsolutePath().normalize().toString());
        args.add("-XstartOnFirstThread");
        args.add("-Xms512M");
        args.add("-Xmx" + clamp(memoryMb, 1024, 12288) + "M");
        args.add("-Dfile.encoding=UTF-8");
        args.add("-Djava.library.path=" + game.resolve("natives").toAbsolutePath().normalize());
        args.add("-Dminecraft.launcher.brand=RV");
        List<String> classpath = new ArrayList<String>();
        for (String entry : installer.classpath) classpath.add(resolveInside(game, entry).toString());
        args.add("-cp");
        args.add(join(classpath, File.pathSeparator));
        args.add(installer.mainClass);
        args.add("--username"); args.add(validNickname(username));
        args.add("--version"); args.add("Warfare-" + EXPECTED_GAME_VERSION);
        args.add("--gameDir"); args.add(game.toAbsolutePath().normalize().toString());
        args.add("--assetsDir"); args.add(game.resolve("assets").toAbsolutePath().normalize().toString());
        args.add("--assetIndex"); args.add(installer.assetIndex);
        args.add("--uuid"); args.add(offlineUuid(username));
        args.add("--accessToken"); args.add("0");
        args.add("--userType"); args.add("legacy");
        args.add("--tweakClass"); args.add(EXPECTED_PLAY_TWEAKER);
        args.add("--versionType"); args.add("Forge");
        if (server != null && !server.trim().isEmpty()) {
            if (port < 1 || port > 65535) throw new IOException("Invalid game server port.");
            args.add("--server"); args.add(server);
            args.add("--port"); args.add(Integer.toString(port));
        }
        return args;
    }

    static String offlineUuid(String username) {
        try {
            byte[] bytes = MessageDigest.getInstance("MD5").digest(("OfflinePlayer:" + validNickname(username)).getBytes(StandardCharsets.UTF_8));
            bytes[6] = (byte) ((bytes[6] & 15) | 48);
            bytes[8] = (byte) ((bytes[8] & 63) | 128);
            ByteBuffer value = ByteBuffer.wrap(bytes);
            return new UUID(value.getLong(), value.getLong()).toString();
        } catch (NoSuchAlgorithmException error) { throw new IllegalStateException(error); }
    }

    static String join(List<String> values, String separator) {
        StringBuilder result = new StringBuilder();
        for (String value : values) { if (result.length() > 0) result.append(separator); result.append(value); }
        return result.toString();
    }

    private Path javaExecutable() throws IOException {
        Path home = Paths.get(System.getProperty("java.home")).toAbsolutePath().normalize();
        Path java = home.resolve("bin").resolve("java");
        if (!Files.isRegularFile(java, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(java) || !Files.isExecutable(java)) throw new IOException("The bundled Java 8 runtime is missing or cannot run.");
        return java;
    }

    private void installClient(CancelToken token, boolean assets) throws Exception {
        ensureDirectory(paths.game);
        Map<String, ManagedFile> managed = new HashMap<String, ManagedFile>();
        for (ManagedFile entry : bundle.manifest.managedFiles) managed.put(entry.path.toLowerCase(Locale.ROOT), entry);
        Path payload = bundle.resources.resolve("payload.zip");
        SafeZip.extract(payload, paths.game, (relative, target) -> {
            token.check();
            if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
                if (Files.isSymbolicLink(target) || !Files.isRegularFile(target, LinkOption.NOFOLLOW_LINKS)) throw new IOException("A managed game file was replaced by an unsafe filesystem entry.");
                ManagedFile entry = managed.get(relative.toLowerCase(Locale.ROOT));
                if (entry == null || preserveExistingConfiguration(relative) || entry.preserveIfExists || entry.existingOnly && !Files.isDirectory(paths.game.resolve("mcheli_addons/default"), LinkOption.NOFOLLOW_LINKS)) return false;
            } else {
                ManagedFile entry = managed.get(relative.toLowerCase(Locale.ROOT));
                if (entry != null && entry.existingOnly && !Files.isDirectory(paths.game.resolve("mcheli_addons/default"), LinkOption.NOFOLLOW_LINKS)) return false;
            }
            return true;
        }, MAX_PAYLOAD_ARCHIVE, 6L * 1024 * 1024 * 1024, token);
        int totalFiles = 0;
        for (DownloadFile file : bundle.installer.files) if (assets || !file.path.startsWith("assets/")) totalFiles++;
        int completed = 0;
        for (DownloadFile file : bundle.installer.files) {
            token.check();
            if (!assets && file.path.startsWith("assets/")) continue;
            completed++;
            if (completed % 10 == 0 || completed == totalFiles) setStatus(("ru".equals(profile.language) ? "Загрузка файлов " : "Downloading files ") + completed + "/" + totalFiles);
            downloadVerified(paths.game, file.path, file.url, file.sha1, MAX_DOWNLOAD_BYTES, -1, token);
        }
        installVendors(paths.game, token);
        extractNatives(paths.game, token);
        installLocalWorld(token);
        token.check();
    }

    static boolean preserveExistingConfiguration(String relative) {
        String lower = relative.toLowerCase(Locale.ROOT);
        return lower.startsWith("config/") || lower.equals("modularwarfare/mod_config.json");
    }

    private void extractNatives(Path game, CancelToken token) throws IOException {
        Path nativeRoot = game.resolve("natives");
        ensureDirectory(nativeRoot);
        for (DownloadFile file : bundle.installer.files) {
            if (!file.nativeFile) continue;
            token.check();
            Path archive = resolveInside(game, file.path);
            SafeZip.extract(archive, nativeRoot, (relative, target) -> {
                String lower = relative.toLowerCase(Locale.ROOT);
                return lower.endsWith(".dylib") || lower.endsWith(".jnilib") || lower.endsWith(".so");
            }, MAX_DOWNLOAD_BYTES, 1073741824L, token);
        }
    }

    private void installLocalWorld(CancelToken token) throws IOException {
        if (bundle.mac.worldTemplateSha256 == null) return;
        Path saves = paths.game.resolve("saves");
        Path destination = saves.resolve("Battlefield-Extended");
        ensureNoSymlinkPath(paths.game, destination);
        if (Files.exists(destination, LinkOption.NOFOLLOW_LINKS)) return;
        ensureDirectory(saves);
        Path temporary = saves.resolve(".rv-world-" + UUID.randomUUID().toString());
        ensureDirectory(temporary);
        try {
            SafeZip.extract(bundle.resources.resolve("world-template.zip"), temporary, (relative, target) -> true, 1073741824L, 2147483648L, token);
            Path selected = temporary;
            if (!Files.isRegularFile(temporary.resolve("level.dat"), LinkOption.NOFOLLOW_LINKS)) {
                List<Path> children = new ArrayList<Path>();
                try (DirectoryStream<Path> stream = Files.newDirectoryStream(temporary)) { for (Path child : stream) children.add(child); }
                if (children.size() == 1 && Files.isDirectory(children.get(0), LinkOption.NOFOLLOW_LINKS) && Files.isRegularFile(children.get(0).resolve("level.dat"), LinkOption.NOFOLLOW_LINKS)) selected = children.get(0);
                else throw new IOException("RV world template does not contain a Minecraft world.");
            }
            if (Files.exists(destination, LinkOption.NOFOLLOW_LINKS)) return;
            moveAtomic(selected, destination);
        } finally { deleteTree(temporary); }
    }

    private static void ensureDirectory(Path path) throws IOException {
        Path absolute = path.toAbsolutePath().normalize();
        Path parent = absolute.getParent();
        if (parent != null && Files.exists(parent, LinkOption.NOFOLLOW_LINKS) && Files.isSymbolicLink(parent)) throw new IOException("Symbolic links are not allowed in RV data folders.");
        if (Files.exists(absolute, LinkOption.NOFOLLOW_LINKS)) {
            if (Files.isSymbolicLink(absolute) || !Files.isDirectory(absolute, LinkOption.NOFOLLOW_LINKS)) throw new IOException("An RV data folder contains an unsafe filesystem entry.");
        } else Files.createDirectories(absolute);
        if (Files.isSymbolicLink(absolute)) throw new IOException("Symbolic links are not allowed in RV data folders.");
    }

    private static void deleteTree(Path root) throws IOException {
        if (!Files.exists(root, LinkOption.NOFOLLOW_LINKS)) return;
        if (Files.isSymbolicLink(root)) throw new IOException("Refusing to remove a symbolic link.");
        if (Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS)) {
            try (DirectoryStream<Path> stream = Files.newDirectoryStream(root)) { for (Path child : stream) deleteTree(child); }
        }
        Files.deleteIfExists(root);
    }

    private void downloadVerified(Path root, String relative, String source, String digest, long limit, long expectedSize, CancelToken token) throws IOException {
        downloadVerified(root, relative, source, digest, "SHA-1", limit, expectedSize, token);
    }

    private void downloadVerified(Path root, String relative, String source, String expectedDigest, String algorithm, long limit, long expectedSize, CancelToken token) throws IOException {
        Path target = resolveInside(root, relative);
        Path parent = target.getParent();
        ensureDirectory(parent);
        if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
            if (Files.isSymbolicLink(target) || !Files.isRegularFile(target, LinkOption.NOFOLLOW_LINKS)) throw new IOException("Unsafe existing download path: " + relative);
            if ((expectedSize < 0 || Files.size(target) == expectedSize) && digest(target, algorithm).equalsIgnoreCase(expectedDigest)) return;
        }
        Set<String> hosts = new HashSet<String>();
        for (String host : bundle.mac.allowedDownloadHosts) hosts.add(host.toLowerCase(Locale.ROOT));
        URI current = validateDownloadUri(source, hosts);
        Path temporary = parent.resolve(target.getFileName().toString() + "." + UUID.randomUUID().toString() + ".partial");
        HttpURLConnection connection = null;
        long total = 0;
        try {
            for (int redirect = 0; redirect <= 5; redirect++) {
                token.check();
                URLConnection raw = current.toURL().openConnection();
                raw.setConnectTimeout(15000);
                raw.setReadTimeout(30000);
                if (!(raw instanceof HttpURLConnection)) throw new IOException("Unsupported download connection.");
                connection = (HttpURLConnection) raw;
                connection.setInstanceFollowRedirects(false);
                int code = connection.getResponseCode();
                if (code >= 300 && code < 400) {
                    String location = connection.getHeaderField("Location");
                    connection.disconnect();
                    connection = null;
                    if (location == null || redirect == 5) throw new IOException("Download redirected too many times.");
                    current = validateDownloadUri(current.resolve(location).toString(), hosts);
                    continue;
                }
                if (code != 200) throw new IOException("Download failed with HTTP " + code + ".");
                try (InputStream in = new BufferedInputStream(connection.getInputStream()); OutputStream out = new BufferedOutputStream(Files.newOutputStream(temporary, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE))) {
                    byte[] buffer = new byte[65536];
                    int count;
                    while ((count = in.read(buffer)) >= 0) {
                        token.check();
                        total += count;
                        if (total > limit || expectedSize >= 0 && total > expectedSize) throw new IOException("Downloaded file exceeds its pinned size.");
                        out.write(buffer, 0, count);
                    }
                }
                connection.disconnect();
                connection = null;
                if (expectedSize >= 0 && total != expectedSize) throw new IOException("Downloaded file size differs from its pin.");
                if (!digest(temporary, algorithm).equalsIgnoreCase(expectedDigest)) throw new IOException("Downloaded file failed " + algorithm + " verification.");
                moveAtomic(temporary, target);
                return;
            }
            throw new IOException("Download redirect was not resolved.");
        } finally {
            if (connection != null) connection.disconnect();
            Files.deleteIfExists(temporary);
        }
    }

    private void launchHost(CancelToken token, Profile next) throws Exception {
        ensureDirectory(paths.host);
        ensureNoSymlinkPath(paths.support, paths.host);
        installClient(token, false);
        installHostPackage(token);
        int selectedPort = next.hostPort;
        testAvailablePort(selectedPort);
        Path eulaFile = paths.host.resolve("eula.txt");
        ensureNoSymlinkPath(paths.host, eulaFile);
        writeAtomic(eulaFile, "# Minecraft EULA accepted in RV launcher\neula=true\n".getBytes(StandardCharsets.UTF_8));
        configureServerPort(selectedPort);
        downloadVerified(paths.host, bundle.mac.server.path, bundle.mac.server.url, bundle.mac.server.sha1, bundle.mac.server.size, bundle.mac.server.size, token);
        List<String> command = serverCommand(javaExecutable(), paths.game, paths.host, bundle.installer, bundle.mac.server.path, bundle.mac.serverMainClass, next.memoryMb);
        Path log = paths.host.resolve("server.log");
        Process process;
        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(paths.host.toFile());
        builder.redirectErrorStream(true);
        builder.redirectOutput(log.toFile());
        long startedMillis = System.currentTimeMillis();
        process = builder.start();
        hostProcess = process;
        hostRunning = true;
        hostStopping = false;
        updateButtons();
        try {
            waitForServer(token, process, paths.host.resolve("logs/latest.log"), selectedPort, startedMillis);
            store.save(next, "host");
            profile = next;
            setStatus("ru".equals(next.language) ? "Сервер готов. Мир сохранится при остановке." : "Server is ready. The world will be saved when stopped.");
        } catch (Exception error) {
            try { stopHost(new CancelToken()); } catch (Exception stopError) { error.addSuppressed(stopError); }
            throw error;
        }
    }

    static List<String> serverCommand(Path java, Path gameRoot, Path hostRoot, InstallerFiles installer, String serverPath, String mainClass, int memoryMb) throws IOException {
        if (!"net.minecraftforge.fml.relauncher.ServerLaunchWrapper".equals(mainClass) || !"net.minecraft.launchwrapper.Launch".equals(installer.mainClass)) throw new IOException("Unsupported Forge server launch metadata.");
        List<String> classpath = new ArrayList<String>();
        for (String entry : installer.classpath) {
            if (entry.matches("(?i)^versions/1\\.12\\.2/1\\.12\\.2\\.jar$")) continue;
            classpath.add(resolveInside(gameRoot, entry).toString());
        }
        Path server = resolveInside(hostRoot, serverPath);
        classpath.add(server.toString());
        List<String> args = new ArrayList<String>();
        args.add(java.toAbsolutePath().normalize().toString());
        args.add("-Xms512M");
        args.add("-Xmx" + clamp(memoryMb, 1024, 12288) + "M");
        args.add("-Dfile.encoding=UTF-8");
        args.add("-cp");
        args.add(join(classpath, File.pathSeparator));
        args.add(mainClass);
        args.add("--tweakClass"); args.add("net.minecraftforge.fml.common.launcher.FMLServerTweaker");
        args.add("--gameDir"); args.add(hostRoot.toAbsolutePath().normalize().toString());
        args.add("nogui");
        return args;
    }

    private void installHostPackage(CancelToken token) throws IOException {
        Set<String> serverPaths = requiredServerModPaths(bundle);
        Map<String, ManagedFile> managed = new HashMap<String, ManagedFile>();
        for (ManagedFile item : bundle.manifest.managedFiles) managed.put(item.path.toLowerCase(Locale.ROOT), item);
        SafeZip.extract(bundle.resources.resolve("payload.zip"), paths.host, (relative, target) -> {
            token.check();
            String lower = relative.toLowerCase(Locale.ROOT);
            if (lower.startsWith("mods/")) {
                if (!serverPaths.contains(relative)) return false;
            } else if (!(lower.startsWith("config/") || lower.startsWith("mcheli_addons/") || lower.equals("server.properties"))) return false;
            if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
                if (Files.isSymbolicLink(target) || !Files.isRegularFile(target, LinkOption.NOFOLLOW_LINKS)) throw new IOException("Unsafe existing host file: " + relative);
                if (!lower.startsWith("mods/")) return false;
                ManagedFile item = managed.get(lower);
                if (item != null && sha256(target).equalsIgnoreCase(item.sha256)) return false;
                throw new IOException("A server mod differs from the pinned package; it was preserved: " + relative);
            }
            return true;
        }, 3L * 1024 * 1024 * 1024, 6L * 1024 * 1024 * 1024, token);
        for (String relative : serverPaths) {
            ManagedFile item = managed.get(relative.toLowerCase(Locale.ROOT));
            Path installed = resolveInside(paths.host, relative);
            String expectedHash = item == null ? expectedVendorHash(relative) : item.sha256;
            if (!Files.exists(installed, LinkOption.NOFOLLOW_LINKS)) {
                Path clientMod = resolveInside(paths.game, relative);
                if (!Files.isRegularFile(clientMod, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(clientMod) || !sha256(clientMod).equalsIgnoreCase(expectedHash)) throw new IOException("A required server mod is missing from the verified client package: " + relative);
                ensureDirectory(installed.getParent());
                Path temporary = installed.resolveSibling(installed.getFileName().toString() + "." + UUID.randomUUID().toString() + ".part");
                try { Files.copy(clientMod, temporary); moveAtomic(temporary, installed); }
                finally { Files.deleteIfExists(temporary); }
            }
            if (expectedHash == null || !Files.isRegularFile(installed, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(installed) || !sha256(installed).equalsIgnoreCase(expectedHash)) throw new IOException("A required server mod is missing or changed: " + relative);
        }
        if (bundle.mac.worldTemplateSha256 != null) installHostWorld(token);
    }

    private String expectedVendorHash(String path) {
        for (VendorFile vendor : bundle.vendors.files) if (vendor.path.equals(path)) return vendor.sha256;
        return null;
    }

    private void installVendors(Path root, CancelToken token) throws IOException {
        for (VendorFile vendor : bundle.vendors.files) {
            token.check();
            Path target = resolveInside(root, vendor.path);
            if (Files.isRegularFile(target, LinkOption.NOFOLLOW_LINKS) && !Files.isSymbolicLink(target) && Files.size(target) == vendor.size && sha256(target).equalsIgnoreCase(vendor.sha256)) continue;
            if ("manual".equalsIgnoreCase(vendor.delivery)) continue;
            if (!"official-download".equalsIgnoreCase(vendor.delivery)) {
                if (Files.isRegularFile(target, LinkOption.NOFOLLOW_LINKS)) continue;
                throw new IOException("Vendor file is missing from the pinned package: " + vendor.path);
            }
            if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
                if (Files.isSymbolicLink(target) || !Files.isRegularFile(target, LinkOption.NOFOLLOW_LINKS)) throw new IOException("Unsafe managed mod path: " + vendor.path);
                Path backup = paths.support.resolve("backups").resolve("vendor-" + System.currentTimeMillis()).resolve(vendor.path);
                ensureNoSymlinkPath(paths.support, backup);
                ensureDirectory(backup.getParent());
                Files.copy(target, backup);
            }
            IOException failure = null;
            boolean installed = false;
            for (String url : vendor.officialUrls) {
                try {
                    downloadVerified(root, vendor.path, url, vendor.sha256, "SHA-256", Math.max(vendor.size, 1), vendor.size, token);
                    installed = true;
                    break;
                } catch (IOException error) { failure = error; }
            }
            if (!installed) throw new IOException("Could not download the verified vendor mod " + vendor.id + ".", failure);
        }
    }

    static Set<String> requiredServerModPaths(PackageBundle bundle) throws IOException {
        Set<String> required = new LinkedHashSet<String>(bundle.release.requiredMods.keySet());
        Set<String> serverDependencies = new LinkedHashSet<String>(Arrays.asList("mixinbooter", "modularui", "elegant_networking", "brigo", "worldedit"));
        Set<String> clientOnly = new HashSet<String>(Arrays.asList("ambientsounds", "mousetweaks", "mcgltf", "jei", "journeymap", "worldeditcui", "worldeditcuife3", "optifine"));
        Set<String> wanted = new HashSet<String>(required);
        wanted.addAll(serverDependencies);
        Set<String> selectedPaths = new LinkedHashSet<String>();
        Set<String> foundIds = new HashSet<String>();
        Map<String, VendorFile> vendorsByPath = new HashMap<String, VendorFile>();
        for (VendorFile file : bundle.vendors.files) {
            vendorsByPath.put(file.path, file);
            if ("server".equalsIgnoreCase(file.side) || "both".equalsIgnoreCase(file.side)) {
                selectedPaths.add(file.path);
                foundIds.addAll(file.expectedModIds);
            }
        }
        for (ManagedMod file : bundle.managedMods.mods) {
            if (!"server".equalsIgnoreCase(file.side) && !"both".equalsIgnoreCase(file.side)) continue;
            selectedPaths.add(file.path);
            foundIds.addAll(file.expectedModIds);
        }
        Path payload = bundle.resources.resolve("payload.zip");
        try (ZipFile archive = new ZipFile(payload.toFile())) {
            java.util.Enumeration<? extends ZipEntry> entries = archive.entries();
            while (entries.hasMoreElements()) {
                ZipEntry entry = entries.nextElement();
                String path = entry.getName();
                if (entry.isDirectory() || !path.startsWith("mods/") || !path.toLowerCase(Locale.ROOT).endsWith(".jar")) continue;
                VendorFile vendor = vendorsByPath.get(path);
                if (vendor != null && ("client".equalsIgnoreCase(vendor.side))) continue;
                Set<String> ids = modIds(archive, entry);
                boolean blocked = false;
                for (String id : ids) if (clientOnly.contains(id.toLowerCase(Locale.ROOT))) blocked = true;
                if (blocked) continue;
                boolean selected = selectedPaths.contains(path);
                for (String id : ids) if (wanted.contains(id.toLowerCase(Locale.ROOT))) selected = true;
                if (selected) {
                    selectedPaths.add(path);
                    foundIds.addAll(ids);
                }
            }
        }
        if (!foundIds.containsAll(required)) {
            Set<String> missing = new LinkedHashSet<String>(required);
            missing.removeAll(foundIds);
            throw new IOException("Server package is missing required mod IDs: " + join(new ArrayList<String>(missing), ", "));
        }
        for (String dependency : serverDependencies) if (!foundIds.contains(dependency)) throw new IOException("Server package is missing a pinned dependency: " + dependency);
        return selectedPaths;
    }

    private static Set<String> modIds(ZipFile outer, ZipEntry jar) throws IOException {
        Set<String> ids = new LinkedHashSet<String>();
        try (InputStream raw = outer.getInputStream(jar); ZipInputStream nested = new ZipInputStream(new BufferedInputStream(raw))) {
            ZipEntry entry;
            while ((entry = nested.getNextEntry()) != null) {
                if ("mcmod.info".equalsIgnoreCase(entry.getName()) || "META-INF/mods.toml".equalsIgnoreCase(entry.getName())) {
                    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                    byte[] buffer = new byte[8192];
                    int count;
                    while ((count = nested.read(buffer)) >= 0) {
                        if (bytes.size() + count > 1048576) throw new IOException("Mod metadata exceeds its supported size.");
                        bytes.write(buffer, 0, count);
                    }
                    JsonElement metadata;
                    try { metadata = new JsonParser().parse(new String(bytes.toByteArray(), StandardCharsets.UTF_8)); }
                    catch (RuntimeException error) { throw new IOException("A packaged mod has invalid compatibility metadata.", error); }
                    collectModIds(metadata, ids);
                    return ids;
                }
                nested.closeEntry();
            }
        } catch (java.util.zip.ZipException error) { throw new IOException("A packaged mod archive is invalid: " + jar.getName(), error); }
        return ids;
    }

    private static void collectModIds(JsonElement value, Set<String> ids) {
        if (value == null || value.isJsonNull()) return;
        if (value.isJsonArray()) { for (JsonElement item : value.getAsJsonArray()) collectModIds(item, ids); return; }
        if (!value.isJsonObject()) return;
        JsonObject object = value.getAsJsonObject();
        JsonElement id = object.get("modid");
        if (id != null && id.isJsonPrimitive() && id.getAsJsonPrimitive().isString()) {
            String candidate = id.getAsString().toLowerCase(Locale.ROOT);
            if (candidate.matches("^[a-z0-9_.-]{1,128}$")) ids.add(candidate);
        }
        for (Map.Entry<String, JsonElement> child : object.entrySet()) collectModIds(child.getValue(), ids);
    }

    private void installHostWorld(CancelToken token) throws IOException {
        Path world = paths.host.resolve("world");
        ensureNoSymlinkPath(paths.host, world);
        if (Files.exists(world, LinkOption.NOFOLLOW_LINKS)) return;
        Path temporary = paths.host.resolve(".rv-world-" + UUID.randomUUID().toString());
        ensureDirectory(temporary);
        try {
            SafeZip.extract(bundle.resources.resolve("world-template.zip"), temporary, (relative, target) -> true, 1073741824L, 2147483648L, token);
            Path selected = temporary;
            if (!Files.isRegularFile(temporary.resolve("level.dat"), LinkOption.NOFOLLOW_LINKS)) {
                Path nested = temporary.resolve("Battlefield-Extended");
                if (Files.isDirectory(nested, LinkOption.NOFOLLOW_LINKS) && Files.isRegularFile(nested.resolve("level.dat"), LinkOption.NOFOLLOW_LINKS)) selected = nested;
                else throw new IOException("RV world template does not contain a Minecraft world.");
            }
            if (Files.exists(world, LinkOption.NOFOLLOW_LINKS)) return;
            moveAtomic(selected, world);
        } finally { deleteTree(temporary); }
    }

    private void configureServerPort(int port) throws IOException {
        Path properties = paths.host.resolve("server.properties");
        ensureNoSymlinkPath(paths.host, properties);
        String original = "";
        boolean existed = Files.exists(properties, LinkOption.NOFOLLOW_LINKS);
        if (existed) {
            if (Files.isSymbolicLink(properties) || !Files.isRegularFile(properties, LinkOption.NOFOLLOW_LINKS) || Files.size(properties) > 1048576) throw new IOException("Invalid server.properties file.");
            original = new String(Files.readAllBytes(properties), StandardCharsets.UTF_8);
        }
        String[] lines = original.split("\\r?\\n", -1);
        int found = 0;
        StringBuilder result = new StringBuilder();
        for (String line : lines) {
            if (line.matches("^server-port=.*$")) {
                found++;
                result.append("server-port=").append(port);
            } else if (!line.isEmpty() || result.length() > 0) result.append(line);
            result.append('\n');
        }
        if (!existed) {
            writeAtomic(properties, ("server-port=" + port + "\nserver-ip=\nonline-mode=false\nlevel-name=world\n" ).getBytes(StandardCharsets.UTF_8));
            return;
        }
        if (found > 1) throw new IOException("server.properties has duplicate server-port values; no changes were made.");
        if (found == 0) result.append("server-port=").append(port).append('\n');
        int onlineMode = 0;
        int serverIp = 0;
        StringBuilder offline = new StringBuilder();
        for (String line : result.toString().split("\\n", -1)) {
            if (line.matches("^online-mode=.*$")) { onlineMode++; offline.append("online-mode=false"); }
            else if (line.matches("^server-ip=.*$")) { serverIp++; offline.append("server-ip="); }
            else if (!line.isEmpty() || offline.length() > 0) offline.append(line);
            offline.append('\n');
        }
        if (onlineMode > 1) throw new IOException("server.properties has duplicate online-mode values; no changes were made.");
        if (serverIp > 1) throw new IOException("server.properties has duplicate server-ip values; no changes were made.");
        if (onlineMode == 0) offline.append("online-mode=false\n");
        if (serverIp == 0) offline.append("server-ip=\n");
        if (!original.equals(offline.toString())) writeAtomic(properties, offline.toString().getBytes(StandardCharsets.UTF_8));
    }

    static boolean serverLogReady(Path log, long startedMillis) throws IOException {
        if (!Files.isRegularFile(log, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(log) || Files.getLastModifiedTime(log).toMillis() < startedMillis) return false;
        try (RandomAccessFile input = new RandomAccessFile(log.toFile(), "r")) {
            input.seek(Math.max(0, input.length() - 65536));
            String line;
            while ((line = input.readLine()) != null) if (line.contains("Done (")) return true;
        }
        return false;
    }

    private void waitForServer(CancelToken token, Process process, Path log, int port, long startedMillis) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.MINUTES.toNanos(5);
        while (System.nanoTime() < deadline) {
            token.check();
            if (!process.isAlive()) throw new IOException("Forge server exited during startup. Details: " + log);
            if (serverLogReady(log, startedMillis) && connects("127.0.0.1", port, 400)) return;
            Thread.sleep(250);
        }
        throw new IOException("Forge server did not finish starting within five minutes. Details: " + log);
    }

    private void stopHost(CancelToken token) throws Exception {
        Process process = hostProcess;
        if (process == null || !process.isAlive()) {
            hostProcess = null;
            hostRunning = false;
            Process tunnel = tunnelProcess;
            tunnelProcess = null;
            if (tunnel != null) stopOwned(tunnel);
            updateButtons();
            return;
        }
        hostStopping = true;
        updateButtons();
        try {
        try {
            OutputStream input = process.getOutputStream();
            input.write("stop\n".getBytes(StandardCharsets.UTF_8));
            input.flush();
        } catch (IOException error) { if (process.isAlive()) throw new IOException("Could not request a graceful server save.", error); }
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(120);
        while (process.isAlive() && System.nanoTime() < deadline) {
            token.check();
            if (process.waitFor(500, TimeUnit.MILLISECONDS)) break;
        }
        if (process.isAlive()) throw new IOException("The server is still saving. It was left running to protect the world.");
        hostProcess = null;
        hostRunning = false;
        hostStopping = false;
        Process tunnel = tunnelProcess;
        tunnelProcess = null;
        hostPortholeCode = "";
        if (tunnel != null) stopOwned(tunnel);
        updateButtons();
        setStatus("ru".equals(profile.language) ? "Сервер остановлен. Мир сохранён." : "Server stopped. The world was saved.");
        } finally {
            hostStopping = false;
            updateButtons();
        }
    }

    private Tunnel startTunnel(CancelToken token, Destination destination, String language) throws Exception {
        if (!isAppleSilicon()) throw new IOException("ru".equals(language) ? "Porthole на этом Mac не поддерживает текущую архитектуру. Выбери прямой IP-адрес." : "Porthole does not support this Mac architecture. Choose a direct IP address.");
        Path executable = findPortholeExecutable();
        if (executable == null) throw new IOException("ru".equals(language) ? "Для Porthole нужен установленный Steam и Porthole на Apple Silicon. Прямой IP работает без них." : "Porthole needs Steam and Porthole installed on Apple Silicon. Direct IP works without them.");
        int localPort = availablePort();
        List<String> command = new ArrayList<String>();
        command.add(executable.toString());
        command.add("connect");
        command.add(destination.target);
        command.add("--auto-approve-ports");
        command.add("tcp/" + destination.port);
        command.add("--remap");
        command.add(destination.port + ":" + localPort);
        command.add("--bind");
        command.add("127.0.0.1");
        command.add("--json");
        Path output = paths.support.resolve("porthole-client-" + UUID.randomUUID().toString() + ".jsonl");
        Path errors = paths.support.resolve("porthole-client-" + UUID.randomUUID().toString() + ".log");
        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(executable.getParent().toFile());
        builder.environment().put("SteamAppId", PORTHOLE_APP_ID);
        builder.environment().put("SteamGameId", PORTHOLE_APP_ID);
        builder.redirectOutput(output.toFile());
        builder.redirectError(errors.toFile());
        Process process = builder.start();
        try {
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(45);
            while (System.nanoTime() < deadline) {
                token.check();
                if (!process.isAlive()) throw new IOException("Porthole exited before the server tunnel was ready. Details: " + errors);
                if (connects("127.0.0.1", localPort, 250)) return new Tunnel(process, localPort, errors);
                Thread.sleep(250);
            }
            throw new IOException("Porthole did not open the local connection in time. Details: " + errors);
        } catch (Exception error) {
            stopOwned(process);
            throw error;
        }
    }

    private void startHostPorthole(CancelToken token) throws Exception {
        if (!hostRunning || hostProcess == null || !hostProcess.isAlive()) throw new IOException("ru".equals(profile.language) ? "Сначала запусти собственный сервер." : "Start your server first.");
        if (!isAppleSilicon()) throw new IOException("ru".equals(profile.language) ? "Porthole для Mac работает только на Apple Silicon. Прямой доступ к LAN-серверу доступен на Intel." : "Porthole for Mac supports Apple Silicon only. Direct LAN access works on Intel.");
        Path executable = findPortholeExecutable();
        if (executable == null) throw new IOException("ru".equals(profile.language) ? "Steam или Porthole не найдены. Сервер останется доступен в локальной сети." : "Steam or Porthole was not found. The server remains available on your local network.");
        int port = readServerPort(paths.host.resolve("server.properties"));
        List<String> command = Arrays.asList(executable.toString(), "expose", "tcp/127.0.0.1:" + port, "--json");
        Path events = paths.support.resolve("porthole-host-" + UUID.randomUUID().toString() + ".jsonl");
        Path errors = paths.support.resolve("porthole-host-" + UUID.randomUUID().toString() + ".log");
        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(executable.getParent().toFile());
        builder.environment().put("SteamAppId", PORTHOLE_APP_ID);
        builder.environment().put("SteamGameId", PORTHOLE_APP_ID);
        builder.redirectOutput(events.toFile());
        builder.redirectError(errors.toFile());
        Process process = builder.start();
        tunnelProcess = process;
        hostPortholeCode = "";
        boolean sessionReady = false;
        boolean portReady = false;
        long offset = 0;
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(60);
        try {
            while (System.nanoTime() < deadline) {
                token.check();
                if (!process.isAlive()) throw new IOException("Porthole stopped before it exposed the server. Details: " + errors);
                if (Files.isRegularFile(events, LinkOption.NOFOLLOW_LINKS) && Files.size(events) >= offset) {
                    try (RandomAccessFile input = new RandomAccessFile(events.toFile(), "r")) {
                        input.seek(offset);
                        String line;
                        while ((line = input.readLine()) != null) {
                            offset = input.getFilePointer();
                            JsonElement element;
                            try { element = new JsonParser().parse(new String(line.getBytes(Charset.forName("ISO-8859-1")), StandardCharsets.UTF_8)); }
                            catch (RuntimeException ignored) { continue; }
                            if (!element.isJsonObject()) continue;
                            JsonObject value = element.getAsJsonObject();
                            String event = stringValue(value.get("event"));
                            if ("static_code".equals(event) && value.has("code")) {
                                String code = stringValue(value.get("code"));
                                if (code.matches("(?i)^[a-z0-9]{4,16}$")) hostPortholeCode = code.toUpperCase(Locale.ROOT);
                            } else if ("ready".equals(event)) sessionReady = true;
                            else if ("port_accepted".equals(event) && value.has("port") && value.get("port").getAsInt() == port && "tcp".equals(stringValue(value.get("proto")))) portReady = true;
                            else if ("error".equals(event)) throw new IOException("Porthole reported an error. Details: " + errors);
                        }
                        offset = input.getFilePointer();
                    }
                }
                if (sessionReady && portReady && !hostPortholeCode.isEmpty()) {
                    String code = hostPortholeCode;
                    setStatus("ru".equals(profile.language) ? "Код Porthole готов: " + code : "Porthole code ready: " + code);
                    SwingUtilities.invokeLater(() -> JOptionPane.showMessageDialog(this,
                            "ru".equals(profile.language) ? "Код Porthole для друзей:\n\n" + code + "\n\nНажми «Копировать код Porthole», чтобы скопировать его." : "Porthole code for friends:\n\n" + code + "\n\nUse Copy Porthole code to copy it.", "RV Warfare", JOptionPane.INFORMATION_MESSAGE));
                    updateButtons();
                    return;
                }
                Thread.sleep(250);
            }
            throw new IOException("Porthole did not confirm the exposed server port in time. Details: " + errors);
        } catch (Exception error) {
            tunnelProcess = null;
            hostPortholeCode = "";
            stopOwned(process);
            updateButtons();
            throw error;
        }
    }

    private void copyPortholeCode() {
        String code = hostPortholeCode;
        if (code.isEmpty()) return;
        try {
            java.awt.Toolkit.getDefaultToolkit().getSystemClipboard().setContents(new java.awt.datatransfer.StringSelection(code), null);
            setStatus("ru".equals(profile.language) ? "Код скопирован." : "Code copied.");
        } catch (Exception error) { showError(error); }
    }

    static String stringValue(JsonElement element) {
        return element != null && element.isJsonPrimitive() && element.getAsJsonPrimitive().isString() ? element.getAsString() : "";
    }

    private static boolean isAppleSilicon() {
        try {
            Process process = new ProcessBuilder("/usr/sbin/sysctl", "-n", "hw.optional.arm64").redirectErrorStream(true).start();
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (InputStream in = process.getInputStream()) { byte[] buffer = new byte[128]; int count; while ((count = in.read(buffer)) >= 0 && bytes.size() < 1024) bytes.write(buffer, 0, count); }
            return process.waitFor(3, TimeUnit.SECONDS) && process.exitValue() == 0 && new String(bytes.toByteArray(), StandardCharsets.UTF_8).trim().equals("1");
        } catch (Exception ignored) { return false; }
    }

    private Path findPortholeExecutable() throws IOException {
        Path steam = Paths.get(System.getProperty("user.home"), "Library", "Application Support", "Steam");
        List<Path> libraries = new ArrayList<Path>();
        libraries.add(steam);
        Path libraryFile = steam.resolve("steamapps/libraryfolders.vdf");
        if (Files.isRegularFile(libraryFile, LinkOption.NOFOLLOW_LINKS) && !Files.isSymbolicLink(libraryFile) && Files.size(libraryFile) < 1048576) {
            String content = new String(Files.readAllBytes(libraryFile), StandardCharsets.UTF_8);
            Matcher matcher = Pattern.compile("\\\"path\\\"\\s+\\\"([^\\\"]+)\\\"").matcher(content);
            while (matcher.find()) libraries.add(Paths.get(matcher.group(1).replace("\\\\", "\\")));
        }
        for (Path library : libraries) {
            Path apps = library.resolve("steamapps");
            Path manifest = apps.resolve("appmanifest_" + PORTHOLE_APP_ID + ".acf");
            if (!Files.isRegularFile(manifest, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(manifest) || Files.size(manifest) > 1048576) continue;
            String content = new String(Files.readAllBytes(manifest), StandardCharsets.UTF_8);
            Matcher installed = Pattern.compile("\\\"StateFlags\\\"\\s+\\\"([0-9]+)\\\"").matcher(content);
            Matcher directory = Pattern.compile("\\\"installdir\\\"\\s+\\\"([^\\\"/\\\\]+)\\\"").matcher(content);
            if (!installed.find() || !"4".equals(installed.group(1)) || !directory.find()) continue;
            Path root = apps.resolve("common").resolve(directory.group(1)).normalize();
            if (!root.startsWith(apps.resolve("common").normalize()) || !Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS) || Files.isSymbolicLink(root)) continue;
            try (java.util.stream.Stream<Path> walk = Files.walk(root, 8)) {
                Path executable = walk.filter(path -> Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS) && !Files.isSymbolicLink(path) && Files.isExecutable(path) && path.getFileName().toString().toLowerCase(Locale.ROOT).contains("porthole")).findFirst().orElse(null);
                if (executable != null) return executable;
            }
        }
        return null;
    }

    private static int availablePort() throws IOException {
        try (java.net.ServerSocket socket = new java.net.ServerSocket(0, 1, java.net.InetAddress.getByName("127.0.0.1"))) { return socket.getLocalPort(); }
    }

    private static void testAvailablePort(int port) throws IOException {
        try (java.net.ServerSocket socket = new java.net.ServerSocket()) {
            socket.setReuseAddress(false);
            socket.bind(new InetSocketAddress(port));
        } catch (IOException error) { throw new IOException("Port " + port + " is already in use.", error); }
    }

    private static boolean connects(String host, int port, int timeout) {
        try (java.net.Socket socket = new java.net.Socket()) {
            socket.connect(new InetSocketAddress(host, port), timeout);
            return true;
        } catch (IOException ignored) { return false; }
    }

    private static int readServerPort(Path properties) throws IOException {
        if (Files.isSymbolicLink(properties) || !Files.isRegularFile(properties, LinkOption.NOFOLLOW_LINKS)) return PORT;
        int found = 0;
        int port = PORT;
        for (String line : Files.readAllLines(properties, StandardCharsets.UTF_8)) {
            Matcher matcher = Pattern.compile("^server-port=([0-9]+)$").matcher(line);
            if (matcher.matches()) { found++; port = parsePort(matcher.group(1)); }
        }
        if (found > 1) throw new IOException("server.properties has duplicate server-port values.");
        return port;
    }

    private static void stopOwned(Process process) {
        if (process == null) return;
        try {
            if (!process.isAlive()) return;
            process.destroy();
            if (!process.waitFor(5, TimeUnit.SECONDS) && process.isAlive()) process.destroyForcibly();
        } catch (InterruptedException error) { Thread.currentThread().interrupt(); }
    }

    interface ArchivePolicy { boolean write(String relative, Path target) throws IOException; }

    static final class ZipRecord {
        final String name;
        final long size;
        final long compressedSize;
        final long crc;
        final boolean directory;
        ZipRecord(String name, long size, long compressedSize, long crc, boolean directory) {
            this.name = name;
            this.size = size;
            this.compressedSize = compressedSize;
            this.crc = crc;
            this.directory = directory;
        }
    }

    static final class SafeZip {
        static List<ZipRecord> inspect(Path archive, long maxArchive, long maxTotal) throws IOException {
            if (Files.isSymbolicLink(archive) || !Files.isRegularFile(archive, LinkOption.NOFOLLOW_LINKS)) throw new IOException("Archive is missing or unsafe.");
            long length = Files.size(archive);
            if (length < 22 || length > maxArchive) throw new IOException("Archive size is outside supported limits.");
            List<ZipRecord> records = new ArrayList<ZipRecord>();
            Set<String> names = new HashSet<String>();
            try (RandomAccessFile input = new RandomAccessFile(archive.toFile(), "r")) {
                long searchStart = Math.max(0, length - 65557);
                int tailLength = (int) (length - searchStart);
                byte[] tail = new byte[tailLength];
                input.seek(searchStart);
                input.readFully(tail);
                int eocd = -1;
                for (int i = tail.length - 22; i >= 0; i--) {
                    if (u32(tail, i) == 0x06054b50L && i + 22 + u16(tail, i + 20) == tail.length) { eocd = i; break; }
                }
                if (eocd < 0) throw new IOException("Archive directory is missing or malformed.");
                int disk = u16(tail, eocd + 4);
                int directoryDisk = u16(tail, eocd + 6);
                int diskCount = u16(tail, eocd + 8);
                int count = u16(tail, eocd + 10);
                long directorySize = u32(tail, eocd + 12);
                long directoryOffset = u32(tail, eocd + 16);
                if (disk != 0 || directoryDisk != 0 || diskCount != count || count == 65535 || directorySize == 0xffffffffL || directoryOffset == 0xffffffffL || count > 100000 || directoryOffset + directorySize > searchStart + eocd) throw new IOException("Multi-disk or ZIP64 archives are not supported.");
                input.seek(directoryOffset);
                long total = 0;
                for (int index = 0; index < count; index++) {
                    if (input.readInt() != 0x504b0102) throw new IOException("Archive directory entry is malformed.");
                    int madeBy = readU16(input);
                    readU16(input);
                    int flags = readU16(input);
                    int method = readU16(input);
                    readU16(input);
                    readU16(input);
                    long crc = readU32(input);
                    long compressed = readU32(input);
                    long uncompressed = readU32(input);
                    int nameLength = readU16(input);
                    int extraLength = readU16(input);
                    int commentLength = readU16(input);
                    int startDisk = readU16(input);
                    readU16(input);
                    long external = readU32(input);
                    long localOffset = readU32(input);
                    if (nameLength < 1 || nameLength > 4096 || extraLength > 65535 || commentLength > 65535 || startDisk != 0 || compressed == 0xffffffffL || uncompressed == 0xffffffffL || localOffset == 0xffffffffL) throw new IOException("Unsupported archive entry metadata.");
                    byte[] encoded = new byte[nameLength];
                    input.readFully(encoded);
                    input.skipBytes(extraLength + commentLength);
                    if ((flags & 1) != 0 || method != ZipEntry.STORED && method != ZipEntry.DEFLATED) throw new IOException("Encrypted or unsupported archive entry.");
                    String name = decodeZipName(encoded, (flags & (1 << 11)) != 0);
                    boolean directory = name.endsWith("/");
                    String relative = directory ? name.substring(0, name.length() - 1) : name;
                    if (!validRelative(relative)) throw new IOException("Unsafe archive path: " + name);
                    if (!names.add(relative.toLowerCase(Locale.ROOT))) throw new IOException("Duplicate archive path: " + relative);
                    int hostSystem = (madeBy >>> 8) & 255;
                    int mode = (int) (external >>> 16);
                    int type = mode & 0170000;
                    if (hostSystem == 3 && type != 0 && type != 0100000 && type != 0040000) throw new IOException("Symbolic links and special files are not allowed in archives.");
                    if (hostSystem == 3 && type == 0040000 && !directory || hostSystem == 3 && type == 0100000 && directory) throw new IOException("Archive path type is inconsistent.");
                    if (uncompressed > MAX_DOWNLOAD_BYTES || compressed > length || (compressed == 0 && uncompressed != 0) || compressed > 0 && uncompressed / Math.max(1, compressed) > 300) throw new IOException("Archive entry exceeds supported expansion limits.");
                    total += uncompressed;
                    if (total > maxTotal) throw new IOException("Archive expands beyond the supported limit.");
                    records.add(new ZipRecord(relative, uncompressed, compressed, crc, directory));
                }
                if (input.getFilePointer() != directoryOffset + directorySize) throw new IOException("Archive directory size does not match its entries.");
            }
            return records;
        }

        static void extract(Path archive, Path destination, ArchivePolicy policy, long maxArchive, long maxTotal, CancelToken token) throws IOException {
            List<ZipRecord> entries = inspect(archive, maxArchive, maxTotal);
            ensureDirectory(destination);
            try (ZipFile zip = new ZipFile(archive.toFile())) {
                for (ZipRecord record : entries) {
                    token.check();
                    Path target = resolveInside(destination, record.name);
                    if (record.directory) { ensureDirectory(target); continue; }
                    ensureNoSymlinkPath(destination, target);
                    Path parent = target.getParent();
                    ensureDirectory(parent);
                    boolean write = policy.write(record.name, target);
                    if (Files.exists(target, LinkOption.NOFOLLOW_LINKS) && (Files.isSymbolicLink(target) || !Files.isRegularFile(target, LinkOption.NOFOLLOW_LINKS))) throw new IOException("An archive target is not a regular file: " + record.name);
                    Path temporary = write ? parent.resolve(target.getFileName().toString() + "." + UUID.randomUUID().toString() + ".part") : null;
                    CRC32 crc = new CRC32();
                    long size = 0;
                    try {
                    ZipEntry entry = zip.getEntry(record.name);
                    if (entry == null || entry.getSize() != record.size || entry.getCrc() != record.crc) throw new IOException("Archive central directory differs from its entry data.");
                    try (InputStream in = new BufferedInputStream(zip.getInputStream(entry)); OutputStream out = write ? new BufferedOutputStream(Files.newOutputStream(temporary, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) : null) {
                        byte[] buffer = new byte[65536];
                        int count;
                        while ((count = in.read(buffer)) >= 0) {
                            token.check();
                            size += count;
                            if (size > record.size || size > MAX_DOWNLOAD_BYTES) throw new IOException("Archive entry expanded beyond its declared size.");
                            crc.update(buffer, 0, count);
                            if (out != null) out.write(buffer, 0, count);
                        }
                    }
                    if (size != record.size || crc.getValue() != record.crc) throw new IOException("Archive entry checksum failed: " + record.name);
                    if (write) moveAtomic(temporary, target);
                    } finally { if (temporary != null) Files.deleteIfExists(temporary); }
                }
            }
        }

        private static String decodeZipName(byte[] value, boolean utf8) throws IOException {
            Charset charset = utf8 ? StandardCharsets.UTF_8 : Charset.forName("CP437");
            try {
                return charset.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(value)).toString();
            } catch (CharacterCodingException error) { throw new IOException("Archive contains an invalid filename encoding.", error); }
        }

        private static int readU16(RandomAccessFile input) throws IOException { return input.readUnsignedByte() | input.readUnsignedByte() << 8; }
        private static long readU32(RandomAccessFile input) throws IOException { return (readU16(input) & 65535L) | ((readU16(input) & 65535L) << 16); }
        private static int u16(byte[] data, int offset) { return (data[offset] & 255) | (data[offset + 1] & 255) << 8; }
        private static long u32(byte[] data, int offset) { return (u16(data, offset) & 65535L) | ((u16(data, offset + 2) & 65535L) << 16); }
    }
}
