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
from runtime_medical_files import stage_medical

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--mcheli', type=Path, required=True)
parser.add_argument('--game', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'Warfare-1.12.2')
parser.add_argument('--max-horizontal-speed', type=float, default=0.38)
parser.add_argument('--max-vertical-speed', type=float, default=0.22)
parser.add_argument('--expected-mcheli-sha256')
args = parser.parse_args()
actual_mcheli_sha256 = hashlib.sha256(args.mcheli.read_bytes()).hexdigest()
if args.expected_mcheli_sha256 and actual_mcheli_sha256.lower() != args.expected_mcheli_sha256.lower():
    raise AssertionError('MCHeli input does not match the expected candidate SHA-256')
work = ROOT / '.local/qa-1.1.0' / ('easy-guards-' + uuid.uuid4().hex)
work.mkdir(parents=True)
java = args.game / 'runtime/bin/java.exe'
libraries = list((args.game / 'libraries').rglob('*.jar'))
asm = next(path for path in libraries if path.name == 'asm-debug-all-5.2.jar')
classes = work / 'classes'
classes.mkdir()
source = work / 'RVEasyGuardRuntime.java'
patch = work / 'patch-easy-guard-test.js'
shutil.copy2(ROOT / 'qa' / source.name, source)
shutil.copy2(ROOT / 'qa' / patch.name, patch)
subprocess.run([str(java), '-jar', str(ROOT / '.local/tools/ecj-4.6.1.jar'), '-1.8', '-encoding', 'UTF-8', '-nowarn', '-cp', os.pathsep.join([str(args.mcheli), *map(str, libraries)]), '-d', str(classes), str(source)], check=True)
subprocess.run([str(java), '-cp', os.pathsep.join([str(args.game / 'runtime/lib/ext/nashorn.jar'), str(asm)]), 'jdk.nashorn.tools.Shell', str(patch), '--', str(args.mcheli), str(classes)], check=True)
instrumented = work / 'mcheli-guards.jar'
with zipfile.ZipFile(args.mcheli) as original, zipfile.ZipFile(instrumented, 'w', zipfile.ZIP_DEFLATED) as target:
    for entry in original.infolist():
        replacement = classes / entry.filename
        target.writestr(entry, replacement.read_bytes() if replacement.is_file() else original.read(entry.filename))
    for helper in classes.glob('RVEasyGuardRuntime*.class'):
        target.write(helper, helper.name)
allowed = {'com/norwood/mcheli/uav/WarfareQuickUav.class'}
with zipfile.ZipFile(args.mcheli) as original, zipfile.ZipFile(instrumented) as target:
    assert {name for name in original.namelist() if original.read(name) != target.read(name)} == allowed, 'Native handlers or guard code modified'


