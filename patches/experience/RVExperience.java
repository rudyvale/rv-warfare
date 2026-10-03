package rv.experience;

import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.entity.living.LivingAttackEvent;
import net.minecraftforge.event.entity.living.LivingDeathEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.common.SidedProxy;
import net.minecraftforge.fml.common.event.FMLInitializationEvent;
import net.minecraftforge.fml.common.event.FMLServerStartingEvent;
import net.minecraftforge.fml.common.event.FMLServerAboutToStartEvent;
import net.minecraftforge.fml.common.event.FMLServerStoppingEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.PlayerEvent;
import net.minecraftforge.fml.common.gameevent.TickEvent;
import net.minecraftforge.fml.common.network.NetworkRegistry;
import net.minecraftforge.fml.common.network.simpleimpl.SimpleNetworkWrapper;
import net.minecraftforge.fml.relauncher.Side;
import rv.experience.protocol.ExperienceProtocol;
import rv.experience.protocol.SessionRequest;
import rv.experience.server.CommonProxy;
import rv.experience.server.ExperienceServer;
import rv.experience.server.Reflect;
import rv.experience.server.ServerRequestHandler;

@Mod(modid="rvexperience",name="RV Experience",version="2.0.0",acceptableRemoteVersions="[2.0.0]")
public final class RVExperience {
    public static SimpleNetworkWrapper network;
    @SidedProxy(clientSide="rv.experience.client.ClientProxy",serverSide="rv.experience.server.CommonProxy")
    public static CommonProxy proxy;
    @Mod.EventHandler
    public void init(FMLInitializationEvent event){network=NetworkRegistry.INSTANCE.newSimpleChannel(ExperienceProtocol.CHANNEL);network.registerMessage(ServerRequestHandler.class,SessionRequest.class,0,Side.SERVER);proxy.init(network);MinecraftForge.EVENT_BUS.register(this);}
    @Mod.EventHandler
    public void before(FMLServerAboutToStartEvent event)throws Exception{ExperienceServer.registerCommand(Reflect.call(event,new String[]{"getServer"}));}
    @Mod.EventHandler
    public void start(FMLServerStartingEvent event)throws Exception{ExperienceServer.start(event);}
    @Mod.EventHandler
    public void stop(FMLServerStoppingEvent event){ExperienceServer.stop();}
    @SubscribeEvent
    public void login(PlayerEvent.PlayerLoggedInEvent event)throws Exception{ExperienceServer.login(Reflect.field(event,"player"));}
    @SubscribeEvent
    public void logout(PlayerEvent.PlayerLoggedOutEvent event)throws Exception{ExperienceServer.logout(Reflect.field(event,"player"));}
    @SubscribeEvent
    public void respawn(PlayerEvent.PlayerRespawnEvent event)throws Exception{ExperienceServer.respawn(Reflect.field(event,"player"));}
    @SubscribeEvent
    public void tick(TickEvent.ServerTickEvent event){if(event.phase==TickEvent.Phase.END)ExperienceServer.tick();}
    @SubscribeEvent
    public void attack(LivingAttackEvent event){try{Object target=Reflect.call(event,new String[]{"getEntityLiving"});Object source=Reflect.call(event,new String[]{"getSource"});Object attacker=Reflect.call(source,new String[]{"getTrueSource","func_76346_g"});if(attacker!=null&&!ExperienceServer.damageAllowed(attacker,target))event.setCanceled(true);}catch(Exception ignored){}}
    @SubscribeEvent
    public void death(LivingDeathEvent event){try{Object target=Reflect.call(event,new String[]{"getEntityLiving"});Object source=Reflect.call(event,new String[]{"getSource"});Object attacker=Reflect.call(source,new String[]{"getTrueSource","func_76346_g"});if(attacker!=null)ExperienceServer.death(attacker,target);}catch(Exception ignored){}}
}
