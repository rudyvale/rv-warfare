package rv.experience.client;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import rv.experience.protocol.ExperienceProtocol;

public final class ClientState {
    public static final class Choice {
        public int id,slot,meta,count,cost;
        public String ru,en,item;
        public String label(boolean english){return english?en:ru;}
    }
    public static final class Preset { public int id;public String ru,en;public String label(boolean english){return english?en:ru;} }
    public long revision;
    public boolean english,ready,canEditGear,gearConfirmed,keepGear;
    public int phase,mode,players,readyPlayers,votes,votesNeeded,countdownSeconds,roundSeconds,bluePlayers,redPlayers,team,freeSlots,requiredSlots,budget,cost,cooldownSeconds;
    public String message;
    public final List<Choice> catalog=new ArrayList<Choice>();
    public final Map<Integer,Choice> choices=new HashMap<Integer,Choice>();
    public final List<Preset> presets=new ArrayList<Preset>();
    public final int[] selection=new int[7];
    public static ClientState parse(String json){
        depth(json);JsonElement parsed=new JsonParser().parse(json);if(!parsed.isJsonObject())throw new IllegalArgumentException("snapshot_object");JsonObject o=parsed.getAsJsonObject();
        if(number(o,"protocol",1,1)!=ExperienceProtocol.VERSION)throw new IllegalArgumentException("protocol");
        ClientState s=new ClientState();s.revision=integer(o,"revision",0,Long.MAX_VALUE);String language=string(o,"language",2);if(!language.equals("en")&&!language.equals("ru"))throw new IllegalArgumentException("language");s.english=language.equals("en");
        s.phase=number(o,"phase",0,3);s.mode=number(o,"mode",0,2);s.team=number(o,"team",0,3);
        s.players=number(o,"players",0,256);s.readyPlayers=number(o,"readyPlayers",0,256);s.votes=number(o,"votes",0,256);s.votesNeeded=number(o,"votesNeeded",0,256);s.bluePlayers=number(o,"bluePlayers",0,256);s.redPlayers=number(o,"redPlayers",0,256);
        s.countdownSeconds=number(o,"countdownSeconds",0,86400);s.roundSeconds=number(o,"roundSeconds",0,86400);s.freeSlots=number(o,"freeSlots",0,36);s.requiredSlots=number(o,"requiredSlots",0,36);s.budget=number(o,"budget",0,1000000);s.cost=number(o,"cost",0,1000000);s.cooldownSeconds=number(o,"cooldownSeconds",0,86400);
        s.ready=bool(o,"ready");s.canEditGear=bool(o,"canEditGear");s.gearConfirmed=bool(o,"gearConfirmed");s.keepGear=bool(o,"keepGear");s.message=string(o,"messageCode",48);if(!s.message.matches("[A-Za-z0-9_]{1,48}"))throw new IllegalArgumentException("message_code");
        JsonArray catalog=array(o,"catalog",0,64);for(JsonElement element:catalog){JsonObject c=element.getAsJsonObject();Choice choice=new Choice();choice.id=number(c,"id",1,65535);choice.slot=number(c,"slot",0,6);choice.ru=string(c,"labelRu",80);choice.en=string(c,"labelEn",80);choice.item=string(c,"itemId",160);if(!choice.item.matches("[a-z0-9_.-]+:[a-z0-9_./-]+"))throw new IllegalArgumentException("item_id");choice.meta=number(c,"meta",0,32767);choice.count=number(c,"count",1,64);choice.cost=number(c,"cost",0,1000000);if(s.choices.put(choice.slot*65536+choice.id,choice)!=null)throw new IllegalArgumentException("duplicate_choice");s.catalog.add(choice);}
        JsonArray selected=array(o,"selection",7,7);for(int i=0;i<7;i++){s.selection[i]=(int)numeric(selected.get(i),0,65535);Choice c=s.choices.get(i*65536+s.selection[i]);if(s.selection[i]!=0&&(c==null||c.slot!=i))throw new IllegalArgumentException("selection");}
        JsonArray presets=array(o,"presets",0,8);for(JsonElement element:presets){JsonObject p=element.getAsJsonObject();Preset preset=new Preset();preset.id=number(p,"id",1,65535);preset.ru=string(p,"labelRu",80);preset.en=string(p,"labelEn",80);for(Preset old:s.presets)if(old.id==preset.id)throw new IllegalArgumentException("duplicate_preset");s.presets.add(preset);}
        return s;
    }
    private static void depth(String json){int level=0;boolean quoted=false,escaped=false;for(int i=0;i<json.length();i++){char c=json.charAt(i);if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='"')quoted=false;}else if(c=='"')quoted=true;else if(c=='{'||c=='['){if(++level>12)throw new IllegalArgumentException("depth");}else if(c=='}'||c==']'){if(--level<0)throw new IllegalArgumentException("depth");}}if(level!=0||quoted)throw new IllegalArgumentException("depth");}
    private static JsonElement member(JsonObject o,String name){JsonElement e=o.get(name);if(e==null||e.isJsonNull())throw new IllegalArgumentException(name);return e;}
    private static long numeric(JsonElement e,long min,long max){if(!e.isJsonPrimitive()||!e.getAsJsonPrimitive().isNumber())throw new IllegalArgumentException("number");java.math.BigDecimal d=e.getAsBigDecimal();long v=d.longValueExact();if(v<min||v>max)throw new IllegalArgumentException("range");return v;}
    private static long integer(JsonObject o,String name,long min,long max){return numeric(member(o,name),min,max);}
    private static int number(JsonObject o,String name,int min,int max){return (int)integer(o,name,min,max);}
    private static boolean bool(JsonObject o,String name){JsonElement e=member(o,name);if(!e.isJsonPrimitive()||!e.getAsJsonPrimitive().isBoolean())throw new IllegalArgumentException(name);return e.getAsBoolean();}
    private static String string(JsonObject o,String name,int max){JsonElement e=member(o,name);if(!e.isJsonPrimitive()||!e.getAsJsonPrimitive().isString())throw new IllegalArgumentException(name);String s=e.getAsString();if(s.length()>max||s.indexOf('\u00a7')>=0)throw new IllegalArgumentException(name);for(int i=0;i<s.length();i++)if(Character.isISOControl(s.charAt(i)))throw new IllegalArgumentException(name);return s;}
    private static JsonArray array(JsonObject o,String name,int min,int max){JsonArray a=member(o,name).getAsJsonArray();if(a.size()<min||a.size()>max)throw new IllegalArgumentException(name);return a;}
}
