package com.norwood.mcheli.vm;

public final class VMComfort {
    public static boolean clearView(){
        try{Object player=VMReflect.get(VMClient.minecraft(),"field_71439_g");return player!=null&&VMReflect.call(Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",player)!=null;}
        catch(Exception|LinkageError e){return false;}
    }
}
