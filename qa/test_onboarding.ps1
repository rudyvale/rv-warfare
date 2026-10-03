$ErrorActionPreference='Stop'
$env:VM_SKIP_UPDATE_CHECK='1'
$workspace=Split-Path -Parent $PSScriptRoot
. (Join-Path $workspace 'src/Warfare-Connection.ps1')
. (Join-Path $workspace 'src/Warfare-Onboarding.ps1')
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Initialize-WarfareSetupUI
[Windows.Forms.Application]::SetUnhandledExceptionMode([Windows.Forms.UnhandledExceptionMode]::ThrowException)
$testRoot=Join-Path $PSScriptRoot ('onboarding-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot -Force|Out-Null
$fakeBridge=@'
param([string]$InstallRoot,[string]$WizardAction,[string]$ReportPath,[string]$Kind,[string]$DeviceId,[string]$Brand,[string]$CancelPath)
$ErrorActionPreference='Stop'
Start-Sleep -Milliseconds 200
$report=@{schema=1;devices=@();profile=@{enabled=$false;connected=$false;calibrated=$false;kind=$Kind;device=$DeviceId;deviceName='Actual test device'}}
if($WizardAction -eq 'Probe'){
    $deviceFile=Join-Path $InstallRoot 'fixture-devices.json'
    if(Test-Path -LiteralPath $deviceFile){$decoded=Get-Content -LiteralPath $deviceFile -Raw|ConvertFrom-Json;$report.devices=@($decoded|ForEach-Object {$_})}
}elseif($WizardAction -eq 'Keyboard'){
    $report.outcome='saved';$report.inputMode='easy'
    [IO.File]::WriteAllText((Join-Path $InstallRoot 'keyboard-applied.txt'),'easy')
    [IO.File]::WriteAllText((Join-Path $InstallRoot 'config/vm-controller.properties'),'enabled=false')
}else{
    $behavior=Get-Content -LiteralPath (Join-Path $InstallRoot 'fixture-behavior.txt') -Raw
    $report.outcome=$behavior.Trim()
    $report.profile.enabled=$true;$report.profile.connected=$true;$report.profile.calibrated=$true
    if($report.outcome -eq 'invalid'){$report.outcome='saved';$report.profile.device='Wrong device'}
    if($report.outcome -eq 'saved'){[IO.File]::WriteAllText((Join-Path $InstallRoot 'config/vm-controller.properties'),'enabled=true;new-calibration')}
}
[IO.File]::WriteAllText($ReportPath,($report|ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
'@
$parent=[Windows.Forms.Form]::new();$parent.ShowInTaskbar=$false;$parent.Opacity=0;$parent.Show()
$script:cases=@()
function New-Instance([string]$Name,$Settings=@{},$Defaults=$null){
    $root=Join-Path $testRoot $Name;New-Item -ItemType Directory -Path $root,(Join-Path $root 'config') -Force|Out-Null
    [IO.File]::WriteAllText((Join-Path $root 'Configure-Controller.ps1'),$fakeBridge,[Text.UTF8Encoding]::new($true))
    Save-WarfareSetupSettings $root $Settings
    if($Defaults){[IO.File]::WriteAllText((Join-Path $root 'server-defaults.json'),($Defaults|ConvertTo-Json),[Text.UTF8Encoding]::new($false))}
    return $root
}
function Read-Settings([string]$Root){Get-Content -LiteralPath (Join-Path $Root 'warfare-settings.json') -Raw -Encoding UTF8|ConvertFrom-Json}
function Find-Control($Window,[string]$Name){@($Window.Controls.Find($Name,$true))[0]}
function Open-ControlChoice($Window){
    if((Find-Control $Window 'setupPage2').Visible){(Find-Control $Window 'setupBack').PerformClick()}
    if(-not(Find-Control $Window 'setupPage0').Visible){throw 'Control choice page is not visible'}
}
function Assert-SetupBounds($Window){
    foreach($page in 0..2){
        $panel=Find-Control $Window ('setupPage'+$page)
        if(-not $panel.Visible){continue}
        $controls=@($panel.Controls)
        foreach($control in $controls){if($control.Left -lt 0 -or $control.Top -lt 0 -or $control.Right -gt $panel.Width -or $control.Bottom -gt $panel.Height){throw ('Control outside setup page: '+$control.Name)}}
        for($i=0;$i -lt $controls.Count;$i++){for($j=$i+1;$j -lt $controls.Count;$j++){if($controls[$i].Bounds.IntersectsWith($controls[$j].Bounds)){throw ('Setup controls overlap: '+$controls[$i].Text+'/'+$controls[$j].Text)}}}
    }
    foreach($name in @('setupNext','setupBack','setupCancel')){
        $control=Find-Control $Window $name
        if($control.Bottom -gt $control.Parent.ClientSize.Height -or $control.Right -gt $control.Parent.ClientSize.Width){throw ('Footer clipped: '+$name)}
    }
}
function Run-Wizard([string]$Root,[scriptblock]$Actions,[string]$Language='ru',[switch]$Owner,[switch]$Reconfigure){
    $script:step=0;$script:callbackError='';$script:wizardWindow=$null
    $script:action=$Actions;$script:callbackRoot=$Root;$script:callbackLanguage=$Language
    $script:deadline=[DateTime]::UtcNow.AddSeconds(25)
    $driver=[Windows.Forms.Timer]::new();$driver.Interval=75
    $driver.Add_Tick({
        $window=@([Windows.Forms.Application]::OpenForms|Where-Object {$_.Name -eq 'firstPlay'})|Select-Object -First 1
        if(-not $window){return};$window.Opacity=0;$window.ShowInTaskbar=$false;$script:wizardWindow=$window
        try {
            if([DateTime]::UtcNow -gt $script:deadline){throw 'Wizard deadline exceeded'}
            Assert-SetupBounds $window
            & $script:action $window
        } catch {
            $script:callbackError=$_.Exception.Message
            [Console]::WriteLine($script:callbackError)
            $window.Dispose()
        }
    })
    $driver.Start()
    try{$result=Show-WarfareOnboarding -Root $Root -Language $Language -Parent $parent -Owner:$Owner -Reconfigure:$Reconfigure}
    finally{$driver.Stop();$driver.Dispose()}
    if($script:callbackError){throw $script:callbackError}
    return $result
}
function Record([string]$Name){$script:cases+=,$Name;Write-Output ($Name+': PASS')}
function Capture-Window($Window,[string]$Name){
    $bitmap=[Drawing.Bitmap]::new($Window.Width,$Window.Height)
    try{$Window.DrawToBitmap($bitmap,[Drawing.Rectangle]::new(0,0,$Window.Width,$Window.Height));$bitmap.Save((Join-Path $testRoot $Name))}finally{$bitmap.Dispose()}
}
try {
    $personal=@{nickname='Tester';language='ru';memoryMB=2560;unknown=@{text='личное'};connectionMode='direct';connectionTarget='saved.example';serverPort=25570}
    $root=New-Instance 'Отмена' $personal
    $result=Run-Wizard $root {param($w);Open-ControlChoice $w;Capture-Window $w 'first-play-ru.png';(Find-Control $w 'inputRadio').Checked=$true;(Find-Control $w 'setupCancel').PerformClick()}
    $saved=Read-Settings $root
    if($result.completed -or $saved.firstPlay -or $saved.firstPlayDraft.inputMode -ne 'radio' -or $saved.memoryMB -ne 2560 -or $saved.unknown.text -ne 'личное' -or $saved.connectionTarget -ne 'saved.example'){throw 'Cancel changed saved state'}
    Record 'Cancel stores a draft and preserves connection and unknown preferences'
    $result=Run-Wizard $root {param($w);if(-not (Find-Control $w 'inputRadio').Checked){throw 'Draft not resumed'};(Find-Control $w 'setupCancel').PerformClick()}
    if($result.completed){throw 'Cancelled resume completed'}
    Record 'Re-entry resumes the chosen input'
    $root=New-Instance 'Keyboard public' @{nickname='Tester';unknown='retain'}
    $result=Run-Wizard $root {param($w)
        $next=Find-Control $w 'setupNext'
        if($script:step -eq 0){
            if(-not (Find-Control $w 'inputEasy').Checked -or -not (Find-Control $w 'setupPage2').Visible){throw 'Fresh keyboard setup did not start at the server choice'}
            if((Find-Control $w 'setupServer').Items.Count -ne 1 -or (Find-Control $w 'setupTarget').Text){throw 'Public setup has private defaults'}
            $next.PerformClick()
            if((Find-Control $w 'setupStatus').Text -ne 'Укажи сервер в настройках.'){throw 'Empty target not rejected'}
            $script:step++;return
        }
        (Find-Control $w 'setupTarget').Text='abcd12';$next.PerformClick()
    }
    $saved=Read-Settings $root
    if(-not $result.completed -or $saved.firstPlay.inputMode -ne 'easy' -or $saved.connectionTarget -ne 'ABCD12' -or $saved.unknown -ne 'retain' -or (Test-Path -LiteralPath (Join-Path $root 'keyboard-applied.txt')) -or (Test-Path -LiteralPath (Join-Path $root 'config/vm-controller.properties'))){throw 'Keyboard/public setup failed'}
    Record 'Fresh keyboard defaults skip the bridge, validate an empty public target and save the current code'
    $script:called=$false
    $result=Show-WarfareOnboarding -Root $root -Parent $parent
    if(-not $result.completed -or @([Windows.Forms.Application]::OpenForms|Where-Object Name -eq firstPlay).Count){throw 'Completed setup reopened'}
    Record 'Completed setup does not prompt on every launch'
    $result=Run-Wizard $root {param($w);(Find-Control $w 'setupCancel').PerformClick()} -Reconfigure
    if($result.completed -or -not(Read-Settings $root).firstPlay.completed){throw 'Reconfigure cancel destroyed completed setup'}
    Record 'Reconfigure remains available and cancelling retains the previous setup'
    $root=New-Instance 'Keyboard from radio' $personal
    $profile=Join-Path $root 'config/vm-controller.properties'
    [IO.File]::WriteAllText($profile,"enabled=true`r`nkeyboardFlight=pro`r`n",[Text.UTF8Encoding]::new($false))
    $result=Run-Wizard $root {param($w)
        if((Find-Control $w 'setupPage0').Visible){(Find-Control $w 'inputEasy').Checked=$true;(Find-Control $w 'setupNext').PerformClick();return}
        if((Find-Control $w 'setupPage2').Visible -and (Find-Control $w 'setupNext').Enabled){(Find-Control $w 'setupNext').PerformClick()}
    }
    if(-not $result.completed -or $result.settings.firstPlay.inputMode -ne 'easy' -or -not(Test-Path -LiteralPath (Join-Path $root 'keyboard-applied.txt')) -or [IO.File]::ReadAllText($profile) -cne 'enabled=false'){throw 'Existing radio profile did not use the Keyboard bridge'}
    Record 'Switching an existing radio profile to keyboard applies the explicit Keyboard bridge'
    $root=New-Instance 'Keyboard cancelled profile' (@{firstPlay=@{schema=1;completed=$true;scope='client';inputMode='radio';device='old-device'};connectionMode='direct';connectionTarget='saved.example';serverPort=25565})
    $profile=Join-Path $root 'config/vm-controller.properties';[IO.File]::WriteAllText($profile,"enabled=true`r`nroll.axis=3`r`nunknown=личное`r`n",[Text.UTF8Encoding]::new($false));$before=[IO.File]::ReadAllBytes($profile)
    $result=Run-Wizard $root {param($w)
        if((Find-Control $w 'setupPage0').Visible){(Find-Control $w 'inputEasy').Checked=$true;(Find-Control $w 'setupNext').PerformClick();return}
        if((Find-Control $w 'setupPage2').Visible){(Find-Control $w 'setupCancel').PerformClick()}
    } -Reconfigure
    if($result.completed -or (Test-Path -LiteralPath (Join-Path $root 'keyboard-applied.txt')) -or [Convert]::ToBase64String([IO.File]::ReadAllBytes($profile)) -cne [Convert]::ToBase64String($before) -or -not (Read-Settings $root).firstPlay.completed){throw 'Keyboard cancel changed a calibrated profile'}
    Record 'Keyboard then Cancel preserves an old calibrated radio profile byte for byte'
    foreach($locale in @('ru','en')){
        $private=New-Instance ('Private '+$locale) @{nickname='Tester'} @{connectionMode='porthole';connectionTarget='PRIVATE9';serverPort=25565}
        $result=Run-Wizard $private {param($w)
            if((Find-Control $w 'setupPage0').Visible){(Find-Control $w 'setupNext').PerformClick();return}
            if((Find-Control $w 'setupPage2').Visible){if((Find-Control $w 'setupTarget').Text -ne 'PRIVATE9' -or (Find-Control $w 'setupTarget').Enabled){throw 'Friend default not preselected'}
                $bitmap=[Drawing.Bitmap]::new($w.Width,$w.Height);try{$w.DrawToBitmap($bitmap,[Drawing.Rectangle]::new(0,0,$w.Width,$w.Height));$bitmap.Save((Join-Path $testRoot ('server-'+$script:callbackLanguage+'.png')))}finally{$bitmap.Dispose()}
                (Find-Control $w 'setupNext').PerformClick()}
        } -Language $locale
        if(-not $result.completed -or $result.connection.connectionTarget -ne 'PRIVATE9'){throw 'Friend setup failed'}
    }
    Record 'Private friend default is preselected and both languages fit without overlap'
    $root=New-Instance 'No device' $personal
    $result=Run-Wizard $root {param($w)
        if($script:step -eq 0){Open-ControlChoice $w;(Find-Control $w 'inputGamepad').Checked=$true;(Find-Control $w 'setupNext').PerformClick();$script:step++;return}
        if($script:step -eq 1 -and (Find-Control $w 'setupPage1').Visible -and (Find-Control $w 'setupRescan').Enabled){
            if((Find-Control $w 'setupDevice').Items.Count -ne 0 -or (Find-Control $w 'setupNext').Enabled -or (Find-Control $w 'setupCalibrate').Enabled){throw 'Nonexistent device accepted'}
            if((Find-Control $w 'setupStatus').Text -notmatch 'не найдено'){throw 'Missing-device message absent'}
            (Find-Control $w 'setupBack').PerformClick();(Find-Control $w 'inputEasy').Checked=$true;(Find-Control $w 'setupNext').PerformClick();$script:step=2;return
        }
        if($script:step -eq 2 -and (Find-Control $w 'setupPage2').Visible){(Find-Control $w 'setupNext').PerformClick()}
    }
    if(-not $result.completed -or $result.settings.firstPlay.inputMode -ne 'easy'){throw 'Keyboard fallback failed'}
    Record 'No fake device is offered and keyboard fallback remains available'
    foreach($kind in @('radio','gamepad')){
        $root=New-Instance ('Actual '+$kind) $personal
        [IO.File]::WriteAllText((Join-Path $root 'fixture-devices.json'),(@(@{id='test|device|4';name='USB test controller';kind=$kind;axisCount=4},@{id='two';name='Two axis stick';kind=$kind;axisCount=2})|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText((Join-Path $root 'fixture-behavior.txt'),'invalid')
        $script:inputKind=$kind
        $result=Run-Wizard $root {param($w)
            $next=Find-Control $w 'setupNext';$calibrate=Find-Control $w 'setupCalibrate'
            if($script:step -eq 0){Open-ControlChoice $w;(Find-Control $w $(if($script:inputKind -eq 'radio'){'inputRadio'}else{'inputGamepad'})).Checked=$true;$next.PerformClick();$script:step++;return}
            if((Find-Control $w 'setupPage2').Visible){$next.PerformClick();return}
            if(-not $calibrate.Enabled){return}
            if($script:step -eq 1){
                if((Find-Control $w 'setupDevice').Items.Count -ne 1 -or (Find-Control $w 'setupDevice').Text -ne 'USB test controller' -or $next.Enabled){throw 'Detector result or uncalibrated gate failed'}
                $calibrate.PerformClick();$script:step++;return
            }
            if($script:step -eq 2){if($next.Enabled){throw 'Wrong calibrated device accepted'};[IO.File]::WriteAllText((Join-Path $script:callbackRoot 'fixture-behavior.txt'),'cancelled');$calibrate.PerformClick();$script:step++;return}
            if($script:step -eq 3){if($next.Enabled){throw 'Cancelled calibration accepted'};[IO.File]::WriteAllText((Join-Path $script:callbackRoot 'fixture-behavior.txt'),'saved');$calibrate.PerformClick();$script:step++;return}
            if($script:step -eq 4){if(-not $next.Enabled){throw 'Saved matching calibration not accepted'};$next.PerformClick();$script:step++}
        }
        if(-not $result.completed -or $result.settings.firstPlay.inputMode -ne $kind -or $result.settings.firstPlay.device -ne 'test|device|4'){throw 'Calibrated choice not retained'}
    }
    Record 'Radio and gamepad require matching successful calibration and reject wrong or cancelled results'
    $root=New-Instance 'Calibration transaction' @{firstPlay=@{schema=1;completed=$true;scope='client';inputMode='radio';device='old-device'};connectionMode='direct';connectionTarget='saved.example';serverPort=25565}
    $profile=Join-Path $root 'config/vm-controller.properties';[IO.File]::WriteAllText($profile,'old calibration and unknown settings');$before=[IO.File]::ReadAllBytes($profile)
    [IO.File]::WriteAllText((Join-Path $root 'fixture-devices.json'),'[{"id":"test|device|4","name":"USB test controller","kind":"radio","axisCount":4}]')
    [IO.File]::WriteAllText((Join-Path $root 'fixture-behavior.txt'),'saved')
    $result=Run-Wizard $root {param($w)
        if($script:step -eq 0){Open-ControlChoice $w;(Find-Control $w 'inputRadio').Checked=$true;(Find-Control $w 'setupNext').PerformClick();$script:step++;return}
        if($script:step -eq 1 -and (Find-Control $w 'setupCalibrate').Enabled){(Find-Control $w 'setupCalibrate').PerformClick();$script:step++;return}
        if($script:step -eq 2 -and (Find-Control $w 'setupNext').Enabled){(Find-Control $w 'setupNext').PerformClick();$script:step++;return}
        if($script:step -eq 3 -and (Find-Control $w 'setupPage2').Visible){(Find-Control $w 'setupCancel').PerformClick()}
    } -Reconfigure
    if($result.completed -or [Convert]::ToBase64String([IO.File]::ReadAllBytes($profile)) -cne [Convert]::ToBase64String($before) -or -not (Read-Settings $root).firstPlay.completed){throw 'Calibration cancellation did not restore the previous profile'}
    Record 'Calibration Save then connection Cancel restores the previous profile exactly'
    $root=New-Instance 'Owner' @{memoryMB=0;unknown='owner-retain'}
    $result=Run-Wizard $root {param($w);if((Find-Control $w 'setupPage0').Visible){(Find-Control $w 'setupNext').PerformClick()}} -Owner
    if(-not $result.completed -or $result.settings.firstPlay.scope -ne 'owner' -or $result.settings.connectionTarget -or $result.settings.unknown -ne 'owner-retain'){throw 'Owner wizard required remote server'}
    Record 'Owner uses the same controls setup and does not request a remote server'
    $root=New-Instance 'Lock' $personal
    $lock=[IO.File]::Open((Join-Path $root '.setup.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    try{
        $blocked=$false;try{[void](Show-WarfareOnboarding -Root $root -Parent $parent)}catch{$blocked=$_.Exception.Message -match 'уже открыта'};if(-not $blocked){throw 'Second setup not blocked'}
        $completed=Read-Settings $root;$completed|Add-Member NoteProperty firstPlay ([PSCustomObject]@{schema=1;completed=$true;scope='client';inputMode='easy'}) -Force;Save-WarfareSetupSettings $root $completed
        $blocked=$false;try{[void](Show-WarfareOnboarding -Root $root -Parent $parent)}catch{$blocked=$_.Exception.Message -match 'уже открыта'};if(-not $blocked){throw 'Saved setup bypassed another active wizard'}
    }finally{$lock.Dispose()}
    Record 'Concurrent setup is blocked before another wizard can write preferences'
    $root=New-Instance 'Cancelled scan' $personal
    $hung=@'
param([string]$ReportPath,[string]$CancelPath)
while(-not (Test-Path -LiteralPath $CancelPath)){Start-Sleep -Milliseconds 100}
[IO.File]::WriteAllText($ReportPath,'{"schema":1,"outcome":"cancelled"}')
'@
    [IO.File]::WriteAllText((Join-Path $root 'Configure-Controller.ps1'),$hung,[Text.UTF8Encoding]::new($true))
    $cancelStart=[DateTime]::UtcNow
    $result=Run-Wizard $root {param($w)
        if($script:step -eq 0){Open-ControlChoice $w;(Find-Control $w 'inputRadio').Checked=$true;(Find-Control $w 'setupNext').PerformClick();$script:step++;return}
        if($script:step -eq 1){if(-not (Find-Control $w 'setupCancel').Enabled){throw 'Cannot cancel a running scan'};(Find-Control $w 'setupCancel').PerformClick();$script:step++}
    }
    if($result.completed -or ([DateTime]::UtcNow-$cancelStart).TotalSeconds -gt 6){throw 'Scan cancellation did not finish promptly'}
    Record 'A running scan can be cancelled and does not strand the modal window'
    $root=New-Instance 'Bounded hung scan' $personal
    [IO.File]::WriteAllText((Join-Path $root 'Configure-Controller.ps1'),'param($ReportPath,$CancelPath);while($true){Start-Sleep -Milliseconds 100}',[Text.UTF8Encoding]::new($true))
    $timeoutStart=[DateTime]::UtcNow
    $result=Run-Wizard $root {param($w)
        if($script:step -eq 0){Open-ControlChoice $w;(Find-Control $w 'inputRadio').Checked=$true;(Find-Control $w 'setupNext').PerformClick();$script:step++}
    }
    $elapsed=([DateTime]::UtcNow-$timeoutStart).TotalSeconds
    if($result.completed -or $elapsed -lt 20 -or $elapsed -gt 25){throw 'Hung scan was not bounded'}
    $remaining=@(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'"|Where-Object {$_.CommandLine -like ('*'+$root+'*')})
    if($remaining.Count){throw 'Owned hung controller worker survived timeout'}
    Record 'A hung backend times out and only its owned worker is terminated'
    $report=@{status='PASS';groups=$script:cases.Count;cases=$script:cases;physicalDeviceTested=$false;actualBackendTested=$false;fixtureRoot=$testRoot}
    [IO.File]::WriteAllText((Join-Path $testRoot 'report.json'),($report|ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
    ('Report: '+(Join-Path $testRoot 'report.json'))
}finally{$parent.Dispose()}