def link(source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
    return str(target)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def wait(process, log, predicate, seconds, label):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        content = log.read_text(encoding='utf-8', errors='replace')
        if predicate(content):
            return
        if process.poll() is not None:
            raise RuntimeError(label + ' exited: ' + str(log))
        if 'java.lang.NullPointerException: group' in content:
            raise RuntimeError('Native Netty bootstrap failed: ' + str(log))
        time.sleep(.25)
    raise TimeoutError(label + ': ' + str(log))


server = work / 'server'
clients = [work / 'pilot', work / 'foreign']
for folder in [server, *clients]:
    folder.mkdir()
base = ROOT / '.local/server-base'
shutil.copytree(base / 'libraries', server / 'libraries', copy_function=link)
for name in ['forge-1.12.2-14.23.5.2860.jar', 'minecraft_server.1.12.2.jar', 'eula.txt']:
    link(base / name, server / name)
techguns = ROOT / '.local/controls/final/techguns-1.12.2-rv.jar'
for folder, origin in [(server, base / 'mods'), *((client, args.game / 'mods') for client in clients)]:
    for mod in origin.glob('*.jar'):
        if not mod.name.startswith(('mcheli', 'techguns', 'firstaid', 'EnhancedVisuals', 'CreativeCore')):
            link(mod, folder / 'mods' / mod.name)
    shutil.copy2(instrumented, folder / 'mods/mcheli-guards.jar')
    link(techguns, folder / 'mods' / techguns.name)
    medical = stage_medical(folder)
(server / 'config/techguns.cfg').write_text('"world generation" {\n B:SpawnStructures=false\n B:SpawnOreClusterStructures=false\n}\n')
with socket.socket() as probe:
    probe.bind(('127.0.0.1', 0))
    port = probe.getsockname()[1]
(server / 'server.properties').write_text(f'server-ip=127.0.0.1\nserver-port={port}\nonline-mode=false\nlevel-name=GuardTest\nlevel-type=FLAT\ngenerator-settings=3;minecraft:bedrock,2*minecraft:dirt,minecraft:grass;1;\ngenerate-structures=false\nview-distance=3\nmax-players=2\nspawn-protection=0\nspawn-monsters=false\nspawn-animals=false\nallow-flight=true\ngamemode=1\n', encoding='ascii')
for client in clients:
    shutil.copy2(args.game / 'config/mcheli.cfg', client / 'config/mcheli.cfg')
    (client / 'config/vm-controller.properties').write_text('enabled=false\nkeyboardFlight=advanced\n')
    (client / 'options.txt').write_text('renderDistance:3\nfancyGraphics:false\nmaxFps:30\nfullscreen:false\npauseOnLostFocus:false\nchatVisibility:2\nsoundCategory_master:0.0\ntutorialStep:none\n')
    (client / 'optionsshaders.txt').write_text('shaderPack=OFF\n')
downloads = read(args.game / 'installer-files.json')
classpath = os.pathsep.join(str(args.game / path) for path in downloads['classpath'])
result = {'mcheliSha256': hashlib.sha256(args.mcheli.read_bytes()).hexdigest(), 'instrumentedSha256': hashlib.sha256(instrumented.read_bytes()).hexdigest(), 'instrumentedMembers': sorted(allowed), 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'patchSha256': hashlib.sha256(patch.read_bytes()).hexdigest(), 'medical': medical, 'actualTransportTested': False}
server_process = None
processes = []
streams = []


def command(text):
    server_process.stdin.write(text + '\n')
    server_process.stdin.flush()


try:
    log = server / 'runtime.log'
    stream = log.open('w', encoding='utf-8')
    streams.append(stream)
    server_process = subprocess.Popen([str(java), '-Xms256M', '-Xmx2G', '-Drv.easy.guard.qa=true', '-Drv.easy.guard.maxHorizontalSpeed=' + str(args.max_horizontal_speed), '-Drv.easy.guard.maxVerticalSpeed=' + str(args.max_vertical_speed), '-jar', 'forge-1.12.2-14.23.5.2860.jar', 'nogui'], cwd=server, stdin=subprocess.PIPE, stdout=stream, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    print('Native Easy guard scene: ' + str(work), flush=True)
    wait(server_process, log, lambda text: 'Done (' in text, 180, 'server startup')
    command('gamerule doMobSpawning false')
    for client, nickname in zip(clients, ['RVGuardPilot', 'RVGuardOther']):
        client_log = client / 'runtime.log'
        stream = client_log.open('w', encoding='utf-8')
        streams.append(stream)
        process = subprocess.Popen([str(java), '-Xms256M', '-Xmx2048M', '-Djava.library.path=' + str(args.game / 'natives'), '-cp', classpath, downloads['mainClass'], '--username', nickname, '--version', 'RV-guards-QA', '--gameDir', str(client), '--assetsDir', str(args.game / 'assets'), '--assetIndex', downloads['assetIndex'], '--uuid', uuid.uuid4().hex, '--accessToken', '0', '--userType', 'legacy', '--tweakClass', 'net.minecraftforge.fml.common.launcher.FMLTweaker', '--server', '127.0.0.1', '--port', str(port), '--width', '640', '--height', '360'], cwd=client, stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(process)
        wait(process, client_log, lambda text: nickname + ' joined the game' in log.read_text(encoding='utf-8', errors='replace'), 180, 'real client join')
    command('mcheli rveasyguards')
    wait(server_process, log, lambda text: (server / 'easy-guards.json').is_file(), 15, 'native handler guard cases')
    result['native'] = read(server / 'easy-guards.json')
    assert result['native']['passed'], result['native'].get('error', 'Native guard failure')
    assert len(result['native']['cases']) == 25 and not result['native']['fakePlayers'], 'Native guard matrix incomplete'
    assert all(value['passed'] for value in result['native']['cases']), 'Native guard case failed'
    result['passed'] = True
finally:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=20)
    if server_process is not None and server_process.poll() is None:
        command('stop')
        try:
            server_process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            server_process.terminate()
            server_process.wait(timeout=10)
    for stream in streams:
        stream.close()
    result['ownedProcessesStopped'] = all(process.poll() is not None for process in processes) and (server_process is None or server_process.poll() is not None)
    (work / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({'passed': result['passed'], 'nativeCases': len(result['native']['cases']), 'ownedProcessesStopped': result['ownedProcessesStopped']}, indent=2), flush=True)
print(str(work / 'report.json'), flush=True)
