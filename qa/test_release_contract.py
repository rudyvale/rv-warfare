import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from release_contract import required_mods, validate_base


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

    def test_preservation_policy_change_rejected(self):
        expected = json.loads(json.dumps(self.manifest))
        expected['managedFiles'][0]['existingOnly'] = True
        self.write(expected)
        with self.assertRaisesRegex(ValueError, 'Base gameplay differs'):
            validate_base(self.root, self.expected)

    def test_nonboolean_preservation_policy_rejected(self):
        self.manifest['managedFiles'][0]['existingOnly'] = 'false'
        self.write()
        with self.assertRaisesRegex(ValueError, 'preservation policy'):
            validate_base(self.root, self.expected)

    def test_changed_mod_retirement_patterns_rejected(self):
        expected = json.loads(json.dumps(self.manifest))
        expected['managedModPatterns'] = ['.*']
        self.write(expected)
        with self.assertRaisesRegex(ValueError, 'Base gameplay differs'):
            validate_base(self.root, self.expected)

    def test_changed_optifine_checksum_rejected(self):
        expected = json.loads(json.dumps(self.manifest))
        expected['optifineSha256'] = '7' * 64
        self.write(expected)
        with self.assertRaisesRegex(ValueError, 'Base gameplay differs'):
            validate_base(self.root, self.expected)

    def test_invalid_global_policy_rejected(self):
        for field, value in [('managedModPatterns', '.*'), ('managedModPatterns', [None]), ('optifineSha256', 'missing')]:
            with self.subTest(field=field, value=value):
                self.manifest.pop('managedModPatterns', None)
                self.manifest.pop('optifineSha256', None)
                self.manifest[field] = value
                self.write()
                with self.assertRaisesRegex(ValueError, 'policy'):
                    validate_base(self.root, self.expected)

    def test_legacy_protocol_metadata_optional(self):
        self.assertEqual(required_mods({'version': '1.0.0'}), {})

    def test_new_protocol_metadata_required(self):
        with self.assertRaisesRegex(ValueError, 'advertised mcheli'):
            required_mods({'version': '1.1.0'})
        self.assertEqual(required_mods({'version': '1.1.0', 'requiredMods': {'mcheli': '1.5.1-rv-controls2'}}), {'mcheli': '1.5.1-rv-controls2'})

    def test_empty_or_invalid_mod_version_rejected(self):
        for value in ('', ' ', 'version\nprivate', 12, None):
            with self.assertRaisesRegex(ValueError, 'Invalid required mod'):
                required_mods({'version': '1.1.0', 'requiredMods': {'mcheli': value}})

    def test_rv2_requires_experience_and_bound_owned_proof(self):
        metadata = {'version': '2.0.0', 'requiredMods': {'mcheli': 'fixture'}, 'clientRequiredMods': {'mcheli': 'fixture'}, 'vendorCatalogSha256': 'a' * 64}
        with self.assertRaisesRegex(ValueError, 'shared experience module'):
            required_mods(metadata)
        metadata['requiredMods']['rvexperience'] = '2.0.0'
        metadata['clientRequiredMods']['rvexperience'] = '2.0.0'
        with self.assertRaisesRegex(ValueError, 'native proof digest'):
            required_mods(metadata)
        metadata['managedModsSha256'] = 'b' * 64
        self.assertEqual(required_mods(metadata), metadata['requiredMods'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
