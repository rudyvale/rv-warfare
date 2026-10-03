import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
parser = argparse.ArgumentParser()
parser.add_argument('--world', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
parser.add_argument('--python-libs', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.python_libs))
from decorate_world import Terrain, block
from merge_world_regions import records
import stage_map_quality as quality

report = json.loads(args.report.read_text())
terrain = Terrain(args.world)
checks = []


def check(result, label):
    checks.append({'name': label, 'passed': bool(result)})
    print(('PASS ' if result else 'FAIL ') + label, flush=True)


ledger = json.loads(gzip.decompress(Path(report['ledger']).read_bytes()))
check(hashlib.sha256(Path(report['ledger']).read_bytes()).hexdigest() == report['ledgerSha256'], 'Exact authored ledger checksum')
check(len(ledger) == report['changedBlocks'] and len(ledger) < 125000, 'Bounded authored block count')
changed = {(x // 16, z // 16) for x, y, z, before, old_meta, after, new_meta in ledger}
check(len(changed) == report['changedChunks'], 'Exact changed chunk set')
check(all(before in quality.SURFACES for x, y, z, before, old_meta, after, new_meta in ledger), 'No authored write replaces existing structure blocks')
check(all(block(terrain.chunk(x, z), x, y, z) == after for x, y, z, before, old_meta, after, new_meta in ledger), 'Every after-block matches the frozen ledger')
untouched = 0
for entry in report['regions']:
    before_bytes = (Path(report['preimageBackup']) / entry['file']).read_bytes()
    after_bytes = (args.world / 'region' / entry['file']).read_bytes()
    before, after = records(before_bytes), records(after_bytes)
    check(hashlib.sha256(before_bytes).hexdigest() == entry['beforeSha256'] and hashlib.sha256(after_bytes).hexdigest() == entry['afterSha256'], 'Region preimage and candidate checksums ' + entry['file'])
    _, rx, rz, _ = entry['file'].split('.')
    rx, rz = int(rx), int(rz)
    same = all(after[index] == item for index, item in before.items() if (rx * 32 + index % 32, rz * 32 + index // 32) not in changed)
    check(same, 'Unchanged raw chunk records ' + entry['file'])
    untouched += sum((rx * 32 + index % 32, rz * 32 + index // 32) not in changed for index in before)
clean_world = report.get('status') == 'STAGED_CLEAN_PUBLIC_WORLD'
border_valid = not report['borderChanged'] if not clean_world else report.get('border') == 2560
check(report['liveWrites'] == 0 and not report['generatorChanged'] and border_valid, 'Live world and generator were not changed; requested clean world border is valid')
road_points = set()
road_bad = []
for feature in report['features']:
    if feature['type'] != 'road':
        continue
    if feature.get('routeWaypoints'):
        points = []
        for first, last in zip(feature['routeWaypoints'], feature['routeWaypoints'][1:]):
            x, z = first
            while [x, z] != last:
                points.append((x, z))
                if x != last[0]:
                    x += 1 if last[0] > x else -1
                else:
                    z += 1 if last[1] > z else -1
        points.append(tuple(feature['routeWaypoints'][-1]))
    else:
        points = [(along, feature['center']) if feature['axis'] == 'x' else (feature['center'], along) for along in range(feature['start'], feature['end'] + 1)]
    half = feature['width'] // 2
    for x, z in points:
        road_points.add((x, z))
        for offset in range(-half, half + 1):
            xx, zz = (x, z + offset) if feature['axis'] == 'x' else (x + offset, z)
            if block(terrain.chunk(xx, zz), xx, 64, zz) not in (251, 5, 98) or any(block(terrain.chunk(xx, zz), xx, y, zz) for y in range(65, 65 + feature['headroom'])):
                road_bad.append([feature['name'], xx, zz])
check(not road_bad, 'Selected road lanes retain declared width and headroom')
buildings = [feature for feature in report['features'] if feature['type'] == 'building']
check(len(buildings) == 4, 'Four accessible architecture variants')
for feature in buildings:
    x, y, z = feature['entrance']
    half = feature['entranceWidth'] // 2
    clear = all(block(terrain.chunk(xx, z), xx, yy, z) == 0 for xx in range(x - half, x + half + 1) for yy in range(y, y + feature['entranceHeadroom']))
    check(clear, 'Open entrance ' + feature['name'])
    if feature['name'] != 'crew-garage':
        interior = feature['interiorBox']
        bx = interior[0] - 1
        depth = interior[5] - interior[2] + 2
        for step in range(9):
            xx, yy, zz = bx + 2 + step, 65 + step, z + depth + 3
            check(block(terrain.chunk(xx, zz), xx, yy, zz) == 53 and block(terrain.chunk(xx, zz), xx, yy + 1, zz) == 0 and block(terrain.chunk(xx, zz), xx, yy + 2, zz) == 0, 'Accessible stair ' + feature['name'] + ' ' + str(step))
check(all(not terrain.chunk(cx * 16, cz * 16)['Level'].get(key) for cx, cz in changed for key in ('Entities', 'TileEntities', 'TileTicks')), 'Authored chunks contain no entity, container or ticking machinery')
result = {'passed': all(item['passed'] for item in checks), 'checks': checks, 'roadLaneFailures': road_bad[:30], 'roads': len([feature for feature in report['features'] if feature['type'] == 'road']), 'buildings': len(buildings), 'changedBlocks': len(ledger), 'changedChunks': len(changed), 'nativeRuntimeVerified': False}
args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
raise SystemExit(0 if result['passed'] else 1)
