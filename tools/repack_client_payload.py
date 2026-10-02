import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def addon_files(jar, asset_map):
    document = json.loads(asset_map.read_text(encoding='utf-8-sig'))
    resources = document.get('resources')
    if document.get('schema') != 1 or document.get('mcheliSha256') != digest(jar) or not isinstance(resources, dict) or len(resources) != 21:
        raise ValueError('The frozen addon map does not match the final JAR')
    additions = {}
    seen = set()
    total = 0
    with zipfile.ZipFile(jar) as archive:
        for name, expected in resources.items():
            path = PurePosixPath(name)
            if not name.startswith('assets/mcheli/') or '\\' in name or path.is_absolute() or '..' in path.parts or str(path) != name or name.casefold() in seen or not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
                raise ValueError('Invalid frozen addon resource: ' + name)
            seen.add(name.casefold())
            info = archive.getinfo(name)
            total += info.file_size
            if info.file_size > 2 * 1024 * 1024 or total > 8 * 1024 * 1024:
                raise ValueError('Frozen addon resources exceed their bounded size')
            data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Frozen addon bytes changed: ' + name)
            additions['mcheli_addons/default/' + name] = data
    return additions


def vendor_files(folder, registry):
    document = json.loads(registry.read_text(encoding='utf-8-sig'))
    components = document.get('components', [])
    if document.get('schema') != 1 or {entry['modId'] for entry in components} != {'firstaid', 'creativecore', 'enhancedvisuals'} or len(components) != 3:
        raise ValueError('The vendor registry must contain the three frozen comfort mods')
    additions = {}
    for entry in components:
        name = entry['binaryFile']
        if Path(name).name != name or '/' in name or '\\' in name or not name.lower().endswith('.jar'):
            raise ValueError('Invalid vendor filename')
        source = folder / name
        if source.stat().st_size != entry['binarySize'] or digest(source) != entry['binarySha256']:
            raise ValueError('Frozen vendor bytes changed: ' + name)
        with zipfile.ZipFile(source) as archive:
            if archive.testzip() is not None:
                raise ValueError('Vendor ZIP integrity failed: ' + name)
        additions['mods/' + name] = source.read_bytes()
    return additions


