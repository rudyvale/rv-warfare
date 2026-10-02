import com.norwood.mcheli.uav.WarfareOwnerAuth;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.concurrent.*;

public final class OwnerLoginAcceptance {
    public static final class Profile {
        final String name;
        Profile(String name) { this.name = name; }
        public String getName() { return name; }
    }
    public static final class Network {
        volatile boolean open = true;
        SocketAddress address = new InetSocketAddress("127.0.0.1", 41000);
        public boolean isChannelOpen() { return open; }
        public SocketAddress getRemoteAddress() { return address; }
        public void closeChannel(Object message) { open = false; }
    }
    public static final class Login {
        public final Network networkManager = new Network();
        public Object loginGameProfile;
        boolean disconnected;
        Login(String name) { loginGameProfile = new Profile(name); }
        public void disconnect(Object message) { disconnected = true; networkManager.open = false; }
    }
    static int passed;
    static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    static void pass(String message) { passed++; System.out.println("PASS " + message); }
    static void policy() throws Exception {
        Files.write(Paths.get("vm-owner.properties"), "nickname=Owner_1\nscript=check-fixture.ps1\n".getBytes(StandardCharsets.ISO_8859_1));
    }
    static void script(String content) throws Exception {
        Files.write(Paths.get("check-fixture.ps1"), ("param([int]$LocalPort,[string]$Nickname)\n" + content + "\n").getBytes(StandardCharsets.UTF_8));
    }
    static boolean complete(Login handler) throws Exception {
        long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
        while (handler.networkManager.open && System.nanoTime() < end) {
            if (WarfareOwnerAuth.allowLogin(handler)) return true;
            Thread.sleep(20);
        }
        require(!handler.networkManager.open, "login did not finish within its deadline");
        return false;
    }
    public static void main(String[] args) throws Exception {
        Files.deleteIfExists(Paths.get("vm-owner.properties"));
        require(WarfareOwnerAuth.allowLogin(new Login("Owner_1")), "public mode rejected ordinary native login");
        pass("public policy absent allows login without checker");
        policy();
        script("throw 'ordinary players must never execute this checker'");
        require(WarfareOwnerAuth.allowLogin(new Login("MenuTester")), "ordinary player was reserved");
        pass("ordinary nickname bypasses owner checker");
        Login wrongCase = new Login("owner_1");
        require(!WarfareOwnerAuth.allowLogin(wrongCase) && wrongCase.disconnected, "case variant admitted");
        pass("reserved nickname case variant rejected before admission");
        Login remote = new Login("Owner_1");
        remote.networkManager.address = new InetSocketAddress("198.51.100.1", 41000);
        require(!WarfareOwnerAuth.allowLogin(remote) && remote.disconnected, "nonlocal reserved identity admitted");
        pass("reserved nonlocal connection rejected without checker");
        script("Start-Sleep -Milliseconds 600; Write-Output true");
        Login trusted = new Login("Owner_1");
        long beginning = System.nanoTime();
        require(!WarfareOwnerAuth.allowLogin(trusted), "pending verification entered vanilla login");
        require(TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - beginning) < 300, "login blocked the server thread");
        require(complete(trusted) && !trusted.disconnected, "verified connection not admitted");
        pass("reserved login is asynchronous and admits only completed verification");
        script("Write-Output false");
        Login denied = new Login("Owner_1");
        Login existing = new Login("Owner_1");
        require(!complete(denied) && denied.disconnected && existing.networkManager.open, "refusal displaced another session");
        pass("refused newcomer closes before vanilla duplicate handling");
        script("Start-Sleep -Milliseconds 600; Write-Output true");
        Login changed = new Login("Owner_1");
        require(!WarfareOwnerAuth.allowLogin(changed), "initial pending failed");
        changed.loginGameProfile = new Profile("Owner_1");
        require(!WarfareOwnerAuth.allowLogin(changed) && changed.disconnected, "stale profile result accepted");
        pass("changed profile cannot use earlier verification");
        Login closed = new Login("Owner_1");
        require(!WarfareOwnerAuth.allowLogin(closed), "closed fixture initial pending failed");
        closed.networkManager.open = false;
        Thread.sleep(900);
        require(!WarfareOwnerAuth.allowLogin(closed), "closed channel admitted by stale result");
        pass("closed channel cannot be admitted later");
        script("Start-Sleep -Seconds 9; Write-Output true");
        Login timeout = new Login("Owner_1");
        require(!complete(timeout) && timeout.disconnected, "checker timeout admitted reserved identity");
        pass("checker timeout rejects login within bounded deadline");
        Files.delete(Paths.get("vm-owner.properties"));
        require(WarfareOwnerAuth.allowLogin(new Login("MenuTester")), "public mode altered after private requests");
        pass("private failures do not alter later public compatibility");
        System.out.println(passed + " prelogin logic tests passed");
    }
}
