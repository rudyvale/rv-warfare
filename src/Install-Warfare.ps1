param([ValidateSet('ru','en')][string]$Language, [string]$Nickname, [string]$InstallRoot, [switch]$NoShortcut, [switch]$NoSteam, [switch]$NoLaunch, [string]$StatusFile, [string]$CancelPath)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
[Net.ServicePointManager]::DefaultConnectionLimit = 16
Add-Type -AssemblyName System.IO.Compression.FileSystem
$packageRoot = $PSScriptRoot
. (Join-Path $packageRoot 'Warfare-Connection.ps1')
. (Join-Path $packageRoot 'Warfare-Performance.ps1')
if(Test-Path -LiteralPath (Join-Path $packageRoot 'Warfare-PlayModes.ps1')){. (Join-Path $packageRoot 'Warfare-PlayModes.ps1')}
if(Test-Path -LiteralPath (Join-Path $packageRoot 'Warfare-ClientControls.ps1')){. (Join-Path $packageRoot 'Warfare-ClientControls.ps1')}
$defaultsPath = Join-Path $packageRoot 'server-defaults.json'
$connectionDefaults = if (Test-Path -LiteralPath $defaultsPath) { Get-Content -LiteralPath $defaultsPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
if (-not $InstallRoot) { $InstallRoot = Join-Path $env:LOCALAPPDATA 'Warfare-1.12.2' }
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
$clientPreferencesExisted = Test-Path -LiteralPath (Join-Path $InstallRoot 'config\rv-client.properties')
$initialPerformance = -not (Test-Path -LiteralPath (Join-Path $InstallRoot 'installed-manifest.json')) -and -not (Test-Path -LiteralPath (Join-Path $InstallRoot 'options.txt')) -and -not (Test-Path -LiteralPath (Join-Path $InstallRoot 'config\rv-client.properties')) -and -not (Test-Path -LiteralPath (Join-Path $InstallRoot 'optionsshaders.txt'))
if ($InstallRoot.TrimEnd('\') -eq [IO.Path]::GetFullPath($packageRoot).TrimEnd('\')) { throw 'Choose an installation directory outside the package folder.' }
. (Join-Path $packageRoot 'Warfare-Updates.ps1')
Assert-VmUpgrade $packageRoot $InstallRoot
function Resolve-Inside([string]$Root, [string]$Relative) {
    if ([IO.Path]::IsPathRooted($Relative)) { throw 'Absolute package path is not allowed.' }
    $absolute = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $absolute.StartsWith($Root.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid package path.' }
    return $absolute
}
$settingsPath = Join-Path $InstallRoot 'warfare-settings.json'
$previousSettings = if (Test-Path -LiteralPath $settingsPath) { Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
if (-not $Language) {
    if ($previousSettings) { $Language = $previousSettings.language } else {
        $choice = Read-Host 'Language / Язык: 1 = Русский, 2 = English [1]'
        $Language = if ($choice -eq '2') { 'en' } else { 'ru' }
    }
}
function Set-InstallStatus([string]$State,[string]$Message) {
    if (-not $StatusFile) { return }
    $temporary=$StatusFile+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
    try {
        [IO.File]::WriteAllText($temporary,([PSCustomObject]@{state=$State;message=$Message}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temporary -Destination $StatusFile -Force
    } finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
}
function Say([string]$Russian, [string]$English) {
    $message=if ($Language -eq 'ru') { $Russian } else { $English }
    Write-Host $message
    Set-InstallStatus 'installing' $message
}
if (-not $Nickname) {
    if ($previousSettings) { $Nickname = $previousSettings.nickname } else {
        Say 'Введи свой ник Minecraft (3–16 букв, цифр или _).' 'Enter your Minecraft nickname (3–16 letters, numbers or _).'
        $Nickname = Read-Host 'Nickname'
    }
}
if ($Nickname -notmatch '^[A-Za-z0-9_]{3,16}$') { throw 'Nickname must contain 3–16 letters, numbers or _.' }
$installLock = $null
try { $installLock = Enter-WarfareClientOperation $InstallRoot 8000 } catch { throw (Get-WarfarePreferenceError $_.Exception.Message 'ru') }
try {
Start-VmUpdateCheck $InstallRoot $packageRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$stage = Join-Path $InstallRoot ('.update-' + $stamp)
$backup = Join-Path $InstallRoot ('backups\' + $stamp)
New-Item -ItemType Directory -Path $stage -Force | Out-Null
$manifest = Get-Content -LiteralPath (Join-Path $packageRoot 'package-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($entry in $manifest.archives) {
    $path = Resolve-Inside $packageRoot $entry.path
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw ('Package checksum mismatch: ' + $entry.path) }
}
Say 'Распаковка сборки и Java 8…' 'Extracting the modpack and Java 8…'
[IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $packageRoot 'payload.zip'), $stage)
[IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $packageRoot 'runtime.zip'), (Join-Path $stage 'runtime'))
$release=Get-Content -LiteralPath (Join-Path $packageRoot 'release.json') -Raw -Encoding UTF8|ConvertFrom-Json
$vendorCatalogPath=Join-Path $packageRoot 'vendor-catalog.json'
if ($release.vendorCatalogSha256) {
    . (Join-Path $packageRoot 'Warfare-VendorDownloads.ps1')
    $vendorProgress={param($value)
        $percent=[int](100*$value.received/[Math]::Max(1,$value.total))
        $message=if ($Language -eq 'ru') { 'Загрузка: '+$value.name+' · '+$percent+'%' } else { 'Downloading: '+$value.name+' · '+$percent+'%' }
        if ($value.state -eq 'retrying') { $message=if ($Language -eq 'ru') { 'Повтор загрузки: '+$value.name } else { 'Retrying: '+$value.name } }
        Set-InstallStatus 'installing' $message
    }
    try {
        $vendors=@(Initialize-WarfareVendorStage -CatalogPath $vendorCatalogPath -ExpectedCatalogSha256 $release.vendorCatalogSha256 -InstallRoot $InstallRoot -StageRoot $stage -CacheRoot (Join-Path $InstallRoot '.vendor-cache') -CancelPath $CancelPath -ProgressCallback $vendorProgress)
        foreach ($vendor in $vendors) {
            $managed=@($manifest.managedFiles|Where-Object {$_.path -ceq $vendor.path -and $_.sha256 -ceq $vendor.sha256})
            if ($managed.Count -ne 1) { throw 'RV_VENDOR_CATALOG' }
        }
    } catch {
        Set-InstallStatus 'failed' (Get-WarfareVendorError $_.Exception.Message $Language)
        throw
    }
} elseif ($release.version -match '^[0-9]+\.[0-9]+\.[0-9]+$' -and [version]$release.version -ge [version]'1.2.0') { throw 'RV_VENDOR_CATALOG' }

foreach ($entry in $manifest.managedFiles) {
    Resolve-Inside $stage $entry.path | Out-Null
    Resolve-Inside $InstallRoot $entry.path | Out-Null
    if ((Get-FileHash -LiteralPath (Join-Path $stage $entry.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw ('File checksum mismatch: ' + $entry.path) }
}
$downloads = Get-Content -LiteralPath (Join-Path $packageRoot 'installer-files.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$pending = [Collections.Generic.Queue[object]]::new()
$completed = 0
foreach ($file in $downloads.files) {
    $target = Resolve-Inside $InstallRoot $file.path
    if (([Uri]$file.url).Scheme -ne 'https') { throw 'Downloads must use HTTPS.' }
    if ((Test-Path -LiteralPath $target) -and (Get-FileHash -LiteralPath $target -Algorithm SHA1).Hash.ToLowerInvariant() -eq $file.sha1) { $completed++; continue }
    $cached = Join-Path (Join-Path $env:APPDATA '.minecraft') $file.path
    if (-not (Test-Path -LiteralPath $cached) -and $file.path -eq 'versions/1.12.2/1.12.2.jar') {
        $versionsRoot = Join-Path $env:APPDATA '.minecraft\versions'
        if (Test-Path -LiteralPath $versionsRoot) {
            foreach ($folder in Get-ChildItem -LiteralPath $versionsRoot -Directory) {
                $candidate = Join-Path $folder.FullName ($folder.Name + '.jar')
                if ((Test-Path -LiteralPath $candidate) -and (Get-FileHash -LiteralPath $candidate -Algorithm SHA1).Hash.ToLowerInvariant() -eq $file.sha1) { $cached = $candidate; break }
            }
        }
    }
    if ((Test-Path -LiteralPath $cached) -and (Get-FileHash -LiteralPath $cached -Algorithm SHA1).Hash.ToLowerInvariant() -eq $file.sha1) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $cached -Destination $target -Force
        $completed++
        continue
    }
    $pending.Enqueue([PSCustomObject]@{file=$file;attempt=0})
}
$running = [Collections.Generic.List[object]]::new()
$lastDownloadProgress = Get-Date
Say 'Загрузка Minecraft, Forge, библиотек и ресурсов…' 'Downloading Minecraft, Forge, libraries and resources…'
try {
while ($pending.Count -gt 0 -or $running.Count -gt 0) {
    while ($pending.Count -gt 0 -and $running.Count -lt 8) {
        $job = $pending.Dequeue()
        $target = Join-Path $InstallRoot $job.file.path
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        $client = [Net.WebClient]::new()
        $client.Headers['User-Agent'] = 'Warfare-Installer/1.0'
        $task = $client.DownloadFileTaskAsync([Uri]$job.file.url, ($target + '.download'))
        $running.Add([PSCustomObject]@{job=$job;client=$client;task=$task;target=$target;started=(Get-Date)})
    }
    foreach ($item in @($running.ToArray())) {
        if (-not $item.task.IsCompleted -and ((Get-Date)-$item.started).TotalSeconds -lt 45) { continue }
        if (-not $item.task.IsCompleted) { $item.client.CancelAsync() }
        $running.Remove($item) | Out-Null
        $item.client.Dispose()
        $valid = $item.task.IsCompleted -and -not $item.task.IsFaulted -and -not $item.task.IsCanceled -and (Test-Path -LiteralPath ($item.target + '.download'))
        if ($valid) { $valid = (Get-FileHash -LiteralPath ($item.target + '.download') -Algorithm SHA1).Hash.ToLowerInvariant() -eq $item.job.file.sha1 }
        if (-not $valid) {
            $item.job.attempt++
            if ($item.job.attempt -ge 3) { throw ('Download/checksum failed: ' + $item.job.file.path) }
            $pending.Enqueue($item.job)
            continue
        }
        Move-Item -LiteralPath ($item.target + '.download') -Destination $item.target -Force
        $completed++
    }
    Write-Progress -Activity 'Minecraft / Forge / Resources' -Status ($completed.ToString() + '/' + $downloads.files.Count) -PercentComplete ([Math]::Min(100, 100*$completed/$downloads.files.Count))
    if (((Get-Date)-$lastDownloadProgress).TotalSeconds -ge 5) { Write-Host ($completed.ToString() + '/' + $downloads.files.Count + ' files'); $lastDownloadProgress = Get-Date }
    Start-Sleep -Milliseconds 100
}
} finally { foreach ($item in @($running.ToArray())) { $item.client.CancelAsync(); $item.client.Dispose() } }
Write-Progress -Activity 'Minecraft / Forge / Resources' -Completed
$natives = Join-Path $stage 'natives'
New-Item -ItemType Directory -Path $natives -Force | Out-Null
foreach ($file in $downloads.files | Where-Object { $_.native }) {
    $archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $InstallRoot $file.path))
    try {
        foreach ($entry in $archive.Entries | Where-Object { $_.Name -like '*.dll' }) {
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $natives $entry.Name), $true)
        }
    } finally { $archive.Dispose() }
}
$optifineName = 'OptiFine_1.12.2_HD_U_G5.jar'
$optifine = Join-Path $stage ('mods\' + $optifineName)
if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot ('mods\' + $optifineName)))) {
    $versionsRoot = Join-Path $env:APPDATA '.minecraft\versions'
    if (Test-Path -LiteralPath $versionsRoot) {
        foreach ($folder in Get-ChildItem -LiteralPath $versionsRoot -Directory) {
            $candidate = Join-Path $folder.FullName ('mods\' + $optifineName)
            if ((Test-Path -LiteralPath $candidate) -and (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant() -eq $manifest.optifineSha256) { Copy-Item -LiteralPath $candidate -Destination $optifine; break }
        }
    }
}
if (Test-Path -LiteralPath (Join-Path $InstallRoot ('mods\' + $optifineName))) {
    Copy-Item -LiteralPath (Join-Path $InstallRoot ('mods\' + $optifineName)) -Destination $optifine
} elseif (-not (Test-Path -LiteralPath $optifine)) {
    Say 'Загрузка OptiFine G5 для шейдеров BSL…' 'Downloading OptiFine G5 for BSL shaders…'
    $landing = Join-Path $stage 'optifine-page.html'
    & curl.exe --fail --location --silent --show-error --max-time 45 --retry 2 --user-agent 'Mozilla/5.0' --output $landing ('https://optifine.net/adloadx?f=' + $optifineName)
    if ($LASTEXITCODE -eq 0) {
        $html = [IO.File]::ReadAllText($landing)
        $link = [regex]::Match($html, 'href=[''"''](downloadx\?[^''"'']+)')
        if ($link.Success) {
            $url = 'https://optifine.net/' + $link.Groups[1].Value.Replace('&amp;', '&')
            & curl.exe --fail --location --silent --show-error --max-time 60 --retry 2 --user-agent 'Mozilla/5.0' --output $optifine $url
        }
    }
    if ((Test-Path -LiteralPath $optifine) -and (Get-FileHash -LiteralPath $optifine -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.optifineSha256) {
        Remove-Item -LiteralPath $optifine
    }
}
if (-not (Test-Path -LiteralPath $optifine)) {
    Say 'OptiFine недоступен: игра установится, для BSL скачай G5 с optifine.net.' 'OptiFine is unavailable: the game will install; download G5 from optifine.net to enable BSL.'
}
$rollback = [Collections.Generic.List[object]]::new()
function Backup-File([string]$Path, [string]$Relative, [switch]$Remove) {
    $absolute = [IO.Path]::GetFullPath($Path)
    if (-not $absolute.StartsWith($InstallRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe update target.' }
    $destination = Join-Path $backup $Relative
    $exists = Test-Path -LiteralPath $Path
    if ($exists) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $Path -Destination $destination -Force
    }
    $rollback.Add([PSCustomObject]@{target=$Path;backup=$destination;existed=$exists})
    if ($Remove -and $exists) { Remove-Item -LiteralPath $absolute }
}

$oldManifestPath = Join-Path $InstallRoot 'installed-manifest.json'
$oldManifest = if (Test-Path -LiteralPath $oldManifestPath) { Get-Content -LiteralPath $oldManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
$currentModNames = @($manifest.managedFiles | Where-Object { $_.path -like 'mods/*' } | ForEach-Object { Split-Path -Leaf $_.path })
try {
if (Test-Path -LiteralPath (Join-Path $InstallRoot 'mods')) {
    foreach ($mod in Get-ChildItem -LiteralPath (Join-Path $InstallRoot 'mods') -File -Filter '*.jar') {
        $owned = $false
        if ($oldManifest) { $owned = @($oldManifest.managedFiles | Where-Object { $_.path -eq ('mods/' + $mod.Name) }).Count -gt 0 }
        foreach ($pattern in $manifest.managedModPatterns) { if ($mod.Name -match $pattern) { $owned = $true } }
        if ($owned -and $mod.Name -notin $currentModNames -and $mod.Name -ne $optifineName) { Backup-File $mod.FullName ('mods\' + $mod.Name) -Remove }
    }
}
foreach ($entry in $manifest.managedFiles) {
    $target = Join-Path $InstallRoot $entry.path
    $source = Join-Path $stage $entry.path
    if ($entry.existingOnly -and -not (Test-Path -LiteralPath (Join-Path $InstallRoot 'mcheli_addons\default') -PathType Container)) { continue }
    if (($entry.path -like 'config/*' -or $entry.path -ceq 'ModularWarfare/mod_config.json') -and (Test-Path -LiteralPath $target)) { continue }
    if ((Test-Path -LiteralPath $target) -and (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -eq $entry.sha256) { continue }
    Backup-File $target $entry.path
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $target
}
foreach ($directory in @('runtime', 'natives')) {
    $source = Join-Path $stage $directory
    $target = Join-Path $InstallRoot $directory
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    foreach ($runtimeFile in Get-ChildItem -LiteralPath $source -Recurse -File) {
        $relative = $directory + '/' + $runtimeFile.FullName.Substring($source.Length+1).Replace('\','/')
        $runtimeTarget = Join-Path $InstallRoot $relative
        if ((Test-Path -LiteralPath $runtimeTarget) -and (Get-FileHash -LiteralPath $runtimeTarget -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $runtimeFile.FullName -Algorithm SHA256).Hash) { continue }
        Backup-File $runtimeTarget $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $runtimeTarget) -Force | Out-Null
        Copy-Item -LiteralPath $runtimeFile.FullName -Destination $runtimeTarget -Force
    }
}
if (Test-Path -LiteralPath $optifine) {
    New-Item -ItemType Directory -Path (Join-Path $InstallRoot 'mods') -Force | Out-Null
    $optifineTarget = Join-Path $InstallRoot ('mods\' + $optifineName)
    Backup-File $optifineTarget ('mods/' + $optifineName)
    Copy-Item -LiteralPath $optifine -Destination $optifineTarget -Force
}
$optionsPath = Join-Path $InstallRoot 'options.txt'
Backup-File $optionsPath 'options.txt'
if (-not (Test-Path -LiteralPath $optionsPath)) {
    Copy-Item -LiteralPath (Join-Path $stage ('PRESETS\options-' + $Language + '.txt')) -Destination $optionsPath
}
$options = [IO.File]::ReadAllText($optionsPath)
$resourceMatch = [regex]::Match($options, '(?m)^resourcePacks:([^\r\n]*)')
$resources = @()
if ($resourceMatch.Success) {
    $decodedResources = ConvertFrom-Json -InputObject $resourceMatch.Groups[1].Value.Trim()
    foreach ($value in $decodedResources) {
        if ($value -is [string]) { if ($value -notmatch '^@\{value=') { $resources += $value } }
        elseif ($value.value) { foreach ($legacy in $value.value) { if ($legacy -is [string]) { $resources += $legacy } } }
    }
}
$resources = @($resources | Where-Object { $_ -notin @('Warfare-UI-fixes.zip','Warfare-Combat-Audio.zip') }) + @('Warfare-UI-fixes.zip','Warfare-Combat-Audio.zip')
$resourceLine = 'resourcePacks:' + (ConvertTo-Json -InputObject @($resources) -Compress)
if ($resourceMatch.Success) { $options = [regex]::Replace($options, '(?m)^resourcePacks:[^\r\n]*', $resourceLine) } else { $options += "`n$resourceLine`n" }
[IO.File]::WriteAllText($optionsPath, $options, [Text.UTF8Encoding]::new($false))
if (-not (Test-Path -LiteralPath (Join-Path $InstallRoot 'optionsshaders.txt'))) {
    Backup-File (Join-Path $InstallRoot 'optionsshaders.txt') 'optionsshaders.txt'
    Copy-Item -LiteralPath (Join-Path $stage 'PRESETS\optionsshaders.txt') -Destination (Join-Path $InstallRoot 'optionsshaders.txt')
}
if ($initialPerformance) {
    Backup-File (Join-Path $InstallRoot 'config\rv-client.properties') 'config/rv-client.properties'
    $initialProfile = Get-WarfareInitialProfile
    Set-WarfarePerformanceProfile -Root $InstallRoot -Profile $initialProfile -Language $Language -ApplyGraphics -Installer
    if ($initialProfile -eq 'low') { Say 'Профиль: слабый ПК. Его можно изменить в настройках.' 'Profile: Low. You can change it in Settings.' }
    else { Say 'Профиль: баланс. Его можно изменить в настройках.' 'Profile: Balanced. You can change it in Settings.' }
} elseif (-not $clientPreferencesExisted) {
    Backup-File (Join-Path $InstallRoot 'config\rv-client.properties') 'config/rv-client.properties'
    Set-WarfarePerformanceProfile -Root $InstallRoot -Language $Language -LanguageOnly -Installer
}
if(Get-Command Initialize-WarfareClientControls -ErrorAction SilentlyContinue){$null=Initialize-WarfareClientControls -Root $InstallRoot -ReleasePath (Join-Path $packageRoot 'release.json')}
$settings = if ($previousSettings) { $previousSettings } else { [PSCustomObject]@{} }
$connection = Get-WarfareConnection -Settings $settings -Defaults $connectionDefaults
$settings = Set-WarfareConnection -Settings $settings -Connection $connection
if(-not $previousSettings -and [version]$release.version -ge [version]'2.0.4'){
    $friendsConnection=[PSCustomObject]@{connectionMode='porthole';connectionTarget='';serverPort=25565}
    if($connection.connectionTarget){try{$friendsConnection=ConvertTo-WarfareConnection $connection.connectionMode $connection.connectionTarget ([string]$connection.serverPort)}catch{}}
    $settings|Add-Member -MemberType NoteProperty -Name playMode -Value 'local' -Force
    $settings|Add-Member -MemberType NoteProperty -Name playProfiles -Value ([PSCustomObject]@{
        friends=$friendsConnection
        owner=[PSCustomObject]@{connectionMode='porthole';connectionTarget='';serverPort=25565}
        host=[PSCustomObject]@{port=25565}
    }) -Force
}
$settings | Add-Member -MemberType NoteProperty -Name language -Value $Language -Force
$settings | Add-Member -MemberType NoteProperty -Name nickname -Value $Nickname -Force
Backup-File $settingsPath 'warfare-settings.json'
[IO.File]::WriteAllText($settingsPath, ($settings | ConvertTo-Json -Depth 32), [Text.UTF8Encoding]::new($false))
foreach ($name in @('Play-Warfare.ps1','Play.cmd','installer-files.json','Warfare-Launcher.ps1','Warfare-Connection.ps1','Warfare-Performance.ps1','Warfare-Ambience.ps1','Warfare-ClientMods.ps1','Warfare-Onboarding.ps1','Configure-FirstPlay.ps1','Warfare-Updates.ps1','Check-WarfareUpdate.ps1','Configure-Controller.ps1','release.json','code.ico')) {
    Backup-File (Join-Path $InstallRoot $name) $name
    Copy-Item -LiteralPath (Join-Path $packageRoot $name) -Destination (Join-Path $InstallRoot $name) -Force
}
if ($release.vendorCatalogSha256) {
    foreach($name in @('Warfare-VendorDownloads.ps1','vendor-catalog.json')) {
        Backup-File (Join-Path $InstallRoot $name) $name
        Copy-Item -LiteralPath (Join-Path $packageRoot $name) -Destination (Join-Path $InstallRoot $name) -Force
    }
}
if (Test-Path -LiteralPath $defaultsPath) {
    Backup-File (Join-Path $InstallRoot 'server-defaults.json') 'server-defaults.json'
    Copy-Item -LiteralPath $defaultsPath -Destination (Join-Path $InstallRoot 'server-defaults.json') -Force
}
Backup-File $oldManifestPath 'installed-manifest.json'
if([version]$release.version -ge [version]'2.0.0'){
    foreach($name in @('Warfare-ClientControls.ps1','Warfare-ConnectionProfiles.ps1')){
        Backup-File (Join-Path $InstallRoot $name) $name
        Copy-Item -LiteralPath (Join-Path $packageRoot $name) -Destination (Join-Path $InstallRoot $name) -Force
    }
}
if([version]$release.version -ge [version]'2.0.4'){
    foreach($name in @('Warfare-PlayModes.ps1','Warfare-SelfHost.ps1','self-host-package.json','self-host-world.zip')){
        $source=Join-Path $packageRoot $name
        if(-not(Test-Path -LiteralPath $source -PathType Leaf)){throw ('Required host file is missing: '+$name)}
        $target=Join-Path $InstallRoot $name
        Backup-File $target $name
        Copy-Item -LiteralPath $source -Destination $target -Force
    }
}
if(-not $previousSettings -and [version]$release.version -ge [version]'2.0.4'){$null=Install-WarfareWorldTemplate $packageRoot $InstallRoot}
Copy-Item -LiteralPath (Join-Path $packageRoot 'package-manifest.json') -Destination $oldManifestPath -Force
} catch {
    for ($index=$rollback.Count-1; $index -ge 0; $index--) {
        $item = $rollback[$index]
        if ($item.existed) { Copy-Item -LiteralPath $item.backup -Destination $item.target -Force }
        elseif (Test-Path -LiteralPath $item.target) { Remove-Item -LiteralPath $item.target }
    }
    throw
}
if (-not $NoShortcut) {
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop 'RV.lnk'
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $canSaveShortcut = -not (Test-Path -LiteralPath $shortcutPath) -or ($shortcut.TargetPath -eq (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -and $shortcut.Arguments.Contains($InstallRoot) -and $shortcut.Arguments.Contains('Warfare-Launcher.ps1'))
    if (-not $canSaveShortcut) {
        $shortcutPath = Join-Path $desktop 'RV Client.lnk'
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $canSaveShortcut = -not (Test-Path -LiteralPath $shortcutPath) -or ($shortcut.TargetPath -eq (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -and $shortcut.Arguments.Contains($InstallRoot) -and $shortcut.Arguments.Contains('Warfare-Launcher.ps1'))
    }
    if ($canSaveShortcut) {
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "' + (Join-Path $InstallRoot 'Warfare-Launcher.ps1') + '" -InstallRoot "' + $InstallRoot + '"'
    $shortcut.WorkingDirectory = $InstallRoot
    $shortcut.Description = 'RV'
    $shortcut.IconLocation = (Join-Path $InstallRoot 'code.ico') + ',0'
    $shortcut.Save()
    $legacyShortcutPath = Join-Path $desktop 'Warfare.lnk'
    if ($legacyShortcutPath -ne $shortcutPath -and (Test-Path -LiteralPath $legacyShortcutPath)) {
        $legacyShortcut = $shell.CreateShortcut($legacyShortcutPath)
        if ($legacyShortcut.TargetPath -eq $shortcut.TargetPath -and $legacyShortcut.Arguments.Contains($InstallRoot) -and $legacyShortcut.Arguments.Contains('Warfare-Launcher.ps1')) {
            $shortcutBackup = Join-Path $backup 'shortcuts'
            New-Item -ItemType Directory -Path $shortcutBackup -Force | Out-Null
            Copy-Item -LiteralPath $legacyShortcutPath -Destination (Join-Path $shortcutBackup 'Warfare.lnk')
            Remove-Item -LiteralPath $legacyShortcutPath
        }
    }
    }
}
$stageAbsolute = [IO.Path]::GetFullPath($stage)
if (-not $stageAbsolute.StartsWith($InstallRoot.TrimEnd('\') + '\.update-', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe staging directory.' }
Remove-Item -LiteralPath $stageAbsolute -Recurse -Force
Say ('Готово. Запуск: ' + (Join-Path $InstallRoot 'Play.cmd')) ('Ready. Start: ' + (Join-Path $InstallRoot 'Play.cmd'))
Say 'Обновления доступны в окне RV. Миры и настройки сохраняются.' 'Updates are available in RV. Worlds and settings are preserved.'
} finally {
    if ($installLock) { Exit-WarfareClientOperation $installLock }
}
if (-not $NoSteam) {
    & (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -NoProfile -ExecutionPolicy Bypass -File (Join-Path $InstallRoot 'Play-Warfare.ps1') -Prepare
    if ($LASTEXITCODE -ne 0) { throw 'Steam/Porthole setup failed / Не удалось подготовить Steam/Porthole.' }
}
if (-not $NoLaunch) {
    Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "' + (Join-Path $InstallRoot 'Warfare-Launcher.ps1') + '" -InstallRoot "' + $InstallRoot + '"') -WindowStyle Hidden
}
