package rv.experience.client;

import com.norwood.mcheli.vm.VMController;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Properties;
import net.java.games.input.Component;
import net.java.games.input.Controller;

public final class ControlDraft {
    public final Properties profile=new Properties();
    public final VMController scanner=new VMController();
    public final double[] raw=new double[4];
    public Controller device;
    public int stage;
    public String notice="usb";
    public ControlDraft(){synchronized(VMController.INSTANCE){profile.putAll(VMController.INSTANCE.profile);}scan();}
    public void scan(){scanner.scan();device=null;for(Controller c:scanner.devices)if(VMController.identity(c).equals(profile.getProperty("device")))device=c;notice=device==null?"usb":"center";}
    public void nextDevice(){if(scanner.devices.length==0){notice="usb";return;}int i=-1;for(int j=0;j<scanner.devices.length;j++)if(scanner.devices[j]==device)i=j;device=scanner.devices[(i+1)%scanner.devices.length];profile.setProperty("device",VMController.identity(device));profile.setProperty("kind",device.getType()==Controller.Type.GAMEPAD?"gamepad":"radio");for(String action:VMController.ACTIONS){profile.remove(action+".axis");profile.remove(action+".min");profile.remove(action+".max");}stage=0;notice="assign";}
    public boolean flag(String key,String fallback){return Boolean.parseBoolean(profile.getProperty(key,fallback));}
    public void toggle(String key,String fallback){profile.setProperty(key,""+!flag(key,fallback));}
    public Component component(String id){if(device==null||id==null)return null;try{int i=Integer.parseInt(id);Component[] all=device.getComponents();return i>=0&&i<all.length?all[i]:null;}catch(NumberFormatException e){return null;}}
    public List<String> axes(){List<String> list=new ArrayList<String>();if(device!=null){Component[] all=device.getComponents();for(int i=0;i<all.length;i++)if(all[i].isAnalog()&&!all[i].isRelative())list.add(""+i);}return list;}
    public void axis(int index){String a=VMController.ACTIONS[index];List<String> list=axes();if(list.isEmpty())return;int i=list.indexOf(profile.getProperty(a+".axis"));profile.setProperty(a+".axis",list.get((i+1)%list.size()));profile.remove(a+".min");profile.remove(a+".max");stage=0;notice="center";}
    public void button(int index){List<String> list=new ArrayList<String>();list.add("");if(device!=null){Component[] all=device.getComponents();for(int i=0;i<all.length;i++){if(all[i].isRelative())continue;list.add(i+":+");if(all[i].isAnalog())list.add(i+":-");}}String key="button."+VMController.BUTTONS[index];int i=list.indexOf(profile.getProperty(key,""));profile.setProperty(key,list.get((i+1)%list.size()));}
    public String axisLabel(int i){Component c=component(profile.getProperty(VMController.ACTIONS[i]+".axis"));return c==null?"—":profile.getProperty(VMController.ACTIONS[i]+".axis")+" "+c.getName();}
    public void poll(){VMController.INSTANCE.poll(false);if(device==null||!device.poll()){Arrays.fill(raw,0);notice="disconnected";return;}for(int i=0;i<4;i++){String a=VMController.ACTIONS[i];Component c=component(profile.getProperty(a+".axis"));raw[i]=c==null?0:c.getPollData();if(stage==1){profile.setProperty(a+".min",""+Math.min(setting(a+".min",raw[i]),raw[i]));profile.setProperty(a+".max",""+Math.max(setting(a+".max",raw[i]),raw[i]));}}}
    public double setting(String key,double fallback){try{double d=Double.parseDouble(profile.getProperty(key));return Double.isFinite(d)?d:fallback;}catch(Exception e){return fallback;}}
    public boolean valid(){List<String> selected=new ArrayList<String>();for(String a:VMController.ACTIONS){String id=profile.getProperty(a+".axis");Component c=component(id);if(c==null||!c.isAnalog()||c.isRelative()||selected.contains(id))return false;selected.add(id);if(setting(a+".center",0)-setting(a+".min",0)<.08||setting(a+".max",0)-setting(a+".center",0)<.08)return false;}return true;}
    public void calibrate(){poll();if(device==null||!device.poll()){notice="disconnected";return;}if(stage!=1){List<String> selected=new ArrayList<String>();for(int i=0;i<4;i++){String a=VMController.ACTIONS[i],id=profile.getProperty(a+".axis");if(component(id)==null||selected.contains(id)){notice="assign";return;}selected.add(id);for(String suffix:new String[]{"min","center","max"})profile.setProperty(a+"."+suffix,""+raw[i]);}stage=1;notice="range";}else if(valid()){stage=2;notice="calibrated";}else notice="range_missing";}
    public void preset(int id){String[] keys={"deadzone","expo","rate","smoothing","throttleSmoothing","throttleExpo","angleLimit","cameraRoll","throttleRate"};double[][] values={{.06,.5,85,.09,.08,.3,28,.35,.3},{.04,.35,110,.045,.04,.15,35,.55,.44},{.04,.25,190,.025,.025,0,45,.7,.6}};for(int i=0;i<keys.length;i++)profile.setProperty(keys[i],""+values[id][i]);profile.setProperty("flight",id==2?"acro":"angle");notice="preset";}
    public boolean save(){if(flag("enabled","false")&&(device==null||!device.poll()||!valid())){notice="range_missing";return false;}VMController input=VMController.INSTANCE;synchronized(input){Properties before=new Properties();before.putAll(input.profile);input.profile.clear();input.profile.putAll(profile);try{input.save();input.load();notice="saved";return true;}catch(Exception error){input.profile.clear();input.profile.putAll(before);notice="save_failed";return false;}}}
}
