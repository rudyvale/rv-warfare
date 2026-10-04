package rv.experience.client;

import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;
import net.minecraftforge.fml.common.network.simpleimpl.SimpleNetworkWrapper;
import net.minecraftforge.fml.relauncher.Side;
import org.lwjgl.input.Keyboard;
import rv.experience.protocol.ExperienceProtocol;
import rv.experience.protocol.SessionRequest;
import rv.experience.protocol.SessionSnapshot;
import rv.experience.server.CommonProxy;

public final class ClientProxy extends CommonProxy {
    public static ClientState state;
    public static boolean pending;
    public static String error="";
    private static SimpleNetworkWrapper channel;
    private static Object world;
    private static boolean joined,f7;
    private static long nextRefresh,lastRequest;
    public void init(SimpleNetworkWrapper network){channel=network;network.registerMessage(ClientSnapshotHandler.class,SessionSnapshot.class,ExperienceProtocol.SNAPSHOT_DISCRIMINATOR,Side.CLIENT);MinecraftForge.EVENT_BUS.register(this);}
    public static boolean request(ExperienceProtocol.Action action,int a,int b){
        long now=System.currentTimeMillis();if(channel==null||pending||now-lastRequest<250)return false;
        channel.sendToServer(new SessionRequest(action,a,b,state==null?0:state.revision));lastRequest=now;nextRefresh=now+2000;pending=true;return true;
    }
    public static void accept(String json){try{Object current=Native.get(Native.minecraft(),"field_71441_e");if(current==null){pending=false;return;}if(current!=world){world=current;state=null;joined=false;}ClientState next=ClientState.parse(json);if(state!=null&&next.revision<state.revision)return;state=next;pending=false;error="";if(!joined){joined=true;open(0);}}catch(RuntimeException malformed){pending=false;error="snapshot_invalid";System.err.println("[RV Experience] Invalid server snapshot: "+malformed.getClass().getSimpleName());}}
    public static void open(int tab){Object mc=Native.minecraft();if(Native.get(mc,"field_71439_g")==null)return;Native.display(new ExperienceScreen(tab));if(state==null&&!pending)request(ExperienceProtocol.Action.SNAPSHOT,0,0);}
    public static void openControls(){open(2);}
    @SubscribeEvent public void tick(TickEvent.ClientTickEvent event){if(event.phase!=TickEvent.Phase.END)return;try{Object mc=Native.minecraft();Object current=Native.get(mc,"field_71441_e");if(current!=world){world=current;state=null;pending=false;joined=false;error="";nextRefresh=System.currentTimeMillis()+1200;}boolean pressed=Keyboard.isCreated()&&Keyboard.isKeyDown(Keyboard.KEY_F7);if(pressed&&!f7&&current!=null){Object screen=Native.get(mc,"field_71462_r");if(screen instanceof ExperienceScreen)Native.display(null);else if(screen==null)open(0);}f7=pressed;long now=System.currentTimeMillis();if(current==null||Native.get(mc,"field_71439_g")==null)return;if(pending&&now-lastRequest>5000){pending=false;error="server_unavailable";nextRefresh=now+5000;}if(now>=nextRefresh&&!pending&&(!joined||Native.get(mc,"field_71462_r") instanceof ExperienceScreen)){request(ExperienceProtocol.Action.SNAPSHOT,0,0);nextRefresh=now+2000;}}catch(RuntimeException error){System.err.println("[RV Experience] Client tick: "+error.getClass().getSimpleName());}}
}
