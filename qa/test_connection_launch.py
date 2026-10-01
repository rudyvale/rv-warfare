from pathlib import Path
import json
import os
import shutil
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'qa/connection-launch'
PS = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
ENV = {key: value for key, value in os.environ.items() if key.lower() != 'psmodulepath'}
ENV['VM_SKIP_UPDATE_CHECK'] = '1'
source = (ROOT / 'src/Play-Warfare.ps1').read_text(encoding='utf-8-sig')
start = source.index('function Test-GameServer(')
end = source.index('\ntry {', start)
source = source[:start] + '''function Test-GameServer([string]$Address,[int]$ServerPort) {
    if($scenario.stale -and $ServerPort -eq 30111){return $null}
    return [PSCustomObject]@{version=[PSCustomObject]@{protocol=340};modinfo=[PSCustomObject]@{modList=@([PSCustomObject]@{modid='mcheli'},[PSCustomObject]@{modid='techguns'})}}
}
''' + source[end:]
source = source.replace('.AddMinutes(10)', '.AddMilliseconds(200)').replace('Start-Sleep -Seconds 2', 'Start-Sleep -Milliseconds 10')
mocks = r'''
$scenario=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'scenario.json') -Raw | ConvertFrom-Json
$mockSteam=Join-Path $PSScriptRoot 'steam'
$mockPorthole=Join-Path $mockSteam 'steamapps\common\porthole\porthole-gnu.exe'
function Get-CimInstance { param($ClassName,$Filter,$ErrorAction)
    if($ClassName -eq 'Win32_ComputerSystem'){return [PSCustomObject]@{TotalPhysicalMemory=16GB}}
    return @()
}
function Get-ItemProperty { param($LiteralPath,$ErrorAction)
    if($scenario.mode -eq 'direct'){throw 'Steam was accessed in direct mode'}
    return [PSCustomObject]@{SteamPath=$mockSteam}
}
function New-FakeProcess([int]$Id,[string]$Path,[bool]$Exited=$false) {
    $process=[PSCustomObject]@{Id=$Id;Path=$Path;StartTime=[datetime]::SpecifyKind([datetime]'2026-10-02T01:00:00',[DateTimeKind]::Utc);HasExited=$Exited}
    $process|Add-Member ScriptMethod Kill {Add-Content -LiteralPath (Join-Path $PSScriptRoot 'killed.txt') -Value $this.Id}
    $process|Add-Member ScriptMethod WaitForExit {param($Timeout) return $this.HasExited}
    return $process
}
function Get-Process { param([string]$Name,[int]$Id,$ErrorAction)
    if($Name -eq 'steam'){
        if($scenario.coldSteam -and -not $script:steamStarted){return $null}
        return [PSCustomObject]@{Name='steam'}
    }
    if($Id -eq 41111){return (New-FakeProcess 41111 $mockPorthole)}
    throw 'Unexpected process lookup'
}
function Start-Process { param($FilePath,$ArgumentList,$WindowStyle,$WorkingDirectory,$RedirectStandardOutput,$RedirectStandardError,[switch]$PassThru)
    if($FilePath -eq (Join-Path $mockSteam 'steam.exe')){$script:steamStarted=$true;Set-Content -LiteralPath (Join-Path $PSScriptRoot 'steam-started.txt') -Value 'started';return}
    if($FilePath -eq 'steam://install/4963920'){
        Set-Content -LiteralPath (Join-Path $PSScriptRoot 'install-requested.txt') -Value 'requested'
        if(-not $scenario.timeout){
            Set-Content -LiteralPath (Join-Path $mockSteam 'steamapps\appmanifest_4963920.acf') -Value '"AppState" { "StateFlags" "4" "installdir" "porthole" }'
            Set-Content -LiteralPath $mockPorthole -Value 'fixture'
            Set-Content -LiteralPath (Join-Path (Split-Path -Parent $mockPorthole) 'steam_api64.dll') -Value 'fixture'
        }
        return
    }
    if($FilePath -eq $mockPorthole){
        [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'tunnel-args.json'),(ConvertTo-Json -InputObject $ArgumentList))
        return (New-FakeProcess 42222 $mockPorthole ([bool]$scenario.fail))
    }
    if($FilePath.EndsWith('java.exe')){
        [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'java-args.txt'),[string]$ArgumentList)
        return (New-FakeProcess 43333 $FilePath)
    }
    throw 'Unexpected process launch'
}
'''


