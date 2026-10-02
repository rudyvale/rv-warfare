param([string]$Output)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
. (Join-Path $repo 'host\Porthole-Host.ps1')
if (-not $Output) { $Output = Join-Path $repo ('.local\rv-1.1.0\porthole-helper-' + [Guid]::NewGuid().ToString('N')) }
[IO.Directory]::CreateDirectory($Output) | Out-Null
$checks = [Collections.Generic.List[object]]::new()
function Assert-Rv($Condition,[string]$Name) {
    $checks.Add([pscustomobject]@{name=$Name;passed=[bool]$Condition})
    if (-not $Condition) { throw $Name }
    Write-Output ('PASS ' + $Name)
}
$statePath = Join-Path $Output 'state.json'
Write-RvPortholeState $statePath ([pscustomobject]@{state='running';ready=$false})
Write-RvPortholeState $statePath ([pscustomobject]@{state='running';ready=$true;reason='ready'})
$saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
Assert-Rv ($saved.ready -and $saved.reason -eq 'ready' -and @(Get-ChildItem -LiteralPath $Output -Filter '*.tmp').Count -eq 0) 'native atomic create and replacement'
$target = 'tcp/127.0.0.1:25565'
$started = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
$script:fixture = [pscustomobject]@{ProcessId=123;Name='porthole.exe';ExecutablePath='C:\QA\porthole.exe';CommandLine='"C:\QA\porthole.exe" expose "tcp/127.0.0.1:25565"';CreationDate=[DateTimeOffset]::FromUnixTimeMilliseconds([long]($started*1000)).UtcDateTime}
function Get-CimInstance { param($ClassName,$Filter,$ErrorAction) return $script:fixture }
$binding = [pscustomobject]@{state='running';pid=123;exposeTarget=$target;startedAt=$started;executable='C:\QA\porthole.exe'}
Assert-Rv ([bool](Get-RvOwnedPorthole $binding $target)) 'exact owned process accepted'
$script:fixture.Name = 'porthole-gnu.exe'
$script:fixture.ExecutablePath = 'C:\QA\porthole-gnu.exe'
$binding.executable = $script:fixture.ExecutablePath
Assert-Rv ([bool](Get-RvOwnedPorthole $binding $target)) 'GNU executable accepted with exact binding'
$script:fixture.CommandLine = 'C:\QA\porthole-gnu.exe expose tcp/127.0.0.1:255650'
Assert-Rv (-not (Get-RvOwnedPorthole $binding $target)) 'target prefix never authorizes stopping another exposure'
$script:fixture.CommandLine = 'C:\QA\porthole-gnu.exe expose tcp/127.0.0.1:25565'
$binding.startedAt = $started - 1
Assert-Rv (-not (Get-RvOwnedPorthole $binding $target)) 'PID reuse rejected'
$binding.startedAt = $started
$binding.executable = 'C:\Other\porthole-gnu.exe'
Assert-Rv (-not (Get-RvOwnedPorthole $binding $target)) 'different executable path rejected'
Remove-Item Function:\Get-CimInstance
$mutex = Enter-RvPortholeLock $Output
try {
    $helper = (Join-Path $repo 'host\Porthole-Host.ps1').Replace("'","''")
    $lockRoot = $Output.Replace("'","''")
    $childPath = Join-Path $Output 'contender.ps1'
    $resultPath = Join-Path $Output 'contender.txt'
    $literalResult = $resultPath.Replace("'","''")
    $child = ". '$helper'`ntry { `$mutex = Enter-RvPortholeLock '$lockRoot'; try { [IO.File]::WriteAllText('$literalResult','unexpected') } finally { `$mutex.ReleaseMutex(); `$mutex.Dispose() } } catch { [IO.File]::WriteAllText('$literalResult','blocked') }"
    [IO.File]::WriteAllText($childPath,$child,[Text.UTF8Encoding]::new($false))
    $shell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $process = Start-Process -FilePath $shell -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',('"' + $childPath + '"')) -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(10000)) { throw 'Owned lock contender timed out' }
    Assert-Rv (([IO.File]::ReadAllText($resultPath)) -eq 'blocked') 'native cross-process lock serializes recovery'
} finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
$mutex = Enter-RvPortholeLock $Output
try { Assert-Rv $true 'released lock can be acquired again' } finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
[IO.File]::WriteAllText((Join-Path $Output 'report.json'),([pscustomobject]@{passed=$true;checks=$checks} | ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
