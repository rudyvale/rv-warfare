import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile


parser = argparse.ArgumentParser()
parser.add_argument('--server-source',type=Path,required=True)
parser.add_argument('--game',type=Path,required=True)
parser.add_argument('--world',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--compiler',type=Path,required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
output = args.output.resolve()
output.mkdir(parents=True,exist_ok=False)
server = output/'server'
server.mkdir()
game = args.game.resolve()
classes = output/'classes'
classes.mkdir()
java = game/'runtime/bin/java.exe'
classpath = os.pathsep.join(str(path) for path in (game/'libraries').rglob('*.jar'))
result = subprocess.run([str(java),'-jar',str(args.compiler),'-1.8','-encoding','UTF-8','-nowarn','-cp',classpath,'-d',str(classes),str(root/'qa/RVSpawnRuntime.java')],capture_output=True,text=True,timeout=30)
assert result.returncode == 0,result.stderr


def link(source,destination):
    try: os.link(source,destination)
    except OSError: shutil.copy2(source,destination)
    return destination


for name in ('libraries','mods','config'):
    shutil.copytree(args.server_source/name,server/name,copy_function=link if name!='config' else shutil.copy2)
for name in ('forge-1.12.2-14.23.5.2860.jar','minecraft_server.1.12.2.jar','eula.txt'):
    link(args.server_source/name,server/name)
helper = server/'mods/rv-spawn-qa.jar.new'
with zipfile.ZipFile(helper,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in classes.rglob('*.class'):archive.write(path,path.relative_to(classes).as_posix())
helper.replace(server/'mods/rv-spawn-qa.jar')
shutil.copytree(args.world,server/'Battlefield-Extended')
(server/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=25579\nonline-mode=false\nlevel-name=Battlefield-Extended\nview-distance=3\nmax-players=1\nspawn-protection=0\nspawn-monsters=false\nspawn-animals=false\nallow-flight=true\n',encoding='ascii')
process = None
report = {'passed':False,'port':25579,'nativeWorld':True,'ordinaryClients':0}
try:
    with (server/'integration.log').open('w',encoding='utf-8') as log:
        process = subprocess.Popen([str(java),'-Dfile.encoding=UTF-8','-Xms256M','-Xmx1536M','-jar','forge-1.12.2-14.23.5.2860.jar','nogui'],cwd=server,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic()+90
        while time.monotonic()<deadline:
            assert process.poll() is None,'Native server exited before readiness'
            if 'Done (' in (server/'integration.log').read_text(encoding='utf-8',errors='replace'):break
            time.sleep(0.1)
        else:raise TimeoutError('Native props server startup timed out')
        process.stdin.write('function warfare:boot\n');process.stdin.flush()
        (server/'rv-qa-props.txt').write_text('bounded native explosion',encoding='ascii')
        result_path = server/'rv-qa-props-result.json'
        deadline = time.monotonic()+20
        while time.monotonic()<deadline and not result_path.exists():
            assert process.poll() is None,'Native props server exited'
            assert not (server/'rv-qa-props-failed.txt').exists(),'Native props QA hook failed'
            time.sleep(0.1)
        native = json.loads(result_path.read_text(encoding='utf-8'))
        assert native['passed'],native
        report.update(native)
        print('PASS native world loads static cover and vanilla explosion destroys its block',flush=True)
finally:
    if process is not None and process.poll() is None:
        process.stdin.write('save-all\nstop\n');process.stdin.flush()
        process.wait(timeout=60)
        report['serverExitCode']=process.returncode
        report['gracefulSave']=process.returncode==0
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
