package rv.experience.server;

import com.google.gson.Gson;
import java.io.File;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import net.minecraftforge.fml.common.event.FMLServerStartingEvent;
import rv.experience.RVExperience;
import rv.experience.protocol.ExperienceProtocol;
import rv.experience.protocol.SessionRequest;
import rv.experience.protocol.SessionSnapshot;

public final class ExperienceServer {
    private static final Gson GSON=new Gson();
    public static final MinecraftInventory inventory=new MinecraftInventory();
    public static SessionEngine engine=new SessionEngine(inventory);
    private static final GearChoices choices=new GearChoices();
    private static final Map<String,Long> watching=new LinkedHashMap<String,Long>();
    private static Object server;
    private static Path stateFile;
    private static boolean healthy=true,dirty;
    private static long savedRevision;
    public static void start(FMLServerStartingEvent event)throws Exception{
        server=Reflect.call(event,new String[]{"getServer"});inventory.online.clear();watching.clear();engine=new SessionEngine(inventory);healthy=true;dirty=false;savedRevision=0;
        Object world=Reflect.call(server,new String[]{"getWorld","func_71218_a"},0);Object handler=Reflect.call(world,new String[]{"getSaveHandler","func_72860_G"});File folder=(File)Reflect.call(handler,new String[]{"getWorldDirectory","func_75765_b"});
        stateFile=folder.toPath().toAbsolutePath().normalize().resolve("data/rvexperience/state.json");
        if(Files.exists(stateFile))try{if(Files.isSymbolicLink(stateFile)||Files.size(stateFile)>262144)throw new IllegalArgumentException("state_size");@SuppressWarnings("unchecked") Map<String,Object> stored=GSON.fromJson(new String(Files.readAllBytes(stateFile),StandardCharsets.UTF_8),Map.class);SessionEngine loaded=new SessionEngine(inventory);loaded.load(stored);for(Object value:((Map<?,?>)stored.get("players")).values()){Map<?,?> player=(Map<?,?>)value;List<?> saved=(List<?>)player.get("choices");int[] ids=new int[7];for(int i=0;i<7;i++)ids[i]=((Number)saved.get(i)).intValue();choices.resolve(ids);}engine=loaded;}
        catch(Exception failure){healthy=false;System.err.println("[RV experience] Session preferences preserved, mutation disabled: "+failure.getClass().getSimpleName());}
    }
    public static void login(Object player){try{String id=Reflect.id(player);inventory.online.put(id,player);engine.join(id);language(player,true);send(player,"welcome");dirty=true;}catch(Exception error){report(error);}}
    public static void logout(Object player){try{String id=Reflect.id(player);if(inventory.online.get(id)!=player)return;engine.leave(id);inventory.online.remove(id);watching.remove(id);ServerRequestHandler.forget(id);dirty=true;}catch(Exception error){report(error);}}
    public static void tick(){
        try{long before=engine.revision;engine.advance();if(engine.revision!=before)dirty=true;
            if(engine.tick%20==0)for(String id:new ArrayList<String>(watching.keySet())){if(engine.tick-watching.get(id)>200||!inventory.online.containsKey(id)){watching.remove(id);continue;}send(inventory.online.get(id),"ok");}
            if(dirty&&engine.tick%100==0)save();
        }catch(Exception failure){engine.cancel("session_error");report(failure);}
    }
    public static void stop(){try{save();}catch(Exception failure){report(failure);}inventory.online.clear();watching.clear();server=null;}
    private static boolean actor(Object player)throws Exception{return player!=null&&Class.forName("net.minecraft.entity.player.EntityPlayerMP").isInstance(player)&&inventory.online.get(Reflect.id(player))==player;}
    private static void send(Object player,String result)throws Exception{
        String json=snapshot(player,result);Method method=RVExperience.network.getClass().getMethod("sendTo",net.minecraftforge.fml.common.network.simpleimpl.IMessage.class,Class.forName("net.minecraft.entity.player.EntityPlayerMP"));method.invoke(RVExperience.network,new SessionSnapshot(json),player);
    }
    public static void handle(Object player,SessionRequest request){
        try{if(!actor(player)||request==null||!request.valid||request.action==null)return;String id=Reflect.id(player);SessionEngine.Player p=engine.player(id);watching.put(id,engine.tick);
            String result;
            if(!validArgs(request))result="invalid_request";
            else if(!healthy&&request.action!=ExperienceProtocol.Action.SNAPSHOT&&request.action!=ExperienceProtocol.Action.OPEN_GUIDE)result="storage_error";
            else result=apply(p,request);
            send(player,result);dirty=true;
        }catch(Exception failure){report(failure);try{if(actor(player))send(player,"session_error");}catch(Exception ignored){}}
    }
    private static boolean validArgs(SessionRequest r){
        if(r.argA<0||r.argB<0||r.argA>65535||r.argB>65535)return false;
        switch(r.action){case CHOOSE_GEAR:return r.argA<7&&(r.argB==0||choices.get(r.argB)!=null&&choices.get(r.argB).slot==r.argA);case CHOOSE_TEAM:return r.argA<=3&&r.argB==0;case CHOOSE_MODE:return r.argA<=2&&r.argB==0;case SET_READY:case CHOOSE_LANGUAGE:return r.argA<=1&&r.argB==0;case SELECT_PRESET:return r.argB==0&&GearChoices.preset(r.argA)!=null;default:return r.argA==0&&r.argB==0;}
    }
    private static String apply(SessionEngine.Player p,SessionRequest r){
        String id=p.id;ExperienceProtocol.Action action=r.action;
        if(action==ExperienceProtocol.Action.SNAPSHOT)return engine.action(id,"REFRESH","",0,r.revision);
        if(r.revision!=p.revision)return "stale_revision";
        if(action==ExperienceProtocol.Action.CHOOSE_MODE)return engine.action(id,"SET_MODE","",r.argA,r.revision);
        if(action==ExperienceProtocol.Action.CHOOSE_TEAM){int team=r.argA;if(team==3){int blue=0,red=0;for(Object player:inventory.online.values())try{SessionEngine.Player other=engine.player(Reflect.id(player));if(other.mode==2){if(other.team==1)blue++;if(other.team==2)red++;}}catch(Exception ignored){}team=blue<=red?1:2;}return engine.action(id,"SET_TEAM","",team,r.revision);}
        if(action==ExperienceProtocol.Action.CHOOSE_GEAR||action==ExperienceProtocol.Action.SELECT_PRESET){
            if(engine.participant(id))return "round_active";int[] selected=action==ExperienceProtocol.Action.SELECT_PRESET?GearChoices.preset(r.argA):p.choices.clone();if(action==ExperienceProtocol.Action.CHOOSE_GEAR)selected[r.argA]=r.argB;
            Map<String,Integer> selection=choices.resolve(selected);String error=engine.catalog.validate(selection);if(error!=null)return error;for(int choice:selected)if(choice!=0&&!choices.available(choices.get(choice),inventory,engine.catalog))return "item_unavailable";
            String gate=engine.action(id,"CLEAR_SELECTION","",0,r.revision);if(!gate.equals("ok"))return gate;p.selection.putAll(selection);System.arraycopy(selected,0,p.choices,0,7);return "preview";
        }
        if(action==ExperienceProtocol.Action.CONFIRM_GEAR)return engine.action(id,"CONFIRM_EQUIP","",0,r.revision);
        if(action==ExperienceProtocol.Action.KEEP_GEAR)return engine.action(id,"KEEP_GEAR","",0,r.revision);
        if(action==ExperienceProtocol.Action.SET_READY)return engine.action(id,"READY","",r.argA,r.revision);
        if(action==ExperienceProtocol.Action.VOTE_START)return engine.action(id,"VOTE_START","",1,r.revision);
        if(action==ExperienceProtocol.Action.CANCEL_VOTE){if(engine.phase==SessionEngine.COUNTDOWN)return engine.action(id,"CANCEL","",0,r.revision);return engine.action(id,"VOTE_START","",0,r.revision);}
        if(action==ExperienceProtocol.Action.CHOOSE_LANGUAGE){String result=engine.action(id,"LANGUAGE","",r.argA,r.revision);if(result.equals("ok"))try{language(inventory.online.get(id),false);}catch(Exception failure){return "language_error";}return result;}
        if(action==ExperienceProtocol.Action.OPEN_GUIDE){String gate=engine.action(id,"GUIDE","",0,r.revision);if(!gate.equals("guide"))return gate;try{Object player=inventory.online.get(id);Object scoreboard=Reflect.call(player,new String[]{"getWorldScoreboard","func_96123_co"});Object objective=Reflect.call(scoreboard,new String[]{"getObjective","func_96518_b"},"wbook");if(objective==null)return "guide_unavailable";String name=Reflect.call(player,new String[]{"getName","func_70005_c_"}).toString();Object score=Reflect.call(scoreboard,new String[]{"getOrCreateScore","func_96529_a"},name,objective);Reflect.call(score,new String[]{"setScorePoints","func_96647_c"},1);return "guide";}catch(Exception unavailable){return "guide_unavailable";}}
        if(action==ExperienceProtocol.Action.GO_LOBBY||action==ExperienceProtocol.Action.GO_TRAINING){
            if(engine.participant(id))return "round_active";String gate=engine.action(id,"SET_MODE","",action==ExperienceProtocol.Action.GO_TRAINING?1:0,r.revision);if(!gate.equals("ok"))return gate;String moved=inventory.teleport(id,action==ExperienceProtocol.Action.GO_TRAINING?-48:0,65,-210);return moved==null?"moved":moved;
        }
        return "unknown_action";
    }
    public static String snapshot(Object player)throws Exception{return snapshot(player,"ok");}
    private static void language(Object player,boolean initial)throws Exception{
        String id=Reflect.id(player);SessionEngine.Player p=engine.player(id);Object scoreboard=Reflect.call(player,new String[]{"getWorldScoreboard","func_96123_co"});Object objective=Reflect.call(scoreboard,new String[]{"getObjective","func_96518_b"},"wlang");if(objective==null){Object criterion=Reflect.field(Class.forName("net.minecraft.scoreboard.IScoreCriteria"),"DUMMY","field_96641_b");objective=Reflect.call(scoreboard,new String[]{"addScoreObjective","func_96535_a"},"wlang",criterion);}String name=Reflect.call(player,new String[]{"getName","func_70005_c_"}).toString();Object score=Reflect.call(scoreboard,new String[]{"getOrCreateScore","func_96529_a"},name,objective);int current=((Number)Reflect.call(score,new String[]{"getScorePoints","func_96652_c"})).intValue();if(initial&&(current==1||current==2)){p.language=current==1?"ru":"en";return;}Reflect.call(score,new String[]{"setScorePoints","func_96647_c"},p.language.equals("ru")?1:2);
    }
    private static String snapshot(Object player,String result)throws Exception{
        if(!actor(player))throw new IllegalArgumentException("offline");String id=Reflect.id(player);SessionEngine.Player p=engine.player(id);Map<String,Object> internal=engine.snapshot(id,result),data=new LinkedHashMap<String,Object>();
        data.put("protocol",1);data.put("revision",p.revision);data.put("language",p.language);data.put("phase",engine.phase);data.put("mode",p.mode);data.put("players",internal.get("queuedPlayers"));data.put("readyPlayers",internal.get("readyPlayers"));data.put("votes",internal.get("startVotes"));int ready=((Number)internal.get("readyPlayers")).intValue();data.put("votesNeeded",Math.max(2,(ready*2+2)/3));data.put("countdownSeconds",engine.phase==1?internal.get("seconds"):0);data.put("roundSeconds",engine.phase==2?internal.get("seconds"):0);data.put("bluePlayers",internal.get("bluePlayers"));data.put("redPlayers",internal.get("redPlayers"));data.put("team",p.team);data.put("ready",p.ready);data.put("canEditGear",healthy&&!engine.participant(id));data.put("gearConfirmed",p.gearConfirmed);data.put("keepGear",p.keepGear);data.put("freeSlots",inventory.freeSlots(id));data.put("requiredSlots",inventory.requiredSlots(id,p.selection));data.put("budget",GearCatalog.BUDGET);data.put("cost",engine.catalog.points(p.selection));long remaining=Math.max(0,10000-(engine.epoch+engine.tick*50-p.lastEquipEpoch));data.put("cooldownSeconds",p.lastEquipEpoch==0?0:(remaining+999)/1000);data.put("messageCode",result);data.put("catalog",choices.json(inventory,engine.catalog));List<Integer> selected=new ArrayList<Integer>();for(int choice:p.choices)selected.add(choice);data.put("selection",selected);data.put("presets",GearChoices.presets());data.put("inventory",inventory.contents(id));data.put("blueScore",engine.blueScore);data.put("redScore",engine.redScore);data.put("notice",engine.notice);data.put("canReady",healthy&&p.mode==2&&p.team!=0&&p.gearConfirmed&&!engine.participant(id));data.put("canVote",healthy&&p.ready&&engine.phase==0);data.put("canCancel",p.vote&&engine.phase==1);data.put("canTravel",!engine.participant(id));return GSON.toJson(data);
    }
    private static void save()throws Exception{
        if(!healthy||stateFile==null||!dirty)return;Path parent=stateFile.getParent();Files.createDirectories(parent);if(Files.isSymbolicLink(parent)||Files.isSymbolicLink(stateFile))throw new IllegalArgumentException("state_link");byte[] bytes=GSON.toJson(engine.save()).getBytes(StandardCharsets.UTF_8);if(bytes.length>262144)throw new IllegalArgumentException("state_size");Path temporary=parent.resolve("state.json.tmp");Files.write(temporary,bytes);try{Files.move(temporary,stateFile,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);}catch(java.nio.file.AtomicMoveNotSupportedException unsupported){Files.move(temporary,stateFile,StandardCopyOption.REPLACE_EXISTING);}savedRevision=engine.revision;dirty=false;
    }
    public static void registerCommand(Object serverTarget)throws Exception{
        Class<?> type=Class.forName("net.minecraft.command.ICommand");Object command=Proxy.newProxyInstance(type.getClassLoader(),new Class<?>[]{type},new InvocationHandler(){public Object invoke(Object proxy,Method method,Object[] args)throws Throwable{
            String name=method.getName();if(name.equals("getName")||name.equals("func_71517_b"))return "rvx";if(name.equals("getUsage")||name.equals("func_71518_a"))return "/rvx open";if(name.equals("getAliases")||name.equals("func_71514_a")||name.equals("getTabCompletions")||name.equals("func_184883_a"))return Collections.emptyList();if(name.equals("checkPermission")||name.equals("func_184882_a"))return true;if(name.equals("isUsernameIndex")||name.equals("func_82358_a"))return false;if(name.equals("compareTo"))return 0;if(name.equals("hashCode"))return System.identityHashCode(proxy);if(name.equals("equals"))return proxy==args[0];if(name.equals("toString"))return "RV session command";
            if(name.equals("execute")||name.equals("func_184881_a")){Object player=Reflect.call(args[1],new String[]{"getCommandSenderEntity","func_174793_f"});if(!actor(player))return null;String[] values=(String[])args[2];if(values.length<1||values.length>3)return null;SessionEngine.Player p=engine.player(Reflect.id(player));ExperienceProtocol.Action action=ExperienceProtocol.Action.SNAPSHOT;int a=0,b=0;String key=values[0];if(key.equals("team")&&values.length==2){action=ExperienceProtocol.Action.CHOOSE_TEAM;a=Integer.parseInt(values[1]);}else if(key.equals("training"))action=ExperienceProtocol.Action.GO_TRAINING;else if(key.equals("lobby"))action=ExperienceProtocol.Action.GO_LOBBY;else if(key.equals("preset")&&values.length==2){action=ExperienceProtocol.Action.SELECT_PRESET;a=Integer.parseInt(values[1]);}else if(key.equals("language")&&values.length==2){action=ExperienceProtocol.Action.CHOOSE_LANGUAGE;a=Integer.parseInt(values[1]);}else if(!key.equals("open"))return null;handle(player,new SessionRequest(action,a,b,p.revision));return null;}return null;
        }});Object manager=Reflect.call(serverTarget,new String[]{"getCommandManager","func_71187_D"});Reflect.call(manager,new String[]{"registerCommand","func_71560_a"},command);
    }
    public static boolean damageAllowed(Object attacker,Object target){try{return engine.damageAllowed(Reflect.id(attacker),Reflect.id(target));}catch(Exception failure){return true;}}
    public static void death(Object attacker,Object target){try{engine.killed(Reflect.id(attacker),Reflect.id(target));dirty=true;}catch(Exception ignored){}}
    public static void respawn(Object player){try{String id=Reflect.id(player);inventory.online.put(id,player);if(engine.participant(id))inventory.teleport(id,engine.player(id).team==1?-220:220,65,0);send(player,"ok");}catch(Exception failure){report(failure);}}
    private static void report(Throwable error){System.err.println("[RV experience] Server operation rejected: "+error.getClass().getSimpleName());}
}
