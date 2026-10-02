import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
from validate_package import audit


EXPECTED = {
    'mods/mcheli-ce-1.5.1-rv.jar': 'c3fd8a25c8124bc9ede55d4de65735d8be6c3115a22d1ec956e9eb0e161ee714',
    'mods/techguns-1.12.2-rv.jar': 'fc8d6797101e76b4e05d96072ee5df0ff65d194645a405f8adfcbae342b66dca',
    'resourcepacks/Warfare-Combat-Audio.zip': 'fb1478bcfcf7f45cd56402fd525cd86d7cc21b8b6d928246431c23fb8e4cab7b',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--private', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.archive)
    assert not result['errors'], result['errors']
    nested = args.output.parent / (args.output.stem + '-members')
    nested.mkdir(exist_ok=True)
    report = {'archive_sha256': result['sha256'], 'archive_bytes': result['bytes'], 'outer_errors': result['errors'], 'outer_warnings': result['warnings']}
    with zipfile.ZipFile(args.archive) as archive:
        root = 'RV-Setup/'
        assert all(name.startswith(root) for name in archive.namelist())
        release = json.loads(archive.read(root + 'release.json'))
        assert release == {'version': '1.0.0', 'repository': 'rudyvale/rv-warfare'}, release
        report['release'] = release
        defaults = json.loads(archive.read(root + 'server-defaults.json'))
        target = defaults['connectionTarget']
        assert defaults['connectionMode'] == 'porthole' and defaults['serverPort'] == 25565
        assert bool(target) == args.private
        if args.private:
            assert re.fullmatch(r'peer:[0-9]{17}', target), 'Private preset must use stable Steam peer'
        report['private_connection_preset'] = bool(target)
        manifest = json.loads(archive.read(root + 'package-manifest.json'))
        assert manifest['version'] == release['version']
        assert {entry['path'] for entry in manifest['archives']} == {'payload.zip', 'runtime.zip'}
        for entry in manifest['archives']:
            data = archive.read(root + entry['path'])
            assert sha(data) == entry['sha256'], entry['path']
            destination = nested / entry['path']
            destination.write_bytes(data)
            details = audit(destination)
            assert not details['errors'], details['errors']
            report[entry['path']] = {'sha256': entry['sha256'], 'entries': details['entries'], 'errors': details['errors'], 'warnings': details['warnings']}
        forbidden = re.compile(r'(?i)generated\s+by|automatically\s+generated|language\s+model')
        for name in archive.namelist():
            if name.endswith(('.md', '.ps1', '.cmd', '.json')):
                assert not forbidden.search(archive.read(name).decode('utf-8-sig')), name
    with zipfile.ZipFile(nested / 'payload.zip') as payload:
        names = payload.namelist()
        private = {'saves', 'logs', 'crash-reports', 'playerdata', 'stats', 'advancements', '.git', '.local', 'vm-owner.json', 'warfare-settings.json', 'launcher_accounts.json', 'servers.dat'}
        bad = [name for name in names if any(part.casefold() in private for part in name.replace('\\', '/').split('/'))]
        assert not bad, bad
        for entry in manifest['managedFiles']:
            assert sha(payload.read(entry['path'])) == entry['sha256'], entry['path']
        report['managed_files_verified'] = len(manifest['managedFiles'])
        for name, digest in EXPECTED.items():
            assert sha(payload.read(name)) == digest, name
        report['gameplay_hashes'] = EXPECTED
        mch = [name for name in names if name.startswith('mods/mcheli') and name.endswith('.jar')]
        tg = [name for name in names if name.startswith('mods/techguns') and name.endswith('.jar')]
        assert len(mch) == len(tg) == 1
        with zipfile.ZipFile(io.BytesIO(payload.read(mch[0]))) as mod:
            assert not any(name.startswith(('RVCombatAcceptance', 'VMControlsRuntime', 'VMControlsClientRuntime', 'VMControlsTest', 'net/minecraft/')) for name in mod.namelist())
        shader = payload.read('PRESETS/optionsshaders.txt').decode('utf-8-sig')
        assert re.search(r'^shaderPack=OFF$', shader, re.M)
        for language in ('ru', 'en'):
            options = payload.read('PRESETS/options-' + language + '.txt').decode('utf-8-sig')
            assert re.search(r'^renderDistance:6$', options, re.M)
            assert not re.search(r'^lastServer:.+', options, re.M)
        report['factory_shader_off'] = True
        report['factory_render_distance'] = 6
    report['passed'] = True
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
