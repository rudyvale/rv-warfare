package rv.experience.protocol;

import io.netty.buffer.ByteBuf;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import net.minecraftforge.fml.common.network.simpleimpl.IMessage;

public final class SessionSnapshot implements IMessage {
    public String json;
    public boolean valid;

    public SessionSnapshot() { }

    public SessionSnapshot(String json) {
        if (json == null) throw new IllegalArgumentException("Missing RV snapshot");
        byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
        if (bytes.length == 0 || bytes.length > ExperienceProtocol.MAX_SNAPSHOT_BYTES) throw new IllegalArgumentException("RV snapshot size exceeds limit");
        this.json = json;
        this.valid = true;
    }

    public void fromBytes(ByteBuf buffer) {
        valid = false;
        json = null;
        if (buffer.readableBytes() < 7 || buffer.readableBytes() > ExperienceProtocol.MAX_SNAPSHOT_BYTES + 7) return;
        if (buffer.readInt() != ExperienceProtocol.MAGIC) return;
        if (buffer.readUnsignedByte() != ExperienceProtocol.VERSION) return;
        int length = buffer.readUnsignedShort();
        if (length == 0 || length > ExperienceProtocol.MAX_SNAPSHOT_BYTES || buffer.readableBytes() != length) return;
        byte[] bytes = new byte[length];
        buffer.readBytes(bytes);
        try {
            json = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();
            valid = true;
        } catch (CharacterCodingException ignored) {
            json = null;
        }
    }

    public void toBytes(ByteBuf buffer) {
        if (!valid || json == null) throw new IllegalStateException("Invalid RV snapshot");
        byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
        if (bytes.length == 0 || bytes.length > ExperienceProtocol.MAX_SNAPSHOT_BYTES) throw new IllegalStateException("RV snapshot size exceeds limit");
        buffer.writeInt(ExperienceProtocol.MAGIC);
        buffer.writeByte(ExperienceProtocol.VERSION);
        buffer.writeShort(bytes.length);
        buffer.writeBytes(bytes);
    }
}
