import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
import zipfile

from world_reset import maintenance


MANIFEST = '.vendor-installed.json'
JOURNAL = '.vendor-update.json'
PATH = re.compile(r'^(mods/[A-Za-z0-9][A-Za-z0-9._+ -]*\.jar|[Mm]odular[Ww]arfare/[A-Za-z0-9][A-Za-z0-9._+ -]*\.(zip|jar))$')
SHA = re.compile(r'^[a-f0-9]{64}$')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def guarded(path):
    path = Path(os.path.abspath(path))
    for parent in (path, *path.parents):
        if parent.exists() or parent.is_symlink():
            info = parent.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
                raise ValueError('RV_VENDOR_PATH')
    return path


def target(root, name):
    if not isinstance(name, str) or not PATH.fullmatch(name) or re.search(r'(^|/)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)', name, re.I):
        raise ValueError('RV_VENDOR_PATH')
    root = guarded(root)
    path = guarded(root / name)
    if not path.is_relative_to(root):
        raise ValueError('RV_VENDOR_PATH')
    return path


def read(path):
    if Path(path).stat().st_size > 2 * 1024 * 1024:
        raise ValueError('RV_VENDOR_CATALOG')
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('RV_VENDOR_CATALOG')
    return value


def atomic_json(path, value):
    path = guarded(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def record_valid(item):
    return isinstance(item, dict) and isinstance(item.get('id'), str) and re.fullmatch(r'[a-z0-9][a-z0-9-]*', item['id']) and isinstance(item.get('sha256'), str) and SHA.fullmatch(item['sha256']) and type(item.get('size')) is int and 0 < item['size'] <= 1024 ** 3


def matches(path, item):
    return path.is_file() and path.stat().st_size == item['size'] and digest(path) == item['sha256']


def contract(root):
    root = guarded(root)
    release_path, catalog_path = guarded(root / 'release.json'), guarded(root / 'vendor-catalog.json')
    release = read(release_path)
    expected = release.get('vendorCatalogSha256')
    if not isinstance(expected, str) or not SHA.fullmatch(expected) or digest(catalog_path) != expected:
        raise ValueError('RV_VENDOR_CATALOG_DIGEST')
    catalog = read(catalog_path)
    if catalog.get('schema') != 1 or catalog.get('state') != 'pinned' or catalog.get('minecraft') != '1.12.2' or catalog.get('loader') != 'forge' or catalog.get('javaMajor') != 8 or not isinstance(catalog.get('files'), list):
        raise ValueError('RV_VENDOR_CATALOG')
    selected, ids, paths = [], set(), set()
    for item in catalog['files']:
        if not record_valid(item) or item.get('side') not in ('both', 'server', 'client') or item.get('delivery') not in ('bundle', 'official-download', 'manual'):
            raise ValueError('RV_VENDOR_CATALOG')
        path = target(root, item.get('path'))
        if item['id'] in ids or str(path).casefold() in paths:
            raise ValueError('RV_VENDOR_CATALOG')
        ids.add(item['id'])
        paths.add(str(path).casefold())
        if item['side'] in ('both', 'server'):
            selected.append(item)
    if not selected:
        raise ValueError('RV_VENDOR_CATALOG')
    managed_digest = release.get('managedModsSha256')
    if managed_digest:
        managed_path = guarded(root / 'rv-managed-mods.json')
        if not isinstance(managed_digest, str) or not SHA.fullmatch(managed_digest) or digest(managed_path) != managed_digest:
            raise ValueError('RV_VENDOR_MANAGED_DIGEST')
        registry = read(managed_path)
        if registry.get('schema') != 1 or not isinstance(registry.get('mods'), list):
            raise ValueError('RV_VENDOR_OWNERSHIP')
        for item in registry['mods']:
            if not record_valid(item) or item['id'] not in ('rvcompat', 'rvexperience') or item.get('side') != 'both' or item['id'] in ids or str(target(root, item.get('path'))).casefold() in paths:
                raise ValueError('RV_VENDOR_OWNERSHIP')
            if item['id'] == 'rvexperience' and (item.get('path') != 'mods/rv-experience-2.0.0.jar' or item.get('fileVersion') != '2.0.0' or item.get('fml') != {'rvexperience': '2.0.0'} or release.get('requiredMods', {}).get('rvexperience') != '2.0.0'):
                raise ValueError('RV_VENDOR_OWNERSHIP')
            selected.append(dict(item, delivery='host-owned'))
            ids.add(item['id'])
            paths.add(str(target(root, item['path'])).casefold())
    return expected, digest(release_path), selected


def owned(root):
    path = guarded(root / MANIFEST)
    if not path.exists():
        return {}, None
    value = read(path)
    if value.get('schema') != 1 or not isinstance(value.get('files'), list):
        raise ValueError('RV_VENDOR_OWNERSHIP')
    result, ids = {}, set()
    for item in value['files']:
        if not record_valid(item):
            raise ValueError('RV_VENDOR_OWNERSHIP')
        target(root, item.get('path'))
        if item['path'].casefold() in result or item['id'] in ids:
            raise ValueError('RV_VENDOR_OWNERSHIP')
        result[item['path'].casefold()] = item
        ids.add(item['id'])
    return result, digest(path)


def mod_ids(path):
    ids = set()
    try:
        with zipfile.ZipFile(path) as archive:
            if 'mcmod.info' in archive.namelist() and archive.getinfo('mcmod.info').file_size <= 65536:
                data = json.loads(archive.read('mcmod.info').decode('utf-8-sig'))
                records = data.get('modList', []) if isinstance(data, dict) else data
                if isinstance(records, list):
                    ids.update(item['modid'] for item in records if isinstance(item, dict) and isinstance(item.get('modid'), str))
            if 'META-INF/mods.toml' in archive.namelist() and archive.getinfo('META-INF/mods.toml').file_size <= 65536:
                ids.update(re.findall(r'^\s*modId\s*=\s*[\"\x27]([a-z0-9_]+)[\"\x27]', archive.read('META-INF/mods.toml').decode('utf-8-sig'), re.M))
    except (OSError, ValueError, zipfile.BadZipFile):
        pass
    return ids


def plan(root):
    journal = guarded(root / JOURNAL)
    if journal.exists() and read(journal).get('state') not in ('committed', 'rolled-back'):
        raise RuntimeError('RV_VENDOR_RECOVERY')
    catalog_hash, release_hash, files = contract(root)
    previous, manifest_hash = owned(root)
    desired = {item['path'].casefold(): item for item in files}
    actions, removals = [], []
    for item in files:
        path = target(root, item['path'])
        old = previous.get(item['path'].casefold())
        if path.exists() and not matches(path, item) and (old is None or not matches(path, old)):
            raise ValueError('RV_VENDOR_CONFLICT:' + item['path'])
        actions.append({'file': item, 'beforeSha256': digest(path) if path.exists() else None, 'reusable': matches(path, item)})
    selected_ids = {item['id'] for item in files}
    for name, item in previous.items():
        if item['id'] in selected_ids and name not in desired:
            path = target(root, item['path'])
            if path.exists():
                if not matches(path, item):
                    raise ValueError('RV_VENDOR_CONFLICT:' + item['path'])
                removals.append(item)
    excluded = {str(target(root, item['path'])).casefold() for item in files + removals}
    known = {modid for item in files for modid in item.get('expectedModIds', [])}
    by_size = {}
    for item in files:
        by_size.setdefault(item['size'], []).append(item)
    for directory in (root / 'mods', root / 'mods/1.12.2'):
        guarded(directory)
        if not directory.exists():
            continue
        for path in directory.glob('*.jar'):
            guarded(path)
            if str(path).casefold() in excluded:
                continue
            same_bytes = any(digest(path) == item['sha256'] for item in by_size.get(path.stat().st_size, []))
            if same_bytes or mod_ids(path) & known:
                raise ValueError('RV_VENDOR_DUPLICATE:' + path.relative_to(root).as_posix())
    return {'schema': 1, 'server': str(root), 'catalogSha256': catalog_hash, 'releaseSha256': release_hash, 'previousManifestSha256': manifest_hash, 'actions': actions, 'removals': removals}


def prepare(root, guard=None):
    root = guarded(root)
    guard = guard or maintenance
    journal = root / JOURNAL
    if journal.exists() and read(journal).get('state') not in ('committed', 'rolled-back'):
        recover(root, guard=guard)
    with guard(root):
        value = plan(root)
        stage = root / '.vendor-stage' / uuid.uuid4().hex[:12]
        if any(len(str(target(stage, action['file']['path']))) + 37 >= 260 for action in value['actions']):
            raise ValueError('RV_VENDOR_PATH_LENGTH')
        guarded(stage).mkdir(parents=True)
        for action in value['actions']:
            if action['reusable'] or action['file']['delivery'] == 'host-owned':
                path = target(stage, action['file']['path'])
                source = target(root, action['file']['path']) if action['reusable'] else target(root / 'host-owned', action['file']['path'])
                if not matches(source, action['file']):
                    raise ValueError('RV_VENDOR_BUNDLE:' + action['file']['id'])
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, path)
                if not matches(path, action['file']):
                    raise ValueError('RV_VENDOR_DIGEST')
        atomic_json(stage / 'prepare.json', value)
    return {'stage': str(stage), 'catalogPath': str(root / 'vendor-catalog.json'), 'catalogSha256': value['catalogSha256'], 'files': sum(action['file']['delivery'] != 'host-owned' for action in value['actions']), 'ownedFiles': sum(action['file']['delivery'] == 'host-owned' for action in value['actions']), 'reused': sum(item['reusable'] for item in value['actions'])}


