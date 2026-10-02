package com.norwood.mcheli.vm;

import java.util.*;
import com.google.gson.JsonObject;

public final class VMCombat {
    private static final Map<Object,double[]> kicks=Collections.synchronizedMap(new WeakHashMap<Object,double[]>());
    private static final Set<Object> tuned=Collections.newSetFromMap(new WeakHashMap<Object,Boolean>());
    private static long budgetTick;
    private static int particleBudget;
    private static Object category() throws Exception { return VMReflect.get(Class.forName("net.minecraft.util.SoundCategory"),"MASTER"); }
    private static Object location(String value) throws Exception {return Class.forName("net.minecraft.util.ResourceLocation").getConstructor(String.class).newInstance(value);}
    private static Object sound(Object name) throws Exception { return VMReflect.call(Class.forName("com.norwood.mcheli.sound.MCH_SoundEvents"),"getSound",name); }
    private static Object player() throws Exception { return VMReflect.get(VMReflect.call(Class.forName("net.minecraft.client.Minecraft"),"func_71410_x"),"field_71439_g"); }
    private static Object ridden(Object player) throws Exception {return VMReflect.call(Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",player);}
    public static void registerSounds() {
        try {
            Object registry=VMReflect.get(Class.forName("com.norwood.mcheli.sound.SoundRegistry"),"INSTANCE");
            Set<Object> names=(Set<Object>)VMReflect.get(registry,"soundSet");
            for(String name:new String[]{"aps_shoot","wrench1","wrench2","wrench3","mchce_patched"})names.add(location("mcheli:"+name));
        }catch(Exception e){throw new IllegalStateException("RV sound registry",e);}
    }
    public static void repairSoundMarkers(Object records){
        try{for(Object record:(List<?>)records){JsonObject object=(JsonObject)VMReflect.get(record,"object");if(object.has("mchce_patched")&&object.get("mchce_patched").toString().contains("patched_marker"))object.remove("mchce_patched");}}
        catch(Exception e){throw new IllegalStateException("RV sound metadata",e);}
    }
    public static boolean soundAt(Object world,double x,double y,double z,Object name,float volume,float pitch) {
        try {
            if(name==null)return false;
            Object event=sound(name);
            if((Boolean)VMReflect.get(world,"field_72995_K")) VMReflect.call(world,"func_184134_a",x,y,z,event,category(),volume,pitch,false);
            else VMReflect.call(world,"func_184148_a",null,x,y,z,event,category(),volume,pitch);
            return true;
        }catch(Exception e){VMReflect.error("positional sound",e);return false;}
    }
    public static boolean weaponSound(Object weapon,Object entity,Object name) {
        try {
            if(VMReflect.remote(entity) || !(Boolean)VMReflect.get(weapon,"canPlaySound"))return true;
            Object info=VMReflect.call(weapon,"getInfo"); if(info==null||name==null)return false;
            Object exclude=null;
            if(entity.getClass().getName().startsWith("com.norwood.mcheli")) {
                Object pilot=VMReflect.call(entity,"getRiddenByEntity");
                if(pilot!=null && Class.forName("net.minecraft.entity.player.EntityPlayer").isInstance(pilot)) exclude=pilot;
            }
            float volume=(float)VMControlMath.clamp(VMReflect.num(VMReflect.get(info,"soundVolume")),1,6);
            float pitch=(float)VMControlMath.clamp(VMReflect.num(VMReflect.get(info,"soundPitch")),.5,1.6);
            Object world=VMReflect.get(entity,"field_70170_p");
            VMReflect.call(world,"func_184148_a",exclude,VMReflect.num(VMReflect.get(entity,"field_70165_t")),VMReflect.num(VMReflect.get(entity,"field_70163_u")),VMReflect.num(VMReflect.get(entity,"field_70161_v")),sound(name),category(),volume,pitch);
            return true;
        }catch(Exception e){VMReflect.error("weapon sound",e);return false;}
    }
    public static void tune(Object info) {
        synchronized(tuned){if(!tuned.add(info))return;}
        try {
            String type=String.valueOf(VMReflect.get(info,"type"));
            if(type.equals("dummy")||type.equals("smoke"))return;
            Object smoke=VMReflect.get(info,"listMuzzleFlashSmoke");
            if(smoke instanceof Iterable)for(Object s:(Iterable<?>)smoke){
                VMReflect.set(s,"size",(float)Math.min(2.2,VMReflect.num(VMReflect.get(s,"size"))));
                VMReflect.set(s,"age",Math.min(9,((Number)VMReflect.get(s,"age")).intValue()));
                VMReflect.set(s,"num",Math.min(3,((Number)VMReflect.get(s,"num")).intValue()));
                VMReflect.set(s,"a",(float)Math.min(.32,VMReflect.num(VMReflect.get(s,"a"))));
            }
            VMReflect.set(info,"recoil",(float)Math.min(.25,Math.max(.06,VMReflect.num(VMReflect.get(info,"recoil")))));
            VMReflect.set(info,"recoilPitch",(float)Math.min(.35,Math.max(.05,VMReflect.num(VMReflect.get(info,"recoilPitch")))));
            VMReflect.set(info,"recoilYaw",0F);VMReflect.set(info,"recoilYawRange",0F);
        }catch(Exception e){VMReflect.error("weapon tuning",e);}
    }
    public static boolean suppressRecoil(Object aircraft) {
        String name=aircraft.getClass().getName();
        return name.contains("MCH_EntityHeli")||name.contains("MCH_EntityTank");
    }
    public static void damageFeedback(Object aircraft,Object source,float amount) {
        try {
            if(amount<=0||VMReflect.remote(aircraft)||!source.getClass().getName().startsWith("techguns."))return;
            Object projectile=VMReflect.call(source,"func_76364_f"),world=VMReflect.get(aircraft,"field_70170_p");
            double x=VMReflect.num(VMReflect.get(aircraft,"field_70165_t")),y=VMReflect.num(VMReflect.get(aircraft,"field_70163_u"))+1,z=VMReflect.num(VMReflect.get(aircraft,"field_70161_v"));
            if(projectile!=null){
                y=VMReflect.num(VMReflect.get(aircraft,"field_70163_u"))+1;
            }
            particles(world,"FIREWORKS_SPARK",x,y,z,6,.15,.1);soundAt(world,x,y,z,location("mcheli:hit"),1F,.95F);
        }catch(Exception|LinkageError e){VMReflect.error("armour impact feedback",e);}
    }
    public static void muzzle(Object aircraft,Object info,double x,double y,double z) {
        try {
            if(!VMReflect.remote(aircraft))return;
            Object p=player(); if(p==null || ridden(p)!=aircraft)return;
            double now=System.nanoTime()/1e9;
            double[] prior=kicks.get(aircraft);
            if(prior!=null && now-prior[0]<.04)return;
            String type=String.valueOf(VMReflect.get(info,"type"));
            if(type.equals("dummy")||type.equals("smoke"))return;
            Object name=VMReflect.get(info,"fireSound");
            if(name!=null) VMReflect.call(Class.forName("com.norwood.mcheli.wrapper.W_McClient"),"playSound",name,.85F,(float)VMControlMath.clamp(VMReflect.num(VMReflect.get(info,"soundPitch")),.5,1.6));
            boolean cannon=VMReflect.num(VMReflect.get(info,"delay"))>=10 && VMReflect.num(VMReflect.get(info,"explosion"))>0;
            if(!VMFlight.uav(aircraft)) kicks.put(aircraft,new double[]{now,cannon?1.25:.23});
            particles(VMReflect.get(aircraft,"field_70170_p"),"FLAME",x,y,z,2,.08,.03);
        }catch(Exception e){VMReflect.error("shot feedback",e);}
    }
    public static void camera(Object event) {
        try {
            Object p=player();if(p==null)return;Object aircraft=ridden(p);double[] kick=kicks.get(aircraft);if(kick==null)return;
            double elapsed=System.nanoTime()/1e9-kick[0];if(elapsed>.5)return;
            float offset=(float)(kick[1]*Math.sin(Math.min(1,elapsed/.07)*Math.PI/2)*Math.exp(-elapsed/.14));
            VMReflect.call(event,"setPitch",((Number)VMReflect.call(event,"getPitch")).floatValue()-offset);
        }catch(Exception e){VMReflect.error("camera recoil",e);}
    }
    private static synchronized boolean budget(int count,boolean remote) {
        long tick=System.nanoTime()/50000000;
        if(tick!=budgetTick){budgetTick=tick;particleBudget=0;}
        int limit=160;if(remote){VMClient.reload();limit=VMClient.effectLimit;}
        if(particleBudget+count>limit)return false;particleBudget+=count;return true;
    }
    private static void particles(Object world,String name,double x,double y,double z,int count,double spread,double speed)throws Exception {
        boolean remote=(Boolean)VMReflect.get(world,"field_72995_K");
        if(remote&&!VMClient.nearby(x,y,z)){VMClient.particlesSkipped+=count;return;}
        if(!budget(count,remote)){if(remote)VMClient.particlesSkipped+=count;return;}
        Object type=VMReflect.get(Class.forName("net.minecraft.util.EnumParticleTypes"),name);
        if(remote) {
            for(int i=0;i<count;i++)VMReflect.call(world,"func_175688_a",type,x,y,z,0D,speed,0D,new int[0]);
            VMClient.particlesDrawn+=count;
        }else {
            for(Object observer:(List<?>)VMReflect.get(world,"field_73010_i")){
                double dx=x-VMReflect.num(VMReflect.get(observer,"field_70165_t")),dy=y-VMReflect.num(VMReflect.get(observer,"field_70163_u")),dz=z-VMReflect.num(VMReflect.get(observer,"field_70161_v"));
                Object controlled=VMReflect.call(Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",observer);
                if(controlled!=null){dx=x-VMReflect.num(VMReflect.get(controlled,"field_70165_t"));dy=y-VMReflect.num(VMReflect.get(controlled,"field_70163_u"));dz=z-VMReflect.num(VMReflect.get(controlled,"field_70161_v"));}
                if(dx*dx+dy*dy+dz*dz<=96*96){
                    Object packet=Class.forName("net.minecraft.network.play.server.SPacketParticles").getConstructor(Class.forName("net.minecraft.util.EnumParticleTypes"),boolean.class,float.class,float.class,float.class,float.class,float.class,float.class,float.class,int.class,int[].class).newInstance(type,true,(float)x,(float)y,(float)z,(float)spread,(float)spread,(float)spread,(float)speed,count,new int[0]);
                    VMReflect.call(VMReflect.get(observer,"field_71135_a"),"func_147359_a",packet);
                }
            }
        }
    }
    public static void trail(Object bullet) {
        try {
            if(!VMReflect.remote(bullet) || (Boolean)VMReflect.get(bullet,"field_70128_L"))return;
            Object info=VMReflect.call(bullet,"getInfo");if(info==null)return;
            String type=String.valueOf(VMReflect.get(info,"type"));
            if(type.equals("smoke")||type.equals("dummy")||type.equals("bomb"))return;
            Object world=VMReflect.get(bullet,"field_70170_p");
            double x=VMReflect.num(VMReflect.get(bullet,"field_70165_t")),y=VMReflect.num(VMReflect.get(bullet,"field_70163_u")),z=VMReflect.num(VMReflect.get(bullet,"field_70161_v"));
            double px=VMReflect.num(VMReflect.get(bullet,"field_70169_q")),py=VMReflect.num(VMReflect.get(bullet,"field_70167_r")),pz=VMReflect.num(VMReflect.get(bullet,"field_70166_s"));
            double distance=Math.sqrt((x-px)*(x-px)+(y-py)*(y-py)+(z-pz)*(z-pz));
            if(distance>24 || distance<.02)return;
            VMClient.reload();int steps=Math.min(VMClient.trailSteps,Math.max(2,(int)(distance*2)));
            for(int i=0;i<steps;i++){double f=(i+.5)/steps;particles(world,i%3==0?"FLAME":"FIREWORKS_SPARK",px+(x-px)*f,py+(y-py)*f,pz+(z-pz)*f,1,0,0);}
        }catch(Exception e){VMReflect.error("projectile trail",e);}
    }
    public static void impact(Object bullet,Object hit) {
        try {
            if(VMReflect.remote(bullet))return;
            Object vec=VMReflect.get(hit,"field_72307_f");if(vec==null)return;
            double x=VMReflect.num(VMReflect.get(vec,"field_72450_a")),y=VMReflect.num(VMReflect.get(vec,"field_72448_b")),z=VMReflect.num(VMReflect.get(vec,"field_72449_c"));
            Object world=VMReflect.get(bullet,"field_70170_p");Object info=VMReflect.call(bullet,"getInfo");
            boolean explosion=info!=null && VMReflect.num(VMReflect.get(info,"explosion"))>0;
            particles(world,"FIREWORKS_SPARK",x,y,z,8,.22,.15);
            particles(world,explosion?"EXPLOSION_LARGE":"CRIT",x,y+.15,z,explosion?2:5,.15,.1);
            if(!explosion)soundAt(world,x,y,z,location("mcheli:hit"),1.2F,.9F);
        }catch(Exception e){VMReflect.error("impact feedback",e);}
    }
}
