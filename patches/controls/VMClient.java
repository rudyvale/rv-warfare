package com.norwood.mcheli.vm;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.lwjgl.input.Keyboard;

public final class VMClient {
    private static final Properties settings=new Properties();
    private static final Path file=Paths.get("config","rv-client.properties");
    private static long nextLoad,stamp=-2;
    private static Object handler;
    public static volatile int effectLimit=96,trailSteps=4;
    public static volatile double effectRange=96;
    public static volatile long particlesDrawn,particlesSkipped,hitsReceived;
    public static volatile int lastHitCode=-1,lastDamage;
    public static volatile long hitTime;
    private static long lastHudSample;
    private static String[] lines=new String[0];
    public static String profile="balanced";
    public static synchronized void reload() {
        long now=System.currentTimeMillis();if(now<nextLoad)return;nextLoad=now+1000;
        try {
            long t=Files.exists(file)?Files.getLastModifiedTime(file).toMillis():-1;
            if(t==stamp)return;stamp=t;settings.clear();
            if(t>=0&&Files.size(file)<=16384)try(InputStream in=Files.newInputStream(file)){settings.load(in);}
            profile=settings.getProperty("profile","balanced");
            if(profile.equals("low")){effectLimit=40;effectRange=48;trailSteps=2;}
            else if(profile.equals("quality")){effectLimit=160;effectRange=128;trailSteps=8;}
            else{profile="balanced";effectLimit=96;effectRange=96;trailSteps=4;}
        }catch(IOException e){VMReflect.error("client preferences",e);}
    }
    public static boolean flag(String key){reload();return Boolean.parseBoolean(settings.getProperty(key,"true"));}
    public static String text(String en,String ru){reload();return settings.getProperty("language","en").equals("ru")?ru:en;}
    public static Object minecraft()throws Exception{return VMReflect.call(Class.forName("net.minecraft.client.Minecraft"),"func_71410_x");}
    public static void bindings(Object value) {
        handler=value;
        try {
            Object mc=minecraft(),attack=VMReflect.get(VMReflect.get(mc,"field_71474_y"),"field_74312_F");
            Object key=VMReflect.get(value,"KeyUseWeapon");
            VMReflect.set(key,"key",VMReflect.call(attack,"func_151463_i"));
        }catch(Exception e){VMReflect.error("current fire binding",e);}
    }
    public static String key(Object value,String field)throws Exception {
        int code=((Number)VMReflect.get(VMReflect.get(value,field),"key")).intValue();
        if(code==0)return text("Unbound","Не назначено");
        if(code<0)return text("Mouse ","Мышь ")+(code+101);
        String name=Keyboard.getKeyName(code);return name==null?Integer.toString(code):name;
    }
    public static boolean nearby(double x,double y,double z)throws Exception {
        Object mc=minecraft(),p=VMReflect.get(mc,"field_71439_g");if(p==null)return false;
        Object center=VMReflect.call(Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",p);
        if(center==null)center=VMReflect.call(mc,"func_175606_aa");if(center==null)center=p;
        double dx=x-VMReflect.num(VMReflect.get(center,"field_70165_t")),dy=y-VMReflect.num(VMReflect.get(center,"field_70163_u")),dz=z-VMReflect.num(VMReflect.get(center,"field_70161_v"));
        reload();return dx*dx+dy*dy+dz*dz<=effectRange*effectRange;
    }
    public static boolean hit(Object packet) {
        try {
            int code=((Number)VMReflect.get(packet,"entityID_Ac")).intValue();
            if(code>-2||code<-(2+3*1048576-1))return false;
            int encoded=-code-2;lastHitCode=encoded/1048576;lastDamage=encoded%1048576;hitTime=System.nanoTime();hitsReceived++;return true;
        }catch(Exception e){VMReflect.error("confirmed hit",e);return false;}
    }
    public static String hitLabel() {
        String damage=lastDamage%10==0?Integer.toString(lastDamage/10):String.format(java.util.Locale.ROOT,"%.1f",lastDamage/10.0);
        return lastHitCode==2?text("DESTROYED","УНИЧТОЖЕНО"):lastHitCode==1?lastDamage==0?text("DAMAGE <0.1","УРОН <0.1"):text("DAMAGE -","УРОН −")+damage:text("HIT · no damage","ПОПАДАНИЕ · без урона");
    }
    public static String[] hints(Object aircraft,Object p)throws Exception {
        if(handler==null)return new String[0];
        if(VMFlight.uav(aircraft)) {
            String type=String.valueOf(VMReflect.call(aircraft,"getTypeName"));
            if(VMFlight.wing(aircraft))return new String[]{(type.equals("rv_geran")?"RV Geran":"RV FP-1")+text(" · contact fuse after takeoff"," · контактный подрыв после взлёта"),key(handler,"KeyUp")+"/"+key(handler,"KeyDown")+text(" throttle · Mouse/stick pitch/roll"," газ · мышь/стик наклон"),text("Fixed wing · native flight · ","Самолёт · обычное управление · ")+Math.round(VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"))*100)+text("% throttle · F8 controls","% газ · F8 управление")};
            String state=type.endsWith("rc-goblin-bomb")?text("Impact FPV · detonates on contact after takeoff","Боевой FPV · подрыв при контакте после взлёта"):text("Recon FPV · no weapons","Разведчик FPV · без оружия");
            if(VMEasy.client(aircraft))return new String[]{state,VMEasy.keyName("field_74351_w")+"/"+VMEasy.keyName("field_74368_y")+text(" forward/back · "," вперёд/назад · ")+VMEasy.keyName("field_74370_x")+"/"+VMEasy.keyName("field_74366_z")+text(" strafe · Mouse look"," вбок · мышь обзор"),"EASY · "+VMEasy.keyName("field_74314_A")+text(" up/start · "," вверх/взлёт · ")+VMEasy.keyName("field_151444_V")+text(" down · "," вниз · ")+VMEasy.keyName("field_74311_E")+text(" exit · F8 advanced"," выход · F8 профи")};
            String controls=key(handler,"KeyUp")+"/"+key(handler,"KeyDown")+text(" throttle · "," газ · ")+key(handler,"KeyLeft")+"/"+key(handler,"KeyRight")+text(" yaw · Mouse/stick pitch/roll"," рыскание · мышь/стик наклон");
            String mode="FPV · "+(VMController.INSTANCE.acro()?"ACRO":"ANGLE")+" · "+Math.round(VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"))*100)+text("% throttle · F8 controls","% газ · F8 управление");
            return new String[]{state,controls,mode};
        }
        Object weapon=VMReflect.call(aircraft,"getCurrentWeapon",p);
        String state;
        if(weapon==null)state=text("No weapon in this seat","На этом месте нет оружия");
        else {
            int ammo=((Number)VMReflect.call(weapon,"getAmmo")).intValue(),reserve=((Number)VMReflect.call(weapon,"getRestAllAmmoNum")).intValue();
            int reload=((Number)VMReflect.call(weapon,"getReloadCooldown")).intValue(),cooldown=Math.abs(((Number)VMReflect.call(weapon,"getCooldown")).intValue());
            boolean pilotReload=(Boolean)VMReflect.call(aircraft,"isPilotReloading");
            state=String.valueOf(VMReflect.call(weapon,"getDisplayName"))+" · "+ammo+" / "+reserve+" · ";
            state+=pilotReload||reload>0?text("RELOADING ","ПЕРЕЗАРЯДКА ")+String.format(java.util.Locale.ROOT,"%.1fs",Math.max(reload,cooldown)/20.0):ammo<=0?text("EMPTY · reload/supply","ПУСТО · перезаряди/пополни"):cooldown>0?text("WAIT ","ОЖИДАНИЕ ")+String.format(java.util.Locale.ROOT,"%.1fs",cooldown/20.0):text("READY","ГОТОВО");
        }
        String controls=key(handler,"KeyUseWeapon")+text(" fire · "," огонь · ")+key(handler,"KeyReloadWeapon")+text(" reload · "," зарядить · ")+key(handler,"KeySwitchWeapon1")+"/"+key(handler,"KeySwitchWeapon2")+text(" weapon"," оружие");
        String third=text("Mouse/stick aim · ","Мышь/стик прицел · ")+key(handler,"KeySwWeaponMode")+text(" mode · F8 controller"," режим · F8 контроллер");
        return new String[]{state,controls,third};
    }
    public static boolean fpvHud(Object gui,Object aircraft,Object p) {
        if(!VMFlight.uav(aircraft))return false;
        try {
            Object hud=VMReflect.call(Class.forName("com.norwood.mcheli.hud.MCH_HudManager"),"get","rv_fpv");if(hud==null)return false;
            VMReflect.call(hud,"draw",aircraft,p,VMReflect.get(gui,"smoothCamPartialTicks"),VMReflect.call(gui,"isExperimentalAutoScaleAircraftGui"));return true;
        }catch(Exception|LinkageError e){VMReflect.error("FPV telemetry HUD",e);return false;}
    }
    public static void hud(Object gui) {
        String name=gui.getClass().getName();if(!name.endsWith("MCH_GuiTank")&&!name.endsWith("MCH_GuiHeli")&&!name.endsWith("MCP_GuiPlane"))return;
        try {
            Object mc=minecraft(),p=VMReflect.get(mc,"field_71439_g");if(p==null||VMReflect.get(mc,"field_71462_r")!=null)return;
            if((Boolean)VMReflect.get(VMReflect.get(mc,"field_71474_y"),"field_74319_N")||!(Boolean)VMReflect.call(gui,"isDrawGui",p))return;
            Object aircraft=VMReflect.call(Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",p);if(aircraft==null)return;
            int width=((Number)VMReflect.get(gui,"field_146294_l")).intValue(),height=((Number)VMReflect.get(gui,"field_146295_m")).intValue();
            if(flag("hudHints")) {
                long now=System.nanoTime();if(now-lastHudSample>100000000L){lastHudSample=now;lines=hints(aircraft,p);}
                Object font=VMReflect.get(mc,"field_71466_p");int y=8;
                VMReflect.call(Class.forName("net.minecraft.client.gui.Gui"),"func_73734_a",4,4,Math.min(width-4,340),43,0x880B1521);
                for(String line:lines){String fitted=(String)VMReflect.call(font,"func_78269_a",line,Math.max(100,width-16));VMReflect.call(gui,"drawString",fitted,8,y,0xFFE9EDF2);y+=11;}
            }
            if(flag("hitFeedback")&&System.nanoTime()-hitTime<1400000000L&&lastHitCode>=0)VMReflect.call(gui,"drawCenteredString",hitLabel(),width/2,height/2+32,lastHitCode==0?0xFFFFD479:0xFF91F2B2);
            Object settings=VMReflect.get(mc,"field_71474_y");
            if((Boolean)VMReflect.get(settings,"field_74330_P")) {
                Runtime runtime=Runtime.getRuntime();long used=(runtime.totalMemory()-runtime.freeMemory())/1048576;
                VMReflect.call(gui,"drawString","RV "+profile+" · "+used+" MiB · FX "+particlesDrawn+" / skipped "+particlesSkipped+" · hits "+hitsReceived,8,46,0xFFD9E2EF);
            }
        }catch(Exception|LinkageError e){VMReflect.error("vehicle HUD",e);}
    }
}
