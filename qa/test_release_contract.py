import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from release_contract import validate_base


class ReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rv-release-contract-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.expected = self.root / 'expected.json'
        for name in ('payload.zip', 'runtime.zip'):
            (self.root / name).write_bytes(name.encode())
        self.manifest = {
            'archives': [{'path': name, 'sha256': hashlib.sha256((self.root / name).read_bytes()).hexdigest()} for name in ('payload.zip', 'runtime.zip')],
            'managedFiles': [{'path': 'mods/game.jar', 'sha256': '1' * 64}, {'path': 'READ-ME.md', 'sha256': '2' * 64}],
        }
        self.write()

    def write(self, expected=None):
        (self.root / 'package-manifest.json').write_text(json.dumps(self.manifest))
        self.expected.write_text(json.dumps(expected or self.manifest))

    def test_matching_base(self):
        self.assertEqual(validate_base(self.root, self.expected), self.manifest)

    def test_old_gameplay_rejected(self):
        expected = json.loads(json.dumps(self.manifest))
        expected['managedFiles'][0]['sha256'] = '3' * 64
        self.write(expected)
        with self.assertRaisesRegex(ValueError, 'Base gameplay differs'):
            validate_base(self.root, self.expected)

    def test_new_runtime_rejected(self):
        expected = json.loads(json.dumps(self.manifest))
        expected['archives'][1]['sha256'] = '4' * 64
        self.write(expected)
        with self.assertRaisesRegex(ValueError, 'Base gameplay differs'):
            validate_base(self.root, self.expected)

    def test_guide_edit_can_reuse_base(self):
        expected = json.loads(json.dumps(self.manifest))
        expected['managedFiles'][1]['sha256'] = '5' * 64
        self.write(expected)
        self.assertEqual(validate_base(self.root, self.expected), self.manifest)

    def test_corrupt_archive_rejected(self):
        (self.root / 'payload.zip').write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            validate_base(self.root, self.expected)

    def test_duplicate_managed_path_rejected(self):
        self.manifest['managedFiles'].append({'path': 'MODS/GAME.JAR', 'sha256': '1' * 64})
        self.write()
        with self.assertRaisesRegex(ValueError, 'duplicate managed'):
            validate_base(self.root, self.expected)

    def test_added_or_removed_mod_rejected(self):
        expected = json.loads(json.dumps(self.manifest))
        expected['managedFiles'].append({'path': 'mods/extra.jar', 'sha256': '6' * 64})
        self.write(expected)
        with self.assertRaisesRegex(ValueError, 'Base gameplay differs'):
            validate_base(self.root, self.expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
