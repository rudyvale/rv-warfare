$env:VM_SKIP_UPDATE_CHECK='1'
$ErrorActionPreference='Stop'
$workspace=Split-Path -Parent $PSScriptRoot
$InstallRoot=Join-Path $PSScriptRoot 'GUI test кириллица'
$PackageRoot=Join-Path $PSScriptRoot 'Package test кириллица'
New-Item -ItemType Directory -Path $InstallRoot,$PackageRoot -Force | Out-Null
foreach ($path in @((Join-Path $InstallRoot 'release.json'),(Join-Path $PackageRoot 'release.json'),(Join-Path $InstallRoot '.updates\status.json'))) { if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force } }
Set-Content -LiteralPath (Join-Path $PackageRoot 'payload.zip') -Value 'fixture' -Encoding ASCII
Set-Content -LiteralPath (Join-Path $PackageRoot 'package-manifest.json') -Value '{"fixture":1}' -Encoding ASCII
$routingSource=[IO.File]::ReadAllText((Join-Path $workspace 'src\Warfare-Launcher.ps1'))
$routingStart=$routingSource.IndexOf('if (-not $InstallRoot)')
$routingEnd=$routingSource.IndexOf('if (-not $PackageRoot')
$routingCode=$routingSource.Substring($routingStart,$routingEnd-$routingStart)
$chosenRoot=$InstallRoot
$InstallRoot=$PackageRoot
Invoke-Expression $routingCode
if($InstallRoot -ne (Join-Path $env:LOCALAPPDATA 'Warfare-1.12.2')){throw 'Package used as game directory'}
$InstallRoot=$chosenRoot
'package Play routes to installed game: PASS'
$fakePlay=@'
param([switch]$Check,[switch]$Prepare,[string]$StatusFile)
if($Prepare){Set-Content -LiteralPath (Join-Path $PSScriptRoot 'prepared.txt') -Value 'ready'}
$state=if($Check){'ready'}else{'running'}
[IO.File]::WriteAllText($StatusFile,(@{state=$state;message='Test game status'}|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
exit 0
'@
Set-Content -LiteralPath (Join-Path $PackageRoot 'Play-Warfare.ps1') -Value $fakePlay -Encoding UTF8
$fakeInstall=@'
param([string]$Language,[string]$Nickname,[string]$InstallRoot,[switch]$NoLaunch,[switch]$NoSteam)
if(-not $NoLaunch -or -not $NoSteam){throw 'Missing GUI flags'}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'package-manifest.json') -Destination (Join-Path $InstallRoot 'installed-manifest.json') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Play-Warfare.ps1') -Destination $InstallRoot -Force
Start-Sleep -Milliseconds 250
exit 0
'@
Set-Content -LiteralPath (Join-Path $PackageRoot 'Install-Warfare.ps1') -Value $fakeInstall -Encoding UTF8
$source=[IO.File]::ReadAllText((Join-Path $workspace 'src\Warfare-Launcher.ps1'))
$source=$source.Substring($source.IndexOf('$ErrorActionPreference'))
$source=$source.Replace(". (Join-Path `$PSScriptRoot 'Warfare-Connection.ps1')", ". '"+(Join-Path $workspace 'src\Warfare-Connection.ps1')+"'")
$source=$source.Replace('$PSScriptRoot',("'"+(Join-Path $workspace 'src')+"'"))
$source=$source.Replace('try { [void]$form.ShowDialog() } finally { $timer.Stop(); $timer.Dispose(); $form.Dispose() }','')
$source=$source.Replace('$dialog.StartPosition = ''CenterParent''','$dialog.StartPosition = ''CenterParent''; $dialog.ShowInTaskbar=$false; $dialog.Opacity=0')
$PreviewPath=''
$Language='ru'
Invoke-Expression $source
$tick=$timer.GetType().GetMethod('OnTick',[Reflection.BindingFlags]'Instance,NonPublic')
function Drain {
    $deadline=[DateTime]::UtcNow.AddSeconds(20)
    while($script:process -and [DateTime]::UtcNow -lt $deadline){Start-Sleep -Milliseconds 100; $tick.Invoke($timer,@([EventArgs]::Empty))|Out-Null}
    if($script:process){throw 'Worker did not complete'}
}
function Click($Control) { $Control.GetType().GetMethod('OnClick',[Reflection.BindingFlags]'Instance,NonPublic').Invoke($Control,@([EventArgs]::Empty)) | Out-Null }
function Check-Bounds {
    $controls = @($form.Controls)
    foreach($control in $controls){if($control.Left -lt 0 -or $control.Top -lt 0 -or $control.Right -gt $form.ClientSize.Width -or $control.Bottom -gt $form.ClientSize.Height){throw ('Control outside window: '+$control.Text)}}
    for($i=0;$i -lt $controls.Count;$i++){for($j=$i+1;$j -lt $controls.Count;$j++){if($controls[$i].Bounds.IntersectsWith($controls[$j].Bounds)){throw ('Overlapping controls: '+$controls[$i].Text+' / '+$controls[$j].Text)}}}
}
try {
    if($form.Text -ne 'RV' -or $title.Text -ne 'RV'){throw 'Wrong branding'}
    foreach($locale in @('ru','en')){
        $script:language=$locale; Refresh-Text
        foreach($size in @(@(740,420),@(820,500),@(960,540),@(820,640),@(960,680),@(1280,720),@(1920,1080))){
            $form.ClientSize=[Drawing.Size]::new([int]($size[0]*$formScale),[int]($size[1]*$formScale)); Update-Layout; Check-Bounds
        }
    }
    $script:language='ru'; Refresh-Text
    'RV branding and ru/en responsive bounds without overlap: PASS'
    $nickname.Text='User_123'
    Click $install
    if(-not $script:busy -or $primary.Enabled){throw 'Install did not disable duplicate action'}
    Drain
    if(-not $script:ready -or $primary.Text -cne 'ИГРАТЬ' -or -not $primary.Enabled){throw ('Install/check state failed: ' + $status.Text)}
    if(-not (Test-Path -LiteralPath (Join-Path $InstallRoot 'prepared.txt'))){throw 'Connection preparation skipped'}
    'install -> prepare -> check -> play: PASS'
    $saved=Get-Content -LiteralPath $script:settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if($saved.nickname -ne 'User_123'){throw 'Nickname not saved'}
    $script:connection=ConvertTo-WarfareConnection 'direct' 'new-server.example:25570' '25565'; Save-Settings
    $nickname.Text='x'; $rejected=$false
    try{Save-Settings}catch{$rejected=$true}
    if(-not $rejected){throw 'Invalid nickname accepted'}
    $nickname.Text='User_123'; Save-Settings
    $saved=Get-Content -LiteralPath $script:settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if($saved.connectionTarget -ne 'new-server.example' -or $saved.serverPort -ne 25570 -or $saved.connectionMode -ne 'direct'){throw 'Connection lost'}
    'settings preservation and invalid nickname: PASS'
    $script:editTicks=0
    $script:dialogTarget='changed.example:25600'
    $editTimer=[Windows.Forms.Timer]::new();$editTimer.Interval=100
    $editTimer.Add_Tick({
        $script:editTicks++
        $window=@([Windows.Forms.Application]::OpenForms | Where-Object {$_.Text -eq 'Настройки'}) | Select-Object -First 1
        if($window){
            foreach($control in $window.Controls){if($control.Right -gt $window.ClientSize.Width -or $control.Bottom -gt $window.ClientSize.Height){throw 'Settings control outside window'}}
            $combo=@($window.Controls|Where-Object {$_ -is [Windows.Forms.ComboBox]})[0]
            $field=@($window.Controls|Where-Object {$_ -is [Windows.Forms.TextBox]})[0]
            $button=@($window.Controls|Where-Object {$_ -is [Windows.Forms.Button]})[0]
            $checkbox=@($window.Controls|Where-Object {$_ -is [Windows.Forms.CheckBox]})[0]
            $checkbox.Checked=$false
            $combo.SelectedIndex=1;$field.Text=$script:dialogTarget;$button.PerformClick()
            if($script:editTicks -gt 15){$window.Close()}
        }
    })
    $editTimer.Start()
    try{Click $changeServer}finally{$editTimer.Stop()}
    $saved=Get-Content -LiteralPath $script:settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if($saved.connectionTarget -ne 'changed.example' -or $saved.serverPort -ne 25600){throw 'Connection dialog did not persist endpoint'}
    if(Get-VmAutoCheck $InstallRoot){throw 'Settings did not disable automatic update checks'}
    'settings dialog persists endpoint, port and automatic update preference: PASS'
    $script:dialogTarget=''; $script:editTicks=0; $editTimer.Start()
    try{Click $changeServer}finally{$editTimer.Stop();$editTimer.Dispose()}
    if($script:connection.connectionTarget -or (Get-VmAutoCheck $InstallRoot)){throw 'Cannot save update preference without a server'}
    $script:connection=ConvertTo-WarfareConnection 'direct' 'changed.example:25600' '25565'; Save-Settings
    'update preference can be saved before choosing a server: PASS'
    Click $primary
    if($script:mode -ne 'play'){throw 'Play button does not start play'}
    Drain
    if($status.Text -ne 'Test game status' -or -not $primary.Enabled){throw 'Play state failed'}
    'asynchronous play: PASS'
    Set-Content -LiteralPath (Join-Path $PackageRoot 'package-manifest.json') -Value '{"fixture":2}' -Encoding ASCII
    Click $repair
    if($script:mode -ne 'check'){throw 'File check started another action'}
    Drain
    if(-not $script:needsUpdate -or $primary.Text -cne 'ИГРАТЬ' -or -not $primary.Enabled -or -not $updateLabel.Text){throw 'Local update blocked Play or was not detected'}
    Click $primary
    if($script:mode -ne 'play'){throw 'Play turned into an update button'}
    Drain
    'file check and Play keep their purpose when an update exists: PASS'
    Write-VmJson (Join-Path $PackageRoot 'release.json') @{version='1.0.0'}
    Write-VmJson (Join-Path $InstallRoot 'release.json') @{version='1.1.0'}
    Check-Install; Drain
    if($script:needsUpdate -or $primary.Text -cne 'ИГРАТЬ'){throw 'Older local package offered a downgrade'}
    $blocked=$false; try { Start-Install } catch { $blocked=$true }
    if(-not $blocked -or $script:process){throw 'Older local package started installation'}
    'reopening old package keeps Play and prevents downgrade: PASS'
    New-Item -ItemType Directory -Path (Join-Path $InstallRoot '.updates') -Force | Out-Null
    Write-VmJson (Join-Path $InstallRoot '.updates\status.json') @{state='available';version='1.2.0'}
    Read-UpdateStatus
    if(-not $script:remoteRelease -or $primary.Text -cne 'ИГРАТЬ' -or -not $primary.Enabled -or -not $updateLabel.Text){throw 'Remote update blocked Play or was not shown'}
    Write-VmJson (Join-Path $InstallRoot '.updates\status.json') @{state='current';version='1.1.0'}
    Read-UpdateStatus
    if($script:remoteRelease -or $script:needsUpdate -or $updateLabel.Text){throw 'Current release offered as update'}
    $originalWorker=(Get-Item Function:Start-Worker).ScriptBlock
    function Start-Worker([string]$Mode,[string]$Script,[string[]]$Arguments){$script:capture=@{mode=$Mode;path=$Script;arguments=$Arguments}}
    try {
        Click $updateAction
        if($script:capture.mode -ne 'download' -or $script:capture.arguments -notcontains '-Download' -or (Get-VmAutoCheck $InstallRoot)){throw 'Manual update ignored its button or disabled preference'}
        Set-Content -LiteralPath (Join-Path $InstallRoot 'Configure-Controller.ps1') -Value 'param([string]$InstallRoot); exit 0' -Encoding UTF8
        Start-Controller
        if($script:capture.mode -ne 'controller' -or $script:capture.arguments[-1] -ne $InstallRoot -or $script:capture.path -ne (Join-Path $InstallRoot 'Configure-Controller.ps1')){throw 'Controller configuration used wrong instance'}
    } finally { Set-Item Function:Start-Worker $originalWorker }
    'manual update remains available with automatic checks disabled: PASS'
    Start-Controller; Drain
    if($status.Text -ne 'Настройка контроллера открыта.' -or -not $primary.Enabled){throw 'Controller configuration blocked the launcher'}
    'controller configuration uses installed instance and returns to ready: PASS'
    $fakeUpdate=Join-Path $PackageRoot 'fake-update.ps1'
    Set-Content -LiteralPath $fakeUpdate -Value 'exit 0' -Encoding UTF8
    Start-Worker 'download' $fakeUpdate @(); Drain
    if($status.Text -ne 'Обновлений нет.' -or -not $primary.Enabled -or -not $script:ready){throw 'Up-to-date result changed ready state'}
    'manual check with no updates keeps game ready: PASS'
    Remove-Item -LiteralPath (Join-Path $PackageRoot 'release.json'),(Join-Path $InstallRoot 'release.json')
    'background release state reaches the update button: PASS'
    $languageBox.SelectedIndex=1
    if($primary.Text -cne 'PLAY' -or $repair.Text -ne 'Check files' -or $updateAction.Text -ne 'Update'){throw 'Language selector did not refresh controls'}
    $languageBox.SelectedIndex=0
    $originalStartProcess=(Get-Command Start-Process -CommandType Cmdlet)
    function Start-Process { param([string]$FilePath,[string[]]$ArgumentList); $script:opened=$FilePath }
    try {
        Click $advanced
        if($script:opened -ne 'explorer.exe'){throw 'Folder button did not open Explorer'}
        Set-Content -LiteralPath (Join-Path $InstallRoot 'client-console.log') -Value 'fixture'
        Click $logs
        if($script:opened -ne 'notepad.exe'){throw 'Log button did not open Notepad'}
        Click $steam
        if($script:opened -notin @('steam://open/main','https://store.steampowered.com/about/')){throw 'Steam button started another action'}
    } finally { Remove-Item Function:Start-Process }
    'language, folder, log and Steam controls: PASS'
    $script:needsUpdate=$false
    Set-Content -LiteralPath (Join-Path $InstallRoot 'Play-Warfare.ps1') -Value "param([switch]`$Prepare,[string]`$StatusFile); Write-Error 'Download pending'; exit 1" -Encoding UTF8
    Start-Worker 'prepare' (Join-Path $InstallRoot 'Play-Warfare.ps1') @('-Prepare','-StatusFile',$script:statusPath); Drain
    if(-not $script:ready -or $primary.Text -cne 'ИГРАТЬ' -or $status.Text -notmatch 'Download pending'){throw 'Preparation failure cannot be retried'}
    'unfinished Steam download can be retried through Play: PASS'
    Set-Content -LiteralPath (Join-Path $PackageRoot 'Install-Warfare.ps1') -Value "Write-Error 'Interrupted download'; exit 1" -Encoding UTF8
    Start-Install; Drain
    if($script:ready -or $script:busy -or $primary.Enabled -or -not $install.Enabled){throw 'Failed install exposed ready state'}
    'failure does not report success: PASS'
    '16 GUI integration tests passed'
} finally { $timer.Dispose(); $form.Dispose() }
