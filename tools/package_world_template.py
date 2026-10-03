import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


def package(stage, output):
    stage, output = Path(stage).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Output already exists; choose a new archive path')
    manifest = json.loads((stage / 'world-template-manifest.json').read_text(encoding='utf-8'))
    name = manifest['name']
    if name != 'Battlefield-Extended' or not all(manifest.get(key) is True for key in ('functionsIncluded', 'playerBookIncluded', 'scoreboardIncluded')):
        raise ValueError('A complete integrated world stage is required')
    if manifest.get('scoreboardPlayerEntries') != 0:
        raise ValueError('World stage contains player scoreboard data')
    world = stage / name
    paths = {path.relative_to(stage).as_posix(): path for path in world.rglob('*') if path.is_file()}
    if set(paths) != set(manifest['files']):
        raise ValueError('World stage inventory differs from its manifest')
    files = {}
    regions = 0
    for relative, path in sorted(paths.items()):
        allowed = relative in {name + '/level.dat', name + '/data/scoreboard.dat'} or re.fullmatch(re.escape(name) + r'/region/r\.-?\d+\.-?\d+\.mca', relative) or re.fullmatch(re.escape(name) + r'/data/functions/warfare/[A-Za-z0-9_]+\.mcfunction', relative) or re.fullmatch(re.escape(name) + r'/data/functions/rvmap/(tree_0[1-9]|tree_1[0-2]|plants)\.mcfunction', relative)
        if not allowed or path.is_symlink():
            raise ValueError('Unexpected world stage file: ' + relative)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest['files'][relative]:
            raise ValueError('World stage checksum mismatch: ' + relative)
        if relative.endswith('.mca'):
            regions += 1
        if relative.endswith('.dat'):
            uncompressed = gzip.decompress(data)
            stream = io.BytesIO()
            with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0, compresslevel=9) as compressed:
                compressed.write(uncompressed)
            data = stream.getvalue()
        files[relative] = data
    if regions != len(manifest['regions']) or name + '/level.dat' not in files or name + '/data/scoreboard.dat' not in files:
        raise ValueError('World stage is incomplete')
    prefix = name + '/data/functions/warfare/'
    for function in ('tick', 'boot', 'book_tick', 'book_setup', 'book_give_en', 'book_give_ru'):
        if prefix + function + '.mcfunction' not in files:
            raise ValueError('Missing world function: ' + function)
    map_prefix = name + '/data/functions/rvmap/'
    map_functions = {relative for relative in files if relative.startswith(map_prefix)}
    required_map_functions = {map_prefix + 'tree_' + str(number).zfill(2) + '.mcfunction' for number in range(1, 13)} | {map_prefix + 'plants.mcfunction'}
    if map_functions and map_functions != required_map_functions:
        raise ValueError('Curated RV map decoration functions are incomplete')
    if sum(relative.endswith('.mcfunction') for relative in files) != manifest['functionCount']:
        raise ValueError('World function count differs from manifest')
    manifest['files'] = {relative: hashlib.sha256(data).hexdigest() for relative, data in sorted(files.items())}
    files['world-template-manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
    files['INSTALL-NEW-WORLD.md'] = (stage / 'INSTALL-NEW-WORLD.md').read_bytes()
    files['SHA256SUMS.txt'] = ''.join(hashlib.sha256(data).hexdigest() + '  ' + relative + '\n' for relative, data in sorted(files.items())).encode('ascii')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for relative, data in sorted(files.items()):
            info = zipfile.ZipInfo(relative, (2021, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=6)
    return {'archive': str(output), 'bytes': output.stat().st_size, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'files': len(files)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Package a verified clean integrated world; never modify its stage or a live server.')
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.stage, args.output)))
