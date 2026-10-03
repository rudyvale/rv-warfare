package rv.experience.server;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicInteger;
import net.minecraftforge.fml.common.network.simpleimpl.IMessage;
import net.minecraftforge.fml.common.network.simpleimpl.IMessageHandler;
import net.minecraftforge.fml.common.network.simpleimpl.MessageContext;
import rv.experience.protocol.SessionRequest;

public final class ServerRequestHandler implements IMessageHandler<SessionRequest,IMessage> {
    private static final ConcurrentMap<String,Gate> gates=new ConcurrentHashMap<String,Gate>();
    private static final AtomicInteger pending=new AtomicInteger();
    private static final class Gate {long second;int count,queued; synchronized boolean allow(){long now=System.nanoTime()/1000000000L;if(now!=second){second=now;count=0;}if(count>=12||queued>=2)return false;count++;queued++;return true;}synchronized void finish(){queued--;}}
    public IMessage onMessage(final SessionRequest request,MessageContext context){
        if(request==null||!request.valid)return null;
        try{Object handler=Reflect.call(context,new String[]{"getServerHandler"});final Object player=Reflect.field(handler,"player","field_147369_b");String id=Reflect.id(player);Gate found=gates.get(id);if(found==null){if(gates.size()>=256)return null;Gate newGate=new Gate();Gate previous=gates.putIfAbsent(id,newGate);found=previous==null?newGate:previous;}final Gate gate=found;if(!gate.allow())return null;if(pending.incrementAndGet()>128){pending.decrementAndGet();gate.finish();return null;}try{Object server=Reflect.call(player,new String[]{"getServer","func_184102_h"});Reflect.schedule(server,new Runnable(){public void run(){try{ExperienceServer.handle(player,request);}finally{pending.decrementAndGet();gate.finish();}}});}catch(Exception failure){pending.decrementAndGet();gate.finish();}}
        catch(Exception ignored){}return null;
    }
    public static void forget(String id){gates.remove(id);}
}
