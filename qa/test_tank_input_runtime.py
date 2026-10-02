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
import sys
from runtime_medical_files import stage_medical

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--game',type=Path,default=Path(os.environ['LOCALAPPDATA'])/'Warfare-1.12.2')
parser.add_argument('--mcheli',type=Path,default=ROOT/'.local/controls/final/mcheli-ce-1.5.1-rv.jar')
parser.add_argument('--techguns',type=Path,default=ROOT/'.local/controls/final/techguns-1.12.2-rv.jar')
parser.add_argument('--audio',type=Path,default=Path(os.environ['LOCALAPPDATA'])/'Warfare-1.12.2/resourcepacks/Warfare-Combat-Audio.zip')
parser.add_argument('--work',type=Path,default=ROOT/'.local/qa-1.1.0')
parser.add_argument('--profile',choices=['low','balanced','quality'],default='balanced')
parser.add_argument('--case',choices=['default','remapped','both'],default='both')
parser.add_argument('--baseline',action='store_true')
parser.add_argument('--feedback-matrix',action='store_true')
parser.add_argument('--prepare-only',action='store_true')
parser.add_argument('--native-keys',action='store_true')
args=parser.parse_args()
work=args.work/('input-'+args.profile+'-'+uuid.uuid4().hex)
work.mkdir(parents=True)
java=args.game/'runtime/bin/java.exe'
libraries=list((args.game/'libraries').rglob('*.jar'))
asm=next(path for path in libraries if path.name=='asm-debug-all-5.2.jar')
compiler=ROOT/'.local/tools/ecj-4.6.1.jar'
classes=work/'classes';classes.mkdir()
compile_source=work/'RVTankInputRuntime.java';shutil.copy2(ROOT/'qa/RVTankInputRuntime.java',compile_source)
patch_source=work/'patch-tank-input-test.js';shutil.copy2(ROOT/'qa/patch-tank-input-test.js',patch_source)
compile_cp=os.pathsep.join([str(args.mcheli),*map(str,libraries)])
subprocess.run([str(java),'-jar',str(compiler),'-1.8','-encoding','UTF-8','-nowarn','-cp',compile_cp,'-d',str(classes),str(compile_source)],check=True)
asm_cp=os.pathsep.join([str(args.game/'runtime/lib/ext/nashorn.jar'),str(asm)])
subprocess.run([str(java),'-cp',asm_cp,'jdk.nashorn.tools.Shell',str(patch_source),'--',str(args.mcheli),str(classes)],check=True)
instrumented=work/'mcheli-input-test.jar'
with zipfile.ZipFile(args.mcheli) as original,zipfile.ZipFile(instrumented,'w',zipfile.ZIP_DEFLATED) as target:
    for item in original.infolist():
        replacement=classes/item.filename
        target.writestr(item,replacement.read_bytes() if replacement.is_file() else original.read(item.filename))
    for helper in classes.glob('RVTankInputRuntime*.class'):target.write(helper,helper.name)
allowed={'com/norwood/mcheli/uav/WarfareQuickUav.class','com/norwood/mcheli/vm/VMPilot.class','com/norwood/mcheli/MCH_Key.class','com/norwood/mcheli/tank/MCH_ClientTankTickHandler.class','com/norwood/mcheli/networking/packet/control/PacketPlayerControlBase.class','com/norwood/mcheli/vm/VMCombat.class','com/norwood/mcheli/weapon/MCH_EntityBaseBullet.class'}
allowed.add('com/norwood/mcheli/aircraft/MCH_AircraftClientTickHandler.class')
with zipfile.ZipFile(args.mcheli) as original,zipfile.ZipFile(instrumented) as target:
    for name in ['com/norwood/mcheli/vm/VMClient.class','com/norwood/mcheli/vm/VMFeedback.class']:
        if name in original.namelist():allowed.add(name)
    changed={name for name in original.namelist() if original.read(name)!=target.read(name)}
    assert changed==allowed,changed
if args.prepare_only:
    print(json.dumps({'instrumented':str(instrumented),'originalSha256':hashlib.sha256(args.mcheli.read_bytes()).hexdigest(),'instrumentedMembers':sorted(allowed),'acceptanceSourceSha256':hashlib.sha256(compile_source.read_bytes()).hexdigest(),'instrumentationSourceSha256':hashlib.sha256(patch_source.read_bytes()).hexdigest(),'instrumentedSha256':hashlib.sha256(instrumented.read_bytes()).hexdigest()}),flush=True)
    sys.exit(0)

