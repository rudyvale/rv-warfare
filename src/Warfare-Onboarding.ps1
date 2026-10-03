function Get-WarfareSetupText([string]$Language,[string]$Ru,[string]$En) {
    if ($Language -eq 'en') { return $En }; return $Ru
}
. (Join-Path $PSScriptRoot 'Warfare-ClientControls.ps1')
. (Join-Path $PSScriptRoot 'Warfare-ConnectionProfiles.ps1')
function Initialize-WarfareSetupUI {
    if(-not ('RvSetupDpi' -as [type])){
        Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class RvSetupDpi {
    [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr value);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
'@
    }
    try{[void][RvSetupDpi]::SetThreadDpiAwarenessContext([IntPtr](-2))}catch{[void][RvSetupDpi]::SetProcessDPIAware()}
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    if(-not ('RvSetupButton' -as [type])){
        Add-Type -ReferencedAssemblies System.Windows.Forms,System.Drawing -WarningAction SilentlyContinue @'
using System.Drawing;
using System.Windows.Forms;
public class RvSetupButton : Button {
    protected override void OnPaint(PaintEventArgs e) {
        if (Enabled) { base.OnPaint(e); return; }
        e.Graphics.Clear(Color.FromArgb(29,35,44));
        using (var pen = new Pen(Color.FromArgb(56,64,76))) {
            e.Graphics.DrawRectangle(pen,0,0,Width-1,Height-1);
        }
        TextRenderer.DrawText(e.Graphics,Text,Font,ClientRectangle,
            Color.FromArgb(145,156,172),TextFormatFlags.HorizontalCenter|TextFormatFlags.VerticalCenter);
    }
}
'@
    }
    [Windows.Forms.Application]::EnableVisualStyles()
}
function Save-WarfareSetupSettings([string]$Root,$Settings) {
    New-Item -ItemType Directory -Path $Root -Force | Out-Null
    $path=Join-Path $Root 'warfare-settings.json'
    $temp=$path+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
    try {
        [IO.File]::WriteAllText($temp,($Settings|ConvertTo-Json -Depth 32),[Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temp -Destination $path -Force
    } finally { if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Force} }
}
function Start-WarfareSetupTask([string]$Root,[string]$Action,[string]$ReportPath,[string]$Kind,[string]$DeviceId,[string]$Brand) {
    $path=Join-Path $Root 'Configure-Controller.ps1'
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw 'setup_bridge_missing'}
    $arguments=@('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',$path,'-InstallRoot',$Root,'-WizardAction',$Action,'-ReportPath',$ReportPath,'-CancelPath',($ReportPath+'.cancel'))
    if($Kind -in @('radio','gamepad')){$arguments+=@('-Kind',$Kind)}
    if($DeviceId){$arguments+=@('-DeviceId',$DeviceId)}
    if($Brand){$arguments+=@('-Brand',$Brand)}
    $quoted=@($arguments|ForEach-Object {'"'+[regex]::Replace([regex]::Replace($_,'(\\*)"','$1$1\"'),'(\\+)$','$1$1')+'"'}) -join ' '
    $shell=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $process=Start-Process -FilePath $shell -ArgumentList $quoted -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput ($ReportPath+'.log') -RedirectStandardError ($ReportPath+'.err') -PassThru
    $null=$process.Handle
    return $process
}
function Stop-WarfareSetupTask($Process,[string]$Root) {
    if(-not $Process -or $Process.HasExited){return}
    $current=Get-Process -Id $Process.Id -ErrorAction SilentlyContinue
    if(-not $current -or $current.StartTime.ToUniversalTime().Ticks -ne $Process.StartTime.ToUniversalTime().Ticks){throw 'setup_process_changed'}
    $javaPaths=@((Join-Path $Root 'runtime/bin/java.exe'),(Join-Path $env:LOCALAPPDATA 'Warfare-1.12.2/runtime/bin/java.exe'))
    $children=@(Get-CimInstance Win32_Process -Filter ('ParentProcessId='+$Process.Id) -ErrorAction Stop)
    foreach($child in $children){
        if($child.Name -ine 'java.exe' -or [string]$child.ExecutablePath -notin $javaPaths){continue}
        $owned=Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
        if($owned -and $owned.Path -in $javaPaths -and $owned.StartTime.ToUniversalTime() -ge $Process.StartTime.ToUniversalTime()){
            $owned.Kill();if(-not $owned.WaitForExit(1500)){throw 'setup_cleanup_failed'}
        }
    }
    $Process.Kill();if(-not $Process.WaitForExit(1500)){throw 'setup_cleanup_failed'}
}
function Show-WarfareOnboarding {
    param([string]$Root,[ValidateSet('ru','en')][string]$Language='ru',$Parent,[switch]$Reconfigure,[switch]$Owner)
    $Root=[IO.Path]::GetFullPath($Root)
    $settingsPath=Join-Path $Root 'warfare-settings.json'
    $settings=$null
    if(Test-Path -LiteralPath $settingsPath){
        try{$settings=Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8|ConvertFrom-Json}catch{throw (Get-WarfareSetupText $Language 'Не удалось прочитать настройки. Открой журнал.' 'Could not read settings. Open Log.')}
    }
    if(-not $settings){$settings=[PSCustomObject]@{}}
    $defaults=$null
    $defaultsPath=Join-Path $Root 'server-defaults.json'
    if(Test-Path -LiteralPath $defaultsPath){try{$defaults=Get-Content -LiteralPath $defaultsPath -Raw -Encoding UTF8|ConvertFrom-Json}catch{}}
    $connection=Get-WarfareConnection $settings $defaults
    $scope=if($Owner){'owner'}else{'client'}
    $saved=$settings.firstPlay
    if(-not $Reconfigure -and $saved -and $saved.schema -eq 1 -and $saved.completed -eq $true -and $saved.scope -eq $scope -and $saved.inputMode -in @('easy','radio','gamepad') -and ($Owner -or $connection.connectionTarget)){
        $check=$null
        try{$check=[IO.File]::Open((Join-Path $Root '.setup.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}
        catch{throw (Get-WarfareSetupText $Language 'Настройка уже открыта в другом окне.' 'Setup is already open in another window.')}
        finally{if($check){$check.Dispose()}}
        return [PSCustomObject]@{completed=$true;settings=$settings;connection=$connection}
    }
    Initialize-WarfareSetupUI
    $state=@{page=0;mode='easy';brand='';devices=@();verified=$null;process=$null;action='';report='';completed=$false;cancelRequested=$false;taskStarted=[DateTime]::MinValue;cancelStarted=[DateTime]::MinValue;profileTouched=$false;profileAfter=$null}
    $profilePath=Join-Path $Root 'config/vm-controller.properties'
    $profileBefore=if(Test-Path -LiteralPath $profilePath){[IO.File]::ReadAllBytes($profilePath)}else{$null}
    $draft=if($settings.firstPlayDraft){$settings.firstPlayDraft}else{$saved}
    if($draft -and $draft.inputMode -in @('easy','radio','gamepad')){$state.mode=$draft.inputMode}
    if(-not $Owner -and -not $draft -and (Test-WarfareKeyboardDefaultsReady $Root)){$state.page=2}
    $dialog=[Windows.Forms.Form]::new()
    $dialog.SuspendLayout()
    $dialog.Name='firstPlay';$dialog.Text='RV';$dialog.StartPosition='CenterParent';$dialog.ShowInTaskbar=$false
    $dialog.FormBorderStyle='FixedDialog';$dialog.MaximizeBox=$false;$dialog.MinimizeBox=$false
    $dialog.BackColor=[Drawing.Color]::FromArgb(21,25,32);$dialog.ForeColor=[Drawing.Color]::FromArgb(238,240,244)
    $dialog.Font=[Drawing.Font]::new('Segoe UI',10)
    $dialog.AutoScaleMode='Dpi';$dialog.AutoScaleDimensions=[Drawing.SizeF]::new(96,96)
    $dialog.ClientSize=[Drawing.Size]::new(620,560)
    $layout=[Windows.Forms.TableLayoutPanel]::new();$layout.Dock='Fill';$layout.ColumnCount=1;$layout.RowCount=3
    [void]$layout.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::Percent,100))
    [void]$layout.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::Absolute,66))
    [void]$layout.RowStyles.Add([Windows.Forms.RowStyle]::new([Windows.Forms.SizeType]::Absolute,56))
    $body=[Windows.Forms.Panel]::new();$body.Name='setupBody';$body.Dock='Fill';$body.AutoScroll=$true
    $errorLabel=[Windows.Forms.Label]::new();$errorLabel.Name='setupStatus';$errorLabel.Dock='Fill';$errorLabel.Padding=[Windows.Forms.Padding]::new(24,8,24,0)
    $errorLabel.ForeColor=[Drawing.Color]::FromArgb(213,231,127)
    $footer=[Windows.Forms.FlowLayoutPanel]::new();$footer.Dock='Fill';$footer.FlowDirection='RightToLeft';$footer.Padding=[Windows.Forms.Padding]::new(12,8,12,8)
    $next=[RvSetupButton]::new();$next.Name='setupNext';$next.Size=[Drawing.Size]::new(155,32)
    $back=[RvSetupButton]::new();$back.Name='setupBack';$back.Size=[Drawing.Size]::new(140,32);$back.Text=Get-WarfareSetupText $Language 'Назад' 'Back'
    $cancel=[RvSetupButton]::new();$cancel.Name='setupCancel';$cancel.Size=[Drawing.Size]::new(140,32);$cancel.Text=Get-WarfareSetupText $Language 'Отмена' 'Cancel'
    foreach($button in @($next,$back,$cancel)){$button.FlatStyle='Flat';$button.BackColor=[Drawing.Color]::FromArgb(32,38,48)}
    $next.BackColor=[Drawing.Color]::FromArgb(213,231,127);$next.ForeColor=[Drawing.Color]::FromArgb(26,32,20)
    $footer.Controls.AddRange(@($next,$back,$cancel));$layout.Controls.Add($body,0,0);$layout.Controls.Add($errorLabel,0,1);$layout.Controls.Add($footer,0,2);$dialog.Controls.Add($layout)
    $pages=@()
    foreach($i in 0..2){$page=[Windows.Forms.Panel]::new();$page.Name='setupPage'+$i;$page.SetBounds(0,0,584,430);$pages+=,$page;$body.Controls.Add($page)}
    function Add-SetupLabel($Page,[string]$Text,[int]$Y,[int]$Height,[int]$Size=10){
        $label=[Windows.Forms.Label]::new();$label.Text=$Text;$label.SetBounds(24,$Y,536,$Height);$label.Font=[Drawing.Font]::new('Segoe UI',$Size);$Page.Controls.Add($label);return $label
    }
    [void](Add-SetupLabel $pages[0] (Get-WarfareSetupText $Language 'Как будешь управлять?' 'How will you play?') 24 42 18)
    [void](Add-SetupLabel $pages[0] (Get-WarfareSetupText $Language 'Есть FPV-пульт или геймпад?' 'Do you have an FPV radio or a gamepad?') 78 40)
    $inputChoices=@()
    $choiceText=@((Get-WarfareSetupText $Language 'Мышь и клавиатура' 'Mouse and keyboard'),(Get-WarfareSetupText $Language 'FPV-пульт' 'FPV radio'),(Get-WarfareSetupText $Language 'Геймпад' 'Gamepad'))
    foreach($i in 0..2){$radio=[Windows.Forms.RadioButton]::new();$radio.Name=@('inputEasy','inputRadio','inputGamepad')[$i];$radio.Text=$choiceText[$i];$radio.SetBounds(24,(132+$i*50),536,34);$radio.Checked=@('easy','radio','gamepad')[$i] -eq $state.mode;$pages[0].Controls.Add($radio);$inputChoices+=,$radio}
    [void](Add-SetupLabel $pages[0] (Get-WarfareSetupText $Language 'Мышь — направление. WASD — движение. Пробел — вверх, Ctrl — вниз, Shift — выход из FPV.' 'Mouse: direction. WASD: movement. Space: up, Ctrl: down, Shift: leave FPV.') 302 92)
    $deviceHeading=Add-SetupLabel $pages[1] '' 24 42 18
    $deviceHint=Add-SetupLabel $pages[1] '' 78 56
    [void](Add-SetupLabel $pages[1] (Get-WarfareSetupText $Language 'Какой контроллер?' 'Which controller?') 144 26)
    $brandBox=[Windows.Forms.ComboBox]::new();$brandBox.Name='setupBrand';$brandBox.DropDownStyle='DropDownList';$brandBox.SetBounds(24,176,536,28);$pages[1].Controls.Add($brandBox)
    [void](Add-SetupLabel $pages[1] (Get-WarfareSetupText $Language 'Подключённое устройство' 'Connected device') 220 26)
    $deviceBox=[Windows.Forms.ComboBox]::new();$deviceBox.Name='setupDevice';$deviceBox.DropDownStyle='DropDownList';$deviceBox.SetBounds(24,252,360,28);$pages[1].Controls.Add($deviceBox)
    $rescan=[RvSetupButton]::new();$rescan.Name='setupRescan';$rescan.SetBounds(400,250,160,32);$rescan.Text=Get-WarfareSetupText $Language 'Обновить' 'Refresh';$pages[1].Controls.Add($rescan)
    $calibrate=[RvSetupButton]::new();$calibrate.Name='setupCalibrate';$calibrate.SetBounds(24,302,536,38);$calibrate.Text=Get-WarfareSetupText $Language 'Настроить оси и проверить стики' 'Map axes and check sticks';$pages[1].Controls.Add($calibrate)
    foreach($button in @($rescan,$calibrate)){$button.FlatStyle='Flat';$button.BackColor=[Drawing.Color]::FromArgb(32,38,48)}
    [void](Add-SetupLabel $pages[1] (Get-WarfareSetupText $Language 'Выбери устройство, проверь направления и пройди калибровку. F8 открывает эти настройки в игре.' 'Select your device, check directions and calibrate. F8 opens these settings in the game.') 358 60)
    [void](Add-SetupLabel $pages[2] (Get-WarfareSetupText $Language 'Выбери сервер' 'Choose a server') 24 48 18)
    $serverBox=[Windows.Forms.ComboBox]::new();$serverBox.Name='setupServer';$serverBox.DropDownStyle='DropDownList';$serverBox.SetBounds(24,94,536,28);$pages[2].Controls.Add($serverBox)
    $serverChoices=@()
    $defaultConnection=Get-WarfareConnection $null $defaults
    if($connection.connectionTarget){
        $isDefault=$connection.connectionTarget -eq $defaultConnection.connectionTarget -and $connection.connectionMode -eq $defaultConnection.connectionMode -and $connection.serverPort -eq $defaultConnection.serverPort
        $label=if($isDefault){Get-WarfareSetupText $Language 'Сервер хозяина' 'Host server'}else{Get-WarfareSetupText $Language 'Сохранённый сервер' 'Saved server'}
        $serverChoices+=,@{label=$label;connection=$connection}
    }
    if($defaultConnection.connectionTarget -and ($defaultConnection.connectionTarget -ne $connection.connectionTarget -or $defaultConnection.connectionMode -ne $connection.connectionMode -or $defaultConnection.serverPort -ne $connection.serverPort)){$serverChoices+=,@{label=(Get-WarfareSetupText $Language 'Сервер хозяина' 'Host server');connection=$defaultConnection}}
    $serverChoices+=,@{label=(Get-WarfareSetupText $Language 'Ввести код или адрес' 'Enter a code or address');connection=$null}
    foreach($choice in $serverChoices){[void]$serverBox.Items.Add($choice.label)}
    $serverBox.SelectedIndex=0
    [void](Add-SetupLabel $pages[2] (Get-WarfareSetupText $Language 'Способ подключения' 'Connection type') 144 26)
    $modeBox=[Windows.Forms.ComboBox]::new();$modeBox.Name='setupConnectionMode';$modeBox.DropDownStyle='DropDownList';$modeBox.SetBounds(24,176,536,28)
    [void]$modeBox.Items.AddRange(@('Porthole / Steam',(Get-WarfareSetupText $Language 'Прямой адрес' 'Direct address')));$pages[2].Controls.Add($modeBox)
    $targetLabel=Add-SetupLabel $pages[2] (Get-WarfareSetupText $Language 'Код подключения или адрес' 'Connection code or address') 220 26;$targetLabel.Width=360
    $portLabel=Add-SetupLabel $pages[2] (Get-WarfareSetupText $Language 'Порт' 'Port') 220 26;$portLabel.SetBounds(400,220,160,26)
    $targetInput=[Windows.Forms.TextBox]::new();$targetInput.Name='setupTarget';$targetInput.MaxLength=300;$targetInput.SetBounds(24,252,360,28);$pages[2].Controls.Add($targetInput)
    $portInput=[Windows.Forms.NumericUpDown]::new();$portInput.Name='setupPort';$portInput.Minimum=1;$portInput.Maximum=65535;$portInput.SetBounds(400,252,160,28);$pages[2].Controls.Add($portInput)
    $importInvite=[RvSetupButton]::new();$importInvite.Name='setupImportInvite';$importInvite.SetBounds(24,298,536,36);$importInvite.Text=Get-WarfareSetupText $Language 'Открыть приглашение' 'Open invitation';$pages[2].Controls.Add($importInvite)
    $inviteHint=Add-SetupLabel $pages[2] (Get-WarfareSetupText $Language 'Выбери файл .rvinvite от хозяина или введи код подключения.' 'Open the host .rvinvite file or enter a connection code.') 350 64
    $importInvite.Add_Click({
        $picker=[Windows.Forms.OpenFileDialog]::new();$picker.Filter='RV invitation|*.rvinvite'
        try{
            if($picker.ShowDialog($dialog) -ne 'OK'){return}
            $invite=ConvertFrom-WarfareInvite -Path $picker.FileName
            $serverBox.SelectedIndex=$serverChoices.Count-1;$modeBox.SelectedIndex=0;$targetInput.Text=$invite.connection.connectionTarget;$portInput.Value=$invite.connection.serverPort
            $inviteHint.Text=$invite.label+' · RV '+$invite.version
        }catch{$errorLabel.Text=Get-WarfareSetupText $Language 'Приглашение повреждено или не подходит для RV.' 'This invitation is damaged or incompatible with RV.'}finally{$picker.Dispose()}
    })
    $updateServerFields={
        $selected=$serverChoices[$serverBox.SelectedIndex].connection
        $manual=$null -eq $selected
        if($manual){$selected=$connection}
        $modeBox.SelectedIndex=if($selected.connectionMode -eq 'direct'){1}else{0}
        $targetInput.Text=$selected.connectionTarget;$portInput.Value=[Math]::Max(1,[Math]::Min(65535,[int]$selected.serverPort))
        foreach($control in @($modeBox,$targetInput,$portInput)){$control.Enabled=$manual}
    }
    $serverBox.Add_SelectedIndexChanged($updateServerFields);& $updateServerFields
    $updateButtons={
        $working=$null -ne $state.process
        $back.Enabled=-not $working -and $state.page -gt 0
        $cancel.Enabled=-not $state.cancelRequested
        $next.Enabled=-not $working -and ($state.page -ne 1 -or $null -ne $state.verified)
        $next.Text=if($state.page -eq 2 -or ($Owner -and ($state.page -eq 1 -or ($state.page -eq 0 -and $inputChoices[0].Checked)))){Get-WarfareSetupText $Language 'Готово' 'Done'}else{Get-WarfareSetupText $Language 'Далее' 'Next'}
        foreach($control in @($brandBox,$deviceBox,$rescan)){$control.Enabled=-not $working}
        $calibrate.Enabled=-not $working -and $deviceBox.SelectedIndex -ge 0
    }
    $showPage={
        foreach($i in 0..2){$pages[$i].Visible=$i -eq $state.page}
        $body.AutoScrollPosition=[Drawing.Point]::new(0,0)
        $errorLabel.Text='';& $updateButtons
    }
    $beginTask={param([string]$Action)
        try {
            if($state.process){return}
            $logRoot=Join-Path $Root '.launcher';New-Item -ItemType Directory -Path $logRoot -Force|Out-Null
            $state.report=Join-Path $logRoot ('setup-'+[Guid]::NewGuid().ToString('N')+'.json')
            $deviceId=if($deviceBox.SelectedIndex -ge 0){[string]$state.devices[$deviceBox.SelectedIndex].id}else{''}
            $state.action=$Action
            $state.process=Start-WarfareSetupTask $Root $Action $state.report $state.mode $deviceId ([string]$brandBox.SelectedItem)
            $state.taskStarted=[DateTime]::UtcNow
            $errorLabel.Text=if($Action -eq 'Configure'){Get-WarfareSetupText $Language 'Заверши настройку в окне контроллера и нажми «Сохранить».' 'Finish controller setup in its window and click Save.'}else{Get-WarfareSetupText $Language 'Проверка управления…' 'Checking controls…'}
            & $updateButtons
        } catch {$errorLabel.Text=Get-WarfareSetupText $Language 'Настройка недоступна. Установи актуальное обновление RV.' 'Control setup is unavailable. Install the current RV update.';& $updateButtons}
    }
    $completeSetup={
        $chosen=if($Owner){$connection}else{ConvertTo-WarfareConnection $(if($modeBox.SelectedIndex -eq 1){'direct'}else{'porthole'}) $targetInput.Text $portInput.Value.ToString()}
        $data=[PSCustomObject]@{schema=1;completed=$true;scope=$scope;inputMode=$state.mode;brand=[string]$brandBox.SelectedItem;device='';deviceName=''}
        if($state.mode -ne 'easy'){$data.device=[string]$state.verified.profile.device;$data.deviceName=[string]$state.devices[$deviceBox.SelectedIndex].name}
        $newSettings=$settings|ConvertTo-Json -Depth 32|ConvertFrom-Json
        $newSettings=Set-WarfareConnection $newSettings $chosen
        $newSettings|Add-Member NoteProperty firstPlay $data -Force
        $newSettings.PSObject.Properties.Remove('firstPlayDraft')
        Save-WarfareSetupSettings $Root $newSettings
        $state.settings=$newSettings;$state.connection=$chosen;$state.completed=$true;$dialog.DialogResult='OK'
    }
    $next.Add_Click({try{
        if($state.page -eq 0){
            $state.mode=if($inputChoices[1].Checked){'radio'}elseif($inputChoices[2].Checked){'gamepad'}else{'easy'}
            if($state.mode -eq 'easy'){if($Owner){if(Test-WarfareKeyboardDefaultsReady $Root){& $completeSetup}else{& $beginTask 'Keyboard'}}else{$state.page=2;& $showPage};return}
            $state.page=1;$state.verified=$null;$deviceBox.Items.Clear();$state.devices=@()
            $brandBox.Items.Clear()
            if($state.mode -eq 'radio'){
                $deviceHeading.Text=Get-WarfareSetupText $Language 'Настройка FPV-пульта' 'FPV radio setup'
                $deviceHint.Text=Get-WarfareSetupText $Language 'Подключи пульт по USB и выбери на нём режим Joystick.' 'Connect the radio by USB and select Joystick mode on it.'
                [void]$brandBox.Items.AddRange(@('RadioMaster','Jumper','FrSky',(Get-WarfareSetupText $Language 'Другой пульт' 'Other radio')))
            }else{
                $deviceHeading.Text=Get-WarfareSetupText $Language 'Настройка геймпада' 'Gamepad setup'
                $deviceHint.Text=Get-WarfareSetupText $Language 'Подключи геймпад по USB или Bluetooth.' 'Connect the gamepad by USB or Bluetooth.'
                [void]$brandBox.Items.AddRange(@('PlayStation','Xbox',(Get-WarfareSetupText $Language 'Другой геймпад' 'Other gamepad')))
            }
            $brandBox.SelectedIndex=$brandBox.Items.Count-1
            if($draft -and $brandBox.Items.Contains([string]$draft.brand)){$brandBox.SelectedItem=[string]$draft.brand}
            & $showPage;& $beginTask 'Probe'
        }elseif($state.page -eq 1){if($Owner){& $completeSetup}else{$state.page=2;& $showPage}}
        elseif($state.mode -eq 'easy'){
            [void](ConvertTo-WarfareConnection $(if($modeBox.SelectedIndex -eq 1){'direct'}else{'porthole'}) $targetInput.Text $portInput.Value.ToString())
            if(Test-WarfareKeyboardDefaultsReady $Root){& $completeSetup}else{& $beginTask 'Keyboard'}
        }else{& $completeSetup}
    }catch{$errorLabel.Text=Get-WarfareConnectionError $_.Exception.Message $Language}})
    foreach($radio in $inputChoices){$radio.Add_CheckedChanged({& $updateButtons})}
    $deviceBox.Add_SelectedIndexChanged({$state.verified=$null;& $updateButtons})
    $rescan.Add_Click({$state.verified=$null;& $beginTask 'Probe'})
    $calibrate.Add_Click({$state.verified=$null;& $beginTask 'Configure'})
    $back.Add_Click({$state.page=0;& $showPage})
    $requestCancel={
        $state.cancelRequested=$true
        if($state.process){[IO.File]::WriteAllText(($state.report+'.cancel'),'cancel');$state.cancelStarted=[DateTime]::UtcNow;$errorLabel.Text=Get-WarfareSetupText $Language 'Отмена настройки…' 'Cancelling setup…';& $updateButtons}
        else{$dialog.DialogResult='Cancel'}
    }
    $cancel.Add_Click($requestCancel)
    $poll=[Windows.Forms.Timer]::new();$poll.Interval=100
    $poll.Add_Tick({
        if(-not $state.process){return}
        if(-not $state.process.HasExited){
            if(-not $state.cancelRequested -and $state.action -in @('Probe','Keyboard') -and ([DateTime]::UtcNow-$state.taskStarted).TotalSeconds -ge 20){& $requestCancel}
            if($state.cancelRequested -and ([DateTime]::UtcNow-$state.cancelStarted).TotalSeconds -ge 3){
                try{Stop-WarfareSetupTask $state.process $Root}catch{$errorLabel.Text=Get-WarfareSetupText $Language 'Не удалось закрыть настройку. Закрой окно контроллера.' 'Could not close setup. Close the controller window.'}
            }
            return
        }
        try {
            $state.process.WaitForExit();$exit=$state.process.ExitCode;$state.process.Dispose();$state.process=$null
            if($state.action -in @('Keyboard','Configure') -and (Test-Path -LiteralPath $profilePath)){$state.profileTouched=$true;$state.profileAfter=[IO.File]::ReadAllBytes($profilePath)}
            if($state.cancelRequested){$dialog.DialogResult='Cancel';return}
            if($exit -ne 0 -or -not(Test-Path -LiteralPath $state.report)){throw 'setup_task_failed'}
            $report=Get-Content -LiteralPath $state.report -Raw -Encoding UTF8|ConvertFrom-Json
            if($report.schema -ne 1){throw 'setup_task_failed'}
            if($state.action -eq 'Probe'){
                $state.devices=@($report.devices|Where-Object {$_.id -and $_.name -and $_.axisCount -ge 4})
                $deviceBox.Items.Clear();foreach($device in $state.devices){[void]$deviceBox.Items.Add([string]$device.name)}
                if($state.devices.Count){$deviceBox.SelectedIndex=0;$errorLabel.Text=Get-WarfareSetupText $Language 'Выбери своё устройство и проверь оси.' 'Select your device and check its axes.'}
                else{$errorLabel.Text=Get-WarfareSetupText $Language 'Устройство не найдено. Подключи его и нажми «Обновить» или выбери клавиатуру.' 'No device found. Connect it and click Refresh, or choose the keyboard.'}
            }elseif($state.action -eq 'Keyboard'){
                if($report.outcome -ne 'saved' -or $report.inputMode -ne 'easy' -or $report.profile.enabled -ne $false){throw 'setup_task_failed'}
                & $completeSetup
            }elseif($report.outcome -eq 'cancelled'){$errorLabel.Text=Get-WarfareSetupText $Language 'Настройка отменена. Можно повторить или выбрать клавиатуру.' 'Setup cancelled. Try again or choose the keyboard.'}
            elseif($report.outcome -eq 'saved' -and $report.profile.enabled -eq $true -and $report.profile.calibrated -eq $true -and $report.profile.connected -eq $true -and $report.profile.kind -eq $state.mode -and $report.profile.device -ceq $state.devices[$deviceBox.SelectedIndex].id){
                $state.verified=$report;$errorLabel.Text=Get-WarfareSetupText $Language 'Оси проверены. Можно продолжить.' 'Axes checked. You can continue.'
            }else{throw 'setup_task_failed'}
        } catch {$errorLabel.Text=Get-WarfareSetupText $Language 'Настройка не завершена. Проверь устройство и повтори попытку.' 'Setup did not complete. Check the device and try again.'}
        & $updateButtons
    })
    $dialog.Add_FormClosing({if($state.process){$_.Cancel=$true;if(-not $state.cancelRequested){& $requestCancel}}})
    & $showPage
    $dialog.AutoScaleDimensions=[Drawing.SizeF]::new(96,96)
    $dialog.ResumeLayout($true)
    $scale=$dialog.CurrentAutoScaleDimensions.Width/96
    $area=[Windows.Forms.Screen]::FromControl($(if($Parent){$Parent}else{$dialog})).WorkingArea
    $dialog.ClientSize=[Drawing.Size]::new([int][Math]::Min(620*$scale,$area.Width-40),[int][Math]::Min(560*$scale,$area.Height-80))
    $lock=$null
    $lockPath=Join-Path $Root '.setup.lock'
    try{$lock=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}
    catch{$poll.Dispose();$dialog.Dispose();throw (Get-WarfareSetupText $Language 'Настройка уже открыта в другом окне.' 'Setup is already open in another window.')}
    $poll.Start()
    try {
        if($Parent){[void]$dialog.ShowDialog($Parent)}else{[void]$dialog.ShowDialog()}
        if(-not $state.completed){
            if($state.profileTouched){
                $current=if(Test-Path -LiteralPath $profilePath){[IO.File]::ReadAllBytes($profilePath)}else{$null}
                $same=$null -ne $current -and $null -ne $state.profileAfter -and [Convert]::ToBase64String($current) -ceq [Convert]::ToBase64String($state.profileAfter)
                if($same){
                    if($null -ne $profileBefore){$temp=$profilePath+'.'+[Guid]::NewGuid().ToString('N')+'.tmp';[IO.File]::WriteAllBytes($temp,$profileBefore);Move-Item -LiteralPath $temp -Destination $profilePath -Force}
                    else{Remove-Item -LiteralPath $profilePath -Force}
                }elseif($settings.firstPlay){$settings.firstPlay.completed=$false}
            }
            $mode=if($inputChoices[1].Checked){'radio'}elseif($inputChoices[2].Checked){'gamepad'}else{'easy'}
            $settings|Add-Member NoteProperty firstPlayDraft ([PSCustomObject]@{inputMode=$mode;brand=[string]$brandBox.SelectedItem}) -Force
            Save-WarfareSetupSettings $Root $settings
            return [PSCustomObject]@{completed=$false;settings=$settings;connection=$connection}
        }
        return [PSCustomObject]@{completed=$true;settings=$state.settings;connection=$state.connection}
    } finally {$poll.Stop();$poll.Dispose();$dialog.Dispose();if($lock){$lock.Dispose();Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue}}
}
