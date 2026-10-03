package rv.experience.client;

import net.minecraftforge.fml.common.network.simpleimpl.IMessage;
import net.minecraftforge.fml.common.network.simpleimpl.IMessageHandler;
import net.minecraftforge.fml.common.network.simpleimpl.MessageContext;
import rv.experience.protocol.SessionSnapshot;

public final class ClientSnapshotHandler implements IMessageHandler<SessionSnapshot,IMessage> {
    public IMessage onMessage(final SessionSnapshot message,MessageContext context){
        if(message.valid)Native.schedule(new Runnable(){public void run(){ClientProxy.accept(message.json);}});
        return null;
    }
}
