import argparse
import hashlib
import json
import io
import os
from pathlib import Path
import subprocess
import time
import uuid
import zipfile
import re


parser = argparse.ArgumentParser()
parser.add_argument('--package', type=Path, required=True)
parser.add_argument('--legacy-package', type=Path)
parser.add_argument('--require-model-assets', action='store_true')
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
package_manifest = json.loads((package / 'package-manifest.json').read_text(encoding='utf-8-sig'))
addon_entries = [entry for entry in package_manifest['managedFiles'] if entry['path'].startswith('mcheli_addons/default/') and entry.get('existingOnly')]
assert addon_entries, 'No bounded extracted-addon migration entries were supplied'
addon_report = {'root': str(root), 'actualLegacyPackage': str(args.legacy_package) if args.legacy_package else None, 'existingOnlyPaths': [entry['path'] for entry in addon_entries], 'nativeResolutionTested': False}


def inside(relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def addon_hashes():
    for entry in addon_entries:
        path = inside(entry['path'])
        assert path.is_file(), 'Missing extracted managed addon file: ' + entry['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], 'Extracted addon checksum mismatch: ' + entry['path']


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
for name in ['Warfare-Connection.ps1', 'Warfare-Performance.ps1', 'Warfare-Onboarding.ps1', 'Configure-FirstPlay.ps1', 'Configure-Controller.ps1', 'Play-Warfare.ps1', 'Warfare-Launcher.ps1', 'server-defaults.json']:
    assert (root / name).read_bytes() == (package / name).read_bytes(), name
print('fresh install uses packaged connection defaults and copies connection files: PASS')
profile_path = root / 'config/rv-client.properties'
profile = dict(line.split('=', 1) for line in profile_path.read_text().splitlines() if '=' in line)
assert profile['profile'] in ('low', 'balanced') and profile['language'] == 'ru'
profile_path.write_bytes(b'schema=1\r\nprofile=quality\r\nlanguage=ru\r\nhudHints=false\r\nhitFeedback=true\r\nunknown=keep\r\n')
options_path = root / 'options.txt'
options_path.write_bytes(options_path.read_bytes().replace(b'renderDistance:4', b'renderDistance:17').replace(b'renderDistance:8', b'renderDistance:17'))
shader_path = root / 'optionsshaders.txt'
shader_path.write_bytes(shader_path.read_bytes().replace(b'shaderPack=OFF', b'shaderPack=my-choice.zip'))
performance_before = {path.relative_to(root): path.read_bytes() for path in (profile_path, options_path, shader_path)}
print('fresh install selects a conservative profile and preserves a manual override for migration: PASS')
for entry in addon_entries:
    assert not inside(entry['path']).exists(), 'Cold install created a partial extracted addon: ' + entry['path']
addon_custom = inside('mcheli_addons/default/assets/mcheli/models/player-custom.mqo')
addon_custom.parent.mkdir(parents=True)
addon_custom.write_bytes(b'personal addon sentinel')
addon_marker = inside('mcheli_addons/default/pack.mcmeta')
assert not addon_marker.exists()
install('connection-partial-default-addon')
missing = [entry['path'] for entry in addon_entries if not inside(entry['path']).is_file()]
addon_report['missingWithoutMarker'] = missing
(root / 'addon-migration-report.json').write_text(json.dumps(addon_report, indent=2), encoding='utf-8')
assert not missing, 'Existing default folder without pack.mcmeta skipped known addon files: ' + ', '.join(missing)
addon_hashes()
assert addon_custom.read_bytes() == b'personal addon sentinel', 'Partial-default repair changed a custom addon'
print('cold install leaves extraction to the mod; partial default folder receives known files without losing custom content: PASS')
missing_asset = inside(addon_entries[0]['path'])
asset_bytes = missing_asset.read_bytes()
missing_asset.unlink()
try:
    missing_check = subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(root / 'Play-Warfare.ps1'), '-Check'], capture_output=True, timeout=60, env=env)
    assert missing_check.returncode == 1 and addon_entries[0]['path'].encode('utf-8') in missing_check.stdout, 'Check files ignored a missing managed addon asset'
