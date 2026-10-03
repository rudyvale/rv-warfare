import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_world_extension as extension
from merge_world_regions import records
from test_world_template import NbtReader

OUTPUT = ROOT / '.local/owner-upgrade-20261002/extension'


class ExtensionTests(unittest.TestCase):
    def test_new_buildings_are_inside_border_and_outside_original_map(self):
        plan, landmarks = extension.landscape()
        self.assertEqual(len(plan.buildings), 142)
        self.assertEqual(len(landmarks), 8)
        for item in plan.buildings:
            self.assertTrue(abs(item['x']) >= extension.CORE or abs(item['z']) >= extension.CORE)
            self.assertGreaterEqual(item['x'], -1280)
            self.assertGreaterEqual(item['z'], -1280)
            self.assertLess(item['x'] + item['width'], 1280)
            self.assertLess(item['z'] + item['depth'], 1280)
            self.assertLess(65 + item['floors'] * 5, 96)

    def test_new_buildings_have_open_entrances(self):
        plan, _ = extension.landscape()
        for item in plan.buildings:
            x = item['x'] + item['width'] // 2
            z = item['z']
            blocks, _ = plan.chunk(x // 16, z // 16)
            for y in (65, 66, 67):
                self.assertEqual(blocks[y * 256 + z % 16 * 16 + x % 16], 0)

    def test_all_generated_records_are_valid_and_original_core_is_absent(self):
        manifest = json.loads((OUTPUT / 'extension-manifest.json').read_text(encoding='utf-8'))
        count = 0
        for path in (OUTPUT / 'region').glob('*.mca'):
            _, rx, rz, _ = path.name.split('.')
            entries = records(path.read_bytes())
            for index, (_, _, raw) in entries.items():
                cx, cz = int(rx) * 32 + index % 32, int(rz) * 32 + index // 32
                self.assertFalse(-48 <= cx < 48 and -48 <= cz < 48)
                length = int.from_bytes(raw[:4], 'big')
                payload = zlib.decompress(raw[5:4 + length])
                self.assertTrue(payload.startswith(b'\x0a\x00\x00'))
            sample = next(iter(entries.values()))[2]
            length = int.from_bytes(sample[:4], 'big')
            nbt = NbtReader(zlib.decompress(sample[5:4 + length])).root()
            self.assertEqual(nbt['DataVersion'], 1343)
            self.assertEqual(nbt['Level']['Entities'], [])
            self.assertEqual(nbt['Level']['TileEntities'], [])
            count += len(entries)
        self.assertEqual(count, manifest['newChunks'])
        self.assertEqual(count, 27648)


if __name__ == '__main__':
    unittest.main()
