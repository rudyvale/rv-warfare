import importlib.util
import hashlib
import io
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import zipfile
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
import host_runtime


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'host' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = load_module('host_races_launcher', 'warfare-launcher.py')
runner = load_module('host_races_runner', 'run-server.py')


def make_launcher(folder):
    app = launcher.Launcher.__new__(launcher.Launcher)
    app.folder = folder
    app.server = {'state': 'running', 'ready': True}
    app.connection = {}
    app.server_job = None
    app.server_generation = 0
    app.server_operation_lock = threading.Lock()
    app.client_job = False
    app.client_running = False
    app.cancel_start = threading.Event()
    app.closed = threading.Event()
    app.events = queue.Queue()
    app.render = Mock()
    app.check_updates = Mock()
    app.window = SimpleNamespace(after=Mock(return_value='test-poll'))
    return app


class HostRaceTests(unittest.TestCase):
    def test_vendor_start_preserves_stopped_maintenance_for_addons_and_pending_profile(self):
        with tempfile.TemporaryDirectory(prefix='rv-host-maintenance-') as temporary:
            root = Path(temporary)
            (root / 'mods').mkdir()
            resource = 'assets/mcheli/textures/rv-test.txt'
            data = b'updated owned addon'
            jar = root / 'mods/mcheli-ce-1.5.1-rv.jar'
            with zipfile.ZipFile(jar, 'w') as archive:
                archive.writestr(resource, data)
            addon = root / 'mcheli_addons/default' / resource
            addon.parent.mkdir(parents=True)
            addon.write_bytes(b'old owned addon')
            host_runtime.write_json(root / 'rv-addon-assets.json', {'schema': 1, 'mcheliSha256': hashlib.sha256(jar.read_bytes()).hexdigest(), 'resources': {resource: hashlib.sha256(data).hexdigest()}})
            host_runtime.write_json(root / 'release.json', {'version': '1.2.0', 'vendorCatalogSha256': 'fixture'})
            host_runtime.write_json(root / 'launcher-settings.json', {'pendingServerProfile': 'balanced'})
            (root / 'server.properties').write_text('server-port=25565\nview-distance=4\n')
            process = SimpleNamespace(pid=43210, returncode=0, stdin=io.StringIO(), poll=Mock(return_value=0))
            def prepared(folder, pulse):
                self.assertEqual(addon.read_bytes(), data)
                self.assertIn('view-distance=6', (root / 'server.properties').read_text())
                self.assertFalse(pulse())
            with patch.object(runner, 'acquire_lock', return_value=object()), patch.object(runner, 'server_status', return_value={'state': 'stopped'}), patch.object(runner, 'java_arguments', return_value=(['fake-java'], 2)), patch.object(runner.socket, 'socket'), patch.object(runner, 'install_for_runner', side_effect=prepared), patch.object(runner.subprocess, 'Popen', return_value=process) as spawn, patch.object(runner.porthole, 'process_identity', return_value={'startedAt': 10}):
                runner.run(root)
            spawn.assert_called_once()
            self.assertEqual(host_runtime.read_json(root / 'server-state.json')['state'], 'stopped')

    def test_stop_waits_for_tunnel_and_rejects_old_completion(self):
        for phase_delivered in (False, True):
            with self.subTest(phase_delivered=phase_delivered), tempfile.TemporaryDirectory(prefix='vm-host-races-') as temporary:
                app = make_launcher(Path(temporary))
                tunnel_entered = threading.Event()
                release_tunnel = threading.Event()
                stop_entered = threading.Event()
                calls = []
                threads = []
                real_thread = threading.Thread

                def tracked_thread(*args, **kwargs):
                    thread = real_thread(*args, **kwargs)
                    threads.append(thread)
                    return thread

                def script(name, timeout=180):
                    if name == 'Start-Porthole.ps1':
                        calls.append('tunnel_started')
                        tunnel_entered.set()
                        if not release_tunnel.wait(3):
                            raise TimeoutError('Test did not release the simulated tunnel')
                        calls.append('tunnel_ready')
                    elif name == 'Stop-All.ps1':
                        calls.append('stop_started')
                        stop_entered.set()
                    else:
                        raise AssertionError('Unexpected script: ' + name)

                app.script = script
                with patch.object(launcher, 'server_status', return_value={'state': 'running', 'ready': True}), patch.object(launcher.threading, 'Thread', tracked_thread):
                    try:
                        app.run_action('start')
                        self.assertTrue(tunnel_entered.wait(2))
                        old_generation = app.server_generation
                        if phase_delivered:
                            app.poll()
                            self.assertEqual(app.server_job, 'tunnel')
                        app.run_action('stop')
                        self.assertEqual(app.server_job, 'stop')
                        self.assertTrue(app.cancel_start.is_set())
                        self.assertFalse(stop_entered.wait(0.1))
                    finally:
                        release_tunnel.set()
                        for thread in threads:
                            thread.join(3)
                    self.assertTrue(all(not thread.is_alive() for thread in threads))
                    self.assertTrue(stop_entered.is_set())
                    self.assertEqual(calls, ['tunnel_started', 'tunnel_ready', 'stop_started'])
                    app.poll()
                    self.assertEqual(app.status_key, 'stopped')
                    self.assertIsNone(app.server_job)
                    app.events.put(('phase', (old_generation, 'tunnel')))
                    app.events.put(('done', ('start', 'online', old_generation)))
                    app.poll()
                    self.assertEqual(app.status_key, 'stopped')
                    self.assertIsNone(app.server_job)

    @unittest.skipUnless(os.name == 'nt', 'Windows file sharing regression')
    def test_atomic_state_write_survives_a_concurrent_reader(self):
        with tempfile.TemporaryDirectory(prefix='vm-host-races-') as temporary:
            path = Path(temporary) / 'server-state.json'
            host_runtime.write_json(path, {'state': 'starting'})
            reader = path.open('r', encoding='utf-8')
            conflict_seen = threading.Event()
            errors = []
            real_replace = Path.replace

            def replace(source, target):
                try:
                    return real_replace(source, target)
                except PermissionError:
                    conflict_seen.set()
                    raise

            def write():
                try:
                    host_runtime.write_json(path, {'state': 'running', 'ready': True})
                except Exception as error:
                    errors.append(error)

            with patch.object(Path, 'replace', replace):
                worker = threading.Thread(target=write, daemon=True)
                worker.start()
                try:
                    self.assertTrue(conflict_seen.wait(2), 'The real Windows sharing conflict was not exercised')
                finally:
                    reader.close()
                    worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(host_runtime.read_json(path), {'state': 'running', 'ready': True})
            self.assertEqual(list(path.parent.glob('*.tmp')), [])

    def test_state_write_failure_does_not_skip_child_shutdown(self):
        with tempfile.TemporaryDirectory(prefix='vm-host-races-') as temporary:
            root = Path(temporary)
            process = SimpleNamespace(pid=43210, returncode=None, stdin=io.StringIO())
            process.poll = Mock(return_value=None)

            def wait(timeout):
                process.returncode = 0
                return 0

            process.wait = Mock(side_effect=wait)
            writes = 0

            def write_state(path, state):
                nonlocal writes
                writes += 1
                if writes > 1:
                    raise PermissionError('Simulated persistent state-file sharing conflict')
                host_runtime.write_json(path, state)

            with patch.object(runner, 'acquire_lock', return_value=object()), patch.object(runner, 'server_status', return_value={'state': 'stopped'}), patch.object(runner, 'java_arguments', return_value=(['fake-java'], 2)), patch.object(runner.socket, 'socket'), patch.object(runner.subprocess, 'Popen', return_value=process) as spawn, patch.object(runner.porthole, 'process_identity', return_value={'startedAt': 10}), patch.object(runner, 'write_json', side_effect=write_state):
                runner.run(root)
            spawn.assert_called_once()
            self.assertGreaterEqual(writes, 3)
            self.assertEqual(process.stdin.getvalue(), 'stop\n')
            process.wait.assert_called_once_with(timeout=120)

    def test_live_starting_java_prevents_duplicate_runner_launch(self):
        with tempfile.TemporaryDirectory(prefix='vm-host-races-') as temporary:
            root = Path(temporary)
            state_path = root / 'server-state.json'
            state = {'state': 'starting', 'ready': False, 'pid': 43210, 'processStartedAt': 10, 'updated': time.time() - 60}
            host_runtime.write_json(state_path, state)
            identity = {'executable': str(root / 'java.exe'), 'startedAt': 10}
            with patch.object(runner, 'acquire_lock', return_value=object()), patch.object(host_runtime.porthole, 'process_identity', return_value=identity), patch.object(runner, 'java_arguments', side_effect=AssertionError('Must preserve the existing Java process')) as arguments, patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('No real child may start')) as spawn:
                runner.run(root)
            arguments.assert_not_called()
            spawn.assert_not_called()
            self.assertEqual(host_runtime.read_json(state_path), state)


if __name__ == '__main__':
    unittest.main(verbosity=2)