finally:
    missing_asset.write_bytes(asset_bytes)
addon_report['missingManagedAssetCheckFails'] = True
print('Check files rejects a deleted known asset in an existing default addon: PASS')

legacy_members = set()
if args.legacy_package:
    legacy_package = args.legacy_package.resolve()
    legacy_manifest = json.loads((legacy_package / 'package-manifest.json').read_text(encoding='utf-8-sig'))
    legacy_mod = next(entry for entry in legacy_manifest['managedFiles'] if entry['path'].startswith('mods/mcheli-ce-'))
    with zipfile.ZipFile(legacy_package / 'payload.zip') as payload:
        legacy_bytes = payload.read(legacy_mod['path'])
    assert hashlib.sha256(legacy_bytes).hexdigest() == legacy_mod['sha256'], 'Legacy MC Heli checksum mismatch'
    with zipfile.ZipFile(io.BytesIO(legacy_bytes)) as archive:
        for entry in archive.infolist():
            if entry.is_dir() or not (entry.filename == 'pack.mcmeta' or entry.filename.startswith('assets/mcheli/')):
                continue
            assert not entry.filename.startswith('/') and '..' not in Path(entry.filename).parts
            target = inside('mcheli_addons/default/' + entry.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))
            legacy_members.add(entry.filename)
    assert addon_marker.is_file() and len(legacy_members) > 100, 'The real old default addon was not extracted'
    addon_report['legacyJarSHA256'] = legacy_mod['sha256']
    addon_report['legacyExtractedFiles'] = len(legacy_members)
else:
    addon_marker.write_text('{"pack":{"pack_format":3,"description":"Existing default addon"}}', encoding='utf-8')

addon_before = {}
addon_new_paths = []
for entry in addon_entries:
    target = inside(entry['path'])
    internal = entry['path'].removeprefix('mcheli_addons/default/')
    if args.legacy_package and internal not in legacy_members:
        target.unlink(missing_ok=True)
        addon_new_paths.append(entry['path'])
    elif target.is_file():
        addon_before[entry['path']] = target.read_bytes()
first_existing = next((entry for entry in addon_entries if entry['path'] in addon_before), None)
if first_existing:
    stale = b'old managed addon overlay'
    inside(first_existing['path']).write_bytes(stale)
    addon_before[first_existing['path']] = stale
addon_report['newMissingPaths'] = addon_new_paths

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
    'mcheli_addons/default/assets/mcheli/models/player-custom.mqo': b'personal addon sentinel',
    **{str(path): data for path, data in performance_before.items()},
}
for name, content in sentinels.items():
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

legacy = {'language': 'ru', 'nickname': 'QAPlayer', 'shareCode': 'QATEST12', 'host': '127.0.0.1', 'port': 25572, 'memoryMB': 2560, 'customSetting': 'preserve me', 'unicodeSetting': {'title': 'Мой сервер', 'values': ['настройки', '中文']}}
legacy['firstPlay'] = {'schema': 1, 'completed': True, 'scope': 'client', 'inputMode': 'radio', 'device': 'saved-controller', 'unknown': ['keep', 'личное']}
settings_path.write_text(json.dumps(legacy, ensure_ascii=False), encoding='utf-8')
install('connection-legacy-code')
assert current_mod_path.exists() and not retired_mod_path.exists(), 'Managed mod filename migration failed'
retired_backups = list((root / 'backups').rglob(retired_mod_path.name))
assert any(hashlib.sha256(path.read_bytes()).hexdigest() == retired_hash for path in retired_backups), 'Retired managed mod backup missing'
for name, content in sentinels.items():
    assert (root / name).read_bytes() == content, 'Personal file changed: ' + name
