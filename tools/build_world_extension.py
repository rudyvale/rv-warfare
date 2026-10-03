import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
import time
import zlib

import build_world_template as base

SIZE = 3072
PLAYABLE = 2560
CORE = 768


def landscape():
    base.SIZE = SIZE
    plan = base.Landscape()
    rng = random.Random(11222026)
    landmarks = []
    for axis in ('x', 'z'):
        for center in (-960, 0, 960):
            plan.road(axis, center, -1260, 1260, 6)
    districts = [(-1060, -1060, 'Северо-западный посёлок'), (0, -1060, 'Северный город'), (1060, -1060, 'Северо-восточный квартал'), (-1060, 1060, 'Юго-западный посёлок'), (0, 1060, 'Южный город'), (1060, 1060, 'Юго-восточный квартал')]
    for x, z, name in districts:
        landmarks.append({'name': name, 'x': x, 'z': z})
        for dx in (-64, -24, 24, 64):
            for dz in (-64, -24, 24, 64):
                plan.building(x + dx, z + dz, 24, 23, rng.choice((1, 2, 3, 4)), rng.choice((45, 98)), rng.random() < .16)
        plan.road('x', z + 10, x - 98, x + 108, 4)
        plan.road('z', x + 10, z - 98, z + 108, 4)
        plan.features['new_districts'] += 1
    landmarks.append({'name': 'Аэродром', 'x': -1060, 'z': 0})
    plan.box(-1082, 64, -340, -1038, 64, 340, 251, 7)
    for z in range(-310, 311, 24):
        plan.box(-1061, 64, z, -1059, 64, z + 9, 251, 0)
    for x in (-1230, -1000):
        for z in (-290, -140, 10, 160):
            plan.building(x, z, 48, 44, 2, 98)
            plan.box(x + 12, 65, z, x + 36, 72, z, 0)
            plan.features['hangars'] += 1
    for z in (-370, 345):
        plan.building(-1040, z, 24, 24, 4, 98)
    for z in (-90, 90):
        plan.box(-1130, 64, z, -1098, 64, z + 32, 251, 8)
        plan.box(-1118, 64, z + 7, -1118, 64, z + 25, 251, 0)
        plan.box(-1110, 64, z + 7, -1110, 64, z + 25, 251, 0)
        plan.box(-1118, 64, z + 15, -1110, 64, z + 17, 251, 0)
        plan.features['helipads'] += 1
    plan.features['airfields'] = 1
    landmarks.append({'name': 'Промзона', 'x': 1060, 'z': 0})
    for x in (1000, 1070, 1140, 1210):
        for z in (-290, -180, -70, 40, 150):
            plan.building(x, z, 44, 40, 1 if x % 3 else 2, 45)
            plan.box(x + 13, 65, z, x + 29, 70, z, 0)
            plan.cover(x + 4, z + 52)
    for z in (-235, -15, 205):
        plan.road('x', z, 970, 1260, 5)
    plan.features['industrial_yards'] = 1
    for x in (-880, 880):
        for z in (-600, -400, 400, 600):
            plan.building(x, z, 22, 20, 1, 98)
            plan.cover(x - 10, z + 30)
            plan.cover(x + 30, z - 10, 'z')
            plan.features['outposts'] += 1
    for x in (-590, -430, 430, 590):
        for z in (-870, 870):
            plan.building(x, z, 23, 21, 1, 5)
            plan.cover(x + 5, z + 30)
            plan.features['farmhouses'] += 1
    for _ in range(1700):
        x, z = rng.randrange(-1245, 1246), rng.randrange(-1245, 1246)
        if abs(x) < CORE + 20 and abs(z) < CORE + 20:
            continue
        if any(abs(x - road) < 20 or abs(z - road) < 20 for road in (-960, 0, 960)):
            continue
        if -1240 < x < -970 and -390 < z < 410:
            continue
        if any(b['x'] - 10 <= x <= b['x'] + b['width'] + 10 and b['z'] - 10 <= z <= b['z'] + b['depth'] + 12 for b in plan.buildings):
            continue
        height = rng.randrange(5, 8)
        plan.box(x - 2, 65 + height - 3, z - 2, x + 2, 65 + height - 1, z + 2, 18, 4)
        plan.box(x - 1, 65 + height, z - 1, x + 1, 65 + height, z + 1, 18, 4)
        plan.box(x, 65, z, x, 65 + height - 1, z, 17)
        plan.features['trees'] += 1
    plan.features['buildings'] = len(plan.buildings)
    return plan, landmarks


def write_region(path, plan, rx, rz):
    header = bytearray(8192)
    count = 0
    with path.open('xb') as stream:
        stream.write(header)
        sector = 2
        for index in range(1024):
            cx, cz = rx * 32 + index % 32, rz * 32 + index // 32
            if -CORE // 16 <= cx < CORE // 16 and -CORE // 16 <= cz < CORE // 16:
                continue
            encoded = zlib.compress(base.chunk_nbt(plan, cx, cz), 6)
            record = struct.pack('>I', len(encoded) + 1) + b'\x02' + encoded
            sectors = (len(record) + 4095) // 4096
            if sectors > 255:
                raise ValueError('Chunk exceeds region limit')
            header[index * 4:index * 4 + 4] = (sector << 8 | sectors).to_bytes(4, 'big')
            header[4096 + index * 4:4100 + index * 4] = base.FIXED_TIME.to_bytes(4, 'big')
            stream.write(record + bytes(sectors * 4096 - len(record)))
            sector += sectors
            count += 1
        stream.seek(0)
        stream.write(header)
    return count


def build(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    region = output / 'region'
    region.mkdir()
    plan, landmarks = landscape()
    regions = []
    started = time.monotonic()
    for rz in range(-3, 3):
        for rx in range(-3, 3):
            if rx in (-1, 0) and rz in (-1, 0):
                continue
            path = region / f'r.{rx}.{rz}.mca'
            count = write_region(path, plan, rx, rz)
            regions.append({'name': path.name, 'chunks': count, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            print(f'{path.name}: {count} new chunks', flush=True)
    manifest = {'playableSize': PLAYABLE, 'generatedSize': SIZE, 'preservedCoreSize': CORE * 2, 'features': dict(plan.features), 'buildings': plan.buildings, 'landmarks': landmarks, 'regions': regions, 'newChunks': sum(item['chunks'] for item in regions), 'elapsedSeconds': round(time.monotonic() - started, 2)}
    (output / 'extension-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: manifest[k] for k in ('playableSize', 'newChunks', 'features', 'elapsedSeconds')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
