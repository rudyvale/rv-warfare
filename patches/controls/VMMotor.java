package com.norwood.mcheli.vm;

public final class VMMotor {
    private static final java.util.Set<Object> tuned=java.util.Collections.newSetFromMap(new java.util.WeakHashMap<Object,Boolean>());
    public static float volume(float original,Object aircraft) {
        if(!VMFlight.drone(aircraft))return original;
        try {Object info=VMReflect.call(aircraft,"getAcInfo");if(info!=null&&tuned.add(info)){VMReflect.set(info,"soundRange",24F);}double gas=VMControlMath.clamp(VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle")),0,1);return (float)(gas<.005?0:.16+.60*Math.sqrt(gas));}
        catch(Exception e){VMReflect.error("FPV motor volume",e);return original;}
    }
    public static float pitch(float original,Object aircraft) {
        if(!VMFlight.drone(aircraft))return original;
        try {double gas=VMControlMath.clamp(VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle")),0,1);return (float)(.72+.68*gas);}
        catch(Exception e){VMReflect.error("FPV motor pitch",e);return original;}
    }
}
