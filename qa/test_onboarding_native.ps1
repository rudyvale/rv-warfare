param([string]$Candidate)
$ErrorActionPreference='Stop'
$env:VM_SKIP_UPDATE_CHECK='1'
$workspace=Split-Path -Parent $PSScriptRoot
. (Join-Path $workspace 'src/Warfare-Connection.ps1')
. (Join-Path $workspace 'src/Warfare-Onboarding.ps1')
Initialize-WarfareSetupUI
[Windows.Forms.Application]::SetUnhandledExceptionMode([Windows.Forms.UnhandledExceptionMode]::ThrowException)
if(-not $Candidate){$Candidate=Join-Path $workspace '.local/rv-1.1/easy-bridge/bridge/mods/mcheli.jar'}
$Candidate=[IO.Path]::GetFullPath($Candidate)
$root=Join-Path $workspace ('.local/rv-1.1/client-wizard-native-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root,(Join-Path $root 'mods'),(Join-Path $root 'config') -Force|Out-Null
Copy-Item -LiteralPath $Candidate -Destination (Join-Path $root 'mods/mcheli.jar')
foreach($name in @('Configure-Controller.ps1','Configure-FirstPlay.ps1','Warfare-Onboarding.ps1','Warfare-Connection.ps1')){Copy-Item -LiteralPath (Join-Path $workspace ('src/'+$name)) -Destination $root}
$profile=Join-Path $root 'config/vm-controller.properties'
$old="enabled=true`r`nkind=radio`r`nkeyboardFlight=pro`r`ndevice=old-device`r`nroll.axis=3`r`nroll.min=-1`r`nroll.max=1`r`nroll.center=0`r`nunknown=keep`r`n"
[IO.File]::WriteAllText($profile,$old,[Text.UTF8Encoding]::new($false))
$settings=[PSCustomObject]@{nickname='QAWizard';language='ru';memoryMB=2560;unknown='retain';connectionMode='porthole';connectionTarget='';serverPort=25565}
Save-WarfareSetupSettings $root $settings
$parent=[Windows.Forms.Form]::new();$parent.ShowInTaskbar=$false;$parent.Opacity=0;$parent.Show()
function Control($Window,[string]$Name){@($Window.Controls.Find($Name,$true))[0]}
function Capture($Window,[string]$Name){
    $bitmap=[Drawing.Bitmap]::new($Window.Width,$Window.Height)
    try{$Window.DrawToBitmap($bitmap,[Drawing.Rectangle]::new(0,0,$Window.Width,$Window.Height));$bitmap.Save((Join-Path $root $Name))}finally{$bitmap.Dispose()}
}
function Native-Wizard([scriptblock]$Action,[string]$Language='ru',[switch]$Owner){
    $script:nativeStep=0;$script:nativeError='';$script:nativeAction=$Action;$script:nativeDeadline=[DateTime]::UtcNow.AddSeconds(35)
    $driver=[Windows.Forms.Timer]::new();$driver.Interval=100
    $driver.Add_Tick({
        $window=@([Windows.Forms.Application]::OpenForms|Where-Object Name -eq firstPlay)|Select-Object -First 1
        if(-not $window){return};$window.Opacity=0
        try{if([DateTime]::UtcNow -gt $script:nativeDeadline){throw 'Native wizard deadline exceeded'};& $script:nativeAction $window}
        catch{$script:nativeError=$_.Exception.Message;$window.Dispose()}
    })
    $driver.Start()
    try{$result=Show-WarfareOnboarding -Root $root -Parent $parent -Language $Language -Owner:$Owner -Reconfigure}
    finally{$driver.Stop();$driver.Dispose()}
    if($script:nativeError){throw $script:nativeError};return $result
}
try {
    $probeReport=Join-Path $root 'actual-probe.json'
    $task=Start-WarfareSetupTask $root 'Probe' $probeReport 'radio' '' ''
    if(-not $task.WaitForExit(18000) -or $task.ExitCode -ne 0){throw 'Actual controller probe failed'}
    $task.Dispose();$probe=Get-Content -LiteralPath $probeReport -Raw -Encoding UTF8|ConvertFrom-Json
    if($probe.schema -ne 1){throw 'Actual controller report invalid'}
    $devices=@($probe.devices|ForEach-Object {$_})
    'Actual Java controller probe and structured device report: PASS'
    $result=Native-Wizard {param($w)
        if($script:nativeStep -eq 0){Capture $w 'first-play-ru.png';(Control $w 'inputRadio').Checked=$true;(Control $w 'setupNext').PerformClick();$script:nativeStep++;return}
        if((Control $w 'setupPage1').Visible -and (Control $w 'setupRescan').Enabled){
            $count=@($devices|Where-Object axisCount -ge 4).Count
            if((Control $w 'setupDevice').Items.Count -ne $count){throw 'Wizard differs from the actual device report'}
            if($count -eq 0 -and ((Control $w 'setupNext').Enabled -or (Control $w 'setupCalibrate').Enabled)){throw 'Wizard offered absent hardware'}
            Capture $w 'actual-radio-devices-ru.png';(Control $w 'setupCancel').PerformClick()
        }
    }
    if($result.completed -or [IO.File]::ReadAllText($profile) -cne $old){throw 'Cancel altered the native controller profile'}
    'Native radio step matches actual devices and cancellation preserves the profile: PASS'
    $result=Native-Wizard {param($w)
        if((Control $w 'setupPage0').Visible){(Control $w 'inputEasy').Checked=$true;(Control $w 'setupNext').PerformClick();return}
        if((Control $w 'setupPage2').Visible -and (Control $w 'setupNext').Enabled){(Control $w 'setupTarget').Text='QAAB12';Capture $w 'actual-server-ru.png';(Control $w 'setupNext').PerformClick()}
    }
    $actual=[IO.File]::ReadAllText($profile)
    if(-not $result.completed -or $actual -notmatch '(?m)^enabled=false' -or $actual -notmatch '(?m)^keyboardFlight=easy' -or $actual -notmatch '(?m)^roll.axis=3' -or $actual -notmatch '(?m)^unknown=keep' -or $result.settings.memoryMB -ne 2560 -or $result.settings.unknown -ne 'retain' -or $result.connection.connectionTarget -ne 'QAAB12'){throw 'Actual Keyboard profile or saved preferences failed'}
    'Native Keyboard applies Easy, preserves calibrated axes and saves the current server: PASS'
    $result=Native-Wizard {param($w);Capture $w 'first-play-en.png';(Control $w 'setupCancel').PerformClick()} -Language en
    if($result.completed){throw 'Native English cancellation completed'}
    $shell=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    & $shell -NoProfile -ExecutionPolicy Bypass -STA -File (Join-Path $root 'Configure-FirstPlay.ps1') -InstallRoot $root
    if($LASTEXITCODE -ne 0){throw 'Completed standalone wrapper did not exit zero'}
    'Standalone first-play wrapper skips completed setup and exits zero: PASS'
    $clientRoot=$root
    $root=Join-Path $clientRoot 'legacy-owner-game'
    New-Item -ItemType Directory -Path $root,(Join-Path $root 'mods'),(Join-Path $root 'config') -Force|Out-Null
    Copy-Item -LiteralPath $Candidate -Destination (Join-Path $root 'mods/mcheli.jar')
    foreach($name in @('Configure-Controller.ps1','Configure-FirstPlay.ps1','Warfare-Onboarding.ps1','Warfare-Connection.ps1')){Copy-Item -LiteralPath (Join-Path $workspace ('src/'+$name)) -Destination $root}
    $legacyPath=Join-Path $root 'Warfare-1.12.2.json';$legacyBytes=[Text.Encoding]::UTF8.GetBytes('{"id":"Warfare-1.12.2","unknown":"retain TLauncher profile"}')
    [IO.File]::WriteAllBytes($legacyPath,$legacyBytes)
    Save-WarfareSetupSettings $root ([PSCustomObject]@{memoryMB=0;unknown='owner-retain'})
    if(@('runtime','libraries','assets','installer-files.json')|Where-Object {Test-Path -LiteralPath (Join-Path $root $_)}){throw 'Legacy owner test accidentally uses a standalone layout'}
    $result=Native-Wizard {param($w)
        if($script:nativeStep -eq 0){(Control $w 'inputRadio').Checked=$true;(Control $w 'setupNext').PerformClick();$script:nativeStep++;return}
        if((Control $w 'setupPage1').Visible -and (Control $w 'setupRescan').Enabled){Capture $w 'legacy-owner-radio.png';(Control $w 'setupCancel').PerformClick()}
    } -Owner
    if($result.completed){throw 'Owner probe cancellation completed'}
    $result=Native-Wizard {param($w)
        if((Control $w 'setupPage2').Visible){throw 'Owner setup asked for a remote server'}
        if((Control $w 'setupPage0').Visible -and (Control $w 'setupNext').Enabled){(Control $w 'inputEasy').Checked=$true;(Control $w 'setupNext').PerformClick()}
    } -Owner
    & $shell -NoProfile -ExecutionPolicy Bypass -STA -File (Join-Path $root 'Configure-FirstPlay.ps1') -InstallRoot $root -Owner
    if($LASTEXITCODE -ne 0 -or -not $result.completed -or $result.settings.firstPlay.scope -ne 'owner' -or $result.settings.unknown -ne 'owner-retain' -or [Convert]::ToBase64String([IO.File]::ReadAllBytes($legacyPath)) -cne [Convert]::ToBase64String($legacyBytes)){throw 'Legacy owner setup altered its profile or failed'}
    'Legacy owner without local runtime, libraries, assets or manifest uses shared Java and preserves TLauncher data: PASS'
    $root=$clientRoot
    $report=@{status='PASS';candidateSHA256=(Get-FileHash -LiteralPath $Candidate -Algorithm SHA256).Hash.ToLowerInvariant();actualBackendTested=$true;physicalDeviceTested=$false;actualDeviceCount=$devices.Count;fixtureRoot=$root;groups=6;legacyOwnerBackendTested=$true;screens=@('first-play-ru.png','actual-radio-devices-ru.png','actual-server-ru.png','first-play-en.png','legacy-owner-game/legacy-owner-radio.png')}
    [IO.File]::WriteAllText((Join-Path $root 'report.json'),($report|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
    ('Report: '+(Join-Path $root 'report.json'))
}finally{$parent.Dispose()}