print('managed mod filename migrates with backup; unknown mods, config and worlds survive: PASS')
addon_hashes()
for path, content in addon_before.items():
    if hashlib.sha256(content).hexdigest() == next(entry['sha256'] for entry in addon_entries if entry['path'] == path):
        continue
    backups_for_asset = [directory / path for directory in (root / 'backups').iterdir() if directory.is_dir()]
    assert any(target.is_file() and target.read_bytes() == content for target in backups_for_asset), 'Old known addon asset backup is missing: ' + path
families = {'definition': [], 'mesh': [], 'texture': [], 'hud': []}
for entry in addon_entries:
    path = entry['path']
    if path.endswith('.yml'):
        families['definition'].append(path)
    if path.endswith(('.mqo', '.obj')):
        families['mesh'].append(path)
    if path.endswith('.png'):
        families['texture'].append(path)
    if '/hud/' in path:
        families['hud'].append(path)
if args.require_model_assets:
    assert all(families.values()), 'The final model package is missing a managed asset family: ' + str(families)
    for path in families['mesh']:
        geometry = inside(path).read_text(encoding='utf-8-sig')
        assert re.search(r'\bvertex\s+[1-9][0-9]*\s*\{', geometry) or re.search(r'(?m)^v\s+[-0-9]', geometry), 'Managed model has no vertices: ' + path
    for path in families['texture']:
        data = inside(path).read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n' and min(int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')) > 0, 'Managed texture is not a valid PNG: ' + path
addon_report.update(managedAssetFamilies=families, allManagedHashesMatch=True, changedAssetsBackedUp=True, customContentPreserved=True, partialDefaultRepair=True)
(root / 'addon-migration-report.json').write_text(json.dumps(addon_report, indent=2), encoding='utf-8')
print('known extracted addon files update with exact checksums and backups; new paths and custom addons are preserved correctly: PASS')
assert assert_connection('porthole', 'QATEST12', 25572)['customSetting'] == 'preserve me'
assert read_settings()['unicodeSetting'] == legacy['unicodeSetting'], 'Unicode settings changed during installation'
assert read_settings()['memoryMB'] == 2560, 'Explicit memory allocation changed during installation'
assert read_settings()['firstPlay'] == legacy['firstPlay'], 'Saved input and onboarding preferences changed during installation'
print('legacy code and port survive update: PASS')

canonical = read_settings()
canonical.update(connectionMode='direct', connectionTarget='changed.example', serverPort=25610)
settings_path.write_text(json.dumps(canonical, ensure_ascii=False), encoding='utf-8')
install('connection-user-choice')
assert assert_connection('direct', 'changed.example', 25610)['customSetting'] == 'preserve me'
assert read_settings()['unicodeSetting'] == legacy['unicodeSetting'], 'Unicode settings changed during update'
assert read_settings()['memoryMB'] == 2560, 'Explicit memory allocation changed during update'
assert read_settings()['firstPlay'] == legacy['firstPlay'], 'Saved input and onboarding preferences changed during update'
for path, data in performance_before.items():
    assert (root / path).read_bytes() == data, 'Personal performance settings changed: ' + str(path)
print('update preserves profile, graphics, shaders and explicit memory exactly: PASS')
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
profile_path.unlink()
graphics_before = {path: path.read_bytes() for path in (options_path, shader_path)}
install('connection-missing-client-preferences')
new_preferences = profile_path.read_text(encoding='utf-8-sig')
assert 'language=ru' in new_preferences, 'Existing language was not migrated'
assert 'profile=low' not in new_preferences and 'profile=quality' not in new_preferences, 'An upgrade silently selected a profile'
for path, data in graphics_before.items():
    assert path.read_bytes() == data, 'Migration changed personal graphics: ' + str(path)
assert read_settings()['memoryMB'] == 2560, 'Migration changed explicit memory'
print('old installation without profile migrates its language without touching graphics or memory: PASS')

results.append({'test': 'installed-check', 'exitCode': check.returncode})
results.append({'test': 'running-game-case-guard', 'exitCode': blocked.returncode})
(qa / 'connection-installation-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results, indent=2))
