from contextlib import nullcontext
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
import world_reset as reset


class WorldResetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = Path(self.temp.name)
        self.world = self.server / 'Battlefield'
        (self.world / 'region').mkdir(parents=True)
        (self.world / 'data').mkdir()
        (self.world / 'playerdata').mkdir()
        (self.server / 'server.properties').write_text('level-name=Battlefield\nserver-port=25565\n')
        (self.world / 'level.dat').write_bytes(b'level')
        (self.world / 'region/r.0.0.mca').write_bytes(b'original terrain')
        (self.world / 'data/scoreboard.dat').write_bytes(b'player scores')
        (self.world / 'playerdata/owner.dat').write_bytes(b'player inventory')
        self.guard = patch.object(reset, 'maintenance', lambda server: nullcontext())
        self.guard.start()
        reset.capture_baseline(self.server)
        (self.world / 'region/r.0.0.mca').write_bytes(b'destroyed terrain')

    def tearDown(self):
        self.guard.stop()
        self.temp.cleanup()

    def test_map_reset_restores_terrain_and_preserves_inventory_and_scores(self):
        result = reset.restore_stopped(self.server, 'map')
        self.assertEqual((self.world / 'region/r.0.0.mca').read_bytes(), b'original terrain')
        self.assertEqual((self.world / 'playerdata/owner.dat').read_bytes(), b'player inventory')
        self.assertEqual((self.world / 'data/scoreboard.dat').read_bytes(), b'player scores')
        self.assertEqual((Path(result['backup']) / 'Battlefield/region/r.0.0.mca').read_bytes(), b'destroyed terrain')

    def test_new_game_reset_does_not_retain_players_or_scores(self):
        reset.restore_stopped(self.server, 'all')
        self.assertFalse((self.world / 'playerdata').exists())
        self.assertFalse((self.world / 'data/scoreboard.dat').exists())
        self.assertEqual((self.world / 'region/r.0.0.mca').read_bytes(), b'original terrain')

    def test_corrupted_baseline_cannot_replace_current_world(self):
        (self.server / '.world-reset/baseline/region/r.0.0.mca').write_bytes(b'corrupted')
        with self.assertRaises(ValueError):
            reset.restore_stopped(self.server)
        self.assertEqual((self.world / 'region/r.0.0.mca').read_bytes(), b'destroyed terrain')

    def test_failed_install_rolls_back_the_original_world(self):
        original = Path.replace
        def replace(path, target):
            if path.name.startswith('.world-reset-stage-'):
                raise OSError('Simulated file lock')
            return original(path, target)
        with patch.object(Path, 'replace', replace), self.assertRaises(OSError):
            reset.restore_stopped(self.server)
        self.assertEqual((self.world / 'region/r.0.0.mca').read_bytes(), b'destroyed terrain')
        self.assertTrue((self.world / 'playerdata/owner.dat').is_file())

    def test_level_name_cannot_escape_the_server(self):
        (self.server / 'server.properties').write_text('level-name=../other\n')
        with self.assertRaises(ValueError):
            reset.restore_stopped(self.server)

    def test_baseline_is_not_silently_replaced(self):
        with self.assertRaises(FileExistsError):
            reset.capture_baseline(self.server)

    def test_active_server_blocks_the_reset(self):
        self.guard.stop()
        with patch.object(reset, 'acquire_lock', return_value=None):
            with self.assertRaises(RuntimeError):
                reset.restore_stopped(self.server)
        self.assertEqual((self.world / 'region/r.0.0.mca').read_bytes(), b'destroyed terrain')
        self.guard.start()


if __name__ == '__main__':
    unittest.main()
