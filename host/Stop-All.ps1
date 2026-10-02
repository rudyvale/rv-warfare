$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Stop-Server.ps1')
$stateFile = Join-Path $PSScriptRoot 'porthole-state.json'
if (Test-Path -LiteralPath $stateFile) {
    $state = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + [int]$state.pid) -ErrorAction SilentlyContinue
    $target = if ($state.exposeTarget) { [string]$state.exposeTarget } else { 'tcp/127.0.0.1:' + [int]$state.port }
    if ($process -and $process.Name -in @('porthole.exe','porthole-gnu.exe') -and $process.CommandLine.Contains('expose ' + $target)) {
        $started = ([DateTimeOffset]$process.CreationDate).ToUnixTimeMilliseconds() / 1000.0
        if ([Math]::Abs($started - [double]$state.startedAt) -lt 2) { Stop-Process -Id $state.pid -ErrorAction Stop }
    }
}
