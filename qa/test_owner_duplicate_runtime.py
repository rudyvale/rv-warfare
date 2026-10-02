import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import uuid
from runtime_medical_files import stage_medical

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--mcheli',type=Path,required=True)
parser.add_argument('--game',type=Path,default=Path(os.environ['LOCALAPPDATA'])/'Warfare-1.12.2')
parser.add_argument('--expect-protected',action='store_true')
parser.add_argument('--public-policy-absent',action='store_true')
args=parser.parse_args()
work=ROOT/'.local/qa-1.1.0'/('owner-duplicate-'+uuid.uuid4().hex)
work.mkdir(parents=True)
checker=ROOT/'host/Check-OwnerConnection.ps1'
checker_sha=hashlib.sha256(checker.read_bytes()).hexdigest()
assert checker_sha=='6029a7277df332ee79b8e93f49fc302f1e6c356fe3f9a617c69444f6a151d166','Owner checker changed'
prepared=subprocess.run([sys.executable,str(ROOT/'qa/test_tank_input_runtime.py'),'--mcheli',str(args.mcheli),'--work',str(work),'--prepare-only'],check=True,capture_output=True,text=True)
identity=json.loads(prepared.stdout.strip().splitlines()[-1]);instrumented=Path(identity['instrumented'])
java=args.game/'runtime/bin/java.exe'
base=ROOT/'.local/server-base'
server=work/'server';server.mkdir()
clients=[work/'trusted',work/'untrusted']
for client in clients:client.mkdir()

def link(source,target):
    source,target=Path(source),Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    try:os.link(source,target)
    except OSError:shutil.copy2(source,target)
    return str(target)

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def wait(process,log,predicate,seconds,label):
    limit=time.monotonic()+seconds
    while time.monotonic()<limit:
        content=log.read_text(encoding='utf-8',errors='replace')
        if predicate(content):return content
        if process.poll() is not None:raise RuntimeError(label+' exited: '+str(log))
        if 'java.lang.NullPointerException: group' in content:raise RuntimeError('Native Netty bootstrap failed: '+str(log))
        time.sleep(.25)
    raise TimeoutError(label+': '+str(log))

def command(text):server_process.stdin.write(text+'\n');server_process.stdin.flush()

shutil.copytree(base/'libraries',server/'libraries',copy_function=link)
for name in ['forge-1.12.2-14.23.5.2860.jar','minecraft_server.1.12.2.jar','eula.txt']:link(base/name,server/name)
for source in (base/'mods').glob('*.jar'):
    if not source.name.startswith(('mcheli','techguns','firstaid','EnhancedVisuals','CreativeCore')):link(source,server/'mods'/source.name)
shutil.copy2(instrumented,server/'mods/mcheli-owner-test.jar')
techguns=ROOT/'.local/controls/final/techguns-1.12.2-rv.jar'
link(techguns,server/'mods'/techguns.name)
medical=stage_medical(server)
(server/'config/techguns.cfg').write_text('"world generation" {\n B:SpawnStructures=false\n B:SpawnOreClusterStructures=false\n}\n')
with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
(server/'server.properties').write_text(f'server-ip=127.0.0.1\nserver-port={port}\nonline-mode=false\nlevel-name=OwnerTest\nlevel-type=FLAT\ngenerator-settings=3;minecraft:bedrock,2*minecraft:dirt,minecraft:grass;1;\nview-distance=3\nmax-players=2\nspawn-protection=0\nspawn-monsters=false\nspawn-animals=false\nallow-flight=true\n',encoding='ascii')
shutil.copy2(checker,server/checker.name)
if not args.public_policy_absent:
    (server/'vm-owner.properties').write_text('nickname=Owner_1\nscript=Check-OwnerConnection.ps1\n',encoding='ascii')
    (server/'vm-owner.json').write_text(json.dumps({'nickname':'Owner_1','serverPort':port,'allowedGameDirs':[str(clients[0].resolve())]}),encoding='utf-8')
for client in clients:
    for source in (args.game/'mods').glob('*.jar'):
        if not source.name.startswith(('mcheli','techguns','firstaid','EnhancedVisuals','CreativeCore')):link(source,client/'mods'/source.name)
    shutil.copy2(instrumented,client/'mods/mcheli-owner-test.jar')
    link(techguns,client/'mods'/techguns.name)
    assert stage_medical(client)==medical
    shutil.copy2(args.game/'config/mcheli.cfg',client/'config/mcheli.cfg')
    (client/'options.txt').write_text('renderDistance:3\nfancyGraphics:false\nmaxFps:30\nfullscreen:false\npauseOnLostFocus:false\nchatVisibility:2\nsoundCategory_master:0.0\ntutorialStep:none\n')
    (client/'optionsshaders.txt').write_text('shaderPack=OFF\n')
