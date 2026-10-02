import com.google.gson.Gson;
import com.norwood.mcheli.vm.VMCombat;
import com.norwood.mcheli.vm.VMController;
import com.norwood.mcheli.vm.VMReflect;
import java.lang.reflect.Array;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.io.File;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;
import org.lwjgl.input.Keyboard;
import org.lwjgl.input.Mouse;

public final class RVTankInputRuntime {
    private static Object world,player,shooter,target;
    private static boolean registered,active,pressed,finished;
    private static int ticks,packets,weaponPackets,created,attackKey,fireTick,nativeFireKey=999;
    private static int initialHP,initialAmmo;
    private static final java.util.Set<Object> bullets=java.util.Collections.newSetFromMap(new java.util.IdentityHashMap<Object,Boolean>());
    private static final List<Map<String,Object>> samples=new ArrayList<Map<String,Object>>();
    private static final List<Long> tickTimes=new ArrayList<Long>();
    private static final List<Map<String,Object>> impacts=new ArrayList<Map<String,Object>>();
    private static final List<Map<String,Object>> trajectories=new ArrayList<Map<String,Object>>();
    private static final List<Map<String,Object>> feedback=new ArrayList<Map<String,Object>>();
    private static final List<Map<String,Object>> rawFeedback=new ArrayList<Map<String,Object>>();
    private static final List<Map<String,Object>> feedbackAttempts=new ArrayList<Map<String,Object>>();
    private static final List<Map<String,Object>> particlePackets=new ArrayList<Map<String,Object>>();
    private static final List<String> observerErrors=new ArrayList<String>();
    private static final Map<String,Object> nativeBindings=new LinkedHashMap<String,Object>();
    private static long feedbackCount;
    private static int screenshotTick;
    private static final Map<String,Object> result=new LinkedHashMap<String,Object>();
    private static long tickStart;
    private static int matrixTick,matrixStage;
    private static Object matrixTarget,matrixBullet;
    private static double matrixBefore;
    private static long matrixNotifications;
    private static final List<Map<String,Object>> matrix=new ArrayList<Map<String,Object>>();
    private static Object authOld;
    private static boolean keysActive;
    private static int keyTicks;
    private static Object keyAircraft;
    private static final java.util.Set<Integer> virtualDown=new java.util.HashSet<Integer>();
    private static final List<Map<String,Object>> controlSamples=new ArrayList<Map<String,Object>>();
    private static Class<?> type(String name)throws Exception{return Class.forName(name);}
    private static Object call(Object value,String name,Object... args)throws Exception{return VMReflect.call(value,name,args);}
    private static int number(Object value){return ((Number)value).intValue();}
    private static double num(Object value,String field)throws Exception{return VMReflect.num(VMReflect.get(value,field));}
    private static void register(){if(!registered){registered=true;MinecraftForge.EVENT_BUS.register(new RVTankInputRuntime());}}
    private static void write(String name,Map<String,Object> value)throws Exception{Files.write(Paths.get(name),new Gson().toJson(value).getBytes("UTF-8"));}
    private static void fail(Throwable error){finished=true;active=false;pressed=false;result.put("exception",error.toString());try{write("tank-input-failed.json",result);}catch(Exception ignored){}error.printStackTrace();}
    public static void frame(){if(Boolean.getBoolean("rv.tank.input.qa"))register();}
    public static boolean keyDown(int key){return active||keysActive?virtualDown.contains(key)||pressed&&attackKey==key:Keyboard.isKeyDown(key);}
    public static boolean mouseDown(int button){return active||keysActive?virtualDown.contains(button-100)||pressed&&attackKey==button-100:Mouse.isButtonDown(button);}
    public static void handler(Object handler){if(!Boolean.getBoolean("rv.tank.input.qa"))return;try{nativeFireKey=number(VMReflect.get(VMReflect.get(handler,"KeyUseWeapon"),"key"));for(String name:new String[]{"KeyUseWeapon","KeySwitchWeapon1","KeySwitchWeapon2","KeySwWeaponMode","KeyReloadWeapon","KeySwitchMode","KeyZoom","KeyFreeLook"})nativeBindings.put(name,VMReflect.get(VMReflect.get(handler,name),"key"));}catch(Exception e){fail(e);}}
    public static void packet(Object aircraft,Object data,Object who){
        if(!Boolean.getBoolean("rv.tank.input.qa")||aircraft!=shooter)return;
        try{packets++;if((Boolean)call(data,"isUseWeapon"))weaponPackets++;}catch(Exception e){fail(e);}
    }
    public static void bulletUpdate(Object entity){
        if(!Boolean.getBoolean("rv.tank.input.qa")||shooter==null)return;
        try{if(VMReflect.remote(entity)||!bullets.add(entity))return;created++;Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("x",num(entity,"field_70165_t"));value.put("y",num(entity,"field_70163_u"));value.put("z",num(entity,"field_70161_v"));value.put("motionX",num(entity,"field_70159_w"));value.put("motionY",num(entity,"field_70181_x"));value.put("motionZ",num(entity,"field_70179_y"));trajectories.add(value);}catch(Exception e){fail(e);}
    }
    public static void impact(Object bullet,Object hit){
        if(!Boolean.getBoolean("rv.tank.input.qa"))return;
        try{if(VMReflect.remote(bullet))return;Map<String,Object> value=new LinkedHashMap<String,Object>();Object point=VMReflect.get(hit,"field_72307_f"),entity=VMReflect.get(hit,"field_72308_g");value.put("kind",String.valueOf(VMReflect.get(hit,"field_72313_a")));value.put("entity",entity==null?"none":entity.getClass().getName());if(point!=null){value.put("x",num(point,"field_72450_a"));value.put("y",num(point,"field_72448_b"));value.put("z",num(point,"field_72449_c"));}impacts.add(value);}catch(Exception e){fail(e);}
    }
    public static void feedbackPacket(Object packet){
        if(!Boolean.getBoolean("rv.tank.input.qa"))return;
        try{int encoded=number(VMReflect.get(packet,"entityID_Ac"));if(encoded>-2||encoded<-(2+3*1048576-1))return;int value=-encoded-2;Map<String,Object> data=new LinkedHashMap<String,Object>();data.put("code",value/1048576);data.put("damageTenths",value%1048576);data.put("clientTick",ticks);rawFeedback.add(data);Map<String,Object> report=new LinkedHashMap<String,Object>();report.put("events",rawFeedback);write("feedback-packets-client.json",report);}catch(Exception e){fail(e);}
    }
    public static void feedbackAttempt(Object who,double before,double after,boolean dead){
        if(!Boolean.getBoolean("rv.tank.input.qa")||matrixStage<=0)return;
        Map<String,Object> data=new LinkedHashMap<String,Object>();data.put("stage",matrixStage);data.put("before",before);data.put("after",after);data.put("dead",dead);data.put("serverMatrixTick",matrixTick);feedbackAttempts.add(data);
    }
    public static Object particleCall(Object receiver,String name,Object[] arguments)throws Exception{
        Object returned=VMReflect.call(receiver,name,arguments);
        if(Boolean.getBoolean("rv.tank.input.qa")&&name.equals("func_147359_a")&&arguments.length==1&&arguments[0].getClass().getName().equals("net.minecraft.network.play.server.SPacketParticles")){
            try{Map<String,Object> data=new LinkedHashMap<String,Object>();for(Field field:arguments[0].getClass().getDeclaredFields()){field.setAccessible(true);if(field.getType().getName().equals("net.minecraft.util.EnumParticleTypes"))data.put("type",String.valueOf(field.get(arguments[0])));else if(field.getType()==boolean.class)data.put("longDistance",field.get(arguments[0]));else if(field.getType()==int.class)data.put("count",field.get(arguments[0]));}data.put("matrixStage",matrixStage);particlePackets.add(data);}catch(Exception e){observerErrors.add(e.toString());}
        }
        return returned;
    }
    private static Object tank(double x,double z)throws Exception{
        Object entity=type("com.norwood.mcheli.tank.MCH_EntityTank").getConstructor(type("net.minecraft.world.World")).newInstance(world);
        call(entity,"setTypeName","m1a2");call(entity,"setTextureName","m1a2");call(entity,"changeType","m1a2");call(entity,"func_70107_b",x,4D,z);
        call(entity,"setRotYaw",0F);call(entity,"setRotPitch",0F);call(entity,"setRotRoll",0F);call(entity,"resyncOrientationFromEuler");call(entity,"setFuel",call(entity,"getMaxFuel"));
        call(world,"func_72964_e",(int)x>>4,(int)z>>4);
        if(!(Boolean)call(world,"func_72838_d",entity))throw new AssertionError("tank spawn rejected");
        call(entity,"updateExtraBoundingBox");
        return entity;
    }
    public static boolean command(Object server,Object sender,String[] args){
        if(!Boolean.getBoolean("rv.tank.input.qa")||server!=sender||args.length!=1||!args[0].startsWith("rvtankinput"))return false;
        try{
            if(args[0].equals("rvtankinputauthbefore")||args[0].equals("rvtankinputauthafter")){
                Object current=call(call(server,"func_184103_al"),"func_152612_a","Owner_1");
                if(args[0].endsWith("before")){if(current==null)throw new AssertionError("trusted owner absent");authOld=current;}
                Map<String,Object> data=new LinkedHashMap<String,Object>();data.put("currentPresent",current!=null);data.put("oldPresent",authOld!=null);data.put("currentIsOld",current==authOld);data.put("oldChannelOpen",authOld!=null&&channelOpen(authOld));data.put("currentChannelOpen",current!=null&&channelOpen(current));data.put("oldOperator",authOld!=null&&(Boolean)call(authOld,"func_70003_b",2,"time"));data.put("currentOperator",current!=null&&(Boolean)call(current,"func_70003_b",2,"time"));data.put("currentOwnerTag",current!=null&&((java.util.Set<?>)call(current,"func_184216_O")).contains("v_owner"));data.put("onlineCount",call(call(server,"func_184103_al"),"func_72394_k"));
                write(args[0].endsWith("before")?"owner-duplicate-before.json":"owner-duplicate-after.json",data);System.out.println("[RV owner duplicate] "+new Gson().toJson(data));
            }else if(args[0].equals("rvtankinputsetup")){
                register();player=call(call(server,"func_184103_al"),"func_152612_a","RVTankQA");
                if(player==null)throw new AssertionError("QA player is absent");world=VMReflect.get(player,"field_70170_p");
                for(int x=-3;x<=3;x++)for(int z=-3;z<=6;z++)call(world,"func_72964_e",x,z);
                call(call(server,"func_71187_D"),"func_71556_a",server,"fill 0 4 0 16 18 64 minecraft:air");
                for(int x=0;x<=16;x++)for(int y=4;y<=18;y++)for(int z=0;z<=64;z++)if(!(Boolean)call(world,"func_175623_d",type("net.minecraft.util.math.BlockPos").getConstructor(int.class,int.class,int.class).newInstance(x,y,z)))throw new AssertionError("Actual firing corridor contains a block");
                shooter=tank(8.5,8.5);target=tank(8.5,44.5);initialHP=number(call(target,"getHP"));
                call(player,"func_184210_p");call(VMReflect.get(player,"field_71135_a"),"func_147364_a",8.5D,5D,8.5D,0F,2F);
                if(!(Boolean)call(player,"func_184205_a",shooter,true))throw new AssertionError("pilot mount rejected");
                call(shooter,"initCurrentWeapon",player);Object weapon=call(shooter,"getCurrentWeapon",player);initialAmmo=number(call(weapon,"getAmmo"));
                if("none".equals(call(weapon,"getName"))||initialAmmo<=0)throw new AssertionError("fixture weapon is not loaded");
                result.put("initialHP",initialHP);result.put("initialAmmo",initialAmmo);result.put("initialAmmoReserve",call(weapon,"getAmmoReserve"));result.put("seat",call(shooter,"getSeatIdByEntity",player));result.put("weapon",call(weapon,"getName"));
                System.out.println("[RV tank input] server fixture ready "+new Gson().toJson(result));
            }else if(args[0].equals("rvtankinputfeedback")){
                matrixStage=1;matrixTick=0;matrix.clear();
                beginMatrix();
            }else if(args[0].equals("rvtankinputfinish")){
                Object weapon=call(shooter,"getCurrentWeapon",player);
                result.put("packets",packets);result.put("weaponPackets",weaponPackets);result.put("projectilesCreated",created);result.put("finalHP",call(target,"getHP"));result.put("finalAmmo",call(weapon,"getAmmo"));result.put("finalAmmoReserve",call(weapon,"getAmmoReserve"));
                result.put("observedProjectileStopped",!bullets.isEmpty()&&allStopped());result.put("serverTickNanos",tickTimes);result.put("impacts",impacts);result.put("trajectories",trajectories);result.put("particlePacketsSent",particlePackets);result.put("qaObserverErrors",observerErrors);result.put("targetY",num(target,"field_70163_u"));result.put("targetBoundingBox",String.valueOf(call(target,"func_174813_aQ")));
                if(!trajectories.isEmpty()){Map<String,Object> t=trajectories.get(0);double x=((Number)t.get("x")).doubleValue(),y=((Number)t.get("y")).doubleValue(),z=((Number)t.get("z")).doubleValue();Class<?> vec=type("net.minecraft.util.math.Vec3d");Object from=vec.getConstructor(double.class,double.class,double.class).newInstance(x,y,z),to=vec.getConstructor(double.class,double.class,double.class).newInstance(x+12*((Number)t.get("motionX")).doubleValue(),y+12*((Number)t.get("motionY")).doubleValue(),z+12*((Number)t.get("motionZ")).doubleValue());result.put("actualFlightRayIntersectsTarget",call(call(target,"func_174813_aQ"),"func_72327_a",from,to)!=null);}
                write("tank-input-server.json",result);
                System.out.println("[RV tank input] server complete "+new Gson().toJson(result));
                call(player,"func_184210_p");call(shooter,"func_70106_y");call(target,"func_70106_y");shooter=null;target=null;
            }
        }catch(Throwable e){fail(e);}return true;
    }
    private static boolean allStopped()throws Exception{for(Object bullet:bullets)if(!(Boolean)VMReflect.get(bullet,"field_70128_L"))return false;return true;}
    private static boolean channelOpen(Object who)throws Exception{return (Boolean)call(VMReflect.get(VMReflect.get(who,"field_71135_a"),"field_147371_a"),"func_150724_d");}
    private static double health(Object entity)throws Exception{return ((Number)call(type("com.norwood.mcheli.vm.VMFeedback"),"health",entity)).doubleValue();}
    private static Object nativeShot(String name,double x,double y,double z,int power)throws Exception{
        Object vector=type("net.minecraft.util.math.Vec3d").getConstructor(double.class,double.class,double.class).newInstance(x,y,z);
        Object weapon=call(type("com.norwood.mcheli.weapon.MCH_WeaponCreator"),"createWeapon",world,name,vector,0F,0F,null,false);
        if(weapon==null)throw new AssertionError("native weapon missing "+name);
        Object parameter=type("com.norwood.mcheli.weapon.MCH_WeaponParam").newInstance();
        VMReflect.set(parameter,"entity",shooter);VMReflect.set(parameter,"user",player);call(parameter,"setPosAndRot",x,y,z,0F,0F);
        java.util.Set<Object> before=java.util.Collections.newSetFromMap(new java.util.IdentityHashMap<Object,Boolean>());before.addAll((List<?>)VMReflect.get(world,"field_72996_f"));
        if(!(Boolean)call(weapon,"shot",parameter))throw new AssertionError("native server weapon shot rejected");
        for(Object entity:(List<?>)VMReflect.get(world,"field_72996_f"))if(!before.contains(entity)&&type("com.norwood.mcheli.weapon.MCH_EntityBaseBullet").isInstance(entity)){if(power>=0)call(entity,"setPower",power);return entity;}
        throw new AssertionError("native server shot created no projectile");
    }
    private static void beginMatrix()throws Exception{
        matrixNotifications=((Number)VMReflect.get(type("com.norwood.mcheli.vm.VMFeedback"),"notifications")).longValue();matrixTick=0;
        if(matrixStage==1){
            matrixTarget=type("net.minecraft.entity.monster.EntityZombie").getConstructor(type("net.minecraft.world.World")).newInstance(world);call(matrixTarget,"func_94061_f",true);call(matrixTarget,"func_70107_b",12.5D,4D,30.5D);call(world,"func_72838_d",matrixTarget);
            String[] slots={"HEAD","CHEST","LEGS","FEET"},items={"diamond_helmet","diamond_chestplate","diamond_leggings","diamond_boots"};
            for(int i=0;i<slots.length;i++){Object item=call(type("net.minecraft.item.Item"),"func_111206_d","minecraft:"+items[i]);Object stack=type("net.minecraft.item.ItemStack").getConstructor(type("net.minecraft.item.Item")).newInstance(item);call(matrixTarget,"func_184201_a",VMReflect.get(type("net.minecraft.inventory.EntityEquipmentSlot"),slots[i]),stack);}
            matrixBefore=health(matrixTarget);matrixBullet=nativeShot("mg7_62mm",12.5D,4.8D,25D,1);
        }else if(matrixStage==2){
            matrixTarget=tank(12.5,30.5);matrixBefore=health(matrixTarget);
            matrixBullet=type("techguns.entities.projectiles.GenericProjectile").getConstructor(type("net.minecraft.world.World")).newInstance(world);VMReflect.set(matrixBullet,"shooter",player);VMReflect.set(matrixBullet,"damage",8F);VMReflect.set(matrixBullet,"damageMin",8F);VMReflect.set(matrixBullet,"damageDropStart",100F);VMReflect.set(matrixBullet,"damageDropEnd",200F);VMReflect.set(matrixBullet,"ticksToLive",20);VMReflect.set(matrixBullet,"speed",20F);call(matrixBullet,"func_70107_b",12.5D,5D,20D);VMReflect.set(matrixBullet,"field_70179_y",20D);call(world,"func_72838_d",matrixBullet);
        }else if(matrixStage==3){matrixTarget=null;matrixBefore=-1;matrixBullet=nativeShot("mg7_62mm",2.5D,8D,25D,1);
        }else if(matrixStage==4){matrixTarget=tank(12.5,30.5);call(matrixTarget,"setDamageTaken",number(call(matrixTarget,"getMaxHP"))-1);matrixBefore=health(matrixTarget);if(matrixBefore!=1)throw new AssertionError("wounded tank fixture HP mismatch");matrixBullet=nativeShot("105mm",12.5D,5D,20D,-1);
        }else throw new AssertionError("unknown matrix stage");
    }
    private static void finishMatrixStage()throws Exception{
        Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("stage",matrixStage);value.put("name",new String[]{"fractional-living","armour-no-damage","miss","destroyed"}[matrixStage-1]);value.put("healthBefore",matrixBefore);value.put("healthAfter",matrixTarget==null?-1:health(matrixTarget));value.put("notifications",((Number)VMReflect.get(type("com.norwood.mcheli.vm.VMFeedback"),"notifications")).longValue()-matrixNotifications);value.put("projectileDead",VMReflect.get(matrixBullet,"field_70128_L"));value.put("targetDead",matrixTarget!=null&&(Boolean)VMReflect.get(matrixTarget,"field_70128_L"));value.put("targetDestroyed",matrixTarget!=null&&matrixTarget.getClass().getName().contains("Tank")&&(Boolean)call(matrixTarget,"isDestroyed"));matrix.add(value);
        call(matrixBullet,"func_70106_y");if(matrixTarget!=null)call(matrixTarget,"func_70106_y");
        Map<String,Object> data=new LinkedHashMap<String,Object>();data.put("cases",matrix);data.put("attempts",feedbackAttempts);write("feedback-matrix-progress.json",data);
        if(matrixStage==4){write("feedback-matrix-server.json",data);matrixStage=0;System.out.println("[RV feedback matrix] server complete");}else{matrixStage++;beginMatrix();}
    }
    @SubscribeEvent public void serverTick(TickEvent.ServerTickEvent event){
        if(shooter==null||finished)return;
        try{
            if(event.phase==TickEvent.Phase.START){tickStart=System.nanoTime();return;}
            if(tickStart!=0)tickTimes.add(System.nanoTime()-tickStart);
            if(matrixStage>0&&++matrixTick>=25)finishMatrixStage();
        }catch(Throwable e){fail(e);}
    }
    private static int countParticles(Object value,Class<?> particle){
        if(value==null)return 0;if(particle.isInstance(value))return 1;
        int sum=0;if(value.getClass().isArray()){for(int i=0;i<Array.getLength(value);i++)sum+=countParticles(Array.get(value,i),particle);}
        else if(value instanceof Collection)for(Object item:(Collection<?>)value)sum+=countParticles(item,particle);
        return sum;
    }
    private static int particles(Object minecraft)throws Exception{
        Object manager=VMReflect.get(minecraft,"field_71452_i");Class<?> particle=type("net.minecraft.client.particle.Particle");int count=0;
        for(Field field:manager.getClass().getDeclaredFields()){field.setAccessible(true);if(!java.lang.reflect.Modifier.isStatic(field.getModifiers()))count+=countParticles(field.get(manager),particle);}
        return count;
    }
    private static void workload(Object mc,Object aircraft,double distance)throws Exception{
        Object clientWorld=VMReflect.get(mc,"field_71441_e");Object localPlayer=VMReflect.get(mc,"field_71439_g");
        Object bullet=type("com.norwood.mcheli.weapon.MCH_EntityBullet").getConstructor(type("net.minecraft.world.World")).newInstance(clientWorld);call(bullet,"setName","105mm");
        double x=num(localPlayer,"field_70165_t")+distance,y=num(localPlayer,"field_70163_u")+1,z=num(localPlayer,"field_70161_v");
        call(bullet,"func_70107_b",x,y,z);VMReflect.set(bullet,"field_70169_q",x-4);VMReflect.set(bullet,"field_70167_r",y);VMReflect.set(bullet,"field_70166_s",z);
        int before=particles(mc);long start=System.nanoTime();for(int i=0;i<100;i++)VMCombat.trail(bullet);long end=System.nanoTime();int after=particles(mc);
        Map<String,Object> sample=new LinkedHashMap<String,Object>();sample.put("distance",distance);sample.put("calls",100);sample.put("particleAdds",after-before);sample.put("nanos",end-start);sample.put("budgetWindows",end/50000000L-start/50000000L+1);samples.add(sample);
    }
    private static void capture(Object mc,String filename)throws Exception{
        Class<?> helper=type("net.minecraft.util.ScreenShotHelper");Object framebuffer=call(mc,"func_147110_a");
        for(java.lang.reflect.Method method:helper.getMethods())if(java.lang.reflect.Modifier.isStatic(method.getModifiers())&&method.getParameterTypes().length==5&&method.getParameterTypes()[0]==File.class&&method.getParameterTypes()[1]==String.class){method.invoke(null,new File("."),filename,number(VMReflect.get(mc,"field_71443_c")),number(VMReflect.get(mc,"field_71440_d")),framebuffer);return;}
        throw new NoSuchMethodException("native screenshot helper");
    }
    private static void feedback(Object mc,Object aircraft)throws Exception{
        Class<?> client;try{client=type("com.norwood.mcheli.vm.VMClient");}catch(ClassNotFoundException absent){return;}
        long count=((Number)VMReflect.get(client,"hitsReceived")).longValue();
        if(count!=feedbackCount){feedbackCount=count;Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("count",count);value.put("code",VMReflect.get(client,"lastHitCode"));value.put("damageTenths",VMReflect.get(client,"lastDamage"));value.put("label",call(client,"hitLabel"));value.put("clientTick",ticks);feedback.add(value);if(screenshotTick==0){workload(mc,aircraft,4D);screenshotTick=ticks+5;}}
        if(screenshotTick>0&&ticks==screenshotTick){capture(mc,"tank-hit.png");result.put("hitScreenshot","screenshots/tank-hit.png");}
    }
    private static void controlSample(Object mc,Object who,String name)throws Exception{
        Map<String,Object> data=new LinkedHashMap<String,Object>();Object weapon=call(keyAircraft,"getCurrentWeapon",who),gui=VMReflect.get(mc,"field_71462_r");data.put("name",name);data.put("tick",keyTicks);data.put("gunnerStatus",call(keyAircraft,"getGunnerStatus"));data.put("gunnerMode",call(keyAircraft,"getIsGunnerMode",who));data.put("cameraZoom",call(VMReflect.get(keyAircraft,"camera"),"getCameraZoom"));data.put("weapon",call(weapon,"getName"));data.put("ammo",call(weapon,"getAmmo"));data.put("reloadCooldown",call(weapon,"getReloadCooldown"));data.put("gui",gui==null?"none":gui.getClass().getName());data.put("mounted",call(who,"func_184187_bx")!=null);controlSamples.add(data);
    }
    private static void nativeKeys(Object mc,Object who,Object aircraft)throws Exception{
        if(keyTicks>=125)return;if(keyTicks==0){keysActive=true;keyAircraft=aircraft;if(keyAircraft==null)throw new AssertionError("native control aircraft absent");controlSample(mc,who,"before");}
        keyTicks++;virtualDown.clear();
        if(keyTicks==1||keyTicks==2){virtualDown.add(29);virtualDown.add(46);}
        if(keyTicks==6||keyTicks==7)virtualDown.add(44);
        if(keyTicks==11||keyTicks==12)virtualDown.add(35);
        if(keyTicks==16||keyTicks==17)virtualDown.add(44);
        if(keyTicks==21||keyTicks==22)virtualDown.add(34);
        if(keyTicks==26||keyTicks==27)virtualDown.add(23);
        if(keyTicks==86||keyTicks==87)virtualDown.add(19);
        if(keyTicks==106||keyTicks==107)virtualDown.add(21);
        if(keyTicks==5)controlSample(mc,who,"after-ctrl-c");if(keyTicks==10)controlSample(mc,who,"after-z-with-status");if(keyTicks==15)controlSample(mc,who,"after-h");if(keyTicks==20)controlSample(mc,who,"after-z-with-gunner");if(keyTicks==25)controlSample(mc,who,"after-g");if(keyTicks==75)controlSample(mc,who,"after-i");
        if(keyTicks==76){call(who,"func_71053_j");call(mc,"func_147108_a",(Object)null);}
        if(keyTicks==95)controlSample(mc,who,"after-r");if(keyTicks==120)controlSample(mc,who,"after-y");
        if(keyTicks==125){keysActive=false;Map<String,Object> data=new LinkedHashMap<String,Object>();data.put("states",controlSamples);data.put("externalKeyboardBoundary",true);data.put("nativePacketAndGUI",true);write("native-controls-client.json",data);}
    }
    @SubscribeEvent public void clientTick(TickEvent.ClientTickEvent event){
        if(event.phase!=TickEvent.Phase.START||!Boolean.getBoolean("rv.tank.input.qa"))return;
        try{
            Object mc=call(type("net.minecraft.client.Minecraft"),"func_71410_x"),localPlayer=VMReflect.get(mc,"field_71439_g");if(localPlayer==null)return;
            Object aircraft=call(type("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",localPlayer);
            if(finished&&Boolean.getBoolean("rv.qa.native.keys")){nativeKeys(mc,localPlayer,aircraft);return;}
            if(aircraft==null||!aircraft.getClass().getName().contains("Tank"))return;
            if(finished){long before=feedbackCount;ticks++;feedback(mc,aircraft);if(before!=feedbackCount){Map<String,Object> data=new LinkedHashMap<String,Object>();data.put("events",feedback);write("feedback-matrix-client.json",data);}return;}
            if(!active){active=true;Object attack=VMReflect.get(VMReflect.get(mc,"field_71474_y"),"field_74312_F");attackKey=number(call(attack,"func_151463_i"));VMController.INSTANCE.profile.setProperty("enabled","false");}
            ticks++;
            feedback(mc,aircraft);
            Object weapon=call(aircraft,"getCurrentWeapon",localPlayer);
            if(fireTick==0&&ticks>=45&&(Boolean)call(weapon,"canFire")&&!(Boolean)call(aircraft,"isPilotReloading")&&!"none".equals(call(weapon,"getName")))fireTick=ticks;
            if(ticks>500&&fireTick==0)throw new AssertionError("native client weapon never became ready");
            pressed=fireTick>0&&ticks>=fireTick&&ticks<fireTick+2;
            if(fireTick>0&&ticks>=fireTick+45&&ticks<fireTick+65)workload(mc,aircraft,ticks%2==0?4D:128D);
            if(fireTick>0&&ticks==fireTick+70){
                pressed=false;result.put("configuredAttackKey",attackKey);result.put("nativeTankFireKey",nativeFireKey);result.put("nativeBindings",nativeBindings);result.put("feedbackEvents",feedback);result.put("fireAtClientTick",fireTick);result.put("clientTicks",ticks);result.put("profile",System.getProperty("rv.qa.profile","balanced"));result.put("effectSamples",samples);result.put("inputEdge","MCH_Key LWJGL key/button reader");result.put("maxHeapBytes",Runtime.getRuntime().maxMemory());result.put("allocatedHeapBytes",Runtime.getRuntime().totalMemory());result.put("usedHeapBytes",Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory());write("tank-input-client.json",result);
                System.out.println("[RV tank input] client complete");finished=true;active=false;
            }
        }catch(Throwable e){fail(e);}
    }
}
