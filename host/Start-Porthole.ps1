$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
. (Join-Path $root 'Porthole-Host.ps1')
$lock = Enter-RvPortholeLock $root
try {
$stateFile = Join-Path $root 'porthole-state.json'
$eventsFile = Join-Path $root 'porthole-events.jsonl'
$steamSettings = Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue
if (-not $steamSettings -or -not $steamSettings.SteamPath) { throw 'Install Steam and sign in before starting Porthole.' }
$steamRoot = [IO.Path]::GetFullPath([string]$steamSettings.SteamPath)
if (-not (Get-Process steam -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath (Join-Path $steamRoot 'steam.exe') -ArgumentList '-silent' -WindowStyle Hidden | Out-Null
}
$steamDeadline = [DateTime]::UtcNow.AddSeconds(8)
do {
    $steamProcess = Get-Process steam -ErrorAction SilentlyContinue | Sort-Object StartTime | Select-Object -First 1
    if ($steamProcess) { break }
    Start-Sleep -Milliseconds 200
} while ([DateTime]::UtcNow -lt $steamDeadline)
if (-not $steamProcess) { throw 'Steam is starting. Wait for sign-in, then retry Porthole.' }
$steamStartedAt = ([DateTimeOffset]$steamProcess.StartTime).ToUnixTimeMilliseconds() / 1000.0
$libraries = @($steamRoot)
$libraryFile = Join-Path $steamRoot 'steamapps\libraryfolders.vdf'
if (Test-Path -LiteralPath $libraryFile) {
    foreach ($match in [regex]::Matches([IO.File]::ReadAllText($libraryFile), '"path"\s+"([^"]+)"')) { $libraries += $match.Groups[1].Value.Replace('\\','\') }
}
$executable = $null
foreach ($library in $libraries | Select-Object -Unique) {
    $manifest = Join-Path $library 'steamapps\appmanifest_4963920.acf'
    if (-not (Test-Path -LiteralPath $manifest)) { continue }
    $content = [IO.File]::ReadAllText($manifest)
    $installed = [regex]::Match($content, '"StateFlags"\s+"([0-9]+)"')
    $directory = [regex]::Match($content, '"installdir"\s+"([^"\\/]+)"')
    if (-not $installed.Success -or $installed.Groups[1].Value -ne '4' -or -not $directory.Success) { continue }
    $appRoot = Join-Path $library ('steamapps\common\' + $directory.Groups[1].Value)
    if (-not (Test-Path -LiteralPath (Join-Path $appRoot 'steam_api64.dll'))) { continue }
    foreach ($name in @('porthole.exe','porthole-gnu.exe')) {
        $candidate = Join-Path $appRoot $name
        if (Test-Path -LiteralPath $candidate) { $executable = $candidate; break }
    }
    if ($executable) { break }
}
if (-not $executable) { throw 'Install Porthole in Steam, then retry the connection.' }
$port = 25565
$serverProperties = Join-Path $root 'server.properties'
if (Test-Path -LiteralPath $serverProperties) {
    $value = [regex]::Match([IO.File]::ReadAllText($serverProperties), '(?m)^server-port=([0-9]+)\s*$')
    if ($value.Success) { $port = [int]$value.Groups[1].Value }
}
if ($port -lt 1 -or $port -gt 65535) { throw 'Invalid server port.' }
$target = 'tcp/127.0.0.1:' + $port
function Save-PortholeState($Process) {
    $started = [DateTimeOffset]$Process.CreationDate
    $state = [ordered]@{pid=$Process.ProcessId;port=$port;exposeTarget=$target;executable=$Process.ExecutablePath;state='running';startedAt=$started.ToUnixTimeMilliseconds()/1000.0;steamPid=$steamProcess.Id;steamStartedAt=$steamStartedAt}
    Write-RvPortholeState $stateFile $state
    $snapshot = & (Get-Command python.exe -ErrorAction Stop).Source (Join-Path $root 'porthole-status.py') --root $root
    if ($LASTEXITCODE -ne 0) { throw 'Could not read Porthole status.' }
    return $snapshot | ConvertFrom-Json
}
$existing = $null
if (Test-Path -LiteralPath $stateFile) {
    try {
        $previous = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        if ([string]$previous.exposeTarget -match '^tcp/127\.0\.0\.1:[0-9]{1,5}$') { $existing = Get-RvOwnedPorthole $previous ([string]$previous.exposeTarget) }
    } catch { $existing = $null }
}
if ($existing) {
    $snapshot = & (Get-Command python.exe -ErrorAction Stop).Source (Join-Path $root 'porthole-status.py') --root $root | ConvertFrom-Json
    $sameSteam = $previous.steamPid -eq $steamProcess.Id -and [Math]::Abs([double]$previous.steamStartedAt - $steamStartedAt) -lt 0.05
    if ($snapshot.ready -and $sameSteam -and $existing.ExecutablePath -eq $executable -and $previous.exposeTarget -eq $target) { exit 0 }
    Stop-Process -Id $existing.ProcessId -ErrorAction Stop
    Wait-Process -Id $existing.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
    $existing = $null
}
if (-not $existing) {
    $env:SteamAppId = '4963920'
    $env:SteamGameId = '4963920'
    $process = Start-Process -FilePath $executable -ArgumentList 'expose',$target,'--visibility','friends','--max-peers','8','--game-name','RV','--json' -WindowStyle Hidden -WorkingDirectory (Split-Path -Parent $executable) -RedirectStandardOutput $eventsFile -RedirectStandardError (Join-Path $root 'porthole-errors.log') -PassThru
    $existing = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $process.Id)
}
if (-not $existing) { throw 'Porthole failed to start.' }
$deadline = [DateTime]::UtcNow.AddSeconds(25)
while ([DateTime]::UtcNow -lt $deadline) {
    $snapshot = Save-PortholeState $existing
    if ($snapshot.ready -and $snapshot.code) { exit 0 }
    if ($snapshot.reason -in @('same_account','steam_offline','steam_changed','failed','timeout')) { throw ('Porthole connection: ' + $snapshot.reason + '. Retry Porthole after checking Steam.') }
    if (-not (Get-Process -Id $existing.ProcessId -ErrorAction SilentlyContinue)) { throw 'Porthole stopped. Details: porthole-errors.log' }
    Start-Sleep -Milliseconds 250
}
$failed = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
$failed | Add-Member -NotePropertyName failureReason -NotePropertyValue timeout -Force
Write-RvPortholeState $stateFile $failed
throw 'Porthole connection timed out. Sign in to Steam and retry Porthole; the local server is still available.'
} finally { $lock.ReleaseMutex(); $lock.Dispose() }
