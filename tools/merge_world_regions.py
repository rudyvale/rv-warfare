import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import struct
import sys
import zipfile


def records(data):
    if len(data) < 8192 or len(data) % 4096:
        raise ValueError('Invalid region size')
    found = {}
    used = {0, 1}
    for index in range(1024):
        entry = int.from_bytes(data[index * 4:index * 4 + 4], 'big')
        if not entry:
            continue
        sector, count = entry >> 8, entry & 255
        allocated = set(range(sector, sector + count))
        if sector < 2 or not count or (sector + count) * 4096 > len(data) or used.intersection(allocated):
            raise ValueError('Invalid or overlapping region entry')
        used.update(allocated)
        begin = sector * 4096
        length = struct.unpack_from('>I', data, begin)[0]
        if length < 2 or length + 4 > count * 4096 or data[begin + 4] not in (1, 2):
            raise ValueError('Invalid chunk record')
        found[index] = (entry, data[4096 + index * 4:4100 + index * 4], data[begin:begin + count * 4096])
    return found


def digest_records(found):
    return {str(index): hashlib.sha256(struct.pack('>I', entry) + stamp + chunk).hexdigest() for index, (entry, stamp, chunk) in found.items()}


def merge_bytes(existing, template):
    before = records(existing)
    source = records(template)
    result = bytearray(existing)
    added = 0
    for index, (_, stamp, chunk) in source.items():
        if index in before:
            continue
        sector, count = len(result) // 4096, len(chunk) // 4096
        if sector > 0xFFFFFF:
            raise ValueError('Region exceeds Anvil offset limit')
        result[index * 4:index * 4 + 4] = ((sector << 8) | count).to_bytes(4, 'big')
        result[4096 + index * 4:4100 + index * 4] = stamp
        result.extend(chunk)
        added += 1
    after = records(result)
    if any(after.get(index) != value for index, value in before.items()):
        raise ValueError('Existing chunk changed')
    return bytes(result), len(before), added


def merge(world, template, backup, apply=False):
    world, template, backup = world.resolve(), template.resolve(), backup.resolve()
    if world == template or world in template.parents or template in world.parents:
        raise ValueError('World and template must be separate')
    if backup == world or world in backup.parents or backup == template or template in backup.parents:
        raise ValueError('Backup must be outside both worlds')
    destination = world / 'region'
    source = template / 'region'
    if not destination.is_dir() or not source.is_dir():
        raise ValueError('Both worlds need region directories')
    planned = []
    for path in sorted(source.glob('r.*.*.mca')):
        target = destination / path.name
        old = target.read_bytes() if target.exists() else bytes(8192)
        original = records(old)
        merged, kept, added = merge_bytes(old, path.read_bytes())
        planned.append((target, old, merged, kept, added, digest_records(original)))
    result = {'applied': apply, 'existingChunksPreserved': sum(item[3] for item in planned), 'addedChunks': sum(item[4] for item in planned), 'regions': []}
    affected_names = {item[0].name for item in planned}
    untouched = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in destination.glob('r.*.*.mca') if path.name not in affected_names}
    result['untouchedRegions'] = untouched
    if apply:
        backup.mkdir(parents=True, exist_ok=False)
    for target, old, merged, kept, added, hashes in planned:
        if apply and added:
            if target.exists():
                shutil.copy2(target, backup / target.name)
            temporary = target.with_suffix('.mca.rv-new')
            if temporary.exists():
                raise FileExistsError(temporary)
            with temporary.open('xb') as stream:
                stream.write(merged)
            temporary.replace(target)
            final = records(target.read_bytes())
            final_hashes = digest_records(final)
            if any(final_hashes.get(index) != value for index, value in hashes.items()):
                raise ValueError('Post-write preservation check failed')
        result['regions'].append({'file': target.name, 'kept': kept, 'added': added, 'originalRecords': hashes, 'originalFileSha256': hashlib.sha256(old).hexdigest(), 'mergedFileSha256': hashlib.sha256(merged).hexdigest()})
    if any(hashlib.sha256((destination / name).read_bytes()).hexdigest() != value for name, value in untouched.items()):
        raise ValueError('Unrelated region changed')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--server-root', type=Path)
    parser.add_argument('--snapshot-file', type=Path)
    args = parser.parse_args()
    if args.apply and (not args.server_root or not args.snapshot_file):
        parser.error('--apply requires --server-root and --snapshot-file')
    lock = None
    if args.server_root:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
        import host_runtime
        server = args.server_root.resolve()
        if args.world.resolve().parent != server:
            raise ValueError('World must be a direct child of the named server directory')
        lock = host_runtime.acquire_lock(server)
        if lock is None or host_runtime.server_status(server).get('state') in ('starting', 'running', 'stopping'):
            raise RuntimeError('Server runner is active')
        with socket.socket() as listener:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(('127.0.0.1', 25565))
    if args.apply:
        snapshot = args.snapshot_file.resolve()
        if args.world.resolve() in snapshot.parents:
            raise ValueError('Snapshot must be outside the live world')
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(snapshot, 'x', zipfile.ZIP_DEFLATED, compresslevel=4) as archive:
            for path in sorted(args.world.rglob('*')):
                if path.is_file():
                    archive.write(path, args.world.name + '/' + path.relative_to(args.world).as_posix())
            for name in ('server.properties', 'ops.json', 'whitelist.json', 'vm-owner.json', 'vm-owner.properties', 'console.log', 'server-state.json', 'config/mcheli.cfg'):
                path = server / name
                if path.is_file():
                    archive.write(path, name)
        with zipfile.ZipFile(snapshot) as archive:
            if archive.testzip() is not None:
                raise ValueError('World snapshot failed verification')
    outcome = merge(args.world, args.template, args.backup, args.apply)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(outcome, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in outcome.items() if key not in ('regions', 'untouchedRegions')}))
