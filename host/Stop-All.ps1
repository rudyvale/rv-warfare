$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Stop-Server.ps1')
$stateFile = Join-Path $PSScriptRoot 'porthole-state.json'
if (Test-Path -LiteralPath $stateFile) {
    $state = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + [int]$state.pid) -ErrorAction SilentlyContinue
    if ($process -and $process.Name -eq 'porthole-gnu.exe' -and $process.CommandLine -match 'expose tcp/127\.0\.0\.1:25565') {
        $started = ([DateTimeOffset]$process.CreationDate).ToUnixTimeMilliseconds() / 1000.0
        if ([Math]::Abs($started - [double]$state.startedAt) -lt 2) { Stop-Process -Id $state.pid -ErrorAction Stop }
    }
}
