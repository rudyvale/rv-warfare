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
. (Join-Path $PSScriptRoot 'Warfare-ClientMods.ps1')
function Get-WarfareDuplicateMods([string]$Root) {
    Get-WarfareDuplicateClientMods $Root
}
function Assert-WarfareUniqueMods([string]$Root) {
    $conflicts=@(Get-WarfareDuplicateMods $Root)
    if(-not $conflicts.Count){return}
    $rootPath=[IO.Path]::GetFullPath($Root).TrimEnd('\')+'\'
    $parts=@(foreach($conflict in $conflicts){
        $paths=@($conflict.paths|ForEach-Object {$_.Substring($rootPath.Length).Replace('\','/')})
        $identity=if($conflict.kind -ceq 'content-pack'){'content-pack '+$conflict.packId}else{$conflict.modid}
        $identity+': '+($paths -join ', ')
    })
    throw ('duplicate_mods:'+($parts -join '; '))
}
function Get-WarfareRequiredMods([string]$Root) {
    $required=[ordered]@{}
    $path=Join-Path $Root 'release.json'
    if(-not (Test-Path -LiteralPath $path)){throw 'connection_package'}
    try {
        $release=Get-Content -LiteralPath $path -Raw -Encoding UTF8|ConvertFrom-Json
        if($release.version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$'){throw 'connection_package'}
        $version=[version]$release.version
        if($release.requiredMods){
            foreach($entry in $release.requiredMods.PSObject.Properties){
                if($entry.Name -notmatch '^[a-z0-9_]+$' -or $entry.Value -isnot [string] -or $entry.Value.Length -lt 1 -or $entry.Value.Length -gt 128 -or $entry.Value -match '[\r\n]'){throw 'connection_package'}
                $required[$entry.Name]=$entry.Value
            }
        }
        if($version -ge [version]'1.1.0' -and -not $required.Contains('mcheli')){throw 'connection_package'}
    }catch{throw 'connection_package'}
    return $required
}
function Assert-WarfareServerCompatibility($Response,$Required) {
    if($Response.version.protocol -ne 340){throw 'incompatible_version'}
    $mods=@($Response.modinfo.modList)
    $ids=@($mods|ForEach-Object {$_.modid})
    if('mcheli' -notin $ids -or 'techguns' -notin $ids){throw 'incompatible_mods'}
    if($Required){
        foreach($id in $Required.Keys){
            $advertised=@($mods|Where-Object {$_.modid -ceq $id})
            if($advertised.Count -ne 1 -or [string]$advertised[0].version -cne $Required[$id]){throw 'incompatible_mod_version'}
        }
    }
}
function Get-WarfareConnectionError([string]$Code,[string]$Language='ru') {
    if($Code.StartsWith('duplicate_mods:')){
        $details=$Code.Substring('duplicate_mods:'.Length)
        if($Language -eq 'en'){return 'Several versions of a mod are installed. Open the game folder and keep one version: '+$details}
        return 'Установлено несколько версий мода. Открой папку игры и оставь одну версию: '+$details
    }
    $ru=@{connection_port='Порт: число от 1 до 65535.';connection_empty='Укажи сервер в настройках.';connection_target='Укажи код Porthole, peer:SteamID или lobby:ID.';connection_address='Укажи IP или домен сервера без http:// и пути.';connection_mode='Выбери способ подключения.'}
    $en=@{connection_port='Port must be between 1 and 65535.';connection_empty='Set the server in Settings.';connection_target='Enter a Porthole code, peer:SteamID or lobby:ID.';connection_address='Enter a server IP or hostname without http:// or a path.';connection_mode='Choose a connection type.'}
    $ru.same_account='Для подключения через Porthole нужен другой Steam-аккаунт на втором ПК.'
    $en.same_account='Use a different Steam account on the second PC to connect through Porthole.'
    $ru.steam_offline='Открой Steam и войди в аккаунт, затем нажми «Играть».'
    $en.steam_offline='Open Steam and sign in, then click Play.'
    $ru.steam_changed='Steam перезапустился. Нажми «Играть» ещё раз.'
    $en.steam_changed='Steam restarted. Click Play again.'
    $ru.timeout='Сервер не отвечает. Проверь, что он запущен, и уточни код у хозяина.'
    $en.timeout='The server is not responding. Check that it is running and confirm the code with the host.'
    $ru.failed='Подключение не удалось. Проверь вход в Steam и запущен ли сервер, затем повтори попытку.'
    $en.failed='Connection failed. Check your Steam login and that the server is running, then try again.'
    $ru.server_offline='Сервер недоступен. Проверь адрес и порт в настройках.'
    $en.server_offline='The server is unavailable. Check the address and port in Settings.'
    $ru.incompatible_version='Другая версия сервера. Нужен Minecraft 1.12.2.'
    $en.incompatible_version='Wrong server version. Minecraft 1.12.2 is required.'
    $ru.incompatible_mods='На сервере другой набор модов. Проверь выбранный сервер.'
    $en.incompatible_mods='This server has a different modpack. Check the selected server.'
    $ru.incompatible_mod_version='Версии сборки не совпадают. Обнови RV или уточни версию у хозяина сервера.'
    $en.incompatible_mod_version='The modpack versions do not match. Update RV or confirm the version with the host.'
    $ru.connection_package='В установке нет данных совместимости. Установи актуальную сборку RV.'
    $en.connection_package='Compatibility data is missing from this installation. Install the current RV package.'
    if ($ru.ContainsKey($Code)) { if ($Language -eq 'en') { return $en[$Code] }; return $ru[$Code] }
    return $Code
}