def link(source,target):
    source,target=Path(source),Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        try:os.link(source,target)
        except OSError:shutil.copy2(source,target)
    return str(target)

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def wait_for(process,log,predicate,seconds,label):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        text=log.read_text(encoding='utf-8',errors='replace')
        if predicate(text):return text
        if label=='client join' and 'java.lang.NullPointerException: group' in text:raise RuntimeError('Native Netty connection bootstrap failed: '+str(log))
        if process.poll() is not None:raise RuntimeError(label+' exited: '+str(log))
        time.sleep(.25)
    raise TimeoutError(label+': '+str(log))

def command(server,text):
    server.stdin.write(text+'\n');server.stdin.flush()

def case(name,key):
    folder=work/name;server=folder/'server';client=folder/'client';server.mkdir(parents=True);client.mkdir()
    base=ROOT/'.local/server-base'
    shutil.copytree(base/'libraries',server/'libraries',copy_function=link)
    for file in ['forge-1.12.2-14.23.5.2860.jar','minecraft_server.1.12.2.jar','eula.txt']:link(base/file,server/file)
    for source in (base/'mods').glob('*.jar'):
        if not source.name.startswith(('mcheli','techguns','firstaid','EnhancedVisuals','CreativeCore')):link(source,server/'mods'/source.name)
    shutil.copy2(instrumented,server/'mods/mcheli-input-test.jar');link(args.techguns,server/'mods/techguns-rv.jar')
    medical=stage_medical(server,args.profile)
    (server/'config/techguns.cfg').write_text('"world generation" {\n B:SpawnStructures=false\n B:SpawnOreClusterStructures=false\n}\n')
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    (server/'server.properties').write_text(f'server-ip=127.0.0.1\nserver-port={port}\nonline-mode=false\nlevel-name=InputTest\nlevel-type=FLAT\ngenerator-settings=3;minecraft:bedrock,2*minecraft:dirt,minecraft:grass;1;\nview-distance=3\nmax-players=2\nspawn-protection=0\nspawn-monsters=false\nspawn-animals=false\nallow-flight=true\ngamemode=1\n',encoding='ascii')
    for source in (args.game/'mods').glob('*.jar'):
        if not source.name.startswith(('mcheli','techguns','firstaid','EnhancedVisuals','CreativeCore')):link(source,client/'mods'/source.name)
    shutil.copy2(instrumented,client/'mods/mcheli-input-test.jar');link(args.techguns,client/'mods/techguns-rv.jar')
    assert stage_medical(client,args.profile)==medical
    shutil.copy2(args.game/'config/mcheli.cfg',client/'config/mcheli.cfg')
    (client/'config/vm-controller.properties').write_text('enabled=false\nflight=angle\n')
    (client/'config/rv-client.properties').write_text(f'schema=1\nprofile={args.profile}\nlanguage=en\nhudHints=true\nhitFeedback=true\n')
    (client/'resourcepacks').mkdir();shutil.copy2(args.audio,client/'resourcepacks'/args.audio.name)
    ui=args.game/'resourcepacks/Warfare-UI-fixes.zip'
    if ui.exists():shutil.copy2(ui,client/'resourcepacks'/ui.name)
    (client/'options.txt').write_text(f'renderDistance:3\nfancyGraphics:false\nmaxFps:60\nfullscreen:false\npauseOnLostFocus:false\nchatVisibility:2\nsoundCategory_master:0.2\nkey_key.attack:{key}\nresourcePacks:["Warfare-UI-fixes.zip","Warfare-Combat-Audio.zip"]\n')
    (client/'optionsshaders.txt').write_text('shaderPack=OFF\n')
    downloads=read(args.game/'installer-files.json')
    client_cp=os.pathsep.join(str(args.game/path) for path in downloads['classpath'])
    server_log=server/'runtime.log';client_log=client/'runtime.log';client_process=None
    started=time.monotonic()
    with server_log.open('w',encoding='utf-8') as server_stream,client_log.open('w',encoding='utf-8') as client_stream:
        server_process=subprocess.Popen([str(java),'-Xms256M','-Xmx2G','-Drv.tank.input.qa=true','-Dlog4j2.formatMsgNoLookups=true','-jar','forge-1.12.2-14.23.5.2860.jar','nogui'],cwd=server,stdin=subprocess.PIPE,stdout=server_stream,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        print('Starting isolated tank input case '+name+'; '+str(folder),flush=True)
        try:
            wait_for(server_process,server_log,lambda text:'Done (' in text,180,'server startup')
            command(server_process,'gamerule doMobSpawning false')
            server_seconds=time.monotonic()-started;client_started=time.monotonic()
            client_process=subprocess.Popen([str(java),'-Xms256M','-Xmx2048M','-Drv.tank.input.qa=true','-Drv.qa.native.keys='+str(args.native_keys).lower(),'-Drv.qa.profile='+args.profile,'-Dlog4j2.formatMsgNoLookups=true','-Djava.library.path='+str(args.game/'natives'),'-cp',client_cp,downloads['mainClass'],'--username','RVTankQA','--version','RV-input-QA','--gameDir',str(client),'--assetsDir',str(args.game/'assets'),'--assetIndex',downloads['assetIndex'],'--uuid','a735f1a045e4471c99426b651bf267c8','--accessToken','0','--userType','legacy','--tweakClass','net.minecraftforge.fml.common.launcher.FMLTweaker','--server','127.0.0.1','--port',str(port),'--width','640','--height','360'],cwd=client,stdout=client_stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            wait_for(client_process,client_log,lambda text:'RVTankQA' in server_log.read_text(encoding='utf-8',errors='replace') and 'joined the game' in server_log.read_text(encoding='utf-8',errors='replace'),180,'client join')
            client_seconds=time.monotonic()-client_started
            command(server_process,'time set 6000')
            command(server_process,'mcheli rvtankinputsetup')
            wait_for(client_process,client_log,lambda text:(client/'tank-input-client.json').exists() or (client/'tank-input-failed.json').exists() or (server/'tank-input-failed.json').exists(),40,'native input scenario')
            assert not (client/'tank-input-failed.json').exists() and not (server/'tank-input-failed.json').exists(),'QA runtime exception; inspect logs'
            controls=None
            if args.native_keys:
                assert not args.feedback_matrix,'Run key workflow separately from feedback timing matrix'
                wait_for(client_process,client_log,lambda text:(client/'native-controls-client.json').exists() or (client/'tank-input-failed.json').exists(),15,'native key workflow')
                assert not (client/'tank-input-failed.json').exists(),'Native key fixture error'
                controls=read(client/'native-controls-client.json')
                states={value['name']:value for value in controls['states']}
                assert states['after-ctrl-c']['gunnerStatus']!=states['before']['gunnerStatus'],'Ctrl+C did not toggle native gunner status'
                assert states['after-z-with-status']['cameraZoom']>states['before']['cameraZoom'],'Z did not zoom from the native M1A2 default camera'
                assert states['after-z-with-gunner']['cameraZoom']>states['after-h']['cameraZoom'],'Z did not zoom in native gunner camera'
                assert states['after-g']['weapon']!=states['after-z-with-gunner']['weapon'],'G did not select another native weapon'
                assert states['after-i']['gui'] in ['com.norwood.mcheli.aircraft.MCH_AircraftGui','com.cleanroommc.modularui.screen.GuiContainerWrapper'],'I did not open native aircraft inventory'
                assert not states['after-y']['mounted'],'Y did not unmount through native controls'
            matrix_result=None
            if args.feedback_matrix:
                command(server_process,'mcheli rvtankinputfeedback')
                wait_for(server_process,server_log,lambda text:(server/'feedback-matrix-server.json').exists() or (server/'tank-input-failed.json').exists(),15,'server feedback matrix')
                assert not (server/'tank-input-failed.json').exists(),'server feedback matrix exception'
                wait_for(client_process,client_log,lambda text:(client/'feedback-matrix-client.json').exists() and len(read(client/'feedback-matrix-client.json')['events'])>=4,5,'client feedback matrix')
                matrix_result={'server':read(server/'feedback-matrix-server.json'),'client':read(client/'feedback-matrix-client.json'),'packets':read(client/'feedback-packets-client.json')}
                values=matrix_result['server']['cases'];events=matrix_result['packets']['events'][1:]
                fractional=values[0];delta=fractional['healthBefore']-fractional['healthAfter']
                assert 0<delta<1 and fractional['projectileDead'] and fractional['notifications']==1,'Actual native fractional living HP scenario failed'
                assert events[0]['code']==1 and events[0]['damageTenths']==int(delta*10+.5) and 'DAMAGE' in matrix_result['client']['events'][1]['label'],'Fractional HP damage was shown as contact/no damage'
                assert values[1]['healthBefore']==values[1]['healthAfter'] and values[1]['projectileDead'] and values[1]['notifications']==1,'Armour contact oracle failed'
                assert events[1]['code']==0 and events[1]['damageTenths']==0 and 'no damage' in matrix_result['client']['events'][2]['label'],'Blocked round was shown as damage'
                assert values[2]['notifications']==0,'A miss sent hit feedback'
                assert values[3]['healthAfter']<=0 and values[3]['targetDestroyed'] and values[3]['projectileDead'] and 1<=values[3]['notifications']<=2,'Native tank destruction oracle failed'
                destruction=events[2:]
                assert destruction[-1]['code']==2 and matrix_result['client']['events'][-1]['label']=='DESTROYED','Destruction feedback missing'
                assert len(destruction)==values[3]['notifications'] and all(a['code']<b['code'] for a,b in zip(destruction,destruction[1:])),'Repeated feedback did not increase result severity'
            command(server_process,'mcheli rvtankinputfinish')
            wait_for(server_process,server_log,lambda text:(server/'tank-input-server.json').exists(),10,'server report')
            native=read(server/'tank-input-server.json');local=read(client/'tank-input-client.json')
            fired=native['weaponPackets']>0 and native['projectilesCreated']>0 and native['finalHP']<native['initialHP'] and native['observedProjectileStopped']
            assert native['packets']>0,'No actual native client/server control traffic'
            assert not native['qaObserverErrors'],'QA particle observer failed'
            assert local['configuredAttackKey']==key,'Minecraft did not load the configured attack binding'
            if name=='default' or not args.baseline:assert fired,'Configured input did not create a stopped projectile with real target damage'
            elif args.baseline:assert not fired and native['weaponPackets']==0 and native['finalHP']==native['initialHP'],'Expected baseline remap characterization changed'
            assert len(local['effectSamples'])>=20,'Effect measurement scenario did not finish'
            if not args.baseline:
                assert local['feedbackEvents'],'No actual server-confirmed feedback received'
                event=local['feedbackEvents'][0]
                assert event['code']==1 and event['damageTenths']==10*(native['initialHP']-native['finalHP']),'HUD damage disagrees with real server HP delta'
                assert (client/'screenshots/tank-hit.png').is_file(),'Native HUD screenshot missing'
                assert native['particlePacketsSent'] and any(packet['type']=='FIREWORKS_SPARK' for packet in native['particlePacketsSent']),'No real server impact spark packets reached the network handler'
                assert '[VM impact feedback]' not in server_log.read_text(encoding='utf-8',errors='replace') and '[VM armour impact feedback]' not in server_log.read_text(encoding='utf-8',errors='replace'),'Native server impact effect failed'
            assert local['maxHeapBytes']<=2147483648,'Client heap limit was not applied'
            assert 'OutOfMemoryError' not in client_log.read_text(encoding='utf-8',errors='replace'),'Client exhausted the 2048M heap'
            result={'name':name,'passed':True,'fired':fired,'server':native,'client':local,'feedbackMatrix':matrix_result,'nativeControls':controls,'medical':medical,'serverStartupSeconds':round(server_seconds,3),'clientJoinSeconds':round(client_seconds,3),'root':str(folder)}
            (folder/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'case':name,'passed':True,'fired':fired,'hp':[native['initialHP'],native['finalHP']],'projectiles':native['projectilesCreated'],'nativeFireKey':local['nativeTankFireKey'],'configuredKey':key,'clientJoinSeconds':result['clientJoinSeconds'],'clientUsedHeapMB':round(local['usedHeapBytes']/1048576)},indent=2),flush=True)
            return result
        finally:
            if client_process is not None and client_process.poll() is None:client_process.terminate();client_process.wait(timeout=20)
            if server_process.poll() is None:
                command(server_process,'stop')
                try:server_process.wait(timeout=25)
                except subprocess.TimeoutExpired:server_process.terminate();server_process.wait(timeout=10)

cases=[]
for name,key in [('default',-100),('remapped',33)]:
    if args.case in ('both',name):cases.append(case(name,key))
report={'passed':all(item['passed'] for item in cases),'mcheliSha256':hashlib.sha256(args.mcheli.read_bytes()).hexdigest(),'techgunsSha256':hashlib.sha256(args.techguns.read_bytes()).hexdigest(),'audioSha256':hashlib.sha256(args.audio.read_bytes()).hexdigest(),'acceptanceSourceSha256':hashlib.sha256(compile_source.read_bytes()).hexdigest(),'instrumentationSourceSha256':hashlib.sha256(patch_source.read_bytes()).hexdigest(),'instrumentedSha256':hashlib.sha256(instrumented.read_bytes()).hexdigest(),'instrumentedMembers':sorted(allowed),'profile':args.profile,'baselineCharacterization':args.baseline,'physicalInputDeviceTested':False,'physicalWeakComputerTested':False,'cases':cases}
(work/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FINAL '+str(work/'report.json'),flush=True)
