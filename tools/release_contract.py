import hashlib
import json
from pathlib import Path
import re


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


def validate_base(base, expected_path):
    base = Path(base)
    manifest = json.loads((base / 'package-manifest.json').read_text(encoding='utf-8-sig'))
    expected = json.loads(Path(expected_path).read_text(encoding='utf-8-sig'))
    archives = {entry['path']: entry['sha256'] for entry in manifest['archives']}
    if len(manifest['archives']) != 2 or set(archives) != {'payload.zip', 'runtime.zip'}:
        raise ValueError('Unexpected base archives')
    expected_runtime = next(entry['sha256'] for entry in expected['archives'] if entry['path'] == 'runtime.zip')
    if archives['runtime.zip'] != expected_runtime or managed_hashes(manifest) != managed_hashes(expected):
        raise ValueError('Base gameplay differs from pack/package-manifest.json. Prepare a verified matching binary base.')
    for name, digest in archives.items():
        if not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid base archive checksum')
        with (base / name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise ValueError('Base archive checksum mismatch: ' + name)
    return manifest
