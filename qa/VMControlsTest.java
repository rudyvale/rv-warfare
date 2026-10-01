import com.norwood.mcheli.vm.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import net.java.games.input.*;

public final class VMControlsTest {
    private static int passed;
    private static void check(boolean condition,String name){if(!condition)throw new AssertionError(name);passed++;System.out.println("PASS "+name);}
    private static void near(double actual,double expected,String name){check(Math.abs(actual-expected)<1e-5,name+" ("+actual+")");}
    private static Component[] components(final float[] axes){
        Component[] result=new Component[4];
        final Component.Identifier.Axis[] ids={Component.Identifier.Axis.X,Component.Identifier.Axis.Y,Component.Identifier.Axis.Z,Component.Identifier.Axis.RZ};
        for(int i=0;i<4;i++){final int j=i;result[i]=(Component)Proxy.newProxyInstance(VMControlsTest.class.getClassLoader(),new Class<?>[]{Component.class},(p,m,a)->{
            switch(m.getName()){case "getName":return "axis "+j;case "getIdentifier":return ids[j];case "isAnalog":return true;case "isRelative":return false;case "getPollData":return axes[j];case "getDeadZone":return 0F;case "toString":return "axis "+j;default:return null;}
        });}return result;
    }
    public static void main(String[] args)throws Exception{
        near(VMControlMath.axis(.03,-1,0,1,false,.05,.35),0,"center noise rejected");
        near(VMControlMath.axis(1,-1,0,1,false,.05,.8),1,"expo preserves full travel");
        near(VMControlMath.axis(-1,-1,0,1,true,.05,.8),1,"inverted axis");
        near(VMControlMath.axis(.1,-.7,.1,.9,false,.03,.3),0,"asymmetric center");
        near(VMControlMath.axis(Float.NaN,-1,0,1,false,0,0),0,"nonfinite input neutral");
        near(VMControlMath.axis(1,0,0,0,false,0,0),0,"invalid calibration neutral");
        near(VMControlMath.throttle(-1,-1,1,false),0,"radio throttle minimum");
        near(VMControlMath.throttle(1,-1,1,false),1,"radio throttle maximum");
        near(VMControlMath.throttle(0,-1,1,false),.5,"radio throttle hover center");
        near(VMControlMath.throttle(1,-1,1,true),0,"reverse radio throttle");
        double v60=0,v120=0;for(int i=0;i<60;i++)v60=VMControlMath.smooth(v60,1,1.0/60,.1);for(int i=0;i<120;i++)v120=VMControlMath.smooth(v120,1,1.0/120,.1);
        near(v60,v120,"filter independent of frame rate");
        check(Math.abs(VMControlMath.angle(35,0,.05,110))<35,"angle mode levels after release");
        check(Math.abs(VMControlMath.angle(0,35,.05,110))<=5.5,"turn rate bounded");
        for(String axis:new String[]{"rotateX","rotateY","rotateZ"}){
            Object q=Class.forName("org.joml.Quaternionf").newInstance();boolean finite=true;
            float[] angles=null;
            for(int i=0;i<720;i++){VMReflect.call(q,axis,(float)Math.toRadians(.5));angles=VMControlMath.euler(VMReflect.num(VMReflect.get(q,"x")),VMReflect.num(VMReflect.get(q,"y")),VMReflect.num(VMReflect.get(q,"z")),VMReflect.num(VMReflect.get(q,"w")));for(float a:angles)finite&=Float.isFinite(a);}
            check(finite,"actual JOML full flip stays finite: "+axis);
            check(Math.abs(Math.sin(Math.toRadians(angles[0])))+Math.abs(Math.sin(Math.toRadians(angles[1])))+Math.abs(Math.sin(Math.toRadians(angles[2])))<.001,"full flip returns to start: "+axis);
        }
        final float[] raw={0,0,0,1};final boolean[] alive={true};final Component[] c=components(raw);
        Controller fake=(Controller)Proxy.newProxyInstance(VMControlsTest.class.getClassLoader(),new Class<?>[]{Controller.class},(p,m,a)->{
            switch(m.getName()){case "getName":return "Test radio";case "getType":return Controller.Type.STICK;case "getComponents":return c;case "poll":return alive[0];case "toString":return "Test radio";default:return null;}
        });
        VMController input=new VMController();input.setRoot(Files.createTempDirectory("vm-controller-test"));input.device=fake;
        input.profile.setProperty("enabled","true");input.profile.setProperty("kind","radio");input.profile.setProperty("device",VMController.identity(fake));
        for(int i=0;i<4;i++){String a=VMController.ACTIONS[i];input.profile.setProperty(a+".axis",""+i);input.profile.setProperty(a+".min","-1");input.profile.setProperty(a+".max","1");input.profile.setProperty(a+".center","0");}
        input.poll(true);check(!input.armed&&input.values[3]==0,"high throttle cannot arm on connect");
        raw[3]=-1;input.poll(true);check(input.armed,"low throttle arms");
        input.poll(false);check(!input.armed&&input.values[3]==0,"focus loss cuts throttle");
        raw[3]=1;input.poll(true);check(!input.armed,"focus regain requires low throttle");
        input.profile.setProperty("yaw.axis","0");check(!input.mappingValid(),"duplicate axis rejected");input.profile.setProperty("yaw.axis","2");
        alive[0]=false;input.poll(true);check(!input.connected&&input.device==null&&input.values[3]==0,"disconnect drops stale device and gas");
        Class<?> dataClass=Class.forName("com.norwood.mcheli.networking.data.DataPlayerControlVehicle");
        Object data=dataClass.newInstance();near(VMReflect.num(VMReflect.get(data,"vmThrottle")),-1,"keyboard packet default");
        VMReflect.set(data,"vmThrottle",.63F);VMReflect.set(data,"unhitchChainId",12345);
        Object buffer=VMReflect.call(Class.forName("io.netty.buffer.Unpooled"),"buffer");VMReflect.call(data,"serialize",buffer);
        Object decoded=dataClass.getConstructor(Class.forName("io.netty.buffer.ByteBuf")).newInstance(buffer);
        near(VMReflect.num(VMReflect.get(decoded,"vmThrottle")),.63,"analog network round trip");
        check(VMReflect.num(VMReflect.get(decoded,"unhitchChainId"))==12345,"derived packet data preserved");
        check(VMReflect.num(VMReflect.call(buffer,"readableBytes"))==0,"packet has no trailing data");VMReflect.call(buffer,"release");
        VMReflect.set(data,"vmThrottle",Float.NaN);
        check(VMControlMath.clamp(Double.POSITIVE_INFINITY,0,1)==0,"invalid throttle fails closed");
        System.out.println("VM controls: "+passed+" checks passed");
    }
}
