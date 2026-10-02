$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$stateFile = Join-Path $root 'porthole-state.json'
$eventsFile = Join-Path $root 'porthole-events.jsonl'
$steamSettings = Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue
if (-not $steamSettings -or -not $steamSettings.SteamPath) { throw 'Install Steam and sign in before starting Porthole.' }
$steamRoot = [IO.Path]::GetFullPath([string]$steamSettings.SteamPath)
if (-not (Get-Process steam -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath (Join-Path $steamRoot 'steam.exe') -ArgumentList '-silent' -WindowStyle Hidden | Out-Null
}
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
    $state = [ordered]@{pid=$Process.ProcessId;port=$port;exposeTarget=$target;state='running';startedAt=$started.ToUnixTimeMilliseconds()/1000.0;ready=$false;code='';peerTarget=''}
    $portReady = $false
    $sessionReady = $false
    if ((Test-Path -LiteralPath $eventsFile) -and (Get-Item -LiteralPath $eventsFile).LastWriteTimeUtc -ge $started.UtcDateTime.AddSeconds(-2)) {
        foreach ($line in (Get-Content -LiteralPath $eventsFile -Encoding UTF8)) {
            try { $event = $line | ConvertFrom-Json } catch { continue }
            if ($event.event -eq 'static_code' -and $event.code -match '^[A-Za-z0-9]{4,16}$') { $state.code = ([string]$event.code).ToUpperInvariant() }
            elseif ($event.event -eq 'steam_id' -and ([string]$event.steam_id) -match '^[0-9]{17}$') { $state.peerTarget = 'peer:' + [string]$event.steam_id }
            elseif ($event.event -eq 'ready') { $sessionReady = $true }
            elseif ($event.event -eq 'lobby_ready' -and ([string]$event.lobby_id) -match '^[1-9][0-9]{0,19}$') { $sessionReady = $true; $portReady = $true }
            elseif ($event.event -eq 'port_accepted' -and $event.port -eq $port -and $event.proto -eq 'tcp') { $portReady = $true }
        }
    }
    $state.ready = $sessionReady -and $portReady
    [IO.File]::WriteAllText($stateFile, ($state | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
    return $state
}
$existing = $null
if (Test-Path -LiteralPath $stateFile) {
    try {
        $previous = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
        $existing = Get-CimInstance Win32_Process -Filter ("ProcessId=" + [int]$previous.pid) -ErrorAction SilentlyContinue
        if ($existing -and ($existing.ExecutablePath -ne $executable -or -not $existing.CommandLine.Contains('expose ' + $target))) { $existing = $null }
    } catch { $existing = $null }
}
if (-not $existing) {
    $env:SteamAppId = '4963920'
    $env:SteamGameId = '4963920'
    $process = Start-Process -FilePath $executable -ArgumentList 'expose',$target,'--visibility','friends','--max-peers','8','--game-name','RV','--json' -WindowStyle Hidden -WorkingDirectory (Split-Path -Parent $executable) -RedirectStandardOutput $eventsFile -RedirectStandardError (Join-Path $root 'porthole-errors.log') -PassThru
    $existing = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $process.Id)
}
if (-not $existing) { throw 'Porthole failed to start.' }
for ($attempt = 0; $attempt -lt 200; $attempt++) {
    $snapshot = Save-PortholeState $existing
    if ($snapshot.ready -and $snapshot.code) { exit 0 }
    if (-not (Get-Process -Id $existing.ProcessId -ErrorAction SilentlyContinue)) { throw 'Porthole stopped. Details: porthole-errors.log' }
    Start-Sleep -Milliseconds 100
}
throw 'Porthole is not ready. Details: porthole-errors.log'
