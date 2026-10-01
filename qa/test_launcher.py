import json
from pathlib import Path
import socket
import subprocess
import threading
import os

ROOT = Path(__file__).resolve().parents[1]
PS = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
source = (ROOT / 'src/Play-Warfare.ps1').read_text(encoding='utf-8-sig')
functions = source[:source.index('\ntry {')]
functions = functions.replace(". (Join-Path $gameRoot 'Warfare-Connection.ps1')", ". '" + str(ROOT / 'src/Warfare-Connection.ps1') + "'")
functions = functions.replace(". (Join-Path $gameRoot 'Warfare-Updates.ps1')", ". '" + str(ROOT / 'src/Warfare-Updates.ps1') + "'")


def varint(number):
    result = bytearray()
    while True:
        byte = number & 127
        number >>= 7
        result.append(byte | (128 if number else 0))
        if not number:
            return result


def receive_varint(stream):
    number = 0
    for i in range(5):
        byte = stream.recv(1)[0]
        number |= (byte & 127) << (i * 7)
        if not byte & 128:
            return number
    raise AssertionError('Malformed VarInt')


def run_case(label, payload, expect_response, address='127.0.0.1'):
    server = socket.socket(socket.AF_INET6 if ':' in address else socket.AF_INET)
    server.bind((address, 0))
    server.settimeout(4)
    server.listen()
    port = server.getsockname()[1]
    errors = []

    def serve():
        try:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(3)
                length = receive_varint(connection)
                body = bytearray()
                while len(body) < length:
                    body.extend(connection.recv(length - len(body)))
                host_bytes = address.encode()
                expected = b'\0' + varint(340) + varint(len(host_bytes)) + host_bytes + port.to_bytes(2, 'big') + b'\x01'
                assert body == expected, (body, expected)
                assert receive_varint(connection) == 1
                assert receive_varint(connection) == 0
                if payload:
                    for offset in range(0, len(payload), 7):
                        connection.sendall(payload[offset:offset + 7])
        except Exception as exc:
            errors.append(str(exc))
        finally:
            server.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    script = functions + f"\n$result=Test-GameServer '{address}' {port}\nif($result){{$result|ConvertTo-Json -Compress -Depth 8}}else{{'null'}}\n"
    path = ROOT / 'qa/probe-case.ps1'
    path.write_text(script, encoding='utf-8-sig')
    result = subprocess.run([str(PS), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(path)], capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    thread.join(4)
    assert not thread.is_alive(), label
    assert not errors, errors
    assert result.returncode == 0, result.stderr
    decoded = json.loads(result.stdout.decode('utf-8-sig').strip())
    assert bool(decoded) == expect_response, (label, decoded)
    print(label + ': PASS')


response = json.dumps({'version': {'name': '1.12.2', 'protocol': 340}, 'modinfo': {'modList': [{'modid': 'mcheli'}, {'modid': 'techguns'}]}}).encode()
packet = b'\0' + varint(len(response)) + response
run_case('fragmented Minecraft status with dynamic port', varint(len(packet)) + packet, True)
run_case('non-Minecraft listener rejected', b'HTTP/1.1 200 OK\r\n\r\n', False)
run_case('truncated response rejected', varint(len(packet)) + packet[:8], False)
run_case('closed socket rejected', b'', False)
with socket.socket(socket.AF_INET6) as ipv6_server:
    ipv6_server.bind(('::1', 0))
    ipv6_server.listen()
    with socket.socket(socket.AF_INET6) as ipv6_client:
        try:
            ipv6_client.connect(ipv6_server.getsockname())
        except OSError as error:
            if getattr(error, 'winerror', None) != 10013:
                raise
            print('IPv6 integration: SKIP (OS blocks IPv6 loopback, error 10013)')
        else:
            run_case('IPv6 Minecraft status with dynamic port', varint(len(packet)) + packet, True, '::1')
print('protocol integration tests complete')
