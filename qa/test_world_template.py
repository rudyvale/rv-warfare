import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.local' / 'world-template'
ARCHIVE = ROOT / 'dist' / 'RV-World-Template.zip'
spec = importlib.util.spec_from_file_location('world_template', ROOT / 'tools' / 'build_world_template.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
FULL = '--full' in sys.argv
REBUILD = '--rebuild' in sys.argv


class NbtReader:
    def __init__(self, data):
        self.stream = io.BytesIO(data)

    def read(self, count):
        value = self.stream.read(count)
        if len(value) != count:
            raise ValueError('Truncated NBT')
        return value

    def number(self, fmt):
        return struct.unpack('>' + fmt, self.read(struct.calcsize('>' + fmt)))[0]

    def string(self):
        return self.read(self.number('H')).decode('utf-8')

    def payload(self, kind):
        if kind in {1, 2, 3, 4, 5, 6}:
            return self.number({1: 'b', 2: 'h', 3: 'i', 4: 'q', 5: 'f', 6: 'd'}[kind])
        if kind == 7:
            return self.read(self.number('i'))
        if kind == 8:
            return self.string()
        if kind == 9:
            subtype, count = self.number('B'), self.number('i')
            if not 0 <= count <= 65536:
                raise ValueError('Invalid NBT list length')
            return [self.payload(subtype) for _ in range(count)]
        if kind == 10:
            result = {}
            while True:
                subtype = self.number('B')
                if subtype == 0:
                    return result
                name = self.string()
                if name in result:
                    raise ValueError('Duplicate NBT key')
                result[name] = self.payload(subtype)
        if kind == 11:
            count = self.number('i')
            return list(struct.unpack('>' + 'i' * count, self.read(count * 4)))
        raise ValueError(f'Unexpected NBT type {kind}')

    def root(self):
        if self.number('B') != 10 or self.string() != '':
            raise ValueError('Invalid NBT root')
        result = self.payload(10)
        if self.stream.read(1):
            raise ValueError('Trailing NBT bytes')
        return result


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def region_chunks(path):
    parts = path.stem.split('.')
    rx, rz = int(parts[1]), int(parts[2])
    with path.open('rb') as stream:
        header = stream.read(8192)
        used = {0, 1}
        for index in range(1024):
            entry = int.from_bytes(header[index * 4:index * 4 + 4], 'big')
            if not entry:
                continue
            sector, sectors = entry >> 8, entry & 255
            if not sectors or sector < 2 or (sector + sectors) * 4096 > path.stat().st_size:
                raise ValueError('Region entry outside file')
            allocated = set(range(sector, sector + sectors))
            if used.intersection(allocated):
                raise ValueError('Overlapping chunk sectors')
            used.update(allocated)
            stream.seek(sector * 4096)
            length = int.from_bytes(stream.read(4), 'big')
            if length < 2 or length + 4 > sectors * 4096 or stream.read(1) != b'\x02':
                raise ValueError('Invalid chunk compression record')
            payload = stream.read(length - 1)
            inflater = zlib.decompressobj()
            data = inflater.decompress(payload)
            if not inflater.eof or inflater.unused_data:
                raise ValueError('Incomplete or overlong compressed stream')
            cx, cz = rx * 32 + index % 32, rz * 32 + index // 32
            yield cx, cz, data
        if used != set(range(path.stat().st_size // 4096)):
            raise ValueError('Unused trailing or internal sectors')


def stored_chunk(cx, cz):
    path = OUTPUT / 'Battlefield-Extended' / 'region' / f'r.{cx // 32}.{cz // 32}.mca'
    with path.open('rb') as stream:
        stream.seek((cx % 32 + cz % 32 * 32) * 4)
        location = int.from_bytes(stream.read(4), 'big')
        stream.seek((location >> 8) * 4096)
        length = int.from_bytes(stream.read(4), 'big')
        if stream.read(1) != b'\x02':
            raise ValueError('Expected zlib chunk')
        return NbtReader(zlib.decompress(stream.read(length - 1))).root()['Level']


class WorldTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((OUTPUT / 'world-template-manifest.json').read_text(encoding='utf-8'))
        cls.plan = builder.landscape()

    def test_01_safe_metadata_and_border_margin(self):
        level = NbtReader(gzip.decompress((OUTPUT / 'Battlefield-Extended' / 'level.dat').read_bytes())).root()['Data']
        self.assertEqual(level['DataVersion'], 1343)
        self.assertEqual(level['Version'], {'Id': 1343, 'Name': '1.12.2', 'Snapshot': 0})
        self.assertEqual(level['version'], 19133)
        self.assertEqual(level['generatorName'], 'flat')
        self.assertEqual(level['MapFeatures'], 0)
        self.assertEqual(level['BorderSize'], 1280)
        self.assertEqual(level['BorderSizeLerpTarget'], 1280)
        self.assertEqual(level['GameType'], 0)
        self.assertEqual([level['SpawnX'], level['SpawnY'], level['SpawnZ']], [0, 65, -210])
        self.assertNotIn('Player', level)
        self.assertNotIn('gameLoopFunction', level['GameRules'])
        self.assertEqual(level['GameRules']['doMobSpawning'], 'false')
        self.assertEqual(self.manifest['generatedSize'], [1536, 1536])
        self.assertEqual(self.manifest['playableSize'], [1280, 1280])
        self.assertGreaterEqual(self.manifest['borderBufferBlocks'], (self.manifest['recommendedViewDistance'] + 1) * 16)
        self.assertTrue(self.manifest['newWorldOnly'])
        self.assertFalse(self.manifest['functionsIncluded'])

    def test_02_all_region_headers_and_payloads(self):
        seen = set()
        sample = {(-48, -48), (47, 47), (-1, -1), (0, 0), (0, -14), (-14, 0), (13, 0)}
        seen_blocks = set()
        for entry in self.manifest['regions']:
            path = OUTPUT / entry['path']
            self.assertEqual(path.stat().st_size % 4096, 0)
            self.assertEqual(path.stat().st_size, entry['bytes'])
            self.assertEqual(digest(path), entry['sha256'])
            count = 0
            for cx, cz, data in region_chunks(path):
                count += 1
                self.assertNotIn((cx, cz), seen)
                self.assertTrue(-48 <= cx < 48 and -48 <= cz < 48)
                seen.add((cx, cz))
                if not FULL and (cx, cz) not in sample:
                    continue
                root = NbtReader(data).root()
                self.assertEqual(root['DataVersion'], 1343)
                level = root['Level']
                self.assertEqual((level['xPos'], level['zPos']), (cx, cz))
                self.assertEqual(level['Entities'], [])
                self.assertEqual(level['TileEntities'], [])
                self.assertEqual(level['TileTicks'], [])
                self.assertEqual(level['TerrainPopulated'], 1)
                self.assertEqual(level['LightPopulated'], 0)
                self.assertEqual(level['Biomes'], bytes([1]) * 256)
                heights = [0] * 256
                ys = set()
                for section in level['Sections']:
                    sy = section['Y']
                    self.assertNotIn(sy, ys)
                    ys.add(sy)
                    self.assertTrue(0 <= sy < 6)
                    blocks = section['Blocks']
                    self.assertEqual(len(blocks), 4096)
                    ids = set(blocks)
                    seen_blocks.update(ids)
                    self.assertTrue(ids <= builder.ALLOWED_BLOCKS)
                    for key in ['Data', 'SkyLight', 'BlockLight']:
                        self.assertEqual(len(section[key]), 2048)
                    if sy == 0:
                        self.assertEqual(blocks[:256], bytes([7]) * 256)
                        self.assertNotIn(7, blocks[256:])
                    else:
                        self.assertNotIn(7, blocks)
                    for local_y in range(16):
                        row = blocks[local_y * 256:(local_y + 1) * 256]
                        for column, block in enumerate(row):
                            if block not in {0, 85, 101, 102, 139}:
                                heights[column] = sy * 16 + local_y + 1
                self.assertEqual(level['HeightMap'], heights)
            self.assertEqual(count, entry['chunks'])
        expected = {(x, z) for z in range(-48, 48) for x in range(-48, 48)}
        self.assertEqual(seen, expected)
        self.assertEqual(len(seen), self.manifest['chunks'])
        if FULL:
            self.assertTrue({9, 45, 53, 98, 251} <= seen_blocks)

    def test_03_spawn_and_building_access(self):
        chunks = {}

        def block(x, y, z):
            key = (x // 16, z // 16)
            if key not in chunks:
                level = stored_chunk(*key)
                chunks[key] = {section['Y']: section['Blocks'] for section in level['Sections']}
            section = chunks[key].get(y // 16, bytes(4096))
            return section[y % 16 * 256 + z % 16 * 16 + x % 16]

        for x, y, z in [(0, 65, -210), (-185, 65, -29), (255, 65, -29)]:
            self.assertNotEqual(block(x, y - 1, z), 0)
            self.assertEqual(block(x, y, z), 0)
            self.assertEqual(block(x, y + 1, z), 0)
        self.assertEqual(len(self.manifest['buildings']), 72)
        self.assertEqual(self.manifest['features']['outer_districts'], 4)
        for building in self.manifest['buildings']:
            x, z = building['x'] + building['width'] // 2, building['z']
            self.assertEqual(block(x, 65, z), 0)
            self.assertEqual(block(x, 66, z), 0)
            self.assertEqual(block(x, 65, z - 1), 0)
            self.assertEqual(block(x, 66, z - 1), 0)
            self.assertNotEqual(block(x, 64, z - 1), 0)
            for floor in range(building['floors']):
                for step in range(5):
                    sx, sy, sz = building['x'] + 2 + step, 65 + floor * 5 + step, z + building['depth'] - 4
                    self.assertEqual(block(sx, sy, sz), 53)
                    self.assertEqual(block(sx, sy + 1, sz), 0)
                    self.assertEqual(block(sx, sy + 2, sz), 0)

    def test_04_archive_contents_and_checksums(self):
        expected = {entry['path'] for entry in self.manifest['regions']}
        expected.update({'Battlefield-Extended/level.dat', 'INSTALL-NEW-WORLD.md', 'SHA256SUMS.txt', 'world-template-manifest.json'})
        with zipfile.ZipFile(ARCHIVE) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), expected)
            self.assertEqual(len(archive.namelist()), len(expected))
            checksums = archive.read('SHA256SUMS.txt').decode('ascii').splitlines()
            checked = set()
            for line in checksums:
                wanted, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), wanted)
                self.assertEqual(digest(OUTPUT / name), wanted)
                checked.add(name)
            self.assertEqual(checked, expected - {'SHA256SUMS.txt'})
            for entry in archive.infolist():
                self.assertEqual(entry.date_time, (2021, 1, 1, 0, 0, 0))
                self.assertNotIn('..', Path(entry.filename).parts)
                self.assertFalse(entry.filename.startswith('/'))
                self.assertNotIn(':', entry.filename)
        metrics = json.loads((OUTPUT / 'build-metrics.json').read_text())
        self.assertEqual(digest(ARCHIVE), metrics['archiveSha256'])
        self.assertLess(metrics['peakWorkingSetBytes'], 500 * 1024 * 1024)

    def test_05_generator_refuses_overwrite(self):
        before = {path.relative_to(OUTPUT).as_posix(): digest(path) for path in OUTPUT.rglob('*') if path.is_file()}
        before_zip = digest(ARCHIVE)
        result = subprocess.run([sys.executable, str(ROOT / 'tools' / 'build_world_template.py')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Output already exists', result.stderr)
        after = {path.relative_to(OUTPUT).as_posix(): digest(path) for path in OUTPUT.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(before_zip, digest(ARCHIVE))

    def test_06_geometry_guards(self):
        for args in [(-769, 65, 0, 1, 66, 0, 1), (0, 65, 0, 768, 66, 0, 1), (0, 95, 0, 1, 96, 0, 1), (0, 65, 0, 1, 66, 0, 7), (0, 65, 0, 1, 66, 0, 137)]:
            with self.assertRaises(ValueError):
                builder.Landscape().box(*args)

    @unittest.skipUnless(REBUILD, 'Pass --rebuild for a second independent process and byte-identical archive check')
    def test_07_reproducible_full_build(self):
        temporary = Path(tempfile.mkdtemp(prefix='world-template-rebuild-', dir=ROOT / '.local'))
        self.assertEqual(temporary.resolve().parent, (ROOT / '.local').resolve())
        (temporary / 'tools').mkdir()
        script = temporary / 'tools' / 'build_world_template.py'
        shutil.copyfile(ROOT / 'tools' / 'build_world_template.py', script)
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr)
        second = temporary / 'dist' / 'RV-World-Template.zip'
        self.assertEqual(digest(ARCHIVE), digest(second))
        print('Rebuild archive identical:', digest(second), flush=True)

    def test_08_lighting_reference_cases(self):
        plan = builder.Landscape()
        for x, block in enumerate([101, 102, 85, 139, 44, 53]):
            plan.box(x, 70, 0, x, 70, 0, block)
        plan.box(6, 69, 0, 6, 70, 0, 18, 4)
        plan.box(7, 69, 0, 7, 70, 0, 9)
        level = NbtReader(builder.chunk_nbt(plan, 0, 0)).root()['Level']
        self.assertEqual(level['HeightMap'][:8], [65, 65, 65, 65, 71, 71, 71, 71])

        def light(chunk, x, y, z):
            section = next(item for item in chunk['Sections'] if item['Y'] == y // 16)
            index = y % 16 * 256 + z % 16 * 16 + x % 16
            return (section['SkyLight'][index // 2] >> ((index % 2) * 4)) & 15

        for x in range(4):
            self.assertEqual([light(level, x, y, 0) for y in [71, 70, 69, 65, 64]], [15, 15, 15, 15, 0])
        for x in [4, 5]:
            self.assertEqual([light(level, x, y, 0) for y in [71, 70, 69]], [15, 0, 0])
        self.assertEqual([light(level, 6, y, 0) for y in [71, 70, 69, 68]], [15, 14, 13, 12])
        self.assertEqual([light(level, 7, y, 0) for y in [71, 70, 69, 68]], [15, 12, 9, 8])
        bridge = stored_chunk(-1, 8)
        self.assertEqual(bridge['HeightMap'][12 * 16 + 9], 65)
        self.assertEqual([light(bridge, -7, y, 140) for y in [67, 66, 65, 64]], [15, 15, 15, 0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--rebuild', action='store_true')
    parser.parse_args()
    unittest.main(argv=[sys.argv[0]], verbosity=2)
