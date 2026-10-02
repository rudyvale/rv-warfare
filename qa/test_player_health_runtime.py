import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--mcheli',type=Path,required=True)
parser.add_argument('--game',type=Path,default=Path(os.environ['LOCALAPPDATA'])/'Warfare-1.12.2')
parser.add_argument('--vendors',type=Path,default=ROOT/'.local/rv-1.1.0/comfort-mods')
parser.add_argument('--baseline',action='store_true')
parser.add_argument('--gui',action='store_true')
args=parser.parse_args()
work=ROOT/'.local/qa-1.1.0'/('player-health-'+uuid.uuid4().hex);work.mkdir(parents=True)
java=args.game/'runtime/bin/java.exe';libraries=list((args.game/'libraries').rglob('*.jar'))
asm=next(path for path in libraries if path.name=='asm-debug-all-5.2.jar')
classes=work/'classes';classes.mkdir();source=work/'RVPlayerDamageRuntime.java';patch=work/'patch-player-health-test.js'
shutil.copy2(ROOT/'qa/RVPlayerDamageRuntime.java',source);shutil.copy2(ROOT/'qa/patch-player-health-test.js',patch)
subprocess.run([str(java),'-jar',str(ROOT/'.local/tools/ecj-4.6.1.jar'),'-1.8','-encoding','UTF-8','-nowarn','-cp',os.pathsep.join([str(args.mcheli),*map(str,libraries)]),'-d',str(classes),str(source)],check=True)
if args.gui:
    gui_source=work/'RVGuiTransformer.java';shutil.copy2(ROOT/'qa/RVGuiTransformer.java',gui_source)
    subprocess.run([str(java),'-jar',str(ROOT/'.local/tools/ecj-4.6.1.jar'),'-1.8','-nowarn','-cp',os.pathsep.join(map(str,libraries)),'-d',str(classes),str(gui_source)],check=True)
subprocess.run([str(java),'-cp',os.pathsep.join([str(args.game/'runtime/lib/ext/nashorn.jar'),str(asm)]),'jdk.nashorn.tools.Shell',str(patch),'--',str(args.mcheli),str(classes),'gui' if args.gui else 'packet'],check=True)
instrumented=work/'mcheli-health-test.jar'
allowed={'com/norwood/mcheli/uav/WarfareQuickUav.class','com/norwood/mcheli/vm/VMPilot.class','com/norwood/mcheli/vm/VMClient.class','com/norwood/mcheli/vm/VMCombat.class'}
if args.gui:allowed.add('com/norwood/mcheli/core/MCHCore.class')
with zipfile.ZipFile(args.mcheli) as original,zipfile.ZipFile(instrumented,'w',zipfile.ZIP_DEFLATED) as target:
    for entry in original.infolist():
        changed=classes/entry.filename;target.writestr(entry,changed.read_bytes() if changed.is_file() else original.read(entry.filename))
    for helper in classes.glob('RV*.class'):target.write(helper,helper.name)
with zipfile.ZipFile(args.mcheli) as original,zipfile.ZipFile(instrumented) as target:
    assert {name for name in original.namelist() if original.read(name)!=target.read(name)}==allowed,'Unexpected production member changes'
vendors=json.loads((args.vendors/'verified-mods.json').read_text(encoding='utf-8'))['mods']
for vendor in vendors:assert hashlib.sha256((args.vendors/vendor['file']).read_bytes()).hexdigest()==vendor['sha256'],'Vendor identity mismatch'
medical=work/'firstaid.cfg';shutil.copy2(ROOT/'patches/controls/config/firstaid.cfg',medical)
server=work/'server';server.mkdir();client_dirs=[work/'actor',work/'victim']
for client in client_dirs:client.mkdir()
base=ROOT/'.local/server-base';techguns=ROOT/'.local/controls/final/techguns-1.12.2-rv.jar';audio=ROOT/'.local/rv-1.1/gameplay/audio/Warfare-Combat-Audio.zip'

def link(source,target):
    source,target=Path(source),Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    try:os.link(source,target)
    except OSError:shutil.copy2(source,target)
    return str(target)

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def wait(process,log,predicate,seconds,label):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        content=log.read_text(encoding='utf-8',errors='replace')
        if predicate(content):return content
        if process.poll() is not None:raise RuntimeError(label+' exited: '+str(log))
        if 'java.lang.NullPointerException: group' in content:raise RuntimeError('Native Netty bootstrap failure: '+str(log))
        time.sleep(.25)
    raise TimeoutError(label+': '+str(log))

