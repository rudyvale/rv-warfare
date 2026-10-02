import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from release_contract import validate_base

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--base', type=Path, required=True)
parser.add_argument('--output', type=Path)
parser.add_argument('--private', action='store_true')
parser.add_argument('--defaults', type=Path)
parser.add_argument('--world-template', type=Path)
args = parser.parse_args()
if args.defaults and not args.private:
    parser.error('--defaults is only allowed with --private')
if args.private and not args.defaults:
    parser.error('--private requires an explicit --defaults file')
manifest = validate_base(args.base, root / 'pack/package-manifest.json')
output = (args.output or root / ('dist-private' if args.private else 'dist')).resolve()
package = output / 'RV-Setup'
package.mkdir(parents=True, exist_ok=True)
for name in ['payload.zip', 'runtime.zip']:
    source = args.base / name
    if source.resolve() != (package / name).resolve():
        shutil.copyfile(source, package / name)
scripts = ['Install-Warfare.ps1', 'Play-Warfare.ps1', 'Warfare-Launcher.ps1', 'Warfare-Connection.ps1', 'Warfare-Updates.ps1', 'Check-WarfareUpdate.ps1', 'Configure-Controller.ps1', 'release.json']
for name in scripts:
    source = root / 'src' / name
    data = source.read_text(encoding='utf-8-sig')
    (package / name).write_text(data, encoding='utf-8-sig' if source.suffix == '.ps1' else 'utf-8')
for name in ['READ-ME.md']:
    shutil.copyfile(root / 'pack' / name, package / name)
shutil.copyfile(args.base / 'installer-files.json', package / 'installer-files.json')
shutil.copyfile(args.defaults if args.private else root / 'pack/server-defaults.json', package / 'server-defaults.json')
shutil.copyfile(root / 'assets/code.ico', package / 'code.ico')
manifest['version'] = json.loads((root / 'src/release.json').read_text())['version']
guide = (root / 'pack/READ-ME.md').read_bytes()
rewritten = package / 'payload-new.zip'
with zipfile.ZipFile(package / 'payload.zip') as old, zipfile.ZipFile(rewritten, 'w', zipfile.ZIP_DEFLATED, compresslevel=4) as new:
    for entry in old.infolist():
        new.writestr(entry, guide if entry.filename == 'READ-ME.md' else old.read(entry.filename))
rewritten.replace(package / 'payload.zip')
for entry in manifest['managedFiles']:
    if entry['path'] == 'READ-ME.md':
        entry['sha256'] = hashlib.sha256(guide).hexdigest()
for entry in manifest['archives']:
    with (package / entry['path']).open('rb') as stream:
        entry['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
(package / 'package-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
command = '@echo off\r\nstart "" powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0Warfare-Launcher.ps1"'
for name in ['INSTALL.cmd', 'УСТАНОВИТЬ.cmd']:
    (package / name).write_bytes((command + '\r\n').encode('ascii'))
play = '@echo off\r\nif exist "%~dp0payload.zip" (\r\n  start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0Warfare-Launcher.ps1"\r\n) else (\r\n  start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0Warfare-Launcher.ps1" -InstallRoot "%~dp0."\r\n)\r\n'
(package / 'Play.cmd').write_bytes(play.encode('ascii'))
archive_path = output / 'RV-Setup.zip'
with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
    for name in sorted(scripts + ['payload.zip', 'runtime.zip', 'installer-files.json', 'server-defaults.json', 'READ-ME.md', 'package-manifest.json', 'code.ico', 'INSTALL.cmd', 'УСТАНОВИТЬ.cmd', 'Play.cmd']):
        archive.write(package / name, 'RV-Setup/' + name)
with archive_path.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
checksums = digest + '  RV-Setup.zip\n'
host_path = output / 'RV-Host-Tools.zip'
with zipfile.ZipFile(host_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
    for name in ['README.md', 'warfare-launcher.py', 'host_runtime.py', 'porthole-status.py', 'run-server.py', 'launch-warfare.py', 'launcher-texts.json', 'Join-Server.ps1', 'Launch-Warfare.ps1', 'Start-All.ps1', 'Start-Server.ps1', 'Start-Porthole.ps1', 'Stop-All.ps1', 'Stop-Server.ps1', 'Check-OwnerConnection.ps1']:
        archive.write(root / 'host' / name, name)
    for name in ['Check-WarfareUpdate.ps1', 'Warfare-Updates.ps1', 'Configure-Controller.ps1', 'release.json']:
        archive.write(root / 'src' / name, name)
    archive.write(root / 'assets/code.ico', 'code.ico')
with host_path.open('rb') as stream:
    checksums += hashlib.file_digest(stream, 'sha256').hexdigest() + '  RV-Host-Tools.zip\n'
if args.world_template:
    world = output / 'RV-World-Template.zip'
    if args.world_template.resolve() != world.resolve():
        shutil.copyfile(args.world_template, world)
    with zipfile.ZipFile(world) as archive:
        if archive.testzip() is not None:
            raise SystemExit('World template is corrupt')
        private = {'ops.json', 'whitelist.json', 'usercache.json', 'usernamecache.json', 'banned-players.json', 'banned-ips.json'}
        for name in archive.namelist():
            parts = name.replace('\\', '/').split('/')
            if name.startswith(('/', '\\')) or ':' in name or '..' in parts or any(part.lower() in private | {'logs', 'playerdata', 'stats', 'advancements'} for part in parts):
                raise SystemExit('Private or unsafe world template entry: ' + name)
    with world.open('rb') as stream:
        checksums += hashlib.file_digest(stream, 'sha256').hexdigest() + '  RV-World-Template.zip\n'
(output / 'SHA256SUMS.txt').write_text(checksums, encoding='ascii')
print(json.dumps({'archive': str(archive_path), 'bytes': archive_path.stat().st_size, 'sha256': digest}))
