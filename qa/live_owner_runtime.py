import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid


parser = argparse.ArgumentParser()
parser.add_argument('--server', type=Path, required=True)
parser.add_argument('--client', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--python-libs', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.python_libs))
import nbtlib

server = args.server.resolve()
game = args.client.resolve()
owner = json.loads((server / 'vm-owner.json').read_text(encoding='utf-8-sig'))['nickname']
if not owner or not owner.isascii() or not owner.replace('_', '').isalnum() or not 3 <= len(owner) <= 16:
    raise RuntimeError('Private owner nickname is invalid')
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=False)
checks = []
clients = []
handles = []
console = server / 'console.log'
start_offset = console.stat().st_size
shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'


def log(offset=start_offset):
    with console.open('r', encoding='utf-8', errors='replace') as handle:
        handle.seek(offset)
        return handle.read()


def wait_for(condition, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        if not json.loads((server / 'server-state.json').read_text())['ready']:
            raise RuntimeError('Live server became unavailable')
        time.sleep(0.2)
    raise TimeoutError('Live runtime condition timed out')


def check(value, name):
    checks.append({'name': name, 'passed': bool(value)})
    print(('PASS ' if value else 'FAIL ') + name, flush=True)
    if not value:
        raise AssertionError(name)


def command(value):
    with (server / 'commands.txt').open('a', encoding='utf-8') as handle:
        handle.write(value + '\n')


def offline_id(name):
    return uuid.UUID(bytes=hashlib.md5(('OfflinePlayer:' + name).encode()).digest(), version=3)


def player_data(name):
    properties = dict(line.split('=', 1) for line in (server / 'server.properties').read_text().splitlines() if '=' in line and not line.startswith('#'))
    path = server / properties.get('level-name', 'world') / 'playerdata' / (str(offline_id(name)) + '.dat')
    previous = path.stat().st_mtime_ns if path.exists() else 0
    command('save-all')
    wait_for(lambda: path.exists() and path.stat().st_mtime_ns != previous, 15)
    return nbtlib.load(path)


def operator(name):
    return [item for item in json.loads((server / 'ops.json').read_text()) if item['name'] == name]


def launch_cold(name):
    plan = json.loads((game / 'installer-files.json').read_text(encoding='utf-8-sig'))
    classpath = os.pathsep.join(str(game / item) for item in plan['classpath'])
    handle = (output / ('untrusted-owner-client.log' if name == owner else 'ordinary-client.log')).open('w', encoding='utf-8')
    handles.append(handle)
    process = subprocess.Popen([str(game / 'runtime/bin/java.exe'), '-Dfile.encoding=UTF-8', '-Xms256M', '-Xmx2G', '-Djava.library.path=' + str(game / 'natives'), '-cp', classpath, plan['mainClass'], '--username', name, '--version', 'RV-live-QA', '--gameDir', str(game), '--assetsDir', str(game / 'assets'), '--assetIndex', plan['assetIndex'], '--uuid', offline_id(name).hex, '--accessToken', '0', '--userType', 'legacy', '--tweakClass', 'net.minecraftforge.fml.common.launcher.FMLTweaker', '--server', '127.0.0.1', '--port', '25565', '--width', '854', '--height', '480'], cwd=game, stdout=handle, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    clients.append((name, process))
    return process


def close(name, process):
    if process.poll() is None:
        command('kick ' + name + ' RV runtime check complete')
        time.sleep(0.5)
        process.terminate()
        process.wait(timeout=15)


class ExistingProcess:
    def __init__(self, pid):
        import ctypes
        from ctypes import wintypes
        self.pid = pid
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.kernel.TerminateProcess.restype = wintypes.BOOL
        self.handle = self.kernel.OpenProcess(0x101001, False, self.pid)
        if not self.handle:
            raise RuntimeError('Could not retain owned client identity')

    def poll(self):
        return None if self.kernel.WaitForSingleObject(self.handle, 0) == 258 else 0

    def terminate(self):
        if not self.kernel.TerminateProcess(self.handle, 0):
            raise RuntimeError('Could not close owned host client')

    def wait(self, timeout):
        deadline = time.monotonic() + timeout
        while self.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        if self.poll() is None:
            raise TimeoutError('Owned host client remained active')


try:
    state = json.loads((server / 'server-state.json').read_text())
    check(state.get('state') == 'running' and state.get('ready') and state.get('port') == 25565, 'actual live server ready')
    spoof_offset = console.stat().st_size
    spoof = launch_cold(owner)
    print('Started one owned untrusted-directory client', flush=True)
    wait_for(lambda: owner + ' joined the game' in log(spoof_offset))
    wait_for(lambda: '[RV owner] operator denied' in log(spoof_offset), 15)
    check(not operator(owner), 'same nickname from untrusted directory remains non-operator')
    check('v_owner' not in [str(tag) for tag in player_data(owner).get('Tags', [])], 'untrusted player has no owner tag')
    close(owner, spoof)
    trusted_offset = console.stat().st_size
    result = subprocess.run([str(shell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(server / 'Launch-Warfare.ps1')], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Production host launch failed')
    launched = json.loads(result.stdout.strip())
    check(launched.get('state') == 'running', 'production host launcher starts a fresh client')
    trusted = ExistingProcess(int(launched['pid']))
    clients.append((owner, trusted))
    wait_for(lambda: owner + ' joined the game' in log(trusted_offset))
    wait_for(lambda: '[RV owner] verified local session' in log(trusted_offset), 15)
    check(len(operator(owner)) == 1 and operator(owner)[0]['level'] == 4, 'actual local owner receives operator level4')
    check('v_owner' in [str(tag) for tag in player_data(owner).get('Tags', [])], 'actual local owner receives admin menu tag')
    ordinary_offset = console.stat().st_size
    ordinary = launch_cold('MenuTester')
    print('Started one owned ordinary player client', flush=True)
    wait_for(lambda: 'MenuTester joined the game' in log(ordinary_offset))
    check(not operator('MenuTester'), 'ordinary connected player remains non-operator')
    check('v_owner' not in [str(tag) for tag in player_data('MenuTester').get('Tags', [])], 'ordinary connected player has no admin menu tag')
    permission_offset = console.stat().st_size
    command('mcheli vmpermissiontest ' + owner + ' MenuTester')
    wait_for(lambda: '[VM permissions] PASS administrator allowed, non-operator denied' in log(permission_offset), 15)
    check(True, 'actual player permission command allows owner and denies ordinary player')
finally:
    for name, process in reversed(clients):
        close(name, process)
    for handle in handles:
        handle.close()
    report = {'passed': len(checks) == 9 and all(item['passed'] for item in checks), 'checks': checks, 'actualServer': True, 'clientsMax': 2, 'privatePolicy': True, 'sourceSha256': hashlib.sha256((server / 'Check-OwnerConnection.ps1').read_bytes()).hexdigest()}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
