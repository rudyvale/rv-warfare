$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Stop-Server.ps1')
. (Join-Path $PSScriptRoot 'Porthole-Host.ps1')
$lock = Enter-RvPortholeLock $PSScriptRoot
try {
$stateFile = Join-Path $PSScriptRoot 'porthole-state.json'
if (Test-Path -LiteralPath $stateFile) {
    $state = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $target = if ($state.exposeTarget) { [string]$state.exposeTarget } else { 'tcp/127.0.0.1:' + [int]$state.port }
    $process = Get-RvOwnedPorthole $state $target
    if ($process) { Stop-Process -Id $process.ProcessId -ErrorAction Stop }
}
} finally { $lock.ReleaseMutex(); $lock.Dispose() }
