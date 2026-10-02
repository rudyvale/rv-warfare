import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def repack(base, output, jar, techguns, audio):
    base, output = base.resolve(), output.resolve()
    if output.exists() or output == base or base in output.parents:
        raise ValueError('Output must be a new directory outside the baseline')
    manifest = json.loads((base / 'package-manifest.json').read_text(encoding='utf-8-sig'))
    for archive in manifest['archives']:
        if digest(base / archive['path']) != archive['sha256']:
            raise ValueError('Baseline archive failed its checksum')
    additions = {'mods/mcheli-ce-1.5.1-rv.jar': jar.read_bytes(), 'mods/techguns-1.12.2-rv.jar': techguns.read_bytes(), 'resourcepacks/Warfare-Combat-Audio.zip': audio.read_bytes()}
    with zipfile.ZipFile(jar) as mod:
        required = ['com/norwood/mcheli/uav/WarfareOwnerAuth.class', 'com/norwood/mcheli/vm/VMVec2f.class', 'com/norwood/mcheli/vm/VMImpact.class']
        if any(name not in mod.namelist() for name in required) or any(name.startswith(('VMControlsRuntime', 'VMControlsClientRuntime', 'RVCombatAcceptance')) for name in mod.namelist()):
            raise ValueError('Jar is incomplete or contains runtime test hooks')
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
    manifest['version'] = '1.0.0'
    manifest['managedFiles'] = sorted(updated, key=lambda entry: entry['path'])
    manifest['archives'] = [{'path': name, 'sha256': digest(output / name)} for name in ('payload.zip', 'runtime.zip')]
    (output / 'package-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    with zipfile.ZipFile(output / 'payload.zip') as archive:
        if archive.testzip() is not None:
            raise ValueError('New payload failed ZIP integrity verification')
        for entry in manifest['managedFiles']:
            if hashlib.sha256(archive.read(entry['path'])).hexdigest() != entry['sha256']:
                raise ValueError('New managed checksum mismatch: ' + entry['path'])
    print(json.dumps({'base': str(output), 'jarSha256': digest(jar), 'techgunsSha256': digest(techguns), 'audioSha256': digest(audio), 'managedFiles': len(updated), 'payloadBytes': (output / 'payload.zip').stat().st_size}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jar', type=Path, required=True)
    parser.add_argument('--techguns', type=Path, required=True)
    parser.add_argument('--audio', type=Path, required=True)
    args = parser.parse_args()
    repack(args.base, args.output, args.jar, args.techguns, args.audio)
