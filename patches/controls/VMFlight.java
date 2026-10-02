package com.norwood.mcheli.vm;

import java.util.*;

public final class VMFlight {
    private static final Map<Object, double[]> targets = Collections.synchronizedMap(new WeakHashMap<Object, double[]>());
    public static boolean drone(Object aircraft) {
        try { String name = String.valueOf(VMReflect.call(aircraft, "getTypeName")); return name.endsWith("rc-goblin") || name.endsWith("rc-goblin-bomb"); }
        catch (Exception e) { return false; }
    }
    public static void receive(Object aircraft, Object data, Object player) {
        try {
            if (player==null || !drone(aircraft) || !(Boolean)VMReflect.call(aircraft, "isPilot", player)) return;
            float value = (Float)VMReflect.get(data, "vmThrottle");
            if (value == -1) { targets.remove(aircraft); return; }
            if (!Float.isFinite(value) || value < 0 || value > 1) return;
            targets.put(aircraft, new double[]{value, System.nanoTime()/1e9});
            VMReflect.set(aircraft, "throttleUp", false); VMReflect.set(aircraft, "throttleDown", false);
        } catch (Exception e) { VMReflect.error("analog throttle receive", e); }
    }
    public static void local(Object aircraft, double value) {
        targets.put(aircraft, new double[]{VMControlMath.clamp(value,0,1),System.nanoTime()/1e9});
    }
    public static void reset(Object aircraft) { targets.remove(aircraft);VMImpact.reset(aircraft); }
    public static boolean release(Object aircraft) { return targets.remove(aircraft)!=null; }
    public static double throttle(Object aircraft, double original) {
        double[] target=targets.get(aircraft);
        if(target==null) return original;
        double desired = System.nanoTime()/1e9-target[1] > .4 ? 0 : target[0];
        return VMControlMath.smooth(original, desired, .05, .12);
    }
    public static boolean afterControl(boolean original,Object aircraft) {
        if(!original || !targets.containsKey(aircraft))return original;
        try {
            double current=VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"));
            double value=throttle(aircraft,current);
            if((Boolean)VMReflect.call(aircraft,"isDestroyed") || !(Boolean)VMReflect.call(aircraft,"canUseFuel",true) || VMReflect.call(aircraft,"getRiddenByEntity")==null)value=0;
            VMReflect.call(aircraft,"setCurrentThrottle",value);
            if(!VMReflect.remote(aircraft))VMReflect.call(aircraft,"setThrottle",value);
        }catch(Exception e){VMReflect.error("analog throttle",e);}
        return original;
    }
    public static void write(Object data, Object buffer) {
        try { VMReflect.call(buffer, "writeFloat", (Float)VMReflect.get(data,"vmThrottle")); }
        catch(Exception e){ throw new IllegalStateException("VM control serialization", e); }
    }
    public static void read(Object data, Object buffer) {
        try { VMReflect.set(data,"vmThrottle",VMReflect.call(buffer,"readFloat")); }
        catch(Exception e){ throw new IllegalStateException("VM control version mismatch: update client and server",e); }
    }
}
