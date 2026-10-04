package rv.experience.server;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class GearCatalog {
    public static final int BUDGET = 24;
    public static final class Entry {
        public final String key, item, category, name, nameRu;
        public final int metadata, limit, points, stack;
        Entry(String key, String item, int metadata, int limit, int points, int stack, String category, String name, String nameRu) {
            this.key=key; this.item=item; this.metadata=metadata; this.limit=limit; this.points=points; this.stack=stack; this.category=category; this.name=name; this.nameRu=nameRu;
        }
        public Map<String,Object> json() {
            Map<String,Object> data=new LinkedHashMap<String,Object>();
            data.put("id",key);data.put("item",item);data.put("metadata",metadata);data.put("limit",limit);data.put("points",points);data.put("category",category);data.put("name",name);data.put("nameRu",nameRu);
            return data;
        }
    }
    private final Map<String,Entry> entries=new LinkedHashMap<String,Entry>();
    public GearCatalog() {
        add("m4","techguns:m4",0,1,6,1,"primary","M4","M4");
        add("scar","techguns:scar",0,1,7,1,"primary","SCAR","SCAR");
        add("aug","techguns:aug",0,1,7,1,"primary","AUG","AUG");
        add("as50","techguns:as50",0,1,9,1,"primary","AS50","AS50");
        add("shotgun","techguns:combatshotgun",0,1,6,1,"primary","Combat shotgun","Дробовик");
        add("mw_m4","modularwarfare:tcp.m4a4",0,1,7,1,"primary","MW M4A4","MW M4A4");
        add("mw_ak","modularwarfare:tcp.ak74",0,1,7,1,"primary","MW AK-74","MW AK-74");
        add("deagle","modularwarfare:tcp.deagle",0,1,3,1,"sidearm","MW Desert Eagle","MW Desert Eagle");
        add("mw_deagle_mag","modularwarfare:tcp.deagleammo",0,2,2,1,"ammo","MW pistol magazine","Магазин MW пистолета");
        add("rifle_ammo","techguns:itemshared",13,32,1,64,"ammo","Rifle ammunition","Патроны для винтовки");
        add("sniper_ammo","techguns:itemshared",19,16,1,64,"ammo","Sniper ammunition","Снайперские патроны");
        add("shotgun_ammo","techguns:itemshared",2,32,1,64,"ammo","Shotgun ammunition","Патроны для дробовика");
        add("mw_m4_mag","modularwarfare:tcp.m4a4ammo",0,2,2,1,"ammo","MW M4 magazine","Магазин MW M4");
        add("mw_ak_mag","modularwarfare:tcp.akammo",0,2,2,1,"ammo","MW AK magazine","Магазин MW AK");
        add("tablet","mcheli:uav_tablet",0,1,1,1,"drone","UAV controller","Контроллер дрона");
        add("fpv","mcheli:rc-goblin-bomb",0,3,5,1,"drone","FPV UAV","FPV-дрон");
        add("geran","mcheli:rv_geran",0,1,8,1,"drone","Geran UAV","Герань");
        add("fp1","mcheli:rv_fp1",0,1,8,1,"drone","FP-1 UAV","FP-1");
        add("bandage","firstaid:bandage",0,4,1,64,"medical","Bandage","Бинт");
        add("plaster","firstaid:plaster",0,4,1,64,"medical","Plaster","Пластырь");
        add("food","minecraft:cooked_beef",0,16,1,64,"utility","Food","Еда");
        add("helmet","minecraft:iron_helmet",0,1,1,1,"armor","Iron helmet","Железный шлем");
        add("chest","minecraft:iron_chestplate",0,1,2,1,"armor","Iron chestplate","Железный нагрудник");
        add("legs","minecraft:iron_leggings",0,1,1,1,"armor","Iron leggings","Железные поножи");
        add("boots","minecraft:iron_boots",0,1,1,1,"armor","Iron boots","Железные ботинки");
    }
    private void add(String key,String item,int meta,int limit,int cost,int stack,String category,String name,String ru) {entries.put(key,new Entry(key,item,meta,limit,cost,stack,category,name,ru));}
    public Entry get(String key) {return entries.get(key);}
    public List<Entry> all() {return Collections.unmodifiableList(new ArrayList<Entry>(entries.values()));}
    public int cost(Entry entry,int count) {if(count==0)return 0;return entry.points*(entry.category.equals("ammo")&&entry.stack>1?(count+15)/16:entry.category.equals("medical")||entry.category.equals("utility")?1:count);}
    public String validate(Map<String,Integer> selection) {
        int total=0, primaries=0, drones=0;
        if(selection.size()>24)return "selection_limit";
        for(Map.Entry<String,Integer> value:selection.entrySet()) {
            Entry entry=get(value.getKey());int count=value.getValue();
            if(entry==null||count<0||count>entry.limit)return "item_limit";
            total+=cost(entry,count);
            if(entry.category.equals("primary"))primaries+=count;
            if(entry.category.equals("drone")&&entry.key.equals("fpv"))drones+=count;
        }
        if(primaries>1||drones>3)return "category_limit";
        return total>BUDGET?"budget_exceeded":null;
    }
    public int points(Map<String,Integer> selection) {int sum=0;for(Map.Entry<String,Integer> value:selection.entrySet()){Entry e=get(value.getKey());if(e!=null)sum+=cost(e,value.getValue());}return sum;}
}
