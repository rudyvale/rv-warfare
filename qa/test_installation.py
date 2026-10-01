import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

QA = Path(__file__).resolve().parent
ROOT = QA / 'Fresh game кириллица'
PACKAGE = QA / 'full-package'
PS = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
ENV = {key: value for key, value in os.environ.items() if key.lower() != 'psmodulepath'}
results = []


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def install(name, expected=0):
    start = time.monotonic()
    result = subprocess.run([str(PS), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(PACKAGE / 'Install-Warfare.ps1'), '-InstallRoot', str(ROOT), '-Language', 'ru', '-Nickname', 'QAPlayer', '-NoLaunch', '-NoShortcut', '-NoSteam'], capture_output=True, timeout=90, env=ENV)
    (QA / (name + '.out')).write_bytes(result.stdout)
    (QA / (name + '.err')).write_bytes(result.stderr)
    assert (result.returncode == 0) == (expected == 0), (name, result.returncode, result.stderr.decode(errors='replace'))
    results.append({'test': name, 'exitCode': result.returncode, 'seconds': round(time.monotonic() - start, 2)})


settings = ROOT / 'warfare-settings.json'
saved = json.loads(settings.read_text(encoding='utf-8-sig'))
saved.update(shareCode='ABCD123', host='127.0.0.9', port=25570)
settings.write_text(json.dumps(saved), encoding='utf-8')
sentinels = {
    'saves/My world/level.dat': b'world sentinel',
    'servers.dat': b'servers sentinel',
    'mods/user-extra.jar': b'unmanaged mod sentinel',
    'config/user-preferences.cfg': b'custom config sentinel',
}
for name, data in sentinels.items():
    target = ROOT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
options = ROOT / 'options.txt'
lines = [line for line in options.read_text(encoding='utf-8').splitlines() if not line.startswith(('gamma:', 'resourcePacks:'))]
options.write_text('\n'.join(lines + ['gamma:0.75', 'resourcePacks:["My-Textures.zip","Warfare-UI-fixes.zip","Warfare-Combat-Audio.zip"]']) + '\n', encoding='utf-8')
old_mod = ROOT / 'mods/mcheli-ce-1.5.1-warfare-fix0.jar'
old_mod.write_bytes(b'old managed mod sentinel')
install('update-preserves-user-files')
for name, data in sentinels.items():
    assert (ROOT / name).read_bytes() == data, name
saved = json.loads(settings.read_text(encoding='utf-8-sig'))
assert (saved['shareCode'], saved['host'], saved['port']) == ('ABCD123', '127.0.0.9', 25570)
assert 'gamma:0.75' in options.read_text(encoding='utf-8')
assert 'My-Textures.zip' in options.read_text(encoding='utf-8')
assert options.read_text(encoding='utf-8').count('Warfare-Combat-Audio.zip') == 1
assert not old_mod.exists()
assert any(p.read_bytes() == b'old managed mod sentinel' for p in (ROOT / 'backups').rglob(old_mod.name))
print('update, user files and obsolete mod backup: PASS')

manifest = PACKAGE / 'package-manifest.json'
original = manifest.read_bytes()
broken = json.loads(original)
broken['archives'][0]['sha256'] = '0' * 64
manifest.write_text(json.dumps(broken), encoding='utf-8')
before = digest(ROOT / 'installed-manifest.json')
try:
    install('bad-checksum-rejected', 1)
finally:
    manifest.write_bytes(original)
assert digest(ROOT / 'installed-manifest.json') == before
print('bad archive checksum rejected before commit: PASS')

managed = json.loads(original)['managedFiles']
victim = next(entry['path'] for entry in managed if 'jei_' in entry['path'])
(ROOT / victim).write_bytes(b'preexisting damaged managed file')
protected = {name: digest(ROOT / name) for name in [victim, 'installed-manifest.json', 'options.txt', 'warfare-settings.json', 'Play-Warfare.ps1']}
play_cmd = PACKAGE / 'Play.cmd'
cmd_bytes = play_cmd.read_bytes()
play_cmd.unlink()
try:
    install('late-commit-rollback', 1)
finally:
    play_cmd.write_bytes(cmd_bytes)
for name, value in protected.items():
    assert digest(ROOT / name) == value, 'Rollback failed: ' + name
print('late commit failure restores previous files: PASS')

check = subprocess.run([str(PS), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'Play-Warfare.ps1'), '-Check'], capture_output=True, timeout=30, env=ENV)
assert check.returncode != 0, 'Damaged mod reported ready'
install('repair-damaged-mod')
assert digest(ROOT / victim) == next(entry['sha256'] for entry in managed if entry['path'] == victim)
check = subprocess.run([str(PS), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'Play-Warfare.ps1'), '-Check'], capture_output=True, timeout=30, env=ENV)
assert check.returncode == 0, check.stderr.decode(errors='replace')
print('damaged mod detected and repaired: PASS')
(QA / 'installation-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results, indent=2))
