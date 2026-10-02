import hashlib
import json
from pathlib import Path
import re

ASSETS = {'RV-Setup.zip', 'RV-Host-Tools.zip', 'RV-World-Template.zip', 'RV-Third-Party-Sources.zip', 'SHA256SUMS.txt'}


def require_source_asset(assets, version):
    if tuple(map(int, version.split('.'))) >= (1, 1, 0) and 'RV-Third-Party-Sources.zip' not in assets:
        raise ValueError('RV 1.1.0 requires the original third-party source asset')


def required_mods(metadata):
    version = metadata['version']
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Invalid release version')
    mods = metadata.get('requiredMods', {})
    if not isinstance(mods, dict) or any(not re.fullmatch(r'[a-z0-9_]+', name) or not isinstance(value, str) or not value or len(value) > 128 or any(character.isspace() for character in value) for name, value in mods.items()):
        raise ValueError('Invalid required mod versions')
    if tuple(map(int, version.split('.'))) >= (1, 1, 0) and not mods.get('mcheli'):
        raise ValueError('RV 1.1.0 requires the advertised mcheli protocol version')
    return mods


def checksums(output):
    result = {}
    for line in (Path(output) / 'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        digest, name = line.split('  ', 1)
        if name not in ASSETS - {'SHA256SUMS.txt'} or name in result or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid or duplicate checksum entry')
        result[name] = digest
    if not {'RV-Setup.zip', 'RV-Host-Tools.zip'}.issubset(result):
        raise ValueError('Incomplete checksum file')
    return result


def asset_hashes(output):
    output = Path(output)
    expected = checksums(output)
    result = {}
    for name in list(expected) + ['SHA256SUMS.txt']:
        with (output / name).open('rb') as stream:
            result[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        if name in expected and result[name] != expected[name]:
            raise ValueError('Candidate checksum mismatch: ' + name)
    return result


def managed_hashes(manifest):
    result = {}
    for entry in manifest['managedFiles']:
        name = entry['path'].replace('\\', '/')
        parts = name.split('/')
        if name.startswith('/') or ':' in name or any(part in ('', '.', '..') for part in parts):
            raise ValueError('Invalid managed path')
        key = name.casefold()
        if key in result or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
            raise ValueError('Invalid or duplicate managed file')
        result[key] = entry['sha256']
    result.pop('read-me.md', None)
    return result


def managed_policies(manifest):
    managed_hashes(manifest)
    result = {}
    for entry in manifest['managedFiles']:
        policy = {key: value for key, value in entry.items() if key not in ('path', 'sha256')}
        policy.setdefault('existingOnly', False)
        if not isinstance(policy['existingOnly'], bool):
            raise ValueError('Invalid managed preservation policy')
        result[entry['path'].replace('\\', '/').casefold()] = policy
    return result


def retirement_policy(manifest):
    patterns = manifest.get('managedModPatterns', [])
    optifine = manifest.get('optifineSha256')
    if not isinstance(patterns, list) or any(not isinstance(pattern, str) or not pattern or len(pattern) > 512 for pattern in patterns):
        raise ValueError('Invalid managed mod retirement policy')
    if optifine is not None and (not isinstance(optifine, str) or not re.fullmatch('[0-9a-f]{64}', optifine)):
        raise ValueError('Invalid OptiFine checksum policy')
    return {'managedModPatterns': patterns, 'optifineSha256': optifine}


def validate_addon_resources(manifest, payload, builtin, required=None):
    managed_hashes(manifest)
    resources = {}
    prefix = 'mcheli_addons/default/'
    for entry in manifest['managedFiles']:
        name = entry['path'].replace('\\', '/')
        if not name.startswith('mcheli_addons/'):
            continue
        if not name.startswith(prefix + 'assets/mcheli/') or entry.get('existingOnly') is not True:
            raise ValueError('Addon update must use bounded default resources with existingOnly=true')
        resource = name[len(prefix):]
        try:
            data = builtin.read(resource)
            installed = payload.read(name)
        except KeyError:
            raise ValueError('Addon resource is missing from the payload or builtin JAR: ' + resource) from None
        digest = hashlib.sha256(data).hexdigest()
        if installed != data or entry['sha256'] != digest:
            raise ValueError('Addon resource differs from the builtin JAR: ' + resource)
        resources[resource] = digest
    if required is not None and resources != required:
        raise ValueError('Addon update differs from the frozen resource map')
    return resources


def load_addon_map(path, jar_sha256):
    frozen = json.loads(Path(path).read_text(encoding='utf-8'))
    resources = frozen.get('resources')
    if frozen.get('schema') != 1 or not isinstance(resources, dict) or not resources:
        raise ValueError('Invalid frozen addon resource map')
    if frozen.get('mcheliSha256') != jar_sha256 or not re.fullmatch('[0-9a-f]{64}', jar_sha256):
        raise ValueError('Frozen addon map belongs to another MCHeli JAR')
    seen = set()
    for name, digest in resources.items():
        if not name.startswith('assets/mcheli/') or ':' in name or any(part in ('', '.', '..') for part in name.split('/')) or '\\' in name or name.casefold() in seen:
            raise ValueError('Invalid frozen addon resource path')
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid frozen addon resource checksum')
        seen.add(name.casefold())
    return resources


def validate_output(output, version, private=False, replace_candidate=False):
    output = Path(output)
    marker = output / '.release-candidate.json'
    if marker.exists():
        candidate = json.loads(marker.read_text(encoding='utf-8'))
        if candidate.get('schema') != 1:
            raise ValueError('Unknown candidate schema')
        if candidate.get('state') != 'candidate':
            raise ValueError('Published output is immutable; choose a new output directory')
        if candidate.get('version') != version or candidate.get('kind') != ('private' if private else 'public'):
            raise ValueError('Output belongs to another version or package type')
        if not replace_candidate:
            raise ValueError('Candidate output already exists; use --replace-candidate only before publication')
    elif any((output / name).exists() for name in ('RV-Setup.zip', 'RV-Host-Tools.zip', 'SHA256SUMS.txt', 'RV-Setup/release.json')):
        raise ValueError('Existing release output has no candidate marker; choose a new output directory')


def write_candidate(output, version, private=False):
    output = Path(output)
    assets = asset_hashes(output)
    require_source_asset(assets, version)
    marker = {'schema': 1, 'state': 'candidate', 'version': version, 'kind': 'private' if private else 'public', 'assets': assets}
    (output / '.release-candidate.json').write_text(json.dumps(marker, indent=2) + '\n', encoding='utf-8')


def validate_candidate(output, version):
    output = Path(output)
    marker = output / '.release-candidate.json'
    if not marker.exists():
        if version == '1.0.0':
            return None
        raise ValueError('Publication requires a verified public candidate marker')
    candidate = json.loads(marker.read_text(encoding='utf-8'))
    if candidate.get('schema') != 1 or candidate.get('state') not in ('candidate', 'published'):
        raise ValueError('Invalid candidate marker')
    if candidate.get('version') != version or candidate.get('kind') != 'public':
        raise ValueError('Only the matching public candidate may be published')
    require_source_asset(candidate.get('assets', {}), version)
    if candidate.get('assets') != asset_hashes(output):
        raise ValueError('Candidate assets changed after packaging')
    return candidate


def mark_published(output, version, commit, url):
    candidate = validate_candidate(output, version)
    if candidate is not None:
        candidate.update(state='published', tag='v' + version, sourceCommit=commit, releaseUrl=url)
        (Path(output) / '.release-candidate.json').write_text(json.dumps(candidate, indent=2) + '\n', encoding='utf-8')


def validate_base(base, expected_path):
    base = Path(base)
    manifest = json.loads((base / 'package-manifest.json').read_text(encoding='utf-8-sig'))
    expected = json.loads(Path(expected_path).read_text(encoding='utf-8-sig'))
    archives = {entry['path']: entry['sha256'] for entry in manifest['archives']}
    if len(manifest['archives']) != 2 or set(archives) != {'payload.zip', 'runtime.zip'}:
        raise ValueError('Unexpected base archives')
    expected_runtime = next(entry['sha256'] for entry in expected['archives'] if entry['path'] == 'runtime.zip')
    if archives['runtime.zip'] != expected_runtime or managed_hashes(manifest) != managed_hashes(expected) or managed_policies(manifest) != managed_policies(expected) or retirement_policy(manifest) != retirement_policy(expected):
        raise ValueError('Base gameplay differs from pack/package-manifest.json. Prepare a verified matching binary base.')
    for name, digest in archives.items():
        if not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid base archive checksum')
        with (base / name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError('Base archive checksum mismatch: ' + name)
    return manifest
