import com.norwood.mcheli.uav.WarfareOwnerAuth;
import net.minecraft.entity.player.EntityPlayerMP;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

public final class OwnerAuthAcceptance {
    public static final class Profile {
        private final UUID id = UUID.nameUUIDFromBytes("Owner_1".getBytes(StandardCharsets.UTF_8));
        public UUID getId() { return id; }
        public String getName() { return "Owner_1"; }
    }
    public static final class Network {
        public boolean open = true;
        public SocketAddress getRemoteAddress() { return new InetSocketAddress("127.0.0.1", 41000); }
        public boolean isChannelOpen() { return open; }
    }
    public static final class Connection {
        public final Network netManager = new Network();
        public boolean disconnected;
        public void disconnect(Object message) { disconnected = true; netManager.open = false; }
    }
    public static final class PlayerList {
        public final Map<UUID, EntityPlayerMP> players = new HashMap<UUID, EntityPlayerMP>();
        public final Set<UUID> operators = new HashSet<UUID>();
        public int additions;
        public boolean failAdd;
        public boolean failRemove;
        public EntityPlayerMP getPlayerByUUID(UUID id) { return players.get(id); }
        public void removeOp(Profile profile) {
            if (failRemove) throw new IllegalStateException("remove failed");
            operators.remove(profile.getId());
            EntityPlayerMP player = players.get(profile.getId());
            if (player != null) player.operator = false;
        }
        public void addOp(Profile profile) {
            operators.add(profile.getId());
            additions++;
            EntityPlayerMP player = players.get(profile.getId());
            if (player != null) player.operator = true;
            if (failAdd) throw new IllegalStateException("partial add failed");
        }
    }
    public static final class ListenableFutureStub {}
    public static final class Server {
        public final PlayerList list = new PlayerList();
        public final BlockingQueue<Runnable> scheduled = new LinkedBlockingQueue<Runnable>();
        public PlayerList getPlayerList() { return list; }
        public ListenableFutureStub addScheduledTask(Runnable task) { scheduled.add(task); return new ListenableFutureStub(); }
    }
    public static final class Event {
        private final EntityPlayerMP player;
        public Event(EntityPlayerMP player) { this.player = player; }
        public EntityPlayerMP getEntity() { return player; }
    }
    private static int passed;
    private static EntityPlayerMP player(Server server, boolean operator) {
        Profile profile = new Profile();
        EntityPlayerMP player = new EntityPlayerMP(server, profile, new Connection());
        server.list.players.put(profile.getId(), player);
        player.operator = operator;
        if (operator) { server.list.operators.add(profile.getId()); player.ownerTag = true; }
        return player;
    }
    private static void script(String content) throws Exception {
        String body = "param([int]$LocalPort,[string]$Nickname)\n" + content + "\n";
        Files.write(Paths.get("check-fixture.ps1"), body.getBytes(StandardCharsets.UTF_8));
    }
    private static void activate() throws Exception {
        Files.write(Paths.get("vm-owner.properties"), "nickname=Owner_1\nscript=check-fixture.ps1\n".getBytes(StandardCharsets.ISO_8859_1));
    }
    private static void callback(Server server) throws Exception {
        Runnable task = server.scheduled.poll(10, TimeUnit.SECONDS);
        require(task != null, "callback missing");
        task.run();
    }
    private static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    private static boolean operator(Server server) { return !server.list.operators.isEmpty(); }
    private static void pass(String name) { passed++; System.out.println(name + ": PASS"); }
    public static void main(String[] args) throws Exception {
        activate();
        script("Start-Sleep -Milliseconds 1600; Write-Output true");
        Server server = new Server();
        EntityPlayerMP player = player(server, true);
        long beginning = System.nanoTime();
        WarfareOwnerAuth.onJoin(new Event(player));
        long elapsed = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - beginning);
        require(elapsed < 800, "join blocked: " + elapsed + "ms");
        require(!operator(server) && !player.ownerTag, "old privileges remained while checking");
        pass("old operator revoked before asynchronous check");
        callback(server);
        require(operator(server) && player.ownerTag && server.list.additions == 1, "verified session not granted");
        pass("verified live session granted after server callback");

        script("Write-Output false");
        server = new Server(); player = player(server, true);
        WarfareOwnerAuth.onJoin(new Event(player)); callback(server);
        require(!operator(server) && !player.ownerTag, "false result granted privileges");
        pass("explicit refusal keeps operator removed");

        script("throw 'fixture failure'");
        server = new Server(); player = player(server, true);
        WarfareOwnerAuth.onJoin(new Event(player)); callback(server);
        require(!operator(server) && !player.ownerTag, "failed process granted privileges");
        pass("checker process failure denies privileges");

        script("Start-Sleep -Seconds 8; Write-Output true");
        server = new Server(); player = player(server, true);
        WarfareOwnerAuth.onJoin(new Event(player)); callback(server);
        require(!operator(server) && !player.ownerTag, "timeout granted privileges");
        pass("checker timeout denies privileges");

        script("Start-Sleep -Milliseconds 600; Write-Output true");
        server = new Server(); player = player(server, true);
        WarfareOwnerAuth.onJoin(new Event(player));
        ((Connection)player.connection).netManager.open = false;
        callback(server);
        require(!operator(server) && !player.ownerTag, "closed connection granted privileges");
        pass("closed channel cannot receive privileges");

        server = new Server(); player = player(server, true);
        WarfareOwnerAuth.onJoin(new Event(player));
        EntityPlayerMP replacement = player(server, false);
        callback(server);
        require(!operator(server) && !replacement.ownerTag, "old result authorized replacement player");
        pass("stale response cannot authorize replacement entity");

        server = new Server(); player = player(server, true);
        WarfareOwnerAuth.onJoin(new Event(player));
        replacement = player(server, false);
        WarfareOwnerAuth.onJoin(new Event(replacement));
        callback(server);
        require(!operator(server) && !replacement.ownerTag, "first queued result granted reconnect");
        callback(server);
        require(operator(server) && replacement.ownerTag && server.list.additions == 1, "new session did not receive its own result");
        pass("reconnect waits for its own verification");

        script("Write-Output true");
        server = new Server(); player = player(server, true); server.list.failAdd = true;
        WarfareOwnerAuth.onJoin(new Event(player)); callback(server);
        require(!operator(server) && !player.ownerTag, "partial addOp was not rolled back");
        pass("partial operator grant is rolled back on exception");

        server = new Server(); player = player(server, true); player.failTag = true;
        WarfareOwnerAuth.onJoin(new Event(player)); callback(server);
        require(!operator(server) && !player.ownerTag, "failed verified tag kept operator");
        pass("tag failure rolls back operator grant");

        server = new Server(); player = player(server, true); server.list.failRemove = true;
        WarfareOwnerAuth.onJoin(new Event(player));
        require(((Connection)player.connection).disconnected && !player.ownerTag, "failed revoke left connection active");
        pass("failed initial revoke disconnects the session");

        Files.delete(Paths.get("vm-owner.properties"));
        server = new Server(); player = player(server, true);
        WarfareOwnerAuth.onJoin(new Event(player));
        require(operator(server) && player.ownerTag, "public mode changed existing operator");
        replacement = player(new Server(), false);
        WarfareOwnerAuth.onJoin(new Event(replacement));
        require(!replacement.ownerTag, "public mode tagged ordinary player");
        pass("public mode reflects ordinary operator permissions");
        System.out.println(passed + " asynchronous owner authentication tests passed");
    }
}
