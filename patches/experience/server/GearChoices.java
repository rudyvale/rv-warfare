package rv.experience.server;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class GearChoices {
    public static final class Choice {
        public final int id,slot;
        public final String ru,en;
        public final Map<String,Integer> items=new LinkedHashMap<String,Integer>();
        Choice(int id,int slot,String ru,String en,String... pairs){this.id=id;this.slot=slot;this.ru=ru;this.en=en;for(int i=0;i<pairs.length;i+=2)items.put(pairs[i],Integer.parseInt(pairs[i+1]));}
    }
    private final Map<Integer,Choice> choices=new LinkedHashMap<Integer,Choice>();
    public GearChoices(){
        add(1,0,"M4","M4","m4","1");add(2,0,"SCAR","SCAR","scar","1");add(3,0,"AUG","AUG","aug","1");add(4,0,"AS50","AS50","as50","1");add(5,0,"Дробовик","Shotgun","shotgun","1");add(6,0,"MW M4A4 + 2 магазина","MW M4A4 + 2 magazines","mw_m4","1","mw_m4_mag","2");add(7,0,"MW AK-74 + 2 магазина","MW AK-74 + 2 magazines","mw_ak","1","mw_ak_mag","2");
        add(10,1,"MW Desert Eagle + 2 магазина","MW Desert Eagle + 2 magazines","deagle","1","mw_deagle_mag","2");
        add(20,2,"Шлем и нагрудник","Helmet and chestplate","helmet","1","chest","1");add(21,2,"Полная железная броня","Full iron armor","helmet","1","chest","1","legs","1","boots","1");
        add(30,3,"FPV-дрон и контроллер","FPV UAV and controller","fpv","1","tablet","1");
        add(31,3,"2 FPV-дрона и контроллер","2 FPV UAVs and controller","fpv","2","tablet","1");add(32,3,"3 FPV-дрона и контроллер","3 FPV UAVs and controller","fpv","3","tablet","1");add(33,3,"Герань и контроллер","Geran UAV and controller","geran","1","tablet","1");add(34,3,"FP-1 и контроллер","FP-1 UAV and controller","fp1","1","tablet","1");add(35,3,"FPV, Герань, FP-1 и контроллер","FPV, Geran, FP-1 and controller","fpv","1","geran","1","fp1","1","tablet","1");
        add(40,4,"4 бинта","4 bandages","bandage","4");add(41,4,"4 бинта и 4 пластыря","4 bandages and 4 plasters","bandage","4","plaster","4");
        add(50,5,"16 порций еды","16 food portions","food","16");
        add(60,6,"32 винтовочных патрона","32 rifle rounds","rifle_ammo","32");add(61,6,"16 снайперских патронов","16 sniper rounds","sniper_ammo","16");add(62,6,"32 патрона для дробовика","32 shotgun rounds","shotgun_ammo","32");add(63,6,"2 магазина MW M4","2 MW M4 magazines","mw_m4_mag","2");add(64,6,"2 магазина MW AK","2 MW AK magazines","mw_ak_mag","2");
    }
    private void add(int id,int slot,String ru,String en,String...pairs){choices.put(id,new Choice(id,slot,ru,en,pairs));}
    public Choice get(int id){return choices.get(id);}
    public Map<String,Integer> resolve(int[] selected){
        if(selected.length!=7)throw new IllegalArgumentException("choice_slots");Map<String,Integer> result=new LinkedHashMap<String,Integer>();
        for(int slot=0;slot<7;slot++){int id=selected[slot];if(id==0)continue;Choice c=get(id);if(c==null||c.slot!=slot)throw new IllegalArgumentException("unknown_choice");for(Map.Entry<String,Integer> e:c.items.entrySet())result.put(e.getKey(),e.getValue());}return result;
    }
    public boolean available(Choice choice,SessionEngine.Inventory inventory,GearCatalog catalog){for(String key:choice.items.keySet())if(!inventory.available(catalog.get(key).item))return false;return true;}
    public List<Map<String,Object>> json(SessionEngine.Inventory inventory,GearCatalog catalog){
        List<Map<String,Object>> result=new ArrayList<Map<String,Object>>();
        for(Choice c:choices.values()){if(!available(c,inventory,catalog))continue;GearCatalog.Entry icon=catalog.get(c.items.keySet().iterator().next());Map<String,Object> v=new LinkedHashMap<String,Object>();v.put("id",c.id);v.put("slot",c.slot);v.put("labelRu",c.ru);v.put("labelEn",c.en);v.put("itemId",icon.item);v.put("meta",icon.metadata);v.put("count",c.items.get(icon.key));v.put("cost",catalog.points(c.items));result.add(v);}return result;
    }
    public static int[] preset(int id){
        switch(id){case 1:return new int[]{1,0,20,0,40,50,60};case 2:return new int[]{4,0,20,0,40,50,61};case 3:return new int[]{0,0,20,30,40,50,0};case 4:return new int[]{6,0,20,0,40,50,63};default:return null;}
    }
    public static List<Map<String,Object>> presets(){List<Map<String,Object>> result=new ArrayList<Map<String,Object>>();String[] ru={"Штурмовик","Снайпер","FPV","MW M4"},en={"Assault","Sniper","FPV","MW M4"};for(int i=0;i<4;i++){Map<String,Object> p=new LinkedHashMap<String,Object>();p.put("id",i+1);p.put("labelRu",ru[i]);p.put("labelEn",en[i]);result.add(p);}return result;}
}
