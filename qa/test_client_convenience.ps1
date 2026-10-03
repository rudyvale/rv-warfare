param([Parameter(Mandatory=$true)][string]$WorkRoot,[Parameter(Mandatory=$true)][string]$ReportPath)
$ErrorActionPreference='Stop'
$workspace=Split-Path -Parent $PSScriptRoot
. (Join-Path $workspace 'src/Warfare-Connection.ps1')
. (Join-Path $workspace 'src/Warfare-ClientControls.ps1')
. (Join-Path $workspace 'src/Warfare-ConnectionProfiles.ps1')
. (Join-Path $workspace 'src/Warfare-Updates.ps1')
New-Item -ItemType Directory -Path $WorkRoot -Force|Out-Null
$cases=[Collections.Generic.List[string]]::new()
function Check([bool]$Value,[string]$Name){if(-not $Value){throw $Name};$cases.Add($Name)}
function Write-Options([string]$Text){[IO.File]::WriteAllText((Join-Path $WorkRoot 'options.txt'),$Text,[Text.UTF8Encoding]::new($true))}
function Equal-Bytes($Before,$After){return [Convert]::ToBase64String($Before) -ceq [Convert]::ToBase64String($After)}
Write-Options "resourcePacks:[`"Personal.zip`"]`r`nrenderDistance:7`r`ncustom:keep"
$path=Join-Path $WorkRoot 'options.txt';$before=[IO.File]::ReadAllBytes($path)
$result=Add-WarfareMissingOptionDefaults -Root $WorkRoot -Defaults @{key_Flashlight=64}
$after=[IO.File]::ReadAllBytes($path)
Check ($result.changed -and (Equal-Bytes $before $after[0..($before.Length-1)]) -and [IO.File]::ReadAllText($path).Contains('key_Flashlight:64')) 'missing-key-appended-with-exact-original-byte-prefix'
$result=Add-WarfareMissingOptionDefaults -Root $WorkRoot -Defaults @{key_Flashlight=64}
Check (-not $result.changed -and (Equal-Bytes $after ([IO.File]::ReadAllBytes($path)))) 'repeated-default-application-byte-preserved'
foreach($value in @('35','0','-99','64')){
    Write-Options ('key_Flashlight:'+$value+"`ncustom:keep`n")
    $before=[IO.File]::ReadAllBytes($path);$result=Add-WarfareMissingOptionDefaults -Root $WorkRoot -Defaults @{key_Flashlight=64}
    Check (-not $result.changed -and (Equal-Bytes $before ([IO.File]::ReadAllBytes($path)))) ('existing-key-'+$value+'-preserved')
}
Write-Options "key_Flashlight:35`nkey_Flashlight:64`n";$before=[IO.File]::ReadAllBytes($path)
$null=Add-WarfareMissingOptionDefaults -Root $WorkRoot -Defaults @{key_Flashlight=64}
Check (Equal-Bytes $before ([IO.File]::ReadAllBytes($path))) 'existing-duplicate-key-lines-untouched'
$failed=$false;try{Add-WarfareMissingOptionDefaults -Root $WorkRoot -Defaults @{'key_bad:injection'=64}|Out-Null}catch{$failed=$true}
Check ($failed -and (Equal-Bytes $before ([IO.File]::ReadAllBytes($path)))) 'invalid-default-does-not-rewrite-options'
Check (Test-WarfareKeyboardDefaultsReady $WorkRoot) 'missing-controller-profile-uses-native-keyboard-default'
$profile=Join-Path $WorkRoot 'config/vm-controller.properties';New-Item -ItemType Directory -Path (Split-Path -Parent $profile) -Force|Out-Null
[IO.File]::WriteAllText($profile,"enabled=true`nkeyboardFlight=easy`n")
Check (-not(Test-WarfareKeyboardDefaultsReady $WorkRoot)) 'enabled-radio-not-claimed-keyboard-ready'
[IO.File]::WriteAllText($profile,"enabled=false`nkeyboardFlight=acro`n")
Check (-not(Test-WarfareKeyboardDefaultsReady $WorkRoot)) 'custom-keyboard-mode-not-overridden'
[IO.File]::WriteAllText($profile,"enabled=false`nkeyboardFlight=easy`n")
Check (Test-WarfareKeyboardDefaultsReady $WorkRoot) 'existing-native-keyboard-profile-ready'
$valid='{"schema":1,"product":"RV","transport":"porthole","target":"ABCD1234","port":27111,"version":"2.0.0","label":"RV test"}'
$invite=ConvertFrom-WarfareInvite -Json $valid
Check ($invite.connection.connectionMode -ceq 'porthole' -and $invite.connection.serverPort -eq 27111 -and $invite.version -ceq '2.0.0') 'dynamic-invitation-port-read-without-command-execution'
$invitePath=Join-Path $WorkRoot 'test.rvinvite';[IO.File]::WriteAllText($invitePath,$valid,[Text.UTF8Encoding]::new($true))
Check ((ConvertFrom-WarfareInvite -Path $invitePath).connection.serverPort -eq 27111) 'utf8-invitation-file-import'
$invalid=@(
    $valid.Replace('"schema":1','"schema":1,"schema":1'),
    $valid.Replace('"schema":1','"schema":1,"\u0073chema":1'),
    $valid.Replace('"schema":1','"schema":true'),
    $valid.Replace('"port":27111','"port":0'),
    $valid.Replace('"port":27111','"port":65536'),
    $valid.Replace('"port":27111','"port":"27111"'),
    $valid.Replace('"port":27111','"port":27111.0'),
    $valid.Replace('"target":"ABCD1234"','"target":"https://example.invalid"'),
    $valid.Replace('"target":"ABCD1234"','"target":"c:\\payload"'),
    $valid.Replace('"target":"ABCD1234"','"target":"abcd1234"'),
    $valid.Replace('"target":"ABCD1234"','"target":"peer:00000000000000000"'),
    $valid.Replace('"version":"2.0.0"','"version":"run.exe"'),
    $valid.Replace('"label":"RV test"','"label":"bad\nlabel"'),
    $valid.Replace('"label":"RV test"','"label":{"nested":"bad"}'),
    $valid.Replace('"label":"RV test"','"label":"RV test","token":"bad"'),
    $valid.Replace('"label":"RV test"','"label":"RV test","accounts":null'),
    ($valid+' {}'),
    ($valid.Substring(0,$valid.Length-1)+',}'),
    (' '*4097)
)
foreach($text in $invalid){$failed=$false;try{ConvertFrom-WarfareInvite -Json $text|Out-Null}catch{$failed=$true};Check $failed ('rejected-invitation-'+$cases.Count)}
$names=@(Get-VmPackageFiles '2.0.0')
Check ('Warfare-ClientControls.ps1' -in $names -and 'Warfare-ConnectionProfiles.ps1' -in $names -and 'Warfare-Ambience.ps1' -in $names -and 'vendor-catalog.json' -in $names) 'new-critical-helpers-in-package-readiness'
Check ('Warfare-ClientControls.ps1' -notin @(Get-VmPackageFiles '1.2.1')) 'legacy-package-contract-preserved'
$report=[PSCustomObject]@{success=$true;shell=$PSVersionTable.PSVersion.ToString();passed=$cases.Count;cases=@($cases);scope='actual isolated option/profile/invitation files and package contract; no GUI, user data or game processes touched'}
[IO.File]::WriteAllText($ReportPath,($report|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
$report|ConvertTo-Json -Depth 8
