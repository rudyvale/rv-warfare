import com.norwood.mcheli.vm.*;
import java.nio.file.*;
import org.lwjgl.input.Keyboard;
import org.lwjgl.input.Mouse;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;

public final class VMControlsClientRuntime {
    private static boolean done;
    private static int frames;
    private static int captureFrames;
    private static Object galleryCamera;
    private static int galleryShot,galleryFrames;
    private static final double[][] cameras={{-.45,1.0,.45,-135,50},{9.0,1.5,2.3,138,20},{16.15,1.55,2.4,138,20},{6.8,4.8,14,170,15}};
    private static final String[] photoNames={"fpv-quadcopter.png","geran.png","fp1.png","battlefield.png"};
    private static boolean wingRegistered,wingActive;
    private static Object wingAircraft;
    private static String wingType;
    private static int wingTicks;
    private static final java.util.Set<Integer> wingKeys=new java.util.HashSet<Integer>();
    private static final java.util.List<java.util.Map<String,Object>> wingSamples=new java.util.ArrayList<java.util.Map<String,Object>>();
    private static boolean guideDone;
    private static void apacheAudio(){
        try{
            Object mc=VMClient.minecraft();if(VMReflect.get(mc,"field_71439_g")==null)return;
            Object event=VMReflect.get(Class.forName("techguns.TGSounds"),"HELICOPTER_BURST"),name=VMReflect.call(event,"getRegistryName"),handler=VMReflect.call(mc,"func_147118_V"),accessor=null,sound=null;
            for(java.lang.reflect.Method method:handler.getClass().getMethods())if(method.getParameterTypes().length==1&&method.getParameterTypes()[0].getName().equals("net.minecraft.util.ResourceLocation")&&method.getReturnType().getName().equals("net.minecraft.client.audio.SoundEventAccessor")){accessor=method.invoke(handler,name);break;}
            if(accessor==null)throw new AssertionError("Missing native Apache sound accessor");
            for(java.lang.reflect.Method method:accessor.getClass().getMethods())if(method.getParameterTypes().length==0&&method.getReturnType().getName().equals("net.minecraft.client.audio.Sound")){sound=method.invoke(accessor);break;}
            if(sound==null)throw new AssertionError("Missing native Apache resolved sound");
            String actual=null;for(java.lang.reflect.Method method:sound.getClass().getMethods())if(method.getParameterTypes().length==0&&method.getReturnType().getName().equals("net.minecraft.util.ResourceLocation")){String value=String.valueOf(method.invoke(sound));if(value.equals("techguns:npcs/rv_apache_burst")){actual=value;break;}}
            if(actual==null)throw new AssertionError("Wrong native Apache audio "+sound);
            java.util.Map<String,Object> report=new java.util.LinkedHashMap<String,Object>();report.put("success",true);report.put("nativeEvent",String.valueOf(name));report.put("nativeResource",actual);Files.write(Paths.get("native-apache-audio.json"),new com.google.gson.Gson().toJson(report).getBytes("UTF-8"));done=true;System.out.println("[VM apache audio] COMPLETE "+name+" -> "+actual);
        }catch(Throwable e){done=true;System.out.println("[VM apache audio] FAILED");e.printStackTrace();}
    }
    private static void guide()throws Exception{
        if(guideDone||!Boolean.getBoolean("rv.guide.check"))return;
        Object font=VMReflect.get(VMClient.minecraft(),"field_71466_p");com.google.gson.JsonParser parser=new com.google.gson.JsonParser();java.util.List<java.util.Map<String,Object>> results=new java.util.ArrayList<java.util.Map<String,Object>>();
        for(String locale:new String[]{"en","ru"}){
            Path path=Paths.get("qa-book-"+locale+".json");if(!Files.exists(path))throw new AssertionError("Missing final guide "+locale);
            com.google.gson.JsonArray pages=parser.parse(new String(Files.readAllBytes(path),"UTF-8")).getAsJsonArray();if(pages.size()!=24)throw new AssertionError("Final guide must have 24 pages "+locale);int pageNumber=0;
            for(com.google.gson.JsonElement page:pages){pageNumber++;String text=parser.parse(page.getAsString()).getAsJsonObject().get("text").getAsString();java.util.List<?> wrapped=(java.util.List<?>)VMReflect.call(font,"func_78271_c",text,114);int maxWidth=0;for(Object line:wrapped)maxWidth=Math.max(maxWidth,((Number)VMReflect.call(font,"func_78256_a",String.valueOf(line))).intValue());check(wrapped.size()<=14&&maxWidth<=114,"actual book font "+locale+" page="+pageNumber+" lines="+wrapped.size()+" maxWidth="+maxWidth);java.util.Map<String,Object> result=new java.util.LinkedHashMap<String,Object>();result.put("locale",locale);result.put("page",pageNumber);result.put("lines",wrapped.size());result.put("maxWidth",maxWidth);results.add(result);}
        }
        java.util.Map<String,Object> report=new java.util.LinkedHashMap<String,Object>();report.put("success",true);report.put("pages",results);Files.write(Paths.get("native-guide-fonts.json"),new com.google.gson.Gson().toJson(report).getBytes("UTF-8"));guideDone=true;
    }
    private static void visualConfig()throws Exception{
        if(!(Boolean)VMReflect.call(Class.forName("net.minecraftforge.fml.common.Loader"),"isModLoaded","enhancedvisuals"))return;
        java.util.Map<String,Object> values=new java.util.LinkedHashMap<String,Object>();Class<?> handlers=Class.forName("team.creative.enhancedvisuals.common.handler.VisualHandlers");
        for(String name:new String[]{"EXPLOSION","SPLASH","HEARTBEAT"}){Object handler=VMReflect.get(handlers,name);values.put(name.toLowerCase()+".blur.disabled",VMReflect.get(VMReflect.get(handler,"blur"),"disabled"));}
        values.put("explosion.dust.disabled",VMReflect.get(VMReflect.get(VMReflect.get(handlers,"EXPLOSION"),"dust"),"disabled"));values.put("damage.opacity",VMReflect.get(VMReflect.get(handlers,"DAMAGE"),"opacity"));values.put("heartbeat.lowhealth.opacity",VMReflect.get(VMReflect.get(VMReflect.get(handlers,"HEARTBEAT"),"lowhealth"),"opacity"));
        String mode=System.getProperty("rv.effects.profile","balanced");boolean low=mode.equals("low");for(String name:new String[]{"explosion.blur.disabled","splash.blur.disabled","heartbeat.blur.disabled"})if(!Boolean.TRUE.equals(values.get(name)))throw new AssertionError("native blur setting "+name);
        if(!Boolean.valueOf(low).equals(values.get("explosion.dust.disabled"))||Math.abs(VMReflect.num(values.get("damage.opacity"))-(low?.2:.35))>.001||Math.abs(VMReflect.num(values.get("heartbeat.lowhealth.opacity"))-(low?.2:.25))>.001)throw new AssertionError("native effects profile "+values);
        Files.write(Paths.get("native-effects.json"),new com.google.gson.Gson().toJson(values).getBytes("UTF-8"));System.out.println("[VM effects] PASS native loaded "+mode+" "+values);
    }
    public static boolean wingKeyDown(int key){return wingActive?wingKeys.contains(key):Keyboard.isKeyDown(key);}
    public static boolean wingMouseDown(int button){return wingActive?false:Mouse.isButtonDown(button);}
    public static void wingMouse(Object handler){if(!wingActive)return;try{double dy=wingTicks>=70&&wingTicks<140?-1.5D:0D;VMReflect.set(handler,"mouseDeltaX",0D);VMReflect.set(handler,"mouseDeltaY",dy);VMReflect.set(handler,"prevMouseDeltaX",0D);VMReflect.set(handler,"prevMouseDeltaY",dy);VMReflect.set(handler,"mouseRollDeltaY",dy);}catch(Throwable e){e.printStackTrace();}}
    @SubscribeEvent public void clientTick(TickEvent.ClientTickEvent event){
        if(event.phase!=TickEvent.Phase.END||!Boolean.getBoolean("rv.wing.input"))return;
        try{
            Object mc=VMClient.minecraft(),player=VMReflect.get(mc,"field_71439_g");if(player==null)return;Object aircraft=VMReflect.call(Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",player);
            if(aircraft!=null&&VMFlight.wing(aircraft)&&aircraft!=wingAircraft){wingAircraft=aircraft;wingType=String.valueOf(VMReflect.call(aircraft,"getTypeName"));wingTicks=0;wingSamples.clear();wingActive=true;VMController.INSTANCE.profile.setProperty("enabled","false");VMReflect.call(mc,"func_71381_h");}
            if(!wingActive)return;wingTicks++;wingKeys.clear();Object handler=VMReflect.get(VMClient.class,"handler");if(handler!=null){String key=wingTicks<175?"KeyUp":wingTicks<195?"KeyDown":wingTicks<205?"KeyUnmount":null;if(key!=null)wingKeys.add(((Number)VMReflect.get(VMReflect.get(handler,key),"key")).intValue());String turn=wingTicks>=110&&wingTicks<135?"KeyLeft":wingTicks>=145&&wingTicks<170?"KeyRight":null;if(turn!=null)wingKeys.add(((Number)VMReflect.get(VMReflect.get(handler,turn),"key")).intValue());}
            if(wingTicks%5==0){java.util.Map<String,Object> sample=new java.util.LinkedHashMap<String,Object>();sample.put("tick",wingTicks);sample.put("controlled",aircraft==wingAircraft);sample.put("dead",VMReflect.get(wingAircraft,"field_70128_L"));sample.put("throttle",VMReflect.call(wingAircraft,"getCurrentThrottle"));sample.put("pitch",VMReflect.call(wingAircraft,"getPitch"));sample.put("roll",VMReflect.call(wingAircraft,"getRoll"));sample.put("yaw",VMReflect.call(wingAircraft,"getYaw"));sample.put("heldKeys",new java.util.ArrayList<Integer>(wingKeys));sample.put("focus",VMReflect.get(mc,"field_71415_G"));sample.put("active",org.lwjgl.opengl.Display.isActive());Object screen=VMReflect.get(mc,"field_71462_r");sample.put("screen",screen==null?null:screen.getClass().getName());sample.put("fuel",VMReflect.call(wingAircraft,"getFuel"));sample.put("handler",handler==null?null:handler.getClass().getName());wingSamples.add(sample);}
            if(wingTicks==300){wingActive=false;wingKeys.clear();java.util.Map<String,Object> data=new java.util.LinkedHashMap<String,Object>();data.put("type",wingType);data.put("physicalDevice",false);data.put("samples",wingSamples);Files.write(Paths.get("wing-launch-client-"+wingType+".json"),new com.google.gson.Gson().toJson(data).getBytes("UTF-8"));System.out.println("[VM wing input] COMPLETE "+wingType);}
        }catch(Throwable e){wingActive=false;wingKeys.clear();System.out.println("[VM wing input] FAILED client");e.printStackTrace();}
    }
    private static void gallery(){
        try{
            Object mc=VMClient.minecraft(),player=VMReflect.get(mc,"field_71439_g"),world=VMReflect.get(mc,"field_71441_e");if(player==null||world==null)return;
            if(galleryCamera==null){
                int count=0;for(Object entity:(java.util.List<?>)VMReflect.get(world,"field_72996_f"))if(VMFlight.uav(entity))count++;if(count<4)return;
                galleryCamera=Class.forName("net.minecraft.entity.item.EntityArmorStand").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);
                VMReflect.call(galleryCamera,"func_82142_c",true);
                guide();
                visualConfig();
                VMReflect.set(VMReflect.get(mc,"field_71474_y"),"field_74319_N",true);VMReflect.set(VMReflect.get(mc,"field_71474_y"),"field_74334_X",55F);VMReflect.call(mc,"func_175607_a",galleryCamera);
            }
            if(galleryShot>=cameras.length)return;
            String[] origin=System.getProperty("rv.gallery.origin","0,4,0").split(",");double[] c=cameras[galleryShot];double x=Double.parseDouble(origin[0])+c[0],y=Double.parseDouble(origin[1])+c[1]-VMReflect.num(VMReflect.call(galleryCamera,"func_70047_e")),z=Double.parseDouble(origin[2])+c[2];
            VMReflect.call(galleryCamera,"func_70107_b",x,y,z);VMReflect.set(galleryCamera,"field_70142_S",x);VMReflect.set(galleryCamera,"field_70137_T",y);VMReflect.set(galleryCamera,"field_70136_U",z);VMReflect.set(galleryCamera,"field_70169_q",x);VMReflect.set(galleryCamera,"field_70167_r",y);VMReflect.set(galleryCamera,"field_70166_s",z);VMReflect.set(galleryCamera,"field_70177_z",(float)c[3]);VMReflect.set(galleryCamera,"field_70126_B",(float)c[3]);VMReflect.set(galleryCamera,"field_70125_A",(float)c[4]);VMReflect.set(galleryCamera,"field_70127_C",(float)c[4]);
            if(++galleryFrames<100)return;galleryFrames=0;
            Class<?> shaders=Class.forName("net.optifine.shaders.Shaders");boolean loaded=(Boolean)VMReflect.get(shaders,"shaderPackLoaded"),initialized=(Boolean)VMReflect.get(shaders,"isShaderPackInitialized");String shader=String.valueOf(VMReflect.call(shaders,"getShaderPackName"));
            if(Boolean.getBoolean("rv.gallery.shaders")&&(!loaded||!initialized))throw new AssertionError("shader requested but not active");
            int width=((Number)VMReflect.get(mc,"field_71443_c")).intValue(),height=((Number)VMReflect.get(mc,"field_71440_d")).intValue();
            VMReflect.call(Class.forName("net.minecraft.util.ScreenShotHelper"),"func_148259_a",new java.io.File("."),photoNames[galleryShot],width,height,VMReflect.call(mc,"func_147110_a"));
            Files.write(Paths.get("screenshots",photoNames[galleryShot]+".json"),("{\"width\":"+width+",\"height\":"+height+",\"shader\":\""+shader+"\",\"shaderLoaded\":"+loaded+",\"shaderInitialized\":"+initialized+",\"camera\":"+java.util.Arrays.toString(c)+",\"origin\":\""+System.getProperty("rv.gallery.origin","0,4,0")+"\"}").getBytes("UTF-8"));
            System.out.println("[VM gallery] CAPTURED "+photoNames[galleryShot]+" "+width+"x"+height+" shader="+shader);galleryShot++;
            if(galleryShot==cameras.length)System.out.println("[VM gallery] COMPLETE");
        }catch(Throwable e){galleryShot=cameras.length;System.out.println("[VM gallery] FAILED");e.printStackTrace();}
    }
    private static void check(boolean result,String label){if(!result)throw new AssertionError(label);System.out.println("[VM client integration] PASS "+label);}
    public static void frame(){
        if(Boolean.getBoolean("rv.apache.audio")){if(!done)apacheAudio();return;}
        if(!Boolean.getBoolean("vm.controls.integration"))return;
        if(Boolean.getBoolean("rv.wing.input")){if(!wingRegistered){wingRegistered=true;MinecraftForge.EVENT_BUS.register(new VMControlsClientRuntime());}return;}
        if(Boolean.getBoolean("rv.gallery.capture")){gallery();return;}
        if(done){
            if(++captureFrames==20)try{
                Object mc=VMClient.minecraft();
                VMReflect.call(Class.forName("net.minecraft.util.ScreenShotHelper"),"func_148260_a",new java.io.File("."),((Number)VMReflect.get(mc,"field_71443_c")).intValue(),((Number)VMReflect.get(mc,"field_71440_d")).intValue(),VMReflect.call(mc,"func_147110_a"));
                System.out.println("[VM client integration] COMPLETE");
            }catch(Throwable e){System.out.println("[VM client integration] FAILED screenshot");e.printStackTrace();}
            return;
        }
        try {
            Object mc=VMReflect.call(Class.forName("net.minecraft.client.Minecraft"),"func_71410_x");Object player=VMReflect.get(mc,"field_71439_g");
            if(player==null)return;
            Object aircraft=VMReflect.call(Class.forName("com.norwood.mcheli.aircraft.MCH_EntityAircraft"),"getAircraft_RiddenOrControl",player);
            if(aircraft==null || !VMFlight.drone(aircraft) || !(Boolean)VMReflect.call(aircraft,"isPilot",player))return;
            if(++frames<30)return;done=true;
            Object world=VMReflect.get(player,"field_70170_p");
            visualConfig();
            if((Boolean)VMReflect.call(Class.forName("net.minecraftforge.fml.common.Loader"),"isModLoaded","enhancedvisuals")){check(VMComfort.clearView(),"native controlled vehicle keeps clear EnhancedVisuals view");VMReflect.call(Class.forName("team.creative.enhancedvisuals.client.render.EVRenderer"),"render",(Object)null);check(true,"actual EnhancedVisuals render guard preserves vehicle HUD");}
            for(String type:new String[]{"rc-goblin","rc-goblin-bomb","rv_geran","rv_fp1"}){
                Object model=VMReflect.call(Class.forName("com.norwood.mcheli.MCH_ModelManager"),"load",type.startsWith("rv_")?"planes":"helicopters",type);
                check(model!=null,"actual native MQO loaded "+type);
                if(type.startsWith("rv_")){
                    Object wing=Class.forName("com.norwood.mcheli.plane.MCH_EntityPlane").getConstructor(Class.forName("net.minecraft.world.World")).newInstance(world);VMReflect.call(wing,"setTypeName",type);
                    check(!VMPilot.angles(wing,player,false,0F,0F,0F,0F,0F,0F,.05F),"fixed wing preserves native attitude controls "+type);
                }
            }
            VMController.INSTANCE.profile.setProperty("enabled","false");VMController.INSTANCE.profile.setProperty("keyboardFlight","advanced");VMController.INSTANCE.profile.setProperty("flight","angle");
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
            VMReflect.call(aircraft,"setCurrentThrottle",0D);check(VMReflect.num(VMReflect.call(aircraft,"getSoundVolume"))==0,"actual FPV motor silent at zero throttle");
            double lowPitch=VMReflect.num(VMReflect.call(aircraft,"getSoundPitch"));VMReflect.call(aircraft,"setCurrentThrottle",1D);
            check(VMReflect.num(VMReflect.call(aircraft,"getSoundVolume"))<=.761,"actual FPV motor volume capped");
            check(lowPitch>=.719&&VMReflect.num(VMReflect.call(aircraft,"getSoundPitch"))>lowPitch+.6,"actual FPV motor pitch follows throttle");VMReflect.call(aircraft,"setCurrentThrottle",0D);
            Object activeHandler=VMReflect.get(VMClient.class,"handler");check(activeHandler!=null,"native vehicle handler captured for HUD");
            Object attack=VMReflect.get(VMReflect.get(mc,"field_71474_y"),"field_74312_F");int oldKey=((Number)VMReflect.call(attack,"func_151463_i")).intValue();VMReflect.call(attack,"func_151462_b",33);
            VMClient.bindings(activeHandler);check(VMClient.key(activeHandler,"KeyUseWeapon").equals("F"),"actual remapped attack reflected by vehicle key/HUD");VMReflect.call(attack,"func_151462_b",oldKey);VMClient.bindings(activeHandler);
            String[] hints=VMClient.hints(aircraft,player);check(hints.length==3&&hints[2].contains("FPV"),"actual FPV HUD contains mode/throttle and controller entry");
            Files.write(Paths.get("config/rv-client.properties"),"profile=low\nlanguage=en\nhudHints=true\nhitFeedback=true\n".getBytes("UTF-8"));VMReflect.set(VMClient.class,"nextLoad",0L);VMReflect.set(VMClient.class,"stamp",-2L);VMClient.reload();
            check(VMClient.effectLimit==40&&VMClient.trailSteps==2&&VMClient.effectRange==48,"Low client effect contract applied");
            double ax=VMReflect.num(VMReflect.get(aircraft,"field_70165_t")),ay=VMReflect.num(VMReflect.get(aircraft,"field_70163_u")),az=VMReflect.num(VMReflect.get(aircraft,"field_70161_v"));
            VMReflect.call(bullet,"func_70107_b",ax+1,ay,az);VMReflect.set(bullet,"field_70169_q",ax);VMReflect.set(bullet,"field_70167_r",ay);VMReflect.set(bullet,"field_70166_s",az);
            long drawn=VMClient.particlesDrawn;VMCombat.trail(bullet);check(VMClient.particlesDrawn-drawn<=2,"Low actual near tracer limited to two particles");
            VMReflect.call(bullet,"func_70107_b",ax+1001,ay,az);VMReflect.set(bullet,"field_70169_q",ax+1000);drawn=VMClient.particlesDrawn;VMCombat.trail(bullet);check(VMClient.particlesDrawn==drawn,"actual distant tracer produces no local particles");
            guide();
            VMController.INSTANCE.profile.setProperty("flight","angle");VMReflect.call(aircraft,"setRotYaw",0F);VMReflect.call(aircraft,"setRotPitch",0F);VMReflect.call(aircraft,"setRotRoll",0F);VMReflect.call(aircraft,"resyncOrientationFromEuler");
            Files.write(Paths.get("client-check.txt"),"PASS actual client controls, camera orientation, sound and particles".getBytes("UTF-8"));
            System.out.println("[VM client integration] waiting for actual rendered FPV screenshot");
        }catch(Throwable e){done=true;System.out.println("[VM client integration] FAILED");e.printStackTrace();}
    }
}
