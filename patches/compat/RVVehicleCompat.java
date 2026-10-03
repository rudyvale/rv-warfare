package rv.compat;

import java.io.InputStream;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;
import net.minecraftforge.fml.common.Loader;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.common.Optional;
import net.minecraftforge.fml.common.event.FMLPostInitializationEvent;
import net.minecraftforge.fml.relauncher.Side;
import net.minecraftforge.fml.relauncher.SideOnly;
import net.minecraftforge.client.settings.IKeyConflictContext;
import minecrafttransportsimulator.items.components.AItemPack;
import minecrafttransportsimulator.jsondefs.AJSONMultiModelProvider;
import minecrafttransportsimulator.jsondefs.JSONSound;
import minecrafttransportsimulator.mcinterface.InterfaceManager;
import minecrafttransportsimulator.packloading.PackParser;

@Mod(modid="rvcompat",name="RV Vehicle Compatibility",version="1.2.0",dependencies="after:mts",acceptableRemoteVersions="[1.2.0]")
public final class RVVehicleCompat {
    @Mod.EventHandler
    public void loaded(FMLPostInitializationEvent event) {
        if(Loader.isModLoaded("mts")) repairVehicleSounds();
        if(event.getSide().isClient()) repairReloadContext();
    }

    @SideOnly(Side.CLIENT)
    private void repairReloadContext() {
        try {
            final Object minecraft=Class.forName("net.minecraft.client.Minecraft").getMethod("func_71410_x").invoke(null);
            Object settings=minecraft.getClass().getField("field_71474_y").get(minecraft);
            for(final Object binding:(Object[])settings.getClass().getField("field_74324_K").get(settings)) {
                if(!"Reload Gun".equals(binding.getClass().getMethod("func_151464_g").invoke(binding))) continue;
                final IKeyConflictContext previous=(IKeyConflictContext)binding.getClass().getMethod("getKeyConflictContext").invoke(binding);
                IKeyConflictContext contextual=new IKeyConflictContext() {
                    public boolean isActive() {
                        if(!previous.isActive()) return false;
                        try {
                            if(minecraft.getClass().getField("field_71462_r").get(minecraft)!=null) return false;
                            Object player=minecraft.getClass().getField("field_71439_g").get(minecraft);
                            if(player==null) return false;
                            Object stack=player.getClass().getMethod("func_184614_ca").invoke(player);
                            Object item=stack.getClass().getMethod("func_77973_b").invoke(stack);
                            String name=item.getClass().getName();
                            return name.equals("com.modularwarfare.common.guns.ItemGun")||name.equals("com.modularwarfare.common.guns.ItemAmmo");
                        } catch(Exception error) {return false;}
                    }
                    public boolean conflicts(IKeyConflictContext other) {return previous.conflicts(other);}
                };
                binding.getClass().getMethod("setKeyConflictContext",IKeyConflictContext.class).invoke(binding,contextual);
                System.out.println("[RV compatibility] ModularWarfare reload context follows the held weapon family; key code preserved");
            }
        } catch(Exception error) {System.err.println("[RV compatibility] Could not configure reload context: "+error);}
    }

    @Optional.Method(modid="mts")
    private void repairVehicleSounds() {
        Set<AJSONMultiModelProvider> seen=Collections.newSetFromMap(new IdentityHashMap<AJSONMultiModelProvider,Boolean>());
        int repaired=0;
        for(AItemPack<?> item:PackParser.getAllPackItems()) {
            if(!(item.definition instanceof AJSONMultiModelProvider)) continue;
            AJSONMultiModelProvider definition=(AJSONMultiModelProvider)item.definition;
            if(!"auweschvebm".equals(definition.packID)||!seen.add(definition)||definition.rendering==null||definition.rendering.sounds==null) continue;
            String bad=null,good=null;
            if("auweschveb_vehicle_obj70".equals(definition.systemName)) {
                bad="mts:iav.iav_horn_truck";good="iav:deep_horn";
            } else if("auweschveb_part_turret_125mm_1".equals(definition.systemName)||"auweschveb_part_turret_125mm_2".equals(definition.systemName)) {
                bad="iavm:ground_guns/125mmgunfar.ogg";good="iavm:ground_guns/125mmgunfar";
            }
            if(bad==null) continue;
            for(JSONSound sound:definition.rendering.sounds) {
                if(!bad.equals(sound.name)) continue;
                String path="/assets/"+good.substring(0,good.indexOf(':'))+"/sounds/"+good.substring(good.indexOf(':')+1)+".ogg";
                try(InputStream resource=InterfaceManager.coreInterface.getPackResource(path)) {
                    if(resource==null) {
                        System.err.println("[RV compatibility] Missing replacement resource: "+path);
                        continue;
                    }
                    sound.name=good;
                    repaired++;
                    System.out.println("[RV compatibility] "+definition.packID+":"+definition.systemName+" "+bad+" -> "+good);
                } catch(Exception error) {
                    System.err.println("[RV compatibility] Could not validate resource "+path+": "+error);
                }
            }
        }
        System.out.println("[RV compatibility] Curated vehicle sound corrections="+repaired);
    }
}
