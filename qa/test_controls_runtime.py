import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

root=Path(__file__).resolve().parents[1]
work=root/'.local/controls'
game=Path(os.environ['LOCALAPPDATA'])/'Warfare-1.12.2'
original=Path.home()/'OneDrive/Рабочий стол/RLCraft Server'
server=work/'server'
server.mkdir(exist_ok=True)
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
    if not mod.name.startswith('mcheli'):link(mod,server/'mods'/mod.name)
java=game/'runtime/bin/java.exe'
libraries=list((game/'libraries').rglob('*.jar'))
asm=next(p for p in libraries if p.name=='asm-debug-all-5.2.jar')
classes=work/'runtime-test-classes'
classes.mkdir(exist_ok=True)
mod=work/'mcheli-ce-1.5.1-vm-controls1.jar'
subprocess.run([str(java),'-jar',str(Path.home()/'Documents/Codex/2026-10-01/new-chat-2/work/ecj-4.6.1.jar'),'-1.8','-encoding','UTF-8','-nowarn','-cp',str(mod),'-d',str(classes),str(root/'qa/VMControlsRuntime.java')],check=True)
cp=os.pathsep.join([str(game/'runtime/lib/ext/nashorn.jar'),str(asm)])
subprocess.run([str(java),'-cp',cp,'jdk.nashorn.tools.Shell',str(root/'qa/patch-controls-test.js'),'--',str(mod),str(classes)],check=True)
with zipfile.ZipFile(mod) as z,zipfile.ZipFile(server/'mods/mcheli-controls-test.jar','w',zipfile.ZIP_DEFLATED) as out:
    for item in z.infolist():
        changed=classes/item.filename
        out.writestr(item,changed.read_bytes() if changed.is_file() else z.read(item.filename))
    out.write(classes/'VMControlsRuntime.class','VMControlsRuntime.class')
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
        report={'success':ok,'log':str(log),'artifact_sha256':hashlib.sha256(mod.read_bytes()).hexdigest(),'checks':issues}
        (work/'runtime-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if not ok:raise RuntimeError('Runtime checks failed')
    finally:
        if process.poll() is None:
            process.stdin.write('stop\n');process.stdin.flush()
            try:process.wait(timeout=25)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=10)
