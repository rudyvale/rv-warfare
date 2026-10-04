if ($PSVersionTable.PSEdition -eq 'Desktop') {
    $env:PSModulePath = $PSHOME + '\Modules;' + $env:PSModulePath
    Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
}
$script:VmRepository = 'rudyvale/rv-warfare'
function Get-VmVersion([string]$Value) {
    if ($Value -notmatch '^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$') { throw 'Invalid release version.' }
    return [version]($Value.TrimStart('v'))
}
function Get-VmPackageFiles([string]$Version) {
    $names=@('Install-Warfare.ps1','Warfare-Launcher.ps1','Play-Warfare.ps1','Play.cmd','Warfare-Connection.ps1','Warfare-Updates.ps1','Check-WarfareUpdate.ps1','Configure-Controller.ps1','package-manifest.json','installer-files.json','payload.zip','runtime.zip','release.json','code.ico')
    $parsed=Get-VmVersion $Version
    if($parsed -ge [version]'1.1.0'){$names+=@('Warfare-Performance.ps1','Warfare-Onboarding.ps1','Configure-FirstPlay.ps1','THIRD-PARTY-NOTICES.md')}
    if($parsed -ge [version]'1.2.0'){$names+=@('Warfare-Ambience.ps1','Warfare-ClientMods.ps1','Warfare-VendorDownloads.ps1','vendor-catalog.json','rv-managed-mods.json')}
    if($parsed -ge [version]'2.0.0'){$names+=@('Warfare-ClientControls.ps1','Warfare-ConnectionProfiles.ps1','READ-ME.md')}
    if($parsed -ge [version]'2.0.4'){$names+=@('Warfare-PlayModes.ps1','Warfare-SelfHost.ps1','self-host-package.json','self-host-world.zip')}
    return $names
}
function Get-VmLocalVersion([string]$Root) {
    try { return [string](Get-Content -LiteralPath (Join-Path $Root 'release.json') -Raw -Encoding UTF8 | ConvertFrom-Json).version } catch { return '0.0.0' }
}
function Assert-VmUpgrade([string]$PackageRoot, [string]$InstallRoot) {
    $installed = Get-VmVersion (Get-VmLocalVersion $InstallRoot)
    $package = Get-VmVersion (Get-VmLocalVersion $PackageRoot)
    if ($installed -gt $package) { throw 'A newer RV version is already installed. Use the latest installer from GitHub.' }
}
function Write-VmJson([string]$Path, $Value) {
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($temporary, $Path, [NullString]::Value) } else { [IO.File]::Move($temporary, $Path) }
}
function Get-VmAutoCheck([string]$Root) {
    try {
        $preferences = Get-Content -LiteralPath (Join-Path $Root '.updates\preferences.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($preferences.autoCheck -is [bool]) { return [bool]$preferences.autoCheck }
    } catch { }
    return $true
}
function Set-VmAutoCheck([string]$Root, [bool]$Enabled) {
    $directory = Join-Path $Root '.updates'
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    Write-VmJson (Join-Path $directory 'preferences.json') @{autoCheck=$Enabled}
}
function Get-VmRelease {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    return Invoke-RestMethod -Uri ('https://api.github.com/repos/' + $script:VmRepository + '/releases/latest') -Headers @{Accept='application/vnd.github+json';'User-Agent'='RV-Warfare-Update';'X-GitHub-Api-Version'='2022-11-28'} -TimeoutSec 8
}
function ConvertTo-VmRelease($Release, [string]$CurrentVersion) {
    if ($Release.draft -or $Release.prerelease) { throw 'Only stable releases are accepted.' }
    $version = Get-VmVersion ([string]$Release.tag_name)
    $current = Get-VmVersion $CurrentVersion
    $asset = @($Release.assets | Where-Object { $_.name -ceq 'RV-Setup.zip' })
    if ($asset.Count -ne 1 -or $asset[0].state -ne 'uploaded') { throw 'Release package is missing.' }
    $url = 'https://github.com/' + $script:VmRepository + '/releases/download/' + $Release.tag_name + '/RV-Setup.zip'
    if ($asset[0].browser_download_url -cne $url) { throw 'Unexpected download origin.' }
    if ($asset[0].digest -cnotmatch '^sha256:[a-f0-9]{64}$') { throw 'Release checksum is missing.' }
    if ([long]$asset[0].size -le 0 -or [long]$asset[0].size -gt 2147483648) { throw 'Invalid release size.' }
    return [ordered]@{state=$(if ($version -gt $current) {'available'} else {'current'});currentVersion=$CurrentVersion;version=$version.ToString();tag=[string]$Release.tag_name;url=$url;sha256=([string]$asset[0].digest).Substring(7);size=[long]$asset[0].size;checkedAt=[DateTime]::UtcNow.ToString('o');releaseUrl=('https://github.com/' + $script:VmRepository + '/releases/tag/' + $Release.tag_name)}
}
function Start-VmUpdateCheck([string]$Root, [string]$SourceRoot = $PSScriptRoot) {
    if ($env:VM_SKIP_UPDATE_CHECK -eq '1' -or -not (Get-VmAutoCheck $Root)) { return }
    try {
        $worker = Join-Path $SourceRoot 'Check-WarfareUpdate.ps1'
        if (-not (Test-Path -LiteralPath $worker)) { return }
        $version = (Get-VmVersion (Get-VmLocalVersion $Root)).ToString()
        $shell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $worker + '" -Root "' + $Root.TrimEnd('\') + '" -CurrentVersion "' + $version + '"'
        Start-Process -FilePath $shell -ArgumentList $arguments -WindowStyle Hidden | Out-Null
    } catch { }
}
function Test-VmPackageHash([string]$Path, [string]$Expected) {
    if ($Expected -cnotmatch '^[a-f0-9]{64}$' -or (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Expected) { throw 'Downloaded package checksum mismatch.' }
}
function Expand-VmPackage([string]$Archive, [string]$Destination, [string]$Version) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        $total = [long]0
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.Replace('\','/')
            if (-not $name.StartsWith('RV-Setup/') -or $name -match '(^|/)\.{1,2}(/|$)|:|^/|[\x00-\x1f]' -or -not $seen.Add($name)) { throw 'Unsafe package entry.' }
            foreach ($segment in $name.Split('/')) { if ($segment -match '[. ]$') { throw 'Unsafe package path.' } }
            $total += $entry.Length
            if ($total -gt 4294967296 -or $zip.Entries.Count -gt 5000) { throw 'Package is too large.' }
        }
        $releaseEntry = $zip.GetEntry('RV-Setup/release.json')
        if (-not $releaseEntry -or $releaseEntry.Length -gt 4096) { throw 'Package version is missing.' }
        $reader = [IO.StreamReader]::new($releaseEntry.Open())
        try { $metadata = $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
        if ($metadata.version -cne $Version -or $metadata.repository -cne $script:VmRepository) { throw 'Package version does not match the release.' }
        foreach ($name in @('Install-Warfare.ps1','Warfare-Launcher.ps1','Play-Warfare.ps1','Warfare-Connection.ps1','Warfare-Updates.ps1','Check-WarfareUpdate.ps1','Configure-Controller.ps1','package-manifest.json','installer-files.json','payload.zip','runtime.zip','code.ico')) {
            if (-not $zip.GetEntry('RV-Setup/' + $name)) { throw ('Incomplete package: ' + $name) }
        }
        if ((Get-VmVersion $Version) -ge [version]'1.1.0') {
            if (-not $zip.GetEntry('RV-Setup/Warfare-Performance.ps1')) { throw 'Incomplete package: Warfare-Performance.ps1' }
            foreach ($name in @('Warfare-Onboarding.ps1','Configure-FirstPlay.ps1','THIRD-PARTY-NOTICES.md')) {
                if (-not $zip.GetEntry('RV-Setup/' + $name)) { throw ('Incomplete package: ' + $name) }
            }
            if ($metadata.requiredMods -isnot [PSCustomObject] -or $metadata.requiredMods.mcheli -isnot [string] -or $metadata.requiredMods.mcheli -cnotmatch '^\S{1,128}$') { throw 'Package server protocol version is missing.' }
        }
        if((Get-VmVersion $Version) -ge [version]'2.0.0'){foreach($name in Get-VmPackageFiles $Version){if(-not $zip.GetEntry('RV-Setup/'+$name)){throw ('Incomplete package: '+$name)}}}
    } finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($Archive, $Destination)
    return Join-Path $Destination 'RV-Setup'
}
