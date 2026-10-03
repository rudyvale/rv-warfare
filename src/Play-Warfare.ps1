param([string]$Server, [int]$Port, [switch]$SkipTunnel, [switch]$Check, [switch]$Prepare, [string]$StatusFile)
$ErrorActionPreference = 'Stop'
$gameRoot = $PSScriptRoot
. (Join-Path $gameRoot 'Warfare-Connection.ps1')
. (Join-Path $gameRoot 'Warfare-Performance.ps1')
if(Test-Path -LiteralPath (Join-Path $gameRoot 'Warfare-ClientControls.ps1')){. (Join-Path $gameRoot 'Warfare-ClientControls.ps1')}
. (Join-Path $gameRoot 'Warfare-Updates.ps1')
if (-not $Check -and -not $Prepare) { Start-VmUpdateCheck $gameRoot $gameRoot }
$script:language = 'ru'
$tunnelStarted = $null
$launchLock = $null
$installGuard = $null
$script:failureReason = 'failed'
function Text([string]$Ru, [string]$En) { if ($script:language -eq 'en') { return $En }; return $Ru }
function Set-Status([string]$State, [string]$Message, [string]$Reason) {
    Write-Output $Message
    if ($StatusFile) {
        $data = @{state=$State; reason=$Reason; message=$Message; time=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Compress
        $temp = $StatusFile + '.tmp'
        [IO.File]::WriteAllText($temp, $data, [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temp -Destination $StatusFile -Force
    }
}
function Quote-Argument([string]$Value) {
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    return '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}
function Read-VarInt([IO.Stream]$Stream,[DateTime]$Deadline=[DateTime]::MaxValue) {
    $result = 0
    for ($i=0; $i -lt 5; $i++) {
        if($Deadline -ne [DateTime]::MaxValue){
            $remaining=[int]($Deadline-[DateTime]::UtcNow).TotalMilliseconds
            if($remaining -le 0){throw 'Server response timed out.'}
            if($Stream.CanTimeout){$Stream.ReadTimeout=[Math]::Min(1500,$remaining)}
        }
        $value = $Stream.ReadByte()
        if ($value -lt 0) { throw 'Connection closed.' }
        $result = $result -bor (($value -band 127) -shl (7*$i))
        if (($value -band 128) -eq 0) { return $result }
    }
    throw 'Invalid server response.'
}
function VarInt([int]$Value) {
    $bytes = [Collections.Generic.List[byte]]::new()
    do {
        $part = [byte]($Value -band 127)
        $Value = $Value -shr 7
        if ($Value -gt 0) { $part = $part -bor 128 }
        $bytes.Add($part)
    } while ($Value -gt 0)
    return $bytes.ToArray()
}
function Find-Porthole([string]$SteamRoot) {
    $libraries = @($SteamRoot)
    $libraryFile = Join-Path $SteamRoot 'steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $libraryFile) {
        foreach ($match in [regex]::Matches([IO.File]::ReadAllText($libraryFile), '"path"\s+"([^"]+)"')) { $libraries += $match.Groups[1].Value.Replace('\\','\') }
    }
    foreach ($library in $libraries | Select-Object -Unique) {
        $appManifest = Join-Path $library 'steamapps\appmanifest_4963920.acf'
        if (-not (Test-Path -LiteralPath $appManifest)) { continue }
        try { $manifestText = Get-Content -LiteralPath $appManifest -Raw -Encoding UTF8 } catch { continue }
        $stateMatch = [regex]::Match($manifestText, '"StateFlags"\s+"([0-9]+)"')
        if (-not $stateMatch.Success -or [int]$stateMatch.Groups[1].Value -ne 4) { continue }
        $folderMatch = [regex]::Match($manifestText, '"installdir"\s+"([^"\\/]+)"')
        $folder = if ($folderMatch.Success) { $folderMatch.Groups[1].Value } else { 'porthole' }
        $appRoot = Join-Path $library ('steamapps\common\' + $folder)
        if (-not (Test-Path -LiteralPath (Join-Path $appRoot 'steam_api64.dll'))) { continue }
        foreach ($name in @('porthole-gnu.exe','porthole.exe')) {
            $candidate = Join-Path $appRoot $name
            if (Test-Path -LiteralPath $candidate) { return $candidate }
        }
    }
    return $null
}
function Initialize-WarfareSteam {
    $steamSettings = Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue
    if (-not $steamSettings -or -not $steamSettings.SteamPath) { throw (Text 'Установи Steam и войди в свой аккаунт.' 'Install Steam and sign in.') }
    $steamRoot = $steamSettings.SteamPath
    if (-not (Get-Process steam -ErrorAction SilentlyContinue)) {
        Set-Status 'preparing' (Text 'Запуск Steam…' 'Starting Steam…') | Out-Host
        Start-Process -FilePath (Join-Path $steamRoot 'steam.exe') -WindowStyle Hidden
        $steamDeadline = [DateTime]::UtcNow.AddSeconds(60)
        while (-not (Get-Process steam -ErrorAction SilentlyContinue) -and [DateTime]::UtcNow -lt $steamDeadline) { Start-Sleep -Milliseconds 500 }
        if (-not (Get-Process steam -ErrorAction SilentlyContinue)) { throw (Text 'Не удалось запустить Steam. Открой его и войди в аккаунт.' 'Could not start Steam. Open it and sign in.') }
    }
    $porthole = Find-Porthole $steamRoot
    if (-not $porthole) {
        Set-Status 'preparing' (Text 'Подтверди установку Porthole в Steam. После загрузки RV продолжит сам.' 'Confirm the Porthole installation in Steam. RV will continue after the download.') | Out-Host
        Start-Process 'steam://install/4963920'
        $installDeadline = [DateTime]::UtcNow.AddMinutes(10)
        while (-not $porthole -and [DateTime]::UtcNow -lt $installDeadline) {
            Start-Sleep -Seconds 2
            $porthole = Find-Porthole $steamRoot
        }
        if (-not $porthole) { throw (Text 'Porthole ещё не установлен. Заверши загрузку в Steam и нажми «Играть».' 'Porthole is not installed yet. Finish the download in Steam and click Play.') }
    }
    return $porthole
}
function Get-WarfareSteamIdentity([string]$SteamExecutable) {
    $process = @(Get-Process steam -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -eq $SteamExecutable } | Select-Object -First 1)
    if (-not $process.Count) { return $null }
    return [PSCustomObject]@{pid=$process[0].Id;started=$process[0].StartTime.ToUniversalTime().Ticks.ToString();path=$process[0].Path}
}
function Get-WarfareTunnelFailure([string]$Root, [string]$Fallback='failed') {
    $parts = [Collections.Generic.List[string]]::new()
    foreach ($name in @('porthole-errors.log','porthole-events.jsonl')) {
        $path = Join-Path $Root $name
        if (-not (Test-Path -LiteralPath $path)) { continue }
        try {
            foreach ($line in @(Get-Content -LiteralPath $path -Tail 32 -Encoding UTF8)) {
                if ($line.Length -gt 16384) { continue }
                if ($name -eq 'porthole-errors.log') { $parts.Add($line) }
                else {
                    try {
                        $event = $line | ConvertFrom-Json
                        if ($event.event -in @('error','failed','steam_error','connection_failed') -or $event.type -in @('error','failed','steam_error','connection_failed') -or $event.error) { $parts.Add($line) }
                    } catch { }
                }
            }
        } catch { }
    }
    $diagnostic = $parts -join "`n"
    if ($diagnostic -match '(?i)(same\s+Steam\s+account|host and peer are the same|same_account)') { return 'same_account' }
    if ($diagnostic -match '(?i)(not\s+logged\s+in|not\s+signed\s+in|Steam\s+(?:client\s+)?(?:is\s+)?not\s+running|steam_offline|SteamAPI_Init\s+(?:failed|returned false))') { return 'steam_offline' }
    if ($diagnostic -match '(?i)(steam_changed|Steam\s+(?:client\s+)?(?:restarted|changed))') { return 'steam_changed' }
    if ($diagnostic -match '(?i)(timed?\s*out|timeout|peer\s+(?:is\s+)?offline|host\s+(?:is\s+)?offline)') { return 'timeout' }
    return $Fallback
}
function Stop-WarfareOwnedTunnel($Process, [string]$Executable, [string]$Started) {
    if (-not $Process) { return $true }
    try {
        $current = Get-Process -Id $Process.Id -ErrorAction SilentlyContinue
        if(-not $current){return $true}
        if ($current.Path -eq $Executable -and $current.StartTime.ToUniversalTime().Ticks.ToString() -eq $Started) {
            if (-not $current.HasExited) { $current.Kill(); return $current.WaitForExit(3000) }
        }
        return $true
    } catch { return $false }
}
function Test-GameServer([string]$Address, [int]$ServerPort) {
    $probeDeadline=[DateTime]::UtcNow.AddSeconds(3)
    $socket = if ([Net.Sockets.Socket]::OSSupportsIPv6) {
        $client = [Net.Sockets.TcpClient]::new([Net.Sockets.AddressFamily]::InterNetworkV6)
        $client.Client.DualMode = $true
        $client
    } else { [Net.Sockets.TcpClient]::new() }
    try {
        $task = $socket.ConnectAsync($Address, $ServerPort)
        if (-not $task.Wait(700) -or -not $socket.Connected) { return $null }
        $stream = $socket.GetStream()
        $stream.ReadTimeout = 1500
        $stream.WriteTimeout = 1500
        $hostBytes = [Text.Encoding]::UTF8.GetBytes($Address)
        [byte[]]$handshake = @(0) + @(VarInt 340) + @(VarInt $hostBytes.Length) + @($hostBytes) + @([byte]($ServerPort -shr 8), [byte]($ServerPort -band 255), 1)
        [byte[]]$packet = @(VarInt $handshake.Length) + @($handshake) + @(1, 0)
        $stream.Write($packet, 0, $packet.Length)
        $packetLength = Read-VarInt $stream $probeDeadline
        if ($packetLength -le 0 -or $packetLength -gt 1048576) { return $null }
        if ((Read-VarInt $stream $probeDeadline) -ne 0) { return $null }
        $length = Read-VarInt $stream $probeDeadline
        if ($length -le 0 -or $length -ge $packetLength) { return $null }
        $bytes = New-Object byte[] $length
        $offset = 0
        while ($offset -lt $length) {
            $remaining=[int]($probeDeadline-[DateTime]::UtcNow).TotalMilliseconds
            if($remaining -le 0){return $null}
            $stream.ReadTimeout=[Math]::Min(1500,$remaining)
            $count = $stream.Read($bytes, $offset, $length-$offset)
            if ($count -le 0) { return $null }
            $offset += $count
        }
        return ([Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json)
    } catch { return $null } finally { $socket.Dispose() }
}
try {
    if (-not $Check) {
        try { $installGuard = [IO.File]::Open((Join-Path $gameRoot '.install.lock'), 'OpenOrCreate', 'ReadWrite', 'None') } catch { throw (Text 'Идёт установка или другой запуск. Дождись завершения.' 'An installation or another launch is in progress. Please wait.') }
    }
    $settings = Get-Content -LiteralPath (Join-Path $gameRoot 'warfare-settings.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $script:language = $settings.language
    if ($settings.nickname -notmatch '^[A-Za-z0-9_]{3,16}$') { throw (Text 'Укажи ник: от 3 до 16 латинских букв, цифр или _.' 'Enter a nickname: 3 to 16 letters, digits or _.') }
    $downloads = Get-Content -LiteralPath (Join-Path $gameRoot 'installer-files.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $java = Join-Path $gameRoot 'runtime\bin\java.exe'
    foreach ($file in @($downloads.classpath) + @('runtime/bin/java.exe','natives/lwjgl64.dll')) {
        $full = [IO.Path]::GetFullPath((Join-Path $gameRoot $file))
        if (-not $full.StartsWith($gameRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $full -PathType Leaf)) {
            throw (Text ('Не хватает файла ' + $file + '. Запусти установку ещё раз.') ('Missing file ' + $file + '. Run the installer again.'))
        }
    }
    Assert-WarfareUniqueMods $gameRoot
    if ($Check) {
        $installed = Get-Content -LiteralPath (Join-Path $gameRoot 'installed-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($entry in $installed.managedFiles | Where-Object { $_.path -notlike 'config/*' -and $_.path -cne 'ModularWarfare/mod_config.json' }) {
            $full = [IO.Path]::GetFullPath((Join-Path $gameRoot $entry.path))
            if (-not $full.StartsWith($gameRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid installed file path.' }
            if ($entry.existingOnly -and -not (Test-Path -LiteralPath (Join-Path $gameRoot 'mcheli_addons\default') -PathType Container)) { continue }
            if (-not (Test-Path -LiteralPath $full -PathType Leaf) -or (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash -ne $entry.sha256) {
                throw (Text ('Файл повреждён или отсутствует: ' + $entry.path + '. Нажми «Установить».') ('File missing or damaged: ' + $entry.path + '. Click Install.'))
            }
        }
        Set-Status 'ready' 'Launch files OK'; exit 0
    }
    try { $launchLock = [IO.File]::Open((Join-Path $gameRoot '.launch.lock'), 'OpenOrCreate', 'ReadWrite', 'None') } catch { throw (Text 'Запуск уже выполняется. Подожди.' 'A launch is already in progress. Please wait.') }
    $activeGame = Get-CimInstance Win32_Process -Filter "Name='java.exe' OR Name='javaw.exe'" -ErrorAction SilentlyContinue | Where-Object { Test-WarfareGameProcess $_.CommandLine $gameRoot }
    if ($activeGame) { Set-Status 'running' (Text 'RV уже запущен. Переключись в окно игры.' 'RV is already running. Switch to the game window.'); exit 0 }
    if(Get-Command Initialize-WarfareClientControls -ErrorAction SilentlyContinue){$null=Initialize-WarfareClientControls -Root $gameRoot}
    $requiredMods=if(-not $Prepare){Get-WarfareRequiredMods $gameRoot}else{$null}
    $defaults = $null
    $defaultsFile = Join-Path $gameRoot 'server-defaults.json'
    if (Test-Path -LiteralPath $defaultsFile) { $defaults = Get-Content -LiteralPath $defaultsFile -Raw -Encoding UTF8 | ConvertFrom-Json }
    $connection = Get-WarfareConnection $settings $defaults
    if (-not $SkipTunnel -and (-not $Prepare -or $connection.connectionTarget)) { $connection = ConvertTo-WarfareConnection $connection.connectionMode $connection.connectionTarget $connection.serverPort }
    if (-not $Server) { $Server = if ($SkipTunnel) { '127.0.0.1' } else { $connection.connectionTarget } }
    if (-not $Port) { $Port = [int]$connection.serverPort }
    if ($Port -lt 1 -or $Port -gt 65535) { throw (Text 'Неверный порт сервера.' 'Invalid server port.') }
    if (-not $SkipTunnel -and $connection.connectionMode -eq 'porthole') {
        $remotePort = [int]$connection.serverPort
        $target = $connection.connectionTarget
        $porthole = Initialize-WarfareSteam
        if ($Prepare) { Set-Status 'ready' (Text 'Готово к запуску.' 'Ready to play.'); exit 0 }
        $tunnelFile = Join-Path $gameRoot 'tunnel-state.json'
        $existing = $null
        $steamSettings = Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue
        $steamExecutable = Join-Path $steamSettings.SteamPath 'steam.exe'
        $steamIdentity = Get-WarfareSteamIdentity $steamExecutable
        if (-not $steamIdentity) { throw 'steam_offline' }
        if (Test-Path -LiteralPath $tunnelFile) {
            $cleanupFailed=$false
            try {
                $oldTunnel = Get-Content -LiteralPath $tunnelFile -Raw -Encoding UTF8 | ConvertFrom-Json
                $process = Get-Process -Id $oldTunnel.pid -ErrorAction Stop
                if ($process.Path -eq $porthole -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $oldTunnel.started) {
                    $oldTarget = if ($oldTunnel.target) { $oldTunnel.target } else { $oldTunnel.code }
                    $oldRemotePort = if ($oldTunnel.remotePort) { [int]$oldTunnel.remotePort } else { 25565 }
                    $sameSteam = $oldTunnel.steamPid -eq $steamIdentity.pid -and $oldTunnel.steamStarted -eq $steamIdentity.started -and $oldTunnel.steamPath -eq $steamIdentity.path
                    if ($sameSteam -and $oldTarget -eq $target -and $oldRemotePort -eq $remotePort -and (Test-GameServer '127.0.0.1' ([int]$oldTunnel.port))) { $existing = $process; $Port = [int]$oldTunnel.port }
                    else { $cleanupFailed=-not (Stop-WarfareOwnedTunnel $process $porthole $oldTunnel.started) }
                }
            } catch { }
            if($cleanupFailed){throw 'failed'}
        }
        $Server = '127.0.0.1'
        $deadline = [DateTime]::UtcNow.AddSeconds(45)
        $response = $null
        for ($attempt=1; $attempt -le 2 -and [DateTime]::UtcNow -lt $deadline; $attempt++) {
            if (-not $existing) {
                $steamIdentity = Get-WarfareSteamIdentity $steamExecutable
                if (-not $steamIdentity) { throw 'steam_offline' }
                $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
                try { $listener.Start(); $Port=$listener.LocalEndpoint.Port } finally { $listener.Stop() }
                $env:SteamAppId='4963920'; $env:SteamGameId='4963920'
                $args=@('connect',$target,'--auto-approve-ports',('tcp/'+$remotePort),'--remap',($remotePort.ToString()+':'+$Port),'--bind','127.0.0.1','--json')
                $tunnelStarted=Start-Process -FilePath $porthole -ArgumentList $args -WindowStyle Hidden -WorkingDirectory (Split-Path -Parent $porthole) -RedirectStandardOutput (Join-Path $gameRoot 'porthole-events.jsonl') -RedirectStandardError (Join-Path $gameRoot 'porthole-errors.log') -PassThru
                $tunnelStamp=$tunnelStarted.StartTime.ToUniversalTime().Ticks.ToString()
                @{pid=$tunnelStarted.Id;started=$tunnelStamp;path=$porthole;port=$Port;target=$target;remotePort=$remotePort;steamPid=$steamIdentity.pid;steamStarted=$steamIdentity.started;steamPath=$steamIdentity.path} | ConvertTo-Json | Set-Content -LiteralPath $tunnelFile -Encoding UTF8
            }
            Set-Status 'connecting' $(if($attempt -eq 1){Text 'Подключение к серверу…' 'Connecting to server…'}else{Text 'Повторное подключение…' 'Reconnecting…'}) 'connecting'
            $attemptDeadline = if($attempt -eq 1 -and -not $existing){[DateTime]::UtcNow.AddSeconds(20)}else{$deadline}
            if($attemptDeadline -gt $deadline){$attemptDeadline=$deadline}
            $reason='timeout'
            while ([DateTime]::UtcNow -lt $attemptDeadline) {
                $currentSteam=Get-WarfareSteamIdentity $steamExecutable
                if(-not $currentSteam){$reason='steam_offline';break}
                if($currentSteam.pid -ne $steamIdentity.pid -or $currentSteam.started -ne $steamIdentity.started){$reason='steam_changed';break}
                if ($tunnelStarted -and $tunnelStarted.HasExited) { $reason=Get-WarfareTunnelFailure $gameRoot; break }
                $response=Test-GameServer $Server $Port
                if($response){break}
                $diagnostic=Get-WarfareTunnelFailure $gameRoot ''
                if($diagnostic -in @('same_account','steam_offline','steam_changed')){$reason=$diagnostic;break}
                Start-Sleep -Milliseconds 500
            }
            if($response){break}
            if($tunnelStarted){if(-not (Stop-WarfareOwnedTunnel $tunnelStarted $porthole $tunnelStamp)){throw 'failed'}; $tunnelStarted=$null}
            if($existing){if(-not (Stop-WarfareOwnedTunnel $existing $porthole $oldTunnel.started)){throw 'failed'}; $existing=$null}
            $script:failureReason=$reason
            if($reason -in @('same_account','steam_offline') -or $attempt -eq 2 -or [DateTime]::UtcNow -ge $deadline){throw $reason}
        }
        if(-not $response){throw 'timeout'}
    } elseif (-not $Prepare) {
        Set-Status 'connecting' (Text 'Проверка адреса сервера…' 'Checking server address…')
        $directDeadline=[DateTime]::UtcNow.AddSeconds(45)
        do{
            $response = Test-GameServer $Server $Port
            if($response){break}
            if([DateTime]::UtcNow -lt $directDeadline){Start-Sleep -Milliseconds 500}
        }while([DateTime]::UtcNow -lt $directDeadline)
        if (-not $response) { throw 'server_offline' }
    }
    if ($Prepare) { Set-Status 'ready' (Text 'Готово к запуску.' 'Ready to play.'); exit 0 }
    Assert-WarfareServerCompatibility $response $requiredMods
    $md5 = [Security.Cryptography.MD5]::Create()
    try { $digest = $md5.ComputeHash([Text.Encoding]::UTF8.GetBytes('OfflinePlayer:' + $settings.nickname)) } finally { $md5.Dispose() }
    $digest[6] = ($digest[6] -band 15) -bor 48
    $digest[8] = ($digest[8] -band 63) -bor 128
    $uuid = -join ($digest | ForEach-Object { $_.ToString('x2') })
    $memoryMB = Get-WarfareHeapMB $settings
    $classpath = @($downloads.classpath | ForEach-Object { Join-Path $gameRoot $_ }) -join ';'
    $arguments = @('-Dfile.encoding=UTF-8','-Dlog4j2.formatMsgNoLookups=true','-Xms512M',('-Xmx' + $memoryMB + 'M'),('-Djava.library.path=' + (Join-Path $gameRoot 'natives')),'-Dminecraft.launcher.brand=Warfare','-Dminecraft.launcher.version=1.1','-cp',$classpath,$downloads.mainClass,'--username',$settings.nickname,'--version','Warfare-1.12.2','--gameDir',$gameRoot,'--assetsDir',(Join-Path $gameRoot 'assets'),'--assetIndex',$downloads.assetIndex,'--uuid',$uuid,'--accessToken','0','--userType','legacy','--tweakClass','net.minecraftforge.fml.common.launcher.FMLTweaker','--versionType','Forge','--server',$Server,'--port',$Port.ToString())
    $logging = Join-Path $gameRoot 'assets\log_configs\client-1.12.xml'
    if (Test-Path -LiteralPath $logging) { $arguments = @('-Dlog4j.configurationFile=' + $logging) + $arguments }
    $argumentLine = ($arguments | ForEach-Object { Quote-Argument $_ }) -join ' '
    Set-Status 'starting' (Text 'Запуск Minecraft…' 'Starting Minecraft…')
    $game = Start-Process -FilePath $java -ArgumentList $argumentLine -WindowStyle Hidden -WorkingDirectory $gameRoot -RedirectStandardOutput (Join-Path $gameRoot 'client-console.log') -RedirectStandardError (Join-Path $gameRoot 'client-errors.log') -PassThru
    @{pid=$game.Id; started=$game.StartTime.ToUniversalTime().Ticks.ToString()} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $gameRoot 'game-state.json') -Encoding UTF8
    if ($game.WaitForExit(5000)) { throw (Text 'Игра закрылась при запуске. Открой «Журнал» или запусти установку повторно.' 'The game closed during startup. Open Log or run the installer again.') }
    Set-Status 'running' (Text 'Minecraft запущен.' 'Minecraft started.')
} catch {
    if ($tunnelStarted) { [void](Stop-WarfareOwnedTunnel $tunnelStarted $porthole $tunnelStamp) }
    $code=$_.Exception.Message
    if($code -in @('same_account','steam_offline','steam_changed','timeout','failed','server_offline','incompatible_version','incompatible_mods','incompatible_mod_version','connection_package')){$script:failureReason=$code}
    if($code -like 'RV_MEMORY_*'){$script:failureReason=$code.Substring(3).ToLowerInvariant()}
    if($code.StartsWith('duplicate_mods:')){$script:failureReason='duplicate_mods'}
    Set-Status 'error' (Get-WarfareConnectionError (Get-WarfarePreferenceError $code $script:language) $script:language) $script:failureReason
    exit 1
} finally { if ($launchLock) { $launchLock.Dispose() }; if ($installGuard) { $installGuard.Dispose() } }
