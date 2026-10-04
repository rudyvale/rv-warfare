package rv.experience.server;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

public final class SessionEngine {
    public static final int FREEPLAY=0, TRAINING=1, TEAM_ROUND=2;
    public static final int LOBBY=0, COUNTDOWN=1, ACTIVE=2;
    public interface Inventory {
        String audit(String player,Map<String,Integer> selection);
        String equip(String player,Map<String,Integer> selection);
        List<Map<String,Object>> contents(String player);
        boolean available(String item);
        String roundStarted(Map<String,Integer> teams);
    }
    public static final class Player {
        public final String id;
        public int mode=FREEPLAY, team, kills;
        public boolean online, ready, vote;
        public boolean gearConfirmed, keepGear;
        public String language="ru";
        public final int[] choices=new int[7];
        public long revision, lastEquip=-1000000, lastAction=-1000000;
        public long lastEquipEpoch;
        public int burst;
        public final Map<String,Integer> selection=new LinkedHashMap<String,Integer>();
        Player(String id) {this.id=id;this.revision=System.nanoTime()&0x1fffffffffffffffL;}
    }
    public final GearCatalog catalog=new GearCatalog();
    private final Map<String,Player> players=new LinkedHashMap<String,Player>();
    private final Set<String> participants=new LinkedHashSet<String>();
    private final Inventory inventory;
    public int phase=LOBBY, blueScore, redScore;
    public long tick, deadline, round, revision;
    public final long epoch=System.currentTimeMillis();
    public String notice="welcome";
    public SessionEngine(Inventory inventory) {this.inventory=inventory;}
    public Player player(String id) {
        UUID.fromString(id);
        Player result=players.get(id);
        if(result==null){if(players.size()>=256)throw new IllegalStateException("player_limit");result=new Player(id);players.put(id,result);}
        return result;
    }
    public void join(String id) {Player p=player(id);p.online=true;p.ready=false;p.vote=false;p.revision++;revision++;}
    public void leave(String id) {Player p=players.get(id);if(p==null)return;p.online=false;p.ready=false;p.vote=false;p.revision++;if(phase==COUNTDOWN&&participants.contains(id))cancel("player_left");if(phase==ACTIVE){participants.remove(id);if(!bothTeams())cancel("team_empty");}revision++;}
    public Set<String> participantIds() {return Collections.unmodifiableSet(participants);}
    public boolean participant(String id) {return phase==ACTIVE&&participants.contains(id);}
    public boolean damageAllowed(String attacker,String target) {
        boolean a=participant(attacker),b=participant(target);
        if(!a&&!b)return true;
        return a&&b&&player(attacker).team!=player(target).team;
    }
    public void killed(String killer,String victim) {if(!damageAllowed(killer,victim)||!participant(killer)||killer.equals(victim))return;Player p=player(killer);p.kills++;if(p.team==1)blueScore++;else redScore++;revision++;if(blueScore>=20||redScore>=20)cancel("score_limit");}
    private void changed(Player p) {p.revision++;revision++;}
    private void invalidate(Player p) {p.ready=false;p.vote=false;if(phase==COUNTDOWN&&participants.contains(p.id))cancel("choice_changed");changed(p);}
    private boolean bothTeams() {boolean blue=false,red=false;for(String id:participants){Player p=players.get(id);if(p!=null&&p.online){blue|=p.team==1;red|=p.team==2;}}return blue&&red;}
    public void cancel(String reason) {phase=LOBBY;deadline=0;notice=reason;for(String id:participants){Player p=players.get(id);if(p!=null){p.ready=false;p.vote=false;changed(p);}}participants.clear();revision++;}
    public String action(String id,String action,String value,int amount,long expected) {
        Player p=player(id);
        if(!p.online)return "offline";
        if(action==null||action.length()>32||value==null||value.length()>64)return "invalid_request";
        if(tick-p.lastAction>=5)p.burst=0;
        if(p.burst>=4)return "rate_limited";
        p.burst++;p.lastAction=tick;
        if(action.equals("OPEN")||action.equals("REFRESH"))return "ok";
        if(expected!=p.revision)return "stale_revision";
        if(action.equals("GUIDE"))return "guide";
        if(action.equals("LANGUAGE")){if(amount<0||amount>1)return "invalid_language";p.language=amount==0?"ru":"en";changed(p);return "ok";}
        boolean locked=phase==ACTIVE&&participants.contains(id);
        if(locked)return "round_active";
        if(action.equals("LEAVE")){leave(id);p.online=true;p.mode=FREEPLAY;changed(p);return "left";}
        if(action.equals("SET_MODE")){
            if(amount<0||amount>2)return "unknown_mode";
            invalidate(p);p.mode=amount;if(amount!=TEAM_ROUND)p.team=0;return "ok";
        }
        if(action.equals("SET_TEAM")){
            if(p.mode!=TEAM_ROUND||amount<1||amount>2)return "invalid_team";
            invalidate(p);p.team=amount;return "ok";
        }
        if(action.equals("SELECT_ITEM")){
            GearCatalog.Entry e=catalog.get(value);if(e==null||!inventory.available(e.item))return "item_unavailable";
            Map<String,Integer> next=new LinkedHashMap<String,Integer>(p.selection);
            if(amount==0)next.remove(value);else next.put(value,amount);
            String error=catalog.validate(next);if(error!=null)return error;
            invalidate(p);p.gearConfirmed=false;p.keepGear=false;p.selection.clear();p.selection.putAll(next);return "ok";
        }
        if(action.equals("CLEAR_SELECTION")){invalidate(p);p.gearConfirmed=false;p.keepGear=false;p.selection.clear();return "ok";}
        if(action.equals("KEEP_GEAR")){invalidate(p);p.selection.clear();java.util.Arrays.fill(p.choices,0);p.gearConfirmed=true;p.keepGear=true;return "gear_kept";}
        if(action.equals("PREVIEW"))return "preview";
        if(action.equals("CONFIRM_EQUIP")){
            if(p.selection.isEmpty())return "selection_empty";
            if(tick-p.lastEquip<200||p.lastEquipEpoch>0&&epoch+tick*50-p.lastEquipEpoch<10000)return "equip_cooldown";
            String error=catalog.validate(p.selection);if(error!=null)return error;
            error=inventory.equip(id,new LinkedHashMap<String,Integer>(p.selection));if(error!=null)return error;
            invalidate(p);p.gearConfirmed=true;p.keepGear=false;p.lastEquip=tick;p.lastEquipEpoch=epoch+tick*50;return "equipped";
        }
        if(action.equals("READY")){
            if(p.mode!=TEAM_ROUND||p.team==0)return "choose_team";
            if(!p.gearConfirmed)return "gear_unconfirmed";
            if(amount==0){invalidate(p);return "not_ready";}
            if(amount!=1)return "invalid_ready";
            String error=inventory.audit(id,p.selection);if(error!=null)return error;
            p.ready=true;changed(p);return "ready";
        }
        if(action.equals("VOTE_START")){
            if(p.mode!=TEAM_ROUND||!p.ready)return "not_ready";
            if(amount<0||amount>1)return "invalid_vote";
            p.vote=amount==1;changed(p);tryCountdown();return phase==COUNTDOWN?"countdown":"vote_recorded";
        }
        if(action.equals("CANCEL")){
            if(phase!=COUNTDOWN||!participants.contains(id))return "no_countdown";
            cancel("player_cancelled");return "cancelled";
        }
        return "unknown_action";
    }
    private void tryCountdown() {
        if(phase!=LOBBY)return;
        List<Player> ready=new ArrayList<Player>();int votes=0,blue=0,red=0;
        for(Player p:players.values())if(p.online&&p.mode==TEAM_ROUND&&p.ready){ready.add(p);if(p.vote)votes++;if(p.team==1)blue++;else if(p.team==2)red++;}
        if(ready.size()<2||blue==0||red==0||Math.abs(blue-red)>1||votes<(ready.size()*2+2)/3)return;
        participants.clear();for(Player p:ready)participants.add(p.id);
        phase=COUNTDOWN;deadline=tick+200;notice="countdown";revision++;
    }
    public void advance() {
        tick++;
        if(phase==COUNTDOWN){
            for(String id:new ArrayList<String>(participants)){Player p=players.get(id);if(p==null||!p.online||!p.ready||inventory.audit(id,p.selection)!=null){cancel("loadout_changed");return;}}
            if(tick>=deadline){Map<String,Integer> teams=new LinkedHashMap<String,Integer>();for(String id:participants)teams.put(id,players.get(id).team);String error=inventory.roundStarted(teams);if(error!=null){cancel(error);return;}phase=ACTIVE;deadline=tick+12000;round++;blueScore=0;redScore=0;notice="round_started";for(String id:participants){Player p=players.get(id);p.kills=0;changed(p);}}
        } else if(phase==ACTIVE&&tick>=deadline)cancel("time_limit");
    }
    public Map<String,Object> snapshot(String id,String result) {
        Player p=player(id);Map<String,Object> data=new LinkedHashMap<String,Object>();
        data.put("schema",1);data.put("revision",p.revision);data.put("sessionRevision",revision);data.put("mode",p.mode);data.put("team",p.team);data.put("ready",p.ready);data.put("vote",p.vote);data.put("phase",phase);data.put("round",round);data.put("seconds",Math.max(0,(deadline-tick+19)/20));data.put("result",result);data.put("notice",notice);data.put("blueScore",blueScore);data.put("redScore",redScore);data.put("kills",p.kills);data.put("budget",GearCatalog.BUDGET);data.put("points",catalog.points(p.selection));data.put("selection",new LinkedHashMap<String,Integer>(p.selection));data.put("inventory",inventory.contents(id));data.put("participating",participants.contains(id));data.put("equipCooldown",Math.max(0,(200-(tick-p.lastEquip)+19)/20));
        int queued=0,ready=0,votes=0,blue=0,red=0;
        for(Player other:players.values())if(other.online&&other.mode==TEAM_ROUND){queued++;if(other.ready)ready++;if(other.vote)votes++;if(other.team==1)blue++;if(other.team==2)red++;}
        data.put("queuedPlayers",queued);data.put("readyPlayers",ready);data.put("startVotes",votes);data.put("bluePlayers",blue);data.put("redPlayers",red);
        List<Map<String,Object>> available=new ArrayList<Map<String,Object>>();for(GearCatalog.Entry e:catalog.all())if(inventory.available(e.item))available.add(e.json());data.put("catalog",available);return data;
    }
    public Map<String,Object> save() {
        Map<String,Object> result=new LinkedHashMap<String,Object>();result.put("schema",1);result.put("round",round);result.put("interrupted",phase!=LOBBY);
        Map<String,Object> prefs=new LinkedHashMap<String,Object>();
        for(Player p:players.values()){Map<String,Object> data=new LinkedHashMap<String,Object>();data.put("mode",p.mode);data.put("team",p.team);data.put("language",p.language);data.put("lastEquipEpoch",p.lastEquipEpoch);List<Integer> choices=new ArrayList<Integer>();for(int choice:p.choices)choices.add(choice);data.put("choices",choices);data.put("selection",new LinkedHashMap<String,Integer>(p.selection));prefs.put(p.id,data);}result.put("players",prefs);return result;
    }
    @SuppressWarnings("unchecked")
    public void load(Map<String,Object> data) {
        if(data==null||!(data.get("schema") instanceof Number)||((Number)data.get("schema")).intValue()!=1)throw new IllegalArgumentException("state_schema");
        Object saved=data.get("players");if(!(saved instanceof Map)||((Map<?,?>)saved).size()>256)throw new IllegalArgumentException("state_players");
        for(Map.Entry<?,?> item:((Map<?,?>)saved).entrySet()){
            String id=(String)item.getKey();UUID.fromString(id);if(!(item.getValue() instanceof Map))throw new IllegalArgumentException("state_player");Map<String,Object> value=(Map<String,Object>)item.getValue();Player p=player(id);
            int mode=((Number)value.get("mode")).intValue(),team=((Number)value.get("team")).intValue();if(mode<0||mode>2||team<0||team>2)throw new IllegalArgumentException("state_choice");p.mode=mode;p.team=team;
            Object language=value.get("language");if(language!=null&&!language.equals("ru")&&!language.equals("en"))throw new IllegalArgumentException("state_language");if(language!=null)p.language=(String)language;
            if(value.get("lastEquipEpoch") instanceof Number){long savedAt=((Number)value.get("lastEquipEpoch")).longValue();if(savedAt<0||savedAt>epoch+300000)throw new IllegalArgumentException("state_cooldown");p.lastEquipEpoch=savedAt;}
            Object choices=value.get("choices");if(!(choices instanceof List)||((List<?>)choices).size()!=7)throw new IllegalArgumentException("state_choices");for(int i=0;i<7;i++){Object choice=((List<?>)choices).get(i);if(!(choice instanceof Number))throw new IllegalArgumentException("state_choice");p.choices[i]=((Number)choice).intValue();}
            Object choice=value.get("selection");if(!(choice instanceof Map))throw new IllegalArgumentException("state_selection");Map<String,Integer> selection=new LinkedHashMap<String,Integer>();for(Map.Entry<?,?> entry:((Map<?,?>)choice).entrySet()){if(!(entry.getKey() instanceof String)||!(entry.getValue() instanceof Number))throw new IllegalArgumentException("state_item");selection.put((String)entry.getKey(),((Number)entry.getValue()).intValue());}if(catalog.validate(selection)!=null)throw new IllegalArgumentException("state_budget");p.selection.putAll(selection);
        }
        if(data.get("round") instanceof Number)round=Math.max(0,((Number)data.get("round")).longValue());
        phase=LOBBY;participants.clear();notice=Boolean.TRUE.equals(data.get("interrupted"))?"restart_cancelled":"welcome";
    }
}
