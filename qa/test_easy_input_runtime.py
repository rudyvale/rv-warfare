import argparse
import hashlib
import json
from verify_easy_report import validate
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
args=parser.parse_args()
work=ROOT/'.local/qa-1.1.0'/('easy-input-'+uuid.uuid4().hex);work.mkdir(parents=True)
java=args.game/'runtime/bin/java.exe';libraries=list((args.game/'libraries').rglob('*.jar'));asm=next(p for p in libraries if p.name=='asm-debug-all-5.2.jar')
source=work/'RVEasyInputRuntime.java';patch=work/'patch-easy-input-test.js';classes=work/'classes';classes.mkdir()
shutil.copy2(ROOT/'qa/RVEasyInputRuntime.java',source);shutil.copy2(ROOT/'qa/patch-easy-input-test.js',patch)
subprocess.run([str(java),'-jar',str(ROOT/'.local/tools/ecj-4.6.1.jar'),'-1.8','-encoding','UTF-8','-nowarn','-cp',os.pathsep.join([str(args.mcheli),*map(str,libraries)]),'-d',str(classes),str(source)],check=True)
subprocess.run([str(java),'-cp',os.pathsep.join([str(args.game/'runtime/lib/ext/nashorn.jar'),str(asm)]),'jdk.nashorn.tools.Shell',str(patch),'--',str(args.mcheli),str(classes)],check=True)
instrumented=work/'mcheli-easy-test.jar'
allowed={'com/norwood/mcheli/'+p+'.class' for p in ['uav/WarfareQuickUav','vm/VMPilot','vm/VMEasy','MCH_Key','aircraft/MCH_AircraftClientTickHandler','event/MouseInputHandler','networking/packet/control/PacketPlayerControlHeli','helper/client/MCH_CameraManager']}
with zipfile.ZipFile(args.mcheli) as original,zipfile.ZipFile(instrumented,'w',zipfile.ZIP_DEFLATED) as target:
    for entry in original.infolist():
        changed=classes/entry.filename;target.writestr(entry,changed.read_bytes() if changed.is_file() else original.read(entry.filename))
    for helper in classes.glob('RVEasyInputRuntime*.class'):target.write(helper,helper.name)
with zipfile.ZipFile(args.mcheli) as original,zipfile.ZipFile(instrumented) as target:assert {name for name in original.namelist() if original.read(name)!=target.read(name)}==allowed,'Unexpected production member changes'

def link(source,target):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    try:os.link(source,target)
    except OSError:shutil.copy2(source,target)
    return str(target)

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def wait(process,log,predicate,seconds,label):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        content=log.read_text(encoding='utf-8',errors='replace')
        if predicate(content):return
        if process.poll() is not None:raise RuntimeError(label+' exited: '+str(log))
        if 'java.lang.NullPointerException: group' in content:raise RuntimeError('Native Netty bootstrap failure: '+str(log))
        time.sleep(.25)
    raise TimeoutError(label+': '+str(log))

server=work/'server';client=work/'client';server.mkdir();client.mkdir();base=ROOT/'.local/server-base'
shutil.copytree(base/'libraries',server/'libraries',copy_function=link)
for name in ['forge-1.12.2-14.23.5.2860.jar','minecraft_server.1.12.2.jar','eula.txt']:link(base/name,server/name)
techguns=ROOT/'.local/controls/final/techguns-1.12.2-rv.jar'
for directory,mods in [(server,base/'mods'),(client,args.game/'mods')]:
    for mod in mods.glob('*.jar'):
        if not mod.name.startswith(('mcheli','techguns','firstaid','EnhancedVisuals','CreativeCore')):link(mod,directory/'mods'/mod.name)
    shutil.copy2(instrumented,directory/'mods/mcheli-easy-test.jar');link(techguns,directory/'mods'/techguns.name)
    vendor_root=ROOT/'.local/rv-1.1.0/comfort-mods'
    for mod in read(vendor_root/'verified-mods.json')['mods']:
        assert hashlib.sha256((vendor_root/mod['file']).read_bytes()).hexdigest()==mod['sha256'];link(vendor_root/mod['file'],directory/'mods'/mod['file'])
    (directory/'config').mkdir();shutil.copy2(ROOT/'patches/controls/config/firstaid.cfg',directory/'config/firstaid.cfg')
