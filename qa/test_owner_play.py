import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
spec = importlib.util.spec_from_file_location('owner_play', ROOT / 'host/play-owner.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


class OwnerPlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.game = self.folder / 'game'
        self.game.mkdir()
        self.cancel = threading.Event()
        self.update = lambda message: None
        self.root_patch = patch.object(owner, 'ROOT', self.folder)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_ready_server_is_reused(self):
        with patch.object(owner, 'server_status', return_value={'state': 'running', 'ready': True, 'port': 25565}), patch.object(owner, 'run_hidden') as run:
            self.assertEqual(owner.wait_for_server(self.cancel, self.update), 25565)
            run.assert_not_called()

    def test_detached_worker_does_not_hold_launcher_output_open(self):
        command = 'import subprocess,sys; subprocess.Popen([sys.executable,"-c","import time;time.sleep(2)"],cwd=sys.prefix); print("OK")'
        started = time.monotonic()
        self.assertEqual(owner.run_hidden([sys.executable, '-c', command], timeout=1), 'OK')
        self.assertLess(time.monotonic() - started, 1.5)

    def test_cold_server_waits_for_world_before_returning(self):
        states = [{'state': 'stopped'}, {'state': 'starting', 'phase': 'world'}, {'state': 'running', 'ready': True, 'port': 25566}]
        with patch.object(owner, 'server_status', side_effect=states), patch.object(owner, 'run_hidden') as run, patch.object(self.cancel, 'wait', return_value=False):
            self.assertEqual(owner.wait_for_server(self.cancel, self.update), 25566)
            self.assertEqual(run.call_args.args[0][-1], 'start')

    def test_stopping_server_is_not_restarted(self):
        with patch.object(owner, 'server_status', return_value={'state': 'stopping'}), patch.object(owner, 'run_hidden') as run:
            with self.assertRaises(RuntimeError):
                owner.wait_for_server(self.cancel, self.update)
            run.assert_not_called()

    def test_failed_server_never_launches_client(self):
        with patch.object(owner, 'validate_owner', return_value='Owner'), patch.object(owner, 'server_status', side_effect=[{'state': 'stopped'}, {'state': 'failed'}]), patch.object(owner, 'run_hidden') as run:
            with self.assertRaises(RuntimeError):
                owner.play(self.game, self.cancel, self.update)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][-1], 'start')

    def test_friends_connection_precedes_local_owner_launch(self):
        order = []
        with patch.object(owner, 'validate_owner', return_value='Owner'), patch.object(owner, 'wait_for_server', return_value=25565), patch.object(owner, 'check_local_compatibility'), patch.object(owner, 'start_friends', side_effect=lambda *args: order.append('friends') or {'code': 'ABCD'}), patch.object(owner, 'run_hidden', side_effect=lambda args, **kwargs: order.append(args)):
            result = owner.play(self.game, self.cancel, self.update)
        self.assertEqual(order[0], 'friends')
        self.assertIn('-SkipTunnel', order[1])
        self.assertEqual(order[1][order[1].index('-Server') + 1], '127.0.0.1')
        self.assertTrue(result['friendsReady'])

    def test_cancelled_launch_does_not_open_friends_or_game(self):
        self.cancel.set()
        with patch.object(owner, 'validate_owner', return_value='Owner'), patch.object(owner, 'wait_for_server', return_value=25565), patch.object(owner, 'start_friends') as friends, patch.object(owner, 'run_hidden') as run:
            self.assertEqual(owner.play(self.game, self.cancel, self.update)['state'], 'cancelled')
            friends.assert_not_called()
            run.assert_not_called()

    def test_other_steam_account_is_rejected(self):
        (self.folder / 'owner-play-settings.json').write_text(json.dumps({'peerTarget': 'peer:11111111111111111'}))
        with patch.object(owner, 'run_hidden'), patch.object(owner.porthole, 'read_status', return_value={'ready': True, 'peerTarget': 'peer:22222222222222222'}):
            with self.assertRaises(ValueError):
                owner.start_friends(self.cancel, self.update)

    def test_steam_warmup_is_retried_automatically(self):
        with patch.object(owner, 'run_hidden', side_effect=[RuntimeError('Steam is starting'), 'OK']) as run, patch.object(owner.porthole, 'read_status', side_effect=[{}, {'ready': True, 'code': 'ABCD'}]), patch.object(self.cancel, 'wait', return_value=False):
            self.assertEqual(owner.start_friends(self.cancel, self.update)['code'], 'ABCD')
            self.assertEqual(run.call_count, 2)

    def test_ready_friend_connection_is_reused_without_starting_processes(self):
        with patch.object(owner.porthole, 'read_status', return_value={'ready': True, 'code': 'ABCD'}), patch.object(owner, 'run_hidden') as run:
            self.assertEqual(owner.start_friends(self.cancel, self.update)['code'], 'ABCD')
            run.assert_not_called()

    def test_owner_cannot_launch_from_an_untrusted_directory(self):
        (self.folder / 'vm-owner.json').write_text(json.dumps({'nickname': 'Owner', 'allowedGameDirs': [str(self.folder / 'trusted')]}))
        (self.game / 'warfare-settings.json').write_text(json.dumps({'nickname': 'Owner'}))
        with self.assertRaises(ValueError):
            owner.validate_owner(self.game)


if __name__ == '__main__':
    unittest.main()
