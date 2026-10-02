import com.google.gson.Gson;
import com.norwood.mcheli.vm.VMReflect;
import java.io.File;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;

public final class RVPlayerDamageRuntime {
    private static boolean registered,active,healingSent;
    private static int tick;
    private static Object actor,victim,world,tank,bullet;
    private static Map<String,Object> before;
    private static int guiStep;
    private static Object guiButton;
    private static long guiStarted;
    private static final Map<String,Object> guiProof=new LinkedHashMap<String,Object>();
    private static final Map<String,Object> result=new LinkedHashMap<String,Object>();
    private static final List<Map<String,Object>> packets=new ArrayList<Map<String,Object>>();
    private static final List<Map<String,Object>> healing=new ArrayList<Map<String,Object>>();
    private static final List<Map<String,Object>> impacts=new ArrayList<Map<String,Object>>();
    private static Class<?> type(String name)throws Exception{return Class.forName(name);}
    private static Object call(Object receiver,String name,Object... values)throws Exception{return VMReflect.call(receiver,name,values);}
    private static double number(Object value){return ((Number)value).doubleValue();}
    private static void write(String path,Object value)throws Exception{Files.write(Paths.get(path),new Gson().toJson(value).getBytes("UTF-8"));}
    private static void register(){if(!registered){registered=true;MinecraftForge.EVENT_BUS.register(new RVPlayerDamageRuntime());}}
    private static void fail(Throwable error){active=false;result.put("error",error.toString());try{write("player-health-failed.json",result);}catch(Exception ignored){}error.printStackTrace();}
    public static void frame(){if(Boolean.getBoolean("rv.player.health.qa"))register();}
    private static Object model(Object who)throws Exception{return call(who,"getCapability",VMReflect.get(type("ichttt.mods.firstaid.api.CapabilityExtendedHealthSystem"),"INSTANCE"),(Object)null);}
    private static Map<String,Object> snapshot(Object who)throws Exception{
        Object model=model(who);if(model==null)throw new AssertionError("Actual FirstAid capability absent");
        Map<String,Object> value=new LinkedHashMap<String,Object>(),parts=new LinkedHashMap<String,Object>();double sum=0;
        for(Object part:(Iterable<?>)model){double health=number(VMReflect.get(part,"currentHealth"));sum+=health;Map<String,Object> data=new LinkedHashMap<String,Object>();data.put("health",health);data.put("maxHealth",call(part,"getMaxHealth"));data.put("activeHealer",VMReflect.get(part,"activeHealer")!=null);parts.put(String.valueOf(VMReflect.get(part,"part")),data);}
        value.put("parts",parts);value.put("limbSum",sum);value.put("vanillaHP",call(who,"func_110143_aJ"));value.put("firstAidDead",call(model,"isDead",who));value.put("entityDead",VMReflect.get(who,"field_70128_L"));value.put("modelClass",model.getClass().getName());value.put("x",VMReflect.get(who,"field_70165_t"));value.put("y",VMReflect.get(who,"field_70163_u"));value.put("z",VMReflect.get(who,"field_70161_v"));value.put("bounds",String.valueOf(call(who,"func_174813_aQ")));value.put("invulnerableAbility",VMReflect.get(VMReflect.get(who,"field_71075_bZ"),"field_75102_a"));return value;
    }
    private static Object itemStack(String name,int count)throws Exception{
        Object item=call(type("net.minecraft.item.Item"),"func_111206_d",name);if(item==null)throw new AssertionError("Item registry absent "+name);
        return type("net.minecraft.item.ItemStack").getConstructor(type("net.minecraft.item.Item"),int.class).newInstance(item,count);
    }
    private static Object shot(String name,int power)throws Exception{
        Object vector=type("net.minecraft.util.math.Vec3d").getConstructor(double.class,double.class,double.class).newInstance(8.5D,5.0D,24.5D);
        Object weapon=call(type("com.norwood.mcheli.weapon.MCH_WeaponCreator"),"createWeapon",world,name,vector,0F,0F,null,false);
        if(weapon==null)throw new AssertionError("Native weapon missing "+name);
        Object param=type("com.norwood.mcheli.weapon.MCH_WeaponParam").newInstance();VMReflect.set(param,"entity",tank);VMReflect.set(param,"user",actor);call(param,"setPosAndRot",8.5D,5D,24.5D,0F,0F);
        Set<Object> prior=java.util.Collections.newSetFromMap(new IdentityHashMap<Object,Boolean>());prior.addAll((List<?>)VMReflect.get(world,"field_72996_f"));
        if(!(Boolean)call(weapon,"shot",param))throw new AssertionError("Native shot rejected");
        for(Object entity:(List<?>)VMReflect.get(world,"field_72996_f"))if(!prior.contains(entity)&&type("com.norwood.mcheli.weapon.MCH_EntityBaseBullet").isInstance(entity)){if(power>=0)call(entity,"setPower",power);return entity;}
        throw new AssertionError("Native shot created no projectile");
    }
    public static boolean command(Object server,Object sender,String[] args){
        if(!Boolean.getBoolean("rv.player.health.qa")||server!=sender||args.length!=1||!args[0].equals("rvhealthsetup"))return false;
        try{
            register();Object list=call(server,"func_184103_al");actor=call(list,"func_152612_a","RVDamageQA");victim=call(list,"func_152612_a","RVVictimQA");if(actor==null||victim==null)throw new AssertionError("Both real native clients required");world=VMReflect.get(actor,"field_70170_p");
            for(int x=-2;x<=2;x++)for(int z=-2;z<=3;z++)call(world,"func_72964_e",x,z);
            call(call(server,"func_71187_D"),"func_71556_a",server,"fill 4 4 4 12 20 40 minecraft:air");
            call(VMReflect.get(actor,"field_71135_a"),"func_147364_a",8.5D,4D,10.5D,0F,0F);call(VMReflect.get(victim,"field_71135_a"),"func_147364_a",8.5D,4D,30.5D,0F,0F);
            call(VMReflect.get(victim,"field_71134_c"),"func_73076_a",VMReflect.get(type("net.minecraft.world.GameType"),"SURVIVAL"));
            call(call(victim,"func_71024_bL"),"func_75114_a",10);
            tank=type("com.norwood.mcheli.tank.MCH_EntityTank").getConstructor(type("net.minecraft.world.World")).newInstance(world);call(tank,"setTypeName","m1a2");call(tank,"changeType","m1a2");call(tank,"func_70107_b",8.5D,4D,10.5D);call(world,"func_72838_d",tank);call(tank,"setFuel",call(tank,"getMaxFuel"));if(!(Boolean)call(actor,"func_184205_a",tank,true))throw new AssertionError("Native actor seat rejected");call(tank,"initCurrentWeapon",actor);
            result.put("victimClass",victim.getClass().getName());result.put("fakePlayer",type("net.minecraftforge.common.util.FakePlayer").isInstance(victim));result.put("actorOperator",call(actor,"func_70003_b",2,"time"));result.put("victimOperator",call(victim,"func_70003_b",2,"time"));active=true;tick=0;System.out.println("[RV player health] fixture ready");
        }catch(Throwable error){fail(error);}return true;
    }
    public static void feedback(Object packet){
        if(!Boolean.getBoolean("rv.player.health.qa"))return;
        try{int encoded=((Number)VMReflect.get(packet,"entityID_Ac")).intValue();if(encoded>-2||encoded<-(2+3*1048576-1))return;int code=-encoded-2;Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("code",code/1048576);value.put("damageTenths",code%1048576);packets.add(value);write("player-health-feedback.json",packets);}catch(Throwable error){fail(error);}
    }
    private static void guiEscape(Object gui)throws Exception{for(Class<?> node=gui.getClass();node!=null;node=node.getSuperclass())try{java.lang.reflect.Method method=node.getDeclaredMethod("func_73869_a",char.class,int.class);method.setAccessible(true);method.invoke(gui,'\0',1);return;}catch(NoSuchMethodException ignored){}throw new NoSuchMethodException("Native GUI escape");}
    private static void woundsKey()throws Exception{Object binding=VMReflect.get(type("ichttt.mods.firstaid.client.ClientProxy"),"showWounds");int key=((Number)call(binding,"func_151463_i")).intValue();guiProof.put("woundsKey",key);call(type("net.minecraft.client.settings.KeyBinding"),"func_74507_a",key);Object event=type("net.minecraftforge.fml.common.gameevent.InputEvent$KeyInputEvent").newInstance();MinecraftForge.EVENT_BUS.post((net.minecraftforge.fml.common.eventhandler.Event)event);}
    public static boolean guiMouseDown(int button){return guiStep==3&&button==0;}
    public static int guiX(Object gui,int original)throws Exception{return guiButton==null?original:((Number)VMReflect.get(guiButton,"field_146128_h")).intValue()+10;}
    public static int guiY(Object gui,int original)throws Exception{return guiButton==null?original:((Number)VMReflect.get(guiButton,"field_146129_i")).intValue()+10;}
    public static void guiSend(Object networking,Object packet)throws Exception{
        call(networking,"sendToServer",packet);
        if(packet.getClass().getName().endsWith("MessageApplyHealingItem")){
            Map<String,Object> data=new LinkedHashMap<String,Object>();data.put("nativeMessageClass",packet.getClass().getName());data.put("part",String.valueOf(VMReflect.get(packet,"part")));data.put("hand",String.valueOf(VMReflect.get(packet,"hand")));data.put("heldRegistry","firstaid:bandage");data.put("nativeGUITriggered",true);write("healing-packet-client.json",data);healingSent=true;guiStep=4;guiProof.put("holdMilliseconds",(System.nanoTime()-guiStarted)/1000000L);guiProof.put("actualMessage",data);write("healing-gui-client.json",guiProof);guiButton=null;
        }
    }
    private static void healingGui(Object mc,Object who,Object held,String part)throws Exception{
        Object gui=VMReflect.get(mc,"field_71462_r");
        if(guiStep==0){woundsKey();gui=VMReflect.get(mc,"field_71462_r");guiProof.put("firstWoundsKeyScreen",gui==null?"none":gui.getClass().getName());guiStep=1;return;}
        if(guiStep==1){if(gui!=null&&gui.getClass().getName().endsWith("GuiTutorial")){guiEscape(gui);woundsKey();gui=VMReflect.get(mc,"field_71462_r");}if(gui==null||!gui.getClass().getName().endsWith("GuiHealthScreen"))throw new AssertionError("Actual FirstAid wounds key did not open health screen");guiProof.put("woundsScreen",gui.getClass().getName());guiProof.put("woundsReadOnly",VMReflect.get(gui,"disableButtons"));guiEscape(gui);call(call(held,"func_77973_b"),"func_77659_a",VMReflect.get(who,"field_70170_p"),who,VMReflect.get(type("net.minecraft.util.EnumHand"),"MAIN_HAND"));guiStep=2;return;}
        if(guiStep==2){if(gui==null||!gui.getClass().getName().endsWith("GuiHealthScreen"))throw new AssertionError("Actual bandage right click did not open health screen");guiProof.put("healingScreen",gui.getClass().getName());guiProof.put("healingHand",String.valueOf(VMReflect.get(gui,"activeHand")));for(Object button:(List<?>)call(gui,"getButtons")){int id=((Number)VMReflect.get(button,"field_146127_k")).intValue();if(id>=1&&id<=8&&part.equals(String.valueOf(call(type("ichttt.mods.firstaid.api.enums.EnumPlayerPart"),"fromID",id))))guiButton=button;}if(guiButton==null||!(Boolean)VMReflect.get(guiButton,"field_146124_l"))throw new AssertionError("Actual wounded limb healing button unavailable");guiProof.put("buttonClass",guiButton.getClass().getName());guiProof.put("buttonText",VMReflect.get(guiButton,"field_146126_j"));guiProof.put("selectedPart",part);guiStarted=System.nanoTime();guiStep=3;}
    }
    public static void impact(Object projectile,Object hit){
        if(!Boolean.getBoolean("rv.player.health.qa"))return;
        try{if(VMReflect.remote(projectile))return;Object entity=VMReflect.get(hit,"field_72308_g"),point=VMReflect.get(hit,"field_72307_f");Map<String,Object> value=new LinkedHashMap<String,Object>();value.put("tick",tick);value.put("kind",String.valueOf(VMReflect.get(hit,"field_72313_a")));value.put("entity",entity==null?"none":entity.getClass().getName());value.put("victimIdentity",entity==victim);value.put("power",call(projectile,"getPower"));if(point!=null){value.put("x",VMReflect.get(point,"field_72450_a"));value.put("y",VMReflect.get(point,"field_72448_b"));value.put("z",VMReflect.get(point,"field_72449_c"));}impacts.add(value);result.put("impacts",impacts);}catch(Throwable error){result.put("impactObserverError",error.toString());}
    }
    @SubscribeEvent public void serverTick(TickEvent.ServerTickEvent event){
        if(event.phase!=TickEvent.Phase.END||!active)return;
        try{
            tick++;if(tick<=80)return;int phase=tick-80;
            if(phase==15){before=snapshot(victim);result.put("beforeShot",before);bullet=shot("mg7_62mm",1);}
            if(phase==40){
                Map<String,Object> after=snapshot(victim);result.put("afterShot",after);result.put("weakProjectileStopped",VMReflect.get(bullet,"field_70128_L"));
                Map<String,Object> oldParts=(Map<String,Object>)before.get("parts"),newParts=(Map<String,Object>)after.get("parts");String selected=null;double loss=0;
                for(String name:oldParts.keySet()){double delta=number(((Map<?,?>)oldParts.get(name)).get("health"))-number(((Map<?,?>)newParts.get(name)).get("health"));if(delta>loss){loss=delta;selected=name;}}
                if(selected==null)throw new AssertionError("Native projectile caused no FirstAid limb damage");result.put("healedPart",selected);
                Object hand=VMReflect.get(type("net.minecraft.util.EnumHand"),"MAIN_HAND");call(victim,"func_184611_a",hand,itemStack("firstaid:bandage",3));
                Map<String,Object> request=new LinkedHashMap<String,Object>();request.put("part",selected);write("healing-request.json",request);
            }
            if(phase>40&&phase%20==0){Map<String,Object> sample=snapshot(victim);sample.put("tick",tick);sample.put("bandageCount",call(call(victim,"func_184586_b",VMReflect.get(type("net.minecraft.util.EnumHand"),"MAIN_HAND")),"func_190916_E"));healing.add(sample);}
            if(phase==520){result.put("afterHealing",snapshot(victim));result.put("healingSamples",healing);result.put("bandageCountAfter",call(call(victim,"func_184586_b",VMReflect.get(type("net.minecraft.util.EnumHand"),"MAIN_HAND")),"func_190916_E"));bullet=shot("mg7_62mm",30);}
            if(phase==560){result.put("afterCriticalShot",snapshot(victim));result.put("criticalProjectileStopped",VMReflect.get(bullet,"field_70128_L"));write("player-health-server.json",result);active=false;System.out.println("[RV player health] complete");}
        }catch(Throwable error){fail(error);}
    }
    @SubscribeEvent public void clientTick(TickEvent.ClientTickEvent event){
        if(event.phase!=TickEvent.Phase.END||!Boolean.getBoolean("rv.player.health.qa")||healingSent)return;
        try{
            Object mc=call(type("net.minecraft.client.Minecraft"),"func_71410_x"),who=VMReflect.get(mc,"field_71439_g");if(who==null||!"RVVictimQA".equals(call(who,"func_70005_c_")))return;
            java.nio.file.Path request=Paths.get(System.getProperty("rv.health.server.root"),"healing-request.json");if(!Files.exists(request))return;
            Object held=call(who,"func_184586_b",VMReflect.get(type("net.minecraft.util.EnumHand"),"MAIN_HAND"));if(!"firstaid:bandage".equals(String.valueOf(call(call(held,"func_77973_b"),"getRegistryName"))))return;
            String part=new Gson().fromJson(new String(Files.readAllBytes(request),"UTF-8"),Map.class).get("part").toString();Object selected=Enum.valueOf((Class)type("ichttt.mods.firstaid.api.enums.EnumPlayerPart"),part);
            if(Boolean.getBoolean("rv.health.gui")){healingGui(mc,who,held,part);return;}
            Object packet=type("ichttt.mods.firstaid.common.network.MessageApplyHealingItem").getConstructor(type("ichttt.mods.firstaid.api.enums.EnumPlayerPart"),type("net.minecraft.util.EnumHand")).newInstance(selected,VMReflect.get(type("net.minecraft.util.EnumHand"),"MAIN_HAND"));call(VMReflect.get(type("ichttt.mods.firstaid.FirstAid"),"NETWORKING"),"sendToServer",packet);healingSent=true;Map<String,Object> data=new LinkedHashMap<String,Object>();data.put("nativeMessageClass",packet.getClass().getName());data.put("part",part);data.put("heldRegistry","firstaid:bandage");write("healing-packet-client.json",data);
        }catch(Throwable error){fail(error);}
    }
}
