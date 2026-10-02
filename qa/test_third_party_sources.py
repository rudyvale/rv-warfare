import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from third_party_sources import build_bundle, download_source, load_registry, verify_bundle, verify_vendor_manifest, verify_vendor_payload


class ThirdPartySourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rv-original-sources-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.registry_path = self.root / 'components.json'
        self.notice = self.root / 'README.md'
        self.notice.write_text('Original upstream sources and license notices.\n')
        self.output = self.root / 'RV-Third-Party-Sources.zip'
        license_data = b'Upstream license fixture'
        self.vendor = b'Original vendor JAR fixture'
        stream = io.BytesIO()
        self.commit = 'a' * 40
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('Example-' + self.commit + '/LICENSE', license_data)
            archive.writestr('Example-' + self.commit + '/src/main/java/Mod.java', 'class Mod {}')
        self.source = stream.getvalue()
        self.entry = {'name': 'Example', 'modId': 'example', 'binaryFile': 'example-1.0.jar', 'binarySize': len(self.vendor), 'binarySha256': hashlib.sha256(self.vendor).hexdigest(), 'sourceRepository': 'https://github.com/Example/Example', 'sourceCommit': self.commit, 'sourceUrl': 'https://codeload.github.com/Example/Example/zip/' + self.commit, 'sourceArchive': 'sources/Example-' + self.commit[:12] + '.zip', 'sourceSize': len(self.source), 'sourceSha256': hashlib.sha256(self.source).hexdigest(), 'licenses': [{'sourcePath': 'LICENSE', 'path': 'licenses/example/LICENSE', 'sha256': hashlib.sha256(license_data).hexdigest()}]}
        self.registry = {'schema': 1, 'minecraft': '1.12.2', 'components': [self.entry]}
        self.write_registry()
        (self.cache / Path(self.entry['sourceArchive']).name).write_bytes(self.source)

    def write_registry(self):
        self.registry_path.write_text(json.dumps(self.registry) + '\n')

    def build(self):
        return build_bundle(self.registry_path, self.notice, self.output, self.cache)

    def rewrite_bundle(self, changed=None, missing=None, extra=None):
        with zipfile.ZipFile(self.output) as archive:
            entries = {name: archive.read(name) for name in archive.namelist() if name != missing}
        if changed:
            entries[changed] = b'replaced'
        if extra:
            entries[extra] = b'private local state'
        with zipfile.ZipFile(self.output, 'w') as archive:
            for name, data in entries.items():
                archive.writestr(name, data)

    def test_original_archive_and_licenses_preserved(self):
        with patch('third_party_sources.urllib.request.urlopen') as network:
            report = self.build()
            network.assert_not_called()
        self.assertEqual(report['components'], 1)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.read(self.entry['sourceArchive']), self.source)
            self.assertEqual(archive.read('licenses/example/LICENSE'), b'Upstream license fixture')
        verify_bundle(self.output, self.registry_path, self.notice)

    def test_existing_source_asset_is_immutable(self):
        self.build()
        original = self.output.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.build()
        self.assertEqual(self.output.read_bytes(), original)

    def test_changed_upstream_archive_rejected(self):
        (self.cache / Path(self.entry['sourceArchive']).name).write_bytes(b'replaced')
        with self.assertRaisesRegex(ValueError, 'checksum or size mismatch'):
            self.build()
        self.assertFalse(self.output.exists())

    def test_unpinned_source_url_rejected(self):
        self.entry['sourceUrl'] = 'https://codeload.github.com/Example/Example/zip/main'
        self.write_registry()
        with self.assertRaisesRegex(ValueError, 'pinned commit'):
            load_registry(self.registry_path)

    def test_missing_main_license_rejected(self):
        self.entry['licenses'] = [{'sourcePath': 'API_LICENSE', 'path': 'licenses/example/API_LICENSE', 'sha256': 'b' * 64}]
        self.write_registry()
        with self.assertRaisesRegex(ValueError, 'main license'):
            load_registry(self.registry_path)

    def test_duplicate_component_rejected(self):
        self.registry['components'].append(dict(self.entry))
        self.write_registry()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            load_registry(self.registry_path)

    def test_replaced_bundle_source_rejected(self):
        self.build()
        self.rewrite_bundle(changed=self.entry['sourceArchive'])
        with self.assertRaisesRegex(ValueError, 'checksum or size mismatch'):
            verify_bundle(self.output, self.registry_path, self.notice)

    def test_replaced_license_rejected(self):
        self.build()
        self.rewrite_bundle(changed='licenses/example/LICENSE')
        with self.assertRaisesRegex(ValueError, 'license differs'):
            verify_bundle(self.output, self.registry_path, self.notice)

    def test_private_extra_file_rejected(self):
        self.build()
        self.rewrite_bundle(extra='credentials.json')
        with self.assertRaisesRegex(ValueError, 'Unexpected source bundle files'):
            verify_bundle(self.output, self.registry_path, self.notice)

    def test_stale_notice_rejected(self):
        self.build()
        self.notice.write_text('New source notice')
        with self.assertRaisesRegex(ValueError, 'frozen source'):
            verify_bundle(self.output, self.registry_path, self.notice)

    def test_modified_vendor_jar_rejected(self):
        registry = load_registry(self.registry_path)
        manifest = {'managedFiles': [{'path': 'mods/' + self.entry['binaryFile'], 'sha256': self.entry['binarySha256']}]}
        verify_vendor_manifest(manifest, registry)
        manifest['managedFiles'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Vendor binary differs'):
            verify_vendor_manifest(manifest, registry)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('mods/' + self.entry['binaryFile'], b'changed')
        with zipfile.ZipFile(stream) as archive:
            with self.assertRaisesRegex(ValueError, 'Vendor binary differs'):
                verify_vendor_payload(archive, registry)

    def test_download_size_bound_rejects_extra_bytes(self):
        for file in self.cache.iterdir():
            file.unlink()
        response = io.BytesIO(self.source + b'overflow')
        response.url = self.entry['sourceUrl']
        with patch('third_party_sources.urllib.request.urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'exceeds its limit'):
                download_source(self.entry, self.cache)
        self.assertEqual(list(self.cache.iterdir()), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