def replace_bytes(path, data):
    guarded(path).parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def cancelled(path):
    if path and Path(path).exists():
        raise RuntimeError('RV_VENDOR_CANCELLED')


def apply(root, stage, cancel_path=None, guard=None):
    root, stage = guarded(root), guarded(stage)
    guard = guard or maintenance
    if stage.parent != root / '.vendor-stage' or not re.fullmatch('[a-f0-9]{12}|[a-f0-9]{32}', stage.name):
        raise ValueError('RV_VENDOR_PATH')
    snapshot = read(stage / 'prepare.json')
    with guard(root):
        value = plan(root)
        if snapshot != value:
            raise ValueError('RV_VENDOR_STALE')
        for action in value['actions']:
            if not matches(target(stage, action['file']['path']), action['file']):
                raise ValueError('RV_VENDOR_DIGEST')
        cancelled(cancel_path)
        changes = [action for action in value['actions'] if not action['reusable']]
        names = [action['file']['path'] for action in changes] + [item['path'] for item in value['removals']] + [MANIFEST]
        backup = guarded(root / 'backups' / ('vendor-update-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]))
        backup.mkdir(parents=True)
        preimages = {}
        for name in names:
            path = guarded(root / name) if name == MANIFEST else target(root, name)
            if path.exists():
                destination = backup / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                if digest(path) != digest(destination):
                    raise ValueError('RV_VENDOR_STALE')
                preimages[name] = digest(destination)
            else:
                preimages[name] = None
        journal = {'schema': 1, 'state': 'applying', 'catalogSha256': value['catalogSha256'], 'backup': str(backup), 'preimages': preimages}
        atomic_json(backup / 'receipt.json', journal)
        atomic_json(root / JOURNAL, journal)
        touched = []
        try:
            for action in changes:
                cancelled(cancel_path)
                item = action['file']
                path = target(root, item['path'])
                if (digest(path) if path.exists() else None) != action['beforeSha256']:
                    raise ValueError('RV_VENDOR_STALE')
                touched.append(item['path'])
                replace_bytes(path, target(stage, item['path']).read_bytes())
                if not matches(path, item):
                    raise ValueError('RV_VENDOR_DIGEST')
            for item in value['removals']:
                cancelled(cancel_path)
                path = target(root, item['path'])
                if not matches(path, item):
                    raise ValueError('RV_VENDOR_STALE')
                touched.append(item['path'])
                path.unlink()
            cancelled(cancel_path)
            retained = [item for name, item in owned(root)[0].items() if item['id'] not in {action['file']['id'] for action in value['actions']}]
            manifest = {'schema': 1, 'catalogSha256': value['catalogSha256'], 'files': retained + [{key: action['file'][key] for key in ('id', 'path', 'size', 'sha256')} for action in value['actions']]}
            touched.append(MANIFEST)
            atomic_json(root / MANIFEST, manifest)
            if any(not matches(target(root, action['file']['path']), action['file']) for action in value['actions']):
                raise ValueError('RV_VENDOR_DIGEST')
            journal['state'] = 'committed'
            atomic_json(root / JOURNAL, journal)
        except BaseException:
            for name in reversed(touched):
                path = guarded(root / name) if name == MANIFEST else target(root, name)
                if preimages[name] is None:
                    if path.exists():
                        path.unlink()
                else:
                    before = backup / name
                    if digest(before) != preimages[name]:
                        raise RuntimeError('RV_VENDOR_RECOVERY')
                    replace_bytes(path, before.read_bytes())
            journal['state'] = 'rolled-back'
            atomic_json(root / JOURNAL, journal)
            raise
        return {'state': 'committed', 'files': len(value['actions']), 'changed': len(changes), 'removedOwned': len(value['removals']), 'backup': str(backup)}


def recover(root, guard=None):
    root = guarded(root)
    guard = guard or maintenance
    with guard(root):
        path = guarded(root / JOURNAL)
        journal = read(path)
        if journal.get('state') != 'applying' or journal.get('schema') != 1:
            raise ValueError('RV_VENDOR_RECOVERY')
        backup = guarded(journal.get('backup', ''))
        if backup.parent != root / 'backups' or not re.fullmatch(r'vendor-update-\d{8}-\d{6}-[a-f0-9]{8}', backup.name):
            raise ValueError('RV_VENDOR_PATH')
        preimages = journal.get('preimages')
        if not isinstance(preimages, dict) or MANIFEST not in preimages or len(preimages) > 40:
            raise ValueError('RV_VENDOR_RECOVERY')
        catalog_hash, _, files = contract(root)
        if catalog_hash != journal.get('catalogSha256'):
            raise ValueError('RV_VENDOR_STALE')
        wanted = {item['path']: item for item in files}
        old_manifest = read(backup / MANIFEST) if preimages[MANIFEST] is not None else {'files': []}
        selected_ids = {item['id'] for item in files}
        expected_manifest = {'schema': 1, 'catalogSha256': catalog_hash, 'files': [item for item in old_manifest['files'] if item['id'] not in selected_ids] + [{key: item[key] for key in ('id', 'path', 'size', 'sha256')} for item in files]}
        destinations = []
        for name, checksum in preimages.items():
            destination = guarded(root / name) if name == MANIFEST else target(root, name)
            if checksum is not None and (not isinstance(checksum, str) or not SHA.fullmatch(checksum) or digest(guarded(backup / name)) != checksum):
                raise ValueError('RV_VENDOR_RECOVERY')
            if destination.exists():
                current = digest(destination)
                if current != checksum:
                    if name == MANIFEST:
                        valid = read(destination) == expected_manifest
                    else:
                        valid = name in wanted and matches(destination, wanted[name])
                    if not valid:
                        raise ValueError('RV_VENDOR_CONFLICT:' + name)
            destinations.append((name, destination, checksum))
        for name, destination, checksum in destinations:
            if checksum is None:
                if destination.exists():
                    destination.unlink()
            elif not destination.exists() or digest(destination) != checksum:
                replace_bytes(destination, (backup / name).read_bytes())
        journal['state'] = 'rolled-back'
        atomic_json(path, journal)
        return {'state': 'rolled-back', 'backup': str(backup), 'files': len(destinations)}


def install_for_runner(root, on_wait=None):
    root = guarded(root)
    metadata = read(root / 'release.json') if (root / 'release.json').exists() else {}
    if not metadata.get('vendorCatalogSha256'):
        return check_ready(root)
    journal = root / JOURNAL
    if journal.exists() and read(journal).get('state') not in ('committed', 'rolled-back'):
        recover(root, guard=lambda root: nullcontext())
    try:
        return check_ready(root)
    except RuntimeError as error:
        if str(error) != 'RV_VENDOR_INSTALL_REQUIRED':
            raise
    prepared = prepare(root, guard=lambda root: nullcontext())
    stage = Path(prepared['stage'])
    cancel = stage / 'cancel'
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    command = [str(powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(root / 'Install-ServerVendors.ps1'), '-ServerRoot', str(root), '-PreparedStage', str(stage), '-StageOnly', '-CancelPath', str(cancel)]
    with (root / 'vendor-install.log').open('wb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=root, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            while process.poll() is None:
                if on_wait and on_wait() and not cancel.exists():
                    cancel.write_text('cancel', encoding='ascii')
                time.sleep(0.25)
        except BaseException:
            cancel.write_text('cancel', encoding='ascii')
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
            raise
    cancelled(cancel)
    if process.returncode != 0:
        raise RuntimeError('RV_VENDOR_DOWNLOAD: see vendor-install.log')
    if on_wait and on_wait():
        raise RuntimeError('RV_VENDOR_CANCELLED')
    result = apply(root, stage, cancel, guard=lambda root: nullcontext())
    check_ready(root)
    return result


def check_ready(root):
    root = guarded(root)
    journal = root / JOURNAL
    if journal.exists() and read(journal).get('state') not in ('committed', 'rolled-back'):
        raise RuntimeError('RV_VENDOR_RECOVERY')
    release = root / 'release.json'
    metadata = read(release) if release.exists() else {}
    if not metadata.get('vendorCatalogSha256'):
        version = metadata.get('version', '1.0.0')
        if re.fullmatch(r'\d+\.\d+\.\d+', version) and tuple(map(int, version.split('.'))) >= (1, 2, 0):
            raise ValueError('RV_VENDOR_CATALOG_DIGEST')
        return {'required': False}
    value = plan(root)
    if any(not action['reusable'] for action in value['actions']) or value['removals']:
        raise RuntimeError('RV_VENDOR_INSTALL_REQUIRED')
    return {'required': True, 'files': len(value['actions']), 'catalogSha256': value['catalogSha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'apply', 'check', 'recover'))
    parser.add_argument('--server-root', type=Path, required=True)
    parser.add_argument('--stage', type=Path)
    parser.add_argument('--cancel-path', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            result = prepare(args.server_root)
        elif args.action == 'apply':
            result = apply(args.server_root, args.stage, args.cancel_path)
        elif args.action == 'recover':
            result = recover(args.server_root)
        else:
            result = check_ready(args.server_root)
        print(json.dumps(result))
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
