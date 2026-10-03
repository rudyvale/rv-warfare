import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import java.nio.charset.StandardCharsets;
import java.util.Random;
import rv.experience.protocol.ExperienceProtocol;
import rv.experience.protocol.SessionRequest;
import rv.experience.protocol.SessionSnapshot;

public final class RVExperienceProtocolTest {
    private static int checks;
    private static void check(boolean value, String name) {
        checks++;
        if (!value) throw new AssertionError(name);
    }
    private static byte[] request(ExperienceProtocol.Action action, int a, int b, long revision) {
        ByteBuf buffer=Unpooled.buffer();
        try {
            new SessionRequest(action,a,b,revision).toBytes(buffer);
            byte[] bytes=new byte[buffer.readableBytes()];buffer.readBytes(bytes);return bytes;
        } finally {buffer.release();}
    }
    private static SessionRequest decodeRequest(byte[] bytes) {
        ByteBuf buffer=Unpooled.wrappedBuffer(bytes);
        try {SessionRequest decoded=new SessionRequest();decoded.fromBytes(buffer);return decoded;}
        finally {buffer.release();}
    }
    private static byte[] snapshot(String json) {
        ByteBuf buffer=Unpooled.buffer();
        try {
            new SessionSnapshot(json).toBytes(buffer);
            byte[] bytes=new byte[buffer.readableBytes()];buffer.readBytes(bytes);return bytes;
        } finally {buffer.release();}
    }
    private static SessionSnapshot decodeSnapshot(byte[] bytes) {
        ByteBuf buffer=Unpooled.wrappedBuffer(bytes);
        try {SessionSnapshot decoded=new SessionSnapshot();decoded.fromBytes(buffer);return decoded;}
        finally {buffer.release();}
    }
    private static void invalidRequest(byte[] bytes, String name) {check(!decodeRequest(bytes).valid,name);}
    private static void invalidSnapshot(byte[] bytes, String name) {check(!decodeSnapshot(bytes).valid,name);}
    public static void main(String[] args) {
        for (ExperienceProtocol.Action action:ExperienceProtocol.Action.values()) {
            for(int value:new int[]{0,1,65535}) {
                byte[] bytes=request(action,value,65535-value,Long.MAX_VALUE);
                SessionRequest result=decodeRequest(bytes);
                check(bytes.length==22,"request exact envelope");
                check(result.valid&&result.action==action&&result.argA==value&&result.argB==65535-value&&result.revision==Long.MAX_VALUE,"action roundtrip");
            }
        }
        byte[] good=request(ExperienceProtocol.Action.SNAPSHOT,0,0,0);
        for(int length=0;length<22;length++)invalidRequest(java.util.Arrays.copyOf(good,length),"truncated request");
        invalidRequest(java.util.Arrays.copyOf(good,23),"trailing request");
        for(int index:new int[]{0,4,5}) {byte[] bytes=good.clone();bytes[index]=(byte)255;invalidRequest(bytes,"unknown envelope field");}
        for(int index:new int[]{6,10,14}) {byte[] bytes=good.clone();bytes[index]=(byte)128;invalidRequest(bytes,"negative request field");}
        for(int index:new int[]{7,11}) {byte[] bytes=good.clone();bytes[index]=1;invalidRequest(bytes,"request argument overflow");}
        SessionRequest reusable=decodeRequest(good);
        ByteBuf bad=Unpooled.wrappedBuffer(new byte[1]);
        try {reusable.fromBytes(bad);check(!reusable.valid&&reusable.action==null,"request reused failure resets acceptance");}finally{bad.release();}
        SessionRequest mutated=new SessionRequest(ExperienceProtocol.Action.CHOOSE_TEAM,1,0,1);mutated.argA=-1;
        ByteBuf output=Unpooled.buffer();
        try {boolean rejected=false;try{mutated.toBytes(output);}catch(IllegalStateException expected){rejected=true;}check(rejected&&output.readableBytes()==0,"mutated outbound request denied");}finally{output.release();}
        String unicode="{\"language\":\"ru\",\"text\":\"Готовность: FPV 🛩\"}";
        byte[] encoded=snapshot(unicode);SessionSnapshot decoded=decodeSnapshot(encoded);
        check(decoded.valid&&unicode.equals(decoded.json),"UTF8 snapshot roundtrip");
        check(encoded.length==unicode.getBytes(StandardCharsets.UTF_8).length+7,"UTF8 byte count");
        char[] maximum=new char[32768];java.util.Arrays.fill(maximum,'x');
        check(decodeSnapshot(snapshot(new String(maximum))).valid,"maximum snapshot accepted");
        check(decodeSnapshot(snapshot("x")).valid,"minimum snapshot accepted");
        for(String invalid:new String[]{"",new String(maximum)+"x"}) {boolean rejected=false;try{new SessionSnapshot(invalid);}catch(IllegalArgumentException expected){rejected=true;}check(rejected,"outbound size denied");}
        for(int length=0;length<encoded.length;length++)invalidSnapshot(java.util.Arrays.copyOf(encoded,length),"truncated snapshot");
        invalidSnapshot(java.util.Arrays.copyOf(encoded,encoded.length+1),"trailing snapshot");
        for(int index:new int[]{0,4}) {byte[] bytes=encoded.clone();bytes[index]=(byte)255;invalidSnapshot(bytes,"unknown snapshot envelope");}
        byte[] empty=encoded.clone();empty[5]=0;empty[6]=0;invalidSnapshot(empty,"empty snapshot denied");
        byte[] oversized=encoded.clone();oversized[5]=(byte)128;oversized[6]=1;invalidSnapshot(oversized,"oversized snapshot denied");
        byte[] malformed=snapshot("xx");malformed[7]=(byte)192;malformed[8]=(byte)175;invalidSnapshot(malformed,"overlong UTF8 denied");
        malformed=snapshot("xxx");malformed[7]=(byte)237;malformed[8]=(byte)160;malformed[9]=(byte)128;invalidSnapshot(malformed,"UTF8 surrogate denied");
        SessionSnapshot old=decodeSnapshot(encoded);bad=Unpooled.wrappedBuffer(new byte[1]);
        try{old.fromBytes(bad);check(!old.valid&&old.json==null,"snapshot reused failure resets acceptance");}finally{bad.release();}
        Random random=new Random(20261003L);
        for(int i=0;i<4096;i++) {byte[] bytes=new byte[random.nextInt(129)];random.nextBytes(bytes);invalidRequest(bytes,"random request denied");invalidSnapshot(bytes,"random snapshot denied");}
        System.out.println("RV experience protocol PASS: "+checks+" checks");
    }
}
