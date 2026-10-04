import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PS = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
ENV = {key: value for key, value in os.environ.items() if key.lower() != 'psmodulepath'}
ENV['VM_SKIP_UPDATE_CHECK'] = '1'
SOURCE = (ROOT / 'src/Play-Warfare.ps1').read_text(encoding='utf-8-sig')
test_start = SOURCE.index('function Test-GameServer(')
test_end = SOURCE.index('\ntry {', test_start)
SOURCE = SOURCE[:test_start] + "function Test-GameServer([string]$Address,[int]$ServerPort) {\n    Add-Content -LiteralPath (Join-Path $PSScriptRoot 'probe.txt') -Value ($Address+':'+$ServerPort)\n    return [PSCustomObject]@{version=[PSCustomObject]@{protocol=340};modinfo=[PSCustomObject]@{modList=@([PSCustomObject]@{modid='mcheli';version='fixture'},[PSCustomObject]@{modid='techguns';version='fixture'})}}\n}\n" + SOURCE[test_end:]

MOCKS = r'''
function Get-CimInstance {
    param($ClassName,$Filter,$ErrorAction)
    if($ClassName -eq 'Win32_ComputerSystem'){return [PSCustomObject]@{TotalPhysicalMemory=16GB}}
    if($ClassName -eq 'Win32_Processor'){return [PSCustomObject]@{NumberOfLogicalProcessors=8}}
    return @()
}
function Get-ItemProperty {
    param($LiteralPath,$ErrorAction)
    Set-Content -LiteralPath (Join-Path $PSScriptRoot 'steam-accessed.txt') -Value $LiteralPath
    throw 'Steam registry accessed in a route that should not use Steam.'
}
function Start-Process {
    param($FilePath,$ArgumentList,$WindowStyle,$WorkingDirectory,$RedirectStandardOutput,$RedirectStandardError,[switch]$PassThru)
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'launch.json'),(@{file=$FilePath;arguments=[string]$ArgumentList}|ConvertTo-Json -Compress))
    $process=[PSCustomObject]@{Id=41123;StartTime=[DateTime]::UtcNow;HasExited=$false}
    $process|Add-Member ScriptMethod WaitForExit {param($Timeout)return $false}
    return $process
}
'''


def run_case(parent, label, play_mode, selected_mode, selected_target='', selected_port=25565, prepare=False):
    game = parent / label
    game.mkdir()
    for relative in ('runtime/bin/java.exe', 'natives/lwjgl64.dll'):
        path = game / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture')
    (game / 'warfare-settings.json').write_text(json.dumps({
        'nickname': 'ModeQA',
        'language': 'en',
        'memoryMB': 2048,
        'connectionMode': 'direct',
        'connectionTarget': 'old-flat-address.example',
        'serverPort': 25570,
        'playMode': selected_mode,
        'playProfiles': {
            'friends': {'connectionMode': 'direct', 'connectionTarget': selected_target if selected_mode == 'friends' else '', 'serverPort': selected_port},
            'owner': {'connectionMode': 'direct', 'connectionTarget': selected_target if selected_mode == 'owner' else '', 'serverPort': selected_port},
            'host': {'port': 25565},
        },
    }))
    (game / 'installer-files.json').write_text(json.dumps({'classpath': [], 'mainClass': 'fixture', 'assetIndex': '1.12'}))
    (game / 'release.json').write_text(json.dumps({'version': '1.0.0'}))
    (game / 'scenario.json').write_text('{}')
    for filename in ('Warfare-Connection.ps1', 'Warfare-PlayModes.ps1', 'Warfare-ClientMods.ps1', 'Warfare-Performance.ps1', 'Warfare-Ambience.ps1', 'Warfare-Updates.ps1'):
        shutil.copyfile(ROOT / 'src' / filename, game / filename)
    before, after = SOURCE.split('\ntry {', 1)
    patched = before + '\n' + MOCKS + '\ntry {' + after
    script = game / 'Play-Warfare.ps1'
    script.write_text(patched, encoding='utf-8-sig')
    command = [str(PS), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-PlayMode', play_mode, '-StatusFile', str(game / 'status.json')]
    if prepare:
        command.append('-Prepare')
    result = subprocess.run(command, env=ENV, capture_output=True, timeout=20)
    stdout = result.stdout.decode(errors='replace')
    stderr = result.stderr.decode(errors='replace')
    if not (game / 'status.json').exists():
        raise AssertionError((label, result.returncode, stdout, stderr))
    status = json.loads((game / 'status.json').read_text(encoding='utf-8-sig'))
    assert result.returncode == 0, (label, result.returncode, status, stdout, stderr)
    assert not (game / 'steam-accessed.txt').exists(), (label, 'Steam registry was accessed')
    launch = json.loads((game / 'launch.json').read_text()) if (game / 'launch.json').exists() else None
    probe = (game / 'probe.txt').read_text() if (game / 'probe.txt').exists() else ''
    if play_mode == 'local':
        if prepare:
            assert status['state'] == 'ready' and launch is None and not probe, (label, status, launch, probe)
        else:
            assert status['state'] == 'running' and launch is not None, (label, status, launch)
            assert '--server' not in launch['arguments'] and '--port' not in launch['arguments'], (label, launch)
            assert not probe, (label, 'Local mode probed a remote server')
    else:
        assert status['state'] == 'running' and launch is not None, (label, status, launch)
        assert f'--server {selected_target}' in launch['arguments'] and f'--port {selected_port}' in launch['arguments'], (label, launch)
        assert probe.strip() == f'{selected_target}:{selected_port}', (label, probe)
    print(label + ': PASS')


with tempfile.TemporaryDirectory(prefix='rv-play-modes-') as temporary:
    base = Path(temporary)
    run_case(base, 'local-with-package-address', 'local', 'local')
    run_case(base, 'local-prepare-no-steam', 'local', 'local', prepare=True)
    run_case(base, 'friends-own-profile', 'friends', 'friends', 'friends.example', 25571)
    run_case(base, 'owner-own-profile', 'owner', 'owner', 'owner.example', 25572)
print('Local launch isolation and separate Friends/Owner destinations: PASS')
