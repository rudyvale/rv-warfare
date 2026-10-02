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
from release_contract import write_candidate
from verify_release import verify_host_map, verify_sources


class ReleaseSourceTests(unittest.TestCase):
    MAP = json.dumps({'schema': 1, 'mcheliSha256': 'a' * 64, 'resources': {'assets/mcheli/models/planes/rv_fp1.mqo': 'b' * 64}}).encode()

    def host_archive(self, changed=None, extra=None, missing=None):
        files = {name: ROOT / 'host' / name for name in ('README.md', 'warfare-launcher.py', 'host_runtime.py', 'porthole-status.py', 'run-server.py', 'launch-warfare.py', 'launcher-texts.json', 'Join-Server.ps1', 'Launch-Warfare.ps1', 'Start-All.ps1', 'Start-Server.ps1', 'Start-Porthole.ps1', 'Porthole-Host.ps1', 'Get-ClientMemory.ps1', 'Stop-All.ps1', 'Stop-Server.ps1', 'Check-OwnerConnection.ps1')}
        files.update({name: ROOT / 'src' / name for name in ('Check-WarfareUpdate.ps1', 'Warfare-Updates.ps1', 'Warfare-Connection.ps1', 'Warfare-Performance.ps1', 'Warfare-Onboarding.ps1', 'Configure-FirstPlay.ps1', 'Configure-Controller.ps1', 'release.json')})
        files['THIRD-PARTY-NOTICES.md'] = ROOT / 'pack/THIRD-PARTY-NOTICES.md'
        files['code.ico'] = ROOT / 'assets/code.ico'
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, file in files.items():
                if name == missing:
                    continue
                archive.writestr(name, b'old launcher' if name == changed else file.read_bytes())
            archive.writestr('rv-addon-assets.json', self.MAP)
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
