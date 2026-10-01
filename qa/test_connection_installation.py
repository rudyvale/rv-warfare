import argparse
import json
import os
from pathlib import Path
import subprocess
import time


parser = argparse.ArgumentParser()
parser.add_argument('--package', type=Path, required=True)
args = parser.parse_args()
package = args.package.resolve()
qa = Path(__file__).resolve().parent
root = qa / 'connection-install'
if root.exists():
    raise SystemExit('Use a fresh connection-install test directory.')
root.mkdir()
shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
env = {key: value for key, value in os.environ.items() if key.lower() != 'psmodulepath'}
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
assert defaults['connectionTarget'].startswith('peer:')
install('connection-fresh')
assert_connection(defaults['connectionMode'], defaults['connectionTarget'], defaults['serverPort'])
for name in ['Warfare-Connection.ps1', 'Play-Warfare.ps1', 'Warfare-Launcher.ps1', 'server-defaults.json']:
    assert (root / name).read_bytes() == (package / name).read_bytes(), name
print('fresh install uses packaged host and copies connection files: PASS')

legacy = {'language': 'ru', 'nickname': 'QAPlayer', 'shareCode': 'QATEST12', 'host': '127.0.0.1', 'port': 25572, 'customSetting': 'preserve me'}
settings_path.write_text(json.dumps(legacy), encoding='utf-8')
install('connection-legacy-code')
assert assert_connection('porthole', 'QATEST12', 25572)['customSetting'] == 'preserve me'
print('legacy code and port survive update: PASS')

canonical = read_settings()
canonical.update(connectionMode='direct', connectionTarget='changed.example', serverPort=25610)
settings_path.write_text(json.dumps(canonical), encoding='utf-8')
install('connection-user-choice')
assert assert_connection('direct', 'changed.example', 25610)['customSetting'] == 'preserve me'
print('user selection overrides package default and old code: PASS')

legacy.pop('shareCode')
legacy.update(host='legacy.example', port=25620)
settings_path.write_text(json.dumps(legacy), encoding='utf-8')
install('connection-legacy-address')
assert assert_connection('direct', 'legacy.example', 25620)['customSetting'] == 'preserve me'
check = subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(root / 'Play-Warfare.ps1'), '-Check'], capture_output=True, timeout=60, env=env)
assert check.returncode == 0, check.stderr.decode(errors='replace')
print('legacy address migrates and installed game passes file check: PASS')

results.append({'test': 'installed-check', 'exitCode': check.returncode})
(qa / 'connection-installation-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results, indent=2))
