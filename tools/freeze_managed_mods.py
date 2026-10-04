import argparse
import json
from pathlib import Path

from vendor_catalog import load_catalog, load_native_projection, require, safe_path, sha256_file, validate_catalog, validate_native_union, verify_artifact, verify_managed_sources


def freeze(spec_path, root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    require(not output.exists(), 'Owned proof output must be a new file')
    spec = json.loads(Path(spec_path).read_text(encoding='utf-8-sig'))
    require(spec.get('schema') == 1 and isinstance(spec.get('mods'), list) and bool(spec['mods']), 'Missing owned build descriptors')
    receipts, native = [], {}
    for side in ('client', 'server'):
        name = safe_path(spec.get('nativeReceipts', {}).get(side))
        path = root / name
        data = load_native_projection(root, name)
        native[side] = data
        receipts.append({'side': side, 'path': name, 'sha256': sha256_file(path)})
    mods = []
    artifacts = []
    for descriptor in spec['mods']:
        require(set(descriptor) == {'id', 'path', 'fileVersion', 'side', 'fml', 'sourceFiles', 'artifact'}, 'Invalid owned build descriptor fields')
        artifact = Path(descriptor['artifact'])
        if not artifact.is_absolute():
            artifact = Path(spec_path).resolve().parent / artifact
        entry = {key: descriptor[key] for key in ('id', 'path', 'fileVersion', 'side', 'fml', 'sourceFiles')}
        entry.update(size=artifact.stat().st_size, sha256=sha256_file(artifact), expectedModIds=sorted(entry['fml']), nativeReceiptSha256=receipts[0]['sha256'])
        mods.append(entry)
        artifacts.append(artifact)
    catalog = load_catalog(root / 'pack/vendor-catalog.json')
    composed = validate_catalog({**catalog, 'managedMods': mods})
    require(all(entry['side'] == 'both' for entry in mods), 'Owned modules require both native sides')
    verify_managed_sources(composed, root)
    expected_mods = {name: version for entry in mods for name, version in entry['fml'].items()}
    for data in native.values():
        validate_native_union(data, mods)
    for entry, artifact in zip(mods, artifacts):
        verify_artifact(entry, artifact)
    proof = {'schema': 1, 'mods': mods, 'nativeReceipts': receipts}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write((json.dumps(proof, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return {'mods': expected_mods, 'managedModsSha256': sha256_file(output), 'nativeSides': sorted(native)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(freeze(arguments.spec, arguments.root, arguments.output)))
