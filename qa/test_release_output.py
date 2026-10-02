import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from release_contract import validate_output


class ReleaseOutputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rv-output-gate-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def marker(self, state='candidate', version='1.1.0', kind='public'):
        (self.root / '.release-candidate.json').write_text(json.dumps({'schema': 1, 'state': state, 'version': version, 'kind': kind}))

    def test_empty_output_allowed(self):
        validate_output(self.root, '1.1.0')

    def test_geometry_only_output_allowed(self):
        (self.root / 'RV-World-Template.zip').write_bytes(b'geometry')
        validate_output(self.root, '1.1.0')

    def test_legacy_published_output_never_overwritten(self):
        path = self.root / 'RV-Setup.zip'
        path.write_bytes(b'published 1.0')
        for replace in (False, True):
            with self.assertRaisesRegex(ValueError, 'no candidate marker'):
                validate_output(self.root, '1.1.0', replace_candidate=replace)
        self.assertEqual(path.read_bytes(), b'published 1.0')

    def test_candidate_needs_explicit_replace(self):
        self.marker()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            validate_output(self.root, '1.1.0')
        validate_output(self.root, '1.1.0', replace_candidate=True)

    def test_other_version_rejected(self):
        self.marker(version='1.0.0')
        with self.assertRaisesRegex(ValueError, 'another version'):
            validate_output(self.root, '1.1.0', replace_candidate=True)

    def test_private_public_mix_rejected(self):
        self.marker(kind='private')
        with self.assertRaisesRegex(ValueError, 'package type'):
            validate_output(self.root, '1.1.0', replace_candidate=True)

    def test_published_candidate_cannot_be_replaced(self):
        self.marker(state='published')
        with self.assertRaisesRegex(ValueError, 'immutable'):
            validate_output(self.root, '1.1.0', replace_candidate=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
