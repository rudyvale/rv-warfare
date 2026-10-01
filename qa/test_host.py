import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
import host_runtime as runtime
spec = importlib.util.spec_from_file_location('host_ui', ROOT / 'host/warfare-launcher.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vm-host-')
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_memory_leaves_room_for_client(self):
        self.assertEqual(runtime.memory_limit({}, 8), 2)
        self.assertEqual(runtime.memory_limit({}, 16), 3)
        self.assertEqual(runtime.memory_limit({}, 32), 4)
        self.assertEqual(runtime.memory_limit({'serverMemoryGB': 99}, 8), 4)
        self.assertEqual(runtime.memory_limit({'serverMemoryGB': 'bad'}, 32), 4)

    def test_stale_pid_is_not_a_running_server(self):
        runtime.write_json(self.root / 'server-state.json', {'state': 'running', 'ready': True, 'pid': 55, 'processStartedAt': 10})
        self.assertEqual(runtime.server_status(self.root, lambda pid: None)['state'], 'stopped')
        wrong_process = lambda pid: {'executable': 'java.exe', 'startedAt': 20}
        self.assertFalse(runtime.server_status(self.root, wrong_process)['ready'])

    def test_broken_state_does_not_break_monitor(self):
        (self.root / 'server-state.json').write_text('{')
        self.assertEqual(runtime.server_status(self.root)['state'], 'stopped')

    def test_stop_waits_and_does_not_kill_on_timeout(self):
        state = {'state': 'running', 'ready': True, 'pid': 55, 'processStartedAt': 10}
        runtime.write_json(self.root / 'server-state.json', state)
        probe = lambda pid: {'executable': 'java.exe', 'startedAt': 10}
        with self.assertRaises(TimeoutError):
            runtime.request_stop(self.root, timeout=0.05, probe=probe)
        self.assertEqual((self.root / 'commands.txt').read_text(), 'stop\n')
        self.assertEqual(runtime.read_json(self.root / 'server-state.json')['state'], 'running')

    def test_stop_returns_after_server_exits(self):
        runtime.write_json(self.root / 'server-state.json', {'state': 'running', 'pid': 55})
        calls = []
        def probe(pid):
            calls.append(pid)
            return {'executable': 'java.exe', 'startedAt': 10} if len(calls) < 3 else None
        runtime.request_stop(self.root, timeout=2, probe=probe)
        self.assertEqual((self.root / 'commands.txt').read_text(), 'stop\n')

    def test_porthole_log_is_incremental_and_resets_on_truncation(self):
        runtime.write_json(self.root / 'porthole-state.json', {'pid': 9, 'state': 'running', 'startedAt': 10, 'port': 25565})
        probe = lambda pid: {'executable': 'porthole-gnu.exe', 'startedAt': 10}
        events = self.root / 'porthole-events.jsonl'
        events.write_text('{"event":"static_code","code":"ABCD"}\n{"event":"ready"}\n')
        first = runtime.porthole.read_status(self.root, probe)
        self.assertFalse(first['ready'])
        with events.open('a') as stream:
            stream.write('{"event":"port_accepted","port":25565,"proto":"tcp"}\n')
        self.assertTrue(runtime.porthole.read_status(self.root, probe)['ready'])
        offset = runtime.porthole._sessions[str(self.root.resolve())]['offset']
        self.assertEqual(runtime.porthole.read_status(self.root, probe)['code'], 'ABCD')
        self.assertEqual(runtime.porthole._sessions[str(self.root.resolve())]['offset'], offset)
        events.write_text('{"event":"ready"}\n')
        reset = runtime.porthole.read_status(self.root, probe)
        self.assertFalse(reset['ready'])
        self.assertEqual(reset['code'], '')


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vm-ui-')
        self.root = Path(self.temp.name)
        self.window = tk.Tk()
        self.window.withdraw()
        self.app = ui.Launcher(self.window, self.root, monitor=False)
        self.invoked = []
        self.app.script = lambda name, timeout=180: self.invoked.append(name)
        self.app.check_updates = lambda: None

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def pump(self, seconds=0.15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.window.update()
            time.sleep(0.005)

    def test_play_does_not_start_server(self):
        self.app.server = {'state': 'running', 'ready': True}
        self.app.render()
        self.app.play_button.invoke()
        self.pump()
        self.assertEqual(self.invoked, ['Join-Server.ps1'])
        self.assertFalse(self.app.client_job)

    def test_no_play_when_server_is_off(self):
        self.app.play_button.invoke()
        self.pump()
        self.assertEqual(self.invoked, [])

    def test_start_does_not_launch_game(self):
        with patch.object(ui, 'server_status', return_value={'state': 'running', 'ready': True}):
            self.app.start_button.invoke()
            self.pump()
        self.assertEqual(self.invoked, ['Start-Porthole.ps1'])

    def test_stop_only_saves_and_stops(self):
        self.app.server = {'state': 'running', 'ready': True}
        self.app.render()
        self.app.stop_button.invoke()
        self.pump()
        self.assertEqual(self.invoked, ['Stop-All.ps1'])
        self.assertEqual(self.app.status_key, 'stopped')

    def test_long_action_keeps_ui_responsive_and_prevents_duplicate(self):
        block = threading.Event()
        def slow(name, timeout=180):
            self.invoked.append(name)
            block.wait(2)
        self.app.script = slow
        self.app.server = {'state': 'running', 'ready': True}
        self.app.render()
        self.app.play_button.invoke()
        self.app.play_button.invoke()
        ticks = []
        self.window.after(20, lambda: ticks.append(True))
        self.pump()
        self.assertTrue(ticks)
        self.assertEqual(self.invoked, ['Join-Server.ps1'])
        block.set()
        self.pump()

    def test_update_disabled_never_spawns_network_worker(self):
        self.app.auto_check = False
        with patch.object(ui.subprocess, 'run', side_effect=AssertionError('network')):
            ui.Launcher.check_updates(self.app)
            self.pump()

    def test_layout_and_translations(self):
        self.window.deiconify()
        for width, height in [(800, 620), (1180, 760), (1920, 1080)]:
            self.window.geometry(f'{width}x{height}+0+0')
            for language in ('ru', 'en'):
                self.app.language = language
                self.app.translate()
                self.window.update()
                for widget in (self.app.play_button, self.app.start_button, self.app.stop_button, self.app.copy_button, self.app.log_button):
                    self.assertGreater(widget.winfo_width(), 50)
                    top = widget.winfo_rooty() - self.window.winfo_rooty()
                    left = widget.winfo_rootx() - self.window.winfo_rootx()
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(top + widget.winfo_height(), self.window.winfo_height())
                    self.assertGreaterEqual(left, 0)
                    self.assertLessEqual(left + widget.winfo_width(), self.window.winfo_width())


if __name__ == '__main__':
    unittest.main(verbosity=2)
