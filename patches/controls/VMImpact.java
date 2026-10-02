package com.norwood.mcheli.vm;

import java.util.*;

public final class VMImpact {
    private static final Set<Object> armed=Collections.synchronizedSet(Collections.newSetFromMap(new WeakHashMap<Object,Boolean>()));
    private static final Set<Object> detonated=Collections.synchronizedSet(Collections.newSetFromMap(new WeakHashMap<Object,Boolean>()));
    private static Object vector(double x,double y,double z)throws Exception{return Class.forName("net.minecraft.util.math.Vec3d").getConstructor(double.class,double.class,double.class).newInstance(x,y,z);}
    private static double coordinate(Object vec,String field)throws Exception{return VMReflect.num(VMReflect.get(vec,field));}
    private static double distance(Object start,Object hit)throws Exception{Object vec=VMReflect.get(hit,"field_72307_f");double x=coordinate(start,"field_72450_a")-coordinate(vec,"field_72450_a"),y=coordinate(start,"field_72448_b")-coordinate(vec,"field_72448_b"),z=coordinate(start,"field_72449_c")-coordinate(vec,"field_72449_c");return Math.sqrt(x*x+y*y+z*z);}
    public static void reset(Object aircraft){armed.remove(aircraft);}
    public static boolean droneMotion(Object aircraft){
        try {
            if(!(String.valueOf(VMReflect.call(aircraft,"getTypeName")).endsWith("rc-goblin-bomb")||VMFlight.wing(aircraft))||VMReflect.remote(aircraft))return false;
            if(detonated.contains(aircraft)||(Boolean)VMReflect.get(aircraft,"field_70128_L"))return true;
            Object pilot=VMReflect.call(aircraft,"getRiddenByEntity");
            double vx=VMReflect.num(VMReflect.get(aircraft,"field_70159_w")),vy=VMReflect.num(VMReflect.get(aircraft,"field_70181_x")),vz=VMReflect.num(VMReflect.get(aircraft,"field_70179_y"));
            double speed=Math.sqrt(vx*vx+vy*vy+vz*vz);
            if(pilot!=null&&!(Boolean)VMReflect.get(aircraft,"field_70122_E")&&VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"))>.15&&speed>.08)armed.add(aircraft);
            if(!armed.contains(aircraft)||speed<.02||!Double.isFinite(speed))return false;
            Object world=VMReflect.get(aircraft,"field_70170_p");
            double x=VMReflect.num(VMReflect.get(aircraft,"field_70165_t")),y=VMReflect.num(VMReflect.get(aircraft,"field_70163_u"))+.35,z=VMReflect.num(VMReflect.get(aircraft,"field_70161_v"));
            java.util.List<Object> starts=new ArrayList<Object>();starts.add(vector(x,y,z));
            if(VMFlight.drone(aircraft)){
                Object bounds=VMReflect.call(aircraft,"func_174813_aQ");double minX=VMReflect.num(VMReflect.get(bounds,"field_72340_a")),minY=VMReflect.num(VMReflect.get(bounds,"field_72338_b")),minZ=VMReflect.num(VMReflect.get(bounds,"field_72339_c")),maxX=VMReflect.num(VMReflect.get(bounds,"field_72336_d")),maxY=VMReflect.num(VMReflect.get(bounds,"field_72337_e")),maxZ=VMReflect.num(VMReflect.get(bounds,"field_72334_f"));
                starts.add(vector(x,minY+.005,z));starts.add(vector(x,maxY-.005,z));starts.add(vector(minX+.005,y,z));starts.add(vector(maxX-.005,y,z));starts.add(vector(x,y,minZ+.005));starts.add(vector(x,y,maxZ-.005));
            }
            Object box=VMReflect.call(VMReflect.call(VMReflect.call(aircraft,"func_174813_aQ"),"func_72321_a",vx,vy,vz),"func_72314_b",1D,1D,1D);
            if(VMFlight.wing(aircraft)){
                VMReflect.call(aircraft,"updateExtraBoundingBox");
                for(Object part:(Object[])VMReflect.get(aircraft,"extraBoundingBox")){
                    Object center=VMReflect.get(part,"center");double cx=coordinate(center,"field_72450_a"),cy=coordinate(center,"field_72448_b"),cz=coordinate(center,"field_72449_c");starts.add(vector(cx,cy,cz));
                    for(String axis:new String[]{"X","Z"}){
                        Object direction=VMReflect.get(part,"axis"+axis);double radius=VMReflect.num(VMReflect.get(part,axis.equals("X")?"halfWidth":"halfDepth"))*.98;
                        for(int sign:new int[]{-1,1})starts.add(vector(cx+coordinate(direction,"field_72450_a")*radius*sign,cy+coordinate(direction,"field_72448_b")*radius*sign,cz+coordinate(direction,"field_72449_c")*radius*sign));
                    }
                    box=VMReflect.call(box,"func_111270_a",VMReflect.call(VMReflect.call(part,"getBoundingBox"),"func_72321_a",vx,vy,vz));
                }
            }
            Object closest=null;double best=Double.POSITIVE_INFINITY;
            java.util.List<?> targets=(List<?>)VMReflect.call(world,"func_72839_b",aircraft,box);
            for(Object start:starts){
                Object end=vector(coordinate(start,"field_72450_a")+vx,coordinate(start,"field_72448_b")+vy,coordinate(start,"field_72449_c")+vz);
                Object block=VMReflect.call(Class.forName("com.norwood.mcheli.wrapper.W_WorldFunc"),"clip",world,start,end);
                if(block!=null&&distance(start,block)<best){best=distance(start,block);closest=block;}
            for(Object target:targets){
                if(target==pilot||(Boolean)VMReflect.get(target,"field_70128_L")||!(Boolean)VMReflect.call(target,"func_70067_L"))continue;
                String type=target.getClass().getName();
                if(type.contains("MCH_EntitySeat")||type.contains("MCH_EntityHitBox")||type.contains("MCH_EntityUavStation")||type.contains("MCH_EntityChain"))continue;
                if((Boolean)VMReflect.call(aircraft,"isMountedEntity",target))continue;
                Object bounds=VMReflect.call(VMReflect.call(target,"func_174813_aQ"),"func_72314_b",.5D,.5D,.5D);
                Object hit=VMReflect.call(bounds,"func_72327_a",start,end);
                if(hit!=null&&distance(start,hit)<best){best=distance(start,hit);closest=Class.forName("net.minecraft.util.math.RayTraceResult").getConstructor(Class.forName("net.minecraft.entity.Entity"),Class.forName("net.minecraft.util.math.Vec3d")).newInstance(target,VMReflect.get(hit,"field_72307_f"));}
            }
            }
            if(closest==null)return false;
            Object hit=VMReflect.get(closest,"field_72307_f");
            Object weapon=VMReflect.call(Class.forName("com.norwood.mcheli.weapon.MCH_WeaponCreator"),"createWeapon",world,"plastic_bomb",hit,0F,0F,null,false);
            Object bomb=Class.forName("com.norwood.mcheli.weapon.MCH_EntityBomb").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
            VMReflect.call(bomb,"setName","plastic_bomb");VMReflect.call(bomb,"setParameterFromWeapon",weapon,aircraft,pilot);
            Object info=VMReflect.call(weapon,"getInfo");VMReflect.call(bomb,"setPower",Math.max(((Number)VMReflect.get(info,"power")).intValue(),(int)(8*VMReflect.num(VMReflect.get(info,"explosion"))+1)));
            VMReflect.call(bomb,"func_70107_b",coordinate(hit,"field_72450_a"),coordinate(hit,"field_72448_b"),coordinate(hit,"field_72449_c"));
            if(!detonated.add(aircraft))return true;
            armed.remove(aircraft);
            try{VMReflect.call(aircraft,"unmountEntity");VMReflect.call(aircraft,"func_70106_y");VMReflect.call(bomb,"onImpact",closest,1F);}
            finally{VMReflect.call(aircraft,"func_70106_y");VMReflect.call(bomb,"func_70106_y");}
            return true;
        }catch(Exception|LinkageError e){VMReflect.error("FPV impact fuse",e);return detonated.contains(aircraft);}
    }
}
