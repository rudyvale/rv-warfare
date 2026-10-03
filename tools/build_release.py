import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from release_contract import load_addon_map, required_mods, validate_base, validate_output, write_candidate
from third_party_sources import verify_bundle, verify_vendor_manifest

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--base', type=Path, required=True)
parser.add_argument('--output', type=Path)
parser.add_argument('--private', action='store_true')
parser.add_argument('--defaults', type=Path)
parser.add_argument('--world-template', type=Path)
parser.add_argument('--third-party-sources', type=Path)
parser.add_argument('--replace-candidate', action='store_true')
args = parser.parse_args()
if args.defaults and not args.private:
    parser.error('--defaults is only allowed with --private')
if args.private and not args.defaults:
    parser.error('--private requires an explicit --defaults file')
manifest = validate_base(args.base, root / 'pack/package-manifest.json')
output = (args.output or root / ('dist-private' if args.private else 'dist')).resolve()
metadata = json.loads((root / 'src/release.json').read_text())
required_mods(metadata)
version = metadata['version']
validate_output(output, version, args.private, args.replace_candidate)
vendor_catalog = None
first_party = {}
if tuple(map(int, version.split('.'))) >= (1, 2, 0):
    from vendor_catalog import first_party_proof_path, load_catalog, sha256_file, validate_release_catalog, verify_first_party_proof, verify_managed_delivery
    catalog_path = root / 'pack/vendor-catalog.json'
    vendor_catalog = load_catalog(catalog_path)
    with zipfile.ZipFile(args.base / 'payload.zip') as payload:
        first_party = verify_first_party_proof(first_party_proof_path(metadata, root), vendor_catalog, manifest, payload, root)
        verify_managed_delivery(vendor_catalog, manifest, payload, 'client')
    validate_release_catalog(vendor_catalog, metadata, sha256_file(catalog_path), first_party)
if tuple(map(int, version.split('.'))) >= (1, 1, 0):
    if not args.third_party_sources:
        raise ValueError('RV 1.1.0 requires --third-party-sources')
    source_registry = verify_bundle(args.third_party_sources, root / 'pack/third-party-sources.json', root / 'pack/THIRD-PARTY-NOTICES.md')
    verify_vendor_manifest(manifest, source_registry)
    notices = root / 'pack/THIRD-PARTY-NOTICES.md'
    notice_sha = hashlib.sha256(notices.read_bytes()).hexdigest()
    if not any(entry['path'] == 'THIRD-PARTY-NOTICES.md' and entry['sha256'] == notice_sha for entry in manifest['managedFiles']):
        raise ValueError('RV 1.1.0 requires the installed third-party notices in the frozen payload')
    addon_map = root / 'pack/rv-addon-assets.json'
    if not addon_map.is_file():
        raise ValueError('RV 1.1.0 requires a frozen addon resource map')
    mcheli_sha = next(entry['sha256'] for entry in manifest['managedFiles'] if entry['path'] == 'mods/mcheli-ce-1.5.1-rv.jar')
    load_addon_map(addon_map, mcheli_sha)
scripts = ['Install-Warfare.ps1', 'Play-Warfare.ps1', 'Warfare-Launcher.ps1', 'Warfare-Connection.ps1', 'Warfare-Updates.ps1', 'Check-WarfareUpdate.ps1', 'Configure-Controller.ps1', 'release.json']
if vendor_catalog is not None:
    for name in ('Warfare-VendorDownloads.ps1', 'Warfare-Ambience.ps1', 'Warfare-ClientMods.ps1'):
        if not (root / 'src' / name).is_file():
            raise ValueError('RV 1.2.0 requires ' + name)
        scripts.append(name)
performance = root / 'src/Warfare-Performance.ps1'
if tuple(map(int, version.split('.'))) >= (1, 1, 0) and not performance.is_file():
    raise ValueError('RV 1.1.0 requires Warfare-Performance.ps1')
if performance.is_file():
    scripts.append('Warfare-Performance.ps1')
first_play = ['Warfare-Onboarding.ps1', 'Configure-FirstPlay.ps1']
for name in first_play:
    source = root / 'src' / name
    if tuple(map(int, version.split('.'))) >= (1, 1, 0) and not source.is_file():
        raise ValueError('RV 1.1.0 requires ' + name)
    if source.is_file():
        scripts.append(name)
host_scripts = ['README.md', 'warfare-launcher.py', 'play-owner.py', 'owner-panel.py', 'world_reset.py', 'host_runtime.py', 'porthole-status.py', 'run-server.py', 'launch-warfare.py', 'launcher-texts.json', 'Join-Server.ps1', 'Launch-Warfare.ps1', 'Start-All.ps1', 'Start-Server.ps1', 'Start-Porthole.ps1', 'Stop-All.ps1', 'Stop-Server.ps1', 'Check-OwnerConnection.ps1']
if vendor_catalog is not None:
    for name in ('server_vendors.py', 'Install-ServerVendors.ps1', 'Warfare-VendorDownloads.ps1'):
        if not (root / 'host' / name).is_file():
            raise ValueError('RV 1.2.0 requires the host source ' + name)
        host_scripts.append(name)
    if sha256_file(root / 'host/Warfare-VendorDownloads.ps1') != sha256_file(root / 'src/Warfare-VendorDownloads.ps1'):
        raise ValueError('Host and client vendor download helpers differ')
