$ErrorActionPreference='Stop'
$env:VM_SKIP_UPDATE_CHECK='1'
$workspace=Split-Path -Parent $PSScriptRoot
. (Join-Path $workspace 'src/Warfare-Connection.ps1')
Add-Type -AssemblyName System.IO.Compression.FileSystem
$root=Join-Path $PSScriptRoot ('duplicate-mods-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root,(Join-Path $root 'mods'),(Join-Path $root 'mods/1.12.2') -Force|Out-Null
function Jar([string]$Path,[string]$Metadata){
    $archive=[IO.Compression.ZipFile]::Open($Path,'Create')
    try{$entry=$archive.CreateEntry('mcmod.info');$writer=[IO.StreamWriter]::new($entry.Open(),[Text.UTF8Encoding]::new($false));try{$writer.Write($Metadata)}finally{$writer.Dispose()}}finally{$archive.Dispose()}
}
foreach($id in @('mcheli','techguns','firstaid','creativecore','enhancedvisuals')){Jar (Join-Path $root ('mods/'+$id+'.jar')) ('[{"modid":"'+$id+'","version":"${version}"}]')}
Jar (Join-Path $root 'mods/firstaid-looking-name.jar') '[{"modid":"player_addon"}]'
Jar (Join-Path $root 'mods/duplicate-metadata.jar') '[{"modid":"another_addon"},{"modid":"another_addon"}]'
[IO.File]::WriteAllText((Join-Path $root 'mods/personal-invalid.jar'),'personal sentinel')
Assert-WarfareUniqueMods $root
'Only actual known mod IDs are counted; names, unknown mods and unknown metadata remain untouched: PASS'
$cases=@()
foreach($id in @('mcheli','techguns','firstaid','creativecore','enhancedvisuals')){
    $extra=Join-Path $root 'mods/1.12.2/Пользовательский.jar'
    Jar $extra ('[{"modid":"'+$id+'","version":"old"},{"modid":"'+$id+'"}]')
    $before=@{};foreach($file in @(Get-ChildItem -LiteralPath (Join-Path $root 'mods') -Recurse -File)){$before[$file.FullName]=(Get-FileHash -LiteralPath $file.FullName).Hash}
    $observed=@(Get-WarfareDuplicateMods $root)
    if($observed.Count -ne 1 -or $observed[0].modid -cne $id -or $observed[0].paths.Count -ne 2){throw ('Duplicate not detected correctly: '+$id)}
    $errorCode='';try{Assert-WarfareUniqueMods $root}catch{$errorCode=$_.Exception.Message}
    if(-not $errorCode.StartsWith('duplicate_mods:') -or $errorCode -notmatch 'mods/1.12.2/Пользовательский.jar'){throw 'Duplicate paths missing'}
    foreach($path in $before.Keys){if((Get-FileHash -LiteralPath $path).Hash -ne $before[$path]){throw 'Duplicate check modified a mod'}}
    foreach($language in @('ru','en')){if((Get-WarfareConnectionError $errorCode $language) -notmatch 'Пользовательский.jar'){throw 'Localized error lost actionable paths'}}
    $cases+=,$id
    Remove-Item -LiteralPath $extra
}
'All five vendor duplicates are detected across Forge mod directories with relative paths and no file changes: PASS'
$extra=Join-Path $root 'mods/1.12.2/second.jar';Jar $extra '{"modList":[{"modid":"firstaid"}]}'
foreach($name in @('Play-Warfare.ps1','Warfare-Connection.ps1','Warfare-ClientMods.ps1','Warfare-Ambience.ps1','Warfare-Performance.ps1','Warfare-Updates.ps1','Configure-FirstPlay.ps1','Warfare-Onboarding.ps1')){Copy-Item -LiteralPath (Join-Path $workspace ('src/'+$name)) -Destination $root}
New-Item -ItemType Directory -Path (Join-Path $root 'runtime/bin'),(Join-Path $root 'natives') -Force|Out-Null
[IO.File]::WriteAllText((Join-Path $root 'runtime/bin/java.exe'),'must not be launched')
[IO.File]::WriteAllText((Join-Path $root 'natives/lwjgl64.dll'),'fixture')
[IO.File]::WriteAllText((Join-Path $root 'installer-files.json'),'{"classpath":[]}')
[IO.File]::WriteAllText((Join-Path $root 'warfare-settings.json'),'{"nickname":"Tester","language":"en"}')
[IO.File]::WriteAllText((Join-Path $root 'installed-manifest.json'),'{"managedFiles":[]}')
$shell=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$statuses=@()
foreach($check in @($true,$false)){
    $statusPath=Join-Path $root ('status-'+$check+'.json')
    $arguments=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $root 'Play-Warfare.ps1'),'-StatusFile',$statusPath)
    if($check){$arguments+='-Check'}
    & $shell @arguments|Out-Null
    if($LASTEXITCODE -ne 1){throw 'Duplicate vendor reached Play or file check'}
    $state=Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8|ConvertFrom-Json
    if($state.reason -ne 'duplicate_mods' -or $state.message -notmatch 'firstaid' -or $state.message -notmatch 'Several versions'){throw 'Duplicate failure state is not actionable'}
    $statuses+=,$state.reason
}
'Actual Play and Check stop before executing Java and publish a localized duplicate_mods status: PASS'
$oldErrorAction=$ErrorActionPreference;$ErrorActionPreference='Continue'
try{& $shell -NoProfile -ExecutionPolicy Bypass -STA -File (Join-Path $root 'Configure-FirstPlay.ps1') -InstallRoot $root -Owner 2>(Join-Path $root 'owner.err')}finally{$ErrorActionPreference=$oldErrorAction}
if($LASTEXITCODE -ne 1 -or [IO.File]::ReadAllText((Join-Path $root 'owner.err')) -notmatch 'firstaid'){throw 'Owner wrapper missed vendor duplicate'}
'Owner first-play wrapper applies the same read-only duplicate guard: PASS'
[IO.File]::WriteAllText((Join-Path $root 'report.json'),(@{status='PASS';vendorCases=$cases;actualPlay=$true;actualCheck=$true;ownerWrapper=$true;filesChanged=$false;root=$root}|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
('Report: '+(Join-Path $root 'report.json'))
