import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('porthole_host', ROOT / 'host/porthole-status.py')
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)


class HostReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rv-porthole-host-')
        self.root = Path(self.temp.name)
        self.started = time.time() - 1
        self.state = {'pid': 123, 'startedAt': self.started, 'state': 'running', 'port': 25565, 'exposeTarget': 'tcp/127.0.0.1:25565'}
        self.identity = {'executable': 'C:/Steam/porthole.exe', 'startedAt': self.started}
        self.events = [{'event': 'steam_id', 'steam_id': '76561198000000001'}, {'event': 'static_code', 'code': 'QA12345'}, {'event': 'lobby_ready', 'lobby_id': '109775240000000001'}]

    def tearDown(self):
        self.temp.cleanup()

    def read(self):
        (self.root / 'porthole-state.json').write_text(json.dumps(self.state))
        (self.root / 'porthole-events.jsonl').write_text('\n'.join(json.dumps(item) for item in self.events) + '\n')
        return status.read_status(self.root, lambda pid: self.identity)

    def test_current_host_lobby_is_ready_without_guest_approval(self):
        self.assertTrue(self.read()['ready'])
        self.assertEqual(self.read()['peerTarget'], 'peer:76561198000000001')

    def test_lobby_requires_exact_configured_tcp_exposure(self):
        self.state['exposeTarget'] = 'tcp/127.0.0.1:25566'
        self.assertFalse(self.read()['ready'])
        self.state.pop('exposeTarget')
        self.assertFalse(self.read()['ready'])

    def test_guest_id_and_roster_do_not_replace_host_identity(self):
        self.events += [{'event': 'peer_connected', 'steam_id': '76561198000000002'}, {'event': 'roster', 'members': ['76561198000000002']}]
        self.assertEqual(self.read()['peerTarget'], 'peer:76561198000000001')

    def test_lobby_needs_valid_identity_and_code(self):
        self.events[2]['lobby_id'] = '0'
        self.assertFalse(self.read()['ready'])
        self.events[2]['lobby_id'] = '109775240000000001'
        self.events = [item for item in self.events if item['event'] != 'steam_id']
        self.assertFalse(self.read()['ready'])

    def test_legacy_ready_and_port_accepted_still_work(self):
        self.state.pop('exposeTarget')
        self.events = [{'event': 'ready'}, {'event': 'port_accepted', 'port': 25565, 'proto': 'tcp'}]
        self.assertTrue(self.read()['ready'])

    def test_both_real_binary_names_and_stale_pid(self):
        self.identity['executable'] = 'C:/Steam/porthole-gnu.exe'
        self.assertTrue(self.read()['ready'])
        self.identity['startedAt'] += 5
        self.assertEqual(self.read(), {})


if __name__ == '__main__':
    unittest.main()
