import argparse
import collections
import gzip
import hashlib
import heapq
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import time
import zlib

from decorate_world import Terrain, block, player_chunks, protected_chunks, set_block
from merge_world_regions import records


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / '.local/rv-1.2.0/map'
SURFACES = {0, 2, 3, 251}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def road(name, axis, center, start, end, width=4, connector=False):
    cells = {}
    for along in range(start, end + 1):
        for across in range(center - width, center + width + 1):
            x, z = (along, across) if axis == 'x' else (across, along)
            cells[x, 64, z] = (251, 0 if abs(across - center) == width else 4 if across == center and along % 12 < 5 else 7)
    return {'name': name, 'type': 'road', 'connector': connector, 'headroom': 6, 'axis': axis, 'center': center, 'start': start, 'end': end, 'width': 2 * width + 1, 'cells': cells}


def box(cells, x1, y1, z1, x2, y2, z2, material, metadata=0):
    for x in range(x1, x2 + 1):
        for z in range(z1, z2 + 1):
            for y in range(y1, y2 + 1):
                cells[x, y, z] = material, metadata


def hall(name, x, z, width, depth, material, hangar=False):
    cells = {}
    height = 9 if hangar else 7
    box(cells, x, 64, z, x + width, 64, z + depth, 98)
    for side in (x, x + width):
        box(cells, side, 65, z, side, 64 + height, z + depth, material)
    for side in (z, z + depth):
        box(cells, x, 65, side, x + width, 64 + height, side, material)
    for xx in range(x + 3, x + width - 2, 5):
        box(cells, xx, 67, z + depth, xx + 1, 68, z + depth, 102)
    center = x + width // 2
    opening = 6 if hangar else 4
    box(cells, center - opening, 65, z, center + opening, 71 if hangar else 69, z, 0)
    for xx in range(x, x + width + 1):
        ridge = min(xx - x, x + width - xx, 5) if hangar else 0
        box(cells, xx, 65 + height + ridge, z, xx, 65 + height + ridge, z + depth, 44, 5)
        if hangar and ridge:
            for side in (z, z + depth):
                box(cells, xx, 65 + height, side, xx, 64 + height + ridge, side, material)
    if not hangar:
        for offset in (3, width - 6):
            box(cells, x + offset, 65, z + depth - 5, x + offset + 2, 66, z + depth - 3, 17)
            box(cells, x + offset, 67, z + depth - 5, x + offset + 2, 67, z + depth - 3, 5)
        for step in range(height + 2):
            xx = x + 2 + step
            box(cells, xx, 65, z + depth + 2, xx, 65 + step, z + depth + 4, 98)
            box(cells, xx, 65 + step, z + depth + 2, xx, 65 + step, z + depth + 4, 53)
        box(cells, x + height + 3, 65 + height, z + depth + 1, x + height + 5, 65 + height, z + depth + 4, 98)
    return {'name': name, 'type': 'building', 'connector': False, 'entrance': [center, 65, z], 'entranceWidth': 2 * opening + 1, 'entranceHeadroom': 7 if hangar else 5, 'interiorBox': [x + 1, 65, z + 1, x + width - 1, 68 if not hangar else 71, z + depth - 1], 'cells': cells}


