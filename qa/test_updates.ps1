$ErrorActionPreference = 'Stop'
$env:VM_SKIP_UPDATE_CHECK = '1'
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $root 'src\Warfare-Updates.ps1')
$testRoot = Join-Path $PSScriptRoot ('updates-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
function Assert([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Reject([scriptblock]$Action, [string]$Message) { $failed=$false; try { & $Action | Out-Null } catch { $failed=$true }; Assert $failed $Message }
function Release([string]$Tag='v1.1.0') {
    return [PSCustomObject]@{tag_name=$Tag;draft=$false;prerelease=$false;assets=@([PSCustomObject]@{name='RV-Setup.zip';state='uploaded';size=100;digest=('sha256:' + ('a'*64));browser_download_url=('https://github.com/rudyvale/rv-warfare/releases/download/' + $Tag + '/RV-Setup.zip')})}
}
Assert ((ConvertTo-VmRelease (Release) '1.0.0').state -eq 'available') 'New release not detected'
Assert ((ConvertTo-VmRelease (Release) '1.1.0').state -eq 'current') 'Equal version must not update'
Assert ((ConvertTo-VmRelease (Release) '2.0.0').state -eq 'current') 'Downgrade offered'
Assert ((Get-VmVersion '1.10.0') -gt (Get-VmVersion '1.9.0')) 'Version ordering is lexical'
foreach ($invalid in @('main','1.0','1.0.0-beta','01.0.0','1.0.0/../../bad')) { Reject { Get-VmVersion $invalid } 'Invalid version accepted' }
$release=Release; $release.draft=$true; Reject { ConvertTo-VmRelease $release '1.0.0' } 'Draft accepted'
$release=Release; $release.prerelease=$true; Reject { ConvertTo-VmRelease $release '1.0.0' } 'Prerelease accepted'
$release=Release; $release.assets[0].digest=''; Reject { ConvertTo-VmRelease $release '1.0.0' } 'Missing checksum accepted'
$release=Release; $release.assets[0].browser_download_url='https://example.com/RV-Setup.zip'; Reject { ConvertTo-VmRelease $release '1.0.0' } 'Wrong repository accepted'
$release=Release; $release.assets += $release.assets[0]; Reject { ConvertTo-VmRelease $release '1.0.0' } 'Duplicate asset accepted'
$release=Release; $release.assets[0].size=3GB; Reject { ConvertTo-VmRelease $release '1.0.0' } 'Oversized download accepted'
'release policy and semantic versions: PASS'
$sample=Join-Path $testRoot 'hash.txt'; [IO.File]::WriteAllText($sample,'fixture')
Test-VmPackageHash $sample ((Get-FileHash $sample).Hash.ToLowerInvariant())
Reject { Test-VmPackageHash $sample ('0'*64) } 'Corrupt package accepted'
'SHA-256 corruption rejection: PASS'
$state=Join-Path $testRoot 'state.json'; Write-VmJson $state @{value=1}; Write-VmJson $state @{value=2}
Assert ((Get-Content $state -Raw|ConvertFrom-Json).value -eq 2) 'State was not replaced'
'atomic state replacement: PASS'
Assert (Get-VmAutoCheck $testRoot) 'Auto check must be enabled by default'
Set-VmAutoCheck $testRoot $false
Assert (-not (Get-VmAutoCheck $testRoot)) 'Disabled preference was not saved'
Set-VmAutoCheck $testRoot $true
Assert (Get-VmAutoCheck $testRoot) 'Enabled preference was not saved'
Write-VmJson (Join-Path $testRoot '.updates\preferences.json') @{autoCheck='false'}
Assert (Get-VmAutoCheck $testRoot) 'Non-boolean preference accepted'
'persistent update preference defaults to enabled: PASS'
$old=Join-Path $testRoot 'old'; $new=Join-Path $testRoot 'new'
New-Item -ItemType Directory -Path $old,$new -Force|Out-Null
Write-VmJson (Join-Path $old 'release.json') @{version='1.0.0'}
Write-VmJson (Join-Path $new 'release.json') @{version='1.1.0'}
Assert-VmUpgrade $new $old
Assert-VmUpgrade $new $new
Reject { Assert-VmUpgrade $old $new } 'Older installer could downgrade existing installation'
Reject { Assert-VmUpgrade $testRoot $new } 'Unversioned installer could downgrade existing installation'
'older and unversioned installer downgrade protection: PASS'
[IO.File]::WriteAllText((Join-Path $old 'Check-WarfareUpdate.ps1'),'fixture')
$env:VM_SKIP_UPDATE_CHECK = '0'
function Start-Process { param($FilePath,$ArgumentList,$WindowStyle) $script:capturedArguments=$ArgumentList }
try {
    Start-VmUpdateCheck $new $old
    Assert ($script:capturedArguments -match '-CurrentVersion "1.1.0"') 'Background check used old package version instead of installed version'
    Set-VmAutoCheck $new $false
    $script:capturedArguments=$null
    Start-VmUpdateCheck $new $old
    Assert (-not $script:capturedArguments) 'Disabled startup launched a worker'
} finally {
    Remove-Item Function:Start-Process
    $env:VM_SKIP_UPDATE_CHECK = '1'
}
'background check uses installed version and respects opt-out: PASS'
Add-Type -AssemblyName System.IO.Compression.FileSystem
function Archive([string]$Name, [string]$Extra='', [string]$Version='1.1.0', [bool]$WithoutPerformance=$false, [bool]$WithoutProtocol=$false, [string]$MissingFirstPlay='') {
    $file=Join-Path $testRoot $Name
    $zip=[IO.Compression.ZipFile]::Open($file,'Create')
    try {
        $names=@('Install-Warfare.ps1','Warfare-Launcher.ps1','Play-Warfare.ps1','Warfare-Connection.ps1','Warfare-Updates.ps1','Check-WarfareUpdate.ps1','Configure-Controller.ps1','package-manifest.json','installer-files.json','payload.zip','runtime.zip','code.ico','release.json')
        if ([version]$Version -ge [version]'1.1.0' -and -not $WithoutPerformance) { $names += 'Warfare-Performance.ps1' }
        if ([version]$Version -ge [version]'1.1.0') { $names += @('Warfare-Onboarding.ps1','Configure-FirstPlay.ps1','THIRD-PARTY-NOTICES.md') | Where-Object { $_ -cne $MissingFirstPlay } }
        $releaseMetadata=@{version=$Version;repository='rudyvale/rv-warfare'}
        if ([version]$Version -ge [version]'1.1.0' -and -not $WithoutProtocol) { $releaseMetadata.requiredMods=@{mcheli='fixture-protocol'} }
        foreach ($name in $names) {
            $entry=$zip.CreateEntry('RV-Setup/'+$name); $writer=[IO.StreamWriter]::new($entry.Open())
            try { $writer.Write($(if($name -eq 'release.json'){$releaseMetadata|ConvertTo-Json}else{'fixture'})) } finally {$writer.Dispose()}
        }
        if($Extra){[void]$zip.CreateEntry($Extra)}
    } finally {$zip.Dispose()}
    return $file
}
$safe=Archive 'safe.zip'; $expanded=Expand-VmPackage $safe (Join-Path $testRoot 'safe') '1.1.0'
Assert (Test-Path (Join-Path $expanded 'Install-Warfare.ps1')) 'Safe archive failed'
$legacy=Archive 'legacy.zip' '' '1.0.0'
$legacyExpanded=Expand-VmPackage $legacy (Join-Path $testRoot 'legacy') '1.0.0'
Assert (-not (Test-Path (Join-Path $legacyExpanded 'Warfare-Performance.ps1'))) 'Legacy package compatibility fixture failed'
$incomplete=Archive 'missing-performance.zip' '' '1.1.0' $true
$incompleteRoot=Join-Path $testRoot 'incomplete'
Reject { Expand-VmPackage $incomplete $incompleteRoot '1.1.0' } 'RV 1.1.0 without performance helper accepted'
Assert (-not (Test-Path $incompleteRoot)) 'Incomplete package wrote files before validation'
'performance helper boundary and 1.0.0 compatibility: PASS'
$noProtocol=Archive 'missing-protocol.zip' '' '1.1.0' $false $true
$noProtocolRoot=Join-Path $testRoot 'missing-protocol'
Reject { Expand-VmPackage $noProtocol $noProtocolRoot '1.1.0' } 'RV 1.1.0 without server mod version accepted'
Assert (-not (Test-Path $noProtocolRoot)) 'Package without protocol wrote files before validation'
'required server mod metadata boundary: PASS'
foreach ($name in @('Warfare-Onboarding.ps1','Configure-FirstPlay.ps1')) {
    $missing=Archive ([Guid]::NewGuid().ToString('N')+'.zip') '' '1.1.0' $false $false $name
    $missingRoot=Join-Path $testRoot ([Guid]::NewGuid().ToString('N'))
    Reject { Expand-VmPackage $missing $missingRoot '1.1.0' } ('RV 1.1.0 without first-play helper accepted: ' + $name)
    Assert (-not (Test-Path $missingRoot)) 'Package without first-play helper wrote files before validation'
}
'first-play helper closure before extraction: PASS'
$noNotices=Archive 'missing-notices.zip' '' '1.1.0' $false $false 'THIRD-PARTY-NOTICES.md'
$noNoticesRoot=Join-Path $testRoot 'missing-notices'
Reject { Expand-VmPackage $noNotices $noNoticesRoot '1.1.0' } 'RV 1.1.0 without installed source notices accepted'
Assert (-not (Test-Path $noNoticesRoot)) 'Package without notices wrote files before validation'
'source notices closure before extraction: PASS'
foreach($entry in @('RV-Setup/../escape.ps1','RV-Setup/../../escape.ps1','RV-Setup/file:stream','outside/file','RV-Setup/folder./file','RV-Setup/release.json')) {
    $zip=Archive ([Guid]::NewGuid().ToString('N')+'.zip') $entry
    Reject { Expand-VmPackage $zip (Join-Path $testRoot ([Guid]::NewGuid().ToString('N'))) '1.1.0' } ('Unsafe archive accepted: '+$entry)
}
$wrong=Archive 'wrong-version.zip' '' '1.0.0'; Reject { Expand-VmPackage $wrong (Join-Path $testRoot 'wrong') '1.1.0' } 'Wrong archive version accepted'
'ZIP traversal, duplicate entries and wrong version rejection: PASS'
$worker=Get-Content (Join-Path $root 'src\Check-WarfareUpdate.ps1') -Raw -Encoding UTF8
$worker=$worker.Replace(". (Join-Path `$PSScriptRoot 'Warfare-Updates.ps1')", ". '" + (Join-Path $root 'src\Warfare-Updates.ps1') + "'`nfunction Get-VmRelease { throw 'Offline fixture' }")
$probe=Join-Path $testRoot 'offline.ps1'; [IO.File]::WriteAllText($probe,$worker,[Text.UTF8Encoding]::new($true))
$shell=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
& $shell -NoProfile -ExecutionPolicy Bypass -File $probe -Root $testRoot -CurrentVersion '1.0.0'
Assert ($LASTEXITCODE -eq 0) 'Offline check blocks launch'
Assert (Test-Path (Join-Path $testRoot '.updates\last-error.json')) 'Offline diagnostic missing'
Assert (-not (Test-Path (Join-Path $testRoot '.updates\status.json'))) 'Offline check reported false success'
'offline startup is quiet and does not report success: PASS'
$lock=[IO.File]::Open((Join-Path $testRoot '.updates\check.lock'),'OpenOrCreate','ReadWrite','None')
try {
    & $shell -NoProfile -ExecutionPolicy Bypass -File $probe -Root $testRoot -CurrentVersion '1.0.0'
    Assert ($LASTEXITCODE -eq 0) 'Parallel check blocks launch'
} finally {$lock.Dispose()}
'concurrent checks do not interrupt launch: PASS'
Set-VmAutoCheck $testRoot $false
Remove-Item -LiteralPath (Join-Path $testRoot '.updates\last-error.json')
& $shell -NoProfile -ExecutionPolicy Bypass -File $probe -Root $testRoot -CurrentVersion '1.0.0'
Assert ($LASTEXITCODE -eq 0) 'Disabled check failed'
Assert (-not (Test-Path (Join-Path $testRoot '.updates\last-error.json'))) 'Disabled check touched the network'
'disabled worker performs no network request: PASS'
