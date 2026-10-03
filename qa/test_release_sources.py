import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from release_contract import client_source_names, write_candidate
from verify_release import verify_host_map, verify_sources


class ReleaseSourceTests(unittest.TestCase):
    MAP = json.dumps({'schema': 1, 'mcheliSha256': 'a' * 64, 'resources': {'assets/mcheli/models/planes/rv_fp1.mqo': 'b' * 64}}).encode()

    def client_fixture(self, root, missing=None, changed=None):
        files = {name: ('frozen source ' + name).encode() for name in client_source_names('2.0.0')}
        files['release.json'] = b'{"version":"2.0.0"}'
        for name, data in files.items():
            path = root / 'src' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for name in ('READ-ME.md', 'server-defaults.json', 'THIRD-PARTY-NOTICES.md', 'vendor-catalog.json'):
            files[name] = ('frozen pack ' + name).encode()
            path = root / 'pack' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[name])
        (root / 'assets').mkdir()
        (root / 'assets/code.ico').write_bytes(b'icon fixture')
        files['code.ico'] = b'icon fixture'
        for name in ('package-manifest.json', 'installer-files.json', 'payload.zip', 'runtime.zip', 'INSTALL.cmd', '\u0423\u0421\u0422\u0410\u041d\u041e\u0412\u0418\u0422\u042c.cmd', 'Play.cmd'):
            files[name] = b'package fixture'
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, data in files.items():
                if name != missing:
                    archive.writestr('RV-Setup/' + name, b'stale helper' if name == changed else data)
        stream.seek(0)
        return zipfile.ZipFile(stream)

    def test_rv2_client_sources_match_checkout(self):
        with tempfile.TemporaryDirectory(prefix='rv2-sources-') as temporary:
            with self.client_fixture(Path(temporary)) as archive:
                verify_sources(archive, Path(temporary), True)

    def test_rv2_cannot_omit_controls_or_connection_profiles(self):
        for name in ('Warfare-ClientControls.ps1', 'Warfare-ConnectionProfiles.ps1'):
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix='rv2-sources-') as temporary:
                with self.client_fixture(Path(temporary), missing=name) as archive:
                    with self.assertRaisesRegex(ValueError, 'Missing packaged source: ' + name):
                        verify_sources(archive, Path(temporary), True)

    def test_rv2_stale_controls_rejected(self):
        with tempfile.TemporaryDirectory(prefix='rv2-sources-') as temporary:
            with self.client_fixture(Path(temporary), changed='Warfare-ClientControls.ps1') as archive:
                with self.assertRaisesRegex(ValueError, 'frozen checkout: Warfare-ClientControls.ps1'):
                    verify_sources(archive, Path(temporary), True)

    def host_archive(self, changed=None, extra=None, missing=None):
        files = {name: ROOT / 'host' / name for name in ('README.md', 'warfare-launcher.py', 'play-owner.py', 'owner-panel.py', 'world_reset.py', 'host_runtime.py', 'porthole-status.py', 'run-server.py', 'launch-warfare.py', 'launcher-texts.json', 'Join-Server.ps1', 'Launch-Warfare.ps1', 'Start-All.ps1', 'Start-Server.ps1', 'Start-Porthole.ps1', 'Porthole-Host.ps1', 'Get-ClientMemory.ps1', 'Stop-All.ps1', 'Stop-Server.ps1', 'Check-OwnerConnection.ps1')}
        files.update({name: ROOT / 'src' / name for name in ('Check-WarfareUpdate.ps1', 'Warfare-Updates.ps1', 'Warfare-Connection.ps1', 'Warfare-Performance.ps1', 'Warfare-Onboarding.ps1', 'Configure-FirstPlay.ps1', 'Configure-Controller.ps1', 'release.json')})
        files['THIRD-PARTY-NOTICES.md'] = ROOT / 'pack/THIRD-PARTY-NOTICES.md'
        files['code.ico'] = ROOT / 'assets/code.ico'
        metadata = json.loads((ROOT / 'src/release.json').read_text())
        if tuple(map(int, metadata['version'].split('.'))) >= (1, 2, 0):
            files['vendor-catalog.json'] = ROOT / 'pack/vendor-catalog.json'
            for name in ('server_vendors.py', 'Install-ServerVendors.ps1', 'Warfare-VendorDownloads.ps1'):
                files[name] = ROOT / 'host' / name
            if metadata.get('managedModsSha256'):
                files['rv-managed-mods.json'] = ROOT / 'pack/rv-managed-mods.json'
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, file in files.items():
                if name == missing:
                    continue
                archive.writestr(name, b'old launcher' if name == changed else file.read_bytes())
            archive.writestr('rv-addon-assets.json', self.MAP)
            if metadata.get('managedModsSha256'):
                owned = json.loads((ROOT / 'pack/rv-managed-mods.json').read_text())
                for entry in owned['mods']:
                    archive.writestr('host-owned/' + entry['path'], b'owned mod source fixture')
            if extra:
                archive.writestr(extra, b'private local state')
        stream.seek(0)
        return zipfile.ZipFile(stream)

    def test_matching_frozen_host_sources_accepted(self):
        with self.host_archive() as archive:
            verify_sources(archive, ROOT, False)

    def test_stale_launcher_rejected(self):
        with self.host_archive(changed='warfare-launcher.py') as archive:
            with self.assertRaisesRegex(ValueError, 'frozen checkout: warfare-launcher.py'):
                verify_sources(archive, ROOT, False)

    def test_host_first_play_cannot_omit_connection_dependency(self):
        with self.host_archive(missing='Warfare-Connection.ps1') as archive:
            with self.assertRaisesRegex(ValueError, 'Missing packaged source: Warfare-Connection.ps1'):
                verify_sources(archive, ROOT, False)

    def test_local_server_profile_cannot_enter_public_host_archive(self):
        with self.host_archive(extra='.server-profile-applied.json') as archive:
            with self.assertRaisesRegex(ValueError, 'Unexpected files'):
                verify_sources(archive, ROOT, False)

    def test_host_map_matches_frozen_source_bytes(self):
        with tempfile.TemporaryDirectory(prefix='rv-host-map-') as temporary:
            source = Path(temporary) / 'rv-addon-assets.json'
            source.write_bytes(self.MAP)
            with self.host_archive() as archive:
                verify_host_map(archive, source)

    def test_host_map_from_other_candidate_rejected(self):
        with tempfile.TemporaryDirectory(prefix='rv-host-map-') as temporary:
            source = Path(temporary) / 'rv-addon-assets.json'
            source.write_bytes(self.MAP.replace(b'aaaaaaaa', b'cccccccc'))
            with self.host_archive() as archive:
                with self.assertRaisesRegex(ValueError, 'differs from the frozen source'):
                    verify_host_map(archive, source)

    def test_private_marker_rejected_by_publisher_before_other_actions(self):
        with tempfile.TemporaryDirectory(prefix='rv-publisher-private-') as temporary:
            output = Path(temporary)
            lines = []
            for name in ('RV-Setup.zip', 'RV-Host-Tools.zip', 'RV-Third-Party-Sources.zip'):
                data = name.encode()
                (output / name).write_bytes(data)
                lines.append(hashlib.sha256(data).hexdigest() + '  ' + name)
            (output / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n')
            version = json.loads((ROOT / 'src/release.json').read_text())['version']
            write_candidate(output, version, private=True)
            result = subprocess.run([sys.executable, str(ROOT / 'tools/publish_release.py'), '--directory', str(output), '--notes', str(output / 'missing-notes.md'), '--publish'], text=True, capture_output=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Only the matching public candidate', result.stderr)
            self.assertNotIn('Authenticate', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
