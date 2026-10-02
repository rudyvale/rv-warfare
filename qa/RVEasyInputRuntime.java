import com.google.gson.Gson;
import com.norwood.mcheli.vm.VMReflect;
import java.nio.file.*;
import java.util.*;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;
import org.lwjgl.input.Keyboard;
import org.lwjgl.input.Mouse;
import org.lwjgl.opengl.Display;

public final class RVEasyInputRuntime {
    private static boolean registered,active,forcedFocus=true,momentumInjected;
    private static int ticks;
    private static int mouseUpdateCalls,mouseSampleCalls,captureCalls;
    private static Object drone,player,world,target;
    private static String kind="movement",phase="waiting",lastPhase="waiting";
    private static final Set<Integer> keys=new HashSet<Integer>();
    private static final List<Map<String,Object>> samples=new ArrayList<Map<String,Object>>(),packets=new ArrayList<Map<String,Object>>(),moves=new ArrayList<Map<String,Object>>(),cameras=new ArrayList<Map<String,Object>>();
    private static final Map<String,Object> result=new LinkedHashMap<String,Object>();
    private static Class<?> type(String value)throws Exception{return Class.forName(value);}
    private static Object call(Object value,String name,Object... args)throws Exception{return VMReflect.call(value,name,args);}
    private static double num(Object value,String field)throws Exception{return VMReflect.num(VMReflect.get(value,field));}
    private static void write(Path path,Object value)throws Exception{Path temp=Paths.get(path+".tmp");Files.write(temp,new Gson().toJson(value).getBytes("UTF-8"));Files.move(temp,path,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}
    private static void fail(Throwable error){active=false;result.put("error",error.toString());try{write(Paths.get("easy-failed.json"),result);}catch(Exception ignored){}error.printStackTrace();}
    private static void register(){if(!registered){registered=true;MinecraftForge.EVENT_BUS.register(new RVEasyInputRuntime());}}
    public static void frame(){if(Boolean.getBoolean("rv.easy.qa"))register();}
    public static boolean keyDown(int key){return active?keys.contains(key):Keyboard.isKeyDown(key);}
    public static boolean mouseDown(int button){return active?keys.contains(button-100):Mouse.isButtonDown(button);}
    public static boolean displayActive(){return active?forcedFocus:Display.isActive();}
    private static void down(Object settings,String binding)throws Exception{keys.add(((Number)call(VMReflect.get(settings,binding),"func_151463_i")).intValue());}
    public static void mouse(Object handler){
        if(!active)return;
        mouseUpdateCalls++;
    }
    public static void sampleMouse(Object mouse)throws Exception{call(mouse,"func_74374_c");if(active){mouseSampleCalls++;VMReflect.set(mouse,"field_74377_a",phase.equals("mouse")?1:0);VMReflect.set(mouse,"field_74375_b",phase.equals("mouse")?1:0);}}
    public static void capture(){if(active)captureCalls++;}
    private static Map<String,Object> sample(Object aircraft)throws Exception{
        Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("tick",ticks);value.put("phase",phase);value.put("x",num(aircraft,"field_70165_t"));value.put("y",num(aircraft,"field_70163_u"));value.put("z",num(aircraft,"field_70161_v"));value.put("vx",num(aircraft,"field_70159_w"));value.put("vy",num(aircraft,"field_70181_x"));value.put("vz",num(aircraft,"field_70179_y"));value.put("yaw",call(aircraft,"getYaw"));value.put("pitch",call(aircraft,"getPitch"));value.put("roll",call(aircraft,"getRoll"));value.put("throttle",call(aircraft,"getCurrentThrottle"));value.put("ground",VMReflect.get(aircraft,"field_70122_E"));value.put("dead",VMReflect.get(aircraft,"field_70128_L"));value.put("controlled",call(aircraft,"getRiddenByEntity")!=null);return value;
    }
    private static String phaseAt(int t){
        if(kind.equals("fuse"))return t<40?"ground-safe":t<85?"fuse-lift":t<180?"fuse-forward":"complete";
        if(t<40)return "before-arm";if(t<100)return "lift";if(t<140)return "forward";if(t<180)return "hover";if(t<220)return "left";if(t<260)return "right";if(t<300)return "back";if(t<320)return "mouse";if(t<350)return "hover-after-mouse";if(t<370)return "down";if(t<400)return "focus-lost";if(t<430)return "focus-restored";if(t<460)return "rearm";if(t<470)return "before-drop";if(t<500)return "packet-drop";if(t<530)return "after-drop";if(t<550)return "rearm-again";if(t<580)return "knockback";if(t<600)return "hover-after-knockback";if(t<605)return "exit";return "complete";
    }
    @SubscribeEvent public void clientTick(TickEvent.ClientTickEvent event){
        if(event.phase!=TickEvent.Phase.START||!Boolean.getBoolean("rv.easy.qa"))return;
        try{
            Object mc=call(type("net.minecraft.client.Minecraft"),"func_71410_x"),who=VMReflect.get(mc,"field_71439_g");if(who==null)return;Object aircraft=call(type("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",who);
            if(aircraft!=null&&aircraft!=drone){drone=aircraft;ticks=0;active=true;samples.clear();cameras.clear();phase="waiting";kind=String.valueOf(call(drone,"getTypeName")).equals("rc-goblin-bomb")?"fuse":"movement";call(mc,"func_71381_h");}
            if(!active)return;ticks++;phase=phaseAt(ticks);keys.clear();forcedFocus=!phase.equals("focus-lost");VMReflect.set(mc,"field_71415_G",forcedFocus);Object settings=VMReflect.get(mc,"field_71474_y");
            if(Arrays.asList("before-arm","forward","focus-lost","focus-restored","before-drop","packet-drop","after-drop","fuse-forward").contains(phase))down(settings,"field_74351_w");
            if(Arrays.asList("lift","rearm","rearm-again","fuse-lift").contains(phase))down(settings,"field_74314_A");
            if(phase.equals("left"))down(settings,"field_74370_x");if(phase.equals("right"))down(settings,"field_74366_z");if(phase.equals("back"))down(settings,"field_74368_y");if(phase.equals("down"))down(settings,"field_151444_V");if(phase.equals("exit"))down(settings,"field_74311_E");
            if(ticks%5==0||!phase.equals(lastPhase)){Map<String,Object> marker=new LinkedHashMap<String,Object>();marker.put("phase",phase);marker.put("tick",ticks);marker.put("kind",kind);write(Paths.get(System.getProperty("rv.easy.server.root"),String.format("easy-stage-%s-%06d.json",kind,ticks)),marker);lastPhase=phase;}
            if(ticks%5==0)samples.add(sample(drone));
            if(phase.equals("complete")){Map<String,Object> report=new LinkedHashMap<String,Object>();report.put("kind",kind);report.put("physicalDeviceTested",false);report.put("samples",samples);report.put("cameras",cameras);report.put("mouseUpdateCalls",mouseUpdateCalls);report.put("mouseSampleCalls",mouseSampleCalls);report.put("captureCalls",captureCalls);report.put("mountedAfterExit",aircraft!=null);write(Paths.get("easy-client-"+kind+".json"),report);active=false;keys.clear();System.out.println("[RV Easy QA] client complete "+kind);}
        }catch(Throwable error){fail(error);}
    }
    public static void camera(Object event){if(!active)return;try{Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("tick",ticks);value.put("phase",phase);value.put("yaw",call(event,"getYaw"));value.put("pitch",call(event,"getPitch"));value.put("roll",call(event,"getRoll"));if(cameras.size()<2000)cameras.add(value);}catch(Throwable error){fail(error);}}
    public static boolean packet(Object aircraft,Object data,Object who){
        if(!Boolean.getBoolean("rv.easy.qa")||aircraft!=drone)return false;
        try{Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("tick",ticks);value.put("phase",phase);value.put("mode",VMReflect.get(data,"vmMode"));value.put("forward",VMReflect.get(data,"vmForward"));value.put("strafe",VMReflect.get(data,"vmStrafe"));value.put("lift",VMReflect.get(data,"vmLift"));value.put("pilot",call(aircraft,"isPilot",who));value.put("discardedByTransport",phase.equals("packet-drop"));packets.add(value);return phase.equals("packet-drop");}catch(Throwable error){fail(error);return false;}
    }
    public static Object motionCall(Object receiver,String name,Object[] args)throws Exception{
        double x=0,y=0,z=0;boolean movement=name.equals("func_70091_d")&&receiver==drone;if(movement){x=num(receiver,"field_70165_t");y=num(receiver,"field_70163_u");z=num(receiver,"field_70161_v");}Object answer=call(receiver,name,args);
        if(movement){Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("tick",ticks);value.put("phase",phase);value.put("requestedX",args[1]);value.put("requestedY",args[2]);value.put("requestedZ",args[3]);value.put("dx",num(receiver,"field_70165_t")-x);value.put("dy",num(receiver,"field_70163_u")-y);value.put("dz",num(receiver,"field_70161_v")-z);moves.add(value);}return answer;
    }
    @SubscribeEvent public void serverTick(TickEvent.ServerTickEvent event){
        if(event.phase!=TickEvent.Phase.START||drone==null||!Boolean.getBoolean("rv.easy.qa"))return;
        try{Path marker=null;try(DirectoryStream<Path> files=Files.newDirectoryStream(Paths.get("."),"easy-stage-"+kind+"-*.json")){for(Path path:files)if(marker==null||path.toString().compareTo(marker.toString())>0)marker=path;}if(marker==null)return;Map<?,?> state=new Gson().fromJson(new String(Files.readAllBytes(marker),"UTF-8"),Map.class);phase=state.get("phase").toString();ticks=((Number)state.get("tick")).intValue();
            if(phase.equals("knockback")&&!momentumInjected){momentumInjected=true;VMReflect.set(drone,"field_70159_w",100D);VMReflect.set(drone,"field_70181_x",100D);VMReflect.set(drone,"field_70179_y",100D);result.put("preexistingMomentumInjected",true);}
            if(ticks%5==0)samples.add(sample(drone));
            if(phase.equals("complete")){result.put("kind",kind);result.put("samples",samples);result.put("packets",packets);result.put("moves",moves);result.put("final",sample(drone));if(target!=null)result.put("targetHPAfter",call(target,"getHP"));write(Paths.get("easy-server-"+kind+".json"),result);drone=null;System.out.println("[RV Easy QA] server complete "+kind);}
        }catch(Throwable error){fail(error);}
    }
    public static boolean command(Object server,Object sender,String[] args){
        if(!Boolean.getBoolean("rv.easy.qa")||server!=sender||args.length!=1||!args[0].startsWith("rveasysetup"))return false;
        try{
            register();kind=args[0].endsWith("fuse")?"fuse":"movement";ticks=0;phase="waiting";samples.clear();moves.clear();packets.clear();result.clear();momentumInjected=false;player=call(call(server,"func_184103_al"),"func_152612_a","RVEasyQA");world=VMReflect.get(player,"field_70170_p");
            call(player,"func_184210_p");call(VMReflect.get(player,"field_71135_a"),"func_147364_a",8.5D,4D,8.5D,0F,45F);for(int x=-3;x<=3;x++)for(int z=-3;z<=4;z++)call(world,"func_72964_e",x,z);for(int z=-24;z<=64;z+=16)call(call(server,"func_71187_D"),"func_71556_a",server,"fill -24 4 "+z+" 40 24 "+Math.min(z+15,64)+" minecraft:air");
            Object item=call(type("net.minecraft.item.Item"),"func_111206_d",kind.equals("fuse")?"mcheli:rc-goblin-bomb":"mcheli:rc-goblin"),stack=type("net.minecraft.item.ItemStack").getConstructor(type("net.minecraft.item.Item")).newInstance(item);drone=call(item,"createAircraft",world,8.5D,4D,8.5D,stack);if(drone==null||!(Boolean)call(world,"func_72838_d",drone))throw new AssertionError("Native ground fixture rejected");call(drone,"setFuel",call(drone,"getMaxFuel"));call(drone,"setRotYaw",0F);call(drone,"resyncOrientationFromEuler");
            Object station=call(type("com.norwood.mcheli.uav.MCH_EntityUavStation"),"createHandheld",world,player,VMReflect.get(type("net.minecraft.util.EnumHand"),"MAIN_HAND"),Collections.singletonList(call(drone,"func_110124_au")),false);call(world,"func_72838_d",station);call(station,"pairUav",call(drone,"func_110124_au"));Object status=call(type("com.norwood.mcheli.uav.MCH_UavControl"),"connect",player,station,drone);if(!String.valueOf(status).equals("OK"))throw new AssertionError("Native tablet connect failed "+status);
            if(kind.equals("fuse")){call(call(server,"func_71187_D"),"func_71556_a",server,"fill 4 4 18 12 20 18 minecraft:stone");target=type("com.norwood.mcheli.tank.MCH_EntityTank").getConstructor(type("net.minecraft.world.World")).newInstance(world);call(target,"setTypeName","m1a2");call(target,"changeType","m1a2");call(target,"func_70107_b",8.5D,4D,40.5D);call(world,"func_72838_d",target);result.put("targetHPBefore",call(target,"getHP"));}
            result.put("nativeStationResult",String.valueOf(status));result.put("initial",sample(drone));System.out.println("[RV Easy QA] fixture "+kind);
        }catch(Throwable error){fail(error);}return true;
    }
}
