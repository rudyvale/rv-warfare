import com.norwood.mcheli.vm.VMReflect;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class RVCombatAcceptance {
    private static final List<String> failures = new ArrayList<String>();
    private static final List<Object> entities = new ArrayList<Object>();
    private static final Map<Object,Object> blocks = new LinkedHashMap<Object,Object>();
    private static int checks;
    private static Object server;
    private static Object world;
    private static Object player;

    private static Class<?> type(String name) throws Exception { return Class.forName(name); }
    private static Object call(Object target,String name,Object... args) throws Exception { return VMReflect.call(target,name,args); }
    private static double num(Object target,String field) throws Exception { return VMReflect.num(VMReflect.get(target,field)); }
    private static boolean dead(Object target) throws Exception { return (Boolean)VMReflect.get(target,"field_70128_L"); }
    private static void check(boolean value,String label) {
        checks++;
        System.out.println("[RV combat QA] "+(value?"PASS ":"FAIL ")+label);
        if(!value)failures.add(label);
    }
    private static Object vec(double x,double y,double z) throws Exception {
        return type("net.minecraft.util.math.Vec3d").getConstructor(double.class,double.class,double.class).newInstance(x,y,z);
    }
    private static Object pos(int x,int y,int z) throws Exception {
        return type("net.minecraft.util.math.BlockPos").getConstructor(int.class,int.class,int.class).newInstance(x,y,z);
    }
    private static Object state(String name) throws Exception {
        return call(call(type("net.minecraft.block.Block"),"func_149684_b",name),"func_176223_P");
    }
    private static void block(int x,int y,int z,String name) throws Exception {
        Object at=pos(x,y,z);
        if(!blocks.containsKey(at))blocks.put(at,call(world,"func_180495_p",at));
        call(world,"func_180501_a",at,state(name),3);
    }
    private static String blockName(int x,int y,int z) throws Exception {
        Object value=call(call(world,"func_180495_p",pos(x,y,z)),"func_177230_c");
        return String.valueOf(call(VMReflect.get(type("net.minecraft.block.Block"),"field_149771_c"),"func_177774_c",value));
    }
    private static void advanceBudgetClock() throws Exception {
        long time=((Number)call(world,"func_82737_E")).longValue();
        Object info=call(world,"func_72912_H");
        call(info,"func_82572_b",Long.valueOf(time+1));
        if(((Number)call(world,"func_82737_E")).longValue()!=time+1)throw new IllegalStateException("private QA world-time advance failed");
    }
    private static Object spawn(Object entity,double x,double y,double z) throws Exception {
        call(entity,"func_70107_b",x,y,z);
        call(world,"func_72964_e",(int)Math.floor(x)>>4,(int)Math.floor(z)>>4);
        check((Boolean)call(world,"func_72838_d",entity),"fixture spawned "+entity.getClass().getSimpleName());
        entities.add(entity);
        return entity;
    }
    private static Object tank(double x,double z,float yaw) throws Exception {
        Object value=type("com.norwood.mcheli.tank.MCH_EntityTank").getConstructor(type("net.minecraft.world.World")).newInstance(world);
        call(value,"setTypeName","m1a2");call(value,"setTextureName","m1a2");
        spawn(value,x,80,z);
        call(value,"setRotYaw",yaw);call(value,"setRotPitch",0F);call(value,"setRotRoll",0F);
        call(value,"resyncOrientationFromEuler");call(value,"updateExtraBoundingBox");
        return value;
    }
    private static int hp(Object value) throws Exception { return ((Number)call(value,"getHP")).intValue(); }
    private static Object bullet(String name,double x,double y,double z,float damage) throws Exception {
        Class<?> projectile=type("techguns.entities.projectiles."+name);
        Object value;
        if(name.equals("FlamethrowerProjectile")) {
            Class<?> firePos=type("techguns.entities.projectiles.EnumBulletFirePos");
            value=projectile.getConstructor(type("net.minecraft.world.World"),type("net.minecraft.entity.EntityLivingBase"),float.class,float.class,int.class,float.class,float.class,float.class,float.class,float.class,boolean.class,firePos,double.class)
                .newInstance(world,player,damage,20F,20,0F,100F,200F,damage,1F,true,firePos.getEnumConstants()[0],0D);
        }else value=projectile.getConstructor(type("net.minecraft.world.World")).newInstance(world);
        VMReflect.set(value,"shooter",player);VMReflect.set(value,"damage",damage);VMReflect.set(value,"damageMin",damage);
        VMReflect.set(value,"damageDropStart",100F);VMReflect.set(value,"damageDropEnd",200F);
        VMReflect.set(value,"ticksToLive",20);VMReflect.set(value,"speed",20F);VMReflect.set(value,"blockdamage",true);
        VMReflect.set(value,"field_70179_y",20D);
        return spawn(value,x,y,z);
    }
    private static Object fire(String name,double x,double y,double z,float damage) throws Exception {
        Object shot=bullet(name,x,y,z,damage);
        call(shot,"func_70071_h_");
        return shot;
    }
    private static Object plainBox(Object bounds) throws Exception {
        return type("net.minecraft.util.math.AxisAlignedBB").getConstructor(double.class,double.class,double.class,double.class,double.class,double.class)
            .newInstance(num(bounds,"field_72340_a"),num(bounds,"field_72338_b"),num(bounds,"field_72339_c"),num(bounds,"field_72336_d"),num(bounds,"field_72337_e"),num(bounds,"field_72334_f"));
    }
    private static double[] extraRay(Object target) throws Exception {
        return extraRay(target,-1);
    }
    private static double[] extraRay(Object target,int part) throws Exception {
        Object primary=call(plainBox(call(target,"func_174813_aQ")),"func_72314_b",.31D,.31D,.31D);
        double tx=num(target,"field_70165_t"),tz=num(target,"field_70161_v");
        Object[] extras=(Object[])VMReflect.get(target,"extraBoundingBox");
        for(int index=0;index<extras.length;index++) {
            if(part>=0 && index!=part)continue;
            Object extra=extras[index];
            Object box=call(extra,"getBoundingBox");
            double cx=(num(box,"field_72340_a")+num(box,"field_72336_d"))/2;
            double cy=part<0?(num(box,"field_72338_b")+num(box,"field_72337_e"))/2:num(box,"field_72337_e")-.1;
            for(double rx:new double[]{cx,num(box,"field_72340_a")+.25,num(box,"field_72336_d")-.25}) {
                Object from=vec(rx,cy,tz-10),to=vec(rx,cy,tz+10);
                if(call(primary,"func_72327_a",from,to)==null && call(call(target,"func_174813_aQ"),"func_72327_a",from,to)!=null)
                    return new double[]{rx,cy,tz-10};
            }
        }
        throw new IllegalStateException("No ray outside primary tank bounds at "+tx+","+tz);
    }
    private static void rotated(float yaw,double x) throws Exception {
        Object target=tank(x,12,yaw);
        double[] ray=extraRay(target);
        check(true,"ray misses primary box and intersects actual extra tank box, yaw="+yaw);
        int before=hp(target);
        Object shot=bullet("GenericProjectile",ray[0],ray[1],ray[2],80F);
        call(shot,"func_70071_h_");
        check(dead(shot),"20-block projectile stops at extra box, yaw="+yaw);
        check(hp(target)<before,"rotated extra-box hit damages tank "+before+" -> "+hp(target)+", yaw="+yaw);
        call(target,"func_70106_y");call(shot,"func_70106_y");
    }
    private static void wall() throws Exception {
        Object target=tank(384.5,14,0F);
        block(384,81,4,"minecraft:stone");
        int before=hp(target);
        Object shot=bullet("GenericProjectile",384.5,81.5,0,80F);
        call(shot,"func_70071_h_");
        check(dead(shot),"fast projectile stops at nearer wall");
        check(hp(target)==before,"wall occludes tank, HP "+before+" -> "+hp(target));
        check(blockName(384,81,4).equals("minecraft:stone"),"rifle does not erase stone wall");
        call(target,"func_70106_y");call(shot,"func_70106_y");
    }
    private static void turret() throws Exception {
        Object target=tank(352,12,45F);
        double[] ray=extraRay(target,4);
        int before=hp(target);
        Object shot=fire("GenericProjectile",ray[0],ray[1],ray[2],80F);
        check(dead(shot),"fast projectile stops at upper turret outside primary bounds");
        check(hp(target)<before,"upper turret hit registers damage "+before+" -> "+hp(target));
        call(target,"func_70106_y");call(shot,"func_70106_y");
    }
    private static Object drone(double x,double y,double z) throws Exception {
        Object value=type("com.norwood.mcheli.helicopter.MCH_EntityHeli").getConstructor(type("net.minecraft.world.World")).newInstance(world);
        call(value,"setTypeName","rc-goblin-bomb");call(value,"setTextureName","rc-goblin-bomb");
        spawn(value,x,y,z);call(value,"setFuel",call(value,"getMaxFuel"));
        Object station=call(type("com.norwood.mcheli.uav.MCH_EntityUavStation"),"createHandheld",world,player,VMReflect.get(type("net.minecraft.util.EnumHand"),"MAIN_HAND"),java.util.Collections.singletonList(call(value,"func_110124_au")),false);
        call(world,"func_72838_d",station);entities.add(station);
        call(station,"pairUav",call(value,"func_110124_au"));
        check("OK".equals(String.valueOf(call(type("com.norwood.mcheli.uav.MCH_UavControl"),"connect",player,station,value))),"real player connects to QA FPV");
        call(value,"setCurrentThrottle",.6D);VMReflect.set(value,"field_70122_E",false);VMReflect.set(value,"field_70179_y",20D);
        return value;
    }
    private static void fpvExtra() throws Exception {
        Object target=tank(432,12,90F);
        double[] ray=extraRay(target);
        Object value=drone(ray[0],ray[1]-.35,ray[2]);
        int before=hp(target);
        call(value,"warfareCheckMotion");
        check(dead(value),"armed fast FPV stops at rotated extra box");
        int after=hp(target);
        check(after<before-1,"contact charge produces meaningful tank damage "+before+" -> "+after);
        call(value,"warfareCheckMotion");
        check(hp(target)==after,"repeated motion call cannot deal second blast damage");
        call(target,"func_70106_y");call(value,"func_70106_y");
    }
    private static void fpvWall() throws Exception {
        Object target=tank(480.5,22,0F);
        block(480,80,3,"minecraft:stone");block(480,81,3,"minecraft:stone");
        Object value=drone(480.5,80,0);
        VMReflect.set(value,"field_70179_y",30D);
        int before=hp(target);
        call(value,"warfareCheckMotion");
        check(dead(value),"FPV detonates at nearer wall");
        check(hp(target)==before,"FPV cannot cross wall to attack distant tank");
        call(target,"func_70106_y");call(value,"func_70106_y");
    }
    private static void destruction() throws Exception {
        Object target=tank(528.5,12,0F);
        int hits=0;
        while(!(Boolean)call(target,"isDestroyed") && hits<12) {
            Object shot=bullet("GenericProjectile",528.5,81,0,80F);
            call(shot,"func_70071_h_");
            check(dead(shot),"penetrating hit stops, destruction sequence hit="+(++hits));
            call(shot,"func_70106_y");
        }
        check((Boolean)call(target,"isDestroyed") && hp(target)<=0,"registered damage destroys real tank, hits="+hits+", HP="+hp(target));
        call(target,"func_70106_y");
    }
    private static Object stack() throws Exception {
        Object item=call(type("net.minecraft.item.Item"),"func_111206_d","minecraft:diamond");
        return type("net.minecraft.item.ItemStack").getConstructor(type("net.minecraft.item.Item")).newInstance(item);
    }
    private static Object drop;
    private static Object frame;
    private static long propsStarted;
    private static void props() throws Exception {
        propsStarted=System.nanoTime();
        advanceBudgetClock();
        block(576,81,8,"minecraft:glass");fire("GenericProjectile",576.5,81.5,0,8F);
        advanceBudgetClock();
        block(608,81,8,"minecraft:planks");
        fire("GenericProjectile",608.5,81.5,0,8F);
        check(blockName(608,81,8).equals("minecraft:planks") && !blockName(608,81,7).equals("minecraft:fire"),"weak ordinary round cannot ignite or erase solid wood");
        for(int i=0;i<12;i++)fire("GenericProjectile",608.5,81.5,0,80F);
        advanceBudgetClock();
        block(640,81,8,"minecraft:bedrock");fire("GenericProjectile",640.5,81.5,0,80F);
        advanceBudgetClock();
        drop=type("net.minecraft.entity.item.EntityItem").getConstructor(type("net.minecraft.world.World"),double.class,double.class,double.class,type("net.minecraft.item.ItemStack")).newInstance(world,672.5,81D,8.5,stack());
        spawn(drop,672.5,81,8.5);fire("GenericProjectile",672.5,81.125,0,8F);
        advanceBudgetClock();
        block(704,81,9,"minecraft:stone");
        frame=type("net.minecraft.entity.item.EntityItemFrame").getConstructor(type("net.minecraft.world.World"),type("net.minecraft.util.math.BlockPos"),type("net.minecraft.util.EnumFacing")).newInstance(world,pos(704,81,8),VMReflect.get(type("net.minecraft.util.EnumFacing"),"NORTH"));
        call(frame,"func_82334_a",stack());call(world,"func_72838_d",frame);entities.add(frame);
        fire("GenericProjectile",704.5,81.5,0,8F);
        for(int x=735;x<=737;x++)for(int y=80;y<=82;y++)for(int z=0;z<=9;z++)block(x,y,z,"minecraft:air");
        block(736,81,8,"minecraft:planks");
        advanceBudgetClock();
        run("incendiary",new RunnableCheck(){public void run() throws Exception{
            Object flame=bullet("FlamethrowerProjectile",736.5,81.5,0,8F);
            VMReflect.set(flame,"field_70159_w",0D);VMReflect.set(flame,"field_70181_x",0D);
            java.lang.reflect.Field chance=flame.getClass().getDeclaredField("chanceToIgnite");chance.setAccessible(true);chance.setFloat(flame,1F);
            call(flame,"func_70071_h_");
        }});
        finishProps();
    }
    private static void finishProps() {
        try {
            check(blockName(576,81,8).equals("minecraft:air"),"rifle breaks actual glass block");
            String wood=blockName(608,81,8);
            check(wood.equals("minecraft:air"),"repeated heavy rounds destroy wooden prop");
            check(blockName(640,81,8).equals("minecraft:bedrock"),"protected bedrock survives heavy projectile");
            check(dead(drop),"bullet hits and destroys dropped item");
            check(dead(frame) || (Boolean)call(call(frame,"func_82335_i"),"func_190926_b"),"bullet removes displayed item from frame");
            boolean burn=!blockName(736,81,8).equals("minecraft:planks");
            for(int x=735;x<=737;x++)for(int y=80;y<=82;y++)for(int z=7;z<=9;z++)if(blockName(x,y,z).equals("minecraft:fire"))burn=true;
            check(burn,"incendiary projectile starts actual wood burn");
            fire("GenericProjectile",704.5,81.5,0,8F);
            check(dead(frame),"second hit breaks empty item frame");
        }catch(Exception e){check(false,"props fixture "+e);}
    }
    private static void finish() {
        for(Object entity:entities)try{call(entity,"func_70106_y");}catch(Exception e){System.err.println("[RV combat QA] Cleanup entity "+e);}
        for(Map.Entry<Object,Object> entry:blocks.entrySet())try{call(world,"func_180501_a",entry.getKey(),entry.getValue(),3);}catch(Exception e){System.err.println("[RV combat QA] Cleanup block "+e);}
        System.out.println("[RV combat QA] "+(failures.isEmpty()?"COMPLETE ":"FAILED ")+checks+" checks, failures="+failures.size()+", propsElapsedMs="+(System.nanoTime()-propsStarted)/1000000L);
    }
    private static void run(String name,RunnableCheck action) {
        try{action.run();}catch(Exception|LinkageError e){check(false,name+" fixture "+e);e.printStackTrace();}
    }
    private interface RunnableCheck { void run() throws Exception; }
    public static void verify(Object value) throws Exception {
        if(!Boolean.getBoolean("vm.controls.integration"))throw new IllegalStateException("Isolated integration server required");
        server=value;world=call(server,"func_71218_a",0);
        player=call(call(server,"func_184103_al"),"func_152612_a","VMControlsTest");
        if(player==null)throw new IllegalStateException("VMControlsTest must be connected");
        checks=0;failures.clear();entities.clear();blocks.clear();
        run("rotated 0",new RunnableCheck(){public void run() throws Exception{rotated(0F,256);}});
        run("rotated 90",new RunnableCheck(){public void run() throws Exception{rotated(90F,288);}});
        run("rotated 135",new RunnableCheck(){public void run() throws Exception{rotated(135F,320);}});
        run("upper turret",new RunnableCheck(){public void run() throws Exception{turret();}});
        run("nearer wall",new RunnableCheck(){public void run() throws Exception{wall();}});
        run("FPV extra box",new RunnableCheck(){public void run() throws Exception{fpvExtra();}});
        run("FPV nearer wall",new RunnableCheck(){public void run() throws Exception{fpvWall();}});
        run("actual destruction",new RunnableCheck(){public void run() throws Exception{destruction();}});
        try{props();}catch(Exception|LinkageError e){check(false,"props setup "+e);e.printStackTrace();}finally{finish();}
        if(!failures.isEmpty())throw new IllegalStateException("Independent combat acceptance: "+failures);
    }
}
