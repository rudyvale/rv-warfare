import com.norwood.mcheli.vm.*;

public final class VMControlsRuntime {
    private static int checks;
    private static void check(boolean value,String label){if(!value)throw new IllegalStateException(label);checks++;System.out.println("[VM integration] PASS "+label);}
    public static boolean command(Object server,Object sender,String[] args){
        if(!Boolean.getBoolean("vm.controls.integration") || server!=sender || args.length!=1 || !args[0].equals("vmcontrolscheck"))return false;
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
            System.out.println("[VM integration] COMPLETE "+checks);
        }catch(Throwable e){System.out.println("[VM integration] FAILED");e.printStackTrace();}
        return true;
    }
}
