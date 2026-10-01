if ($PSVersionTable.PSEdition -eq 'Desktop') {
    $nativeModules = $PSHOME + '\Modules'
    if (($env:PSModulePath -split ';')[0] -ne $nativeModules -or -not (Get-Command Get-FileHash -ErrorAction SilentlyContinue)) {
        $env:PSModulePath = $nativeModules + ';' + $env:PSModulePath
        Import-Module ($nativeModules + '\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -Force
    }
}
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
function Get-WarfareConnection($Settings, $Defaults = $null) {
    $mode = 'porthole'; $target = ''; $port = 25565
    if ($Defaults) {
        if ($Defaults.connectionMode) { $mode = [string]$Defaults.connectionMode }
        if ($Defaults.connectionTarget) { $target = [string]$Defaults.connectionTarget }
        if ($Defaults.serverPort) { $port = $Defaults.serverPort }
    }
    if ($Settings -and $Settings.PSObject.Properties['connectionMode']) {
        $mode = [string]$Settings.connectionMode
        $target = [string]$Settings.connectionTarget
        if ($Settings.serverPort) { $port = $Settings.serverPort }
    } elseif ($Settings -and $Settings.shareCode) {
        $mode = 'porthole'; $target = [string]$Settings.shareCode
        if ($Settings.port) { $port = $Settings.port }
    } elseif ($Settings -and $Settings.host -and $Settings.host -notin @('127.0.0.1','localhost','::1')) {
        $mode = 'direct'; $target = [string]$Settings.host
        if ($Settings.port) { $port = $Settings.port }
    }
    return [PSCustomObject]@{connectionMode=$mode;connectionTarget=$target;serverPort=$port}
}
function ConvertTo-WarfareConnection([string]$Mode,[string]$Target,[string]$Port = '25565') {
    $modeValue = $Mode.Trim().ToLowerInvariant()
    $targetValue = $Target.Trim()
    $portValue = 0
    if (-not [int]::TryParse($Port,[ref]$portValue) -or $portValue -lt 1 -or $portValue -gt 65535) { throw 'connection_port' }
    if (-not $targetValue) { throw 'connection_empty' }
    if ($modeValue -eq 'porthole') {
        if ($targetValue -match '^(peer|lobby):([0-9]{1,20})$') {
            $kind=$Matches[1].ToLowerInvariant(); $number=$Matches[2]; $id=[uint64]0
            if (-not [uint64]::TryParse($number,[ref]$id) -or $id -eq 0 -or ($kind -eq 'peer' -and $number.Length -ne 17)) { throw 'connection_target' }
            $targetValue=$kind+':'+$number
        } elseif ($targetValue -match '^[A-Za-z0-9]{4,16}$') { $targetValue=$targetValue.ToUpperInvariant() }
        else { throw 'connection_target' }
    } elseif ($modeValue -eq 'direct') {
        if ($targetValue -match '^\[([^\]]+)\](?::([0-9]+))?$') {
            $targetValue=$Matches[1]
            if ($Matches[2]) { if (-not [int]::TryParse($Matches[2],[ref]$portValue)) { throw 'connection_port' } }
        } elseif ($targetValue -match '^([^:]+):([0-9]+)$') {
            $targetValue=$Matches[1]
            if (-not [int]::TryParse($Matches[2],[ref]$portValue)) { throw 'connection_port' }
        }
        if ($portValue -lt 1 -or $portValue -gt 65535) { throw 'connection_port' }
        $ip=$null
        if ([Net.IPAddress]::TryParse($targetValue,[ref]$ip)) { $targetValue=$ip.ToString() }
        else {
            if ($targetValue.Length -gt 253 -or $targetValue -notmatch '^(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$' -or $targetValue -match '^[0-9.]+$') { throw 'connection_address' }
            foreach ($label in $targetValue.Split('.')) { if ($label.Length -gt 63 -or $label -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$') { throw 'connection_address' } }
            $targetValue=$targetValue.ToLowerInvariant()
        }
    } else { throw 'connection_mode' }
    return [PSCustomObject]@{connectionMode=$modeValue;connectionTarget=$targetValue;serverPort=$portValue}
}
function Set-WarfareConnection($Settings,$Connection) {
    foreach ($key in @('connectionMode','connectionTarget','serverPort')) { $Settings | Add-Member -MemberType NoteProperty -Name $key -Value $Connection.$key -Force }
    return $Settings
}
function Get-WarfareConnectionError([string]$Code,[string]$Language='ru') {
    $ru=@{connection_port='Порт: число от 1 до 65535.';connection_empty='Укажи сервер в настройках.';connection_target='Укажи код Porthole, peer:SteamID или lobby:ID.';connection_address='Укажи IP или домен сервера без http:// и пути.';connection_mode='Выбери способ подключения.'}
    $en=@{connection_port='Port must be between 1 and 65535.';connection_empty='Set the server in Settings.';connection_target='Enter a Porthole code, peer:SteamID or lobby:ID.';connection_address='Enter a server IP or hostname without http:// or a path.';connection_mode='Choose a connection type.'}
    if ($ru.ContainsKey($Code)) { if ($Language -eq 'en') { return $en[$Code] }; return $ru[$Code] }
    return $Code
}
