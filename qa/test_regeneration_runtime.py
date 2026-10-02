import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
import uuid
from runtime_medical_files import stage_medical

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--mcheli', type=Path, required=True)
parser.add_argument('--game', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'Warfare-1.12.2')
args = parser.parse_args()
work = ROOT / '.local/qa-1.1.0' / ('regeneration-' + uuid.uuid4().hex)
server = work / 'server'
server.mkdir(parents=True)
base = ROOT / '.local/server-base'
java = args.game / 'runtime/bin/java.exe'


def link(source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
    return str(target)


shutil.copytree(base / 'libraries', server / 'libraries', copy_function=link)
for name in ['forge-1.12.2-14.23.5.2860.jar', 'minecraft_server.1.12.2.jar', 'eula.txt']:
    link(base / name, server / name)
for source in (base / 'mods').glob('*.jar'):
    if not source.name.startswith(('mcheli', 'techguns', 'firstaid', 'EnhancedVisuals', 'CreativeCore')):
        link(source, server / 'mods' / source.name)
shutil.copy2(args.mcheli, server / 'mods/mcheli-rv.jar')
techguns = ROOT / '.local/controls/final/techguns-1.12.2-rv.jar'
link(techguns, server / 'mods' / techguns.name)
medical = stage_medical(server)
(server / 'config/techguns.cfg').write_text('"world generation" {\n B:SpawnStructures=false\n B:SpawnOreClusterStructures=false\n}\n')
with socket.socket() as probe:
    probe.bind(('127.0.0.1', 0))
    port = probe.getsockname()[1]
(server / 'server.properties').write_text(f'server-ip=127.0.0.1\nserver-port={port}\nonline-mode=false\nlevel-name=SavedRules\nlevel-type=FLAT\ngenerator-settings=3;minecraft:bedrock,2*minecraft:dirt,minecraft:grass;1;\ngenerate-structures=false\nview-distance=3\nspawn-monsters=false\nspawn-animals=false\n', encoding='ascii')
result = {'mcheliSha256': hashlib.sha256(args.mcheli.read_bytes()).hexdigest(), 'techgunsSha256': hashlib.sha256(techguns.read_bytes()).hexdigest(), 'medical': medical, 'productionJarUnmodified': True, 'cases': []}
process = None


def wait(log, predicate, seconds, label):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        content = log.read_text(encoding='utf-8', errors='replace')
        if predicate(content):
            return content
        if process.poll() is not None:
            raise RuntimeError(label + ' exited: ' + str(log))
        time.sleep(.2)
    raise TimeoutError(label + ': ' + str(log))


def command(text):
    process.stdin.write(text + '\n')
    process.stdin.flush()


try:
    for number, expected, setting in [(1, None, 'false'), (2, 'false', 'true'), (3, 'true', None)]:
        log = server / ('runtime-' + str(number) + '.log')
        with log.open('w', encoding='utf-8') as stream:
            process = subprocess.Popen([str(java), '-Xms256M', '-Xmx2G', '-jar', 'forge-1.12.2-14.23.5.2860.jar', 'nogui'], cwd=server, stdin=subprocess.PIPE, stdout=stream, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            print('Actual regeneration restart ' + str(number) + ': ' + str(log), flush=True)
            content = wait(log, lambda value: 'Done (' in value, 180, 'native startup')
            assert '[RV comfort] FirstAid preserves world regeneration' in content, 'Native FirstAid world-load compatibility hook absent'
            command('gamerule naturalRegeneration')
            content = wait(log, lambda value: bool(re.search(r'naturalRegeneration = (true|false)', value)), 5, 'actual gamerule query')
            observed = re.search(r'naturalRegeneration = (true|false)', content).group(1)
            if expected is not None:
                assert observed == expected, 'Saved regeneration rule overwritten: ' + observed
            result['cases'].append({'restart': number, 'expectedSavedRule': expected, 'actualNativeRule': observed, 'setBeforeSave': setting, 'pid': process.pid})
            if setting is not None:
                command('gamerule naturalRegeneration ' + setting)
            command('stop')
            process.wait(timeout=30)
            assert process.returncode == 0, 'Native server did not save and stop normally'
        assert (server / 'SavedRules/level.dat').is_file(), 'Actual saved world missing'
    result['passed'] = True
finally:
    if process is not None and process.poll() is None:
        process.terminate()
        process.wait(timeout=20)
    result['ownedProcessesStopped'] = process is None or process.poll() is not None
    (work / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2), flush=True)
print(str(work / 'report.json'), flush=True)
