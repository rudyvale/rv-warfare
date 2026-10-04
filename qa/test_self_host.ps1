$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$helper = Join-Path $root 'src\Warfare-SelfHost.ps1'
$tokens = $null
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile($helper, [ref]$tokens, [ref]$parseErrors) | Out-Null
if ($parseErrors.Count) { throw ('Self-host helper parse error: ' + ($parseErrors.Message -join '; ')) }
$source = [IO.File]::ReadAllText($helper)
if ($source -match '(?i)-EncodedCommand') { throw 'Self-host worker must start through -File.' }
if ($source -notmatch '(?s)-File.*-SelfHostWorker.*-WorkerGameRoot.*-WorkerInstanceId') { throw 'Self-host worker launch arguments are incomplete.' }
if ($source -notmatch "(?m)^\s*'online-mode=false',\s*$") { throw 'Self-host must support the installed offline nickname launcher.' }
if ($source -notmatch "(?m)^\s*'server-ip=',\s*$") { throw 'Self-host must listen on LAN interfaces for friends to connect.' }
if ($source -notmatch "logs\\latest\.log") { throw 'Self-host readiness must use the Forge log file.' }
if ($source -notmatch 'JavaStartedAtUnixMs') { throw 'Self-host readiness must reject a stale Forge log.' }
if ($source -notmatch 'OfflinePlayer:'' \+ \$Nickname') { throw 'Offline-mode operator identity is not mapped to the installed nickname.' }
if ($source -notmatch 'level = 4; bypassesPlayerLimit = \$true') { throw 'The host is not configured as a full operator.' }
if ($source -notmatch 'ServerLaunchWrapper') { throw 'The dedicated Forge server entry point is missing.' }
if ($source -notmatch 'versions/1\.12\.2/1\.12\.2\.jar') { throw 'The client-only Minecraft JAR must be excluded from the server classpath.' }
if ($source -notmatch "WriteLine\('stop'\)") { throw 'Self-host stop must request a graceful save.' }
. $helper

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('rv-selfhost-qa-' + [Guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $tempRoot)
try {
    $paths = Get-WarfareSelfHostPaths $tempRoot
    if ($paths.ServerRoot -ne (Join-Path $tempRoot '.rv-selfhost\server')) { throw 'Self-host data is not isolated from the client game folder.' }
    if (Get-WarfareSelfHostEulaAccepted $tempRoot) { throw 'Missing EULA file was treated as accepted.' }
    [void](New-Item -ItemType Directory -Path $paths.ServerRoot -Force)
    [IO.File]::WriteAllText((Join-Path $paths.ServerRoot 'eula.txt'), 'eula=false', [Text.UTF8Encoding]::new($false))
    if (Get-WarfareSelfHostEulaAccepted $tempRoot) { throw 'eula=false was treated as accepted.' }
    [IO.File]::WriteAllText((Join-Path $paths.ServerRoot 'eula.txt'), '# accepted' + [Environment]::NewLine + 'eula=true', [Text.UTF8Encoding]::new($false))
    if (-not (Get-WarfareSelfHostEulaAccepted $tempRoot)) { throw 'eula=true was not recognized.' }
    $unsafeRejected = $false
    try { ConvertTo-WarfareSelfHostPath $tempRoot '../outside.txt' | Out-Null } catch { $unsafeRejected = $true }
    if (-not $unsafeRejected) { throw 'A package path could escape the selected game folder.' }

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $forgeRelative = 'libraries/net/minecraftforge/forge/1.12.2-14.23.5.2860/forge-1.12.2-14.23.5.2860.jar'
    $forgePath = Join-Path $tempRoot $forgeRelative.Replace('/','\')
    [void](New-Item -ItemType Directory -Path (Split-Path -Parent $forgePath) -Force)
    $forge = [IO.Compression.ZipFile]::Open($forgePath, [IO.Compression.ZipArchiveMode]::Create)
    try {
        $entry = $forge.CreateEntry('net/minecraftforge/fml/relauncher/ServerLaunchWrapper.class')
        $writer = [IO.StreamWriter]::new($entry.Open())
        try { $writer.Write('fixture') } finally { $writer.Dispose() }
    } finally { $forge.Dispose() }
    [void](New-Item -ItemType Directory -Path (Join-Path $tempRoot 'runtime\bin') -Force)
    [IO.File]::WriteAllBytes((Join-Path $tempRoot 'runtime\bin\java.exe'), [byte[]]@(0))
    $forgeHash = (Get-FileHash -LiteralPath $forgePath -Algorithm SHA1).Hash.ToLowerInvariant()
    $installer = [pscustomobject]@{
        classpath = @($forgeRelative, 'versions/1.12.2/1.12.2.jar')
        files = @([pscustomobject]@{ path = $forgeRelative; sha1 = $forgeHash })
    }
    [IO.File]::WriteAllText($paths.InstallerFilesPath, (ConvertTo-Json -InputObject $installer -Depth 6), [Text.UTF8Encoding]::new($false))
    $serverJar = Join-Path $paths.ServerRoot 'minecraft_server.1.12.2.jar'
    $classpath = @(Get-WarfareSelfHostClasspath $paths $serverJar)
    if (@($classpath | Where-Object { $_ -like '*versions\1.12.2\1.12.2.jar' }).Count) { throw 'Client Minecraft JAR leaked into the server classpath.' }
    if (-not (@($classpath | Where-Object { $_ -eq $serverJar }).Count)) { throw 'Pinned dedicated server JAR is missing from the classpath.' }
    if (-not (@($classpath | Where-Object { $_ -eq $forgePath }).Count)) { throw 'Verified Forge server library is missing from the classpath.' }
    $classPathArgument = Quote-WarfareSelfHostWindowsArgument ('C:\Program Files\RV\server.jar;C:\RV\forge.jar')
    if ($classPathArgument -ne '"C:\Program Files\RV\server.jar;C:\RV\forge.jar"') { throw 'Windows classpath quoting damaged paths containing spaces.' }

    $game = Join-Path $tempRoot 'fixture-install'
    [void](New-Item -ItemType Directory -Path (Join-Path $game 'mods') -Force)
    $fixturePaths = Get-WarfareSelfHostPaths $game
    function New-TestModJar([string]$Path, [string]$ModId) {
        $archive = [IO.Compression.ZipFile]::Open($Path, [IO.Compression.ZipArchiveMode]::Create)
        try {
            $entry = $archive.CreateEntry('mcmod.info')
            $writer = [IO.StreamWriter]::new($entry.Open())
            try { $writer.Write('[{"modid":"' + $ModId + '","name":"fixture"}]') } finally { $writer.Dispose() }
        } finally { $archive.Dispose() }
    }
    $serverMod = Join-Path $game 'mods\serverfixture.jar'
    $clientMod = Join-Path $game 'mods\clientfixture.jar'
    $bootMod = Join-Path $game 'mods\mixinbooter-fixture.jar'
    New-TestModJar $serverMod 'corefixture'
    New-TestModJar $clientMod 'clientfixture'
    New-TestModJar $bootMod 'mixinbooter'
    $serverHash = (Get-FileHash -LiteralPath $serverMod -Algorithm SHA256).Hash.ToLowerInvariant()
    $clientHash = (Get-FileHash -LiteralPath $clientMod -Algorithm SHA256).Hash.ToLowerInvariant()
    $bootHash = (Get-FileHash -LiteralPath $bootMod -Algorithm SHA256).Hash.ToLowerInvariant()
    $catalogPath = $fixturePaths.VendorCatalogPath
    [IO.File]::WriteAllText($catalogPath, '{"baseline":{"files":[]},"files":[{"side":"client","expectedModIds":["clientfixture"]}]}', [Text.UTF8Encoding]::new($false))
    $catalogHash = (Get-FileHash -LiteralPath $catalogPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $release = [pscustomobject]@{
        requiredMods = [pscustomobject]@{ corefixture = '1.0' }
        clientRequiredMods = [pscustomobject]@{ corefixture = '1.0'; clientfixture = '1.0' }
        vendorCatalogSha256 = $catalogHash
    }
    [IO.File]::WriteAllText($fixturePaths.ReleasePath, (ConvertTo-Json -InputObject $release -Depth 6), [Text.UTF8Encoding]::new($false))
    $manifest = [pscustomobject]@{ managedFiles = @(
        [pscustomobject]@{ path = 'mods/serverfixture.jar'; sha256 = $serverHash },
        [pscustomobject]@{ path = 'mods/clientfixture.jar'; sha256 = $clientHash },
        [pscustomobject]@{ path = 'mods/mixinbooter-fixture.jar'; sha256 = $bootHash }
    ) }
    [IO.File]::WriteAllText($fixturePaths.PackageManifestPath, (ConvertTo-Json -InputObject $manifest -Depth 6), [Text.UTF8Encoding]::new($false))
    $descriptor = [pscustomobject]@{ serverModIds = @('corefixture'); clientOnlyModIds = @('clientfixture') }
    Copy-WarfareSelfHostMods $fixturePaths $descriptor $fixturePaths.ServerRoot
    $serverMods = Join-Path $fixturePaths.ServerRoot 'mods'
    if (-not (Test-Path -LiteralPath (Join-Path $serverMods 'serverfixture.jar'))) { throw 'Pinned server mod did not copy into the private server.' }
    if (-not (Test-Path -LiteralPath (Join-Path $serverMods 'mixinbooter-fixture.jar'))) { throw 'Shared Forge bootstrap dependency was not copied.' }
    if (Test-Path -LiteralPath (Join-Path $serverMods 'clientfixture.jar')) { throw 'Client-only mod was copied into the dedicated server.' }

    $worldRoot = Join-Path $tempRoot 'world-fixture'
    $worldInput = Join-Path $worldRoot 'Template'
    [void](New-Item -ItemType Directory -Path $worldInput -Force)
    [IO.File]::WriteAllText((Join-Path $worldInput 'level.dat'), 'world', [Text.UTF8Encoding]::new($false))
    $worldZip = Join-Path $tempRoot 'self-host-world.zip'
    $worldArchive = [IO.Compression.ZipFile]::Open($worldZip, [IO.Compression.ZipArchiveMode]::Create)
    try {
        $worldEntry = $worldArchive.CreateEntry('Template/level.dat')
        $worldWriter = [IO.StreamWriter]::new($worldEntry.Open())
        try { $worldWriter.Write('world') } finally { $worldWriter.Dispose() }
    } finally { $worldArchive.Dispose() }
    $worldDescriptor = [pscustomobject]@{ worldTemplate = [pscustomobject]@{ path = 'self-host-world.zip'; size = (Get-Item $worldZip).Length; sha256 = (Get-FileHash $worldZip -Algorithm SHA256).Hash.ToLowerInvariant() } }
    $worldDestination = Join-Path $tempRoot 'expanded-world'
    if (-not (Expand-WarfareSelfHostWorldTemplate $worldDescriptor $tempRoot $worldDestination)) { throw 'Verified RV world template was not extracted.' }
    if (-not (Test-Path -LiteralPath (Join-Path $worldDestination 'level.dat'))) { throw 'The world template root folder was not normalized.' }

    $hostGame = Join-Path $tempRoot 'fixture install with spaces'
    [void](New-Item -ItemType Directory -Path $hostGame -Force)
    $hostPaths = Get-WarfareSelfHostPaths $hostGame
    [void](New-Item -ItemType Directory -Path (Join-Path $hostGame 'runtime\bin') -Force)
    $fakeJava = Join-Path $hostGame 'runtime\bin\java.exe'
    $fakeSource = @'
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
public static class FakeJava {
    public static void Main(string[] args) {
        int port = 25565;
        foreach (string line in File.ReadAllLines("server.properties")) {
            if (line.StartsWith("server-port=")) { Int32.TryParse(line.Substring(12), out port); break; }
        }
        TcpListener listener = new TcpListener(IPAddress.Any, port);
        listener.Start();
        Directory.CreateDirectory("logs");
        File.AppendAllText(Path.Combine("logs", "latest.log"), "[00:00:01] [Server thread/INFO] [net.minecraft.server.dedicated.DedicatedServer]: Done (0.1s)! For help, type help" + Environment.NewLine);
        Console.WriteLine("[Server thread/INFO] [net.minecraft.server.dedicated.DedicatedServer]: %minecraftFormatting");
        string input;
        while ((input = Console.ReadLine()) != null) { if (input == "stop") break; }
        listener.Stop();
    }
}
'@
    Add-Type -TypeDefinition $fakeSource -OutputAssembly $fakeJava -OutputType ConsoleApplication -ErrorAction Stop
    $hostForgeRelative = 'libraries/net/minecraftforge/forge/1.12.2-14.23.5.2860/forge-1.12.2-14.23.5.2860.jar'
    $hostForge = Join-Path $hostGame $hostForgeRelative.Replace('/','\')
    [void](New-Item -ItemType Directory -Path (Split-Path -Parent $hostForge) -Force)
    $hostForgeArchive = [IO.Compression.ZipFile]::Open($hostForge, [IO.Compression.ZipArchiveMode]::Create)
    try {
        $entry = $hostForgeArchive.CreateEntry('net/minecraftforge/fml/relauncher/ServerLaunchWrapper.class')
        $writer = [IO.StreamWriter]::new($entry.Open())
        try { $writer.Write('fixture') } finally { $writer.Dispose() }
    } finally { $hostForgeArchive.Dispose() }
    $hostForgeHash = (Get-FileHash -LiteralPath $hostForge -Algorithm SHA1).Hash.ToLowerInvariant()
    $hostInstaller = [pscustomobject]@{
        classpath = @($hostForgeRelative, 'versions/1.12.2/1.12.2.jar')
        files = @([pscustomobject]@{ path = $hostForgeRelative; sha1 = $hostForgeHash })
    }
    [IO.File]::WriteAllText($hostPaths.InstallerFilesPath, (ConvertTo-Json -InputObject $hostInstaller -Depth 6), [Text.UTF8Encoding]::new($false))
    $officialDescriptor = [pscustomobject]@{
        schema = 1
        minecraftVersion = '1.12.2'
        forgeVersion = '14.23.5.2860'
        serverJar = [pscustomobject]@{ url = 'https://piston-data.mojang.com/v1/objects/886945bfb2b978778c3a0288fd7fab09d315b25f/server.jar'; sha1 = '886945bfb2b978778c3a0288fd7fab09d315b25f'; size = 30222121 }
        serverModIds = @('corefixture')
        clientOnlyModIds = @('clientfixture')
    }
    $officialPin = Get-WarfareSelfHostServerJarPin $officialDescriptor
    if ($officialPin.sha1 -ne '886945bfb2b978778c3a0288fd7fab09d315b25f' -or $officialPin.size -ne 30222121) { throw 'Minecraft server pin changed unexpectedly.' }
    $descriptorPath = $hostPaths.DescriptorPath
    [IO.File]::WriteAllText($descriptorPath, (ConvertTo-Json -InputObject $officialDescriptor -Depth 6), [Text.UTF8Encoding]::new($false))
    $hostServer = $hostPaths.ServerRoot
    [void](New-Item -ItemType Directory -Path (Join-Path $hostServer 'world') -Force)
    [IO.File]::WriteAllText((Join-Path $hostServer 'world\level.dat'), 'preserve-me', [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $hostServer 'eula.txt'), 'eula=true', [Text.UTF8Encoding]::new($false))
    $properties = @('server-ip=127.0.0.1','server-port=25565','online-mode=false','level-name=world') -join [Environment]::NewLine
    [IO.File]::WriteAllText((Join-Path $hostServer 'server.properties'), $properties + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    $fakeServerJar = Join-Path $hostServer 'minecraft_server.1.12.2.jar'
    [IO.File]::WriteAllBytes($fakeServerJar, [byte[]]@(1,2,3,4))
    $script:SelfHostQaServerPin = [pscustomobject]@{ url = 'fixture'; sha1 = (Get-WarfareSelfHostHash $fakeServerJar SHA1); size = (Get-Item $fakeServerJar).Length }
    function Get-WarfareSelfHostServerJarPin($Descriptor) { return $script:SelfHostQaServerPin }
    Write-WarfareSelfHostJson (Join-Path $hostServer 'self-host-server.json') ([pscustomobject]@{
        schema = 1
        descriptorSha256 = Get-WarfareSelfHostHash $descriptorPath SHA256
    })
    [IO.File]::WriteAllText((Join-Path $hostGame 'release.json'), '{"requiredMods":{"corefixture":"1.0"},"clientRequiredMods":{"corefixture":"1.0"},"vendorCatalogSha256":"' + ('0' * 64) + '"}', [Text.UTF8Encoding]::new($false))
    $portProbe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    $portProbe.Start()
    $serverPort = [int]$portProbe.LocalEndpoint.Port
    $portProbe.Stop()
    $staleLogRoot = Join-Path $hostServer 'logs'
    [void](New-Item -ItemType Directory -Path $staleLogRoot -Force)
    $staleLog = Join-Path $staleLogRoot 'latest.log'
    [IO.File]::WriteAllText($staleLog, '[00:00:01] [Server thread/INFO] [DedicatedServer]: Done (old)!', [Text.UTF8Encoding]::new($false))
    [IO.File]::SetLastWriteTimeUtc($staleLog, [DateTime]::UtcNow.AddMinutes(-5))
    $staleListener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $serverPort)
    $staleListener.Start()
    try {
        $startTime = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
        if (Test-WarfareSelfHostServerReady $serverPort $hostServer $startTime) { throw 'A stale Forge readiness log was accepted.' }
    } finally { $staleListener.Stop() }
    $started = Start-WarfareSelfHost -GameRoot $hostGame -Port $serverPort -Nickname 'Tester'
    if ($started.server -ne '127.0.0.1' -or $started.port -ne $serverPort) { throw 'Self-host start returned the wrong local endpoint.' }
    $hostProperties = @{}
    foreach ($line in Get-Content -LiteralPath (Join-Path $hostServer 'server.properties')) { if ($line -match '^([^=]+)=(.*)$') { $hostProperties[$Matches[1]] = $Matches[2] } }
    if ($hostProperties['server-ip'] -ne '') { throw 'Self-host did not clear the loopback-only bind for LAN connections.' }
    $stopped = Stop-WarfareSelfHost -GameRoot $hostGame
    if ($stopped.state -ne 'stopped' -or -not $stopped.worldPreserved) { throw 'Self-host did not stop gracefully while preserving its world.' }
    if ([IO.File]::ReadAllText((Join-Path $hostServer 'world\level.dat')) -ne 'preserve-me') { throw 'Self-host stop modified the world fixture.' }
    'Self-host helper checks passed.'
} finally {
    $resolvedTemp = [IO.Path]::GetFullPath($tempRoot)
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if (-not $resolvedTemp.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -or -not (Split-Path -Leaf $resolvedTemp).StartsWith('rv-selfhost-qa-')) { throw 'Refusing to remove an unexpected test directory.' }
    if (Test-Path -LiteralPath $resolvedTemp) { Remove-Item -LiteralPath $resolvedTemp -Recurse -Force }
}
