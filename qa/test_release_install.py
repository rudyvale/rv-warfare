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
root = Path(__file__).resolve().parent / ('release-install-' + uuid.uuid4().hex)
shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
env = {**os.environ, 'VM_SKIP_UPDATE_CHECK': '1'}
results = []

def install(label, expected=0):
    start = time.monotonic()
    result = subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(package / 'Install-Warfare.ps1'), '-InstallRoot', str(root), '-Nickname', 'ReleaseQA', '-Language', 'ru', '-NoLaunch', '-NoSteam', '-NoShortcut'], capture_output=True, timeout=240, env=env)
    if result.returncode != expected:
        raise AssertionError((label, result.returncode, result.stderr.decode('utf-8', errors='replace')))
    results.append({'test': label, 'seconds': round(time.monotonic() - start, 2), 'exitCode': result.returncode})

install('fresh-public-install')
for name in ['Warfare-Updates.ps1', 'Check-WarfareUpdate.ps1', 'release.json', 'code.ico', 'Warfare-Launcher.ps1', 'Play-Warfare.ps1', 'Warfare-Connection.ps1', 'Configure-Controller.ps1']:
    assert (root / name).read_bytes() == (package / name).read_bytes(), name
settings_path = root / 'warfare-settings.json'
settings = json.loads(settings_path.read_text(encoding='utf-8-sig'))
assert settings['connectionTarget'] == ''
settings.update(connectionMode='direct', connectionTarget='example.test', serverPort=25571, custom='keep')
settings_path.write_text(json.dumps(settings), encoding='utf-8')
(root / '.updates').mkdir(exist_ok=True)
(root / '.updates/preferences.json').write_text('{"autoCheck":false}')
(root / 'saves').mkdir(exist_ok=True)
(root / 'saves/sentinel.dat').write_bytes(b'personal world')
install('update-preserves-settings-world-and-update-preference')
saved = json.loads(settings_path.read_text(encoding='utf-8-sig'))
assert (saved['connectionTarget'], saved['serverPort'], saved['custom']) == ('example.test', 25571, 'keep')
assert (root / 'saves/sentinel.dat').read_bytes() == b'personal world'
assert json.loads((root / '.updates/preferences.json').read_text())['autoCheck'] is False
metadata = json.loads((root / 'release.json').read_text())
metadata['version'] = '99.0.0'
(root / 'release.json').write_text(json.dumps(metadata))
protected = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in ['release.json', 'warfare-settings.json', 'installed-manifest.json', 'Play-Warfare.ps1']}
install('older-package-rejected-before-changing-installation', 1)
for name, digest in protected.items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
print(json.dumps(results, indent=2))
