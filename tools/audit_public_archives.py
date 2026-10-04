import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import zipfile

LIMITS = {'depth': 8, 'entries': 200000, 'memberBytes': 536870912, 'topBytes': 2147483648, 'expandedBytes': 17179869184}
LEGACY_CASE_COLLISIONS = {
    'b72c9dd7e6dd0f7438c01ea8e440519bf4a3c0b47674810929a9c899dc98b406': 'JourneyMap 1.12.2-5.7.1p3, unchanged published RV 1.1.0',
    'f6339650a40b6473d76e38d6c73bb82221a988918d319888c272580489f729da': 'WorldEdit CUI FE3 1.12.2-3.0.9, unchanged published RV 1.1.0',
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_member(name):
    if '\\' in name or name.startswith('/'):
        return False
    parts = name.rstrip('/').split('/')
    for part in parts:
        if not part or part in ('.', '..') or part.endswith(('.', ' ')) or re.search(r'[\x00-\x1f<>:"|?*]', part):
            return False
        if re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part):
            return False
    return True


def populated_connection_json(data):
    data = data.strip()
    if len(data) > 65536:
        if not data.removeprefix(b'\xef\xbb\xbf').startswith((b'{', b'[')):
            return False
        return re.search(rb'"connectionTarget"\s*:\s*"[^"\s]', data) is not None or re.search(rb'"product"\s*:\s*"RV"', data) is not None and re.search(rb'"transport"\s*:\s*"porthole"', data) is not None and re.search(rb'"target"\s*:\s*"[^"\s]', data) is not None
    try:
        text = data.decode('utf-16') if data.startswith((b'\xff\xfe', b'\xfe\xff')) else data.decode('utf-8-sig')
        if not text.lstrip().startswith(('{', '[')):
            return False
        document = json.loads(text, object_pairs_hook=tuple)
    except (ValueError, UnicodeError, RecursionError):
        return False
    def inspect(value, depth=0):
        if depth > 64:
            return False
        if isinstance(value, tuple):
            if any(key == 'connectionTarget' and isinstance(item, str) and item.strip() for key, item in value):
                return True
            products = [item for key, item in value if key == 'product']
            transports = [item for key, item in value if key == 'transport']
            targets = [item for key, item in value if key == 'target']
            if 'RV' in products and 'porthole' in transports and any(isinstance(item, str) and item.strip() for item in targets):
                return True
            return any(inspect(item, depth + 1) for key, item in value)
        if isinstance(value, list):
            return any(inspect(item, depth + 1) for item in value)
        return False
    return inspect(document)


