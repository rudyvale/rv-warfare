package com.norwood.mcheli.vm;

import java.util.*;
import org.lwjgl.input.Keyboard;
import org.lwjgl.input.Mouse;
import org.lwjgl.opengl.Display;

public final class VMEasy {
    private static final double HORIZONTAL_SPEED=.60;
    private static final double VERTICAL_SPEED=.30;
    private static final Map<Object,double[]> states=Collections.synchronizedMap(new WeakHashMap<Object,double[]>());
    private static Object localAircraft;
    private static boolean localArmed;
    private static double heading,lookPitch;
    public static boolean selected(){return !VMController.INSTANCE.enabled()&&!VMController.INSTANCE.profile.getProperty("keyboardFlight","easy").equals("advanced");}
    public static boolean client(Object aircraft){return VMFlight.drone(aircraft)&&selected();}
    public static boolean focus(){
        try{Object mc=VMClient.minecraft();return Display.isActive()&&!VMCalibration.showing&&VMReflect.get(mc,"field_71462_r")==null&&(Boolean)VMReflect.get(mc,"field_71415_G");}
        catch(Exception e){return false;}
    }
    public static boolean key(String field)throws Exception{
        Object mc=VMClient.minecraft(),binding=VMReflect.get(VMReflect.get(mc,"field_71474_y"),field);int code=((Number)VMReflect.call(binding,"func_151463_i")).intValue();
        return code<0?Mouse.isCreated()&&Mouse.isButtonDown(code+100):Keyboard.isCreated()&&code>0&&Keyboard.isKeyDown(code);
    }
    public static String keyName(String field)throws Exception{
        Object mc=VMClient.minecraft(),binding=VMReflect.get(VMReflect.get(mc,"field_71474_y"),field);int code=((Number)VMReflect.call(binding,"func_151463_i")).intValue();return code<0?VMClient.text("Mouse ","Мышь ")+(code+101):code==0?VMClient.text("Unbound","Не назначено"):String.valueOf(Keyboard.getKeyName(code));
    }
    private static void local(Object aircraft)throws Exception{
        if(localAircraft!=aircraft){localAircraft=aircraft;localArmed=false;lookPitch=0;heading=VMReflect.num(VMReflect.call(aircraft,"getYaw"));}
    }
    public static void capture(Object handler,Object aircraft)throws Exception{
        if(!client(aircraft))return;local(aircraft);
        if(!focus()){localArmed=false;return;}
        Object mc=VMClient.minecraft(),mouse=VMReflect.get(mc,"field_71417_B"),settings=VMReflect.get(mc,"field_71474_y");
        double sensitivity=VMReflect.num(VMReflect.get(settings,"field_74341_c"))*.6+.2,factor=sensitivity*sensitivity*sensitivity*1.2;
        double dx=VMReflect.num(VMReflect.get(mouse,"field_74377_a")),dy=VMReflect.num(VMReflect.get(mouse,"field_74375_b"));if((Boolean)VMReflect.get(settings,"field_74338_d"))dy=-dy;
        heading=wrap(heading+VMControlMath.clamp(dx*factor,-12,12));lookPitch=VMControlMath.clamp(lookPitch-dy*factor,-75,75);
    }
    private static double wrap(double value){return (value%360+540)%360-180;}
    public static boolean packet(Object aircraft,Object data)throws Exception{
        if(!client(aircraft))return false;local(aircraft);boolean active=focus();
        if(!active)localArmed=false;else if(key("field_74314_A"))localArmed=true;
        VMReflect.set(data,"vmMode",(byte)(active?2:3));VMReflect.set(data,"vmForward",(float)(active&&localArmed?((key("field_74351_w")?1:0)-(key("field_74368_y")?1:0)):0));VMReflect.set(data,"vmStrafe",(float)(active&&localArmed?((key("field_74366_z")?1:0)-(key("field_74370_x")?1:0)):0));VMReflect.set(data,"vmLift",(float)(active?((key("field_74314_A")?1:0)-(localArmed&&key("field_151444_V")?1:0)):0));
        VMReflect.set(data,"vmThrottle",-1F);VMReflect.call(data,"setThrottleUp",false);VMReflect.call(data,"setThrottleDown",false);VMReflect.set(aircraft,"throttleUp",false);VMReflect.set(aircraft,"throttleDown",false);VMReflect.set(aircraft,"moveLeft",false);VMReflect.set(aircraft,"moveRight",false);
        receive(aircraft,data,VMReflect.get(VMClient.minecraft(),"field_71439_g"));return true;
    }
    public static boolean receive(Object aircraft,Object data,Object player)throws Exception{
        int mode=((Number)VMReflect.get(data,"vmMode")).intValue();
        if(player==null||!VMFlight.drone(aircraft)||!(Boolean)VMReflect.call(aircraft,"isPilot",player))return mode==2||mode==3;
        if(mode!=2&&mode!=3){states.remove(aircraft);return false;}
        double f=VMReflect.num(VMReflect.get(data,"vmForward")),s=VMReflect.num(VMReflect.get(data,"vmStrafe")),u=VMReflect.num(VMReflect.get(data,"vmLift"));
        if(!Double.isFinite(f+s+u)||Math.abs(f)>1||Math.abs(s)>1||Math.abs(u)>1){states.put(aircraft,new double[]{0,0,0,System.nanoTime()/1e9,0});control(aircraft);return true;}
        if(mode==3){f=0;s=0;u=0;}
        double[] old=states.get(aircraft);boolean armed=mode==2&&(old!=null&&old[4]>0||u>.5);states.put(aircraft,new double[]{f,s,u,System.nanoTime()/1e9,armed?1:0});return true;
    }
    public static void reset(Object aircraft){states.remove(aircraft);if(localAircraft==aircraft){localArmed=false;}}
    public static boolean control(Object aircraft){
        double[] state=states.get(aircraft);if(state==null)return false;
        try{
            boolean armed=state[4]>0&&System.nanoTime()/1e9-state[3]<=.4&&VMReflect.call(aircraft,"getRiddenByEntity")!=null&&!(Boolean)VMReflect.call(aircraft,"isDestroyed")&&(Boolean)VMReflect.call(aircraft,"canUseFuel",true);
            if(!armed)state[4]=0;double gas=armed?.5+state[2]*.15:0;VMReflect.call(aircraft,"setCurrentThrottle",gas);if(!VMReflect.remote(aircraft))VMReflect.call(aircraft,"setThrottle",gas);return true;
        }catch(Exception e){VMReflect.error("Easy flight throttle",e);return true;}
    }
    public static boolean motion(Object aircraft){
        double[] state=states.get(aircraft);if(state==null)return false;
        try{
            if(VMReflect.remote(aircraft))return false;
            control(aircraft);boolean armed=state[4]>0;double yaw=VMReflect.num(VMReflect.call(aircraft,"getYaw"));if(!Double.isFinite(yaw)){state[4]=0;armed=false;yaw=0;VMReflect.call(aircraft,"setRotYaw",0F);VMReflect.call(aircraft,"setCurrentThrottle",0D);}yaw=Math.toRadians(wrap(yaw));
            double magnitude=Math.max(1,Math.sqrt(state[0]*state[0]+state[1]*state[1])),f=armed?state[0]/magnitude:0,s=armed?state[1]/magnitude:0;
            double vx=VMReflect.num(VMReflect.get(aircraft,"field_70159_w")),vy=VMReflect.num(VMReflect.get(aircraft,"field_70181_x")),vz=VMReflect.num(VMReflect.get(aircraft,"field_70179_y"));
            if(!Double.isFinite(vx))vx=0;if(!Double.isFinite(vy))vy=0;if(!Double.isFinite(vz))vz=0;
            vx=VMControlMath.smooth(vx,(-Math.sin(yaw)*f+Math.cos(yaw)*s)*HORIZONTAL_SPEED,.05,.10);vz=VMControlMath.smooth(vz,(Math.cos(yaw)*f+Math.sin(yaw)*s)*HORIZONTAL_SPEED,.05,.10);vy=armed?VMControlMath.smooth(vy,state[2]*VERTICAL_SPEED,.05,.10):Math.max(-.5,vy-.04);
            double horizontal=Math.hypot(vx,vz);if(horizontal>HORIZONTAL_SPEED){vx*=HORIZONTAL_SPEED/horizontal;vz*=HORIZONTAL_SPEED/horizontal;}vy=VMControlMath.clamp(vy,-.5,VERTICAL_SPEED);
            VMReflect.set(aircraft,"field_70159_w",vx);VMReflect.set(aircraft,"field_70181_x",vy);VMReflect.set(aircraft,"field_70179_y",vz);
            VMReflect.call(aircraft,"setRotPitch",(float)(f*10));VMReflect.call(aircraft,"setRotRoll",(float)(-s*12));VMReflect.call(aircraft,"resyncOrientationFromEuler");
            if(VMImpact.droneMotion(aircraft))return true;
            Object mover=VMReflect.get(Class.forName("net.minecraft.entity.MoverType"),"SELF");VMReflect.call(aircraft,"func_70091_d",mover,vx,vy,vz);return true;
        }catch(Exception|LinkageError e){VMReflect.error("Easy flight motion",e);return false;}
    }
    public static boolean angles(Object aircraft,Object player)throws Exception{
        if(!client(aircraft)||!VMReflect.remote(aircraft)||!(Boolean)VMReflect.call(aircraft,"isPilot",player))return false;local(aircraft);double[] state=states.get(aircraft);double f=state==null?0:state[0],s=state==null?0:state[1];
        VMReflect.call(aircraft,"setRotYaw",(float)heading);VMReflect.call(aircraft,"setRotPitch",(float)(f*10));VMReflect.call(aircraft,"setRotRoll",(float)(-s*12));VMReflect.call(aircraft,"resyncOrientationFromEuler");VMReflect.set(aircraft,"field_70126_B",(float)heading);VMReflect.set(aircraft,"field_70127_C",(float)(f*10));VMReflect.set(aircraft,"prevRotationRoll",(float)(-s*12));VMReflect.set(player,"field_70177_z",(float)heading);VMReflect.set(player,"field_70125_A",(float)lookPitch);VMReflect.set(player,"field_70126_B",(float)heading);VMReflect.set(player,"field_70127_C",(float)lookPitch);VMReflect.set(aircraft,"aircraftRotChanged",true);return true;
    }
    public static boolean camera(Object event){
        try{Object player=VMReflect.get(VMClient.minecraft(),"field_71439_g");if(player==null)return false;Object aircraft=VMReflect.call(Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",player);if(!client(aircraft))return false;local(aircraft);VMReflect.call(event,"setYaw",(float)(heading+180));VMReflect.call(event,"setPitch",(float)lookPitch);VMReflect.call(event,"setRoll",0F);return true;}
        catch(Exception|LinkageError e){VMReflect.error("Easy flight camera",e);return false;}
    }
}
