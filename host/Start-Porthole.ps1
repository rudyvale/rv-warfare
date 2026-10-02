$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$stateFile = Join-Path $root 'porthole-state.json'
$eventsFile = Join-Path $root 'porthole-events.jsonl'
$executable = 'C:\Program Files (x86)\Steam\steamapps\common\porthole\porthole-gnu.exe'
function Save-PortholeState($Process) {
    $started = [DateTimeOffset]$Process.CreationDate
    $state = [ordered]@{pid=$Process.ProcessId;port=25565;state='running';startedAt=$started.ToUnixTimeMilliseconds()/1000.0;ready=$false;code='';peerTarget=''}
    $portReady = $false
    $sessionReady = $false
    if ((Test-Path -LiteralPath $eventsFile) -and (Get-Item -LiteralPath $eventsFile).LastWriteTimeUtc -ge $started.UtcDateTime.AddSeconds(-2)) {
        foreach ($line in (Get-Content -LiteralPath $eventsFile -Encoding UTF8)) {
            try { $event = $line | ConvertFrom-Json } catch { continue }
            if ($event.event -eq 'static_code' -and $event.code -match '^[A-Za-z0-9]{4,16}$') { $state.code = ([string]$event.code).ToUpperInvariant() }
            elseif ($event.event -eq 'steam_id' -and ([string]$event.steam_id) -match '^[0-9]{17}$') { $state.peerTarget = 'peer:' + [string]$event.steam_id }
            elseif ($event.event -eq 'ready') { $sessionReady = $true }
            elseif ($event.event -eq 'port_accepted' -and $event.port -eq 25565 -and $event.proto -eq 'tcp') { $portReady = $true }
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
        if ($existing -and ($existing.ExecutablePath -ne $executable -or $existing.CommandLine -notmatch 'expose tcp/127\.0\.0\.1:25565')) { $existing = $null }
    } catch { $existing = $null }
}
if (-not $existing) {
    $env:SteamAppId = '4963920'
    $env:SteamGameId = '4963920'
    $process = Start-Process -FilePath $executable -ArgumentList 'expose','tcp/127.0.0.1:25565','--visibility','friends','--max-peers','8','--game-name','RV','--json' -WindowStyle Hidden -WorkingDirectory $root -RedirectStandardOutput $eventsFile -RedirectStandardError (Join-Path $root 'porthole-errors.log') -PassThru
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
