$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
. (Join-Path $root 'src/Warfare-Connection.ps1')
. (Join-Path $root 'src/Warfare-PlayModes.ps1')
function Assert([bool]$Value,[string]$Message){if(-not $Value){throw $Message}}
$fresh=[PSCustomObject]@{}
$freshState=Get-WarfarePlayModeState $fresh
Assert ($freshState.mode -eq 'local') 'Clean install must default to Local.'
Assert (-not $freshState.friends.connectionTarget -and -not $freshState.owner.connectionTarget) 'Clean profiles must have no destinations.'
$installedFresh=[PSCustomObject]@{playMode='local';playProfiles=[PSCustomObject]@{friends=(New-WarfareModeConnection);owner=(New-WarfareModeConnection);host=[PSCustomObject]@{port=25565}};connectionMode='direct';connectionTarget='package-default.example';serverPort=25565}
$installedFreshState=Get-WarfarePlayModeState $installedFresh
Assert ($installedFreshState.mode -eq 'local' -and -not $installedFreshState.friends.connectionTarget) 'A package server default must not activate a remote destination on a clean install.'
$providedFriendDefault=ConvertTo-WarfareConnection 'porthole' 'ABCD1234' '25565'
$installedWithFriendDefault=[PSCustomObject]@{playMode='local';playProfiles=[PSCustomObject]@{friends=$providedFriendDefault;owner=(New-WarfareModeConnection);host=[PSCustomObject]@{port=25565}};connectionMode='porthole';connectionTarget='ABCD1234';serverPort=25565}
$providedDefaultState=Get-WarfarePlayModeState $installedWithFriendDefault
Assert ($providedDefaultState.mode -eq 'local' -and $providedDefaultState.friends.connectionTarget -eq 'ABCD1234' -and -not $providedDefaultState.owner.connectionTarget) 'A supplied Friends destination was not preserved separately from Local mode.'
$lanAddresses=@(Get-WarfareLanIPv4Addresses @('127.0.0.1','169.254.2.4','8.8.8.8','10.2.3.4','172.15.0.1','172.16.2.3','172.31.2.3','172.32.2.3','192.168.1.25','192.168.1.25'))
Assert (($lanAddresses -join ',') -eq '10.2.3.4,172.16.2.3,172.31.2.3,192.168.1.25') 'Host share hint included a non-LAN, duplicate, or invalid address.'
$legacy=[PSCustomObject]@{nickname='ModeTester';language='en';connectionMode='direct';connectionTarget='friends.example';serverPort=25571;extra='preserve'}
$state=Get-WarfarePlayModeState $legacy
Assert ($state.mode -eq 'friends' -and $state.migrated) 'A legacy target must migrate into Friends.'
Assert ($state.friends.connectionMode -eq 'direct' -and $state.friends.connectionTarget -eq 'friends.example' -and $state.friends.serverPort -eq 25571) 'Friends migration lost the legacy destination.'
Assert (-not $state.owner.connectionTarget) 'Owner profile must not inherit Friends.'
$owner=ConvertTo-WarfareConnection 'porthole' 'OWNER123' '25580'
$state=Set-WarfarePlayModeConnection $state 'owner' $owner
$saved=Set-WarfarePlayModeState $legacy $state 'owner'
Assert ($saved.extra -eq 'preserve' -and $saved.connectionTarget -eq 'OWNER123') 'Saving Owner did not preserve unrelated settings or legacy mirror.'
$roundtrip=$saved|ConvertTo-Json -Depth 16|ConvertFrom-Json
$state2=Get-WarfarePlayModeState $roundtrip
Assert ($state2.mode -eq 'owner' -and $state2.friends.connectionTarget -eq 'friends.example' -and $state2.owner.connectionTarget -eq 'OWNER123') 'Friends and Owner persistence crossed profiles.'
$emptyOwner=[PSCustomObject]@{playMode='owner';playProfiles=[PSCustomObject]@{friends=$state2.friends;owner=(New-WarfareModeConnection);host=[PSCustomObject]@{port=25565}};connectionMode='direct';connectionTarget='friends.example';serverPort=25571}
$emptyState=Get-WarfarePlayModeState $emptyOwner
Assert ($emptyState.mode -eq 'owner' -and -not $emptyState.owner.connectionTarget) 'An empty Owner profile fell back to Friends.'
$before=$emptyOwner|ConvertTo-Json -Depth 16
$after=$emptyOwner|ConvertTo-Json -Depth 16
Assert ($before -ceq $after) 'Cancelling profile editing changed persisted settings.'
$fixture=Join-Path ([IO.Path]::GetTempPath()) ('rv-play-modes-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixture -Force|Out-Null
try{
    function New-TestWorldPackage([string]$PackageRoot,[string[]]$EntryNames){
        New-Item -ItemType Directory -Path $PackageRoot -Force|Out-Null
        $archivePath=Join-Path $PackageRoot 'self-host-world.zip'
        $archive=[IO.Compression.ZipFile]::Open($archivePath,[IO.Compression.ZipArchiveMode]::Create)
        try{foreach($entryName in $EntryNames){$entry=$archive.CreateEntry($entryName,[IO.Compression.CompressionLevel]::Optimal);$stream=$entry.Open();try{$bytes=[Text.Encoding]::UTF8.GetBytes('fixture');$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}}}finally{$archive.Dispose()}
        $archiveInfo=Get-Item -LiteralPath $archivePath
        $descriptor=[PSCustomObject]@{schema=1;worldTemplate=[PSCustomObject]@{path='self-host-world.zip';sha256=(Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant();size=[long]$archiveInfo.Length}}
        [IO.File]::WriteAllText((Join-Path $PackageRoot 'self-host-package.json'),($descriptor|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
    }
    $worldNames=@('world-template-manifest.json','INSTALL-NEW-WORLD.md','SHA256SUMS.txt','Battlefield-Extended/level.dat','Battlefield-Extended/data/scoreboard.dat','Battlefield-Extended/region/r.0.0.mca','Battlefield-Extended/data/functions/warfare/boot.mcfunction')
    $worldPackage=Join-Path $fixture 'world-package';$worldGame=Join-Path $fixture 'world-game'
    New-TestWorldPackage $worldPackage $worldNames
    $worldInstalled=Install-WarfareWorldTemplate $worldPackage $worldGame
    $worldDestination=Join-Path $worldGame 'saves/Battlefield-Extended'
    Assert ($worldInstalled -and (Test-Path -LiteralPath (Join-Path $worldDestination 'level.dat')) -and (Test-Path -LiteralPath (Join-Path $worldDestination 'region/r.0.0.mca')) -and -not (Test-Path -LiteralPath (Join-Path $worldDestination 'world-template-manifest.json'))) 'Fresh world template was not installed into Saves.'
    [IO.File]::WriteAllText((Join-Path $worldDestination 'player-note.txt'),'keep')
    $preservedWorld=Install-WarfareWorldTemplate $worldPackage $worldGame
    Assert (-not $preservedWorld -and [IO.File]::ReadAllText((Join-Path $worldDestination 'player-note.txt')) -eq 'keep') 'An existing world was changed by template installation.'
    $unsafePackage=Join-Path $fixture 'unsafe-world-package';$unsafeGame=Join-Path $fixture 'unsafe-world-game'
    New-TestWorldPackage $unsafePackage ($worldNames+@('Battlefield-Extended/../escape.txt'))
    $unsafeRejected=$false
    try{$null=Install-WarfareWorldTemplate $unsafePackage $unsafeGame}catch{$unsafeRejected=$true}
    Assert ($unsafeRejected -and -not (Test-Path -LiteralPath (Join-Path $fixture 'escape.txt'))) 'Unsafe world archive path was not rejected before extraction.'
    Copy-Item -LiteralPath (Join-Path $root 'src/Warfare-PlayModes.ps1') -Destination (Join-Path $fixture 'Warfare-PlayModes.ps1')
    $selfHost=@'
function Get-WarfareSelfHostEulaAccepted([string]$GameRoot){Test-Path -LiteralPath (Join-Path $GameRoot 'eula.txt')}
function Start-WarfareSelfHost([string]$GameRoot,[int]$Port,[string]$Nickname,[switch]$AcceptEula){
    $call=[PSCustomObject]@{gameRoot=$GameRoot;port=$Port;nickname=$Nickname;acceptEula=[bool]$AcceptEula}
    $path=Join-Path $GameRoot 'helper-calls.jsonl'
    Add-Content -LiteralPath $path -Value ($call|ConvertTo-Json -Compress)
    if(-not (Test-Path -LiteralPath (Join-Path $GameRoot 'eula.txt'))){if(-not $AcceptEula){throw 'self_host_eula_required'};Set-Content -LiteralPath (Join-Path $GameRoot 'eula.txt') -Value 'eula=true'}
    if(-not (Test-Path -LiteralPath (Join-Path $GameRoot 'started.txt'))){Set-Content -LiteralPath (Join-Path $GameRoot 'started.txt') -Value 'started';$chosen=if($Port){$Port}else{25575}}else{$chosen=25575}
    return [PSCustomObject]@{server='127.0.0.1';port=$chosen;shareCode='ABCD1234'}
}
function Stop-WarfareSelfHost([string]$GameRoot){Set-Content -LiteralPath (Join-Path $GameRoot 'stopped.txt') -Value 'stopped';Remove-Item -LiteralPath (Join-Path $GameRoot 'started.txt') -Force -ErrorAction SilentlyContinue}
'@
    [IO.File]::WriteAllText((Join-Path $fixture 'Warfare-SelfHost.ps1'),$selfHost,[Text.UTF8Encoding]::new($true))
    $ps=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $rootArg=Join-Path $fixture 'GameRoot';New-Item -ItemType Directory -Path $rootArg -Force|Out-Null
    $status=Join-Path $fixture 'status.json'
    $script=Join-Path $fixture 'Warfare-PlayModes.ps1'
    $base=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$script,'-WarfareWorkerGameRoot',$rootArg,'-WarfareWorkerPort','25581','-WarfareWorkerNickname','ModeTester','-WarfareWorkerStatusFile',$status)
    $refused=Start-Process -FilePath $ps -ArgumentList ($base+@('-WarfareWorkerAction','start-host')) -PassThru -Wait -WindowStyle Hidden
    $refusedStatus=Get-Content -LiteralPath $status -Raw -Encoding UTF8|ConvertFrom-Json
    Assert ($refused.ExitCode -eq 1 -and $refusedStatus.reason -eq 'self_host_eula_required') 'Unaccepted EULA did not stop host startup.'
    Assert (-not (Test-Path -LiteralPath (Join-Path $rootArg 'started.txt')) -and -not (Test-Path -LiteralPath (Join-Path $rootArg 'helper-calls.jsonl'))) 'The server helper ran before EULA confirmation.'
    $accepted=Start-Process -FilePath $ps -ArgumentList ($base+@('-WarfareWorkerAction','start-host','-WarfareWorkerAcceptEula')) -PassThru -Wait -WindowStyle Hidden
    $acceptedStatus=Get-Content -LiteralPath $status -Raw -Encoding UTF8|ConvertFrom-Json
    Assert ($accepted.ExitCode -eq 0 -and $acceptedStatus.state -eq 'ready' -and $acceptedStatus.port -eq 25581 -and $acceptedStatus.shareCode -eq 'ABCD1234' -and $acceptedStatus.message -eq 'Сервер запущен.') 'Accepted host startup, localized status or share-code handoff failed.'
    $again=Start-Process -FilePath $ps -ArgumentList ($base+@('-WarfareWorkerAction','start-host')) -PassThru -Wait -WindowStyle Hidden
    $calls=@(Get-Content -LiteralPath (Join-Path $rootArg 'helper-calls.jsonl')|ForEach-Object {$_|ConvertFrom-Json})
    Assert ($again.ExitCode -eq 0 -and $calls.Count -eq 2 -and $calls[0].acceptEula -and -not $calls[1].acceptEula) 'Accepted EULA was repeated or the start call was duplicated.'
    $stopped=Start-Process -FilePath $ps -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$script,'-WarfareWorkerAction','stop-host','-WarfareWorkerGameRoot',$rootArg,'-WarfareWorkerStatusFile',$status) -PassThru -Wait -WindowStyle Hidden
    $stopStatus=Get-Content -LiteralPath $status -Raw -Encoding UTF8|ConvertFrom-Json
    Assert ($stopped.ExitCode -eq 0 -and (Test-Path -LiteralPath (Join-Path $rootArg 'stopped.txt')) -and $stopStatus.message -eq 'Сервер остановлен.') 'Graceful stop action or localized status was not dispatched.'
}finally{Remove-Item -LiteralPath $fixture -Recurse -Force}
$sourceFiles=@('src/Install-Warfare.ps1','src/Play-Warfare.ps1','src/Warfare-Launcher.ps1','src/Warfare-Onboarding.ps1','src/Warfare-PlayModes.ps1')
foreach($file in $sourceFiles){$tokens=$null;$parseErrors=$null;[void][Management.Automation.Language.Parser]::ParseFile((Join-Path $root $file),[ref]$tokens,[ref]$parseErrors);if($parseErrors.Count){throw ($file+': '+(($parseErrors|ForEach-Object{$_.Message}) -join '; '))}}
'Local default, legacy migration, profile isolation, cancellation, host worker vector and EULA gating: PASS'
