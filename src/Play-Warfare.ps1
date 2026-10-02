param([string]$Server, [int]$Port, [switch]$SkipTunnel, [switch]$Check, [switch]$Prepare, [string]$StatusFile)
$ErrorActionPreference = 'Stop'
$gameRoot = $PSScriptRoot
. (Join-Path $gameRoot 'Warfare-Connection.ps1')
. (Join-Path $gameRoot 'Warfare-Updates.ps1')
if (-not $Check -and -not $Prepare) { Start-VmUpdateCheck $gameRoot $gameRoot }
$script:language = 'ru'
$tunnelStarted = $null
$launchLock = $null
$installGuard = $null
function Text([string]$Ru, [string]$En) { if ($script:language -eq 'en') { return $En }; return $Ru }
function Set-Status([string]$State, [string]$Message) {
    Write-Output $Message
    if ($StatusFile) {
        $data = @{state=$State; message=$Message; time=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Compress
        $temp = $StatusFile + '.tmp'
        [IO.File]::WriteAllText($temp, $data, [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temp -Destination $StatusFile -Force
    }
}
function Quote-Argument([string]$Value) {
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    return '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}
function Read-VarInt([IO.Stream]$Stream) {
    $result = 0
    for ($i=0; $i -lt 5; $i++) {
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
function Test-GameServer([string]$Address, [int]$ServerPort) {
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
        $packetLength = Read-VarInt $stream
        if ($packetLength -le 0 -or $packetLength -gt 1048576) { return $null }
        if ((Read-VarInt $stream) -ne 0) { return $null }
        $length = Read-VarInt $stream
        if ($length -le 0 -or $length -ge $packetLength) { return $null }
        $bytes = New-Object byte[] $length
        $offset = 0
        while ($offset -lt $length) {
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
    if ($Check) {
        $installed = Get-Content -LiteralPath (Join-Path $gameRoot 'installed-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($entry in $installed.managedFiles | Where-Object { $_.path -notlike 'config/*' }) {
            $full = [IO.Path]::GetFullPath((Join-Path $gameRoot $entry.path))
            if (-not $full.StartsWith($gameRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid installed file path.' }
            if ($entry.existingOnly -and -not (Test-Path -LiteralPath $full)) { continue }
            if (-not (Test-Path -LiteralPath $full -PathType Leaf) -or (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash -ne $entry.sha256) {
                throw (Text ('Файл повреждён или отсутствует: ' + $entry.path + '. Нажми «Установить».') ('File missing or damaged: ' + $entry.path + '. Click Install.'))
            }
        }
        Set-Status 'ready' 'Launch files OK'; exit 0
    }
    try { $launchLock = [IO.File]::Open((Join-Path $gameRoot '.launch.lock'), 'OpenOrCreate', 'ReadWrite', 'None') } catch { throw (Text 'Запуск уже выполняется. Подожди.' 'A launch is already in progress. Please wait.') }
    $activeGame = Get-CimInstance Win32_Process -Filter "Name='java.exe' OR Name='javaw.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($gameRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0 }
    if ($activeGame) { Set-Status 'running' (Text 'RV уже запущен. Переключись в окно игры.' 'RV is already running. Switch to the game window.'); exit 0 }
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
        if (Test-Path -LiteralPath $tunnelFile) {
            try {
                $oldTunnel = Get-Content -LiteralPath $tunnelFile -Raw -Encoding UTF8 | ConvertFrom-Json
                $process = Get-Process -Id $oldTunnel.pid -ErrorAction Stop
                if ($process.Path -eq $porthole -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $oldTunnel.started) {
                    $oldTarget = if ($oldTunnel.target) { $oldTunnel.target } else { $oldTunnel.code }
                    $oldRemotePort = if ($oldTunnel.remotePort) { [int]$oldTunnel.remotePort } else { 25565 }
                    if ($oldTarget -eq $target -and $oldRemotePort -eq $remotePort -and (Test-GameServer '127.0.0.1' ([int]$oldTunnel.port))) { $existing = $process; $Port = [int]$oldTunnel.port }
                    else { $process.Kill(); [void]$process.WaitForExit(3000) }
                }
            } catch { }
        }
        $Server = '127.0.0.1'
        if (-not $existing) {
            $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
            $listener.Start()
            $Port = $listener.LocalEndpoint.Port
            $listener.Stop()
            $env:SteamAppId = '4963920'
            $env:SteamGameId = '4963920'
            $args = @('connect',$target,'--auto-approve-ports',('tcp/' + $remotePort),'--remap',($remotePort.ToString() + ':' + $Port),'--bind','127.0.0.1','--json')
            $tunnelStarted = Start-Process -FilePath $porthole -ArgumentList $args -WindowStyle Hidden -WorkingDirectory (Split-Path -Parent $porthole) -RedirectStandardOutput (Join-Path $gameRoot 'porthole-events.jsonl') -RedirectStandardError (Join-Path $gameRoot 'porthole-errors.log') -PassThru
            @{pid=$tunnelStarted.Id; started=$tunnelStarted.StartTime.ToUniversalTime().Ticks.ToString(); port=$Port; target=$target; remotePort=$remotePort} | ConvertTo-Json | Set-Content -LiteralPath $tunnelFile -Encoding UTF8
        }
        Set-Status 'connecting' (Text 'Подключение к серверу…' 'Connecting to server…')
        $deadline = [DateTime]::UtcNow.AddSeconds(45)
        $response = $null
        while ([DateTime]::UtcNow -lt $deadline) {
            if ($tunnelStarted -and $tunnelStarted.HasExited) { throw (Text 'Не удалось подключиться. Проверь вход в Steam и запущен ли сервер.' 'Could not connect. Check your Steam login and that the server is running.') }
            $response = Test-GameServer $Server $Port
            if ($response) { break }
            Start-Sleep -Milliseconds 500
        }
        if (-not $response) { throw (Text 'Сервер не отвечает. Проверь, запущен ли он, и уточни код у хозяина.' 'No response. Check that the server is running and confirm the code with the host.') }
    } elseif (-not $SkipTunnel -and -not $Prepare) {
        Set-Status 'connecting' (Text 'Проверка адреса сервера…' 'Checking server address…')
        $response = Test-GameServer $Server $Port
        if (-not $response) { throw (Text 'Сервер недоступен. Проверь адрес и порт в настройках.' 'Server unavailable. Check the address and port in Settings.') }
    }
    if ($Prepare) { Set-Status 'ready' (Text 'Готово к запуску.' 'Ready to play.'); exit 0 }
    if (-not $SkipTunnel) {
        if ($response.version.protocol -ne 340) { throw (Text 'Другая версия сервера. Нужен Minecraft 1.12.2.' 'Wrong server version. Minecraft 1.12.2 is required.') }
        if ($response.modinfo.modList) {
            $ids = @($response.modinfo.modList | ForEach-Object { $_.modid })
            if ('mcheli' -notin $ids -or 'techguns' -notin $ids) { throw (Text 'На сервере другой набор модов. Проверь выбранный сервер.' 'This server has a different modpack. Check the selected server.') }
        }
    }
    $md5 = [Security.Cryptography.MD5]::Create()
    try { $digest = $md5.ComputeHash([Text.Encoding]::UTF8.GetBytes('OfflinePlayer:' + $settings.nickname)) } finally { $md5.Dispose() }
    $digest[6] = ($digest[6] -band 15) -bor 48
    $digest[8] = ($digest[8] -band 63) -bor 128
    $uuid = -join ($digest | ForEach-Object { $_.ToString('x2') })
    $memoryMB = 3072
    try { $ramMB = [int]((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1MB); $memoryMB = [Math]::Min(4096, [Math]::Max(1536, [int]($ramMB*0.45))) } catch { }
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
    if ($tunnelStarted -and -not $tunnelStarted.HasExited) { try { $tunnelStarted.Kill() } catch { } }
    Set-Status 'error' (Get-WarfareConnectionError $_.Exception.Message $script:language)
    exit 1
} finally { if ($launchLock) { $launchLock.Dispose() }; if ($installGuard) { $installGuard.Dispose() } }