def audit_archives(paths, catalog, public=True):
    if type(public) is not bool:
        raise ValueError('Public archive mode must be a boolean')
    catalog_bytes = Path(catalog).read_bytes() if isinstance(catalog, (str, Path)) else None
    definition = json.loads(catalog_bytes) if catalog_bytes is not None else catalog
    forbidden = {}
    for entry in definition['files']:
        if entry.get('delivery') == 'official-download' or not entry.get('rights', {}).get('rehostAllowed', False):
            forbidden.setdefault(entry['sha256'], []).append({'id': entry['id'], 'path': entry['path'], 'kind': 'official-vendor'})
            for child in entry.get('embedded', []):
                forbidden.setdefault(child['sha256'], []).append({'id': entry['id'], 'path': child['path'], 'kind': 'embedded-content'})
    if not forbidden or any(not re.fullmatch('[a-f0-9]{64}', value) for value in forbidden):
        raise ValueError('Invalid or empty forbidden byte inventory')
    report = {'passed': False, 'public': public, 'status': 'PUBLIC_ARCHIVE_AUDIT_FAILED' if public else 'PRIVATE_ARCHIVE_AUDIT_FAILED', 'scope': 'Exact forbidden byte SHA and ZIP path/CRC audit at top and recursively nested members; public mode also rejects invitations and populated connection defaults; no extraction, execution or gameplay acceptance', 'catalogSha256': sha256(catalog_bytes) if catalog_bytes is not None else None, 'catalogCanonicalSha256': sha256(json.dumps(definition, sort_keys=True, separators=(',', ':')).encode()), 'forbiddenSha256': forbidden, 'limits': dict(LIMITS), 'inputs': [], 'findings': [], 'counts': {'filesHashed': 0, 'archives': 0, 'entries': 0, 'expandedBytes': 0, 'maxDepth': 0}}

    def finding(kind, location, **details):
        report['findings'].append({'kind': kind, 'location': location, **details})

    def check_bytes(digest, location):
        report['counts']['filesHashed'] += 1
        if digest in forbidden:
            finding('FORBIDDEN_VENDOR_BYTES', location, sha256=digest, matched=forbidden[digest])

    def check_private(data, location, name):
        if public and (name.casefold().endswith('.rvinvite') or populated_connection_json(data)):
            finding('PRIVATE_CONNECTION_DATA', location)

    report['legacyCaseCollisionPins'] = dict(LEGACY_CASE_COLLISIONS)
    report['legacyCaseCollisions'] = []

    def scan_archive(source, location, depth, archive_digest):
        if depth > LIMITS['depth']:
            finding('DEPTH_LIMIT', location, depth=depth)
            return
        report['counts']['maxDepth'] = max(report['counts']['maxDepth'], depth)
        report['counts']['archives'] += 1
        try:
            with zipfile.ZipFile(source) as archive:
                entries = archive.infolist()
                report['counts']['entries'] += len(entries)
                if report['counts']['entries'] > LIMITS['entries']:
                    finding('ENTRY_LIMIT', location)
                    return
                seen = {}
                for entry in entries:
                    member_location = location + '!' + entry.filename
                    if not safe_member(entry.filename):
                        finding('UNSAFE_MEMBER_PATH', member_location)
                        continue
                    key = entry.filename.rstrip('/').casefold()
                    if key in seen:
                        if archive_digest in LEGACY_CASE_COLLISIONS and seen[key] != entry.filename.rstrip('/'):
                            report['legacyCaseCollisions'].append({'location': member_location, 'archiveSha256': archive_digest, 'previous': seen[key]})
                        else:
                            finding('DUPLICATE_MEMBER', member_location)
                    seen[key] = entry.filename.rstrip('/')
                    if stat.S_ISLNK(entry.external_attr >> 16):
                        finding('SYMLINK_MEMBER', member_location)
                        continue
                    if entry.flag_bits & 1:
                        finding('ENCRYPTED_MEMBER', member_location)
                        continue
                    if entry.is_dir():
                        continue
                    if entry.file_size > LIMITS['memberBytes']:
                        finding('MEMBER_SIZE_LIMIT', member_location, size=entry.file_size)
                        continue
                    if report['counts']['expandedBytes'] + entry.file_size > LIMITS['expandedBytes']:
                        finding('EXPANSION_LIMIT', member_location)
                        return
                    buffer = io.BytesIO()
                    digest = hashlib.sha256()
                    read = 0
                    with archive.open(entry) as member:
                        while True:
                            data = member.read(1048576)
                            if not data:
                                break
                            read += len(data)
                            report['counts']['expandedBytes'] += len(data)
                            if read > LIMITS['memberBytes'] or report['counts']['expandedBytes'] > LIMITS['expandedBytes']:
                                finding('ACTUAL_EXPANSION_LIMIT', member_location)
                                return
                            digest.update(data)
                            buffer.write(data)
                    if read != entry.file_size:
                        finding('MEMBER_SIZE_MISMATCH', member_location, read=read, declared=entry.file_size)
                        continue
                    check_bytes(digest.hexdigest(), member_location)
                    check_private(buffer.getvalue(), member_location, entry.filename)
                    buffer.seek(0)
                    if zipfile.is_zipfile(buffer):
                        buffer.seek(0)
                        scan_archive(buffer, member_location, depth + 1, digest.hexdigest())
                    elif buffer.getvalue().startswith((b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08')) or entry.filename.lower().endswith(('.zip', '.jar')):
                        finding('INVALID_NESTED_ARCHIVE', member_location)
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError, EOFError) as exc:
            finding('ARCHIVE_READ_ERROR', location, error=str(exc))

    unique_paths = set()
    for value in paths:
        path = Path(value).resolve()
        key = str(path).casefold()
        if key in unique_paths:
            finding('DUPLICATE_INPUT', str(path))
            continue
        unique_paths.add(key)
        if not path.is_file():
            finding('MISSING_INPUT', str(path))
            continue
        size = path.stat().st_size
        if size > LIMITS['topBytes']:
            finding('INPUT_SIZE_LIMIT', str(path), size=size)
            continue
        digest = hashlib.sha256()
        with path.open('rb') as file:
            while data := file.read(1048576):
                digest.update(data)
        actual = digest.hexdigest()
        report['inputs'].append({'path': str(path), 'size': size, 'sha256': actual})
        check_bytes(actual, str(path))
        if public and path.name.casefold().endswith('.rvinvite'):
            finding('PRIVATE_CONNECTION_DATA', str(path))
        try:
            is_archive = zipfile.is_zipfile(path)
            if is_archive:
                scan_archive(path, str(path), 0, actual)
            else:
                with path.open('rb') as file:
                    data = file.read(65537)
                    check_private(data, str(path), '')
                    prefix = data[:4]
                if prefix.startswith(b'PK') or path.suffix.lower() in ('.zip', '.jar'):
                    finding('INVALID_INPUT_ARCHIVE', str(path))
        except OSError as exc:
            finding('INPUT_READ_ERROR', str(path), error=str(exc))
        if path.stat().st_size != size:
            finding('INPUT_CHANGED_DURING_SCAN', str(path))
    if not report['inputs']:
        finding('NO_INPUTS', '')
    report['passed'] = not report['findings']
    if report['passed']:
        report['status'] = 'PUBLIC_ARCHIVE_BYTES_READY' if public else 'PRIVATE_ARCHIVE_BYTES_READY'
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--catalog', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('paths', nargs='+', type=Path)
    args = parser.parse_args()
    result = audit_archives(args.paths, args.catalog)
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
