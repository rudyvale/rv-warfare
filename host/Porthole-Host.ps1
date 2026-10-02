if ($PSVersionTable.PSEdition -eq 'Desktop') {
    $env:PSModulePath = $PSHOME + '\Modules;' + $env:PSModulePath
    Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
}
function Enter-RvPortholeLock([string]$Root) {
    $bytes = [Text.Encoding]::UTF8.GetBytes([IO.Path]::GetFullPath($Root).ToLowerInvariant())
    $hash = [Security.Cryptography.SHA256]::Create()
    try { $key = ([BitConverter]::ToString($hash.ComputeHash($bytes))).Replace('-','').Substring(0,24) } finally { $hash.Dispose() }
    $mutex = [Threading.Mutex]::new($false, ('Local\RV-Porthole-' + $key))
    try { $acquired = $mutex.WaitOne(4000) } catch [Threading.AbandonedMutexException] { $acquired = $true }
    if (-not $acquired) { $mutex.Dispose(); throw 'Porthole recovery is already running. Wait, then retry.' }
    return $mutex
}
function Write-RvPortholeState([string]$Path, $State) {
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($temporary, ($State | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
    try {
        if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary,$Path,[NullString]::Value) } else { [IO.File]::Move($temporary,$Path) }
    } finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
}
function Get-RvOwnedPorthole($State, [string]$Target) {
    if (-not $State -or $State.state -ne 'running' -or $State.exposeTarget -ne $Target) { return $null }
    $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + [int]$State.pid) -ErrorAction SilentlyContinue
    $exposure = '(?:^|\s)expose\s+(?:"' + [regex]::Escape($Target) + '"|' + [regex]::Escape($Target) + ')(?:\s|$)'
    if (-not $process -or $process.Name -notin @('porthole.exe','porthole-gnu.exe') -or -not $process.ExecutablePath -or -not $process.CommandLine -or $process.CommandLine -notmatch $exposure) { return $null }
    if ($State.executable -and [IO.Path]::GetFullPath($process.ExecutablePath) -ne [IO.Path]::GetFullPath([string]$State.executable)) { return $null }
    $started = ([DateTimeOffset]$process.CreationDate).ToUnixTimeMilliseconds() / 1000.0
    if ([Math]::Abs($started - [double]$State.startedAt) -gt 0.05) { return $null }
    return $process
}
