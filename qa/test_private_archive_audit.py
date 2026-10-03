import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from audit_public_archives import audit_archives


def archive_bytes(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return stream.getvalue()


class PrivateArchiveTests(unittest.TestCase):
    INVITE = {'schema': 1, 'product': 'RV', 'transport': 'porthole', 'target': 'TESTCODE', 'port': 25565, 'version': '2.0.0', 'label': 'Fixture'}

    def audit(self, files, public=True):
        with tempfile.TemporaryDirectory(prefix='rv-private-audit-') as temporary:
            path = Path(temporary) / 'candidate.zip'
            path.write_bytes(archive_bytes(files))
            return audit_archives([path], ROOT / 'pack/vendor-catalog.json', public=public)

    def assert_private(self, files):
        result = self.audit(files)
        self.assertFalse(result['passed'])
        self.assertIn('PRIVATE_CONNECTION_DATA', {item['kind'] for item in result['findings']})
        self.assertNotIn('TESTCODE', json.dumps(result))

    def test_named_invite_rejected_even_with_blank_or_invalid_content(self):
        for data in (b'{}', b'invalid', json.dumps(self.INVITE).encode()):
            with self.subTest(data=data):
                self.assert_private({'world/RV.RVInvite': data})

    def test_renamed_and_nested_invite_rejected(self):
        data = json.dumps(self.INVITE).encode()
        self.assert_private({'world/data/settings.dat': data})
        self.assert_private({'payload.data': archive_bytes({'renamed.bin': data})})

    def test_bom_utf16_nested_and_padded_json_rejected(self):
        text = json.dumps(self.INVITE)
        for data in (text.encode('utf-8-sig'), text.encode('utf-16'), json.dumps({'profile': self.INVITE}).encode(), (text + ' ' * 70000).encode()):
            with self.subTest(encoding=len(data)):
                self.assert_private({'world/data/fixture.dat': data})

    def test_populated_defaults_rejected_and_public_blank_allowed(self):
        self.assert_private({'server-defaults.json': b'{"connectionMode":"porthole","connectionTarget":"TESTCODE"}'})
        result = self.audit({'server-defaults.json': b'{"connectionMode":"porthole","connectionTarget":""}', 'config/game.json': b'{"target":"enemy","product":"RV"}'})
        self.assertTrue(result['passed'])

    def test_duplicate_keys_preserve_private_values(self):
        self.assert_private({'renamed.json': b'{"connectionTarget":"TESTCODE","connectionTarget":""}'})
        self.assert_private({'renamed.json': b'{"product":"RV","transport":"porthole","target":"TESTCODE","target":""}'})

    def test_public_mode_is_strict_and_top_level_suffix_is_checked(self):
        for value in (None, 0, 1, '', 'false'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'boolean'):
                self.audit({'safe.json': b'{}'}, public=value)
        with tempfile.TemporaryDirectory(prefix='rv-top-invite-') as temporary:
            path = Path(temporary) / 'fixture.rvinvite'
            path.write_bytes(archive_bytes({'safe.txt': b'fixture'}))
            result = audit_archives([path], ROOT / 'pack/vendor-catalog.json')
            self.assertFalse(result['passed'])
            self.assertIn('PRIVATE_CONNECTION_DATA', {item['kind'] for item in result['findings']})

    def test_private_friend_mode_keeps_vendor_checks_active(self):
        private = self.audit({'server-defaults.json': json.dumps(self.INVITE).encode()}, public=False)
        self.assertTrue(private['passed'])
        self.assertFalse(private['public'])
        self.assertEqual(private['status'], 'PRIVATE_ARCHIVE_BYTES_READY')
        data = b'vendor fixture'
        import hashlib
        catalog = {'files': [{'id': 'fixture', 'path': 'mods/fixture.jar', 'sha256': hashlib.sha256(data).hexdigest(), 'delivery': 'official-download', 'rights': {'rehostAllowed': False}}]}
        with tempfile.TemporaryDirectory(prefix='rv-private-rights-') as temporary:
            path = Path(temporary) / 'friend.zip'
            path.write_bytes(archive_bytes({'renamed.bin': data}))
            result = audit_archives([path], catalog, public=False)
            self.assertFalse(result['passed'])
            self.assertIn('FORBIDDEN_VENDOR_BYTES', {item['kind'] for item in result['findings']})


if __name__ == '__main__':
    unittest.main(verbosity=2)
