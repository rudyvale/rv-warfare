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
test_root = qa / ('cold-install-' + uuid.uuid4().hex)
game = test_root / 'Игра RV'
appdata = test_root / 'AppData'
localdata = test_root / 'LocalAppData'
appdata.mkdir(parents=True)
localdata.mkdir()
system = Path(os.environ['SystemRoot'])
shell = system / 'System32/WindowsPowerShell/v1.0/powershell.exe'
excluded = {'path', 'java_home', 'psmodulepath', 'appdata', 'localappdata'}
env = {key: value for key, value in os.environ.items() if key.lower() not in excluded}
env.update(APPDATA=str(appdata), LOCALAPPDATA=str(localdata), PATH=os.pathsep.join(map(str, [system / 'System32', system, shell.parent])), VM_SKIP_UPDATE_CHECK='1')
assert not (appdata / '.minecraft').exists()
started = time.monotonic()
result = subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(package / 'Install-Warfare.ps1'), '-InstallRoot', str(game), '-Language', 'ru', '-Nickname', 'ColdTester', '-NoLaunch', '-NoShortcut', '-NoSteam'], capture_output=True, timeout=300, env=env)
(test_root / 'install.out').write_bytes(result.stdout)
(test_root / 'install.err').write_bytes(result.stderr)
assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
elapsed = round(time.monotonic() - started, 2)
downloads = json.loads((game / 'installer-files.json').read_text(encoding='utf-8-sig'))
for entry in downloads['files']:
    path = game / entry['path']
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha1').hexdigest()
    assert digest == entry['sha1'], 'Downloaded file checksum differs: ' + entry['path']
java = game / 'runtime/bin/java.exe'
java_result = subprocess.run([str(java), '-version'], capture_output=True, timeout=15, env=env)
assert java_result.returncode == 0 and b'1.8.0' in java_result.stderr, 'Bundled Java 8 does not run'
check = subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(game / 'Play-Warfare.ps1'), '-Check'], capture_output=True, timeout=60, env=env)
assert check.returncode == 0, check.stderr.decode('utf-8', errors='replace')
defaults = json.loads((package / 'server-defaults.json').read_text(encoding='utf-8-sig'))
settings = json.loads((game / 'warfare-settings.json').read_text(encoding='utf-8-sig'))
assert settings['connectionTarget'] == defaults['connectionTarget']
report = {'package': str(package), 'game': str(game), 'seconds': elapsed, 'verifiedDownloads': len(downloads['files']), 'bundledJava8Runs': True, 'installedCheck': True, 'existingMinecraftCache': False, 'externalJavaOnPath': False, 'steamInstallationTested': False}
(test_root / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
