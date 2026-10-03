import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from verify_release import verify_remote


class ReleasePreviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rv-preview-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.expected = {}
        self.assets = []
        for name in ('RV-Setup.zip', 'RV-Host-Tools.zip', 'RV-Third-Party-Sources.zip', 'RV-World-Template.zip', 'SHA256SUMS.txt'):
            data = name.encode()
            (self.root / name).write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.assets.append({'name': name, 'digest': 'sha256:' + digest, 'size': len(data), 'state': 'uploaded'})
            if name != 'SHA256SUMS.txt':
                self.expected[name] = digest
        self.release = {'draft': False, 'prerelease': True, 'tag_name': 'v2.0.0', 'assets': self.assets}

    def verify(self, release=None, latest='v1.2.1', prerelease=True):
        documents = [release or self.release, {'tag_name': latest}]
        with patch('verify_release.urllib.request.urlopen', side_effect=[io.BytesIO(json.dumps(item).encode()) for item in documents]):
            verify_remote(self.root, 'v2.0.0', self.expected, prerelease)

    def test_preview_preserves_stable_update_target(self):
        self.verify()

    def test_preview_cannot_be_latest(self):
        with self.assertRaisesRegex(ValueError, 'replaced stable latest'):
            self.verify(latest='v2.0.0')

    def test_stable_verification_cannot_accept_preview(self):
        with self.assertRaisesRegex(ValueError, 'preview status'):
            self.verify(prerelease=False)

    def test_stable_release_must_be_latest(self):
        release = {**self.release, 'prerelease': False}
        with self.assertRaisesRegex(ValueError, 'not latest'):
            self.verify(release=release, prerelease=False)
        self.verify(release=release, latest='v2.0.0', prerelease=False)

    def test_preview_requires_exact_uploaded_asset_bytes(self):
        for field, value in (('digest', 'sha256:' + '0' * 64), ('size', 0), ('state', 'new')):
            with self.subTest(field=field):
                release = copy.deepcopy(self.release)
                release['assets'][0][field] = value
                with self.assertRaises(ValueError):
                    self.verify(release=release)

    def test_preview_rejects_draft_wrong_tag_and_extra_asset(self):
        for field, value in (('draft', True), ('tag_name', 'v2.0.1')):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(release={**self.release, field: value})
        with self.assertRaisesRegex(ValueError, 'Unexpected release assets'):
            self.verify(release={**self.release, 'assets': self.assets + [self.assets[0]]})


if __name__ == '__main__':
    unittest.main(verbosity=2)