def plans():
    features = []
    for axis in ('x', 'z'):
        for sign in (-1, 1):
            features.append(road(f'core-{axis}-{sign}', axis, 0, 606 if sign == 1 else -966, 966 if sign == 1 else -606, 6, True))
    features += [road('airfield-bypass', 'z', -928, -966, 966, 5), road('airfield-north-link', 'x', -400, -1224, -928, 5), road('airfield-south-link', 'x', 400, -1224, -928, 5)]
    for x in (-1230, -1000):
        for z in (-290, -140, 10, 160):
            center = x + 24
            target = -1160 if x == -1230 else -928
            features += [road(f'hangar-apron-{x}-{z}', 'x', z - 12, min(center, target), max(center, target), 5), road(f'hangar-entry-{x}-{z}', 'z', center, z - 12, z - 1, 5)]
    features.append(road('airfield-west-taxi', 'z', -1160, -400, 400, 6))
    for z in (-345, -235, -15, 205, 330):
        features.append(road(f'industrial-cross-{z}', 'x', z, 960, 1252, 5))
    for x in (1000, 1070, 1140, 1210):
        for z in (-290, -180, -70, 40, 150):
            previous = max(row for row in (-345, -235, -125, -15, 95) if row < z)
            features.append(road(f'factory-entry-{x}-{z}', 'z', x + 21, previous + 6, z - 1, 3))
    features += [road('industrial-cross-minus125', 'x', -125, 960, 1252, 5), road('industrial-cross95', 'x', 95, 960, 1252, 5)]
    features += [road('garage-access', 'x', -185, -960, -866, 5), road('garage-entry', 'z', -898, -185, -167, 5), road('armory-entry', 'z', -864, -185, -167, 4)]
    features += [hall('crew-garage', -914, -166, 32, 34, 98, True), hall('crew-armory', -874, -166, 20, 24, 45)]
    features += [road('repair-yard-entry', 'z', 1130, 330, 359, 5), hall('industrial-workshop', 1110, 360, 40, 28, 45)]
    features += [road('field-route', 'z', 650, 960, 1063, 4), hall('timber-field-station', 640, 1064, 20, 20, 5)]
    for x, z in ((-888, 260), (888, 560), (690, -900), (-610, -1100), (460, 1100), (-690, 900)):
        cells = {}
        for dx in range(-11, 12):
            for dz in range(-11, 12):
                rise = max(0, 4 - (dx * dx + dz * dz) // 31)
                if rise:
                    box(cells, x + dx, 64, z + dz, x + dx, 63 + rise, z + dz, 3)
                    cells[x + dx, 64 + rise, z + dz] = 2, 0
        features.append({'name': f'earth-cover-{x}-{z}', 'type': 'terrain', 'connector': False, 'cells': cells})
    pond = {}
    for dx in range(-21, 22):
        for dz in range(-21, 22):
            if dx * dx + dz * dz < 21 * 21:
                pond[650 + dx, 64, -1140 + dz] = 0, 0
                box(pond, 650 + dx, 62, -1140 + dz, 650 + dx, 63, -1140 + dz, 9)
    features.append({'name': 'woodland-pond', 'type': 'water', 'connector': False, 'cells': pond})
    bridge = {}
    box(bridge, 645, 64, -1163, 655, 64, -1117, 5)
    for x in (645, 655):
        box(bridge, x, 65, -1162, x, 66, -1118, 85)
    features.append({'name': 'pond-bridge', 'type': 'bridge', 'connector': False, 'cells': bridge})
    features += [road('pond-north-access', 'z', 650, -1200, -1164, 4), road('pond-south-access', 'z', 650, -1116, -960, 4)]
    for z in (-985, -1015, -1045, -1075, -1105):
        cells = {}
        for x in (515, 525):
            box(cells, x, 65, z, x, 72, z, 17)
        box(cells, 515, 73, z, 525, 73, z, 5)
        features.append({'name': f'fpv-gate-{z}', 'type': 'fpv', 'connector': False, 'opening': [516, 65, z, 524, 72, z], 'cells': cells})
    features.append(road('fpv-route', 'x', -960, 505, 655, 3))
    for x, z in ((-1096, -370), (-1096, 350), (-910, -420), (1170, 330)):
        cells = {}
        box(cells, x, 64, z, x + 16, 64, z + 16, 251, 8)
        box(cells, x + 4, 64, z + 4, x + 4, 64, z + 12, 251, 0)
        box(cells, x + 12, 64, z + 4, x + 12, 64, z + 12, 251, 0)
        box(cells, x + 4, 64, z + 8, x + 12, 64, z + 8, 251, 0)
        features.append({'name': f'vehicle-pad-{x}-{z}', 'type': 'pad', 'connector': False, 'placement': [x + 8, 65, z + 8], 'cells': cells})
    for x, z in ((-900, -205), (-925, 220), (950, 360), (1100, 415), (628, 1100), (520, -940), (-1180, -420), (-1180, 420)):
        cells = {}
        box(cells, x, 65, z, x + 6, 66, z + 1, 24)
        box(cells, x + 8, 65, z + 3, x + 9, 66, z + 4, 17)
        features.append({'name': f'cover-{x}-{z}', 'type': 'cover', 'connector': False, 'cells': cells})
    return features


def safe_feature(feature, terrain, legacy, player, reserved=None):
    chunks = {(x // 16, z // 16) for x, y, z in feature['cells']}
    if chunks & player:
        return 'player-footprint'
    if chunks & legacy and not feature['connector']:
        return 'protected-original-chunk'
    for cx, cz in chunks:
        level = terrain.chunk(cx * 16, cz * 16)['Level']
        if any(level.get(key) for key in ('Entities', 'TileEntities', 'TileTicks')):
            return 'existing-entity-or-container'
    for (x, y, z), value in feature['cells'].items():
        old = block(terrain.chunk(x, z), x, y, z)
        if old not in SURFACES:
            return 'existing-non-terrain-block'
        if feature['type'] == 'road':
            if any(block(terrain.chunk(x, z), x, yy, z) != 0 or reserved and reserved.get((x, yy, z), (0, 0))[0] != 0 for yy in range(65, 65 + feature['headroom'])):
                return 'blocked-vehicle-headroom'
    if feature['type'] == 'building':
        x1, y1, z1, x2, y2, z2 = feature['interiorBox']
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                if any(block(terrain.chunk(x, z), x, y, z) != 0 for y in range(y1, y2 + 1)):
                    return 'occupied-interior'
        center, _, front = feature['entrance']
        for x in range(center - 6, center + 7):
            for z in range(front - 20, front):
                if (x // 16, z // 16) in player or any(block(terrain.chunk(x, z), x, y, z) != 0 for y in range(65, 71)):
                    return 'blocked-building-approach'
    return None


def routed_road(feature, terrain, legacy, players, cache, reserved):
    half = feature['width'] // 2
    axis = feature['axis']
    start, end, center = feature['start'], feature['end'], feature['center']
    begin = (start, center) if axis == 'x' else (center, start)
    target = (end, center) if axis == 'x' else (center, end)
    bounds = (min(begin[0], target[0]) - (8 if axis == 'x' else 64), max(begin[0], target[0]) + (8 if axis == 'x' else 64), min(begin[1], target[1]) - (64 if axis == 'x' else 8), max(begin[1], target[1]) + (64 if axis == 'x' else 8))
    def column_clear(x, z):
        key = x, z, feature['headroom'], feature['connector']
        if key not in cache:
            chunk_key = x // 16, z // 16
            if chunk_key in players or chunk_key in legacy and not feature['connector']:
                cache[key] = False
            else:
                chunk = terrain.chunk(x, z)
                level = chunk['Level']
                cache[key] = not any(level.get(name) for name in ('Entities', 'TileEntities', 'TileTicks')) and block(chunk, x, 64, z) in SURFACES and all(block(chunk, x, y, z) == 0 and reserved.get((x, y, z), (0, 0))[0] == 0 for y in range(65, 65 + feature['headroom']))
        return cache[key]
    checked = {}
    def clear(point):
        if point not in checked:
            x, z = point
            checked[point] = bounds[0] <= x <= bounds[1] and bounds[2] <= z <= bounds[3] and all(column_clear(xx, zz) for xx in range(x - half, x + half + 1) for zz in range(z - half, z + half + 1))
        return checked[point]
    if not clear(begin) or not clear(target):
        return None
    queue = [(abs(begin[0] - target[0]) + abs(begin[1] - target[1]), 0, begin)]
    costs, previous = {begin: 0}, {}
    found = None
    while queue and len(costs) < 18000:
        _, cost, point = heapq.heappop(queue)
        if costs.get(point) != cost:
            continue
        if abs(point[0] - target[0]) + abs(point[1] - target[1]) <= 4:
            found = point
            break
        for dx, dz in ((4, 0), (-4, 0), (0, 4), (0, -4)):
            next_point = point[0] + dx, point[1] + dz
            next_cost = cost + 4
            if next_cost >= costs.get(next_point, 100000000) or not clear(next_point):
                continue
            costs[next_point], previous[next_point] = next_cost, point
            heapq.heappush(queue, (next_cost + abs(next_point[0] - target[0]) + abs(next_point[1] - target[1]), next_cost, next_point))
    if found is None:
        return None
    points = [target, found]
    while points[-1] != begin:
        points.append(previous[points[-1]])
    points.reverse()
    line = []
    for first, second in zip(points, points[1:]):
        x, z = first
        while (x, z) != second:
            line.append((x, z))
            if x != second[0]:
                x += 1 if second[0] > x else -1
            elif z != second[1]:
                z += 1 if second[1] > z else -1
    line.append(target)
    area = {(xx, zz) for x, z in line for xx in range(x - half, x + half + 1) for zz in range(z - half, z + half + 1)}
    if not all(column_clear(x, z) for x, z in area):
        return None
    result = dict(feature)
    result['cells'] = {(x, 64, z): (251, 0 if any((x + dx, z + dz) not in area for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))) else 7) for x, z in area}
    for number, (x, z) in enumerate(line):
        if number % 12 < 5:
            result['cells'][x, 64, z] = 251, 4
    result['routeWaypoints'] = [list(point) for point in points]
    result['avoidedExistingBlocks'] = True
    return result


def stage(server, output, preservation, libraries):
    sys.path.insert(0, str(libraries))
    sys.path.insert(0, str(ROOT / 'host'))
    import world_reset
    output = output.resolve()
    if not output.is_relative_to(STAGE.resolve()) or output.exists():
        raise ValueError('Use a fresh candidate directory inside .local/rv-1.2.0/map')
    with world_reset.maintenance(server):
        world = world_reset.world_path(server)
        baseline = {path.relative_to(world).as_posix(): digest(path) for path in world.rglob('*') if path.is_file()}
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(world, output)
        if any(digest(world / name) != value or digest(output / name) != value for name, value in baseline.items()):
            raise ValueError('Offline snapshot changed during copy')
    legacy = protected_chunks(json.loads(preservation.read_text(encoding='utf-8')))
    players = player_chunks(output)
    import nbtlib
    for path in (output / 'playerdata').glob('*.dat'):
        data = nbtlib.load(path)
        if all(key in data for key in ('SpawnX', 'SpawnZ')):
            x, z = int(data['SpawnX']), int(data['SpawnZ'])
            players |= {(xx // 16, zz // 16) for xx in range(x - 12, x + 13) for zz in range(z - 12, z + 13)}
    terrain = Terrain(output)
    selected, skipped, ledger, edits, cumulative = [], [], [], set(), {}
    features = plans()
    original = {}
    clear_cache = {}
    definitions = [('crew-garage', -914, -166, 32, 34, 98, True, 'garage-entry', -185), ('crew-armory', -874, -166, 20, 24, 45, False, 'armory-entry', -185), ('industrial-workshop', 1110, 360, 40, 28, 45, False, 'repair-yard-entry', 330), ('timber-field-station', 640, 1064, 20, 20, 5, False, 'field-route', 960)]
    claimed = []
    arterial_cells = {(x, z) for feature in features if feature['type'] == 'road' and feature['name'] not in {item[8] for item in definitions} for x, y, z in feature['cells']}
    for name, x, z, width, depth, material, hangar, entry, anchor in definitions:
        chosen = None
        for dx, dz in [(0, 0), (0, 48), (0, -48), (48, 0), (-48, 0), (0, 96), (0, -96), (48, 48), (-48, 48), (96, 0), (-96, 0), (48, 96), (-48, 96), (96, 96), (-96, 96)]:
            xx, zz = x + dx, z + dz
            if max(abs(xx - 2), abs(xx + width + 2), abs(zz - 21), abs(zz + depth + 6)) >= 1275:
                continue
            bounds = xx - 7, zz - 21, xx + width + 7, zz + depth + 7
            if any(bounds[0] <= other[2] and other[0] <= bounds[2] and bounds[1] <= other[3] and other[1] <= bounds[3] for other in claimed):
                continue
            if any((xx + ddx, zz + ddz) in arterial_cells for ddx in range(width + 1) for ddz in range(depth + 6)):
                continue
            option = hall(name, xx, zz, width, depth, material, hangar)
            if safe_feature(option, terrain, legacy, players) is None:
                chosen = option
                claimed.append(bounds)
                break
        if chosen:
            features = [chosen if feature['name'] == name else feature for feature in features]
            gx, gy, gz = chosen['entrance']
            approach = road(entry, 'z', gx, min(anchor, gz - 1), max(anchor, gz - 1), 5 if hangar else 4)
            approach['headroom'] = 6 if hangar else 5
            features = [approach if feature['name'] == entry else feature for feature in features]
    reserved = {coordinate: value for feature in features if feature['type'] not in ('road', 'pad', 'bridge') and safe_feature(feature, terrain, legacy, players) is None for coordinate, value in feature['cells'].items() if value[0] and coordinate[1] >= 65}
    for feature in features:
        reason = safe_feature(feature, terrain, legacy, players, reserved)
        if reason and feature['type'] == 'road':
            alternative = routed_road(feature, terrain, legacy, players, clear_cache, reserved)
            if alternative:
                feature, reason = alternative, None
        if reason:
            skipped.append({'name': feature['name'], 'reason': reason})
            continue
        selected.append({key: value for key, value in feature.items() if key != 'cells'})
        for coordinate, value in feature['cells'].items():
            cumulative[coordinate] = value
    if len(cumulative) > 125000:
        raise ValueError('Authored block budget exceeded')
    for (x, y, z), (value, metadata) in cumulative.items():
        chunk = terrain.chunk(x, z)
        before = block(chunk, x, y, z)
        section = next(section for section in chunk['Level']['Sections'] if int(section['Y']) == y // 16)
        index = y % 16 * 256 + z % 16 * 16 + x % 16
        data = int(section['Data'][index // 2]) & 255
        old_meta = data >> (4 * (index % 2)) & 15
        if (before, old_meta) == (value, metadata):
            continue
        ledger.append([x, y, z, before, old_meta, value, metadata])
        set_block(chunk, x, y, z, value, metadata)
        edits.add((x // 16, z // 16))
    for x, z in {(row[0], row[2]) for row in ledger}:
        chunk = terrain.chunk(x, z)
        heights = chunk['Level']['HeightMap']
        column = z % 16 * 16 + x % 16
        top = int(heights[column])
        for y in range(top - 1, -1, -1):
            value = block(chunk, x, y, z)
            if value not in (0, 85, 101, 102):
                heights[column] = y + 1
                break
    untouched = 0
    region_preimages, changed_regions = {}, []
    pending = []
    for path in sorted((output / 'region').glob('*.mca')):
        before_bytes = path.read_bytes()
        old_records = records(before_bytes)
        _, rx, rz, _ = path.name.split('.')
        rx, rz = int(rx), int(rz)
        changes = {index: (rx * 32 + index % 32, rz * 32 + index // 32) for index in old_records if (rx * 32 + index % 32, rz * 32 + index // 32) in edits}
        if not changes:
            untouched += len(old_records)
            continue
        result = bytearray(before_bytes)
        for index, key in changes.items():
            stream = io.BytesIO()
            terrain.chunks[key].write(stream)
            encoded = zlib.compress(stream.getvalue(), 6)
            raw = struct.pack('>I', len(encoded) + 1) + b'\x02' + encoded
            count = (len(raw) + 4095) // 4096
            if count > 255:
                raise ValueError('Anvil record allocation exceeded')
            result[index * 4:index * 4 + 4] = (len(result) // 4096 << 8 | count).to_bytes(4, 'big')
            result.extend(raw + bytes(count * 4096 - len(raw)))
        after_records = records(result)
        assert all(after_records[index] == item for index, item in old_records.items() if index not in changes)
        untouched += len(old_records) - len(changes)
        original[path.name] = before_bytes
        region_preimages[path.name] = hashlib.sha256(before_bytes).hexdigest()
        pending.append((path, before_bytes, bytes(result)))
        changed_regions.append({'file': path.name, 'chunks': [list(key) for key in sorted(changes.values())], 'beforeSha256': region_preimages[path.name], 'afterSha256': hashlib.sha256(result).hexdigest()})
    backup = output.parent / (output.name + '-before')
    backup.mkdir(exist_ok=False)
    for name, data in original.items():
        (backup / name).write_bytes(data)
        assert digest(backup / name) == region_preimages[name]
    for path, before, result in pending:
        if path.read_bytes() != before:
            raise ValueError('Candidate changed before applying its authored patch')
        temporary = path.with_suffix('.mca.quality-new')
        with temporary.open('xb') as stream:
            stream.write(result)
        temporary.replace(path)
    ledger_path = output.parent / (output.name + '-block-ledger.json.gz')
    with gzip.GzipFile(filename=str(ledger_path), mode='wb', mtime=0) as stream:
        stream.write(json.dumps(ledger, separators=(',', ':')).encode())
    non_region = {name: value for name, value in baseline.items() if not name.startswith('region/')}
    assert all(digest(output / name) == value for name, value in non_region.items())
    assert all(digest(world / name) == value for name, value in baseline.items())
    bounds = [[min(row[index] for row in ledger), max(row[index] for row in ledger)] for index in range(3)]
    exceptions = sorted(edits & legacy)
    report = {'schema': 1, 'status': 'STAGED_PRIVATE_CLONE', 'publicSafe': False, 'candidate': str(output), 'sourceWorldReadOnly': str(world), 'sourceFilesExact': len(baseline), 'nonRegionFilesExact': len(non_region), 'features': selected, 'skipped': skipped, 'plannedFeatures': len(features), 'changedBlocks': len(ledger), 'changedChunks': len(edits), 'untouchedChunkRecordsExact': untouched, 'legacyChunks': len(legacy), 'explicitLegacyConnectorExceptions': [list(key) for key in exceptions], 'otherLegacyChunksExact': len(legacy) - len(exceptions), 'protectedPlayerAndBedChunks': len(players), 'coordinateBounds': bounds, 'regions': changed_regions, 'preimageBackup': str(backup), 'ledger': str(ledger_path), 'ledgerSha256': digest(ledger_path), 'addedEntities': 0, 'addedTileEntities': 0, 'generatorChanged': False, 'borderChanged': False, 'liveWrites': 0, 'elapsedSeconds': 0}
    report_path = output.parent / (output.name + '-report.json')
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report, terrain


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preservation-report', type=Path, required=True)
    parser.add_argument('--python-libs', type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    report, terrain = stage(args.server_root, args.output, args.preservation_report, args.python_libs)
    report['elapsedSeconds'] = round(time.monotonic() - start, 2)
    (args.output.parent / (args.output.name + '-report.json')).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('status', 'plannedFeatures', 'changedBlocks', 'changedChunks', 'untouchedChunkRecordsExact', 'otherLegacyChunksExact', 'explicitLegacyConnectorExceptions', 'liveWrites', 'elapsedSeconds')}))
