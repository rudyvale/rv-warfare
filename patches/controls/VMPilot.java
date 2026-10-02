package com.norwood.mcheli.vm;

import java.util.*;
import org.lwjgl.input.Keyboard;
import org.lwjgl.opengl.Display;

public final class VMPilot {
    private static final VMController input = VMController.INSTANCE;
    private static final Map<Object,Boolean> keys = new WeakHashMap<Object,Boolean>();
    private static boolean f8, previousMode;
    private static Object currentAircraft;
    private static double mousePitch, mouseRoll;
    private static long lastMouse;
    private static Object attitudeAircraft,attitude;
    private static double lastYaw,lastPitch,lastRoll;
    private static Object minecraft() throws Exception { return VMReflect.call(Class.forName("net.minecraft.client.Minecraft"),"func_71410_x"); }
    private static boolean focus() throws Exception {
        Object mc=minecraft();
        return Display.isActive() && !VMCalibration.showing && VMReflect.get(mc,"field_71462_r")==null && (Boolean)VMReflect.get(mc,"field_71415_G");
    }
    public static void frame() {
        try {
            boolean pressed=Keyboard.isCreated() && Keyboard.isKeyDown(Keyboard.KEY_F8);
            if(pressed&&!f8) VMCalibration.open();
            f8=pressed;
            input.poll(focus());
            boolean mode=input.down("mode");
            if(mode&&!previousMode){input.profile.setProperty("flight",input.acro()?"angle":"acro");boolean armed=input.armed;input.save();input.armed=armed;}
            previousMode=mode;
        } catch(Exception | LinkageError e){VMReflect.error("controller frame",e);}
    }
    public static void keys(Object handler,Object player,Object aircraft,boolean pilot) {
        try {
            input.poll(focus());
            if (currentAircraft != aircraft) { input.armed=false; Arrays.fill(input.values,0); currentAircraft=aircraft; mousePitch=0; mouseRoll=0; }
            if(!input.enabled()) return;
            boolean active=input.connected&&input.armed&&focus();
            bind(handler,"KeyUseWeapon",active&&input.down("fire"));
            bind(handler,"KeySwitchWeapon1",active&&input.down("weapon"));
            bind(handler,"KeyBrake",active&&input.down("brake"));
            bind(handler,"KeyUnmount",active&&input.down("exit"));
            if(!pilot || VMFlight.drone(aircraft)) return;
            double gas=active?input.values[3]:0;
            boolean tank=aircraft.getClass().getName().contains("Tank") || aircraft.getClass().getName().contains("Vehicle");
            if(!input.gamepad() && tank) gas=active?gas*2-1:0;
            if(!input.gamepad() && !tank){double current=VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"));gas=active?gas-current:-current;}
            bind(handler,"KeyUp",gas>.07); bind(handler,"KeyDown",gas<-.07);
            bind(handler,"KeyRight",active&&input.values[2]>.15); bind(handler,"KeyLeft",active&&input.values[2]<-.15);
        }catch(Exception e){VMReflect.error("controller buttons",e);}
    }
    private static void bind(Object handler,String field,boolean pressed) throws Exception {
        Object key=VMReflect.get(handler,field);
        boolean keyboard=(Boolean)VMReflect.get(key,"isPress");
        boolean prior=Boolean.TRUE.equals(keys.put(key,pressed));
        VMReflect.set(key,"isPress",keyboard||pressed);
        VMReflect.set(key,"isBeforePress",(Boolean)VMReflect.get(key,"isBeforePress")||prior);
    }
    public static boolean packet(boolean original,Object aircraft,Object data,boolean pilot) {
        try {
            if(!input.enabled())return VMFlight.release(aircraft)||original;
            if(!pilot || !VMFlight.drone(aircraft)) return original || input.enabled();
            double desired=0;
            if(input.connected&&input.armed&&focus()) {
                desired=input.gamepad()? VMControlMath.clamp(VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"))+input.values[3]*.022,0,1):input.values[3];
            }
            VMReflect.set(data,"vmThrottle",(float)desired); VMFlight.local(aircraft,desired);
            VMReflect.call(data,"setThrottleUp",false); VMReflect.call(data,"setThrottleDown",false);
            VMReflect.set(aircraft,"throttleUp",false); VMReflect.set(aircraft,"throttleDown",false);
            return true;
        }catch(Exception e){VMReflect.error("controller packet",e);return original;}
    }
    public static void mouse(Object handler) {
        try {
            long now=System.nanoTime(); double dt=lastMouse==0?1.0/60:Math.min(.05,(now-lastMouse)/1e9); lastMouse=now;
            Object player=VMReflect.get(minecraft(),"field_71439_g");
            if(player==null) return;
            Object aircraft=VMReflect.call(Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",player);
            if(aircraft==null || !input.enabled() || !input.connected || !input.armed || !focus()) return;
            double rate=VMControlMath.clamp(input.setting("rate",110),45,240)*(input.down("aim")?.3:1);
            VMReflect.set(handler,"mouseDeltaX",input.values[0]*rate*dt/.15);
            VMReflect.set(handler,"mouseDeltaY",-input.values[1]*rate*dt/.15);
            VMReflect.set(handler,"prevMouseDeltaX",input.values[0]*rate*dt/.15);
            VMReflect.set(handler,"prevMouseDeltaY",-input.values[1]*rate*dt/.15);
        }catch(Exception e){VMReflect.error("controller aim",e);}
    }
    public static boolean angles(Object aircraft,Object player,boolean fixRot,float fixYaw,float fixPitch,float dx,float dy,float ix,float iy,float seconds) {
        boolean fpv=VMFlight.drone(aircraft);
        try {
            boolean controller=input.enabled();
            if(!fpv && (!controller || !aircraft.getClass().getName().contains("Heli"))) return false;
            if(!VMReflect.remote(aircraft) || !(Boolean)VMReflect.call(aircraft,"isPilot",player)) return false;
            double dt=VMControlMath.clamp(seconds,0,.05), roll=0,pitch=0,yaw=0;
            if(focus() && !(Boolean)VMReflect.call(aircraft,"isFreeLookMode")) {
                if(controller) { if(input.connected&&input.armed){roll=input.values[0];pitch=input.values[1];yaw=input.values[2];} }
                else {
                    mouseRoll=VMControlMath.smooth(mouseRoll,VMControlMath.clamp(dx*.002/Math.max(dt,.005),-1,1),dt,.1);
                    mousePitch=VMControlMath.smooth(mousePitch,VMControlMath.clamp(-dy*.002/Math.max(dt,.005),-1,1),dt,.1);
                    roll=mouseRoll; pitch=mousePitch;
                    yaw=((Boolean)VMReflect.get(aircraft,"moveRight")?1:0)-((Boolean)VMReflect.get(aircraft,"moveLeft")?1:0);
                }
            }
            double oldYaw=VMReflect.num(VMReflect.call(aircraft,"getYaw")), oldPitch=VMReflect.num(VMReflect.call(aircraft,"getPitch")), oldRoll=VMReflect.num(VMReflect.call(aircraft,"getRoll"));
            double rate=controller?VMControlMath.clamp(input.setting("rate",110),45,240):75;
            double newYaw=oldYaw+yaw*rate*dt,newPitch,newRoll;
            if(fpv&&input.acro()) {
                float rad=(float)(Math.PI/180);
                if(attitude==null || attitudeAircraft!=aircraft || Math.abs(oldYaw-lastYaw)+Math.abs(oldPitch-lastPitch)+Math.abs(oldRoll-lastRoll)>.1) {
                    attitude=Class.forName("org.joml.Quaternionf").newInstance();attitudeAircraft=aircraft;
                    VMReflect.call(attitude,"rotateY",(float)-oldYaw*rad);VMReflect.call(attitude,"rotateX",(float)oldPitch*rad);VMReflect.call(attitude,"rotateZ",(float)oldRoll*rad);
                }
                VMReflect.call(attitude,"rotateY",(float)(-yaw*rate*dt)*rad);VMReflect.call(attitude,"rotateX",(float)(pitch*rate*dt)*rad);VMReflect.call(attitude,"rotateZ",(float)(-roll*rate*dt)*rad);VMReflect.call(attitude,"normalize");
                float[] rotation=VMControlMath.worldEuler(VMReflect.num(VMReflect.get(attitude,"x")),VMReflect.num(VMReflect.get(attitude,"y")),VMReflect.num(VMReflect.get(attitude,"z")),VMReflect.num(VMReflect.get(attitude,"w")));
                newPitch=rotation[0];newYaw=rotation[1];newRoll=rotation[2];
            }else {
                attitude=null;
                double max=fpv?35:25;
                newPitch=VMControlMath.angle(oldPitch,pitch*max,dt,rate);newRoll=VMControlMath.angle(oldRoll,-roll*max,dt,rate);
            }
            if((Boolean)VMReflect.get(aircraft,"field_70122_E")){newPitch=oldPitch;newRoll=oldRoll;attitude=null;}
            lastYaw=newYaw;lastPitch=newPitch;lastRoll=newRoll;
            VMReflect.call(aircraft,"setRotYaw",(float)newYaw);VMReflect.call(aircraft,"setRotPitch",(float)newPitch);VMReflect.call(aircraft,"setRotRoll",(float)newRoll);
            VMReflect.call(aircraft,"resyncOrientationFromEuler");
            VMReflect.set(aircraft,"prevRotationRoll",(float)newRoll);VMReflect.set(aircraft,"field_70127_C",(float)newPitch);VMReflect.set(aircraft,"field_70126_B",(float)newYaw);
            VMReflect.set(player,"field_70177_z",(float)newYaw+fixYaw);VMReflect.set(player,"field_70125_A",(float)newPitch+fixPitch);
            VMReflect.set(player,"field_70126_B",(float)newYaw+fixYaw);VMReflect.set(player,"field_70127_C",(float)newPitch+fixPitch);
            if(Math.abs(oldYaw-newYaw)+Math.abs(oldPitch-newPitch)+Math.abs(oldRoll-newRoll)>.00001) VMReflect.set(aircraft,"aircraftRotChanged",true);
            return true;
        }catch(Exception | LinkageError e){VMReflect.error("flight controls",e);return false;}
    }
    public static float cameraRoll(float original,Object aircraft) {
        return VMFlight.drone(aircraft)&&!input.acro()?(float)VMControlMath.clamp(original*.55,-18,18):original;
    }
}
