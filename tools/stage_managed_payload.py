import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile

from download_release_base import safe_entries
from release_contract import validate_base
from vendor_catalog import load_catalog, require, safe_path, sha256_file, validate_catalog, verify_artifact, verify_first_party_proof, verify_managed_delivery, verify_managed_sources


def stage(base, artifacts, proof_path, root, output, version):
    base, artifacts, root, output = (Path(path).resolve() for path in (base, artifacts, root, output))
    require(not output.exists() and output != base and base not in output.parents, 'Owned payload output must be a new directory outside the baseline')
    require(re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version) is not None, 'Invalid package version')
    manifest = validate_base(base, base / 'package-manifest.json')
    catalog = load_catalog(root / 'pack/vendor-catalog.json')
    proof = json.loads(Path(proof_path).read_text(encoding='utf-8-sig'))
    require(proof.get('schema') == 1 and isinstance(proof.get('mods'), list) and bool(proof['mods']), 'Missing owned proof')
    composed = validate_catalog({**catalog, 'managedMods': proof['mods']})
    verify_managed_sources(composed, root)
    prior_path = base / 'rv-managed-mods.json'
    prior = set()
    if prior_path.exists():
        metadata = json.loads((base / 'release.json').read_text(encoding='utf-8-sig'))
        require(metadata.get('managedModsSha256') == sha256_file(prior_path), 'Baseline owned registry differs from its release digest')
        previous = json.loads(prior_path.read_text(encoding='utf-8-sig'))
        validate_catalog({**catalog, 'managedMods': previous['mods']})
        prior = {entry['path'] for entry in previous['mods']}
    additions = {}
    with zipfile.ZipFile(base / 'payload.zip') as archive:
        safe_entries(archive)
        verify_managed_delivery(catalog, manifest, archive, 'client')
        for entry in proof['mods']:
            name = safe_path(entry['path'])
            artifact = artifacts / name
            if artifact.is_file():
                verify_artifact(entry, artifact)
                additions[name] = artifact.read_bytes()
            else:
                require(name in archive.namelist(), 'Owned artifact is absent from staging and the baseline: ' + name)
                data = archive.read(name)
                require(len(data) == entry['size'] and hashlib.sha256(data).hexdigest() == entry['sha256'], 'Baseline owned artifact differs from the new proof: ' + name)
                additions[name] = data
    tracked = {entry['path']: entry for entry in manifest['managedFiles']}
    retire = prior - set(additions)
    patterns = list(manifest.get('managedModPatterns', []))
    for entry in proof['mods']:
        filename = PurePosixPath(entry['path']).name
        suffix = entry['fileVersion'] + '.jar'
        require(re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', entry['fileVersion']) is not None and filename.endswith('-' + suffix) and filename.startswith('rv-'), 'Owned artifact must use a bounded RV semantic-version filename')
        pattern = '^' + re.escape(filename[:-len(suffix)]) + r'[0-9]+\.[0-9]+\.[0-9]+\.jar$'
        if pattern not in patterns:
            patterns.append(pattern)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.' + output.name + '-stage-', dir=output.parent) as temporary:
        staged = Path(temporary).resolve()
        require(staged.parent == output.parent, 'Staging directory escaped the output parent')
        updated = []
        with zipfile.ZipFile(base / 'payload.zip') as old, zipfile.ZipFile(staged / 'payload.zip', 'x', zipfile.ZIP_DEFLATED, compresslevel=4) as new:
            for info in old.infolist():
                name = info.filename
                if name in additions or name in retire:
                    continue
                new.writestr(info, old.read(name))
            for name, data in additions.items():
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                new.writestr(info, data)
            for name, entry in tracked.items():
                if name not in additions and name not in retire:
                    updated.append(entry)
            for name, data in additions.items():
                updated.append({**tracked.get(name, {}), 'path': name, 'sha256': hashlib.sha256(data).hexdigest()})
        for name in ('runtime.zip', 'installer-files.json'):
            shutil.copyfile(base / name, staged / name)
        manifest.update(version=version, managedFiles=sorted(updated, key=lambda entry: entry['path']), managedModPatterns=patterns)
        manifest['archives'] = [{'path': name, 'sha256': sha256_file(staged / name)} for name in ('payload.zip', 'runtime.zip')]
        with zipfile.ZipFile(staged / 'payload.zip') as archive:
            safe_entries(archive)
            require(archive.testzip() is None, 'Staged owned payload failed CRC verification')
            verify_managed_delivery(composed, manifest, archive, 'client')
            identities = verify_first_party_proof(proof_path, catalog, manifest, archive, root)
        (staged / 'package-manifest.json').write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        staged.rename(output)
    return {'version': version, 'mods': identities, 'payloadSha256': sha256_file(output / 'payload.zip'), 'runtimeSha256': sha256_file(output / 'runtime.zip'), 'managedFiles': len(updated), 'retiredOwnedPaths': sorted(retire)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', required=True)
    arguments = parser.parse_args()
    print(json.dumps(stage(arguments.base, arguments.artifacts, arguments.proof, arguments.root, arguments.output, arguments.version)))
