import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rv_profile_runtime', ROOT / 'host/host_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class ServerProfiles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rv-server-profile-')
        self.root = Path(self.temp.name)
        self.original = b'# keep custom settings\r\nlevel-name=PersonalWorld\r\nview-distance=12\r\npvp=true\r\nonline-mode=false\r\n'
        (self.root / 'server.properties').write_bytes(self.original)

    def tearDown(self):
        self.temp.cleanup()

    def test_no_selection_preserves_original_byte_for_byte(self):
        runtime.apply_pending_profile(self.root, {'custom': True})
        self.assertEqual((self.root / 'server.properties').read_bytes(), self.original)
        self.assertFalse((self.root / 'backups').exists())

    def test_explicit_low_profile_only_changes_distance_and_keeps_backup(self):
        result = runtime.apply_pending_profile(self.root, {'pendingServerProfile': 'low', 'serverMemoryGB': 2, 'custom': True})
        self.assertEqual((self.root / 'server.properties').read_bytes(), self.original.replace(b'view-distance=12', b'view-distance=4'))
        self.assertEqual(next((self.root / 'backups').glob('*.properties')).read_bytes(), self.original)
        self.assertEqual(runtime.read_json(self.root / '.server-profile-applied.json')['profile'], 'low')
        self.assertTrue(result['custom'])
        runtime.apply_pending_profile(self.root, result)
        self.assertEqual(len(list((self.root / 'backups').glob('*.properties'))), 1)
        (self.root / 'server.properties').write_bytes(self.original)
        runtime.apply_pending_profile(self.root, result)
        self.assertEqual((self.root / 'server.properties').read_bytes(), self.original)

    def test_new_request_can_reapply_without_overwriting_latest_settings(self):
        runtime.write_json(self.root / 'launcher-settings.json', {'pendingServerProfile': 'quality', 'serverProfileRequest': 'new', 'other': 'keep'})
        before = (self.root / 'launcher-settings.json').read_bytes()
        runtime.apply_pending_profile(self.root, {'pendingServerProfile': 'low', 'serverProfileRequest': 'older'})
        self.assertEqual((self.root / 'launcher-settings.json').read_bytes(), before)
        runtime.apply_pending_profile(self.root, runtime.read_json(self.root / 'launcher-settings.json'))
        self.assertIn(b'view-distance=8', (self.root / 'server.properties').read_bytes())

    def test_running_server_cannot_change_properties(self):
        with patch.object(runtime, 'server_status', return_value={'state': 'running', 'ready': True}):
            with self.assertRaises(RuntimeError):
                runtime.apply_pending_profile(self.root, {'pendingServerProfile': 'balanced'})
        self.assertEqual((self.root / 'server.properties').read_bytes(), self.original)

    def test_invalid_or_ambiguous_profile_never_writes(self):
        with self.assertRaises(ValueError):
            runtime.apply_pending_profile(self.root, {'pendingServerProfile': 'unsafe'})
        duplicate = self.original + b'view-distance=8\r\n'
        (self.root / 'server.properties').write_bytes(duplicate)
        with self.assertRaises(ValueError):
            runtime.apply_pending_profile(self.root, {'pendingServerProfile': 'quality'})
        self.assertEqual((self.root / 'server.properties').read_bytes(), duplicate)

    def test_memory_profiles_remain_capped_on_low_ram(self):
        for total in (8, 12, 16, 32):
            for profile in runtime.SERVER_PROFILES.values():
                value = runtime.memory_limit({'serverMemoryGB': profile['memory']}, total)
                self.assertLessEqual(value, total / 2)
                self.assertGreaterEqual(value, 2)


if __name__ == '__main__':
    unittest.main()
