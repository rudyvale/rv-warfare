import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


parser = argparse.ArgumentParser()
parser.add_argument('--package', type=Path, required=True)
args = parser.parse_args()
package = args.package.resolve()
qa = Path(__file__).resolve().parent
root = qa / ('connection-install-' + uuid.uuid4().hex)
root.mkdir()
shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
env = {key: value for key, value in os.environ.items() if key.lower() != 'psmodulepath'}
env['VM_SKIP_UPDATE_CHECK'] = '1'
results = []
settings_path = root / 'warfare-settings.json'


def read_settings():
    return json.loads(settings_path.read_text(encoding='utf-8-sig'))


def install(name):
    start = time.monotonic()
    result = subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(package / 'Install-Warfare.ps1'), '-InstallRoot', str(root), '-Language', 'ru', '-Nickname', 'QAPlayer', '-NoLaunch', '-NoShortcut', '-NoSteam'], capture_output=True, timeout=180, env=env)
    (qa / (name + '.out')).write_bytes(result.stdout)
    (qa / (name + '.err')).write_bytes(result.stderr)
    assert result.returncode == 0, (name, result.returncode, result.stderr.decode(errors='replace'))
    results.append({'test': name, 'seconds': round(time.monotonic() - start, 2)})


def assert_connection(mode, target, port):
    settings = read_settings()
    assert (settings['connectionMode'], settings['connectionTarget'], settings['serverPort']) == (mode, target, port)
    assert settings['nickname'] == 'QAPlayer'
    return settings


defaults = json.loads((package / 'server-defaults.json').read_text(encoding='utf-8-sig'))
assert defaults['connectionMode'] == 'porthole'
assert defaults['connectionTarget'] == '' or defaults['connectionTarget'].startswith('peer:')
install('connection-fresh')
assert_connection(defaults['connectionMode'], defaults['connectionTarget'], defaults['serverPort'])
for name in ['Warfare-Connection.ps1', 'Play-Warfare.ps1', 'Warfare-Launcher.ps1', 'server-defaults.json']:
    assert (root / name).read_bytes() == (package / name).read_bytes(), name
print('fresh install uses packaged connection defaults and copies connection files: PASS')

installed_manifest_path = root / 'installed-manifest.json'
installed_manifest = json.loads(installed_manifest_path.read_text(encoding='utf-8-sig'))
managed_mod = next(entry for entry in installed_manifest['managedFiles'] if entry['path'].startswith('mods/mcheli-ce-'))
current_mod_path = root / managed_mod['path']
retired_mod_path = root / 'mods/mcheli-ce-1.5.1-warfare-fix0.jar'
assert current_mod_path != retired_mod_path
current_mod_path.rename(retired_mod_path)
retired_hash = hashlib.sha256(retired_mod_path.read_bytes()).hexdigest()
managed_mod['path'] = retired_mod_path.relative_to(root).as_posix()
installed_manifest_path.write_text(json.dumps(installed_manifest), encoding='utf-8')
sentinels = {
    'mods/player-addon.jar': b'unknown mod',
    'config/player-preferences.cfg': 'Мои настройки'.encode('utf-8'),
    'saves/Мой мир/level.dat': b'personal world',
    'servers.dat': b'personal server list',
}
for name, content in sentinels.items():
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

legacy = {'language': 'ru', 'nickname': 'QAPlayer', 'shareCode': 'QATEST12', 'host': '127.0.0.1', 'port': 25572, 'customSetting': 'preserve me', 'unicodeSetting': {'title': 'Мой сервер', 'values': ['настройки', '中文']}}
settings_path.write_text(json.dumps(legacy, ensure_ascii=False), encoding='utf-8')
install('connection-legacy-code')
assert current_mod_path.exists() and not retired_mod_path.exists(), 'Managed mod filename migration failed'
retired_backups = list((root / 'backups').rglob(retired_mod_path.name))
assert any(hashlib.sha256(path.read_bytes()).hexdigest() == retired_hash for path in retired_backups), 'Retired managed mod backup missing'
for name, content in sentinels.items():
    assert (root / name).read_bytes() == content, 'Personal file changed: ' + name
print('managed mod filename migrates with backup; unknown mods, config and worlds survive: PASS')
assert assert_connection('porthole', 'QATEST12', 25572)['customSetting'] == 'preserve me'
assert read_settings()['unicodeSetting'] == legacy['unicodeSetting'], 'Unicode settings changed during installation'
print('legacy code and port survive update: PASS')

canonical = read_settings()
canonical.update(connectionMode='direct', connectionTarget='changed.example', serverPort=25610)
settings_path.write_text(json.dumps(canonical, ensure_ascii=False), encoding='utf-8')
install('connection-user-choice')
assert assert_connection('direct', 'changed.example', 25610)['customSetting'] == 'preserve me'
assert read_settings()['unicodeSetting'] == legacy['unicodeSetting'], 'Unicode settings changed during update'
print('user selection overrides package default and old code: PASS')

legacy.pop('shareCode')
legacy.update(host='legacy.example', port=25620)
settings_path.write_text(json.dumps(legacy, ensure_ascii=False), encoding='utf-8')
install('connection-legacy-address')
assert assert_connection('direct', 'legacy.example', 25620)['customSetting'] == 'preserve me'
check = subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(root / 'Play-Warfare.ps1'), '-Check'], capture_output=True, timeout=60, env=env)
assert check.returncode == 0, check.stderr.decode(errors='replace')
print('legacy address migrates and installed game passes file check: PASS')

guard = root / 'guard-case.ps1'
guard.write_text('''param([string]$PackageRoot,[string]$GameRoot)
$ErrorActionPreference='Stop'
function Get-CimInstance {
    param($ClassName,$Filter,$ErrorAction)
    return [PSCustomObject]@{CommandLine=('java.exe -cp fixture --gameDir "' + $GameRoot.ToUpperInvariant() + '"')}
}
& (Join-Path $PackageRoot 'Install-Warfare.ps1') -InstallRoot $GameRoot -Language ru -Nickname QAPlayer -NoLaunch -NoShortcut -NoSteam
''', encoding='utf-8-sig')
before = {path.relative_to(root): path.read_bytes() for path in root.iterdir() if path.is_file()}
backups = sorted((root / 'backups').iterdir())
blocked = subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(guard), '-PackageRoot', str(package), '-GameRoot', str(root)], capture_output=True, timeout=30, env=env)
assert blocked.returncode == 1 and b'Close RV' in blocked.stderr, 'Running game with a differently cased path was not blocked'
assert sorted((root / 'backups').iterdir()) == backups, 'Blocked install created an update backup'
for path, data in before.items():
    assert (root / path).read_bytes() == data, str(path)
print('running game blocks updates regardless of Windows path case: PASS')

results.append({'test': 'installed-check', 'exitCode': check.returncode})
results.append({'test': 'running-game-case-guard', 'exitCode': blocked.returncode})
(qa / 'connection-installation-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results, indent=2))
