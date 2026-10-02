import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from download_release_base import download, REQUIRED


def zip_bytes(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return stream.getvalue()


class Response(io.BytesIO):
    def __init__(self, data, url='https://release-assets.githubusercontent.com/fixture'):
        super().__init__(data)
        self.url = url


class ReleaseBaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rv-base-download-')
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / 'baseline'

    def fixture(self, version='1.0.0', extra=None, performance=True, omit=None):
        payload = zip_bytes([('mods/game.jar', b'game')])
        runtime = zip_bytes([('bin/java.exe', b'java')])
        manifest = {'version': version, 'archives': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest()} for name, data in [('payload.zip', payload), ('runtime.zip', runtime)]], 'managedFiles': [{'path': 'mods/game.jar', 'sha256': hashlib.sha256(b'game').hexdigest()}]}
        metadata = {'version': version, 'repository': 'rudyvale/rv-warfare'}
        if version != '1.0.0':
            metadata['requiredMods'] = {'mcheli': 'fixture-advertised-version'}
        content = {'payload.zip': payload, 'runtime.zip': runtime, 'release.json': json.dumps(metadata), 'package-manifest.json': json.dumps(manifest)}
        names = set(REQUIRED)
        if version != '1.0.0' and performance:
            names.add('Warfare-Performance.ps1')
        if version != '1.0.0':
            names.update({'Warfare-Onboarding.ps1', 'Configure-FirstPlay.ps1', 'THIRD-PARTY-NOTICES.md'})
        if omit:
            names.discard(omit)
        entries = [('RV-Setup/' + name, content.get(name, 'fixture')) for name in sorted(names)]
        if extra:
            entries.append(extra)
        data = zip_bytes(entries)
        tag = 'v' + version
        asset = {'name': 'RV-Setup.zip', 'state': 'uploaded', 'digest': 'sha256:' + hashlib.sha256(data).hexdigest(), 'size': len(data), 'browser_download_url': 'https://github.com/rudyvale/rv-warfare/releases/download/' + tag + '/RV-Setup.zip'}
        release = {'draft': False, 'prerelease': False, 'tag_name': tag, 'html_url': 'https://github.com/rudyvale/rv-warfare/releases/tag/' + tag, 'assets': [asset]}
        return release, data

    def attempt(self, release, data, redirect='https://release-assets.githubusercontent.com/fixture'):
        with patch('download_release_base.urllib.request.urlopen', side_effect=[Response(json.dumps(release).encode()), Response(data, redirect)]) as network:
            report = download(release['tag_name'], self.output)
            self.assertEqual(network.call_count, 2)
            return report

    def test_verified_baseline_extracted_and_reported(self):
        release, data = self.fixture()
        report = self.attempt(release, data)
        self.assertTrue(report['passed'])
        self.assertEqual(report['assetSha256'], hashlib.sha256(data).hexdigest())
        self.assertTrue((self.output / 'RV-Setup/payload.zip').is_file())
        self.assertTrue((self.output / 'baseline-report.json').is_file())

    def test_new_baseline_without_source_notice_rejected(self):
        release, data = self.fixture('1.1.0', omit='THIRD-PARTY-NOTICES.md')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.attempt(release, data)
        self.assertFalse((self.output / 'RV-Setup').exists())

    def test_new_metadata_mapping_and_performance_helper_supported(self):
        report = self.attempt(*self.fixture('1.1.0'))
        self.assertEqual(report['tag'], 'v1.1.0')
        self.assertTrue((self.output / 'RV-Setup/Warfare-Performance.ps1').is_file())

    def test_missing_new_helper_rejected_before_extraction(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.attempt(*self.fixture('1.1.0', performance=False))
        self.assertFalse((self.output / 'RV-Setup').exists())

    def test_missing_first_play_helper_rejected_before_extraction(self):
        for name in ('Warfare-Onboarding.ps1', 'Configure-FirstPlay.ps1'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='rv-base-onboarding-') as temporary:
                self.output = Path(temporary) / 'baseline'
                with self.assertRaisesRegex(ValueError, 'incomplete'):
                    self.attempt(*self.fixture('1.1.0', omit=name))
                self.assertFalse((self.output / 'RV-Setup').exists())

    def test_existing_output_never_changes(self):
        self.output.mkdir()
        kept = self.output / 'kept.txt'
        kept.write_text('published')
        with patch('download_release_base.urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'already exists'):
                download('v1.0.0', self.output)
            network.assert_not_called()
        self.assertEqual(kept.read_text(), 'published')

    def test_draft_and_prerelease_rejected(self):
        for field in ('draft', 'prerelease'):
            release, data = self.fixture()
            release[field] = True
            with self.assertRaisesRegex(ValueError, 'public and stable'):
                self.attempt(release, data)
        self.assertFalse(self.output.exists())

    def test_other_origin_and_duplicate_asset_rejected(self):
        release, data = self.fixture()
        release['assets'][0]['browser_download_url'] = 'https://example.com/RV-Setup.zip'
        with self.assertRaisesRegex(ValueError, 'origin'):
            self.attempt(release, data)
        release, data = self.fixture()
        release['assets'].append(release['assets'][0])
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            self.attempt(release, data)
        self.assertFalse(self.output.exists())

    def test_untrusted_redirect_rejected(self):
        with self.assertRaisesRegex(ValueError, 'redirect'):
            self.attempt(*self.fixture(), redirect='https://example.com/package')
        self.assertFalse((self.output / 'RV-Setup').exists())

    def test_corrupt_download_rejected(self):
        release, data = self.fixture()
        release['assets'][0]['digest'] = 'sha256:' + '0' * 64
        with self.assertRaisesRegex(ValueError, 'checksum or size'):
            self.attempt(release, data)
        self.assertFalse((self.output / 'RV-Setup').exists())

    def test_traversal_rejected_before_extraction(self):
        with self.assertRaisesRegex(ValueError, 'Unsafe archive path'):
            self.attempt(*self.fixture(extra=('RV-Setup/../../escape.ps1', 'unsafe')))
        self.assertFalse((self.output / 'RV-Setup').exists())

    def test_download_size_limit_rejected_without_output(self):
        release, data = self.fixture()
        release['assets'][0]['size'] = 2147483649
        with self.assertRaisesRegex(ValueError, 'size is invalid'):
            self.attempt(release, data)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
