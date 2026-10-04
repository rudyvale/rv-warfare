param(
    [string]$WarfareWorkerAction,
    [string]$WarfareWorkerGameRoot,
    [int]$WarfareWorkerPort = 25565,
    [string]$WarfareWorkerNickname,
    [string]$WarfareWorkerStatusFile,
    [ValidateSet('ru','en')][string]$WarfareWorkerLanguage = 'ru',
    [switch]$WarfareWorkerAcceptEula
)
$ErrorActionPreference = 'Stop'
function Get-WarfareModeValue($Object,[string]$Name) {
    if ($null -eq $Object) { return $null }
    if ($Object -is [Collections.IDictionary]) {
        if ($Object.Contains($Name)) { return $Object[$Name] }
        return $null
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) { return $property.Value }
    return $null
}
function New-WarfareModeConnection([string]$Mode = 'porthole',[string]$Target = '',[int]$Port = 25565) {
    return [PSCustomObject]@{connectionMode=$Mode;connectionTarget=$Target;serverPort=$Port}
}
function ConvertTo-WarfareModeConnection($Value) {
    if (Get-Command Get-WarfareConnection -ErrorAction SilentlyContinue) {
        $connection = Get-WarfareConnection $Value $null
    } else {
        $mode = [string](Get-WarfareModeValue $Value 'connectionMode')
        $target = [string](Get-WarfareModeValue $Value 'connectionTarget')
        $port = [int]25565
        $parsed = 0
        if ([int]::TryParse([string](Get-WarfareModeValue $Value 'serverPort'),[ref]$parsed) -and $parsed -ge 1 -and $parsed -le 65535) { $port = $parsed }
        if ($mode -notin @('porthole','direct')) { $mode = 'porthole' }
        $connection = New-WarfareModeConnection $mode $target $port
    }
    $mode = [string]$connection.connectionMode
    if ($mode -notin @('porthole','direct')) { $mode = 'porthole' }
    $port = 25565
    $parsed = 0
    if ([int]::TryParse([string]$connection.serverPort,[ref]$parsed) -and $parsed -ge 1 -and $parsed -le 65535) { $port = $parsed }
    return (New-WarfareModeConnection $mode ([string]$connection.connectionTarget) $port)
}
function Get-WarfarePlayModeState($Settings) {
    $legacy = ConvertTo-WarfareModeConnection $Settings
    $savedProfiles = Get-WarfareModeValue $Settings 'playProfiles'
    $savedFriends = Get-WarfareModeValue $savedProfiles 'friends'
    $savedOwner = Get-WarfareModeValue $savedProfiles 'owner'
    $friends = if ($null -ne $savedFriends) { ConvertTo-WarfareModeConnection $savedFriends } elseif ($legacy.connectionTarget) { $legacy } else { New-WarfareModeConnection }
    $owner = if ($null -ne $savedOwner) { ConvertTo-WarfareModeConnection $savedOwner } else { New-WarfareModeConnection }
    $savedHost = Get-WarfareModeValue $savedProfiles 'host'
    $hostPort = 25565
    $parsedPort = 0
    if ([int]::TryParse([string](Get-WarfareModeValue $savedHost 'port'),[ref]$parsedPort) -and $parsedPort -ge 1 -and $parsedPort -le 65535) { $hostPort = $parsedPort }
    $savedMode = [string](Get-WarfareModeValue $Settings 'playMode')
    if ($savedMode -in @('local','friends','owner','host')) { $mode = $savedMode }
    elseif ($legacy.connectionTarget) { $mode = 'friends' }
    else { $mode = 'local' }
    $migrated = ($null -eq $savedFriends -and [bool]$legacy.connectionTarget)
    return [PSCustomObject]@{mode=$mode;friends=$friends;owner=$owner;hostPort=$hostPort;migrated=$migrated}
}
function Get-WarfarePlayModeConnection($State,[ValidateSet('friends','owner')][string]$Mode) {
    return ConvertTo-WarfareModeConnection $State.$Mode
}
function Set-WarfarePlayModeConnection($State,[ValidateSet('friends','owner')][string]$Mode,$Connection) {
    $State.$Mode = ConvertTo-WarfareModeConnection $Connection
    return $State
}
function Set-WarfarePlayModeHostPort($State,[int]$Port) {
    if ($Port -lt 1 -or $Port -gt 65535) { throw 'host_port' }
    $State.hostPort = $Port
    return $State
}
function Set-WarfarePlayModeState($Settings,$State,[ValidateSet('local','friends','owner','host')][string]$Mode) {
    if ($null -eq $Settings) { $Settings = [PSCustomObject]@{} }
    $State.mode = $Mode
    $profiles = [PSCustomObject]@{
        friends = ConvertTo-WarfareModeConnection $State.friends
        owner = ConvertTo-WarfareModeConnection $State.owner
        host = [PSCustomObject]@{port=[int]$State.hostPort}
    }
    $Settings | Add-Member -MemberType NoteProperty -Name playMode -Value $Mode -Force
    $Settings | Add-Member -MemberType NoteProperty -Name playProfiles -Value $profiles -Force
    if ($Mode -in @('friends','owner') -and (Get-Command Set-WarfareConnection -ErrorAction SilentlyContinue)) {
        $Settings = Set-WarfareConnection $Settings (Get-WarfarePlayModeConnection $State $Mode)
    }
    return $Settings
}
function Get-WarfareLanIPv4Addresses([object[]]$Addresses) {
    $valid = [Collections.Generic.List[string]]::new()
    foreach ($value in $Addresses) {
        $address = $null
        if (-not [Net.IPAddress]::TryParse([string]$value,[ref]$address) -or $address.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { continue }
        $bytes = $address.GetAddressBytes()
        if ($bytes[0] -eq 10 -or ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or ($bytes[0] -eq 192 -and $bytes[1] -eq 168)) {
            $formatted = $address.ToString()
            if (-not $valid.Contains($formatted)) { $valid.Add($formatted) }
        }
    }
    return $valid.ToArray()
}
function Get-WarfareHostLanIPv4Addresses {
    $addresses = [Collections.Generic.List[string]]::new()
    try { $adapters = [Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() } catch { return @() }
    foreach ($adapter in $adapters) {
        try {
            if ($adapter.OperationalStatus -ne [Net.NetworkInformation.OperationalStatus]::Up -or $adapter.NetworkInterfaceType -notin @([Net.NetworkInformation.NetworkInterfaceType]::Ethernet,[Net.NetworkInformation.NetworkInterfaceType]::Wireless80211)) { continue }
            foreach ($unicast in $adapter.GetIPProperties().UnicastAddresses) {
                if ($unicast.Address.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork) { $addresses.Add($unicast.Address.ToString()) }
            }
        } catch { }
    }
    return @(Get-WarfareLanIPv4Addresses $addresses.ToArray())
}
function Install-WarfareWorldTemplate([string]$PackageRoot,[string]$GameRoot) {
    $savesRoot=Join-Path $GameRoot 'saves'
    $destination=Join-Path $savesRoot 'Battlefield-Extended'
    if(Test-Path -LiteralPath $destination){return $false}
    $descriptorPath=Join-Path $PackageRoot 'self-host-package.json'
    $archivePath=Join-Path $PackageRoot 'self-host-world.zip'
    if(-not(Test-Path -LiteralPath $descriptorPath -PathType Leaf) -or -not(Test-Path -LiteralPath $archivePath -PathType Leaf)){throw 'The world template package is incomplete.'}
    try{$descriptor=Get-Content -LiteralPath $descriptorPath -Raw -Encoding UTF8|ConvertFrom-Json}catch{throw 'The world template package is invalid.'}
    $template=$descriptor.worldTemplate
    $archiveItem=Get-Item -LiteralPath $archivePath
    if($template.path -cne 'self-host-world.zip' -or $template.sha256 -cnotmatch '^[a-f0-9]{64}$' -or [long]$template.size -ne $archiveItem.Length -or (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $template.sha256){throw 'The world template checksum does not match.'}
    $archive=[IO.Compression.ZipFile]::OpenRead($archivePath)
    $files=[Collections.Generic.List[object]]::new()
    $paths=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $metadata=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $totalBytes=[long]0
    $regionCount=0
    $functionCount=0
    try{
        if($archive.Entries.Count -gt 8192){throw 'The world template has too many files.'}
        foreach($entry in $archive.Entries){
            $relative=$entry.FullName.Replace('\','/')
            if(-not $relative -or $relative.StartsWith('/') -or $relative -match '^[A-Za-z]:' -or $relative -match '//') {throw 'The world template contains an unsafe path.'}
            $isDirectory=$relative.EndsWith('/')
            $parts=@($relative.TrimEnd('/').Split('/'))
            if(@($parts|Where-Object { -not $_ -or $_ -in @('.','..') -or $_.Contains(':') }).Count){throw 'The world template contains an unsafe path.'}
            if(-not $isDirectory -and $parts.Count -eq 1 -and $parts[0] -in @('world-template-manifest.json','INSTALL-NEW-WORLD.md','SHA256SUMS.txt')){$null=$metadata.Add($parts[0]);continue}
            if($parts[0] -cne 'Battlefield-Extended'){throw 'The world template contains an unexpected file.'}
            if($isDirectory){continue}
            if(-not $paths.Add($relative)){throw 'The world template contains duplicate paths.'}
            $worldRelative=($parts|Select-Object -Skip 1) -join '/'
            if(-not $worldRelative){throw 'The world template contains an invalid world root.'}
            $allowed=$worldRelative -in @('level.dat','data/scoreboard.dat') -or $worldRelative -match '^region/r\.-?[0-9]+\.-?[0-9]+\.mca$' -or $worldRelative -match '^data/functions/warfare/[A-Za-z0-9_]+\.mcfunction$' -or $worldRelative -match '^data/functions/rvmap/(tree_0[1-9]|tree_1[0-2]|plants)\.mcfunction$'
            if(-not $allowed){throw 'The world template contains an unexpected file.'}
            $totalBytes += [long]$entry.Length
            if($totalBytes -gt 1073741824){throw 'The world template is too large.'}
            if($worldRelative -match '^region/'){ $regionCount++ }
            if($worldRelative -match '^data/functions/'){ $functionCount++ }
            $files.Add($entry)
        }
        if($metadata.Count -ne 3 -or -not $paths.Contains('Battlefield-Extended/level.dat') -or -not $paths.Contains('Battlefield-Extended/data/scoreboard.dat') -or $regionCount -lt 1 -or $functionCount -lt 1){throw 'The world template is incomplete.'}
        New-Item -ItemType Directory -Path $savesRoot -Force|Out-Null
        $stageRoot=Join-Path $savesRoot ('.rv-world-stage-'+[Guid]::NewGuid().ToString('N'))
        $stageWorld=Join-Path $stageRoot 'Battlefield-Extended'
        New-Item -ItemType Directory -Path $stageWorld -Force|Out-Null
        try{
            foreach($entry in $files){
                $worldRelative=($entry.FullName.Replace('\','/').Split('/')|Select-Object -Skip 1) -join '/'
                $target=[IO.Path]::GetFullPath((Join-Path $stageWorld $worldRelative.Replace('/',[IO.Path]::DirectorySeparatorChar)))
                if(-not $target.StartsWith([IO.Path]::GetFullPath($stageWorld).TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'The world template contains an unsafe target.'}
                New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force|Out-Null
                $inputStream=$entry.Open()
                $outputStream=$null
                try{$outputStream=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);$inputStream.CopyTo($outputStream)}finally{if($outputStream){$outputStream.Dispose()};$inputStream.Dispose()}
            }
            if(Test-Path -LiteralPath $destination){return $false}
            [IO.Directory]::Move($stageWorld,$destination)
            return $true
        }finally{if(Test-Path -LiteralPath $stageRoot){Remove-Item -LiteralPath $stageRoot -Recurse -Force}}
    }finally{$archive.Dispose()}
}
function Write-WarfarePlayModeWorkerStatus([string]$State,[string]$Message,$Result = $null,[string]$Reason = '') {
    if (-not $WarfareWorkerStatusFile) { return }
    $data = [ordered]@{state=$State;message=$Message;reason=$Reason}
    if ($Result) {
        $data.server = [string](Get-WarfareModeValue $Result 'server')
        $data.port = [int](Get-WarfareModeValue $Result 'port')
        $shareCode = Get-WarfareModeValue $Result 'shareCode'
        if ($shareCode) { $data.shareCode = [string]$shareCode }
    }
    $temporary = $WarfareWorkerStatusFile + '.tmp'
    [IO.File]::WriteAllText($temporary,($data | ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $WarfareWorkerStatusFile -Force
}
if ($WarfareWorkerAction) {
    try {
        if ($WarfareWorkerAction -notin @('start-host','stop-host')) { throw 'self_host_action' }
        $selfHostPath = Join-Path $PSScriptRoot 'Warfare-SelfHost.ps1'
        if (-not (Test-Path -LiteralPath $selfHostPath -PathType Leaf)) { throw 'self_host_helper_missing' }
        . $selfHostPath
        if ($WarfareWorkerAction -eq 'start-host') {
            $startParameters = @{GameRoot=$WarfareWorkerGameRoot;Port=$WarfareWorkerPort;Nickname=$WarfareWorkerNickname}
            $eulaAccepted = Get-WarfareSelfHostEulaAccepted -GameRoot $WarfareWorkerGameRoot
            if (-not $eulaAccepted -and -not $WarfareWorkerAcceptEula) { throw 'self_host_eula_required' }
            if (-not $eulaAccepted -and $WarfareWorkerAcceptEula) { $startParameters.AcceptEula = $true }
            $result = Start-WarfareSelfHost @startParameters
            if ([string](Get-WarfareModeValue $result 'server') -ne '127.0.0.1') { throw 'self_host_address' }
            $resultPort = 0
            if (-not [int]::TryParse([string](Get-WarfareModeValue $result 'port'),[ref]$resultPort) -or $resultPort -lt 1 -or $resultPort -gt 65535) { throw 'self_host_port' }
            Write-WarfarePlayModeWorkerStatus 'ready' $(if($WarfareWorkerLanguage -eq 'ru'){'Сервер запущен.'}else{'Server started.'}) $result
        } else {
            Stop-WarfareSelfHost -GameRoot $WarfareWorkerGameRoot
            Write-WarfarePlayModeWorkerStatus 'ready' $(if($WarfareWorkerLanguage -eq 'ru'){'Сервер остановлен.'}else{'Server stopped.'})
        }
        exit 0
    } catch {
        $reason = if ($_.Exception.Message -eq 'self_host_eula_required') { 'self_host_eula_required' } else { 'self_host_failed' }
        Write-WarfarePlayModeWorkerStatus 'error' $_.Exception.Message $null $reason
        exit 1
    }
}
