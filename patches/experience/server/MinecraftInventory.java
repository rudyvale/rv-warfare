package rv.experience.server;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class MinecraftInventory implements SessionEngine.Inventory {
    private final GearCatalog catalog=new GearCatalog();
    public final Map<String,Object> online=new LinkedHashMap<String,Object>();
    private Object item(String id)throws Exception{Object registry=Reflect.field(Class.forName("net.minecraftforge.fml.common.registry.ForgeRegistries"),"ITEMS");Object resource=Class.forName("net.minecraft.util.ResourceLocation").getConstructor(String.class).newInstance(id);return Reflect.call(registry,new String[]{"getValue"},resource);}
    public boolean available(String id){try{return item(id)!=null;}catch(Exception failure){return false;}}
    @SuppressWarnings("unchecked")
    private List<Object> main(Object player)throws Exception{return (List<Object>)Reflect.field(Reflect.field(player,"inventory","field_71071_by"),"mainInventory","field_70462_a");}
    @SuppressWarnings("unchecked")
    private List<Object> all(Object player)throws Exception{Object inv=Reflect.field(player,"inventory","field_71071_by");List<Object> result=new ArrayList<Object>(main(player));result.addAll((List<Object>)Reflect.field(inv,"armorInventory","field_70460_b"));result.addAll((List<Object>)Reflect.field(inv,"offHandInventory","field_184439_c"));return result;}
    private boolean empty(Object stack)throws Exception{return Boolean.TRUE.equals(Reflect.call(stack,new String[]{"isEmpty","func_190926_b"}));}
    private int count(Object stack)throws Exception{return empty(stack)?0:((Number)Reflect.call(stack,new String[]{"getCount","func_190916_E"})).intValue();}
    private void count(Object stack,int value)throws Exception{Reflect.call(stack,new String[]{"setCount","func_190920_e"},value);}
    private int meta(Object stack)throws Exception{return ((Number)Reflect.call(stack,new String[]{"getMetadata","func_77960_j"})).intValue();}
    private String registry(Object stack)throws Exception{Object item=Reflect.call(stack,new String[]{"getItem","func_77973_b"});return Class.forName("net.minecraftforge.registries.IForgeRegistryEntry").getMethod("getRegistryName").invoke(item).toString();}
    private Object copy(Object stack)throws Exception{return Reflect.call(stack,new String[]{"copy","func_77946_l"});}
    private Object create(GearCatalog.Entry e,int count)throws Exception{Class<?> itemClass=Class.forName("net.minecraft.item.Item"),stackClass=Class.forName("net.minecraft.item.ItemStack");return stackClass.getConstructor(itemClass,int.class,int.class).newInstance(item(e.item),count,e.metadata);}
    private boolean matches(Object stack,GearCatalog.Entry entry)throws Exception{return !empty(stack)&&registry(stack).equals(entry.item)&&(entry.stack==1||meta(stack)==entry.metadata);}
    private int owned(Object player,GearCatalog.Entry e)throws Exception{int result=0;for(Object stack:all(player))if(matches(stack,e))result+=count(stack);return result;}
    public int freeSlots(String id){try{int free=0;for(Object stack:main(online.get(id)))if(empty(stack))free++;return free;}catch(Exception error){return 0;}}
    private List<Object> prepared(String id,Map<String,Integer> selection)throws Exception{
        Object player=online.get(id);if(player==null)throw new IllegalArgumentException("offline");List<Object> result=new ArrayList<Object>();for(Object stack:main(player))result.add(copy(stack));
        for(Map.Entry<String,Integer> requested:selection.entrySet()){
            GearCatalog.Entry e=catalog.get(requested.getKey());if(e==null||!available(e.item))throw new IllegalArgumentException("item_unavailable");int remaining=Math.max(0,requested.getValue()-owned(player,e));
            Object prototype=create(e,1);int limit=((Number)Reflect.call(prototype,new String[]{"getMaxStackSize","func_77976_d"})).intValue();
            for(Object stack:result){if(remaining==0)break;if(!matches(stack,e))continue;boolean tags=Boolean.TRUE.equals(Reflect.call(Class.forName("net.minecraft.item.ItemStack"),new String[]{"areItemStackTagsEqual","func_77970_a"},stack,prototype));if(!tags)continue;int add=Math.min(remaining,Math.max(0,limit-count(stack)));count(stack,count(stack)+add);remaining-=add;}
            for(int slot=0;slot<result.size()&&remaining>0;slot++)if(empty(result.get(slot))){int add=Math.min(remaining,limit);result.set(slot,create(e,add));remaining-=add;}
            if(remaining>0)throw new IllegalArgumentException("inventory_full");
        }
        return result;
    }
    public int requiredSlots(String id,Map<String,Integer> selection){try{List<Object> list=prepared(id,selection);int free=0;for(Object stack:list)if(empty(stack))free++;return Math.max(0,freeSlots(id)-free);}catch(Exception failure){return 36;}}
    public String equip(String id,Map<String,Integer> selection){
        try{List<Object> original=new ArrayList<Object>(main(online.get(id)));List<Object> prepared=prepared(id,selection);List<Object> live=main(online.get(id));
            try{for(int i=0;i<36;i++)live.set(i,prepared.get(i));Reflect.call(Reflect.field(online.get(id),"inventory","field_71071_by"),new String[]{"markDirty","func_70296_d"});Object container=Reflect.field(online.get(id),"inventoryContainer","field_71069_bz");Reflect.call(container,new String[]{"detectAndSendChanges","func_75142_b"});}
            catch(Exception failure){for(int i=0;i<36;i++)live.set(i,original.get(i));throw failure;}return null;
        }catch(IllegalArgumentException failure){return failure.getMessage();}catch(Exception failure){System.err.println("[RV experience] Inventory transaction rejected: "+failure.getClass().getSimpleName());return "inventory_error";}
    }
    public String audit(String id,Map<String,Integer> selection){
        try{Object player=online.get(id);if(player==null)return "offline";Map<String,Integer> owned=new LinkedHashMap<String,Integer>();
            for(Object stack:all(player)){if(empty(stack))continue;GearCatalog.Entry entry=null;for(GearCatalog.Entry candidate:catalog.all())if(matches(stack,candidate)){entry=candidate;break;}
                if(entry!=null){Integer n=owned.get(entry.key);owned.put(entry.key,(n==null?0:n)+count(stack));continue;}
                Object it=Reflect.call(stack,new String[]{"getItem","func_77973_b"});String cls=it.getClass().getName().toLowerCase(),name=registry(stack);
                if(cls.contains("itemgun")||cls.contains("itemammo")||cls.contains("itemvehicle")||name.startsWith("mcheli:")||name.startsWith("modularwarfare:"))return "unsupported_combat_gear";
            }
            String error=catalog.validate(owned);if(error!=null)return error;
            for(Map.Entry<String,Integer> e:selection.entrySet())if(owned(player,catalog.get(e.getKey()))<e.getValue())return "gear_missing";
            return null;
        }catch(Exception error){return "inventory_error";}
    }
    public List<Map<String,Object>> contents(String id){List<Map<String,Object>> out=new ArrayList<Map<String,Object>>();try{int slot=0;for(Object stack:all(online.get(id))){if(!empty(stack)){Map<String,Object> e=new LinkedHashMap<String,Object>();e.put("slot",slot);e.put("itemId",registry(stack));e.put("count",count(stack));e.put("meta",meta(stack));out.add(e);}slot++;}}catch(Exception ignored){}return out;}
    private String destination(String id,int x,int y,int z){
        try{Object player=online.get(id);if(player==null)return "offline";if(((Number)Reflect.field(player,"dimension","field_71093_bK")).intValue()!=0)return "wrong_dimension";Object world=Reflect.field(player,"world","field_70170_p");Class<?> pos=Class.forName("net.minecraft.util.math.BlockPos");
            Object check=pos.getConstructor(int.class,int.class,int.class).newInstance(x,y,z);if(!Boolean.TRUE.equals(Reflect.call(world,new String[]{"isBlockLoaded","func_175667_e"},check))){Object provider=Reflect.call(world,new String[]{"getChunkProvider","func_72863_F"});if(!Boolean.TRUE.equals(Reflect.call(provider,new String[]{"isChunkGeneratedAt","func_191062_e"},x>>4,z>>4)))return "destination_unavailable";Reflect.call(world,new String[]{"getChunkFromChunkCoords","func_72964_e"},x>>4,z>>4);}
            for(int dy=-1;dy<=1;dy++){Object block=pos.getConstructor(int.class,int.class,int.class).newInstance(x,y+dy,z);Object state=Reflect.call(world,new String[]{"getBlockState","func_180495_p"},block);Object material=Reflect.call(state,new String[]{"getMaterial","func_185904_a"});boolean solid=Boolean.TRUE.equals(Reflect.call(material,new String[]{"blocksMovement","func_76230_c"}));boolean liquid=Boolean.TRUE.equals(Reflect.call(material,new String[]{"isLiquid","func_76224_d"}));if(liquid||(dy==-1?!solid:solid))return "destination_unavailable";}
            return null;
        }catch(Exception error){return "destination_unavailable";}
    }
    public String teleport(String id,int x,int y,int z){String ready=destination(id,x,y,z);if(ready!=null)return ready;try{Reflect.call(online.get(id),new String[]{"setPositionAndUpdate","func_70634_a"},x+0.5,(double)y,z+0.5);return null;}catch(Exception error){return "destination_unavailable";}}
    public String roundStarted(Map<String,Integer> teams){
        Map<String,double[]> original=new LinkedHashMap<String,double[]>();
        try{for(Map.Entry<String,Integer> entry:teams.entrySet()){String result=destination(entry.getKey(),entry.getValue()==1?-220:220,65,0);if(result!=null)return result;Object player=online.get(entry.getKey());original.put(entry.getKey(),new double[]{((Number)Reflect.field(player,"posX","field_70165_t")).doubleValue(),((Number)Reflect.field(player,"posY","field_70163_u")).doubleValue(),((Number)Reflect.field(player,"posZ","field_70161_v")).doubleValue()});}
            for(Map.Entry<String,Integer> entry:teams.entrySet()){String result=teleport(entry.getKey(),entry.getValue()==1?-220:220,65,0);if(result!=null)throw new IllegalStateException(result);}return null;
        }catch(Exception error){for(Map.Entry<String,double[]> entry:original.entrySet())try{double[] pos=entry.getValue();Reflect.call(online.get(entry.getKey()),new String[]{"setPositionAndUpdate","func_70634_a"},pos[0],pos[1],pos[2]);}catch(Exception ignored){}return "destination_unavailable";}
    }
}
