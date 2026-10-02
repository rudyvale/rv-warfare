import com.norwood.mcheli.vm.*;

public final class VMControlsRuntime {
    private static int checks;
    private static void check(boolean value,String label){if(!value)throw new IllegalStateException(label);checks++;System.out.println("[VM integration] PASS "+label);}
    private static Object vector(double x,double y,double z)throws Exception{return Class.forName("net.minecraft.util.math.Vec3d").getConstructor(double.class,double.class,double.class).newInstance(x,y,z);}
    private static void chunks(Object world,double x,double z)throws Exception{for(int a=-1;a<=1;a++)for(int b=-1;b<=1;b++)VMReflect.call(world,"func_72964_e",((int)Math.floor(x)>>4)+a,((int)Math.floor(z)>>4)+b);}
    private static Object tank(Object world,double x,double z)throws Exception{
        Object tank=Class.forName("com.norwood.mcheli.tank.MCH_EntityTank").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
        VMReflect.call(tank,"setTypeName","m1a2");VMReflect.call(tank,"setTextureName","m1a2");VMReflect.call(tank,"func_70107_b",x,80D,z);chunks(world,x,z);VMReflect.call(world,"func_72838_d",tank);return tank;
    }
    private static Object connect(Object world,Object player,String type,double x,double z)throws Exception{
        Object uav=Class.forName("com.norwood.mcheli.helicopter.MCH_EntityHeli").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
        VMReflect.call(uav,"setTypeName",type);VMReflect.call(uav,"setTextureName",type);VMReflect.call(uav,"func_70107_b",x,80D,z);VMReflect.call(uav,"setFuel",VMReflect.call(uav,"getMaxFuel"));VMReflect.call(world,"func_72964_e",(int)x>>4,(int)z>>4);VMReflect.call(world,"func_72838_d",uav);
        Object station=VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_EntityUavStation"),"createHandheld",world,player,VMReflect.get(Class.forName("net.minecraft.util.EnumHand"),"MAIN_HAND"),java.util.Collections.singletonList(VMReflect.call(uav,"func_110124_au")),false);
        VMReflect.call(world,"func_72838_d",station);VMReflect.call(station,"pairUav",VMReflect.call(uav,"func_110124_au"));VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_UavControl"),"connect",player,station,uav);return uav;
    }
    private static void combat(Object server)throws Exception{
        Object player=VMReflect.call(VMReflect.call(server,"func_184103_al"),"func_152612_a","VMControlsTest"),world=VMReflect.get(player,"field_70170_p");
        Object target=tank(world,96,12),drone=connect(world,player,"rc-goblin-bomb",96,0);
        check(VMReflect.call(drone,"getRiddenByEntity")==player,"real player controls armed FPV fixture");
        VMReflect.set(drone,"field_70122_E",true);VMReflect.call(drone,"setCurrentThrottle",0D);
        check(!VMImpact.droneMotion(drone)&&!(Boolean)VMReflect.get(drone,"field_70128_L"),"fresh grounded FPV cannot detonate");
        VMReflect.set(drone,"field_70122_E",false);VMReflect.call(drone,"setCurrentThrottle",.6D);VMReflect.set(drone,"field_70179_y",20D);
        int before=((Number)VMReflect.call(target,"getHP")).intValue();VMReflect.call(drone,"warfareCheckMotion");
        check((Boolean)VMReflect.get(drone,"field_70128_L"),"fast armed FPV stops and detonates on tank");
        int after=((Number)VMReflect.call(target,"getHP")).intValue();check(after<before-5,"contact bomb damages tank: "+before+" -> "+after);
        VMReflect.call(drone,"warfareCheckMotion");check(((Number)VMReflect.call(target,"getHP")).intValue()==after,"contact fuse detonates only once");
        Object recon=connect(world,player,"rc-goblin",96,0);VMReflect.call(recon,"setCurrentThrottle",.6D);VMReflect.set(recon,"field_70179_y",20D);
        check(!VMImpact.droneMotion(recon)&&!(Boolean)VMReflect.get(recon,"field_70128_L"),"recon FPV has no explosive contact fuse");VMReflect.call(recon,"func_70106_y");VMReflect.call(target,"func_70106_y");
        techguns(world,player,8F,128);
        techguns(world,player,80F,160);
        try{Class<?> qa=Class.forName("RVCombatAcceptance");VMReflect.call(qa,"verify",server);}catch(ClassNotFoundException ignored){}
    }
    private static void techguns(Object world,Object player,float damage,double x)throws Exception{
        Object target=tank(world,x,12),bullet=Class.forName("techguns.entities.projectiles.GenericProjectile").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
        VMReflect.set(bullet,"shooter",player);VMReflect.set(bullet,"damage",damage);VMReflect.set(bullet,"damageMin",damage);VMReflect.set(bullet,"damageDropStart",100F);VMReflect.set(bullet,"damageDropEnd",200F);VMReflect.set(bullet,"ticksToLive",20);VMReflect.set(bullet,"speed",20F);
        VMReflect.call(bullet,"func_70107_b",x,81D,0D);VMReflect.set(bullet,"field_70179_y",20D);VMReflect.call(world,"func_72838_d",bullet);
        int hp=((Number)VMReflect.call(target,"getHP")).intValue();VMReflect.call(bullet,"func_70071_h_");int after=((Number)VMReflect.call(target,"getHP")).intValue();
        check((Boolean)VMReflect.get(bullet,"field_70128_L"),"real fast Techguns projectile stops at tank, damage="+damage);
        check(damage<12?after==hp:after<hp,"Techguns armour/penetration HP: "+hp+" -> "+after+", damage="+damage);VMReflect.call(target,"func_70106_y");
    }
    private static void shot(Object world,String name,double x)throws Exception{
        Object tank=Class.forName("com.norwood.mcheli.tank.MCH_EntityTank").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
        VMReflect.call(tank,"setTypeName","m1a2");VMReflect.call(tank,"func_70107_b",x,80D,12D);chunks(world,x,0);VMReflect.call(world,"func_72838_d",tank);
        Object shooter=Class.forName("com.norwood.mcheli.tank.MCH_EntityTank").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
        VMReflect.call(shooter,"setTypeName","m1a2");VMReflect.call(shooter,"func_70107_b",x,80D,0D);
        Object weapon=VMReflect.call(Class.forName("com.norwood.mcheli.weapon.MCH_WeaponCreator"),"createWeapon",world,name,vector(x,81,0),0F,0F,null,false);
        check(weapon!=null,"native weapon created "+name);
        Object parameter=Class.forName("com.norwood.mcheli.weapon.MCH_WeaponParam").newInstance();VMReflect.set(parameter,"entity",shooter);VMReflect.set(parameter,"user",shooter);VMReflect.call(parameter,"setPosAndRot",x,81D,0D,0F,0F);
        java.util.Set<Object> prior=new java.util.HashSet<Object>((java.util.List<?>)VMReflect.get(world,"field_72996_f"));
        check((Boolean)VMReflect.call(weapon,"shot",parameter),"native server shot succeeds "+name);
        Object bullet=null;for(Object entity:(java.util.List<?>)VMReflect.get(world,"field_72996_f"))if(!prior.contains(entity)&&Class.forName("com.norwood.mcheli.weapon.MCH_EntityBaseBullet").isInstance(entity)){bullet=entity;break;}
        check(bullet!=null,"native shot creates projectile "+name);
        int hp=((Number)VMReflect.call(tank,"getHP")).intValue();
        for(int i=0;i<20&&!(Boolean)VMReflect.get(bullet,"field_70128_L");i++)VMReflect.call(bullet,"func_70071_h_");
        check((Boolean)VMReflect.get(bullet,"field_70128_L"),"projectile stops at tank "+name);
        int after=((Number)VMReflect.call(tank,"getHP")).intValue();
        check(after<hp,"tank HP decreases "+name+": "+hp+" -> "+after);
        VMReflect.call(tank,"func_70106_y");VMReflect.call(shooter,"func_70106_y");
    }
    public static boolean command(Object server,Object sender,String[] args){
        if(!Boolean.getBoolean("vm.controls.integration") || server!=sender || args.length!=1)return false;
        if(args[0].equals("vmcontrolscombat")){
            try{combat(server);System.out.println("[VM combat integration] COMPLETE");}catch(Throwable e){System.out.println("[VM combat integration] FAILED");e.printStackTrace();}return true;
        }
        if(args[0].equals("vmcontrolsride")) {
            try {
                Object player=VMReflect.call(VMReflect.call(server,"func_184103_al"),"func_152612_a","VMControlsTest");
                Object world=VMReflect.get(player,"field_70170_p");
                Object uav=Class.forName("com.norwood.mcheli.helicopter.MCH_EntityHeli").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
                VMReflect.call(uav,"setTypeName","rc-goblin");VMReflect.call(uav,"setTextureName","rc-goblin");VMReflect.call(uav,"func_70107_b",VMReflect.num(VMReflect.get(player,"field_70165_t"))+2,12D,VMReflect.num(VMReflect.get(player,"field_70161_v")));VMReflect.call(uav,"setFuel",VMReflect.call(uav,"getMaxFuel"));VMReflect.call(world,"func_72838_d",uav);
                Object station=VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_EntityUavStation"),"createHandheld",world,player,VMReflect.get(Class.forName("net.minecraft.util.EnumHand"),"MAIN_HAND"),java.util.Collections.singletonList(VMReflect.call(uav,"func_110124_au")),false);
                VMReflect.call(world,"func_72838_d",station);VMReflect.call(station,"pairUav",VMReflect.call(uav,"func_110124_au"));
                Object result=VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_UavControl"),"connect",player,station,uav);
                System.out.println("[VM client fixture] "+result);
            }catch(Throwable e){e.printStackTrace();}return true;
        }
        if(!args[0].equals("vmcontrolscheck"))return false;
        try {
            Object world=VMReflect.call(server,"func_71218_a",0);
            Object info=VMReflect.call(Class.forName("com.norwood.mcheli.weapon.MCH_WeaponInfoManager"),"get","105mm");
            check(info!=null,"real cannon definition loaded");VMCombat.tune(info);
            Object smoke=VMReflect.get(info,"listMuzzleFlashSmoke");
            for(Object s:(Iterable<?>)smoke){check(VMReflect.num(VMReflect.get(s,"size"))<=2.201,"muzzle smoke size capped: "+VMReflect.get(s,"size"));check(VMReflect.num(VMReflect.get(s,"num"))<=3,"muzzle smoke particle budget");}
            Object pos=Class.forName("net.minecraft.util.math.Vec3d").getConstructor(double.class,double.class,double.class).newInstance(0D,80D,0D);
            Object weapon=VMReflect.call(Class.forName("com.norwood.mcheli.weapon.MCH_WeaponCreator"),"createWeapon",world,"105mm",pos,0F,0F,null,false);
            check(weapon!=null,"real cannon created");
            Object entity=Class.forName("com.norwood.mcheli.helicopter.MCH_EntityHeli").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
            VMReflect.call(entity,"setTypeName","rc-goblin");VMReflect.call(entity,"func_70107_b",0D,80D,0D);
            Object fire=VMReflect.get(info,"fireSound");check(VMCombat.weaponSound(weapon,entity,fire),"real server weapon sound path");
            check(VMCombat.soundAt(world,0,80,0,fire,1,1),"real positional sound path");
            Object bullet=Class.forName("com.norwood.mcheli.weapon.MCH_EntityBullet").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
            VMReflect.call(bullet,"setName","105mm");
            Object hit=Class.forName("net.minecraft.util.math.RayTraceResult").getConstructor(Class.forName("net.minecraft.util.math.Vec3d"),Class.forName("net.minecraft.util.EnumFacing"),Class.forName("net.minecraft.util.math.BlockPos")).newInstance(pos,VMReflect.get(Class.forName("net.minecraft.util.EnumFacing"),"UP"),Class.forName("net.minecraft.util.math.BlockPos").getConstructor(double.class,double.class,double.class).newInstance(0D,80D,0D));
            VMCombat.impact(bullet,hit);
            check(true,"real projectile impact path invoked");
            Object data=Class.forName("com.norwood.mcheli.networking.data.DataPlayerControlVehicle").newInstance();VMReflect.set(data,"vmThrottle",.8F);
            VMFlight.receive(entity,data,null);check(VMFlight.throttle(entity,.2)==.2,"unoccupied drone rejects remote throttle");
            VMFlight.local(entity,.8);check(VMFlight.throttle(entity,.2)>.2,"analog throttle approaches target");
            VMReflect.call(Class.forName("com.norwood.mcheli.uav.WarfareFpv"),"resetControl",entity);check(VMFlight.throttle(entity,0)==0,"reconnect discards old analog throttle");
            VMFlight.local(entity,.8);
            Thread.sleep(450);check(VMFlight.throttle(entity,.2)<.2,"missing packets cut throttle");
            VMReflect.call(entity,"setCurrentThrottle",.5D);VMFlight.afterControl(true,entity);check(VMReflect.num(VMReflect.call(entity,"getCurrentThrottle"))==0,"empty aircraft cannot retain thrust");
            check(VMCombat.suppressRecoil(entity),"FPV attitude protected from weapon recoil");
            shot(world,"105mm",0);
            shot(world,"rehinmetall_apfsds",32);
            System.out.println("[VM integration] COMPLETE "+checks);
        }catch(Throwable e){System.out.println("[VM integration] FAILED");e.printStackTrace();}
        return true;
    }
}
