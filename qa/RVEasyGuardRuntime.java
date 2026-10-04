import com.google.gson.Gson;
import com.norwood.mcheli.vm.VMReflect;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

public final class RVEasyGuardRuntime {
    private static Object aircraft,pilot,other,world;
    private static final List<Map<String,Object>> cases=new ArrayList<Map<String,Object>>();
    private static Class<?> type(String name)throws Exception{return Class.forName(name);}
    private static Object call(Object receiver,String name,Object... args)throws Exception{return VMReflect.call(receiver,name,args);}
    private static double number(Object value){return ((Number)value).doubleValue();}
    private static double speedLimit(String property,double fallback){String raw=System.getProperty(property);if(raw==null)return fallback;double value=Double.parseDouble(raw);if(!Double.isFinite(value)||value<=0)throw new IllegalArgumentException("Invalid speed limit: "+property);return value;}
    private static Map<String,Object> snapshot()throws Exception{
        Map<String,Object> value=new LinkedHashMap<String,Object>();
        for(String field:new String[]{"field_70165_t","field_70163_u","field_70161_v","field_70159_w","field_70181_x","field_70179_y"})value.put(field,VMReflect.get(aircraft,field));
        value.put("throttle",call(aircraft,"getCurrentThrottle"));value.put("yaw",call(aircraft,"getYaw"));value.put("pitch",call(aircraft,"getPitch"));value.put("roll",call(aircraft,"getRoll"));value.put("pilot",call(aircraft,"isPilot",pilot));value.put("foreignPilot",call(aircraft,"isPilot",other));
        double[] state=(double[])((Map<?,?>)VMReflect.get(type("com.norwood.mcheli.vm.VMEasy"),"states")).get(aircraft);value.put("easyState",state==null?null:state.clone());return value;
    }
    private static Object packet(int mode,float f,float s,float u)throws Exception{
        Class<?> dataType=type("com.norwood.mcheli.networking.data.DataPlayerControlVehicle");Object original=dataType.newInstance();VMReflect.set(original,"vmMode",(byte)mode);VMReflect.set(original,"vmForward",f);VMReflect.set(original,"vmStrafe",s);VMReflect.set(original,"vmLift",u);VMReflect.set(original,"vmThrottle",-1F);
        Object buffer=call(type("io.netty.buffer.Unpooled"),"buffer"),decoded;
        try{call(original,"serialize",buffer);decoded=dataType.getConstructor(type("io.netty.buffer.ByteBuf")).newInstance(buffer);if(((Number)call(buffer,"readableBytes")).intValue()!=0)throw new AssertionError("Native packet leaves trailing bytes");for(String field:new String[]{"vmMode","vmForward","vmStrafe","vmLift","vmThrottle"})if(!String.valueOf(VMReflect.get(original,field)).equals(String.valueOf(VMReflect.get(decoded,field))))throw new AssertionError("Native roundtrip changed "+field);}finally{call(buffer,"release");}
        return type("com.norwood.mcheli.networking.packet.control.PacketPlayerControlHeli").getConstructor(dataType).newInstance(decoded);
    }
    private static void dispatch(Object packet,Object sender)throws Exception{call(packet,"onReceive",sender);call(type("com.norwood.mcheli.vm.VMEasy"),"control",aircraft);}
    private static void arm()throws Exception{dispatch(packet(2,.4F,-.2F,1F),pilot);if(number(call(aircraft,"getCurrentThrottle"))<.6)throw new AssertionError("Actual pilot native handler did not arm");}
    private static void finiteMotion()throws Exception{
        Map<String,Object> before=snapshot();call(aircraft,"func_70071_h_");Map<String,Object> after=snapshot();
        for(Object value:after.values())if(value instanceof Number&&!Double.isFinite(number(value)))throw new AssertionError("Nonfinite actual aircraft field");
        double dx=number(after.get("field_70165_t"))-number(before.get("field_70165_t")),dy=number(after.get("field_70163_u"))-number(before.get("field_70163_u")),dz=number(after.get("field_70161_v"))-number(before.get("field_70161_v"));double horizontalLimit=speedLimit("rv.easy.guard.maxHorizontalSpeed",.38),verticalLimit=speedLimit("rv.easy.guard.maxVerticalSpeed",.22);if(Math.hypot(dx,dz)>horizontalLimit+.000001||dy<-.500001||dy>verticalLimit+.000001)throw new AssertionError("Actual native tick exceeds bounded displacement");
    }
    private static void foreign(int mode,boolean deep)throws Exception{
        arm();Map<String,Object> before=snapshot();Object incoming=packet(mode,Float.NaN,Float.POSITIVE_INFINITY,2F);
        if(deep)call(incoming,"process",aircraft,VMReflect.get(incoming,"controlBaseData"),other);else call(incoming,"onReceive",other);
        Map<String,Object> after=snapshot();if(!new Gson().toJson(before).equals(new Gson().toJson(after)))throw new AssertionError("Foreign sender mutated native target/state mode="+mode+" deep="+deep);
        Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("case","foreign-mode-"+mode+(deep?"-process":"-onReceive"));value.put("before",before);value.put("after",after);value.put("passed",true);cases.add(value);
    }
    private static void invalid(String field,float input)throws Exception{
        arm();Object incoming=packet(2,.4F,-.2F,1F),data=VMReflect.get(incoming,"controlBaseData");VMReflect.set(data,field,input);incoming=packet(2,((Number)VMReflect.get(data,"vmForward")).floatValue(),((Number)VMReflect.get(data,"vmStrafe")).floatValue(),((Number)VMReflect.get(data,"vmLift")).floatValue());dispatch(incoming,pilot);
        Map<String,Object> after=snapshot();double[] state=(double[])after.get("easyState");if(number(after.get("throttle"))!=0||state==null||state[0]!=0||state[1]!=0||state[2]!=0||state[4]!=0)throw new AssertionError("Malformed pilot intent did not neutralize/disarm");finiteMotion();
        Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("case","malformed-"+field+"-"+input);value.put("after",snapshot());value.put("nativeCodecRoundTrip",true);value.put("passed",true);cases.add(value);
    }
    public static boolean command(Object server,Object sender,String[] args){
        if(!Boolean.getBoolean("rv.easy.guard.qa")||sender!=server||args.length!=1||!args[0].equals("rveasyguards"))return false;
        Map<String,Object> result=new LinkedHashMap<String,Object>();
        try{
            pilot=call(call(server,"func_184103_al"),"func_152612_a","RVGuardPilot");other=call(call(server,"func_184103_al"),"func_152612_a","RVGuardOther");if(pilot==null||other==null)throw new AssertionError("Two real native players required");world=VMReflect.get(pilot,"field_70170_p");
            call(pilot,"func_184210_p");call(other,"func_184210_p");call(VMReflect.get(pilot,"field_71135_a"),"func_147364_a",8.5D,4D,8.5D,0F,0F);call(VMReflect.get(other,"field_71135_a"),"func_147364_a",20.5D,4D,8.5D,0F,0F);
            Object item=call(type("net.minecraft.item.Item"),"func_111206_d","mcheli:rc-goblin"),stack=type("net.minecraft.item.ItemStack").getConstructor(type("net.minecraft.item.Item")).newInstance(item);aircraft=call(item,"createAircraft",world,8.5D,8D,8.5D,stack);if(aircraft==null||!(Boolean)call(world,"func_72838_d",aircraft))throw new AssertionError("Actual drone spawn failed");call(aircraft,"setFuel",call(aircraft,"getMaxFuel"));
            Object station=call(type("com.norwood.mcheli.uav.MCH_EntityUavStation"),"createHandheld",world,pilot,VMReflect.get(type("net.minecraft.util.EnumHand"),"MAIN_HAND"),Collections.singletonList(call(aircraft,"func_110124_au")),false);call(world,"func_72838_d",station);call(station,"pairUav",call(aircraft,"func_110124_au"));if(!"OK".equals(String.valueOf(call(type("com.norwood.mcheli.uav.MCH_UavControl"),"connect",pilot,station,aircraft))))throw new AssertionError("Actual station pairing failed");
            for(int mode:new int[]{0,1,2,3}){foreign(mode,false);foreign(mode,true);}
            for(String field:new String[]{"vmForward","vmStrafe","vmLift"})for(float input:new float[]{Float.NaN,Float.POSITIVE_INFINITY,Float.NEGATIVE_INFINITY,1.01F,-1.01F})invalid(field,input);
            arm();dispatch(packet(3,1F,1F,1F),pilot);finiteMotion();if(number(call(aircraft,"getCurrentThrottle"))!=0)throw new AssertionError("Mode3 retained motor power");Map<String,Object> neutral=new LinkedHashMap<String,Object>();neutral.put("case","valid-mode3-disarms");neutral.put("after",snapshot());neutral.put("passed",true);cases.add(neutral);
            arm();call(aircraft,"setRotYaw",Float.NaN);VMReflect.set(aircraft,"field_70159_w",Double.POSITIVE_INFINITY);VMReflect.set(aircraft,"field_70181_x",Double.NaN);VMReflect.set(aircraft,"field_70179_y",Double.NEGATIVE_INFINITY);finiteMotion();if(number(call(aircraft,"getCurrentThrottle"))!=0)throw new AssertionError("Nonfinite yaw did not cut motor");Map<String,Object> sanitized=new LinkedHashMap<String,Object>();sanitized.put("case","nonfinite-native-yaw-momentum");sanitized.put("after",snapshot());sanitized.put("passed",true);cases.add(sanitized);
            result.put("passed",true);result.put("actualNativeHandlerTested",true);result.put("actualTransportTested",false);result.put("pilotClass",pilot.getClass().getName());result.put("otherClass",other.getClass().getName());result.put("fakePlayers",type("net.minecraftforge.common.util.FakePlayer").isInstance(pilot)||type("net.minecraftforge.common.util.FakePlayer").isInstance(other));result.put("cases",cases);
        }catch(Throwable error){result.put("passed",false);result.put("error",error.toString());result.put("completedCases",cases);error.printStackTrace();}
        try{Files.write(Paths.get("easy-guards.json"),new Gson().toJson(result).getBytes("UTF-8"));}catch(Exception error){error.printStackTrace();}return true;
    }
}
