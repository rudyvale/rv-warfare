import java.io.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.common.event.FMLInitializationEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;

@Mod(modid="rv_spawn_qa",name="RV isolated spawn QA",version="1",acceptableRemoteVersions="*")
public final class RVSpawnRuntime {
    @Mod.EventHandler public void init(FMLInitializationEvent event) { MinecraftForge.EVENT_BUS.register(this); }
    static Object call(Object target,String name,Object... args) throws Exception {
        Class<?> type = target instanceof Class ? (Class<?>)target : target.getClass();
        for(Method method:type.getMethods()) {
            if(!method.getName().equals(name)||method.getParameterTypes().length!=args.length)continue;
            method.setAccessible(true);
            return method.invoke(target instanceof Class?null:target,args);
        }
        throw new NoSuchMethodException(name);
    }
    static Object field(Object target,String name) throws Exception {
        for(Class<?> type=target.getClass();type!=null;type=type.getSuperclass()) {
            try { Field field=type.getDeclaredField(name);field.setAccessible(true);return field.get(target); }
            catch(NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    @SubscribeEvent public void client(TickEvent.ClientTickEvent event) {
        if(event.phase!=TickEvent.Phase.END)return;
        Path request=Paths.get("rv-qa-respawn.txt");
        if(!Files.isRegularFile(request))return;
        try {
            Object minecraft=call(Class.forName("net.minecraft.client.Minecraft"),"func_71410_x");
            Object player=field(minecraft,"field_71439_g");
            if(player==null)return;
            call(player,"func_71004_bE");
            call(minecraft,"func_147108_a",new Object[]{null});
            Files.delete(request);
            Files.write(Paths.get("rv-qa-respawn-result.txt"),"native client PERFORM_RESPAWN sent".getBytes(StandardCharsets.UTF_8));
        } catch(Throwable error) {
            try { Files.move(request,Paths.get("rv-qa-respawn-failed.txt")); } catch(Throwable ignored) { }
            error.printStackTrace();
        }
    }
    @SubscribeEvent public void server(TickEvent.ServerTickEvent event) {
        if(event.phase!=TickEvent.Phase.END)return;
        Path propRequest=Paths.get("rv-qa-props.txt");
        if(Files.isRegularFile(propRequest)) {
            try {
                Object server=call(call(Class.forName("net.minecraftforge.fml.common.FMLCommonHandler"),"instance"),"getMinecraftServerInstance");
                Object world=call(server,"func_71218_a",0);
                int x=-160,z=558;
                for(int cx=(x-8)>>4;cx<=(x+8)>>4;cx++)for(int cz=(z-8)>>4;cz<=(z+8)>>4;cz++)call(world,"func_72964_e",cx,cz);
                Class<?> posClass=Class.forName("net.minecraft.util.math.BlockPos");
                Object position=posClass.getConstructor(int.class,int.class,int.class).newInstance(x,65,z);
                Object before=call(call(world,"func_180495_p",position),"func_177230_c");
                Object registry=Class.forName("net.minecraft.block.Block").getField("field_149771_c").get(null);
                String beforeName=String.valueOf(call(registry,"func_177774_c",before));
                call(world,"func_72885_a",null,x+0.5D,65.5D,z+0.5D,6F,false,true);
                Object after=call(call(world,"func_180495_p",position),"func_177230_c");
                String afterName=String.valueOf(call(registry,"func_177774_c",after));
                boolean passed=beforeName.equals("minecraft:sandstone")&&afterName.equals("minecraft:air");
                Files.delete(propRequest);
                Files.write(Paths.get("rv-qa-props-result.json"),("{\"passed\":"+passed+",\"nativeWorld\":true,\"nativeExplosion\":true,\"before\":\""+beforeName+"\",\"after\":\""+afterName+"\",\"position\":[-160,65,558]}").getBytes(StandardCharsets.UTF_8));
            } catch(Throwable error) {
                try { Files.move(propRequest,Paths.get("rv-qa-props-failed.txt")); } catch(Throwable ignored) { }
                error.printStackTrace();
            }
        }
        Path request=Paths.get("rv-qa-bed.txt");
        if(!Files.isRegularFile(request))return;
        try {
            Class<?> common=Class.forName("net.minecraftforge.fml.common.FMLCommonHandler");
            Object server=call(call(common,"instance"),"getMinecraftServerInstance");
            Object list=call(server,"func_184103_al");
            Object player=call(list,"func_152612_a","MenuTester");
            Object position=Class.forName("net.minecraft.util.math.BlockPos").getConstructor(int.class,int.class,int.class).newInstance(10,65,-210);
            call(player,"func_180473_a",position,false);
            Files.delete(request);
            Files.write(Paths.get("rv-qa-bed-result.txt"),"native player bed spawn stored with SpawnForced=false".getBytes(StandardCharsets.UTF_8));
        } catch(Throwable error) {
            try { Files.move(request,Paths.get("rv-qa-bed-failed.txt")); } catch(Throwable ignored) { }
            error.printStackTrace();
        }
    }
}
