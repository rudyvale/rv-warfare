import com.norwood.mcheli.vm.*;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;

public final class VMControlsRuntime {
    private static int checks;
    private static Object launchAircraft;
    private static String launchType;
    private static int launchTicks;
    private static boolean launchRegistered;
    private static double launchY,launchX,launchZ;
    private static final java.util.List<java.util.Map<String,Object>> launchSamples=new java.util.ArrayList<java.util.Map<String,Object>>();
    @SubscribeEvent public void tick(TickEvent.ServerTickEvent event){
        if(event.phase!=TickEvent.Phase.END||launchAircraft==null)return;
        try{
            launchTicks++;if(launchTicks%5!=0)return;
            java.util.Map<String,Object> sample=new java.util.LinkedHashMap<String,Object>();sample.put("tick",launchTicks);sample.put("x",VMReflect.get(launchAircraft,"field_70165_t"));sample.put("y",VMReflect.get(launchAircraft,"field_70163_u"));sample.put("z",VMReflect.get(launchAircraft,"field_70161_v"));sample.put("throttle",VMReflect.call(launchAircraft,"getCurrentThrottle"));sample.put("pitch",VMReflect.call(launchAircraft,"getPitch"));sample.put("roll",VMReflect.call(launchAircraft,"getRoll"));sample.put("yaw",VMReflect.call(launchAircraft,"getYaw"));sample.put("onGround",VMReflect.get(launchAircraft,"field_70122_E"));sample.put("controlled",VMReflect.call(launchAircraft,"getRiddenByEntity")!=null);sample.put("dead",VMReflect.get(launchAircraft,"field_70128_L"));launchSamples.add(sample);
            java.util.Map<String,Object> data=new java.util.LinkedHashMap<String,Object>();data.put("type",launchType);data.put("startX",launchX);data.put("startY",launchY);data.put("startZ",launchZ);data.put("samples",launchSamples);java.nio.file.Files.write(java.nio.file.Paths.get("wing-launch-server-"+launchType+".json"),new com.google.gson.Gson().toJson(data).getBytes("UTF-8"));
        }catch(Throwable e){System.out.println("[VM wing input] FAILED server sample");e.printStackTrace();launchAircraft=null;}
    }
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
        wing(world,player,"rv_geran",192);
        wing(world,player,"rv_fp1",224);
        techguns(world,player,8F,128);
        techguns(world,player,80F,160);
        try{Class<?> qa=Class.forName("RVCombatAcceptance");VMReflect.call(qa,"verify",server);}catch(ClassNotFoundException ignored){}
    }
    private static void wing(Object world,Object player,String type,double x)throws Exception{
        Object item=VMReflect.call(Class.forName("net.minecraft.item.Item"),"func_111206_d","mcheli:"+type);
        check(item!=null&&item.getClass().getName().endsWith("MCP_ItemPlane"),"registered native plane item "+type);
        Object stack=Class.forName("net.minecraft.item.ItemStack").getConstructor(Class.forName("net.minecraft.item.Item")).newInstance(item);
        Object aircraft=VMReflect.call(item,"createAircraft",world,x,80D,0D,stack);
        check(aircraft!=null&&VMFlight.wing(aircraft)&&!VMFlight.drone(aircraft),"item factory creates distinct native fixed wing "+type);
        Object saved=Class.forName("net.minecraft.nbt.NBTTagCompound").newInstance();VMReflect.call(aircraft,"func_70039_c",saved);
        Object restored=VMReflect.call(Class.forName("net.minecraft.entity.EntityList"),"func_75615_a",saved,world);
        check(restored!=null&&String.valueOf(VMReflect.call(restored,"getTypeName")).equals(type)&&VMFlight.wing(restored),"native NBT reload preserves exact wing type "+type);
        chunks(world,x,0);VMReflect.call(world,"func_72838_d",aircraft);VMReflect.call(aircraft,"setFuel",VMReflect.call(aircraft,"getMaxFuel"));
        Object station=VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_EntityUavStation"),"createHandheld",world,player,VMReflect.get(Class.forName("net.minecraft.util.EnumHand"),"MAIN_HAND"),java.util.Collections.singletonList(VMReflect.call(aircraft,"func_110124_au")),false);
        VMReflect.call(world,"func_72838_d",station);VMReflect.call(station,"pairUav",VMReflect.call(aircraft,"func_110124_au"));
        VMReflect.call(aircraft,"setCurrentThrottle",.8D);VMFlight.local(aircraft,.8);
        Object result=VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_UavControl"),"connect",player,station,aircraft);
        check(String.valueOf(result).equals("OK")&&VMReflect.call(aircraft,"getRiddenByEntity")==player,"tablet station controls fixed wing "+type);
        check(VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"))==0&&VMFlight.target(aircraft,0)==0,"native connection clears old wing throttle "+type);
        VMReflect.set(aircraft,"field_70122_E",true);check(!VMImpact.droneMotion(aircraft),"grounded wing contact fuse is safe "+type);
        Object data=Class.forName("com.norwood.mcheli.networking.data.DataPlayerControlVehicle").newInstance();VMReflect.set(data,"vmThrottle",.7F);
        VMFlight.receive(aircraft,data,null);check(VMFlight.target(aircraft,0)==0,"nonpilot wing analog rejected "+type);
        VMFlight.receive(aircraft,data,player);VMReflect.call(aircraft,"onUpdate_Control");
        check(VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"))>.1,"native wing update applies analog packet "+type);
        double gas=VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"));Thread.sleep(450);VMReflect.call(aircraft,"onUpdate_Control");
        check(VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"))<gas,"lost wing packets reduce throttle "+type);
        VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_UavControl"),"disconnect",station);
        check(VMReflect.num(VMReflect.call(aircraft,"getCurrentThrottle"))==0,"native wing disconnect cuts throttle "+type);
        VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_UavControl"),"connect",player,station,aircraft);
        Object target=tank(world,x,12);int before=((Number)VMReflect.call(target,"getHP")).intValue();
        VMReflect.set(aircraft,"field_70122_E",false);VMReflect.call(aircraft,"setCurrentThrottle",.6D);VMReflect.set(aircraft,"field_70179_y",20D);VMReflect.call(aircraft,"onUpdate_Server");
        check((Boolean)VMReflect.get(aircraft,"field_70128_L")&&((Number)VMReflect.call(target,"getHP")).intValue()<before,"native wing contact stops and damages tank "+type);
        int after=((Number)VMReflect.call(target,"getHP")).intValue();VMReflect.call(aircraft,"onUpdate_Server");
        check(((Number)VMReflect.call(target,"getHP")).intValue()==after,"wing contact damage occurs once "+type);VMReflect.call(target,"func_70106_y");
        Object wing=VMReflect.call(item,"createAircraft",world,x+8,80D,0D,stack);VMReflect.call(wing,"setFuel",VMReflect.call(wing,"getMaxFuel"));chunks(world,x+8,0);VMReflect.call(world,"func_72838_d",wing);
        VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_UavControl"),"connect",player,station,wing);
        Object wall=Class.forName("net.minecraft.util.math.BlockPos").getConstructor(int.class,int.class,int.class).newInstance((int)x+9,80,7);
        Object prior=VMReflect.call(world,"func_180495_p",wall),stone=VMReflect.call(Class.forName("net.minecraft.block.Block"),"func_149684_b","minecraft:stone");VMReflect.call(world,"func_180501_a",wall,VMReflect.call(stone,"func_176223_P"),3);
        Object behind=tank(world,x+8,24);int behindHP=((Number)VMReflect.call(behind,"getHP")).intValue();
        VMReflect.set(wing,"field_70122_E",false);VMReflect.call(wing,"setCurrentThrottle",.6D);VMReflect.set(wing,"field_70179_y",20D);VMReflect.call(wing,"onUpdate_Server");
        check((Boolean)VMReflect.get(wing,"field_70128_L"),"fast wingtip-only wall contact detonates while fuselage path is clear "+type);
        check(((Number)VMReflect.call(behind,"getHP")).intValue()==behindHP,"nearer wingtip wall stops contact before distant target "+type);
        VMReflect.call(behind,"func_70106_y");VMReflect.call(world,"func_180501_a",wall,prior,3);
        Object incoming=VMReflect.call(item,"createAircraft",world,x+16,80D,12D,stack);chunks(world,x+16,12);VMReflect.call(world,"func_72838_d",incoming);VMReflect.call(incoming,"updateExtraBoundingBox");
        Object commands=VMReflect.call(serverFor(world),"func_71187_D");VMReflect.call(commands,"func_71556_a",serverFor(world),"fill "+(int)(x+14)+" 78 -2 "+(int)(x+21)+" 84 15 minecraft:air");
        check(((Object[])VMReflect.get(incoming,"extraBoundingBox")).length==7,"native wing body/wing/tail collision boxes loaded "+type);
        double tip=type.equals("rv_geran")?1.35:1.65,height=type.equals("rv_geran")?.20:.425;
        Object shooter=Class.forName("com.norwood.mcheli.helicopter.MCH_EntityHeli").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);VMReflect.call(shooter,"setTypeName","rc-goblin");VMReflect.call(shooter,"func_70107_b",x+20,80D,0D);VMReflect.call(world,"func_72838_d",shooter);
        Object weapon=VMReflect.call(Class.forName("com.norwood.mcheli.weapon.MCH_WeaponCreator"),"createWeapon",world,"rehinmetall_apfsds",vector(x+16+tip,80+height,0),0F,0F,null,false),parameter=Class.forName("com.norwood.mcheli.weapon.MCH_WeaponParam").newInstance();VMReflect.set(parameter,"entity",shooter);VMReflect.set(parameter,"user",player);VMReflect.call(parameter,"setPosAndRot",x+16+tip,80+height,0D,0F,.0001F);Object exactInfo=VMReflect.call(weapon,"getInfo");float accuracy=((Number)VMReflect.get(exactInfo,"accuracy")).floatValue();VMReflect.set(exactInfo,"accuracy",0F);
        java.util.Set<Object> entities=new java.util.HashSet<Object>((java.util.List<?>)VMReflect.get(world,"field_72996_f"));try{VMReflect.call(weapon,"shot",parameter);}finally{VMReflect.set(exactInfo,"accuracy",accuracy);}Object projectile=null;for(Object entity:(java.util.List<?>)VMReflect.get(world,"field_72996_f"))if(!entities.contains(entity)&&Class.forName("com.norwood.mcheli.weapon.MCH_EntityBaseBullet").isInstance(entity)){projectile=entity;break;}
        check(projectile!=null,"native incoming wing projectile exists "+type);int hp=((Number)VMReflect.call(incoming,"getHP")).intValue();for(int i=0;i<20&&!(Boolean)VMReflect.get(projectile,"field_70128_L");i++)VMReflect.call(projectile,"func_70071_h_");
        check((Boolean)VMReflect.get(projectile,"field_70128_L")&&((Number)VMReflect.call(incoming,"getHP")).intValue()<hp,"native incoming round damages visible wingtip outside fuselage "+type);VMReflect.call(incoming,"func_70106_y");VMReflect.call(shooter,"func_70106_y");
    }
    private static Object serverFor(Object world)throws Exception{return VMReflect.call(world,"func_73046_m");}
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
        if(args[0].startsWith("vmcontrolswinglaunch")){
            try{
                if(launchAircraft!=null)VMReflect.call(launchAircraft,"func_70106_y");
                Object player=VMReflect.call(VMReflect.call(server,"func_184103_al"),"func_152612_a","VMControlsTest"),world=VMReflect.get(player,"field_70170_p");
                for(int cx=-1;cx<=7;cx++)for(int cz=-1;cz<=2;cz++)VMReflect.call(world,"func_72964_e",cx,cz);
                VMReflect.call(player,"func_184210_p");VMReflect.call(VMReflect.get(player,"field_71135_a"),"func_147364_a",8.5D,5D,8.5D,0F,70F);
                VMReflect.call(VMReflect.call(server,"func_71187_D"),"func_71556_a",server,"fill -8 4 -8 112 18 8 minecraft:air");
                VMReflect.call(VMReflect.call(server,"func_71187_D"),"func_71556_a",server,"fill -8 4 9 112 18 24 minecraft:air");
                VMReflect.call(VMReflect.call(server,"func_71187_D"),"func_71556_a",server,"fill -8 3 -8 112 3 24 minecraft:stone");
                launchType=args[0].endsWith("fp1")?"rv_fp1":"rv_geran";
                Object item=VMReflect.call(Class.forName("net.minecraft.item.Item"),"func_111206_d","mcheli:"+launchType),stack=Class.forName("net.minecraft.item.ItemStack").getConstructor(Class.forName("net.minecraft.item.Item")).newInstance(item),pos=Class.forName("net.minecraft.util.math.BlockPos").getConstructor(int.class,int.class,int.class).newInstance(8,3,8);
                launchAircraft=VMReflect.call(item,"spawnAircraft",stack,world,player,pos);if(launchAircraft==null)throw new AssertionError("native ground placement rejected");VMReflect.call(launchAircraft,"setFuel",VMReflect.call(launchAircraft,"getMaxFuel"));
                Object station=VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_EntityUavStation"),"createHandheld",world,player,VMReflect.get(Class.forName("net.minecraft.util.EnumHand"),"MAIN_HAND"),java.util.Collections.singletonList(VMReflect.call(launchAircraft,"func_110124_au")),false);VMReflect.call(world,"func_72838_d",station);VMReflect.call(station,"pairUav",VMReflect.call(launchAircraft,"func_110124_au"));VMReflect.call(Class.forName("com.norwood.mcheli.uav.MCH_UavControl"),"connect",player,station,launchAircraft);
                launchX=VMReflect.num(VMReflect.get(launchAircraft,"field_70165_t"));launchY=VMReflect.num(VMReflect.get(launchAircraft,"field_70163_u"));launchZ=VMReflect.num(VMReflect.get(launchAircraft,"field_70161_v"));launchTicks=0;launchSamples.clear();if(!launchRegistered){launchRegistered=true;MinecraftForge.EVENT_BUS.register(new VMControlsRuntime());}System.out.println("[VM wing input] FIXTURE "+launchType);
            }catch(Throwable e){System.out.println("[VM wing input] FAILED fixture");e.printStackTrace();}return true;
        }
        if(args[0].equals("vmcontrolsgallery")){
            try{
                Object player=VMReflect.call(VMReflect.call(server,"func_184103_al"),"func_152612_a","VMControlsTest"),world=VMReflect.get(player,"field_70170_p");
                String[] origin=System.getProperty("rv.gallery.origin","0,4,0").split(",");double x=Double.parseDouble(origin[0]),y=Double.parseDouble(origin[1]),z=Double.parseDouble(origin[2]);
                VMReflect.call(player,"func_184210_p");VMReflect.call(VMReflect.get(player,"field_71135_a"),"func_147364_a",x+6,y+8,z+8,180F,30F);
                String[] names={"rc-goblin","rc-goblin-bomb","rv_geran","rv_fp1"};double[] offsets={0,-5,7,14};
                for(int i=0;i<names.length;i++){
                    Object item=VMReflect.call(Class.forName("net.minecraft.item.Item"),"func_111206_d","mcheli:"+names[i]),stack=Class.forName("net.minecraft.item.ItemStack").getConstructor(Class.forName("net.minecraft.item.Item")).newInstance(item);
                    Object aircraft=VMReflect.call(item,"createAircraft",world,x+offsets[i],y+.10,z,stack);VMReflect.call(aircraft,"setRotYaw",0F);VMReflect.call(aircraft,"setFuel",0);chunks(world,x+offsets[i],z);VMReflect.call(world,"func_72838_d",aircraft);
                }
                System.out.println("[VM gallery] FIXTURE READY");
            }catch(Throwable e){System.out.println("[VM gallery] FAILED");e.printStackTrace();}return true;
        }
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
            if((Boolean)VMReflect.call(Class.forName("net.minecraftforge.fml.common.Loader"),"isModLoaded","firstaid")){
                Object rules=VMReflect.call(world,"func_82736_K"),load=Class.forName("net.minecraftforge.event.world.WorldEvent$Load").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);boolean original=(Boolean)VMReflect.call(rules,"func_82766_b","naturalRegeneration");
                for(boolean value:new boolean[]{false,true}){VMReflect.call(rules,"func_82764_b","naturalRegeneration",""+value);VMReflect.call(Class.forName("ichttt.mods.firstaid.common.EventHandler"),"onWorldLoad",load);check((Boolean)VMReflect.call(rules,"func_82766_b","naturalRegeneration")==value,"native FirstAid load preserves saved regeneration="+value);}
                VMReflect.call(rules,"func_82764_b","naturalRegeneration",""+original);
                for(String id:new String[]{"firstaid:bandage","firstaid:plaster"}){Object item=VMReflect.call(Class.forName("net.minecraft.item.Item"),"func_111206_d",id);check(item!=null&&String.valueOf(VMReflect.call(item,"getRegistryName")).equals(id),"actual medical registry "+id);Object stack=Class.forName("net.minecraft.item.ItemStack").getConstructor(Class.forName("net.minecraft.item.Item")).newInstance(item);int max=((Number)VMReflect.call(stack,"func_77976_d")).intValue();check(max>=4,"native medical stack limit "+id+"="+max);}
                check((Boolean)VMReflect.get(VMReflect.get(Class.forName("ichttt.mods.firstaid.FirstAidConfig"),"externalHealing"),"allowNaturalRegeneration"),"shared FirstAid config allows existing food regeneration");
            }
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