def repack(base, output, jar, techguns, audio, version='1.0.0', asset_map=None, comfort_mods=None, vendor_registry=None, comfort_config=None, notices=None):
    base, output = base.resolve(), output.resolve()
    if output.exists() or output == base or base in output.parents:
        raise ValueError('Output must be a new directory outside the baseline')
    manifest = json.loads((base / 'package-manifest.json').read_text(encoding='utf-8-sig'))
    for archive in manifest['archives']:
        if digest(base / archive['path']) != archive['sha256']:
            raise ValueError('Baseline archive failed its checksum')
    additions = {'mods/mcheli-ce-1.5.1-rv.jar': jar.read_bytes(), 'mods/techguns-1.12.2-rv.jar': techguns.read_bytes(), 'resourcepacks/Warfare-Combat-Audio.zip': audio.read_bytes()}
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid package version')
    expanded = tuple(map(int, version.split('.'))) >= (1, 1, 0)
    if expanded:
        if not all((asset_map, comfort_mods, vendor_registry, comfort_config, notices)):
            raise ValueError('RV 1.1 requires the frozen addon map, vendor registry, config and notices')
        additions.update(addon_files(jar, asset_map))
        additions.update(vendor_files(comfort_mods, vendor_registry))
        for name in ('firstaid.cfg', 'enhancedvisuals.json', 'enhancedvisuals-client.json'):
            data = (comfort_config / name).read_bytes()
            if not data or len(data) > 65536:
                raise ValueError('Invalid comfort config: ' + name)
            additions['config/' + name] = data
        additions['THIRD-PARTY-NOTICES.md'] = notices.read_bytes()
    with zipfile.ZipFile(jar) as mod:
        required = ['com/norwood/mcheli/uav/WarfareOwnerAuth.class', 'com/norwood/mcheli/vm/VMVec2f.class', 'com/norwood/mcheli/vm/VMImpact.class']
        if any(name not in mod.namelist() for name in required) or any(name.startswith(('VMControlsRuntime', 'VMControlsClientRuntime', 'RVCombatAcceptance')) for name in mod.namelist()):
            raise ValueError('Jar is incomplete or contains runtime test hooks')
        if not expanded:
            for name in ('rc-goblin.yml', 'rc-goblin-bomb.yml'):
                additions['mcheli_addons/default/assets/mcheli/helicopters/' + name] = mod.read('assets/mcheli/helicopters/' + name)
    output.mkdir(parents=True)
    updated = []
    with zipfile.ZipFile(base / 'payload.zip') as old, zipfile.ZipFile(output / 'payload.zip', 'x', zipfile.ZIP_DEFLATED, compresslevel=4) as new:
        tracked = {entry['path']: entry for entry in manifest['managedFiles']}
        for entry in old.infolist():
            name = entry.filename
            if name.startswith(('mods/mcheli-ce-', 'mods/techguns-')) or name in additions:
                continue
            data = old.read(name)
            if name in tracked and hashlib.sha256(data).hexdigest() != tracked[name]['sha256']:
                raise ValueError('Baseline managed file failed its checksum: ' + name)
            if name == 'config/mcheli.cfg':
                data = data.replace(b'Explosion_FlamingBlock=true', b'Explosion_FlamingBlock=false')
            if name == 'PRESETS/optionsshaders.txt':
                data = re.sub(rb'(?m)^shaderPack=.*$', b'shaderPack=OFF', data)
            if name.startswith('PRESETS/options-') and name.endswith('.txt'):
                data = re.sub(rb'(?m)^renderDistance:.*$', b'renderDistance:6', data)
            new.writestr(entry, data)
            if name in tracked:
                updated.append(dict(tracked[name], sha256=hashlib.sha256(data).hexdigest()))
        for name, data in additions.items():
            new.writestr(name, data)
            metadata = {'path': name, 'sha256': hashlib.sha256(data).hexdigest()}
            if name.startswith('mcheli_addons/'):
                metadata['existingOnly'] = True
            updated.append(metadata)
    shutil.copy2(base / 'runtime.zip', output / 'runtime.zip')
    shutil.copy2(base / 'installer-files.json', output / 'installer-files.json')
    manifest['version'] = version
    manifest['managedFiles'] = sorted(updated, key=lambda entry: entry['path'])
    manifest['archives'] = [{'path': name, 'sha256': digest(output / name)} for name in ('payload.zip', 'runtime.zip')]
    (output / 'package-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    with zipfile.ZipFile(output / 'payload.zip') as archive:
        if archive.testzip() is not None:
            raise ValueError('New payload failed ZIP integrity verification')
        for entry in manifest['managedFiles']:
            if hashlib.sha256(archive.read(entry['path'])).hexdigest() != entry['sha256']:
                raise ValueError('New managed checksum mismatch: ' + entry['path'])
    report = {'base': str(output), 'version': version, 'jarSha256': digest(jar), 'techgunsSha256': digest(techguns), 'audioSha256': digest(audio), 'managedFiles': len(updated), 'payloadBytes': (output / 'payload.zip').stat().st_size, 'addonResources': len([name for name in additions if name.startswith('mcheli_addons/')]), 'vendorMods': sorted(name for name in additions if name.startswith('mods/') and name not in ('mods/mcheli-ce-1.5.1-rv.jar', 'mods/techguns-1.12.2-rv.jar')), 'noticesSha256': digest(notices) if notices else None}
    print(json.dumps(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jar', type=Path, required=True)
    parser.add_argument('--techguns', type=Path, required=True)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--version', default='1.0.0')
    parser.add_argument('--asset-map', type=Path)
    parser.add_argument('--comfort-mods', type=Path)
    parser.add_argument('--vendor-registry', type=Path)
    parser.add_argument('--comfort-config', type=Path)
    parser.add_argument('--notices', type=Path)
    args = parser.parse_args()
    repack(args.base, args.output, args.jar, args.techguns, args.audio, args.version, args.asset_map, args.comfort_mods, args.vendor_registry, args.comfort_config, args.notices)
