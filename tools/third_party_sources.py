import hashlib
import io
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
import zipfile
from download_release_base import safe_entries


def load_registry(path):
    registry = json.loads(Path(path).read_text(encoding='utf-8'))
    components = registry.get('components')
    if registry.get('schema') != 1 or registry.get('minecraft') != '1.12.2' or not isinstance(components, list) or not components:
        raise ValueError('Invalid third-party source registry')
    seen = set()
    for entry in components:
        mod_id = entry['modId']
        if not re.fullmatch('[a-z0-9_]+', mod_id) or mod_id in seen:
            raise ValueError('Invalid or duplicate third-party mod ID')
        seen.add(mod_id)
        if not re.fullmatch('[A-Za-z0-9_.-]+\\.jar', entry['binaryFile']):
            raise ValueError('Invalid vendor binary filename')
        if not re.fullmatch('https://github.com/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', entry['sourceRepository']) or not re.fullmatch('[0-9a-f]{40}', entry['sourceCommit']):
            raise ValueError('Invalid pinned upstream source')
        repository = entry['sourceRepository'].removeprefix('https://github.com/')
        if entry['sourceUrl'] != 'https://codeload.github.com/' + repository + '/zip/' + entry['sourceCommit']:
            raise ValueError('Source URL differs from the pinned commit')
        expected_archive = 'sources/' + repository.split('/')[-1] + '-' + entry['sourceCommit'][:12] + '.zip'
        if entry['sourceArchive'] != expected_archive:
            raise ValueError('Invalid source archive name')
        for field in ('binarySha256', 'sourceSha256'):
            if not isinstance(entry[field], str) or not re.fullmatch('[0-9a-f]{64}', entry[field]):
                raise ValueError('Invalid third-party checksum')
        for field in ('binarySize', 'sourceSize'):
            if type(entry[field]) is not int or not 0 < entry[field] <= 67108864:
                raise ValueError('Invalid third-party size')
        licenses = entry['licenses']
        if not isinstance(licenses, list) or not licenses or len({item['sourcePath'] for item in licenses}) != len(licenses):
            raise ValueError('Invalid upstream license list')
        for item in licenses:
            if item['sourcePath'] not in ('LICENSE', 'LICENSE_HEADER', 'API_LICENSE', 'API_LICENSE_HEADER') or item['path'] != 'licenses/' + mod_id + '/' + item['sourcePath'] or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
                raise ValueError('Invalid upstream license entry')
        if 'LICENSE' not in {item['sourcePath'] for item in licenses}:
            raise ValueError('Upstream main license is missing')
    return registry


def archive_content(entry, data):
    if len(data) != entry['sourceSize'] or hashlib.sha256(data).hexdigest() != entry['sourceSha256']:
        raise ValueError('Upstream source checksum or size mismatch: ' + entry['modId'])
    result = {entry['sourceArchive']: data}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        safe_entries(archive)
        prefix = entry['sourceRepository'].rsplit('/', 1)[1] + '-' + entry['sourceCommit'] + '/'
        if any(not name.startswith(prefix) for name in archive.namelist()):
            raise ValueError('Upstream archive root differs from the pinned commit')
        for item in entry['licenses']:
            try:
                license_data = archive.read(prefix + item['sourcePath'])
            except KeyError:
                raise ValueError('Upstream license is missing') from None
            if hashlib.sha256(license_data).hexdigest() != item['sha256']:
                raise ValueError('Upstream license checksum mismatch')
            result[item['path']] = license_data
    return result


def download_source(entry, cache):
    target = Path(cache) / Path(entry['sourceArchive']).name
    if target.exists():
        data = target.read_bytes()
        archive_content(entry, data)
        return data
    target.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    request = urllib.request.Request(entry['sourceUrl'], headers={'User-Agent': 'RV-third-party-sources'})
    data = bytearray()
    with urllib.request.urlopen(request, timeout=30) as response:
        origin = urllib.parse.urlsplit(response.url)
        if origin.scheme != 'https' or origin.hostname != 'codeload.github.com':
            raise ValueError('Unexpected upstream source redirect')
        while block := response.read(1024 * 1024):
            data.extend(block)
            if len(data) > entry['sourceSize'] or time.monotonic() - started > 600:
                raise ValueError('Upstream source download exceeds its limit')
    data = bytes(data)
    archive_content(entry, data)
    with target.open('xb') as stream:
        stream.write(data)
    return data


def build_bundle(registry_path, notice_path, output, cache):
    output = Path(output)
    if output.exists():
        raise ValueError('Source bundle output already exists; choose a fresh path')
    registry = load_registry(registry_path)
    content = {'components.json': Path(registry_path).read_bytes(), 'README.md': Path(notice_path).read_bytes()}
    for entry in registry['components']:
        content.update(archive_content(entry, download_source(entry, cache)))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
        for name, data in sorted(content.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    verify_bundle(output, registry_path, notice_path)
    return {'asset': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'size': output.stat().st_size, 'components': len(registry['components'])}


def verify_bundle(path, registry_path, notice_path):
    registry = load_registry(registry_path)
    with zipfile.ZipFile(path) as archive:
        safe_entries(archive)
        if archive.read('components.json') != Path(registry_path).read_bytes() or archive.read('README.md') != Path(notice_path).read_bytes():
            raise ValueError('Source bundle registry or notices differ from the frozen source')
        expected = {'components.json', 'README.md'}
        for entry in registry['components']:
            content = archive_content(entry, archive.read(entry['sourceArchive']))
            expected.update(content)
            for name, data in content.items():
                if archive.read(name) != data:
                    raise ValueError('Source bundle license differs from the original source')
        if set(archive.namelist()) != expected:
            raise ValueError('Unexpected source bundle files')
    return registry


def verify_vendor_manifest(manifest, registry):
    managed = {entry['path']: entry['sha256'] for entry in manifest['managedFiles']}
    for entry in registry['components']:
        if managed.get('mods/' + entry['binaryFile']) != entry['binarySha256']:
            raise ValueError('Vendor binary differs from the source registry: ' + entry['modId'])


def verify_vendor_payload(payload, registry):
    for entry in registry['components']:
        try:
            data = payload.read('mods/' + entry['binaryFile'])
        except KeyError:
            raise ValueError('Vendor binary is missing: ' + entry['modId']) from None
        if len(data) != entry['binarySize'] or hashlib.sha256(data).hexdigest() != entry['binarySha256']:
            raise ValueError('Vendor binary differs from the source registry: ' + entry['modId'])