def command(value):server_process.stdin.write(value+'\n');server_process.stdin.flush()

shutil.copytree(base/'libraries',server/'libraries',copy_function=link)
for name in ['forge-1.12.2-14.23.5.2860.jar','minecraft_server.1.12.2.jar','eula.txt']:link(base/name,server/name)
for source_mod in (base/'mods').glob('*.jar'):
    if not source_mod.name.startswith(('mcheli','techguns')):link(source_mod,server/'mods'/source_mod.name)
shutil.copy2(instrumented,server/'mods/mcheli-health-test.jar');link(techguns,server/'mods'/techguns.name)
for vendor in vendors:link(args.vendors/vendor['file'],server/'mods'/vendor['file'])
(server/'config').mkdir(exist_ok=True);shutil.copy2(medical,server/'config/firstaid.cfg')
(server/'config/techguns.cfg').write_text('"world generation" {\n B:SpawnStructures=false\n B:SpawnOreClusterStructures=false\n}\n')
with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
(server/'server.properties').write_text(f'server-ip=127.0.0.1\nserver-port={port}\nonline-mode=false\nlevel-name=HealthTest\nlevel-type=FLAT\ngenerator-settings=3;minecraft:bedrock,2*minecraft:dirt,minecraft:grass;1;\ngenerate-structures=false\nview-distance=3\nmax-players=2\nspawn-protection=0\nspawn-monsters=false\nspawn-animals=false\ndifficulty=2\nallow-flight=true\ngamemode=1\npvp=true\n',encoding='ascii')
for client in client_dirs:
    for source_mod in (args.game/'mods').glob('*.jar'):
        if not source_mod.name.startswith(('mcheli','techguns','firstaid','EnhancedVisuals','CreativeCore')):link(source_mod,client/'mods'/source_mod.name)
    shutil.copy2(instrumented,client/'mods/mcheli-health-test.jar');link(techguns,client/'mods'/techguns.name)
    for vendor in vendors:link(args.vendors/vendor['file'],client/'mods'/vendor['file'])
    (client/'config').mkdir();shutil.copy2(args.game/'config/mcheli.cfg',client/'config/mcheli.cfg')
    shutil.copy2(medical,client/'config/firstaid.cfg')
    (client/'config/rv-client.properties').write_text('schema=1\nprofile=low\nlanguage=en\nhudHints=true\nhitFeedback=true\n')
    (client/'options.txt').write_text('renderDistance:3\nfancyGraphics:false\nmaxFps:30\nfullscreen:false\npauseOnLostFocus:false\nchatVisibility:2\nsoundCategory_master:0.0\ntutorialStep:none\nresourcePacks:["Warfare-Combat-Audio.zip"]\n')
    (client/'optionsshaders.txt').write_text('shaderPack=OFF\n');(client/'resourcepacks').mkdir();shutil.copy2(audio,client/'resourcepacks'/audio.name)
