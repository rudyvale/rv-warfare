package rv.experience.server;

import net.minecraftforge.fml.common.network.simpleimpl.SimpleNetworkWrapper;
import net.minecraftforge.fml.common.network.simpleimpl.IMessage;
import net.minecraftforge.fml.common.network.simpleimpl.IMessageHandler;
import net.minecraftforge.fml.common.network.simpleimpl.MessageContext;
import net.minecraftforge.fml.relauncher.Side;
import rv.experience.protocol.SessionSnapshot;

public class CommonProxy {
    public void init(SimpleNetworkWrapper network) {network.registerMessage(SnapshotCodec.class,SessionSnapshot.class,1,Side.CLIENT);}
    public static final class SnapshotCodec implements IMessageHandler<SessionSnapshot,IMessage>{public IMessage onMessage(SessionSnapshot message,MessageContext context){return null;}}
}
