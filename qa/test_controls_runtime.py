import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile
import argparse

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--client',action='store_true')
parser.add_argument('--game',type=Path,default=Path(os.environ.get('RV_GAME_ROOT',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Warfare-1.12.2'))))
parser.add_argument('--compiler',type=Path,default=Path(os.environ.get('RV_ECJ_JAR',str(root/'.local/tools/ecj-4.6.1.jar'))))
parser.add_argument('--server-base',type=Path,default=Path(os.environ.get('RV_SERVER_BASE',str(root/'.local/server-base'))))
parser.add_argument('--audio',type=Path,default=Path(os.environ.get('RV_COMBAT_AUDIO',str(root/'.local/controls/audio/Warfare-Combat-Audio.zip'))))
options=parser.parse_args()

work=root/'.local/controls'
game=options.game
original=options.server_base
server=work/'server'
server.mkdir(exist_ok=True)
test_world=(server/'ControlsTest').resolve()
assert test_world.parent==server.resolve() and test_world.is_relative_to(work.resolve())
if test_world.exists():shutil.rmtree(test_world)
def link(src,dst):
    if not Path(dst).exists():
        try:os.link(src,dst)
        except OSError:shutil.copy2(src,dst)
    return dst
shutil.copytree(original/'libraries',server/'libraries',dirs_exist_ok=True,copy_function=link)
for name in ['forge-1.12.2-14.23.5.2860.jar','minecraft_server.1.12.2.jar','eula.txt']:
    link(original/name,server/name)
(server/'mods').mkdir(exist_ok=True)
for mod in (original/'mods').glob('*.jar'):
    if not mod.name.startswith(('mcheli','techguns')):link(mod,server/'mods'/mod.name)
props=work/'techguns-1.12.2-2.0.2.0-rv-gameplay.jar'
if props.exists():
    for prior in (server/'mods').glob('techguns*.jar'):prior.unlink()
    shutil.copy2(props,server/'mods'/props.name)
else:
    for mod in (original/'mods').glob('techguns*.jar'):link(mod,server/'mods'/mod.name)
java=game/'runtime/bin/java.exe'
libraries=list((game/'libraries').rglob('*.jar'))
asm=next(p for p in libraries if p.name=='asm-debug-all-5.2.jar')
classes=work/'runtime-test-classes'
classes.mkdir(exist_ok=True)
mod=work/'mcheli-ce-1.5.1-vm-controls1.jar'
compile_cp=os.pathsep.join([str(mod),*(str(p) for p in libraries)])
sources=[root/'qa/VMControlsRuntime.java',root/'qa/VMControlsClientRuntime.java']
acceptance=root/'qa/RVCombatAcceptance.java'
if acceptance.exists():sources.append(acceptance)
subprocess.run([str(java),'-jar',str(options.compiler),'-1.8','-encoding','UTF-8','-nowarn','-cp',compile_cp,'-d',str(classes),*map(str,sources)],check=True)
cp=os.pathsep.join([str(game/'runtime/lib/ext/nashorn.jar'),str(asm)])
subprocess.run([str(java),'-cp',cp,'jdk.nashorn.tools.Shell',str(root/'qa/patch-controls-test.js'),'--',str(mod),str(classes)],check=True)
with zipfile.ZipFile(mod) as z,zipfile.ZipFile(server/'mods/mcheli-controls-test.jar','w',zipfile.ZIP_DEFLATED) as out:
    for item in z.infolist():
        changed=classes/item.filename
        out.writestr(item,changed.read_bytes() if changed.is_file() else z.read(item.filename))
    out.write(classes/'VMControlsRuntime.class','VMControlsRuntime.class')
    out.write(classes/'VMControlsClientRuntime.class','VMControlsClientRuntime.class')
    if acceptance.exists():
        for helper in classes.glob('RVCombatAcceptance*.class'):out.write(helper,helper.name)
(server/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=25576\nonline-mode=false\nlevel-name=ControlsTest\nlevel-type=FLAT\ngenerator-settings=3;minecraft:bedrock,2*minecraft:dirt,minecraft:grass;1;\nview-distance=3\nmax-players=2\nspawn-protection=0\nspawn-monsters=false\nspawn-animals=false\nallow-flight=true\ngamemode=1\n',encoding='ascii')
log=server/'integration.log'
with log.open('w',encoding='utf-8') as stream:
    process=subprocess.Popen([str(java),'-Xms256M','-Xmx2G','-Dvm.controls.integration=true','-Dlog4j2.formatMsgNoLookups=true','-jar','forge-1.12.2-14.23.5.2860.jar','nogui'],cwd=server,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    print('Started isolated Forge server on 127.0.0.1:25576',flush=True)
    try:
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            content=log.read_text(encoding='utf-8',errors='replace')
            if 'Done (' in content:break
            if process.poll() is not None:raise RuntimeError('Server exited. See '+str(log))
            time.sleep(.25)
        else:raise TimeoutError('Server startup timeout')
        print('Forge server ready; invoking real entity/sound/particle checks',flush=True)
        process.stdin.write('mcheli vmcontrolscheck\n');process.stdin.flush()
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            content=log.read_text(encoding='utf-8',errors='replace')
            if '[VM integration] COMPLETE' in content or '[VM integration] FAILED' in content:break
            time.sleep(.2)
        issues=[line for line in content.splitlines() if '[VM ' in line]
        print('\n'.join(issues),flush=True)
        ok='[VM integration] COMPLETE' in content and '[VM integration] FAILED' not in content and not any('Exception' in line for line in issues)
        report={'success':ok,'log':str(log),'artifact_sha256':hashlib.sha256(mod.read_bytes()).hexdigest(),'props_sha256':hashlib.sha256(props.read_bytes()).hexdigest() if props.exists() else None,'checks':issues}
        if acceptance.exists():report['acceptance_source_sha256']=hashlib.sha256(acceptance.read_bytes()).hexdigest()
        (work/'runtime-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if not ok:raise RuntimeError('Runtime checks failed')
        if options.client:
            client=work/'client';client.mkdir(exist_ok=True)
            (client/'mods').mkdir(exist_ok=True)
            for item in (game/'mods').glob('*.jar'):
                if not item.name.startswith(('mcheli','techguns')):link(item,client/'mods'/item.name)
            if props.exists():
                for prior in (client/'mods').glob('techguns*.jar'):prior.unlink()
                shutil.copy2(props,client/'mods'/props.name)
            else:
                for item in (game/'mods').glob('techguns*.jar'):link(item,client/'mods'/item.name)
            shutil.copy2(server/'mods/mcheli-controls-test.jar',client/'mods/mcheli-controls-test.jar')
            shutil.copytree(game/'config',client/'config',dirs_exist_ok=True)
            (client/'resourcepacks').mkdir(exist_ok=True)
            audio=options.audio
            shutil.copy2(audio,client/'resourcepacks'/audio.name)
            ui_pack=game/'resourcepacks/Warfare-UI-fixes.zip'
            if ui_pack.exists():shutil.copy2(ui_pack,client/'resourcepacks'/ui_pack.name)
            (client/'config/vm-controller.properties').write_text('enabled=false\nflight=angle\n')
            (client/'options.txt').write_text('renderDistance:3\nfancyGraphics:false\nmaxFps:60\nfullscreen:false\npauseOnLostFocus:false\nsoundCategory_master:0.2\nresourcePacks:["Warfare-UI-fixes.zip","Warfare-Combat-Audio.zip"]\n')
            downloads=json.loads((game/'installer-files.json').read_text(encoding='utf-8-sig'))
            client_cp=os.pathsep.join(str(game/p) for p in downloads['classpath'])
            client_log=client/'integration.log'
            with client_log.open('w',encoding='utf-8') as client_stream:
                client_process=subprocess.Popen([str(java),'-Xms256M','-Xmx3G','-Dvm.controls.integration=true','-Dlog4j2.formatMsgNoLookups=true',f'-Djava.library.path={game / "natives"}','-cp',client_cp,downloads['mainClass'],'--username','VMControlsTest','--version','VM-controls-test','--gameDir',str(client),'--assetsDir',str(game/'assets'),'--assetIndex',downloads['assetIndex'],'--uuid','a735f1a045e4471c99426b651bf267c8','--accessToken','0','--userType','legacy','--tweakClass','net.minecraftforge.fml.common.launcher.FMLTweaker','--server','127.0.0.1','--port','25576','--width','960','--height','600'],cwd=client,stdout=client_stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                print('Started isolated Minecraft client for render/sound/control hooks',flush=True)
                try:
                    deadline=time.monotonic()+180
                    while time.monotonic()<deadline:
                        server_text=log.read_text(encoding='utf-8',errors='replace')
                        if 'VMControlsTest joined the game' in server_text:break
                        if client_process.poll() is not None:raise RuntimeError('Client startup failed')
                        if 'Fatally missing registry entries' in client_log.read_text(encoding='utf-8',errors='replace'):raise RuntimeError('Client registry mismatch')
                        time.sleep(.5)
                    else:raise TimeoutError('Client join timeout')
                    process.stdin.write('mcheli vmcontrolsride\n');process.stdin.flush()
                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline:
                        client_text=client_log.read_text(encoding='utf-8',errors='replace')
                        if '[VM client integration] COMPLETE' in client_text or '[VM client integration] FAILED' in client_text:break
                        time.sleep(.25)
                    lines=[line for line in client_text.splitlines() if '[VM ' in line]
                    print('\n'.join(lines),flush=True)
                    client_ok='[VM client integration] COMPLETE' in client_text and '[VM client integration] FAILED' not in client_text and not any('Exception' in line or 'Error' in line for line in lines)
                    (work/'client-result.json').write_text(json.dumps({'success':client_ok,'artifact_sha256':hashlib.sha256(mod.read_bytes()).hexdigest(),'checks':lines},ensure_ascii=False,indent=2),encoding='utf-8')
                    if not client_ok:raise RuntimeError('Client integration failed; see '+str(client_log))
                    process.stdin.write('mcheli vmcontrolscombat\n');process.stdin.flush()
                    deadline=time.monotonic()+30
                    while time.monotonic()<deadline:
                        server_text=log.read_text(encoding='utf-8',errors='replace')
                        if '[VM combat integration] COMPLETE' in server_text or '[VM combat integration] FAILED' in server_text:break
                        time.sleep(.25)
                    combat_lines=[line for line in server_text.splitlines() if '[VM ' in line or '[RV combat QA]' in line]
                    print('\n'.join(combat_lines[-10:]),flush=True)
                    combat_ok='[VM combat integration] COMPLETE' in server_text and '[VM combat integration] FAILED' not in server_text and not any('Exception' in line or 'Error' in line for line in combat_lines)
                    (work/'combat-result.json').write_text(json.dumps({'success':combat_ok,'artifact_sha256':hashlib.sha256(mod.read_bytes()).hexdigest(),'props_sha256':hashlib.sha256(props.read_bytes()).hexdigest() if props.exists() else None,'acceptance_source_sha256':hashlib.sha256(acceptance.read_bytes()).hexdigest() if acceptance.exists() else None,'checks':combat_lines},ensure_ascii=False,indent=2),encoding='utf-8')
                    if not combat_ok:raise RuntimeError('Actual collision/damage checks failed; see '+str(log))
                finally:
                    if client_process.poll() is None:client_process.terminate();client_process.wait(timeout=20)
    finally:
        if process.poll() is None:
            process.stdin.write('stop\n');process.stdin.flush()
            try:process.wait(timeout=25)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=10)