downloads=read(args.game/'installer-files.json');classpath=os.pathsep.join(str(args.game/path) for path in downloads['classpath'])
streams=[];processes=[];server_process=None;result={'mcheliSha256':hashlib.sha256(args.mcheli.read_bytes()).hexdigest(),'medicalConfigSha256':hashlib.sha256(medical.read_bytes()).hexdigest(),'vendors':[{key:vendor[key] for key in ['file','sha256','version']} for vendor in vendors],'instrumentedMembers':sorted(allowed),'instrumentedSha256':hashlib.sha256(instrumented.read_bytes()).hexdigest(),'acceptanceSourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'baselineCharacterization':args.baseline,'nativeHealingPacketTested':False,'healingGUIClickTested':False}
try:
    log=server/'runtime.log';stream=log.open('w',encoding='utf-8');streams.append(stream)
    server_process=subprocess.Popen([str(java),'-Xms256M','-Xmx2G','-Drv.player.health.qa=true','-Dlog4j2.formatMsgNoLookups=true','-jar','forge-1.12.2-14.23.5.2860.jar','nogui'],cwd=server,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    result['serverPID']=server_process.pid;print('Actual FirstAid two-client scene '+str(work),flush=True);wait(server_process,log,lambda text:'Done (' in text,180,'server startup');command('gamerule doMobSpawning false')
    for client,nickname in zip(client_dirs,['RVDamageQA','RVVictimQA']):
        client_log=client/'runtime.log';stream=client_log.open('w',encoding='utf-8');streams.append(stream)
        process=subprocess.Popen([str(java),'-Xms256M','-Xmx2048M','-Drv.player.health.qa=true','-Drv.health.gui='+str(args.gui).lower(),'-Drv.health.server.root='+str(server),'-Djava.library.path='+str(args.game/'natives'),'-cp',classpath,downloads['mainClass'],'--username',nickname,'--version','RV-health-QA','--gameDir',str(client),'--assetsDir',str(args.game/'assets'),'--assetIndex',downloads['assetIndex'],'--uuid',uuid.uuid4().hex,'--accessToken','0','--userType','legacy','--tweakClass','net.minecraftforge.fml.common.launcher.FMLTweaker','--server','127.0.0.1','--port',str(port),'--width','640','--height','360'],cwd=client,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(process);result[nickname+'PID']=process.pid
        wait(process,client_log,lambda text:nickname+' joined the game' in log.read_text(encoding='utf-8',errors='replace'),180,'native client join '+nickname)
    command('time set 6000');command('mcheli rvhealthsetup')
    wait(server_process,log,lambda text:(server/'player-health-server.json').exists() or (server/'player-health-failed.json').exists(),45,'native damage and healing matrix')
    assert not (server/'player-health-failed.json').exists(),'Server fixture failure'
    data=read(server/'player-health-server.json');result['server']=data
    for client in client_dirs:assert not (client/'player-health-failed.json').exists(),'Client fixture failure'
    result['actorFeedback']=read(client_dirs[0]/'player-health-feedback.json');result['healingPacket']=read(client_dirs[1]/'healing-packet-client.json');result['nativeHealingPacketTested']=True
    if args.gui:
        proof=read(client_dirs[1]/'healing-gui-client.json');result['nativeGUI']=proof;result['vendorInstrumentedAtLoad']=['ichttt.mods.firstaid.client.gui.GuiHealthScreen','ichttt.mods.firstaid.client.gui.GuiHoldButton']
        assert proof['woundsKey']==35 and proof['woundsReadOnly'] and proof['healingHand']=='MAIN_HAND' and proof['holdMilliseconds']>=2500 and proof['actualMessage']['nativeGUITriggered'],'Actual FirstAid key/right click/native hold flow failed'
        result['healingGUIClickTested']=True;result['physicalMouseTested']=False
    delta=data['beforeShot']['limbSum']-data['afterShot']['limbSum'];assert delta>0 and data['weakProjectileStopped'] and not data['fakePlayer'] and any(hit['victimIdentity'] for hit in data['impacts']),'Native FirstAid damage oracle failed'
    healed=data['afterHealing']['limbSum']-data['afterShot']['limbSum'];assert healed>0 and data['bandageCountAfter']==2,'Native bandage consumption/healing failed'
    assert data['afterCriticalShot']['firstAidDead'] and data['criticalProjectileStopped'],'Native projectile did not cause actual FirstAid critical death'
    if not args.baseline:
        assert result['actorFeedback'][0]['code']==1,'Actual limb damage was shown as no damage'
        assert result['actorFeedback'][-1]['code']==2,'Actual FirstAid critical death was not shown as destroyed'
    result['passed']=True;print(json.dumps({'passed':True,'limbDamage':delta,'healed':healed,'nativeFeedback':result['actorFeedback'],'firstAidDead':data['afterCriticalShot']['firstAidDead'],'limbSumAfterDeath':data['afterCriticalShot']['limbSum']},indent=2),flush=True)
finally:
    for process in reversed(processes):
        if process.poll() is None:process.terminate();process.wait(timeout=20)
    if server_process is not None and server_process.poll() is None:
        command('stop')
        try:server_process.wait(timeout=25)
        except subprocess.TimeoutExpired:server_process.terminate();server_process.wait(timeout=10)
    for stream in streams:stream.close()
    result['ownedProcessesStopped']=all(process.poll() is not None for process in processes) and (server_process is None or server_process.poll() is not None)
    (work/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('FINAL '+str(work/'report.json'),flush=True)
