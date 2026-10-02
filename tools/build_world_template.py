import argparse
import collections
import ctypes
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import random
import struct
import sys
import time
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.local' / 'world-template'
ARCHIVE = ROOT / 'dist' / 'RV-World-Template.zip'
NAME = 'Battlefield-Extended'
SIZE = 1536
PLAYABLE = 1280
HEIGHT = 96
SEED = 1122
FIXED_TIME = 1609459200
FIXED_ZIP_TIME = (2021, 1, 1, 0, 0, 0)
ALLOWED_BLOCKS = {0, 1, 2, 3, 4, 5, 7, 9, 17, 18, 24, 35, 44, 45, 53, 85, 98, 101, 102, 139, 251}
LIGHT_OPACITY = {block: 255 for block in ALLOWED_BLOCKS}
LIGHT_OPACITY.update({0: 0, 9: 3, 18: 1, 85: 0, 101: 0, 102: 0, 139: 0})


def nbt_string(value):
    encoded = value.encode('utf-8')
    return struct.pack('>H', len(encoded)) + encoded


def nbt_payload(tag_type, value):
    if tag_type in {1, 2, 3, 4, 5, 6}:
        return struct.pack({1: '>b', 2: '>h', 3: '>i', 4: '>q', 5: '>f', 6: '>d'}[tag_type], value)
    if tag_type == 7:
        return struct.pack('>i', len(value)) + value
    if tag_type == 8:
        return nbt_string(value)
    if tag_type == 9:
        subtype, values = value
        return bytes([subtype]) + struct.pack('>i', len(values)) + b''.join(nbt_payload(subtype, item) for item in values)
    if tag_type == 10:
        return b''.join(bytes([kind]) + nbt_string(name) + nbt_payload(kind, item) for name, (kind, item) in value.items()) + b'\0'
    if tag_type == 11:
        return struct.pack('>i', len(value)) + struct.pack('>' + 'i' * len(value), *value)
    raise ValueError(f'Unsupported NBT tag {tag_type}')


