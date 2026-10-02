import argparse
import json
import os
from pathlib import Path
import subprocess


parser = argparse.ArgumentParser()
parser.add_argument('--helper', type=Path, required=True)
args = parser.parse_args()
source = args.helper.read_text(encoding='utf-8-sig')
first, body = source.split('\n', 1)
root = Path(__file__).resolve().parent / 'owner-connection'
root.mkdir(parents=True, exist_ok=True)
game = str(root / 'Client with spaces')
policy = {'nickname': 'Owner_1', 'serverPort': 25565, 'allowedGameDirs': [game]}
command = f'java.exe -cp libraries net.minecraft.launchwrapper.Launch --username Owner_1 --gameDir "{game}"'
connection = {'LocalAddress': '127.0.0.1', 'RemoteAddress': '127.0.0.1', 'OwningProcess': 41111}
process = {'Name': 'java.exe', 'CommandLine': command}
mocks = r'''
$case = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'case.json') -Raw -Encoding UTF8 | ConvertFrom-Json
function Get-NetTCPConnection {
    param($State,$LocalPort,$RemotePort,$ErrorAction)
    if ($State -ne 'Established' -or $LocalPort -ne 41000 -or $RemotePort -ne 25565) { throw 'Incorrect socket lookup' }
    if ($case.networkError) { throw 'Network lookup failed' }
    return $case.connections
}
function Get-CimInstance {
    param($ClassName,$Filter)
    if ($ClassName -ne 'Win32_Process' -or $Filter -ne 'ProcessId=41111') { throw 'Incorrect process lookup' }
    if ($case.processError) { throw 'Process lookup failed' }
    return $case.process
}
'''
cases = [
    ('local-client', True, {}),
    ('local-javaw', True, {'process': dict(process, Name='javaw.exe')}),
    ('porthole-forwarder', False, {'process': dict(process, Name='porthole-gnu.exe')}),
    ('remote-name-match', False, {'connections': [dict(connection, RemoteAddress='192.0.2.10')]}),
    ('untrusted-local-address', False, {'connections': [dict(connection, LocalAddress='192.0.2.11')]}),
    ('missing-socket', False, {'connections': []}),
    ('ambiguous-socket', False, {'connections': [connection, connection]}),
    ('missing-process', False, {'process': None}),
    ('wrong-java-program', False, {'process': dict(process, CommandLine=command.replace('net.minecraft.launchwrapper.Launch', 'Other.Main'))}),
    ('wrong-player', False, {'process': dict(process, CommandLine=command.replace('--username Owner_1', '--username Other_1'))}),
    ('wrong-directory', False, {'process': dict(process, CommandLine=command.replace(game, game + '-untrusted'))}),
    ('missing-game-directory', False, {'process': dict(process, CommandLine=command.split(' --gameDir')[0])}),
    ('network-query-failure', False, {'networkError': True}),
    ('process-query-failure', False, {'processError': True}),
    ('wrong-owner-request', False, {'nickname': 'Other_1'}),
    ('case-changed-owner', False, {'nickname': 'owner_1'}),
    ('invalid-port', False, {'port': 0}),
]
shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
environment = {key: value for key, value in os.environ.items() if key.lower() != 'psmodulepath'}
script = root / 'Check-OwnerConnection.ps1'
script.write_text(first + '\n' + mocks + '\n' + body, encoding='utf-8-sig')
(root / 'vm-owner.json').write_text(json.dumps(policy), encoding='utf-8')
for name, expected, changes in cases:
    case = dict(connections=[connection], process=process)
    case.update(changes)
    (root / 'case.json').write_text(json.dumps(case), encoding='utf-8')
    result = subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-LocalPort', str(case.get('port', 41000)), '-Nickname', case.get('nickname', 'Owner_1')], env=environment, capture_output=True, timeout=10)
    output = result.stdout.decode('utf-8-sig', errors='replace').strip()
    assert result.returncode == 0 and output == str(expected).lower(), (name, result.returncode, output)
    print(name + ': PASS')
print(f'{len(cases)} owner connection boundary tests passed')