with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
(server/'server.properties').write_text(f'server-ip=127.0.0.1\nserver-port={port}\nonline-mode=false\nlevel-name=EasyTest\nlevel-type=FLAT\ngenerator-settings=3;minecraft:bedrock,2*minecraft:dirt,minecraft:grass;1;\ngenerate-structures=false\nview-distance=4\nmax-players=1\nspawn-protection=0\nspawn-monsters=false\nspawn-animals=false\nallow-flight=true\ngamemode=1\n',encoding='ascii')
shutil.copy2(args.game/'config/mcheli.cfg',client/'config/mcheli.cfg')
(client/'config/vm-controller.properties').write_text('enabled=false\nkeyboardFlight=easy\n')
(client/'config/rv-client.properties').write_text('schema=1\nprofile=low\nlanguage=en\nhudHints=true\nhitFeedback=true\n')
(client/'options.txt').write_text('renderDistance:4\nfancyGraphics:false\nmaxFps:30\nfullscreen:false\npauseOnLostFocus:false\nchatVisibility:2\nsoundCategory_master:0.0\ntutorialStep:none\n')
(client/'optionsshaders.txt').write_text('shaderPack=OFF\n')
downloads=read(args.game/'installer-files.json');classpath=os.pathsep.join(str(args.game/p) for p in downloads['classpath'])
streams=[];processes=[];server_process=None;result={'mcheliSha256':hashlib.sha256(args.mcheli.read_bytes()).hexdigest(),'instrumentedMembers':sorted(allowed),'instrumentedSha256':hashlib.sha256(instrumented.read_bytes()).hexdigest(),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'patchSha256':hashlib.sha256(patch.read_bytes()).hexdigest(),'physicalDeviceTested':False,'nativeInputPipelineTested':False,'cases':{}}

def command(value):server_process.stdin.write(value+'\n');server_process.stdin.flush()

def phase_samples(data,name):return [v for v in data['samples'] if v['phase']==name]

try:
    log=server/'runtime.log';stream=log.open('w',encoding='utf-8');streams.append(stream)
    server_process=subprocess.Popen([str(java),'-Xms256M','-Xmx2G','-Drv.easy.qa=true','-jar','forge-1.12.2-14.23.5.2860.jar','nogui'],cwd=server,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW);result['serverPID']=server_process.pid
    print('Actual Easy input scene '+str(work),flush=True);wait(server_process,log,lambda text:'Done (' in text,180,'server startup')
    client_log=client/'runtime.log';stream=client_log.open('w',encoding='utf-8');streams.append(stream)
    process=subprocess.Popen([str(java),'-Xms256M','-Xmx2048M','-Drv.easy.qa=true','-Drv.easy.server.root='+str(server),'-Djava.library.path='+str(args.game/'natives'),'-cp',classpath,downloads['mainClass'],'--username','RVEasyQA','--version','RV-Easy-QA','--gameDir',str(client),'--assetsDir',str(args.game/'assets'),'--assetIndex',downloads['assetIndex'],'--uuid',uuid.uuid4().hex,'--accessToken','0','--userType','legacy','--tweakClass','net.minecraftforge.fml.common.launcher.FMLTweaker','--server','127.0.0.1','--port',str(port),'--width','640','--height','360'],cwd=client,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);processes.append(process);result['clientPID']=process.pid
    wait(process,client_log,lambda text:'RVEasyQA joined the game' in log.read_text(encoding='utf-8',errors='replace'),180,'native client join')
    for kind in ['movement','fuse']:
        command('time set 6000');command('mcheli rveasysetup'+('fuse' if kind=='fuse' else ''))
        wait(process,client_log,lambda text:(client/f'easy-client-{kind}.json').exists() or (client/'easy-failed.json').exists() or (server/'easy-failed.json').exists(),50,'native Easy '+kind)
        assert not (client/'easy-failed.json').exists() and not (server/'easy-failed.json').exists(),'Native Easy fixture failed'
        wait(server_process,log,lambda text:(server/f'easy-server-{kind}.json').exists(),10,'server Easy report')
        result['cases'][kind]={'server':read(server/f'easy-server-{kind}.json'),'client':read(client/f'easy-client-{kind}.json')}
    evidence=validate(result)
    result['nativeInputPipelineTested']=True;result['passed']=True;print(json.dumps({'passed':True,**evidence},indent=2),flush=True)
finally:
    for process in reversed(processes):
        if process.poll() is None:process.terminate();process.wait(timeout=20)
    if server_process is not None and server_process.poll() is None:
        command('stop')
        try:server_process.wait(timeout=25)
        except subprocess.TimeoutExpired:server_process.terminate();server_process.wait(timeout=10)
    for stream in streams:stream.close()
    result['ownedProcessesStopped']=all(p.poll() is not None for p in processes) and (server_process is None or server_process.poll() is not None)
    (work/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('FINAL '+str(work/'report.json'),flush=True)
