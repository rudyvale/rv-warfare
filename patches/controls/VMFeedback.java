package com.norwood.mcheli.vm;

import java.util.*;
import java.lang.ref.WeakReference;

public final class VMFeedback {
    private static final Map<Object,long[]> sent=Collections.synchronizedMap(new WeakHashMap<Object,long[]>());
    public static volatile long notifications;
    private static final ThreadLocal<ArrayDeque<Object[]>> snapshots=new ThreadLocal<ArrayDeque<Object[]>>() {protected ArrayDeque<Object[]> initialValue(){return new ArrayDeque<Object[]>();}};
    public static void begin(Object target,Object source) {
        try {
            if(VMReflect.remote(target))return;
            ArrayDeque<Object[]> stack=snapshots.get();if(stack.size()>=64)stack.removeLast();
            stack.addFirst(new Object[]{new WeakReference<Object>(target),new WeakReference<Object>(source),health(target)});
        }catch(Exception|LinkageError e){VMReflect.error("hit snapshot",e);}
    }
    private static double take(Object target,Object source) {
        Iterator<Object[]> i=snapshots.get().iterator();
        while(i.hasNext()){Object[] record=i.next();Object t=((WeakReference<?>)record[0]).get(),s=((WeakReference<?>)record[1]).get();if(t==null||s==null){i.remove();continue;}if(t==target&&s==source){i.remove();return (Double)record[2];}}
        return -1;
    }
    private static Object medical(Object entity)throws Exception {
        if(!Class.forName("net.minecraft.entity.player.EntityPlayer").isInstance(entity))return null;
        try{Object capability=VMReflect.get(Class.forName("ichttt.mods.firstaid.api.CapabilityExtendedHealthSystem"),"INSTANCE");return capability==null?null:VMReflect.call(entity,"getCapability",capability,null);}catch(ClassNotFoundException e){return null;}
    }
    public static boolean dead(Object entity)throws Exception {
        if((Boolean)VMReflect.get(entity,"field_70128_L"))return true;Object model=medical(entity);return model!=null&&(Boolean)VMReflect.call(model,"isDead",entity);
    }
    public static double health(Object entity) {
        try {
            if(entity.getClass().getName().startsWith("com.norwood.mcheli")&&Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft").isInstance(entity))return ((Number)VMReflect.call(entity,"getHP")).intValue();
            Object model=medical(entity);if(model!=null)return VMReflect.num(VMReflect.call(model,"getCurrentHealth"));
            if(Class.forName("net.minecraft.entity.EntityLivingBase").isInstance(entity))return VMReflect.num(VMReflect.call(entity,"func_110143_aJ"));
        }catch(Exception|LinkageError e){VMReflect.error("damage snapshot",e);}return -1;
    }
    public static void notify(Object shooter,double before,double after,boolean dead) {
        try {
            if(before<0||shooter==null||!Class.forName("net.minecraft.entity.player.EntityPlayerMP").isInstance(shooter))return;
            double damage=Math.max(0,before-after);int result=dead&&before>0?2:damage>0?1:0;
            long now=System.nanoTime();long[] prior=sent.get(shooter);
            if(prior!=null&&now-prior[0]<80000000L&&result<=prior[1])return;
            sent.put(shooter,new long[]{now,result});
            Object packet=Class.forName("com.norwood.mcheli.networking.packet.PacketNotifyHit").newInstance();
            VMReflect.set(packet,"entityID_Ac",-(2+result*1048576+(int)Math.min(1048575,Math.round(damage*10))));
            VMReflect.call(packet,"sendToPlayer",shooter);notifications++;
        }catch(Exception|LinkageError e){VMReflect.error("server hit feedback",e);}
    }
    public static boolean aircraft(boolean result,Object target,Object source,float amount) {
        try {
            if(VMReflect.remote(target))return result;double before=take(target,source);if(amount<=0)return result;
            double after=health(target);Object attacker=VMReflect.call(source,"func_76346_g");
            notify(attacker,before,after,after<=0||(Boolean)VMReflect.get(target,"field_70128_L"));
            VMCombat.damageFeedback(target,source,amount);
        }catch(Exception|LinkageError e){VMReflect.error("confirmed vehicle damage",e);}return result;
    }
    public static void entity(Object bullet,Object target) {
        try {
            if(VMReflect.remote(bullet))return;double before=take(target,bullet);if(target.getClass().getName().startsWith("com.norwood.mcheli"))return;
            double after=health(target);notify(VMReflect.get(bullet,"shootingEntity"),before,after,dead(target)||after==0);
        }catch(Exception|LinkageError e){VMReflect.error("confirmed entity damage",e);}
    }
}
