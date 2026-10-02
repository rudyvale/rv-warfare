param([string]$Candidate)
$ErrorActionPreference='Stop'
$workspace=Split-Path -Parent $PSScriptRoot
$root=Join-Path $workspace ('.local/qa-1.1.0/onboarding-state-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root -Force|Out-Null
$frozen=Join-Path $root 'source';New-Item -ItemType Directory -Path $frozen -Force|Out-Null
$sourceHashes=@{}
foreach($name in @('Warfare-Connection.ps1','Warfare-Onboarding.ps1','Configure-Controller.ps1','Configure-FirstPlay.ps1')){
    Copy-Item -LiteralPath (Join-Path $workspace ('src/'+$name)) -Destination $frozen
    $sourceHashes[$name]=(Get-FileHash -LiteralPath (Join-Path $frozen $name)).Hash.ToLowerInvariant()
}
. (Join-Path $frozen 'Warfare-Connection.ps1')
. (Join-Path $frozen 'Warfare-Onboarding.ps1')
Initialize-WarfareSetupUI
[Windows.Forms.Application]::SetUnhandledExceptionMode([Windows.Forms.UnhandledExceptionMode]::ThrowException)
$parent=[Windows.Forms.Form]::new();$parent.Opacity=0;$parent.ShowInTaskbar=$false;$parent.Show()
$results=@()
function Control($Window,[string]$Name){@($Window.Controls.Find($Name,$true))[0]}
function Read-Settings([string]$Instance){Get-Content -LiteralPath (Join-Path $Instance 'warfare-settings.json') -Raw -Encoding UTF8|ConvertFrom-Json}
function Profile-Bytes([string]$Instance){[Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $Instance 'config/vm-controller.properties')))}
function New-Instance([string]$Name){
    $instance=Join-Path $root $Name;New-Item -ItemType Directory -Path $instance,(Join-Path $instance 'mods'),(Join-Path $instance 'config') -Force|Out-Null
    foreach($file in Get-ChildItem -LiteralPath $frozen -File){Copy-Item -LiteralPath $file.FullName -Destination $instance}
    if($Candidate){Copy-Item -LiteralPath $Candidate -Destination (Join-Path $instance 'mods/mcheli.jar')}
    $settings=@{nickname='QAWizard';memoryMB=2560;language='en';unknown=@{value='retain';version=7};connectionMode='direct';connectionTarget='old.example';serverPort=25570;firstPlay=@{schema=1;completed=$true;scope='client';inputMode='radio';device='old-radio';brand='RadioMaster'}}
    Save-WarfareSetupSettings $instance $settings
    [IO.File]::WriteAllText((Join-Path $instance 'config/vm-controller.properties'),"enabled=true`r`nkind=radio`r`ndevice=old-radio`r`nkeyboardFlight=advanced`r`nroll.axis=3`r`nunknown=retain`r`n",[Text.UTF8Encoding]::new($false))
    return $instance
}
function Run-Wizard([string]$Instance,[scriptblock]$Action){
    $script:driverAction=$Action;$script:stage=0;$script:instance=$Instance;$script:failure='';$script:deadline=[DateTime]::UtcNow.AddSeconds(40)
    $driver=[Windows.Forms.Timer]::new();$driver.Interval=75
    $driver.Add_Tick({
        $window=@([Windows.Forms.Application]::OpenForms|Where-Object Name -eq firstPlay)|Select-Object -First 1
        if(-not $window){return};$window.Opacity=0
        try{if([DateTime]::UtcNow -gt $script:deadline){throw 'Independent wizard deadline exceeded'};& $script:driverAction $window}
        catch{$script:failure=$_.Exception.Message;$window.Dispose()}
    })
    $driver.Start()
    try{$answer=Show-WarfareOnboarding -Root $Instance -Parent $parent -Language en -Reconfigure}
    finally{$driver.Stop();$driver.Dispose()}
    if($script:failure){throw $script:failure};return $answer
}
function Assert-PersonalState([string]$Instance){$actual=Read-Settings $Instance;if($actual.nickname -ne 'QAWizard' -or $actual.memoryMB -ne 2560 -or $actual.unknown.value -ne 'retain' -or $actual.unknown.version -ne 7 -or $actual.connectionTarget -ne 'old.example' -or $actual.serverPort -ne 25570){throw 'Personal preferences or saved connection changed'}}
try{
    $instance=New-Instance 'keyboard-cancel';$old=Profile-Bytes $instance
    $answer=Run-Wizard $instance {param($w)
        if((Control $w 'setupPage0').Visible){(Control $w 'inputEasy').Checked=$true;(Control $w 'setupNext').PerformClick();return}
        if((Control $w 'setupPage2').Visible){(Control $w 'setupCancel').PerformClick()}
    }
    Assert-PersonalState $instance;$saved=Read-Settings $instance
    if($answer.completed -or (Profile-Bytes $instance) -cne $old -or -not $saved.firstPlay.completed -or $saved.firstPlay.inputMode -ne 'radio' -or $saved.firstPlay.device -ne 'old-radio'){throw 'Cancelled keyboard reconfiguration split persisted state'}
    $resume=Show-WarfareOnboarding -Root $instance -Parent $parent -Language en
    if(-not $resume.completed -or $resume.settings.firstPlay.inputMode -ne 'radio' -or (Profile-Bytes $instance) -cne $old){throw 'Next launch skipped into mismatched controls'}
    $results+=@{name='Keyboard reconfigure then connection cancel and next launch';passed=$true;nativeBackendTested=$true}
    $instance=New-Instance 'calibration-cancel';$old=Profile-Bytes $instance
    $bridge=@'
param([string]$InstallRoot,[string]$WizardAction,[string]$ReportPath,[string]$Kind,[string]$DeviceId)
$ErrorActionPreference='Stop'
$profile=@{enabled=$true;calibrated=$true;connected=$true;kind=$Kind;device=$DeviceId;deviceName='Fixture radio'}
if($WizardAction -eq 'Probe'){$report=@{schema=1;devices=@(@{id='fixture-radio';name='Fixture radio';axisCount=4});profile=$profile}}
else{[IO.File]::WriteAllText((Join-Path $InstallRoot 'config/vm-controller.properties'),'enabled=true;new external calibration');$report=@{schema=1;outcome='saved';profile=$profile}}
[IO.File]::WriteAllText($ReportPath,($report|ConvertTo-Json -Depth 8))
'@
    [IO.File]::WriteAllText((Join-Path $instance 'Configure-Controller.ps1'),$bridge)
    $answer=Run-Wizard $instance {param($w)
        if($script:stage -eq 0){(Control $w 'inputRadio').Checked=$true;(Control $w 'setupNext').PerformClick();$script:stage=1;return}
        if($script:stage -eq 1 -and (Control $w 'setupCalibrate').Enabled){(Control $w 'setupCalibrate').PerformClick();$script:stage=2;return}
        if($script:stage -eq 2 -and (Control $w 'setupNext').Enabled){if((Profile-Bytes $script:instance) -ceq $old){throw 'External calibration never changed the actual profile'};(Control $w 'setupNext').PerformClick();$script:stage=3;return}
        if($script:stage -eq 3 -and (Control $w 'setupPage2').Visible){(Control $w 'setupCancel').PerformClick()}
    }
    Assert-PersonalState $instance;$saved=Read-Settings $instance
    if($answer.completed -or (Profile-Bytes $instance) -cne $old -or $saved.firstPlay.inputMode -ne 'radio' -or $saved.firstPlay.device -ne 'old-radio' -or -not $saved.firstPlay.completed){throw 'Cancelled calibration did not restore coherent prior state'}
    $results+=@{name='External calibration save then connection cancel restores byte-exact prior state';passed=$true;nativeBackendTested=$false;physicalDeviceTested=$false}
    $instance=New-Instance 'ignored-cancel-child'
    $waitSource=Join-Path $instance 'RVSetupWait.java';[IO.File]::WriteAllText($waitSource,'public class RVSetupWait { public static void main(String[] args) throws Exception { Thread.sleep(120000); } }')
    $java=Join-Path $env:LOCALAPPDATA 'Warfare-1.12.2/runtime/bin/java.exe'
    & $java -jar (Join-Path $workspace '.local/tools/ecj-4.6.1.jar') -1.8 -nowarn -d $instance $waitSource
    if($LASTEXITCODE -ne 0){throw 'Owned wait helper compilation failed'}
    $bridge=@'
param([string]$InstallRoot,[string]$ReportPath)
$ErrorActionPreference='Stop'
$java=Join-Path $env:LOCALAPPDATA 'Warfare-1.12.2/runtime/bin/java.exe'
$child=Start-Process -FilePath $java -ArgumentList @('-cp',('"'+$InstallRoot+'"'),'RVSetupWait') -WindowStyle Hidden -PassThru
$null=$child.Handle
[IO.File]::WriteAllText((Join-Path $InstallRoot 'owned-processes.json'),(@{parentPID=$PID;javaPID=$child.Id;javaStarted=$child.StartTime.ToUniversalTime().Ticks}|ConvertTo-Json))
Start-Sleep -Seconds 90
'@
    [IO.File]::WriteAllText((Join-Path $instance 'Configure-Controller.ps1'),$bridge)
    $started=[DateTime]::UtcNow
    $answer=Run-Wizard $instance {param($w)
        if($script:stage -eq 0){(Control $w 'inputRadio').Checked=$true;(Control $w 'setupNext').PerformClick();$script:stage=1;return}
        if($script:stage -eq 1 -and (Test-Path -LiteralPath (Join-Path $script:instance 'owned-processes.json'))){if(-not (Control $w 'setupCancel').Enabled){throw 'Cannot cancel a running native setup task'};$w.Close();$script:stage=2}
    }
    $owned=Get-Content -LiteralPath (Join-Path $instance 'owned-processes.json') -Raw|ConvertFrom-Json
    if($answer.completed -or ([DateTime]::UtcNow-$started).TotalSeconds -gt 10 -or (Get-Process -Id $owned.parentPID -ErrorAction SilentlyContinue) -or (Get-Process -Id $owned.javaPID -ErrorAction SilentlyContinue)){throw 'Closing busy wizard leaked an owned backend or Java child'}
    Assert-PersonalState $instance
    $results+=@{name='Close busy wizard when backend ignores cancellation, stop actual owned Java and PowerShell';passed=$true;nativeBackendTested=$false;actualOwnedJavaProcessTested=$true}
    if($Candidate){
        $instance=New-Instance 'native-keyboard-complete'
        $answer=Run-Wizard $instance {param($w)
            if((Control $w 'setupPage0').Visible){(Control $w 'inputEasy').Checked=$true;(Control $w 'setupNext').PerformClick();return}
            if((Control $w 'setupPage2').Visible -and (Control $w 'setupNext').Enabled){(Control $w 'setupNext').PerformClick()}
        }
        Assert-PersonalState $instance;$saved=Read-Settings $instance;$profile=[IO.File]::ReadAllText((Join-Path $instance 'config/vm-controller.properties'))
        if(-not $answer.completed -or $saved.firstPlay.inputMode -ne 'easy' -or -not $saved.firstPlay.completed -or $profile -notmatch '(?m)^enabled=false' -or $profile -notmatch '(?m)^keyboardFlight=easy' -or $profile -notmatch '(?m)^roll.axis=3' -or $profile -notmatch '(?m)^unknown=retain'){throw 'Actual native Keyboard backend did not commit coherent state'}
        $results+=@{name='Actual Java Keyboard commit matches first-play metadata and preserves calibration';passed=$true;nativeBackendTested=$true}
    }
    $report=@{passed=$true;sourceHashes=$sourceHashes;cases=$results;physicalDeviceTested=$false;root=$root}
    [IO.File]::WriteAllText((Join-Path $root 'report.json'),($report|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
    $results|ForEach-Object {$_.name+': PASS'}
    'FINAL '+(Join-Path $root 'report.json')
}finally{$parent.Dispose()}
