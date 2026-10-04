[CmdletBinding()]
param(
    [switch]$SelfHostWorker,
    [string]$WorkerGameRoot,
    [string]$WorkerInstanceId
)

$ErrorActionPreference = 'Stop'

function Get-WarfareSelfHostPaths([string]$GameRoot) {
    if (-not $GameRoot) { throw 'GameRoot is required.' }
    $root = [IO.Path]::GetFullPath($GameRoot)
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { throw 'The selected game folder does not exist.' }
    $private = Join-Path $root '.rv-selfhost'
    [pscustomobject]@{
        GameRoot = $root
        PrivateRoot = $private
        ServerRoot = Join-Path $private 'server'
        ControlRoot = Join-Path $private 'control'
        StatePath = Join-Path $private 'control\state.json'
        CommandPath = Join-Path $private 'control\command.json'
        LogPath = Join-Path $private 'control\supervisor.log'
        DescriptorPath = Join-Path $root 'self-host-package.json'
        InstallerFilesPath = Join-Path $root 'installer-files.json'
        PackageManifestPath = Join-Path $root 'installed-manifest.json'
        VendorCatalogPath = Join-Path $root 'vendor-catalog.json'
        ReleasePath = Join-Path $root 'release.json'
        JavaPath = Join-Path $root 'runtime\bin\java.exe'
    }
}

