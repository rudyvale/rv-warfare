import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from release_contract import mark_published, validate_candidate, validate_output, write_candidate


class ReleaseCandidateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rv-publication-gate-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        lines = []
        for name in ('RV-Setup.zip', 'RV-Host-Tools.zip', 'RV-Third-Party-Sources.zip'):
            data = name.encode()
            (self.root / name).write_bytes(data)
            lines.append(hashlib.sha256(data).hexdigest() + '  ' + name)
        (self.root / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n')

    def test_public_candidate_matches_all_assets(self):
        write_candidate(self.root, '1.1.0')
        candidate = validate_candidate(self.root, '1.1.0')
        self.assertEqual(candidate['state'], 'candidate')
        self.assertEqual(set(candidate['assets']), {'RV-Setup.zip', 'RV-Host-Tools.zip', 'RV-Third-Party-Sources.zip', 'SHA256SUMS.txt'})

    def test_204_cannot_publish_without_mac_package(self):
        with self.assertRaisesRegex(ValueError, 'Mac package'):
            write_candidate(self.root, '2.0.4')
        self.assertFalse((self.root / '.release-candidate.json').exists())

    def test_204_binds_mac_package_bytes(self):
        data = b'Mac package fixture'
        (self.root / 'RV-Mac-Setup.zip').write_bytes(data)
        checksum = self.root / 'SHA256SUMS.txt'
        checksum.write_text(checksum.read_text() + hashlib.sha256(data).hexdigest() + '  RV-Mac-Setup.zip\n')
        write_candidate(self.root, '2.0.4')
        self.assertIn('RV-Mac-Setup.zip', validate_candidate(self.root, '2.0.4')['assets'])
        (self.root / 'RV-Mac-Setup.zip').write_bytes(b'changed Mac package')
        with self.assertRaisesRegex(ValueError, 'Candidate checksum mismatch'):
            validate_candidate(self.root, '2.0.4')

    def test_new_candidate_cannot_omit_source_asset(self):
        checksum_file = self.root / 'SHA256SUMS.txt'
        checksum_file.write_text('\n'.join(line for line in checksum_file.read_text().splitlines() if 'RV-Third-Party-Sources.zip' not in line) + '\n')
        with self.assertRaisesRegex(ValueError, 'third-party source asset'):
            write_candidate(self.root, '1.1.0')
        self.assertFalse((self.root / '.release-candidate.json').exists())

    def test_legacy_candidate_remains_valid_without_source_asset(self):
        checksum_file = self.root / 'SHA256SUMS.txt'
        checksum_file.write_text('\n'.join(line for line in checksum_file.read_text().splitlines() if 'RV-Third-Party-Sources.zip' not in line) + '\n')
        write_candidate(self.root, '1.0.0')
        self.assertNotIn('RV-Third-Party-Sources.zip', validate_candidate(self.root, '1.0.0')['assets'])

    def test_private_candidate_cannot_publish_even_with_public_content(self):
        write_candidate(self.root, '1.1.0', private=True)
        with self.assertRaisesRegex(ValueError, 'matching public'):
            validate_candidate(self.root, '1.1.0')

    def test_missing_marker_rejected_for_new_release(self):
        with self.assertRaisesRegex(ValueError, 'marker'):
            validate_candidate(self.root, '1.1.0')
        self.assertIsNone(validate_candidate(self.root, '1.0.0'))

    def test_other_version_rejected(self):
        write_candidate(self.root, '1.1.0')
        with self.assertRaisesRegex(ValueError, 'matching public'):
            validate_candidate(self.root, '1.2.0')

    def test_replaced_asset_and_updated_checksum_file_rejected(self):
        write_candidate(self.root, '1.1.0')
        changed = b'replaced gameplay'
        (self.root / 'RV-Setup.zip').write_bytes(changed)
        checksum_file = self.root / 'SHA256SUMS.txt'
        lines = checksum_file.read_text().splitlines()
        lines[0] = hashlib.sha256(changed).hexdigest() + '  RV-Setup.zip'
        checksum_file.write_text('\n'.join(lines) + '\n')
        with self.assertRaisesRegex(ValueError, 'changed after packaging'):
            validate_candidate(self.root, '1.1.0')

    def test_published_output_can_only_verify_identical_bytes(self):
        write_candidate(self.root, '1.1.0')
        original = (self.root / 'RV-Setup.zip').read_bytes()
        mark_published(self.root, '1.1.0', 'a' * 40, 'https://github.com/rudyvale/rv-warfare/releases/tag/v1.1.0')
        candidate = validate_candidate(self.root, '1.1.0')
        self.assertEqual(candidate['state'], 'published')
        self.assertEqual(candidate['sourceCommit'], 'a' * 40)
        self.assertEqual((self.root / 'RV-Setup.zip').read_bytes(), original)
        with self.assertRaisesRegex(ValueError, 'immutable'):
            validate_output(self.root, '1.1.0', replace_candidate=True)

    def test_write_rejects_incorrect_checksums(self):
        (self.root / 'RV-Setup.zip').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            write_candidate(self.root, '1.1.0')
        self.assertFalse((self.root / '.release-candidate.json').exists())

    def test_unknown_marker_schema_rejected(self):
        write_candidate(self.root, '1.1.0')
        marker = self.root / '.release-candidate.json'
        data = json.loads(marker.read_text())
        data['schema'] = 2
        marker.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Invalid candidate'):
            validate_candidate(self.root, '1.1.0')


if __name__ == '__main__':
    unittest.main(verbosity=2)