downloads=read(args.game/'installer-files.json');classpath=os.pathsep.join(str(args.game/path) for path in downloads['classpath'])
processes=[];streams=[];server_process=None;result={'checkerSha256':checker_sha,'mcheliSha256':identity['originalSha256'],'techgunsSha256':hashlib.sha256(techguns.read_bytes()).hexdigest(),'medical':medical,'instrumentedMembers':identity['instrumentedMembers'],'instrumentedSha256':identity['instrumentedSha256'],'singleDuplicateAttempt':True,'serverLoopbackOnly':True,'fixtureNickname':'Owner_1'}
try:
    server_log=server/'runtime.log';stream=server_log.open('w',encoding='utf-8');streams.append(stream)
    server_process=subprocess.Popen([str(java),'-Xms256M','-Xmx2G','-Drv.tank.input.qa=true','-Dlog4j2.formatMsgNoLookups=true','-jar','forge-1.12.2-14.23.5.2860.jar','nogui'],cwd=server,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    result['serverPID']=server_process.pid
    print('Isolated owner duplicate fixture '+str(work),flush=True)
    wait(server_process,server_log,lambda text:'Done (' in text,180,'server startup')
    for index,client in enumerate(clients[:1] if args.public_policy_absent else clients):
        log=client/'runtime.log';stream=log.open('w',encoding='utf-8');streams.append(stream)
        process=subprocess.Popen([str(java),'-Xms256M','-Xmx2048M','-Drv.tank.input.qa=true','-Dlog4j2.formatMsgNoLookups=true','-Djava.library.path='+str(args.game/'natives'),'-cp',classpath,downloads['mainClass'],'--username','Owner_1','--version','RV-owner-QA','--gameDir',str(client),'--assetsDir',str(args.game/'assets'),'--assetIndex',downloads['assetIndex'],'--uuid','61357df26ea748be90e24b5a7ba5b05c','--accessToken','0','--userType','legacy','--tweakClass','net.minecraftforge.fml.common.launcher.FMLTweaker','--server','127.0.0.1','--port',str(port),'--width','640','--height','360'],cwd=client,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(process);result[('trustedPID','untrustedPID')[index]]=process.pid
        if index==0:
            wait(process,log,lambda text:('Owner_1' in server_log.read_text(encoding='utf-8',errors='replace') and 'joined the game' in server_log.read_text(encoding='utf-8',errors='replace')) if args.public_policy_absent else '[RV owner] verified local session' in server_log.read_text(encoding='utf-8',errors='replace'),180,'public join' if args.public_policy_absent else 'trusted actual TCP/CIM verification')
            command('mcheli rvtankinputauthbefore')
            wait(server_process,server_log,lambda text:(server/'owner-duplicate-before.json').exists() or (server/'tank-input-failed.json').exists(),5,'trusted native snapshot')
            assert not (server/'tank-input-failed.json').exists(),'Native trusted snapshot failed'
            result['before']=read(server/'owner-duplicate-before.json')
            assert result['before']['currentIsOld'] and result['before']['oldChannelOpen'],'Native first client not alive'
            if args.public_policy_absent:
                assert not result['before']['currentOperator'] and not result['before']['currentOwnerTag'],'Public policy absent unexpectedly granted operator'
                result.update({'passed':True,'publicPolicyAbsentCompatibility':True,'singleDuplicateAttempt':False});break
            assert result['before']['currentOperator'] and result['before']['currentOwnerTag'],'Trusted owner fixture was not verified and native operator'
            print('Actual trusted session verified; starting one owned untrusted duplicate login.',flush=True)
        else:
            wait(process,log,lambda text:any(marker in server_log.read_text(encoding='utf-8',errors='replace') for marker in ['[RV owner] operator denied','[RV owner] login denied before player admission']) or 'Owner verification failed' in text,180,'single duplicate denial')
            time.sleep(2)
            command('mcheli rvtankinputauthafter')
            wait(server_process,server_log,lambda text:(server/'owner-duplicate-after.json').exists() or (server/'tank-input-failed.json').exists(),5,'post duplicate native snapshot')
            assert not (server/'tank-input-failed.json').exists(),'Native post duplicate snapshot failed'
            result['after']=read(server/'owner-duplicate-after.json')
            result['oldSessionPreserved']=result['after']['oldChannelOpen'] and result['after']['currentIsOld'] and result['after']['currentOperator']
            result['untrustedHasNoOperator']=result['after']['currentIsOld'] or not result['after']['currentOperator']
            result['oldKickedByVanillaDuplicate']='You logged in from another location' in server_log.read_text(encoding='utf-8',errors='replace')
            result['untrustedStillConnected']=result['after']['currentPresent'] and not result['after']['currentIsOld'] and result['after']['currentChannelOpen']
            result['preloginRefused']='[RV owner] login denied before player admission' in server_log.read_text(encoding='utf-8',errors='replace')
            assert result['untrustedHasNoOperator'],'Untrusted duplicate obtained operator'
            if args.expect_protected:assert result['oldSessionPreserved'] and not result['untrustedStillConnected'],'Trusted owner session displaced by untrusted duplicate'
            result['passed']=True;result['characterization']=not args.expect_protected
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
print(json.dumps(result,indent=2),flush=True)
print('FINAL '+str(work/'report.json'),flush=True)