function Assert-WarfareSelfHostPath([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($item -and (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw 'A self-host path is a link or reparse point. No files were changed.'
    }
}

function ConvertTo-WarfareSelfHostPath([string]$Root, [string]$RelativePath) {
    if (-not $RelativePath -or [IO.Path]::IsPathRooted($RelativePath) -or $RelativePath -match '(^|[\\/])\.\.?([\\/]|$)' -or $RelativePath -match '^[A-Za-z]:') {
        throw 'The self-host package contains an unsafe path.'
    }
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $path = [IO.Path]::GetFullPath((Join-Path $rootFull ($RelativePath.Replace('/', '\'))))
    if (-not $path.StartsWith($rootFull + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'The self-host package path escapes the game folder.' }
    return $path
}

function Get-WarfareSelfHostHash([string]$Path, [ValidateSet('SHA1','SHA256')][string]$Algorithm = 'SHA256') {
    (Get-FileHash -LiteralPath $Path -Algorithm $Algorithm -ErrorAction Stop).Hash.ToLowerInvariant()
}

function Get-WarfareSelfHostTextHash([string]$Text) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text)))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Read-WarfareSelfHostJson([string]$Path) {
    Assert-WarfareSelfHostPath $Path
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    if ((Get-Item -LiteralPath $Path).Length -gt 1048576) { throw 'Self-host state file is too large.' }
    Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
}

function Write-WarfareSelfHostJson([string]$Path, $Value) {
    $parent = Split-Path -Parent $Path
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    Assert-WarfareSelfHostPath $parent
    Assert-WarfareSelfHostPath $Path
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 12 -Compress), [Text.UTF8Encoding]::new($false))
    try {
        if (Test-Path -LiteralPath $Path -PathType Leaf) { [IO.File]::Replace($temporary, $Path, [NullString]::Value) }
        else { [IO.File]::Move($temporary, $Path) }
    } finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function Enter-WarfareSelfHostLock([string]$GameRoot) {
    $bytes = [Text.Encoding]::UTF8.GetBytes([IO.Path]::GetFullPath($GameRoot).ToLowerInvariant())
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $key = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').Substring(0, 32) } finally { $sha.Dispose() }
    $mutex = [Threading.Mutex]::new($false, ('Local\RV-SelfHost-' + $key))
    try { $acquired = $mutex.WaitOne(15000) } catch [Threading.AbandonedMutexException] { $acquired = $true }
    if (-not $acquired) { $mutex.Dispose(); throw 'Another self-host start or stop is still running. Wait and retry.' }
    Write-Output -NoEnumerate $mutex
}

function Get-WarfareSelfHostWmiProcess([int]$ProcessId) {
    if ($ProcessId -le 0) { return $null }
    Get-CimInstance -ClassName Win32_Process -Filter ('ProcessId=' + $ProcessId) -ErrorAction SilentlyContinue
}

function Get-WarfareSelfHostStartMilliseconds($Process) {
    if (-not $Process -or -not $Process.CreationDate) { return 0 }
    $time = if ($Process.CreationDate -is [DateTime]) { ([DateTime]$Process.CreationDate).ToUniversalTime() } else { [Management.ManagementDateTimeConverter]::ToDateTime([string]$Process.CreationDate).ToUniversalTime() }
    [DateTimeOffset]::new($time).ToUnixTimeMilliseconds()
}

function Get-WarfareSelfHostPowerShellPath {
    Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
}

function Test-WarfareSelfHostWorkerProcess($State) {
    $process = Get-WarfareSelfHostWmiProcess ([int]$State.workerPid)
    if (-not $process -or -not $process.CommandLine -or -not $process.ExecutablePath) { return $false }
    if (-not [string]::Equals([IO.Path]::GetFullPath($process.ExecutablePath), [IO.Path]::GetFullPath([string]$State.workerExecutable), [StringComparison]::OrdinalIgnoreCase)) { return $false }
    if (-not [string]::Equals([IO.Path]::GetFullPath($process.ExecutablePath), [IO.Path]::GetFullPath((Get-WarfareSelfHostPowerShellPath)), [StringComparison]::OrdinalIgnoreCase)) { return $false }
    if ([Math]::Abs((Get-WarfareSelfHostStartMilliseconds $process) - [long]$State.workerStartedAtUnixMs) -gt 1000) { return $false }
    if ((Get-WarfareSelfHostTextHash ([string]$process.CommandLine)) -ne [string]$State.workerCommandLineSha256) { return $false }
    return $true
}

function Test-WarfareSelfHostJavaProcess($State) {
    $process = Get-WarfareSelfHostWmiProcess ([int]$State.javaPid)
    if (-not $process -or -not $process.CommandLine -or -not $process.ExecutablePath) { return $false }
    if (-not [string]::Equals([IO.Path]::GetFullPath($process.ExecutablePath), [IO.Path]::GetFullPath([string]$State.javaExecutable), [StringComparison]::OrdinalIgnoreCase)) { return $false }
    if ([Math]::Abs((Get-WarfareSelfHostStartMilliseconds $process) - [long]$State.javaStartedAtUnixMs) -gt 1000) { return $false }
    if ((Get-WarfareSelfHostTextHash ([string]$process.CommandLine)) -ne [string]$State.javaCommandLineSha256) { return $false }
    if (-not $process.CommandLine.Contains([string]$State.instanceMarker) -or -not $process.CommandLine.Contains([string]$State.serverJar)) { return $false }
    if (-not $process.CommandLine.Contains('net.minecraftforge.fml.relauncher.ServerLaunchWrapper')) { return $false }
    return $true
}

function Quote-WarfareSelfHostWindowsArgument([string]$Value) {
    $builder = [Text.StringBuilder]::new()
    [void]$builder.Append('"')
    $slashes = 0
    foreach ($character in ([string]$Value).ToCharArray()) {
        if ($character -eq '\') { $slashes++; continue }
        if ($character -eq '"') {
            [void]$builder.Append(('\' * (($slashes * 2) + 1)))
            [void]$builder.Append('"')
            $slashes = 0
            continue
        }
        if ($slashes) { [void]$builder.Append(('\' * $slashes)); $slashes = 0 }
        [void]$builder.Append($character)
    }
    if ($slashes) { [void]$builder.Append(('\' * ($slashes * 2))) }
    [void]$builder.Append('"')
    $builder.ToString()
}

function Assert-WarfareSelfHostPortAvailable([int]$Port) {
    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count) { throw ('Port ' + $Port + ' is already occupied.') }
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Any, $Port)
    try { $listener.Server.ExclusiveAddressUse = $true; $listener.Start() }
    catch { throw ('Port ' + $Port + ' is already occupied.') }
    finally { if ($listener -and $listener.Server.IsBound) { $listener.Stop() } }
}

function Get-WarfareSelfHostServerJarPin($Descriptor) {
    $url = 'https://piston-data.mojang.com/v1/objects/886945bfb2b978778c3a0288fd7fab09d315b25f/server.jar'
    if (-not $Descriptor.serverJar -or [string]$Descriptor.serverJar.url -cne $url -or [string]$Descriptor.serverJar.sha1 -cne '886945bfb2b978778c3a0288fd7fab09d315b25f' -or [long]$Descriptor.serverJar.size -ne 30222121) {
        throw 'The self-host package does not match the pinned Minecraft 1.12.2 server file.'
    }
    [pscustomobject]@{ url = $url; sha1 = '886945bfb2b978778c3a0288fd7fab09d315b25f'; size = 30222121 }
}

function Get-WarfareSelfHostDescriptor($Paths) {
    $descriptor = Read-WarfareSelfHostJson $Paths.DescriptorPath
    if (-not $descriptor -or [int]$descriptor.schema -ne 1 -or [string]$descriptor.minecraftVersion -cne '1.12.2' -or [string]$descriptor.forgeVersion -cne '14.23.5.2860') {
        throw 'Self-host package metadata is missing or incompatible. Update the RV client first.'
    }
    $null = Get-WarfareSelfHostServerJarPin $descriptor
    if ($descriptor.serverModIds -isnot [System.Array] -or $descriptor.clientOnlyModIds -isnot [System.Array]) { throw 'Self-host mod metadata is invalid.' }
    foreach ($id in @($descriptor.serverModIds) + @($descriptor.clientOnlyModIds)) {
        if ([string]$id -notmatch '^[a-z0-9][a-z0-9_.-]{0,63}$') { throw 'Self-host package contains an invalid Forge mod ID.' }
    }
    if ($descriptor.worldTemplate) {
        if (-not $descriptor.worldTemplate.path -or [string]$descriptor.worldTemplate.sha256 -notmatch '^[0-9a-f]{64}$' -or [long]$descriptor.worldTemplate.size -le 0) {
            throw 'Self-host world template metadata is invalid.'
        }
    }
    return $descriptor
}

function Invoke-WarfareSelfHostPinnedDownload($Pin, [string]$Destination) {
    Assert-WarfareSelfHostPath $Destination
    if (Test-Path -LiteralPath $Destination) { throw 'Refusing to overwrite an existing self-host server file.' }
    $temporary = $Destination + '.' + [Guid]::NewGuid().ToString('N') + '.download'
    $oldProtocol = [Net.ServicePointManager]::SecurityProtocol
    try {
        [Net.ServicePointManager]::SecurityProtocol = $oldProtocol -bor [Net.SecurityProtocolType]::Tls12
        $client = [Net.WebClient]::new()
        try { $client.DownloadFile([string]$Pin.url, $temporary) } finally { $client.Dispose() }
        if ((Get-Item -LiteralPath $temporary).Length -ne [long]$Pin.size -or (Get-WarfareSelfHostHash $temporary SHA1) -ne [string]$Pin.sha1) {
            throw 'The downloaded Minecraft server JAR did not match its pinned size and SHA-1.'
        }
        [IO.File]::Move($temporary, $Destination)
    } finally {
        [Net.ServicePointManager]::SecurityProtocol = $oldProtocol
        if (Test-Path -LiteralPath $temporary -PathType Leaf) { Remove-Item -LiteralPath $temporary -Force }
    }
}

function Get-WarfareSelfHostClasspath($Paths, $ServerJar) {
    if (-not (Test-Path -LiteralPath $Paths.JavaPath -PathType Leaf)) { throw 'Java 8 is missing from the installed client. Run the installer again.' }
    $installer = Read-WarfareSelfHostJson $Paths.InstallerFilesPath
    if (-not $installer -or $installer.classpath -isnot [System.Array] -or $installer.files -isnot [System.Array]) { throw 'The installed Forge library manifest is invalid.' }
    $records = @{}
    foreach ($file in $installer.files) {
        $key = ([string]$file.path).ToLowerInvariant()
        if (-not $key -or $records.ContainsKey($key)) { throw 'The installed Forge library manifest has duplicate paths.' }
        $records[$key] = $file
    }
    $result = [Collections.Generic.List[string]]::new()
    $forgeJar = $null
    foreach ($relative in $installer.classpath) {
        $relative = [string]$relative
        if ($relative -ceq 'versions/1.12.2/1.12.2.jar') { continue }
        if ($relative -notmatch '^libraries/[A-Za-z0-9._+/-]+\.jar$') { throw 'The Forge classpath contains an unsafe entry.' }
        $key = $relative.ToLowerInvariant()
        if (-not $records.ContainsKey($key) -or [string]$records[$key].sha1 -notmatch '^[0-9a-f]{40}$') { throw ('Missing SHA-1 pin for ' + $relative) }
        $full = ConvertTo-WarfareSelfHostPath $Paths.GameRoot $relative
        Assert-WarfareSelfHostPath $full
        if (-not (Test-Path -LiteralPath $full -PathType Leaf) -or (Get-WarfareSelfHostHash $full SHA1) -ne [string]$records[$key].sha1) {
            throw ('Missing or damaged Forge library: ' + $relative)
        }
        $result.Add($full)
        if ($relative -match '^libraries/net/minecraftforge/forge/1\.12\.2-14\.23\.5\.2860/forge-1\.12\.2-14\.23\.5\.2860\.jar$') { $forgeJar = $full }
    }
    if (-not $forgeJar) { throw 'The installed Forge 1.12.2 server wrapper is missing.' }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($forgeJar)
    try {
        if (-not $archive.GetEntry('net/minecraftforge/fml/relauncher/ServerLaunchWrapper.class')) { throw 'The Forge JAR has no dedicated-server launch wrapper.' }
    } finally { $archive.Dispose() }
    [void]$result.Remove($forgeJar)
    $result.Insert(0, $forgeJar)
    $result.Insert(1, $ServerJar)
    return ,$result.ToArray()
}

function Get-WarfareSelfHostModIds([string]$JarPath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($JarPath)
    try {
        $entry = $archive.GetEntry('mcmod.info')
        $ids = @()
        if ($entry -and $entry.Length -le 131072) {
            $reader = [IO.StreamReader]::new($entry.Open(), [Text.Encoding]::UTF8, $true)
            try { $data = $reader.ReadToEnd() | ConvertFrom-Json -ErrorAction Stop } finally { $reader.Dispose() }
            $records = if ($data -is [System.Array]) { @($data) } elseif ($data.modList -is [System.Array]) { @($data.modList) } elseif ($data.modid) { @($data) } else { @() }
            $ids = @($records | ForEach-Object { [string]$_.modid } | Where-Object { $_ -match '^[a-z0-9][a-z0-9_.-]{0,63}$' } | Select-Object -Unique)
        }
        if ($ids.Count) { return $ids }
        $name = [IO.Path]::GetFileName($JarPath)
        if ($name -match '^rv-vehicle-compat-') { return @('rvcompat') }
        if ($name -match '^rv-experience-') { return @('rvexperience') }
        return @()
    } finally { $archive.Dispose() }
}

function Copy-WarfareSelfHostTree([string]$Source, [string]$Destination) {
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) { return }
    $sourceFull = [IO.Path]::GetFullPath($Source).TrimEnd('\')
    [IO.Directory]::CreateDirectory($Destination) | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $sourceFull -Force -Recurse) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
        $relative = $item.FullName.Substring($sourceFull.Length).TrimStart('\')
        $target = [IO.Path]::GetFullPath((Join-Path $Destination $relative))
        $destinationFull = [IO.Path]::GetFullPath($Destination).TrimEnd('\')
        if (-not $target.StartsWith($destinationFull + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Self-host data escaped its staging folder.' }
        if ($item.PSIsContainer) { [IO.Directory]::CreateDirectory($target) | Out-Null }
        else {
            [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
            [IO.File]::Copy($item.FullName, $target, $false)
        }
    }
}

function Get-WarfareSelfHostModPolicy($Paths, $Descriptor) {
    $release = Read-WarfareSelfHostJson $Paths.ReleasePath
    $catalog = Read-WarfareSelfHostJson $Paths.VendorCatalogPath
    if (-not $release -or -not $release.requiredMods -or -not $catalog) { throw 'Installed server mod metadata is incomplete.' }
    if ([string]$release.vendorCatalogSha256 -notmatch '^[a-f0-9]{64}$' -or (Get-WarfareSelfHostHash $Paths.VendorCatalogPath SHA256) -cne [string]$release.vendorCatalogSha256) { throw 'Installed vendor metadata failed verification.' }
    $server = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $client = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($id in @($Descriptor.serverModIds)) { [void]$server.Add([string]$id) }
    foreach ($id in $release.requiredMods.PSObject.Properties.Name) { [void]$server.Add([string]$id) }
    foreach ($file in @($catalog.baseline.files) + @($catalog.files)) {
        foreach ($id in @($file.expectedModIds)) {
            if ([string]$file.side -eq 'both') { [void]$server.Add([string]$id) }
            elseif ([string]$file.side -eq 'client') { [void]$client.Add([string]$id) }
        }
    }
    foreach ($id in @($Descriptor.clientOnlyModIds)) { [void]$client.Add([string]$id) }
    foreach ($id in $release.clientRequiredMods.PSObject.Properties.Name) {
        if (-not $release.requiredMods.PSObject.Properties[$id]) { [void]$client.Add([string]$id) }
    }
    $modRoot = Join-Path $Paths.GameRoot 'mods'
    if (Test-Path -LiteralPath $modRoot -PathType Container) {
        $installedIds = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        foreach ($jar in Get-ChildItem -LiteralPath $modRoot -Filter '*.jar' -File) {
            if (($jar.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
            foreach ($id in @(Get-WarfareSelfHostModIds $jar.FullName)) { [void]$installedIds.Add($id) }
        }
        foreach ($id in @('mixinbooter','brigo','elegant_networking','foamfix','modularui','worldedit')) {
            if ($installedIds.Contains($id)) { [void]$server.Add($id) }
        }
    }
    $conflicts = @($server | Where-Object { $client.Contains($_) })
    if ($conflicts.Count) { throw ('Mod metadata marks server mods as client-only: ' + ($conflicts -join ', ')) }
    return [pscustomobject]@{ ServerIds = $server; ClientIds = $client; Catalog = $catalog }
}

function Copy-WarfareSelfHostMods($Paths, $Descriptor, [string]$Destination) {
    $modRoot = Join-Path $Paths.GameRoot 'mods'
    if (-not (Test-Path -LiteralPath $modRoot -PathType Container)) { throw 'The installed client mod folder is missing.' }
    $manifest = Read-WarfareSelfHostJson $Paths.PackageManifestPath
    if (-not $manifest -or $manifest.managedFiles -isnot [System.Array]) { throw 'The installed package file manifest is invalid.' }
    $policy = Get-WarfareSelfHostModPolicy $Paths $Descriptor
    $approved = @{}
    foreach ($entry in $manifest.managedFiles) {
        if ([string]$entry.path -match '^(mods|mcheli_addons)/[A-Za-z0-9._+! /-]+$' -and [string]$entry.sha256 -match '^[0-9a-f]{64}$') {
            $approved[[string]$entry.path.ToLowerInvariant()] = [string]$entry.sha256
        }
    }
    $copied = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($jar in Get-ChildItem -LiteralPath $modRoot -Filter '*.jar' -File) {
        if (($jar.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
        $ids = @(Get-WarfareSelfHostModIds $jar.FullName)
        if (-not $ids.Count -or @($ids | Where-Object { $policy.ClientIds.Contains($_) }).Count) { continue }
        $serverIds = @($ids | Where-Object { $policy.ServerIds.Contains($_) })
        if (-not $serverIds.Count) { continue }
        $relative = 'mods/' + $jar.Name
        $key = $relative.ToLowerInvariant()
        if (-not $approved.ContainsKey($key)) { throw ('Unpinned server mod refused: ' + $jar.Name) }
        if ((Get-WarfareSelfHostHash $jar.FullName SHA256) -ne $approved[$key]) { throw ('Installed server mod hash mismatch: ' + $jar.Name) }
        $target = ConvertTo-WarfareSelfHostPath $Destination $relative
        [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
        [IO.File]::Copy($jar.FullName, $target, $false)
        if ((Get-WarfareSelfHostHash $target SHA256) -ne $approved[$key]) { throw ('Server mod copy hash mismatch: ' + $jar.Name) }
        foreach ($id in $serverIds) { [void]$copied.Add($id) }
    }
    foreach ($file in @($policy.Catalog.baseline.files) + @($policy.Catalog.files)) {
        if ([string]$file.side -cne 'both' -or [string]$file.kind -cne 'content-pack' -or -not $file.path) { continue }
        $relative = [string]$file.path
        $key = $relative.ToLowerInvariant()
        if (-not $approved.ContainsKey($key)) { throw ('Unpinned server content pack refused: ' + $relative) }
        $source = ConvertTo-WarfareSelfHostPath $Paths.GameRoot $relative
        if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or (Get-WarfareSelfHostHash $source SHA256) -cne $approved[$key]) { throw ('Server content pack is missing or damaged: ' + $relative) }
        $target = ConvertTo-WarfareSelfHostPath $Destination $relative
        [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
        [IO.File]::Copy($source, $target, $false)
        if ((Get-WarfareSelfHostHash $target SHA256) -cne $approved[$key]) { throw ('Server content pack copy hash mismatch: ' + $relative) }
    }
    $required = @($policy.ServerIds)
    $missing = @($required | Where-Object { -not $copied.Contains($_) })
    if ($missing.Count) { throw ('Required server mods are missing or not approved: ' + ($missing -join ', ')) }
}

function Expand-WarfareSelfHostWorldTemplate($Descriptor, [string]$GameRoot, [string]$Destination) {
    if (-not $Descriptor.worldTemplate) { return $false }
    $archivePath = ConvertTo-WarfareSelfHostPath $GameRoot ([string]$Descriptor.worldTemplate.path)
    Assert-WarfareSelfHostPath $archivePath
    if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) { throw 'The packaged RV world template is missing.' }
    if ((Get-Item -LiteralPath $archivePath).Length -ne [long]$Descriptor.worldTemplate.size -or (Get-WarfareSelfHostHash $archivePath SHA256) -ne [string]$Descriptor.worldTemplate.sha256) {
        throw 'The RV world template failed its size or SHA-256 check.'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        if ($archive.Entries.Count -gt 100000) { throw 'The RV world template has too many entries.' }
        $entries = [Collections.Generic.List[object]]::new()
        $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        $total = [long]0
        foreach ($entry in $archive.Entries) {
            $name = [string]$entry.FullName
            if (-not $name -or $name.StartsWith('/') -or $name -match '^[A-Za-z]:' -or $name -match '(^|/)\.\.?(/|$)' -or $name.Contains('\')) { throw 'The RV world template contains an unsafe ZIP path.' }
            if ((([long]$entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) { throw 'The RV world template contains a symbolic link.' }
            $normalized = $name.TrimEnd('/')
            if (-not $normalized) { continue }
            if (-not $seen.Add($normalized)) { throw 'The RV world template contains duplicate paths.' }
            if ($entry.Length -gt 2147483648) { throw 'The RV world template contains an oversized entry.' }
            $total += [long]$entry.Length
            if ($total -gt 4294967296) { throw 'The RV world template is too large.' }
            $entries.Add([pscustomobject]@{ Entry = $entry; Name = $normalized; Directory = $entry.FullName.EndsWith('/') })
        }
        $files = @($entries | Where-Object { -not $_.Directory } | ForEach-Object Name)
        if (-not ($files | Where-Object { $_ -match '(^|/)level\.dat$' })) { throw 'The RV world template has no level.dat.' }
        $common = $null
        if ($files.Count -and @($files | Where-Object { $_ -notmatch '^[^/]+/' }).Count -eq 0) {
            $roots = @($files | ForEach-Object { $_.Split('/')[0] } | Select-Object -Unique)
            if ($roots.Count -eq 1) { $common = [string]$roots[0] }
        }
        [IO.Directory]::CreateDirectory($Destination) | Out-Null
        $destinationFull = [IO.Path]::GetFullPath($Destination).TrimEnd('\')
        foreach ($record in $entries) {
            $relative = [string]$record.Name
            if ($common) {
                if ($relative -ceq $common) { continue }
                if ($relative.StartsWith($common + '/', [StringComparison]::Ordinal)) { $relative = $relative.Substring($common.Length + 1) }
            }
            $target = [IO.Path]::GetFullPath((Join-Path $destinationFull ($relative.Replace('/', '\'))))
            if (-not $target.StartsWith($destinationFull + '\', [StringComparison]::OrdinalIgnoreCase) -or $target.Length -ge 260) { throw 'An RV world path is unsafe or too long for Windows.' }
            if ($record.Directory) { [IO.Directory]::CreateDirectory($target) | Out-Null }
            else {
                [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
                $input = $record.Entry.Open()
                try {
                    $output = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
                    try { $input.CopyTo($output) } finally { $output.Dispose() }
                } finally { $input.Dispose() }
            }
        }
    } finally { $archive.Dispose() }
    return $true
}

function Set-WarfareSelfHostProperty([string]$Path, [string]$Name, [string]$Value) {
    Assert-WarfareSelfHostPath $Path
    $lines = if (Test-Path -LiteralPath $Path -PathType Leaf) { @(Get-Content -LiteralPath $Path -Encoding UTF8) } else { @() }
    $found = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match ('^' + [regex]::Escape($Name) + '=')) { $lines[$index] = $Name + '=' + $Value; $found = $true }
    }
    if (-not $found) { $lines += $Name + '=' + $Value }
    $text = ($lines -join [Environment]::NewLine) + [Environment]::NewLine
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($temporary, $text, [Text.UTF8Encoding]::new($false))
    try {
        if (Test-Path -LiteralPath $Path -PathType Leaf) { [IO.File]::Replace($temporary, $Path, [NullString]::Value) }
        else { [IO.File]::Move($temporary, $Path) }
    } finally { if (Test-Path -LiteralPath $temporary -PathType Leaf) { Remove-Item -LiteralPath $temporary -Force } }
}

function New-WarfareSelfHostServer([string]$GameRoot, [int]$Port, [string]$Nickname, [bool]$AcceptEula, $Descriptor) {
    $paths = Get-WarfareSelfHostPaths $GameRoot
    [IO.Directory]::CreateDirectory($paths.PrivateRoot) | Out-Null
    Assert-WarfareSelfHostPath $paths.PrivateRoot
    Assert-WarfareSelfHostPath $paths.ServerRoot
    if (Test-Path -LiteralPath $paths.ServerRoot -PathType Container) {
        $marker = Read-WarfareSelfHostJson (Join-Path $paths.ServerRoot 'self-host-server.json')
        if (-not $marker -or [int]$marker.schema -ne 1) { throw 'The self-host server folder is incomplete; leaving its contents untouched.' }
        if ([string]$marker.descriptorSha256 -ne (Get-WarfareSelfHostHash $paths.DescriptorPath SHA256)) { throw 'This self-host world belongs to another package version. It was left untouched.' }
        $serverJar = Join-Path $paths.ServerRoot 'minecraft_server.1.12.2.jar'
        $pin = Get-WarfareSelfHostServerJarPin $Descriptor
        if (-not (Test-Path -LiteralPath $serverJar -PathType Leaf) -or (Get-Item -LiteralPath $serverJar).Length -ne [long]$pin.size -or (Get-WarfareSelfHostHash $serverJar SHA1) -ne [string]$pin.sha1) {
            throw 'The self-host Minecraft server JAR is missing or damaged. Its world was left untouched.'
        }
        return [pscustomobject]@{ Paths = $paths; ServerJar = $serverJar; Classpath = (Get-WarfareSelfHostClasspath $paths $serverJar) }
    }
    $setup = Join-Path $paths.PrivateRoot ('.setup-' + [Guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($setup) | Out-Null
    Assert-WarfareSelfHostPath $setup
    $serverJar = Join-Path $setup 'minecraft_server.1.12.2.jar'
    $pin = Get-WarfareSelfHostServerJarPin $Descriptor
    Invoke-WarfareSelfHostPinnedDownload $pin $serverJar
    $classpath = Get-WarfareSelfHostClasspath $paths $serverJar
    Copy-WarfareSelfHostMods $paths $Descriptor $setup
    foreach ($name in @('config','ModularWarfare','mcheli_addons')) {
        Copy-WarfareSelfHostTree (Join-Path $GameRoot $name) (Join-Path $setup $name)
    }
    $usedTemplate = Expand-WarfareSelfHostWorldTemplate $Descriptor $GameRoot (Join-Path $setup 'world')
    if (-not $usedTemplate) { [IO.Directory]::CreateDirectory((Join-Path $setup 'world')) | Out-Null }
    $properties = @(
        'server-ip=',
        ('server-port=' + $Port),
        ('motd=RV Warfare - ' + $Nickname),
        'online-mode=false',
        'white-list=false',
        'max-players=8',
        'level-name=world',
        'allow-flight=true',
        'view-distance=8',
        'spawn-protection=0'
    ) -join [Environment]::NewLine
    [IO.File]::WriteAllText((Join-Path $setup 'server.properties'), $properties + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $setup 'eula.txt'), 'eula=true' + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    $uuidHash = [Security.Cryptography.MD5]::Create()
    try { $uuidBytes = $uuidHash.ComputeHash([Text.Encoding]::UTF8.GetBytes('OfflinePlayer:' + $Nickname)) } finally { $uuidHash.Dispose() }
    $uuidBytes[6] = ($uuidBytes[6] -band 0x0F) -bor 0x30
    $uuidBytes[8] = ($uuidBytes[8] -band 0x3F) -bor 0x80
    $uuidHex = ([BitConverter]::ToString($uuidBytes)).Replace('-', '').ToLowerInvariant()
    $offlineUuid = $uuidHex.Substring(0,8) + '-' + $uuidHex.Substring(8,4) + '-' + $uuidHex.Substring(12,4) + '-' + $uuidHex.Substring(16,4) + '-' + $uuidHex.Substring(20,12)
    $operator = [pscustomobject]@{ uuid = $offlineUuid; name = $Nickname; level = 4; bypassesPlayerLimit = $true }
    [IO.File]::WriteAllText((Join-Path $setup 'ops.json'), (ConvertTo-Json -InputObject @($operator) -Depth 4 -Compress), [Text.UTF8Encoding]::new($false))
    Write-WarfareSelfHostJson (Join-Path $setup 'self-host-server.json') ([pscustomobject]@{
        schema = 1
        minecraftVersion = '1.12.2'
        forgeVersion = '14.23.5.2860'
        descriptorSha256 = Get-WarfareSelfHostHash $paths.DescriptorPath SHA256
        serverJarSha1 = [string]$pin.sha1
        serverModIds = @($Descriptor.serverModIds)
        clientOnlyModIds = @($Descriptor.clientOnlyModIds)
        worldTemplateSha256 = if ($Descriptor.worldTemplate) { [string]$Descriptor.worldTemplate.sha256 } else { $null }
        worldTemplateInstalled = [bool]$usedTemplate
        createdAtUtc = [DateTime]::UtcNow.ToString('o')
    })
    if (Test-Path -LiteralPath $paths.ServerRoot) { throw 'The self-host server folder appeared during setup. Existing data was not replaced.' }
    [IO.Directory]::Move($setup, $paths.ServerRoot)
    $serverJar = Join-Path $paths.ServerRoot 'minecraft_server.1.12.2.jar'
    [pscustomobject]@{ Paths = $paths; ServerJar = $serverJar; Classpath = (Get-WarfareSelfHostClasspath $paths $serverJar) }
}

function Get-WarfareSelfHostEulaAccepted([string]$GameRoot) {
    $paths = Get-WarfareSelfHostPaths $GameRoot
    $eula = Join-Path $paths.ServerRoot 'eula.txt'
    if (-not (Test-Path -LiteralPath $eula -PathType Leaf)) { return $false }
    (Get-Content -LiteralPath $eula -Raw -Encoding UTF8) -match '(?im)^\s*eula\s*=\s*true\s*$'
}

function Test-WarfareSelfHostServerReady([int]$Port, [string]$ServerRoot, [long]$JavaStartedAtUnixMs) {
    $latestLog = Join-Path $ServerRoot 'logs\latest.log'
    if (-not (Test-Path -LiteralPath $latestLog -PathType Leaf)) { return $false }
    $startedAt = [DateTimeOffset]::FromUnixTimeMilliseconds($JavaStartedAtUnixMs).UtcDateTime
    if ((Get-Item -LiteralPath $latestLog).LastWriteTimeUtc -lt $startedAt) { return $false }
    $stream = $null
    try {
        $stream = [IO.File]::Open($latestLog, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        $length = [Math]::Min([long]65536, $stream.Length)
        [void]$stream.Seek(($stream.Length - $length), [IO.SeekOrigin]::Begin)
        $buffer = New-Object byte[] ([int]$length)
        $offset = 0
        while ($offset -lt $buffer.Length) {
            $read = $stream.Read($buffer, $offset, $buffer.Length - $offset)
            if ($read -le 0) { break }
            $offset += $read
        }
        $serverLog = [Text.Encoding]::UTF8.GetString($buffer, 0, $offset)
    } catch { return $false } finally {
        if ($stream) { $stream.Dispose() }
    }
    if ($serverLog -notmatch '(?m)^\[[^\r\n]+\]\s+\[Server thread/INFO\].*\bDone\s*\(') { return $false }
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $task = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $task.AsyncWaitHandle.WaitOne(500)) { return $false }
        $client.EndConnect($task)
        return $true
    } catch { return $false } finally { $client.Dispose() }
}

function Write-WarfareSelfHostLog([string]$Path, [string]$Line) {
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    [IO.File]::AppendAllText($Path, $Line + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}

function Invoke-WarfareSelfHostWorker([string]$GameRoot, [string]$InstanceId) {
    $paths = Get-WarfareSelfHostPaths $GameRoot
    $process = $null
    try {
        $deadline = [DateTime]::UtcNow.AddSeconds(20)
        do {
            $state = Read-WarfareSelfHostJson $paths.StatePath
            if ($state -and [string]$state.instanceId -eq $InstanceId -and $state.launchAuthorized) { break }
            Start-Sleep -Milliseconds 100
        } while ([DateTime]::UtcNow -lt $deadline)
        if (-not $state -or [string]$state.instanceId -ne $InstanceId -or -not $state.launchAuthorized) { throw 'Self-host start authorization expired.' }
        if ([IO.Path]::GetFullPath([string]$state.gameRoot) -ne $paths.GameRoot -or [IO.Path]::GetFullPath([string]$state.serverRoot) -ne $paths.ServerRoot) { throw 'Self-host state paths do not match the selected game folder.' }
        if (Test-Path -LiteralPath $paths.CommandPath -PathType Leaf) {
            $earlyCommand = Read-WarfareSelfHostJson $paths.CommandPath
            if ($earlyCommand -and [string]$earlyCommand.instanceId -eq $InstanceId -and [string]$earlyCommand.action -eq 'stop') {
                $state.state = 'stopped'
                $state.ready = $false
                $state.updatedAtUtc = [DateTime]::UtcNow.ToString('o')
                Write-WarfareSelfHostJson $paths.StatePath $state
                return
            }
        }
        $arguments = @(
            '-Dfile.encoding=UTF-8',
            '-Dlog4j2.formatMsgNoLookups=true',
            '-Xms512M',
            '-Xmx2048M',
            ('-Drv.selfhost.instance=' + $InstanceId),
            '-cp',
            (@($state.classpath) -join ';'),
            'net.minecraftforge.fml.relauncher.ServerLaunchWrapper',
            'nogui'
        )
        $startInfo = [Diagnostics.ProcessStartInfo]::new()
        $startInfo.FileName = [string]$state.javaPath
        $startInfo.Arguments = ($arguments | ForEach-Object { Quote-WarfareSelfHostWindowsArgument ([string]$_) }) -join ' '
        $startInfo.WorkingDirectory = $paths.ServerRoot
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardInput = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $process = [Diagnostics.Process]::new()
        $process.StartInfo = $startInfo
        if (-not $process.Start()) { throw 'Forge server process did not start.' }
        $state.javaPid = $process.Id
        $state.javaExecutable = [IO.Path]::GetFullPath([string]$state.javaPath)
        $state.javaStartedAtUnixMs = [DateTimeOffset]::new($process.StartTime.ToUniversalTime()).ToUnixTimeMilliseconds()
        $state.state = 'starting'
        $state.ready = $false
        $identityDeadline = [DateTime]::UtcNow.AddSeconds(8)
        $identity = $null
        do {
            $identity = Get-WarfareSelfHostWmiProcess $process.Id
            if ($identity -and $identity.CommandLine) { break }
            Start-Sleep -Milliseconds 100
        } while ([DateTime]::UtcNow -lt $identityDeadline)
        if (-not $identity -or -not $identity.CommandLine) { throw 'Could not verify the launched Forge process identity.' }
        $state.javaCommandLineSha256 = Get-WarfareSelfHostTextHash ([string]$identity.CommandLine)
        $state.updatedAtUtc = [DateTime]::UtcNow.ToString('o')
        Write-WarfareSelfHostJson $paths.StatePath $state
        $stdout = $process.StandardOutput.ReadLineAsync()
        $stderr = $process.StandardError.ReadLineAsync()
        $sawDone = $false
        $stopSentAt = $null
        $requestedStop = $false
        while (-not $process.HasExited) {
            if ($stdout.IsCompleted) {
                $line = $stdout.GetAwaiter().GetResult()
                if ($null -ne $line) {
                    Write-WarfareSelfHostLog $paths.LogPath $line
                    if ($line -match 'Done\s*\(') { $sawDone = $true }
                    $stdout = $process.StandardOutput.ReadLineAsync()
                }
            }
            if ($stderr.IsCompleted) {
                $line = $stderr.GetAwaiter().GetResult()
                if ($null -ne $line) { Write-WarfareSelfHostLog $paths.LogPath $line; $stderr = $process.StandardError.ReadLineAsync() }
            }
            if (-not $state.ready -and (Test-WarfareSelfHostServerReady ([int]$state.port) $paths.ServerRoot ([long]$state.javaStartedAtUnixMs))) {
                $state.state = 'running'
                $state.ready = $true
                $state.updatedAtUtc = [DateTime]::UtcNow.ToString('o')
                Write-WarfareSelfHostJson $paths.StatePath $state
            }
            if (Test-Path -LiteralPath $paths.CommandPath -PathType Leaf) {
                $command = Read-WarfareSelfHostJson $paths.CommandPath
                if ($command -and [string]$command.instanceId -eq $InstanceId -and [string]$command.action -eq 'stop' -and -not $requestedStop) {
                    $requestedStop = $true
                    $stopSentAt = [DateTime]::UtcNow
                    $state.state = 'stopping'
                    $state.ready = $false
                    $state.updatedAtUtc = [DateTime]::UtcNow.ToString('o')
                    Write-WarfareSelfHostJson $paths.StatePath $state
                    $process.StandardInput.WriteLine('stop')
                    $process.StandardInput.Flush()
                }
            }
            if ($requestedStop -and ([DateTime]::UtcNow - $stopSentAt).TotalSeconds -gt 120) {
                $state.state = 'stopping'
                $state.ready = $false
                $state.error = 'Server did not confirm a graceful stop within 120 seconds.'
                $state.updatedAtUtc = [DateTime]::UtcNow.ToString('o')
                Write-WarfareSelfHostJson $paths.StatePath $state
                return
            }
            if (-not $state.ready -and ([DateTime]::UtcNow - [DateTime]::Parse([string]$state.startedAtUtc).ToUniversalTime()).TotalSeconds -gt 600) { throw 'Forge server did not become ready within 10 minutes.' }
            $process.WaitForExit(100)
        }
        while ($stdout.IsCompleted -or $stderr.IsCompleted) {
            if ($stdout.IsCompleted) {
                $line = $stdout.GetAwaiter().GetResult()
                if ($null -ne $line) { Write-WarfareSelfHostLog $paths.LogPath $line; $stdout = $process.StandardOutput.ReadLineAsync() } else { break }
            }
            if ($stderr.IsCompleted) {
                $line = $stderr.GetAwaiter().GetResult()
                if ($null -ne $line) { Write-WarfareSelfHostLog $paths.LogPath $line; $stderr = $process.StandardError.ReadLineAsync() } else { break }
            }
            Start-Sleep -Milliseconds 50
        }
        $state.state = if ($process.ExitCode -eq 0) { 'stopped' } else { 'failed' }
        $state.ready = $false
        $state.exitCode = $process.ExitCode
        $state.updatedAtUtc = [DateTime]::UtcNow.ToString('o')
        Write-WarfareSelfHostJson $paths.StatePath $state
    } catch {
        try {
            if ($process -and -not $process.HasExited) {
                $process.StandardInput.WriteLine('stop')
                $process.StandardInput.Flush()
                $null = $process.WaitForExit(120000)
            }
        } catch {}
        try {
            $state = Read-WarfareSelfHostJson $paths.StatePath
            if ($state -and [string]$state.instanceId -eq $InstanceId) {
                $state.state = if ($process -and -not $process.HasExited) { 'stopping' } else { 'failed' }
                $state.ready = $false
                $state.error = $_.Exception.Message
                $state.updatedAtUtc = [DateTime]::UtcNow.ToString('o')
                Write-WarfareSelfHostJson $paths.StatePath $state
            }
        } catch {}
        if ($process) { $process.Dispose() }
        return
    }
    if ($process) { $process.Dispose() }
}

function Wait-WarfareSelfHostReady([string]$GameRoot, [string]$InstanceId, [int]$TimeoutSeconds = 600) {
    $paths = Get-WarfareSelfHostPaths $GameRoot
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $state = Read-WarfareSelfHostJson $paths.StatePath
        if (-not $state -or [string]$state.instanceId -ne $InstanceId) { throw 'Self-host startup state changed unexpectedly.' }
        if ($state.state -eq 'running' -and $state.ready -and (Test-WarfareSelfHostJavaProcess $state) -and (Test-WarfareSelfHostWorkerProcess $state)) {
            return [pscustomobject]@{ server = '127.0.0.1'; port = [int]$state.port }
        }
        if ($state.state -eq 'failed' -or $state.state -eq 'stopped') {
            $detail = if ($state.error) { [string]$state.error } else { 'Forge server exited before becoming ready.' }
            throw ($detail + ' See ' + $paths.LogPath)
        }
        if (-not (Test-WarfareSelfHostWorkerProcess $state)) { throw 'The self-host supervisor identity changed; no process was terminated.' }
        Start-Sleep -Milliseconds 250
    }
    throw ('Forge server is still starting. It remains owned and can be stopped with Stop-WarfareSelfHost. See ' + $paths.LogPath)
}

function Start-WarfareSelfHost {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$GameRoot,
        [Parameter(Mandatory=$true)][ValidateRange(1,65535)][int]$Port,
        [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_]{3,16}$')][string]$Nickname,
        [switch]$AcceptEula
    )
    $paths = Get-WarfareSelfHostPaths $GameRoot
    $mutex = Enter-WarfareSelfHostLock $paths.GameRoot
    $instanceId = $null
    try {
        [IO.Directory]::CreateDirectory($paths.PrivateRoot) | Out-Null
        Assert-WarfareSelfHostPath $paths.PrivateRoot
        Assert-WarfareSelfHostPath $paths.ControlRoot
        $state = Read-WarfareSelfHostJson $paths.StatePath
        if ($state -and $state.state -in @('starting','running','stopping')) {
            $workerValid = Test-WarfareSelfHostWorkerProcess $state
            $javaValid = if ([int]$state.javaPid -gt 0) { Test-WarfareSelfHostJavaProcess $state } else { $false }
            if ($workerValid -and ([int]$state.javaPid -eq 0 -or $javaValid)) {
                if ([int]$state.port -ne $Port) { throw ('This self-host server is already running on port ' + $state.port + '.') }
                if ($state.state -eq 'stopping') { throw 'The self-host server is saving its world. Wait for it to stop before restarting.' }
                $instanceId = [string]$state.instanceId
            } elseif ($javaValid) {
                throw 'The Forge server is still running but its supervisor identity is unavailable. It was left untouched.'
            } elseif ($workerValid) {
                throw 'The self-host process identity changed. No process was terminated and its world was left untouched.'
            } else {
                $state = $null
            }
        }
        if (-not $instanceId) {
            if (-not (Get-WarfareSelfHostEulaAccepted $paths.GameRoot) -and -not $AcceptEula) {
                throw ('Minecraft EULA consent is required before the first self-host start. Show the official EULA and pass -AcceptEula only after the user agrees. Expected file: ' + (Join-Path $paths.ServerRoot 'eula.txt'))
            }
            Assert-WarfareSelfHostPortAvailable $Port
            $descriptor = Get-WarfareSelfHostDescriptor $paths
            $runtime = New-WarfareSelfHostServer $paths.GameRoot $Port $Nickname ([bool]$AcceptEula) $descriptor
            Set-WarfareSelfHostProperty (Join-Path $paths.ServerRoot 'server.properties') 'server-port' ([string]$Port)
            Set-WarfareSelfHostProperty (Join-Path $paths.ServerRoot 'server.properties') 'server-ip' ''
            $instanceId = [Guid]::NewGuid().ToString('N')
            $state = [pscustomobject]@{
                schema = 1
                instanceId = $instanceId
                gameRoot = $paths.GameRoot
                serverRoot = $paths.ServerRoot
                javaPath = [IO.Path]::GetFullPath($paths.JavaPath)
                serverJar = [IO.Path]::GetFullPath($runtime.ServerJar)
                classpath = @($runtime.Classpath)
                port = $Port
                nickname = $Nickname
                instanceMarker = ('-Drv.selfhost.instance=' + $instanceId)
                state = 'starting'
                ready = $false
                launchAuthorized = $false
                workerPid = 0
                workerExecutable = ''
                workerStartedAtUnixMs = 0
                workerCommandLineSha256 = ''
                javaPid = 0
                javaExecutable = ''
                javaStartedAtUnixMs = 0
                javaCommandLineSha256 = ''
                exitCode = $null
                error = ''
                startedAtUtc = [DateTime]::UtcNow.ToString('o')
                updatedAtUtc = [DateTime]::UtcNow.ToString('o')
            }
            Write-WarfareSelfHostJson $paths.StatePath $state
        $source = $MyInvocation.MyCommand.ScriptBlock.File
        if (-not $source) { throw 'Could not locate the self-host helper script.' }
            $shell = Get-WarfareSelfHostPowerShellPath
            if (-not (Test-Path -LiteralPath $shell -PathType Leaf)) { throw 'Windows PowerShell 5.1 is unavailable.' }
            $workerArguments = @(
                '-NoLogo',
                '-NoProfile',
                '-NonInteractive',
                '-ExecutionPolicy',
                'Bypass',
                '-File',
                (Quote-WarfareSelfHostWindowsArgument $source),
                '-SelfHostWorker',
                '-WorkerGameRoot',
                (Quote-WarfareSelfHostWindowsArgument $paths.GameRoot),
                '-WorkerInstanceId',
                (Quote-WarfareSelfHostWindowsArgument $instanceId)
            ) -join ' '
            $worker = Start-Process -FilePath $shell -ArgumentList $workerArguments -WindowStyle Hidden -PassThru -ErrorAction Stop
            $deadline = [DateTime]::UtcNow.AddSeconds(8)
            $workerInfo = $null
            do {
                $workerInfo = Get-WarfareSelfHostWmiProcess $worker.Id
                if ($workerInfo -and $workerInfo.CommandLine) { break }
                Start-Sleep -Milliseconds 100
            } while ([DateTime]::UtcNow -lt $deadline)
            if (-not $workerInfo -or -not $workerInfo.CommandLine) { throw 'Could not verify the self-host supervisor process identity.' }
            $state.workerPid = $worker.Id
            $state.workerExecutable = [IO.Path]::GetFullPath($workerInfo.ExecutablePath)
            $state.workerStartedAtUnixMs = Get-WarfareSelfHostStartMilliseconds $workerInfo
            $state.workerCommandLineSha256 = Get-WarfareSelfHostTextHash ([string]$workerInfo.CommandLine)
            $state.launchAuthorized = $true
            $state.updatedAtUtc = [DateTime]::UtcNow.ToString('o')
            Write-WarfareSelfHostJson $paths.StatePath $state
        }
    } finally {
        $mutex.ReleaseMutex()
        $mutex.Dispose()
    }
    Wait-WarfareSelfHostReady $paths.GameRoot $instanceId
}

function Stop-WarfareSelfHost {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$GameRoot)
    $paths = Get-WarfareSelfHostPaths $GameRoot
    if (-not (Test-Path -LiteralPath $paths.StatePath -PathType Leaf)) { return [pscustomobject]@{ state = 'stopped'; worldPreserved = $true } }
    $mutex = Enter-WarfareSelfHostLock $paths.GameRoot
    $instanceId = $null
    try {
        $state = Read-WarfareSelfHostJson $paths.StatePath
        if (-not $state -or $state.state -in @('stopped','failed')) { return [pscustomobject]@{ state = 'stopped'; worldPreserved = $true } }
        if (-not (Test-WarfareSelfHostWorkerProcess $state)) { throw 'Self-host supervisor ownership could not be verified. No process was terminated.' }
        if ([int]$state.javaPid -gt 0 -and -not (Test-WarfareSelfHostJavaProcess $state)) { throw 'Forge server ownership could not be verified. No process was terminated.' }
        $instanceId = [string]$state.instanceId
        Write-WarfareSelfHostJson $paths.CommandPath ([pscustomobject]@{ schema = 1; action = 'stop'; instanceId = $instanceId })
        $state.state = 'stopping'
        $state.ready = $false
        $state.updatedAtUtc = [DateTime]::UtcNow.ToString('o')
        Write-WarfareSelfHostJson $paths.StatePath $state
    } finally {
        $mutex.ReleaseMutex()
        $mutex.Dispose()
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(125)
    while ([DateTime]::UtcNow -lt $deadline) {
        $state = Read-WarfareSelfHostJson $paths.StatePath
        if ($state -and [string]$state.instanceId -eq $instanceId -and $state.state -eq 'stopped' -and -not (Test-WarfareSelfHostWorkerProcess $state) -and -not (Test-WarfareSelfHostJavaProcess $state)) {
            return [pscustomobject]@{ state = 'stopped'; worldPreserved = (Test-Path -LiteralPath (Join-Path $paths.ServerRoot 'world') -PathType Container) }
        }
        Start-Sleep -Milliseconds 250
    }
    throw ('The server is still saving. It was not force-killed. Check ' + $paths.LogPath)
}

if ($SelfHostWorker) {
    Invoke-WarfareSelfHostWorker -GameRoot $WorkerGameRoot -InstanceId $WorkerInstanceId
    exit
}
