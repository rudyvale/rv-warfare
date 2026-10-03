package rv.experience.protocol;

import io.netty.buffer.ByteBuf;
import net.minecraftforge.fml.common.network.simpleimpl.IMessage;

public final class SessionRequest implements IMessage {
    public ExperienceProtocol.Action action;
    public int argA;
    public int argB;
    public long revision;
    public boolean valid;

    public SessionRequest() { }

    public SessionRequest(ExperienceProtocol.Action action, int argA, int argB, long revision) {
        this.action = action;
        this.argA = argA;
        this.argB = argB;
        this.revision = revision;
        this.valid = action != null && argA >= 0 && argA <= 65535 && argB >= 0 && argB <= 65535 && revision >= 0;
    }

    public void fromBytes(ByteBuf buffer) {
        valid = false;
        action = null;
        if (buffer.readableBytes() != ExperienceProtocol.REQUEST_BYTES) return;
        if (buffer.readInt() != ExperienceProtocol.MAGIC) return;
        if (buffer.readUnsignedByte() != ExperienceProtocol.VERSION) return;
        int id = buffer.readUnsignedByte();
        if (id >= ExperienceProtocol.Action.values().length) return;
        int first = buffer.readInt();
        int second = buffer.readInt();
        long nonce = buffer.readLong();
        if (first < 0 || first > 65535 || second < 0 || second > 65535 || nonce < 0) return;
        action = ExperienceProtocol.Action.values()[id];
        argA = first;
        argB = second;
        revision = nonce;
        valid = true;
    }

    public void toBytes(ByteBuf buffer) {
        if (!valid || action == null || argA < 0 || argA > 65535 || argB < 0 || argB > 65535 || revision < 0) throw new IllegalStateException("Invalid RV session request");
        buffer.writeInt(ExperienceProtocol.MAGIC);
        buffer.writeByte(ExperienceProtocol.VERSION);
        buffer.writeByte(action.ordinal());
        buffer.writeInt(argA);
        buffer.writeInt(argB);
        buffer.writeLong(revision);
    }
}
