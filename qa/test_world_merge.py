import importlib.util
from pathlib import Path
import struct
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('merge_world', ROOT / 'tools/merge_world_regions.py')
merger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merger)


def region(entries):
    output = bytearray(8192)
    for index, value in entries.items():
        payload = bytes([2]) + zlib.compress(value)
        chunk = struct.pack('>I', len(payload)) + payload
        chunk += bytes((-len(chunk)) % 4096)
        offset = len(output) // 4096
        struct.pack_into('>I', output, index * 4, (offset << 8) | (len(chunk) // 4096))
        struct.pack_into('>I', output, 4096 + index * 4, 123456 + index)
        output.extend(chunk)
    return bytes(output)


class MergeTests(unittest.TestCase):
    def test_preserves_existing_record_offsets_timestamps_padding(self):
        old = region({0: b'player building', 500: b'live tank'})
        new, kept, added = merger.merge_bytes(old, region({0: b'template house', 1: b'new road', 500: b'template tank'}))
        self.assertEqual((kept, added), (2, 1))
        before, after = merger.records(old), merger.records(new)
        for key in before:
            self.assertEqual(before[key], after[key])

    def test_new_region_and_all_missing_chunks(self):
        source = region({0: b'a', 1023: b'b'})
        new, kept, added = merger.merge_bytes(bytes(8192), source)
        self.assertEqual((kept, added), (0, 2))
        self.assertEqual(new, source)

    def test_second_merge_is_byte_identical(self):
        source = region({1: b'a', 2: b'b'})
        first = merger.merge_bytes(region({0: b'private'}), source)[0]
        second, kept, added = merger.merge_bytes(first, source)
        self.assertEqual(first, second)
        self.assertEqual((kept, added), (3, 0))

    def test_invalid_size_and_overlap_fail_before_merge(self):
        with self.assertRaises(ValueError):
            merger.merge_bytes(bytes(100), region({1: b'a'}))
        broken = bytearray(region({0: b'a'}))
        broken[4:8] = broken[0:4]
        with self.assertRaises(ValueError):
            merger.merge_bytes(broken, region({1: b'a'}))

    def test_bad_compression_and_length_are_rejected(self):
        broken = bytearray(region({0: b'a'}))
        broken[8196] = 5
        with self.assertRaises(ValueError):
            merger.records(broken)
        broken = bytearray(region({0: b'a'}))
        struct.pack_into('>I', broken, 8192, 5000)
        with self.assertRaises(ValueError):
            merger.records(broken)

    def test_unreferenced_old_sectors_remain_intact(self):
        old = region({0: b'a'}) + b'Q' * 4096
        new, _, _ = merger.merge_bytes(old, region({1: b'b'}))
        self.assertEqual(old[8192:], new[8192:len(old)])


if __name__ == '__main__':
    unittest.main()
