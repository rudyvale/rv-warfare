import com.norwood.mcheli.vm.*;
import java.nio.file.*;

public final class VMControlsClientRuntime {
    private static boolean done;
    private static int frames;
    private static void check(boolean result,String label){if(!result)throw new AssertionError(label);System.out.println("[VM client integration] PASS "+label);}
    public static void frame(){
        if(done || !Boolean.getBoolean("vm.controls.integration"))return;
        try {
            Object mc=VMReflect.call(Class.forName("net.minecraft.client.Minecraft"),"func_71410_x");Object player=VMReflect.get(mc,"field_71439_g");
            if(player==null)return;
            Object aircraft=VMReflect.call(Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",player);
            if(aircraft==null || !VMFlight.drone(aircraft) || !(Boolean)VMReflect.call(aircraft,"isPilot",player))return;
            if(++frames<30)return;done=true;
            Object world=VMReflect.get(player,"field_70170_p");
            VMController.INSTANCE.profile.setProperty("enabled","false");VMController.INSTANCE.profile.setProperty("flight","angle");
            VMReflect.set(aircraft,"field_70122_E",false);VMReflect.call(aircraft,"setRotPitch",25F);VMReflect.call(aircraft,"setRotRoll",20F);
            VMReflect.call(aircraft,"setAngles",player,false,0F,0F,0F,0F,0F,0F,.05F);
            check(VMReflect.num(VMReflect.call(aircraft,"getPitch"))<25 && VMReflect.num(VMReflect.call(aircraft,"getRoll"))<20,"actual setAngles hook levels FPV");
            check((Boolean)VMReflect.get(aircraft,"aircraftRotChanged"),"rotation marked for network sync");
            VMController.INSTANCE.profile.setProperty("flight","acro");
            for(float p:new float[]{-90F,-89.9999F,0F,89.9999F,90F}){
                VMReflect.call(aircraft,"setRotYaw",-180F);VMReflect.call(aircraft,"setRotPitch",p);VMReflect.call(aircraft,"setRotRoll",165F);
                VMReflect.call(aircraft,"setAngles",player,false,0F,0F,0F,0F,0F,0F,.01F);
                check(Double.isFinite(VMReflect.num(VMReflect.call(aircraft,"getPitch"))+VMReflect.num(VMReflect.call(aircraft,"getRoll"))),"actual Acro vertical pose "+p);
            }
            Object info=VMReflect.call(Class.forName("com.norwood.mcheli.weapon.MCH_WeaponInfoManager"),"get","105mm");
            VMReflect.set(aircraft,"field_70122_E",true);
            VMReflect.call(aircraft,"setAngles",player,false,0F,0F,15F,15F,0F,0F,.05F);
            check(VMReflect.get(VMPilot.class,"attitude")==null,"grounded Acro discards unapplied attitude");
            double groundPitch=VMReflect.num(VMReflect.call(aircraft,"getPitch"));
            VMReflect.set(aircraft,"field_70122_E",false);
            VMReflect.call(aircraft,"setAngles",player,false,0F,0F,0F,0F,0F,0F,0F);
            check(Math.abs(VMReflect.num(VMReflect.call(aircraft,"getPitch"))-groundPitch)<.1,"takeoff has no accumulated pitch jump");
            VMFlight.local(aircraft,.8);
            Object data=Class.forName("com.norwood.mcheli.networking.data.DataPlayerControlVehicle").newInstance();
            check(VMPilot.packet(false,aircraft,data,true),"disabling controller sends keyboard handover packet");
            check(VMFlight.throttle(aircraft,.3)==.3,"keyboard regains local throttle immediately");
            Object fire=VMReflect.get(info,"fireSound");
            check(VMCombat.soundAt(world,VMReflect.num(VMReflect.get(aircraft,"field_70165_t")),VMReflect.num(VMReflect.get(aircraft,"field_70163_u")),VMReflect.num(VMReflect.get(aircraft,"field_70161_v")),fire,1,1),"real client positional sound overload");
            Object direction=Class.forName("net.minecraft.util.math.Vec3d").getConstructor(double.class,double.class,double.class).newInstance(0D,0D,1D);
            VMReflect.call(aircraft,"spawnParticleMuzzleFlash",world,info,VMReflect.num(VMReflect.get(aircraft,"field_70165_t")),VMReflect.num(VMReflect.get(aircraft,"field_70163_u")),VMReflect.num(VMReflect.get(aircraft,"field_70161_v")),direction);
            check(true,"real confirmed muzzle sound and particles invoked");
            double beforePitch=VMReflect.num(VMReflect.call(aircraft,"getPitch"));
            VMReflect.call(aircraft,"setTypeName","ah-64");
            VMCombat.muzzle(aircraft,info,0,12,0);
            Object event=null;
            for(java.lang.reflect.Constructor<?> constructor:Class.forName("net.minecraftforge.client.event.EntityViewRenderEvent$CameraSetup").getConstructors())if(constructor.getParameterTypes().length==7)event=constructor.newInstance(null,player,null,0D,0F,0F,0F);
            Thread.sleep(50);VMCombat.camera(event);
            double kick=Math.abs(VMReflect.num(VMReflect.call(event,"getPitch")));
            check(kick>0 && kick<=1.25,"bounded cannon camera recoil applied to real Forge event");
            check(VMReflect.num(VMReflect.call(aircraft,"getPitch"))==beforePitch,"camera recoil does not change vehicle attitude");
            VMReflect.call(aircraft,"setTypeName","rc-goblin");
            Object bullet=Class.forName("com.norwood.mcheli.weapon.MCH_EntityBullet").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);VMReflect.call(bullet,"setName","105mm");
            VMReflect.call(bullet,"func_70107_b",2D,12D,2D);VMReflect.set(bullet,"field_70169_q",1D);VMReflect.set(bullet,"field_70167_r",12D);VMReflect.set(bullet,"field_70166_s",2D);VMCombat.trail(bullet);
            check(true,"real client tracer particles invoked");
            VMController.INSTANCE.profile.setProperty("flight","angle");VMReflect.call(aircraft,"setRotYaw",0F);VMReflect.call(aircraft,"setRotPitch",0F);VMReflect.call(aircraft,"setRotRoll",0F);VMReflect.call(aircraft,"resyncOrientationFromEuler");
            Files.write(Paths.get("client-check.txt"),"PASS actual client controls, camera orientation, sound and particles".getBytes("UTF-8"));
            System.out.println("[VM client integration] COMPLETE");
        }catch(Throwable e){done=true;System.out.println("[VM client integration] FAILED");e.printStackTrace();}
    }
}