def nbt_file(value):
    return b'\x0a\0\0' + nbt_payload(10, value)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Landscape:
    def __init__(self):
        self.boxes = collections.defaultdict(list)
        self.buildings = []
        self.features = collections.Counter()
        self.operations = 0

    def box(self, x1, y1, z1, x2, y2, z2, block, data=0):
        if not (-SIZE // 2 <= x1 <= x2 < SIZE // 2 and -SIZE // 2 <= z1 <= z2 < SIZE // 2):
            raise ValueError('Geometry outside generated area')
        if not (0 <= y1 <= y2 < HEIGHT and block in ALLOWED_BLOCKS and 0 <= data <= 15):
            raise ValueError('Invalid geometry')
        if block == 7:
            raise ValueError('Bedrock is reserved for the generated foundation')
        item = (x1, y1, z1, x2, y2, z2, block, data)
        for cz in range(z1 // 16, z2 // 16 + 1):
            for cx in range(x1 // 16, x2 // 16 + 1):
                self.boxes[cx, cz].append(item)
        self.operations += 1

    def building(self, x, z, width, depth, floors, material, damaged=False):
        self.buildings.append({'x': x, 'z': z, 'width': width, 'depth': depth, 'floors': floors, 'damaged': damaged})
        self.box(x, 64, z, x + width, 64, z + depth, 98)
        for floor in range(floors):
            y = 65 + floor * 5
            self.box(x, y, z, x + width, y + 4, z + depth, material)
            self.box(x + 1, y, z + 1, x + width - 1, y + 3, z + depth - 1, 0)
            self.box(x + 1, y + 4, z + 1, x + width - 1, y + 4, z + depth - 1, 5)
            for xx in range(x + 3, x + width - 1, 5):
                self.box(xx, y + 1, z, xx + 1, y + 2, z, 102)
                self.box(xx, y + 1, z + depth, xx + 1, y + 2, z + depth, 102)
            for zz in range(z + 3, z + depth - 1, 5):
                self.box(x, y + 1, zz, x, y + 2, zz + 1, 102)
                self.box(x + width, y + 1, zz, x + width, y + 2, zz + 1, 102)
        top = 65 + floors * 5
        self.box(x, top, z, x + width, top, z + depth, 44, 5)
        for floor in range(floors):
            y = 65 + floor * 5
            for step in range(5):
                self.box(x + 2 + step, y + step + 1, z + depth - 4, x + 2 + step, y + step + 3, z + depth - 3, 0)
                self.box(x + 2 + step, y + step, z + depth - 4, x + 2 + step, y + step, z + depth - 3, 53)
        self.box(x + width // 2, 65, z, x + width // 2 + 1, 67, z, 0)
        if damaged:
            self.box(x + width - 4, top - 5, z + depth - 4, x + width, top, z + depth, 0)
            for step in range(5):
                self.box(x + step * 2, 65, z + depth + 2, x + step * 2 + 1, 65 + step % 2, z + depth + 3, 4)

    def road(self, axis, center, start, end, width=6):
        if axis == 'x':
            self.box(start, 64, center - width, end, 64, center + width, 251, 7)
            for x in range(start, end - 4, 12):
                self.box(x, 64, center, x + 4, 64, center, 251, 4)
        else:
            self.box(center - width, 64, start, center + width, 64, end, 251, 7)
            for z in range(start, end - 4, 12):
                self.box(center, 64, z, center, 64, z + 4, 251, 4)
        self.features['road_segments'] += 1

    def cover(self, x, z, axis='x'):
        if axis == 'x':
            self.box(x, 65, z, x + 6, 66, z + 1, 24)
        else:
            self.box(x, 65, z, x + 1, 66, z + 6, 24)
        self.features['cover_positions'] += 1

    def base(self, center, color):
        self.box(center - 59, 64, -120, center + 59, 64, 115, 251, 8)
        for zz in [-120, 115]:
            self.box(center - 59, 65, zz, center + 59, 68, zz, 98)
        for xx in [center - 59, center + 59]:
            self.box(xx, 65, -120, xx, 68, 115, 98)
            self.box(xx, 65, -6, xx, 68, 6, 0)
        self.road('z', center, -110, 104, 9)
        for z in [-103, 36]:
            self.box(center - 50, 65, z, center - 19, 78, z + 51, 251, 8)
            self.box(center - 49, 65, z + 1, center - 20, 77, z + 50, 0)
            self.box(center - 47, 65, z, center - 22, 75, z, 0)
            self.features['hangars'] += 1
        self.building(center + 20, -93, 24, 25, 2, 98)
        self.building(center + 20, 45, 24, 25, 1, 45)
        for z in [-42, 3]:
            self.box(center + 23, 64, z, center + 49, 64, z + 23, 251, 7)
            self.box(center + 30, 64, z + 6, center + 30, 64, z + 17, 251, 0)
            self.box(center + 42, 64, z + 6, center + 42, 64, z + 17, 251, 0)
            self.box(center + 30, 64, z + 11, center + 42, 64, z + 12, 251, 0)
            self.features['helipads'] += 1
        self.box(center + 54, 65, -10, center + 54, 79, -10, 101)
        self.box(center + 55, 76, -10, center + 61, 79, -10, 35, color)
        self.features['bases'] += 1

    def chunk(self, cx, cz):
        blocks = bytearray(HEIGHT * 256)
        meta = bytearray(HEIGHT * 256)
        blocks[:256] = bytes([7]) * 256
        blocks[256:61 * 256] = bytes([1]) * (60 * 256)
        blocks[61 * 256:64 * 256] = bytes([3]) * (3 * 256)
        blocks[64 * 256:65 * 256] = bytes([2]) * 256
        ox, oz = cx * 16, cz * 16
        for x1, y1, z1, x2, y2, z2, block, data in self.boxes.get((cx, cz), ()):
            left, right = max(0, x1 - ox), min(15, x2 - ox)
            front, back = max(0, z1 - oz), min(15, z2 - oz)
            row = bytes([block]) * (right - left + 1)
            metadata = bytes([data]) * len(row)
            for y in range(y1, y2 + 1):
                for z in range(front, back + 1):
                    start = y * 256 + z * 16 + left
                    blocks[start:start + len(row)] = row
                    meta[start:start + len(row)] = metadata
        return blocks, meta


def landscape():
    plan = Landscape()
    rng = random.Random(SEED)
    for x in range(-700, 701):
        z = 150 + int(7 * math.sin(x / 45))
        plan.box(x, 61, z - 7, x, 64, z + 7, 0)
        plan.box(x, 60, z - 7, x, 60, z + 7, 4)
        plan.box(x, 61, z - 6, x, 62, z + 6, 9)
        plan.box(x, 63, z - 9, x, 64, z - 8, 24)
        plan.box(x, 63, z + 8, x, 64, z + 9, 24)
    for axis in ['x', 'z']:
        plan.road(axis, 0, -620, 620)
        for center in [-480, -320, 320, 480]:
            plan.road(axis, center, -600, 600, 4)
    for x in [-480, -320, 0, 320, 480]:
        plan.box(x - 7, 64, 132, x + 7, 64, 168, 98)
        plan.box(x - 7, 65, 132, x - 7, 66, 168, 101)
        plan.box(x + 7, 65, 132, x + 7, 66, 168, 101)
        for z in [138, 162]:
            plan.box(x - 6, 61, z, x + 6, 63, z + 2, 98)
        plan.features['bridges'] += 1
    for x in [-73, -43, 19, 50]:
        for z in [-75, -42, 21, 52]:
            plan.building(x, z, 21, 20, rng.choice([2, 3]), rng.choice([98, 45]), rng.random() < 0.35)
    plan.base(-220, 11)
    plan.base(220, 14)
    for center_x in [-410, 405]:
        for center_z in [-410, 405]:
            for dx in [-45, -5, 35]:
                for dz in [-45, -5, 35]:
                    plan.building(center_x + dx, center_z + dz, 24, 23, rng.choice([1, 2, 3]), rng.choice([45, 98, 251]), rng.random() < 0.3)
            for dz in [-30, 15]:
                plan.cover(center_x - 15, center_z + dz)
            plan.features['outer_districts'] += 1
    for z in [-570, 530]:
        for x in [-100, -35, 30, 95]:
            plan.building(x, z, 35, 32, 1, 45, x == -35)
            plan.cover(x + 6, z + 40)
        plan.features['industrial_yards'] += 1
    for x in [-570, 535]:
        for z in [-190, -125, 215, 270]:
            plan.building(x, z, 25, 23, 1, 5)
            plan.cover(x + 7, z + 32)
    for x in [-115, 112]:
        plan.box(x, 62, -105, x + 3, 65, 103, 0)
        plan.box(x - 1, 62, -105, x - 1, 64, 103, 17)
        plan.box(x + 4, 62, -105, x + 4, 64, 103, 17)
        for z in range(-95, 100, 28):
            plan.cover(x - 2, z)
            plan.box(x, 62, z, x + 3, 65, z + 1, 0)
        plan.features['trenches'] += 1
    for x in [-280, -180, 160, 270]:
        for z in [-290, 250]:
            plan.box(x, 65, z, x + 14, 71, z + 13, 98)
            plan.box(x + 1, 65, z + 1, x + 13, 70, z + 12, 0)
            plan.box(x + 5, 65, z, x + 7, 67, z, 0)
            plan.box(x + 3, 68, z + 13, x + 11, 68, z + 13, 0)
            plan.features['bunkers'] += 1
    for x in [-285, -170, 170, 285]:
        for z in [-460, -390, -250, 230, 390, 460]:
            plan.cover(x, z, 'z' if z % 3 else 'x')
    for _ in range(950):
        x, z = rng.randrange(-618, 619), rng.randrange(-618, 619)
        if any(abs(x - road) < 16 or abs(z - road) < 16 for road in [-480, -320, 0, 320, 480]):
            continue
        if -130 < z < 125 and abs(x) < 290 or -245 < z < -180 and abs(x) < 40 or 125 < z < 177:
            continue
        if any(b['x'] - 7 <= x <= b['x'] + b['width'] + 7 and b['z'] - 7 <= z <= b['z'] + b['depth'] + 9 for b in plan.buildings):
            continue
        if any(bx - 5 <= x <= bx + 20 and bz - 5 <= z <= bz + 18 for bx in [-280, -180, 160, 270] for bz in [-290, 250]):
            continue
        height = rng.randrange(5, 8)
        plan.box(x - 2, 65 + height - 3, z - 2, x + 2, 65 + height - 1, z + 2, 18, 4)
        plan.box(x - 1, 65 + height, z - 1, x + 1, 65 + height, z + 1, 18, 4)
        plan.box(x, 65, z, x, 65 + height - 1, z, 17)
        plan.features['trees'] += 1
    plan.box(-25, 64, -234, 25, 64, -186, 98)
    for x in [-25, 25]:
        plan.box(x, 65, -234, x, 65, -186, 98)
    for z in [-234, -186]:
        plan.box(-25, 65, z, 25, 65, z, 98)
        plan.box(-3, 65, z, 3, 65, z, 0)
    for x in [-14, 14]:
        plan.box(x, 65, -211, x + 2, 65, -204, 53)
    plan.features['buildings'] = len(plan.buildings)
    return plan


def pack_nibbles(values):
    return bytes(a | (b << 4) for a, b in zip(values[::2], values[1::2]))


def chunk_nbt(plan, cx, cz):
    blocks, metadata = plan.chunk(cx, cz)
    heights = [0] * 256
    sky = bytearray(HEIGHT * 256)
    for column in range(256):
        light = 15
        for y in range(HEIGHT - 1, -1, -1):
            index = y * 256 + column
            opacity = LIGHT_OPACITY[blocks[index]]
            if opacity and heights[column] == 0:
                heights[column] = y + 1
            if opacity == 0 and light != 15:
                opacity = 1
            light -= opacity
            if light <= 0:
                break
            sky[index] = light
    sections = []
    for sy in range(HEIGHT // 16):
        start = sy * 4096
        data = bytes(blocks[start:start + 4096])
        if not any(data):
            continue
        sections.append({'Y': (1, sy), 'Blocks': (7, data), 'Data': (7, pack_nibbles(metadata[start:start + 4096])), 'SkyLight': (7, pack_nibbles(sky[start:start + 4096])), 'BlockLight': (7, bytes(2048))})
    level = {'xPos': (3, cx), 'zPos': (3, cz), 'LastUpdate': (4, 0), 'InhabitedTime': (4, 0), 'TerrainPopulated': (1, 1), 'LightPopulated': (1, 0), 'V': (1, 1), 'Biomes': (7, bytes([1]) * 256), 'HeightMap': (11, heights), 'Sections': (9, (10, sections)), 'Entities': (9, (10, [])), 'TileEntities': (9, (10, [])), 'TileTicks': (9, (10, []))}
    return nbt_file({'DataVersion': (3, 1343), 'Level': (10, level)})


def level_nbt():
    rules = {'doMobSpawning': 'false', 'doDaylightCycle': 'false', 'doWeatherCycle': 'false', 'keepInventory': 'true', 'commandBlockOutput': 'false', 'logAdminCommands': 'false', 'sendCommandFeedback': 'false', 'announceAdvancements': 'false', 'spawnRadius': '0', 'mobGriefing': 'true', 'doFireTick': 'false'}
    data = {'DataVersion': (3, 1343), 'Version': (10, {'Id': (3, 1343), 'Name': (8, '1.12.2'), 'Snapshot': (1, 0)}), 'version': (3, 19133), 'LevelName': (8, NAME), 'RandomSeed': (4, SEED), 'generatorName': (8, 'flat'), 'generatorVersion': (3, 0), 'generatorOptions': (8, '3;minecraft:bedrock,60*minecraft:stone,3*minecraft:dirt,minecraft:grass;1;'), 'MapFeatures': (1, 0), 'GameType': (3, 0), 'hardcore': (1, 0), 'allowCommands': (1, 0), 'initialized': (1, 1), 'SpawnX': (3, 0), 'SpawnY': (3, 65), 'SpawnZ': (3, -210), 'Time': (4, 1000), 'DayTime': (4, 1000), 'LastPlayed': (4, 0), 'SizeOnDisk': (4, 0), 'raining': (1, 0), 'thundering': (1, 0), 'rainTime': (3, 0), 'thunderTime': (3, 0), 'clearWeatherTime': (3, 0), 'Difficulty': (1, 2), 'DifficultyLocked': (1, 0), 'BorderCenterX': (6, 0.0), 'BorderCenterZ': (6, 0.0), 'BorderSize': (6, float(PLAYABLE)), 'BorderSizeLerpTarget': (6, float(PLAYABLE)), 'BorderSizeLerpTime': (4, 0), 'BorderSafeZone': (6, 5.0), 'BorderDamagePerBlock': (6, 0.2), 'BorderWarningBlocks': (3, 5), 'BorderWarningTime': (3, 15), 'GameRules': (10, {key: (8, value) for key, value in rules.items()})}
    return nbt_file({'Data': (10, data)})


def write_region(path, plan, rx, rz):
    header = bytearray(8192)
    count = 0
    with path.open('xb') as stream:
        stream.write(header)
        sector = 2
        for index in range(1024):
            cx, cz = rx * 32 + index % 32, rz * 32 + index // 32
            if not (-SIZE // 32 <= cx < SIZE // 32 and -SIZE // 32 <= cz < SIZE // 32):
                continue
            compressed = zlib.compress(chunk_nbt(plan, cx, cz), 6)
            record = struct.pack('>I', len(compressed) + 1) + b'\x02' + compressed
            sectors = (len(record) + 4095) // 4096
            if sectors > 255:
                raise ValueError('Chunk record exceeds Anvil limit')
            header[index * 4:index * 4 + 4] = (sector << 8 | sectors).to_bytes(4, 'big')
            header[4096 + index * 4:4100 + index * 4] = FIXED_TIME.to_bytes(4, 'big')
            stream.write(record)
            stream.write(bytes(sectors * 4096 - len(record)))
            sector += sectors
            count += 1
        stream.seek(0)
        stream.write(header)
    return count


def peak_memory_bytes():
    if os.name == 'nt':
        class Counters(ctypes.Structure):
            _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong), ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess
        process.restype = ctypes.c_void_p
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        if not get_memory(process(), ctypes.byref(counters), counters.cb):
            raise OSError('GetProcessMemoryInfo failed')
        return int(counters.PeakWorkingSetSize)
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == 'darwin' else value * 1024


def install_guide():
    return '''# RV: Battlefield Extended

A separate world for Minecraft Java 1.12.2. The playable area is 1280 x 1280
blocks; a 1536 x 1536 area is pregenerated. Explore additional residential
districts, warehouses, houses, bunkers, trenches, bridges and cover positions.
Structures use ordinary breakable blocks. Bedrock exists only at y=0.

## Install as a new world

1. Use Stop server and wait until the server has fully stopped.
2. Back up the current world and server.properties.
3. Extract this archive to a separate temporary directory. Verify SHA256SUMS.txt.
4. Check that Battlefield-Extended does not already exist in the server directory.
   If it exists, stop here. Never extract this template over an existing world.
5. Copy the complete new Battlefield-Extended directory into the server directory.
6. Set level-name=Battlefield-Extended, view-distance=6 and spawn-protection=0
   in server.properties. Preserve the other settings.
7. Start the server. Check joining, spawn at 0 65 -210, worldborder size 1280,
   building entrances, breaking and placing an ordinary block. Stop normally
   and restart, then confirm that the changes persisted.
8. To return to the previous world, stop the server and restore the old
   level-name value. Keep the old world intact; do not merge the two worlds.

This archive contains only the new world. Gameplay functions, team commands,
the welcome book and equipment delivery are maintained by the game package.
The package maintainer must install its current function bundle and configure
gameLoopFunction separately. Do not copy playerdata, advancements, stats,
an old level.dat or another world's scoreboard.dat. When applying setup
commands, keep worldborder=1280; older setup commands may set it to 630.

## Performance

Start with server view-distance 6 and client render distance 6-8. Minecraft does
not keep the entire map loaded. A 128-block buffer outside the world border
covers the nearby chunks at view-distance 6. Players travelling in separate
directions increase the number of loaded chunks. RAM and FPS must be checked
with the final modpack and the intended player count.

The template contains no pre-spawned entities, ticking block entities,
command blocks or automatic machines. Leaves do not decay, fire does not
spread and natural mob spawning is disabled. Rubble consists of ordinary
blocks without a separate structural-collapse simulation. Minecraft finishes
lighting on first visit.

## Build and validate

Python 3.11 or newer; no external packages are required. From the source tree:
python tools/build_world_template.py
python qa/test_world_template.py --full

The generator only writes .local/world-template and dist/RV-World-Template.zip.
It refuses to overwrite existing output; preserve or rename previous build
output before rebuilding. The archive contains no server settings, addresses,
accounts, player inventories, logs or executable installers.
'''


def build():
    if OUTPUT.exists() or ARCHIVE.exists():
        raise SystemExit('Output already exists. Preserve/rename it before building; no world is overwritten.')
    started = time.monotonic()
    world = OUTPUT / NAME
    region = world / 'region'
    region.mkdir(parents=True, exist_ok=False)
    plan = landscape()
    entries = []
    count = 0
    for rz in range(-2, 2):
        for rx in range(-2, 2):
            path = region / f'r.{rx}.{rz}.mca'
            chunks = write_region(path, plan, rx, rz)
            count += chunks
            entries.append({'path': path.relative_to(OUTPUT).as_posix(), 'chunks': chunks, 'bytes': path.stat().st_size, 'sha256': sha256(path)})
            print(f'{path.name}: {chunks} chunks; {count}/{(SIZE // 16) ** 2}', flush=True)
    with (world / 'level.dat').open('xb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0, compresslevel=9) as compressed:
            compressed.write(level_nbt())
    manifest = {'name': NAME, 'format': 'Minecraft Java 1.12.2 Anvil', 'dataVersion': 1343, 'seed': SEED, 'generatedSize': [SIZE, SIZE], 'playableSize': [PLAYABLE, PLAYABLE], 'generatedBounds': [-768, -768, 767, 767], 'playableBounds': [-640, -640, 639, 639], 'chunks': count, 'regions': entries, 'spawn': [0, 65, -210], 'blue': [-220, 65, 0], 'red': [220, 65, 0], 'features': dict(sorted(plan.features.items())), 'buildings': plan.buildings, 'entities': 0, 'tileEntities': 0, 'scheduledTicks': 0, 'recommendedViewDistance': 6, 'borderBufferBlocks': 128, 'bedrockLayers': [0], 'generatorWorkingSetLimitMB': 500, 'newWorldOnly': True, 'functionsIncluded': False}
    (OUTPUT / 'world-template-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (OUTPUT / 'INSTALL-NEW-WORLD.md').write_text(install_guide(), encoding='utf-8')
    files = sorted(path for path in OUTPUT.rglob('*') if path.is_file())
    checksums = ''.join(f'{sha256(path)}  {path.relative_to(OUTPUT).as_posix()}\n' for path in files)
    (OUTPUT / 'SHA256SUMS.txt').write_text(checksums, encoding='ascii')
    files.append(OUTPUT / 'SHA256SUMS.txt')
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(path.relative_to(OUTPUT).as_posix(), FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=6)
    peak = peak_memory_bytes()
    metrics = {'chunks': count, 'regionBytes': sum(item['bytes'] for item in entries), 'archiveBytes': ARCHIVE.stat().st_size, 'archiveSha256': sha256(ARCHIVE), 'peakWorkingSetBytes': peak, 'elapsedSeconds': round(time.monotonic() - started, 2), 'geometryOperations': plan.operations}
    (OUTPUT / 'build-metrics.json').write_text(json.dumps(metrics, indent=2) + '\n', encoding='utf-8')
    if peak > 500 * 1024 * 1024:
        raise SystemExit('Generator exceeded the 500 MiB working-set limit')
    print(json.dumps(metrics, indent=2))


def main():
    parser = argparse.ArgumentParser(description='Build a separate new-world template; never edit a live world.')
    parser.parse_args()
    build()


if __name__ == '__main__':
    main()