def run(name, mode='porthole', target='NEWCODE', port=25570, old=None, stale=False, fail=False, prepare=False, missing=False, partial=False, cold_steam=False, timeout=False):
    game = BASE / name
    game.mkdir(parents=True, exist_ok=True)
    for filename in ['java-args.txt', 'tunnel-args.json', 'killed.txt', 'tunnel-state.json', 'install-requested.txt', 'steam-started.txt']:
        (game / filename).unlink(missing_ok=True)
    for path in ['runtime/bin/java.exe', 'natives/lwjgl64.dll', 'steam/steamapps/common/porthole/porthole-gnu.exe', 'steam/steamapps/common/porthole/steam_api64.dll']:
        item = game / path
        item.parent.mkdir(parents=True, exist_ok=True)
        item.write_bytes(b'fixture')
    manifest = game / 'steam/steamapps/appmanifest_4963920.acf'
    manifest.write_text('"AppState" { "StateFlags" "' + ('1026' if partial else '4') + '" "installdir" "porthole" }')
    if missing:
        manifest.unlink()
        (game / 'steam/steamapps/common/porthole/porthole-gnu.exe').unlink()
    settings = dict(nickname='QAPlayer', language='en', connectionMode=mode, connectionTarget=target, serverPort=port)
    (game / 'warfare-settings.json').write_text(json.dumps(settings))
    (game / 'installer-files.json').write_text(json.dumps(dict(classpath=[], mainClass='fixture', assetIndex='1.12')))
    (game / 'scenario.json').write_text(json.dumps(dict(mode=mode, stale=stale, fail=fail, coldSteam=cold_steam, timeout=timeout)))
    if old:
        ticks = str(int((datetime(2026, 10, 2, 1) - datetime(1, 1, 1)).total_seconds()) * 10_000_000)
        prior = dict(pid=41111, started=ticks, port=30111, target=old[0], remotePort=old[1])
        (game / 'tunnel-state.json').write_text(json.dumps(prior))
    for filename in ['Warfare-Connection.ps1', 'Warfare-Updates.ps1']:
        shutil.copyfile(ROOT / 'src' / filename, game / filename)
    first, rest = source.split('\n', 1)
    (game / 'Play-Warfare.ps1').write_text(first + '\n' + mocks + '\n' + rest, encoding='utf-8-sig')
    command = [str(PS), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(game / 'Play-Warfare.ps1'), '-StatusFile', str(game / 'status.json')]
    if prepare:
        command.append('-Prepare')
    result = subprocess.run(command, env=ENV, capture_output=True, timeout=15)
    status = json.loads((game / 'status.json').read_text(encoding='utf-8-sig'))
    expected_error = fail or (not target and not prepare) or timeout
    assert (result.returncode != 0) == expected_error, (name, result.returncode, status, result.stderr.decode(errors='replace'))
    java = (game / 'java-args.txt').read_text() if (game / 'java-args.txt').exists() else ''
    args = json.loads((game / 'tunnel-args.json').read_text()) if (game / 'tunnel-args.json').exists() else None
    killed = (game / 'killed.txt').read_text(encoding='utf-8-sig') if (game / 'killed.txt').exists() else ''
    if expected_error:
        assert status['state'] == 'error' and not java, (name, status, java)
    elif prepare:
        assert status['state'] == 'ready' and not java and not args, (name, status, java, args)
    elif mode == 'direct':
        assert not args and f'--server {target}' in java and f'--port {port}' in java, (name, args, java)
    else:
        reuse = bool(old and old == (target, port) and not stale)
        if reuse:
            assert not args and not killed and '--port 30111' in java, (name, args, killed, java)
        else:
            assert args[0:2] == ['connect', target], (name, args)
            assert args[3] == f'tcp/{port}' and args[5].startswith(f'{port}:'), (name, args)
            local = int(args[5].split(':')[1])
            assert 0 < local < 65536 and f'--port {local}' in java
            if old:
                assert '41111' in killed, (name, killed)
    if missing or partial:
        assert (game / 'install-requested.txt').exists(), name
    if cold_steam:
        assert (game / 'steam-started.txt').exists(), name
    print(name + ': PASS')


run('direct-no-Steam', mode='direct', target='changed.example', port=25590)
run('first-tunnel')
run('reuse-matching-tunnel', old=('NEWCODE', 25570))
run('changed-target', old=('OLDCODE', 25570))
run('changed-remote-port', old=('NEWCODE', 25565))
run('stale-tunnel', old=('NEWCODE', 25570), stale=True)
run('empty-target', target='')
run('failed-tunnel-no-game', fail=True)
run('prepare-existing', prepare=True)
run('prepare-clean-Steam-only', prepare=True, missing=True, cold_steam=True)
run('prepare-before-server-selection', target='', prepare=True, missing=True, cold_steam=True)
run('prepare-incomplete-install', prepare=True, partial=True)
run('play-installs-Porthole', missing=True)
run('prepare-timeout-no-game', prepare=True, missing=True, timeout=True)
run('prepare-direct-no-Steam', mode='direct', target='changed.example', prepare=True)
run('prepare-direct-empty-target', mode='direct', target='', prepare=True)
print('16 connection launch integration tests passed')