porthole = root / 'host/Porthole-Host.ps1'
if tuple(map(int, version.split('.'))) >= (1, 1, 0) and not porthole.is_file():
    raise ValueError('RV 1.1.0 requires Porthole-Host.ps1')
if porthole.is_file():
    host_scripts.append('Porthole-Host.ps1')
client_memory = root / 'host/Get-ClientMemory.ps1'
if tuple(map(int, version.split('.'))) >= (1, 1, 0) and not client_memory.is_file():
    raise ValueError('RV 1.1.0 requires Get-ClientMemory.ps1')
if client_memory.is_file():
    host_scripts.append('Get-ClientMemory.ps1')
package = output / 'RV-Setup'
package.mkdir(parents=True, exist_ok=True)
for name in ['payload.zip', 'runtime.zip']:
    source = args.base / name
    if source.resolve() != (package / name).resolve():
        shutil.copyfile(source, package / name)
for name in scripts:
    source = root / 'src' / name
    data = source.read_text(encoding='utf-8-sig')
    (package / name).write_text(data, encoding='utf-8-sig' if source.suffix == '.ps1' else 'utf-8')
pack_files = ['READ-ME.md']
if vendor_catalog is not None:
    pack_files.append('vendor-catalog.json')
    if metadata.get('managedModsSha256'):
        pack_files.append('rv-managed-mods.json')
if tuple(map(int, version.split('.'))) >= (1, 1, 0):
    pack_files.append('THIRD-PARTY-NOTICES.md')
for name in pack_files:
    shutil.copyfile(root / 'pack' / name, package / name)
if vendor_catalog is not None and (package / 'release.json').stat().st_size > 4096:
    raise ValueError('Packaged release metadata exceeds the immutable older updater limit')
shutil.copyfile(args.base / 'installer-files.json', package / 'installer-files.json')
shutil.copyfile(args.defaults if args.private else root / 'pack/server-defaults.json', package / 'server-defaults.json')
shutil.copyfile(root / 'assets/code.ico', package / 'code.ico')
manifest['version'] = version
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
    for name in sorted(scripts + pack_files + ['payload.zip', 'runtime.zip', 'installer-files.json', 'server-defaults.json', 'package-manifest.json', 'code.ico', 'INSTALL.cmd', 'УСТАНОВИТЬ.cmd', 'Play.cmd']):
        archive.write(package / name, 'RV-Setup/' + name)
with archive_path.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
checksums = digest + '  RV-Setup.zip\n'
host_path = output / 'RV-Host-Tools.zip'
with zipfile.ZipFile(host_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
    for name in host_scripts:
        archive.write(root / 'host' / name, name)
    for name in ['Check-WarfareUpdate.ps1', 'Warfare-Updates.ps1', 'Configure-Controller.ps1', 'release.json']:
        archive.write(root / 'src' / name, name)
    if vendor_catalog is not None:
        archive.write(root / 'pack/vendor-catalog.json', 'vendor-catalog.json')
        if metadata.get('managedModsSha256'):
            archive.write(root / 'pack/rv-managed-mods.json', 'rv-managed-mods.json')
            owned = json.loads((root / 'pack/rv-managed-mods.json').read_text(encoding='utf-8'))
            with zipfile.ZipFile(args.base / 'payload.zip') as payload:
                for entry in owned['mods']:
                    archive.writestr('host-owned/' + entry['path'], payload.read(entry['path']))
    if performance.is_file():
        archive.write(package / 'Warfare-Performance.ps1', 'Warfare-Performance.ps1')
    for name in first_play:
        if (package / name).is_file():
            archive.write(package / name, name)
    if tuple(map(int, version.split('.'))) >= (1, 1, 0):
        archive.write(package / 'Warfare-Connection.ps1', 'Warfare-Connection.ps1')
        archive.write(package / 'THIRD-PARTY-NOTICES.md', 'THIRD-PARTY-NOTICES.md')
    addon_map = root / 'pack/rv-addon-assets.json'
    if addon_map.is_file():
        archive.write(addon_map, 'rv-addon-assets.json')
    archive.write(root / 'assets/code.ico', 'code.ico')
with host_path.open('rb') as stream:
    checksums += hashlib.file_digest(stream, 'sha256').hexdigest() + '  RV-Host-Tools.zip\n'
if tuple(map(int, version.split('.'))) >= (1, 1, 0):
    source_asset = output / 'RV-Third-Party-Sources.zip'
    if args.third_party_sources.resolve() != source_asset.resolve():
        shutil.copyfile(args.third_party_sources, source_asset)
    with source_asset.open('rb') as stream:
        checksums += hashlib.file_digest(stream, 'sha256').hexdigest() + '  RV-Third-Party-Sources.zip\n'
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
if vendor_catalog is not None:
    from audit_public_archives import audit_archives
    paths = [output / line.split('  ', 1)[1] for line in checksums.splitlines()]
    audit = audit_archives(paths, vendor_catalog)
    (output.parent / (output.name + '-vendor-public-audit.json')).write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    if audit.get('passed') is not True:
        raise ValueError('RV 1.2.0 vendor archive audit failed')
write_candidate(output, version, args.private)
print(json.dumps({'archive': str(archive_path), 'bytes': archive_path.stat().st_size, 'sha256': digest}))
