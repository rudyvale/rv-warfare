$ErrorActionPreference='Stop'
$workspace=Split-Path -Parent $PSScriptRoot
. (Join-Path $workspace 'src\Warfare-Performance.ps1')
$fixture=Join-Path $PSScriptRoot ('performance-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $fixture 'config') -Force|Out-Null
function Get-CimInstance { param($ClassName,$Filter,$ErrorAction)
    if($script:running){return [PSCustomObject]@{CommandLine=('java.exe --gameDir "'+$fixture.ToUpperInvariant()+'"')}}
    return @()
}
function Expect-Error($Action,[string]$Code){$observed='';try{& $Action}catch{$observed=$_.Exception.Message};if($observed -ne $Code){throw "Expected $Code, got $observed"}}
function Read-Pref([string]$Name){return [IO.File]::ReadAllText((Join-Path $fixture $Name))}
$options=Join-Path $fixture 'options.txt'
$shaders=Join-Path $fixture 'optionsshaders.txt'
$preferences=Join-Path $fixture 'config\rv-client.properties'
[IO.File]::WriteAllText($options,"mouseSensitivity:0.27`r`nkey_key.attack:47`r`nrenderDistance:20`r`nresourcePacks:[`"my pack.zip`"]`r`nunknown:中文`r`nrenderDistance:15`r`n")
[IO.File]::WriteAllText($shaders,"shaderPack=custom.zip`ncustom=настройки`n")
[IO.File]::WriteAllText($preferences,"schema=1`nprofile=quality`nlanguage=en`nhudHints=false`nhitFeedback=true`nPROFILE=custom`nunknown=中文`n# player comment`n")
Set-WarfarePerformanceProfile -Root $fixture -Profile low -Language ru -HudHints $false -ApplyGraphics
$read=Get-WarfareClientPreferences $fixture
if($read.profile -ne 'low' -or $read.language -ne 'ru' -or $read.hudHints -or -not $read.hitFeedback){throw 'Preferences not applied'}
$after=Read-Pref 'options.txt'
foreach($expected in @('renderDistance:4','fancyGraphics:false','particles:2','ao:0','mipmapLevels:0','renderClouds:false','mouseSensitivity:0.27','key_key.attack:47','unknown:中文','resourcePacks:["my pack.zip"]')){if(-not $after.Contains($expected)){throw ('Missing or changed option: '+$expected)}}
if([regex]::Matches($after,'(?m)^renderDistance:').Count -ne 1){throw 'Duplicate option remains'}
if(-not (Read-Pref 'optionsshaders.txt').Contains('shaderPack=OFF') -or -not (Read-Pref 'optionsshaders.txt').Contains('custom=настройки')){throw 'Shader preferences lost'}
foreach($expected in @('PROFILE=custom','unknown=中文','# player comment')){if(-not (Read-Pref 'config\rv-client.properties').Contains($expected)){throw 'Unknown properties lost'}}
'explicit Low preserves bindings, packs, unknown Unicode keys and comments: PASS'
$hash=(Get-FileHash $options).Hash
Set-WarfarePerformanceProfile -Root $fixture -Language en -LanguageOnly
if((Get-FileHash $options).Hash -ne $hash -or (Get-WarfareClientPreferences $fixture).profile -ne 'low'){throw 'Language changed graphics or profile'}
'language alone leaves graphics and profile intact: PASS'
Set-WarfarePerformanceProfile -Root $fixture -Profile quality -Language en -ApplyGraphics
if(-not (Read-Pref 'options.txt').Contains('renderClouds:true')){throw 'Quality clouds invalid'}
Set-WarfarePerformanceProfile -Root $fixture -Profile balanced -Language en -ApplyGraphics
if(-not (Read-Pref 'options.txt').Contains('renderClouds:fast')){throw 'Balanced clouds invalid'}
[IO.File]::WriteAllText($options,(Read-Pref 'options.txt').Replace('renderDistance:8','renderDistance:31'))
Set-WarfarePerformanceProfile -Root $fixture -Profile balanced -Language en -ApplyGraphics
if(-not (Read-Pref 'options.txt').Contains('renderDistance:8')){throw 'Cannot reapply same profile'}
'Balanced and Quality apply correctly; same profile can be reapplied: PASS'
$before=@{};foreach($path in @($options,$shaders,$preferences)){$before[$path]=(Get-FileHash $path).Hash}
$script:running=$true
Expect-Error {Set-WarfarePerformanceProfile -Root $fixture -Profile low -Language ru -ApplyGraphics} 'RV_SETTINGS_RUNNING'
$script:running=$false
$lock=[IO.File]::Open((Join-Path $fixture '.install.lock'),'OpenOrCreate','ReadWrite','None')
try{Expect-Error {Set-WarfarePerformanceProfile -Root $fixture -Profile low -Language ru -ApplyGraphics} 'RV_SETTINGS_BUSY'}finally{$lock.Dispose()}
foreach($path in $before.Keys){if((Get-FileHash $path).Hash -ne $before[$path]){throw 'Blocked operation wrote settings'}}
'active game and install lock block graphics changes before writing: PASS'
$script:moves=0
function Move-Item {param($LiteralPath,$Destination,[switch]$Force)
    $script:moves++;if($script:moves -eq 2){throw 'fixture write failure'}
    Microsoft.PowerShell.Management\Move-Item -LiteralPath $LiteralPath -Destination $Destination -Force
}
try{Expect-Error {Set-WarfarePerformanceProfile -Root $fixture -Profile low -Language ru -ApplyGraphics} 'fixture write failure'}finally{Remove-Item Function:Move-Item}
foreach($path in $before.Keys){if((Get-FileHash $path).Hash -ne $before[$path]){throw 'Failed apply did not roll back'}}
'interrupted multi-file apply restores exact previous settings: PASS'
foreach($case in @(@(4096,8,'low'),@(8192,8,'low'),@(16384,2,'low'),@(16384,8,'balanced'),@(0,0,'balanced'))){if((Get-WarfareInitialProfile ([PSCustomObject]@{ramMB=$case[0];logicalProcessors=$case[1]})) -ne $case[2]){throw 'Unexpected hardware profile'}}
'initial profile uses known RAM/CPU facts and a conservative unknown fallback: PASS'
foreach($case in @(@(4096,0,2048),@(8192,0,3584),@(16384,0,4096),@(16384,12288,2560),@(0,0,3072))){
    $facts=[PSCustomObject]@{ramMB=$case[0];serverHeapMB=$case[1]}
    if((Get-WarfareHeapMB ([PSCustomObject]@{}) $facts) -ne $case[2]){throw ('Unexpected heap: '+($case -join ','))}
}
$facts=[PSCustomObject]@{ramMB=16384;serverHeapMB=0}
$settings=[PSCustomObject]@{memoryMB=6144;unknown='keep'}
if((Get-WarfareHeapMB $settings $facts) -ne 6144 -or $settings.memoryMB -ne 6144){throw 'Explicit heap override changed'}
Expect-Error {Get-WarfareHeapMB ([PSCustomObject]@{memoryMB=100}) $facts} 'RV_MEMORY_INVALID'
Expect-Error {Get-WarfareHeapMB ([PSCustomObject]@{}) ([PSCustomObject]@{ramMB=2048;serverHeapMB=0})} 'RV_MEMORY_LOW'
Expect-Error {Get-WarfareHeapMB ([PSCustomObject]@{memoryMB=8192}) ([PSCustomObject]@{ramMB=8192;serverHeapMB=0})} 'RV_MEMORY_BUDGET'
'heap is bounded, accounts for local server memory and preserves explicit allocation: PASS'
Add-Type -AssemblyName System.IO.Compression.FileSystem
foreach($case in @(@('server.jar','net.minecraftforge.fml.relauncher.ServerLaunchWrapper'),@('forge-unrelated.jar','player.OtherApp'))){
    $archive=[IO.Compression.ZipFile]::Open((Join-Path $fixture $case[0]),'Create')
    try{$entry=$archive.CreateEntry('META-INF/MANIFEST.MF');$writer=[IO.StreamWriter]::new($entry.Open());try{$writer.Write("Main-Class: "+$case[1]+"`r`n")}finally{$writer.Dispose()}}finally{$archive.Dispose()}
}
function Get-CimInstance {param($ClassName,$Filter,$ErrorAction)
    switch($ClassName){
        'Win32_ComputerSystem'{return [PSCustomObject]@{TotalPhysicalMemory=16GB}}
        'Win32_Processor'{return [PSCustomObject]@{NumberOfLogicalProcessors=8}}
        'Win32_Process'{return @([PSCustomObject]@{CommandLine=('java.exe -Xmx12G -jar "'+(Join-Path $fixture 'server.jar')+'" nogui')},[PSCustomObject]@{CommandLine=('java.exe -Xmx100G -jar "'+(Join-Path $fixture 'forge-unrelated.jar')+'"')},[PSCustomObject]@{CommandLine='java.exe -Xmx4G -cp client net.minecraft.client.main.Main'})}
    }
}
$facts=Get-WarfareHardwareFacts
if($facts.ramMB -ne 16384 -or $facts.logicalProcessors -ne 8 -or $facts.serverHeapMB -ne 12288){throw 'Foreign Java counted as Minecraft server'}
'server memory is counted only for a verified server main class or JAR manifest: PASS'
if(Test-WarfareGameProcess ('"'+$fixture+'\runtime\bin\java.exe" -Xmx4G -jar server.jar') $fixture){throw 'Shared runtime server detected as client'}
if(-not (Test-WarfareGameProcess ('java.exe --gameDir "'+$fixture.ToUpperInvariant()+'" --username Player') $fixture)){throw 'Own client not detected'}
if(Test-WarfareGameProcess ('java.exe --gameDir "'+$fixture+'-other"') $fixture){throw 'Another instance detected as own'}
'client detection compares the exact game directory rather than a shared Java path: PASS'
$effects=Join-Path $fixture 'config/enhancedvisuals-client.json'
if(Test-Path -LiteralPath $effects){throw 'Applying old profiles created an unsupported effects config'}
Copy-Item -LiteralPath (Join-Path $workspace 'patches/controls/config/enhancedvisuals-client.json') -Destination $effects
$document=Get-Content -LiteralPath $effects -Raw -Encoding UTF8|ConvertFrom-Json
$document|Add-Member NoteProperty unknown ([PSCustomObject]@{text='личное';array=@('retain','中文')})
$document.handlers.explosion.dust|Add-Member NoteProperty unknown 17
$document|ConvertTo-Json -Depth 64|Set-Content -LiteralPath $effects -Encoding UTF8
Set-WarfarePerformanceProfile -Root $fixture -Profile low -Language ru -ApplyGraphics
$document=Get-Content -LiteralPath $effects -Raw -Encoding UTF8|ConvertFrom-Json
if(-not $document.handlers.explosion.dust.disabled -or $document.handlers.damage.opacity -ne 0.2 -or $document.handlers.heartbeat.lowhealth.opacity -ne 0.2 -or -not $document.handlers.explosion.blur.disabled -or -not $document.handlers.splash.blur.disabled -or -not $document.handlers.heartbeat.blur.disabled -or $document.unknown.text -ne 'личное' -or $document.unknown.array[1] -ne '中文' -or $document.handlers.explosion.dust.unknown -ne 17){throw 'Low effects profile lost known or unknown fields'}
'Low applies the native effects keys and preserves nested unknown Unicode values: PASS'
$effectHash=(Get-FileHash -LiteralPath $effects).Hash
Set-WarfarePerformanceProfile -Root $fixture -Language en -LanguageOnly
if((Get-FileHash -LiteralPath $effects).Hash -ne $effectHash){throw 'Language modified native effects'}
Set-WarfarePerformanceProfile -Root $fixture -Profile balanced -Language en -ApplyGraphics
$document=Get-Content -LiteralPath $effects -Raw -Encoding UTF8|ConvertFrom-Json
if($document.handlers.explosion.dust.disabled -or $document.handlers.damage.opacity -ne 0.35 -or $document.handlers.heartbeat.lowhealth.opacity -ne 0.25 -or $document.unknown.text -ne 'личное'){throw 'Balanced effects did not apply'}
'Language leaves effects intact and explicit Balanced restores its known effect values: PASS'
$snapshots=@{};foreach($path in @($options,$shaders,$preferences,$effects)){$snapshots[$path]=[IO.File]::ReadAllBytes($path)}
$effectLock=[IO.File]::Open($effects,'Open','Read','Read')
try{$rejected=$false;try{Set-WarfarePerformanceProfile -Root $fixture -Profile low -Language ru -ApplyGraphics}catch{$rejected=$true};if(-not $rejected){throw 'Locked effect config unexpectedly changed'}}finally{$effectLock.Dispose()}
foreach($path in $snapshots.Keys){if([Convert]::ToBase64String([IO.File]::ReadAllBytes($path)) -cne [Convert]::ToBase64String($snapshots[$path])){throw 'Locked effects apply did not restore every previous file'}}
'Native file locking rolls back all previous profile writes exactly: PASS'
[IO.File]::WriteAllText($effects,'{broken')
$before=@{};foreach($path in @($options,$shaders,$preferences)){$before[$path]=(Get-FileHash -LiteralPath $path).Hash}
Expect-Error {Set-WarfarePerformanceProfile -Root $fixture -Profile low -Language ru -ApplyGraphics} 'RV_EFFECTS_CONFIG'
foreach($path in $before.Keys){if((Get-FileHash -LiteralPath $path).Hash -ne $before[$path]){throw 'Malformed effects changed another setting'}}
'Malformed effect configuration is rejected before writing other settings: PASS'
[IO.File]::WriteAllText((Join-Path $fixture 'report.json'),(@{passed=13;physicalWeakPC=$false;nativeEffectsRuntimeTested=$false;root=$fixture}|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
'13 performance acceptance groups passed'
