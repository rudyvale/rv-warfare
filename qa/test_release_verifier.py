import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class ReleaseVerifierTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rv-verifier-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_optimized(self):
        return subprocess.run([sys.executable, '-O', str(ROOT / 'tools/verify_release.py'), '--directory', str(self.root), '--tag', 'v1.1.0'], text=True, capture_output=True, timeout=20)

    def test_checksum_verification_survives_optimized_python(self):
        (self.root / 'RV-Setup.zip').write_bytes(b'corrupt')
        (self.root / 'SHA256SUMS.txt').write_text('0' * 64 + '  RV-Setup.zip\n' + '1' * 64 + '  RV-Host-Tools.zip\n')
        result = self.run_optimized()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Asset checksum mismatch', result.stderr)

    def test_private_world_rejected_in_optimized_python(self):
        with zipfile.ZipFile(self.root / 'RV-World-Template.zip', 'w') as archive:
            archive.writestr('Battlefield/playerdata/personal.dat', b'private')
        data = (self.root / 'RV-World-Template.zip').read_bytes()
        (self.root / 'SHA256SUMS.txt').write_text(hashlib.sha256(data).hexdigest() + '  RV-World-Template.zip\n' + '0' * 64 + '  RV-Setup.zip\n' + '1' * 64 + '  RV-Host-Tools.zip\n')
        result = self.run_optimized()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Private world entry', result.stderr)

    def test_windows_path_traversal_rejected(self):
        with zipfile.ZipFile(self.root / 'RV-Setup.zip', 'w') as archive:
            archive.writestr('RV-Setup\\..\\escape.ps1', b'unsafe')
        data = (self.root / 'RV-Setup.zip').read_bytes()
        (self.root / 'SHA256SUMS.txt').write_text(hashlib.sha256(data).hexdigest() + '  RV-Setup.zip\n' + '1' * 64 + '  RV-Host-Tools.zip\n')
        result = self.run_optimized()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unsafe archive path', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
