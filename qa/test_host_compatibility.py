import importlib.util
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rv_host_compatibility', ROOT / 'host/host_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def integer(value):
    result = bytearray()
    while True:
        byte = value & 127
        value >>= 7
        result.append(byte | (128 if value else 0))
        if not value:
            return bytes(result)


def response(mods=None, protocol=340):
    data = json.dumps({'version': {'protocol': protocol}, 'modinfo': {'modList': mods if mods is not None else [{'modid': 'mcheli', 'version': '1.5.1-rv-controls2'}, {'modid': 'techguns', 'version': '2.0.2.0'}]}}).encode()
    body = b'\x00' + integer(len(data)) + data
    return integer(len(body)) + body


class HostCompatibility(unittest.TestCase):
    def probe(self, packet, timeout=1, pause=0):
        errors = []
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            def serve():
                try:
                    with listener.accept()[0] as connection:
                        connection.settimeout(2)
                        connection.recv(1024)
                        time.sleep(pause)
                        connection.sendall(packet)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except BaseException as error:
                    errors.append(error)
            worker = threading.Thread(target=serve)
            worker.start()
            try:
                return runtime.local_mod_versions(port, timeout)
            finally:
                worker.join(3)
                self.assertFalse(worker.is_alive())
                self.assertEqual(errors, [])

    def test_real_loopback_frame_preserves_exact_versions(self):
        self.assertEqual(self.probe(response()), {'mcheli': '1.5.1-rv-controls2', 'techguns': '2.0.2.0'})

    def test_protocol_mismatch_rejected_before_game_launch(self):
        with self.assertRaises(runtime.CompatibilityError):
            self.probe(response(protocol=760))

    def test_declared_frame_cannot_read_outside_its_boundary(self):
        data = b'{"version":{"protocol":340}}'
        with self.assertRaises(ValueError):
            self.probe(b'\x02\x00' + integer(len(data)) + data)

    def test_trailing_bytes_and_invalid_varints_rejected(self):
        for packet in (b'\x05\x00\x02{}X', b'\x06\x00\x80\x80\x80\x80\x10', b'\x80\x80\x80\x80\x80'):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                self.probe(packet)

    def test_partial_frame_and_oversized_frame_rejected(self):
        for packet in (b'\x05\x00', integer(1048577)):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                self.probe(packet)

    def test_duplicate_or_malformed_mod_versions_rejected(self):
        for mods in ([{'modid': 'mcheli', 'version': 'a'}, {'modid': 'mcheli', 'version': 'b'}], [{'modid': 'mcheli', 'version': 2}], ['mcheli']):
            with self.subTest(mods=mods), self.assertRaises(ValueError):
                self.probe(response(mods=mods))

    def test_status_timeout_is_bounded(self):
        before = time.monotonic()
        with self.assertRaises(TimeoutError):
            self.probe(response(), timeout=0.1, pause=0.25)
        self.assertLess(time.monotonic() - before, 1)

    def test_missing_contract_and_different_bytes_are_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix='rv-host-versions-') as temporary:
            root = Path(temporary)
            host, game = root / 'host', root / 'game'
            for folder in (host, game):
                (folder / 'mods').mkdir(parents=True)
                for name in ('mcheli-ce-1.5.1-rv.jar', 'techguns-1.12.2-rv.jar'):
                    (folder / 'mods' / name).write_bytes(b'verified-same-artifact')
            with self.assertRaises(runtime.CompatibilityError):
                runtime.check_local_compatibility(host, game, 25565)
            required = {'mcheli': '1.5.1-rv-controls2', 'techguns': '2.0.2.0'}
            runtime.write_json(host / 'release.json', {'requiredMods': required})
            with patch.object(runtime, 'local_mod_versions', return_value=required):
                runtime.check_local_compatibility(host, game, 25565)
                (game / 'mods/mcheli-ce-1.5.1-rv.jar').write_bytes(b'wrong-build-same-version')
                with self.assertRaises(runtime.CompatibilityError):
                    runtime.check_local_compatibility(host, game, 25565)
            with patch.object(runtime, 'local_mod_versions', return_value={'mcheli': '1.5.1'}):
                with self.assertRaises(runtime.CompatibilityError):
                    runtime.check_local_compatibility(host, game, 25565)


if __name__ == '__main__':
    unittest.main()
