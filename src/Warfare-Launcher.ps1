param([string]$InstallRoot, [string]$PackageRoot, [string]$PreviewPath, [ValidateSet('ru','en')][string]$Language)
$ErrorActionPreference = 'Stop'
if (-not ('VmDpi' -as [type])) {
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class VmDpi {
    [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr value);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
'@
}
try { [void][VmDpi]::SetThreadDpiAwarenessContext([IntPtr](-2)) } catch { [void][VmDpi]::SetProcessDPIAware() }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
if (-not ('VmButton' -as [type])) {
    Add-Type -ReferencedAssemblies System.Windows.Forms,System.Drawing -WarningAction SilentlyContinue @'
using System.Drawing;
using System.Windows.Forms;
public class VmButton : Button {
    protected override void OnPaint(PaintEventArgs e) {
        if (Enabled) { base.OnPaint(e); return; }
        e.Graphics.Clear(Color.FromArgb(29,35,44));
        using (var pen = new Pen(Color.FromArgb(56,64,76))) {
            e.Graphics.DrawRectangle(pen, 0, 0, Width - 1, Height - 1);
        }
        TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle,
            Color.FromArgb(145,156,172), TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
    }
}
'@
}
. (Join-Path $PSScriptRoot 'Warfare-Connection.ps1')
. (Join-Path $PSScriptRoot 'Warfare-Performance.ps1')
. (Join-Path $PSScriptRoot 'Warfare-Onboarding.ps1')
. (Join-Path $PSScriptRoot 'Warfare-Updates.ps1')
[Windows.Forms.Application]::EnableVisualStyles()
if (-not $InstallRoot) { $InstallRoot = Join-Path $env:LOCALAPPDATA 'Warfare-1.12.2' }
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
if ((Test-Path -LiteralPath (Join-Path $InstallRoot 'payload.zip')) -and (Test-Path -LiteralPath (Join-Path $InstallRoot 'package-manifest.json'))) {
    $InstallRoot = Join-Path $env:LOCALAPPDATA 'Warfare-1.12.2'
}
if (-not $PackageRoot -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'payload.zip'))) { $PackageRoot = $PSScriptRoot }
$script:settingsPath = Join-Path $InstallRoot 'warfare-settings.json'
$script:settings = $null
if (Test-Path -LiteralPath $script:settingsPath) { try { $script:settings = Get-Content -LiteralPath $script:settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { } }
$defaults = $null
foreach ($candidate in @((Join-Path $InstallRoot 'server-defaults.json'),(Join-Path $PSScriptRoot 'server-defaults.json'))) {
    if (Test-Path -LiteralPath $candidate) { try { $defaults=Get-Content -LiteralPath $candidate -Raw -Encoding UTF8 | ConvertFrom-Json; break } catch { } }
}
$script:connection = Get-WarfareConnection $script:settings $defaults
if (-not $Language) { $Language = if ($script:settings -and $script:settings.language -eq 'en') { 'en' } else { 'ru' } }
$script:language = $Language
$sourcePath = Join-Path $InstallRoot 'launcher-source.json'
if (-not $PackageRoot -and (Test-Path -LiteralPath $sourcePath)) { try { $PackageRoot = (Get-Content -LiteralPath $sourcePath -Raw -Encoding UTF8 | ConvertFrom-Json).path } catch { } }
$script:packageRoot = $PackageRoot
$script:process = $null
$script:mode = ''
$script:ready = $false
$script:busy = $false
$script:jobId = [Guid]::NewGuid().ToString('N')
$script:logDirectory = Join-Path $InstallRoot '.launcher'
$script:statusPath = Join-Path $script:logDirectory ($script:jobId + '.json')
$script:lastStatus = ''
$script:workerState = ''
$script:needsUpdate = $false
$script:localNeedsUpdate = $false
$script:remoteRelease = $null
function L([string]$Ru, [string]$En) { if ($script:language -eq 'en') { return $En }; return $Ru }
function Quote-Argument([string]$Value) {
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    return '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}
function Has-Package {
    if (-not $script:packageRoot) { return $false }
    foreach ($name in @('Install-Warfare.ps1','Play-Warfare.ps1','Play.cmd','Warfare-Launcher.ps1','Warfare-Connection.ps1','Warfare-Performance.ps1','Warfare-Onboarding.ps1','Configure-FirstPlay.ps1','Warfare-Updates.ps1','Check-WarfareUpdate.ps1','Configure-Controller.ps1','release.json','code.ico','payload.zip','runtime.zip','package-manifest.json','installer-files.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $script:packageRoot $name) -PathType Leaf)) { return $false }
    }
    return $true
}
$form = [Windows.Forms.Form]::new()
$form.Text = 'RV'
$form.ShowIcon = $false
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'code.ico')) { $form.Icon = [Drawing.Icon]::new((Join-Path $PSScriptRoot 'code.ico')); $form.ShowIcon = $true }
$form.ClientSize = [Drawing.Size]::new(960,640)
$form.StartPosition = 'CenterScreen'
$form.BackColor = [Drawing.Color]::FromArgb(21,25,32)
$form.ForeColor = [Drawing.Color]::FromArgb(238,240,244)
$form.Font = [Drawing.Font]::new('Segoe UI',10)
$form.AutoScaleMode = 'Dpi'
$form.AutoScaleDimensions = [Drawing.SizeF]::new(96,96)
$form.SuspendLayout()
function Label([int]$X,[int]$Y,[int]$W,[int]$H,[int]$Size=10) {
    $control = [Windows.Forms.Label]::new()
    $control.Location = [Drawing.Point]::new($X,$Y)
    $control.Size = [Drawing.Size]::new($W,$H)
    $control.Font = [Drawing.Font]::new('Segoe UI',$Size)
    $form.Controls.Add($control)
    return $control
}
function Button([int]$X,[int]$Y,[int]$W,[int]$H) {
    $control = [VmButton]::new()
    $control.Location = [Drawing.Point]::new($X,$Y)
    $control.Size = [Drawing.Size]::new($W,$H)
$control.FlatStyle = 'Flat'
    $control.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(66,74,87)
    $control.BackColor = [Drawing.Color]::FromArgb(32,38,48)
    $control.ForeColor = $form.ForeColor
    $control.Cursor = 'Hand'
    $control.FlatAppearance.MouseOverBackColor = [Drawing.Color]::FromArgb(49,59,72)
    $control.FlatAppearance.MouseDownBackColor = [Drawing.Color]::FromArgb(58,70,84)
    $form.Controls.Add($control)
    return $control
}
$title = Label 32 24 430 64 34
$title.Text = 'RV'
$nicknameLabel = Label 35 113 350 26
$nickname = [Windows.Forms.TextBox]::new()
$nickname.Location = [Drawing.Point]::new(35,145)
$nickname.Size = [Drawing.Size]::new(340,32)
$nickname.MaxLength = 16
$nickname.Font = [Drawing.Font]::new('Segoe UI',13)
$nickname.BackColor = [Drawing.Color]::FromArgb(35,42,53)
$nickname.ForeColor = $form.ForeColor
$nickname.BorderStyle = 'FixedSingle'
if ($script:settings) { $nickname.Text = $script:settings.nickname }
$form.Controls.Add($nickname)
$languageBox = [Windows.Forms.ComboBox]::new()
$languageBox.DropDownStyle = 'DropDownList'
$languageBox.Location = [Drawing.Point]::new(487,40)
$languageBox.Size = [Drawing.Size]::new(158,28)
[void]$languageBox.Items.AddRange(@('Русский','English'))
$languageBox.SelectedIndex = if ($Language -eq 'en') {1} else {0}
$form.Controls.Add($languageBox)
$hint = Label 35 184 610 24 9
$hint.ForeColor = [Drawing.Color]::FromArgb(153,164,181)
$serverLabel = Label 35 229 475 32 10
$serverLabel.AutoEllipsis = $true
$serverHeading = Label 35 204 475 26 10
$serverHeading.ForeColor = [Drawing.Color]::FromArgb(153,164,181)
$changeServer = Button 521 223 124 32
$status = Label 35 282 610 60 11
$status.Text = ''
$progress = [Windows.Forms.ProgressBar]::new()
$progress.Location = [Drawing.Point]::new(35,346)
$progress.Size = [Drawing.Size]::new(610,5)
$progress.Style = 'Marquee'
$progress.Visible = $false
$form.Controls.Add($progress)
$primary = Button 35 373 610 56
$primary.BackColor = [Drawing.Color]::FromArgb(213,231,127)
$primary.ForeColor = [Drawing.Color]::FromArgb(26,32,20)
$primary.Font = [Drawing.Font]::new('Segoe UI',16,[Drawing.FontStyle]::Bold)
$primary.FlatAppearance.BorderSize = 0
$primary.FlatAppearance.MouseOverBackColor = [Drawing.Color]::FromArgb(229,241,168)
$primary.FlatAppearance.MouseDownBackColor = [Drawing.Color]::FromArgb(194,215,103)
$steam = Button 35 449 176 32
$advanced = Button 223 449 162 32
$logs = Button 397 449 112 32
$repair = Button 521 449 124 32
$install = Button 35 400 200 40
$updateAction = Button 300 400 200 40
$updateLabel = Label 35 310 610 26 9
$updateLabel.ForeColor = [Drawing.Color]::FromArgb(153,164,181)
$form.AcceptButton = $primary
function Update-Layout {
    $scale = $form.CurrentAutoScaleDimensions.Width / 96
    $width = $form.ClientSize.Width / $scale
    $height = $form.ClientSize.Height / $scale
    $margin = [Math]::Max(28,[Math]::Min(64,$width * 0.04))
    $content = $width - 2 * $margin
    $column = ($content - 48) / 2
    $compact = $height -lt 600
    $titleY = if ($compact) { 8 } else { 24 }
    $fieldY = if ($compact) { 80 } else { 132 }
    $bounds = @(
        @($title,$margin,$titleY,($content-200),64),
        @($languageBox,($width-$margin-168),($titleY+20),168,30),
        @($nicknameLabel,$margin,$fieldY,$column,26),
        @($nickname,$margin,($fieldY+35),$column,38),
        @($hint,$margin,($fieldY+83),$column,26),
        @($serverHeading,($margin+$column+48),$fieldY,$column,26),
        @($serverLabel,($margin+$column+48),($fieldY+41),$column,32),
        @($status,$margin,[Math]::Max(278,($height-316)/2),$content,80),
        @($updateLabel,$margin,($height-264),$content,26),
        @($progress,$margin,($height-226),$content,5),
        @($install,$margin,($height-200),(($content-24)/3),42),
        @($repair,($margin+($content+12)/3),($height-200),(($content-24)/3),42),
        @($updateAction,($margin+2*($content+12)/3),($height-200),(($content-24)/3),42),
        @($primary,$margin,($height-142),$content,66),
        @($changeServer,$margin,($height-54),(($content-36)/4),32),
        @($advanced,($margin+($content+12)/4),($height-54),(($content-36)/4),32),
        @($logs,($margin+2*($content+12)/4),($height-54),(($content-36)/4),32),
        @($steam,($margin+3*($content+12)/4),($height-54),(($content-36)/4),32)
    )
    foreach ($item in $bounds) { $item[0].SetBounds([int]($item[1]*$scale),[int]($item[2]*$scale),[int]($item[3]*$scale),[int]($item[4]*$scale)) }
    if ($compact) {
        $compactBounds = @(
            @($hint,$margin,154,$column,26),
            @($updateLabel,($margin+$column+48),154,$column,26),
            @($status,$margin,186,$content,44),
            @($progress,$margin,($height-190),$content,4),
            @($install,$margin,($height-178),(($content-24)/3),36),
            @($repair,($margin+($content+12)/3),($height-178),(($content-24)/3),36),
            @($updateAction,($margin+2*($content+12)/3),($height-178),(($content-24)/3),36),
            @($primary,$margin,($height-124),$content,56),
            @($changeServer,$margin,($height-46),(($content-36)/4),28),
            @($advanced,($margin+($content+12)/4),($height-46),(($content-36)/4),28),
            @($logs,($margin+2*($content+12)/4),($height-46),(($content-36)/4),28),
            @($steam,($margin+3*($content+12)/4),($height-46),(($content-36)/4),28)
        )
        foreach ($item in $compactBounds) { $item[0].SetBounds([int]($item[1]*$scale),[int]($item[2]*$scale),[int]($item[3]*$scale),[int]($item[4]*$scale)) }
    }
}
$form.Add_ClientSizeChanged({ Update-Layout })
function Refresh-Text {
    $nicknameLabel.Text = L 'Ник' 'Nickname'
    $hint.Text = L '3–16 латинских букв, цифр или _.' '3–16 letters, digits or _.'
    $changeServer.Text = L 'Настройки' 'Settings'
    $serverHeading.Text = L 'Подключение' 'Connection'
    $serverLabel.Text = if ($script:connection.connectionTarget) {
        if($script:connection.connectionMode -eq 'porthole') {
            if ($script:connection.connectionTarget -like 'peer:*') { L 'Сервер в Steam' 'Steam server' }
            else { 'Porthole: ' + $script:connection.connectionTarget }
        }
        else { (L 'Сервер: ' 'Server: ') + $script:connection.connectionTarget + ':' + $script:connection.serverPort }
    } else { L 'Сервер не выбран' 'No server selected' }
    $steam.Text = 'Steam'
    $advanced.Text = L 'Папка игры' 'Game folder'
    $logs.Text = L 'Журнал' 'Log'
    $repair.Text = L 'Проверить файлы' 'Check files'
    $install.Text = L 'Установить' 'Install'
    $updateAction.Text = L 'Обновить' 'Update'
    $primary.Text = L 'ИГРАТЬ' 'PLAY'
    $primary.Enabled = $script:ready -and -not $script:busy
    $repair.Enabled = -not $script:busy -and (Test-Path -LiteralPath (Join-Path $InstallRoot 'installed-manifest.json'))
    $updateLabel.Text = if ($script:needsUpdate) { L 'Доступно обновление.' 'Update available.' } else { '' }
    $updateAction.BackColor = if ($script:needsUpdate) { [Drawing.Color]::FromArgb(63,76,52) } else { [Drawing.Color]::FromArgb(32,38,48) }
}
function Set-Busy([bool]$Busy) {
    $script:busy = $Busy
    foreach ($control in @($primary,$nickname,$languageBox,$advanced,$repair,$steam,$changeServer,$install,$updateAction)) { $control.Enabled = -not $Busy }
    $progress.Visible = $Busy
    Refresh-Text
}
function Save-Settings([switch]$ConnectionOnly) {
    if (-not $ConnectionOnly -and $nickname.Text.Trim() -notmatch '^[A-Za-z0-9_]{3,16}$') { throw (L 'Введи ник: 3–16 латинских букв, цифр или _.' 'Enter a nickname: 3–16 letters, digits or _.') }
    if (-not $script:settings) { $script:settings = [PSCustomObject]@{language=$script:language;nickname=$nickname.Text.Trim()} }
    $script:settings|Add-Member NoteProperty nickname $nickname.Text.Trim() -Force
    $script:settings|Add-Member NoteProperty language $script:language -Force
    $script:settings = Set-WarfareConnection $script:settings $script:connection
    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    $temp = $script:settingsPath + '.tmp'
    [IO.File]::WriteAllText($temp, ($script:settings | ConvertTo-Json -Depth 32), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temp -Destination $script:settingsPath -Force
}
function Start-Worker([string]$Mode,[string]$Script,[string[]]$Arguments) {
    New-Item -ItemType Directory -Path $script:logDirectory -Force | Out-Null
    $script:outFile = Join-Path $script:logDirectory ($script:jobId + '-' + $Mode + '.log')
    $script:errFile = Join-Path $script:logDirectory ($script:jobId + '-' + $Mode + '.err')
    if (Test-Path -LiteralPath $script:statusPath) { Remove-Item -LiteralPath $script:statusPath -Force }
    $script:lastStatus = ''
    $script:workerState = ''
    $script:mode = $Mode
    $shell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $argLine = (@('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',$Script) + $Arguments | ForEach-Object { Quote-Argument $_ }) -join ' '
    $script:process = Start-Process -FilePath $shell -ArgumentList $argLine -WindowStyle Hidden -WorkingDirectory (Split-Path -Parent $Script) -RedirectStandardOutput $script:outFile -RedirectStandardError $script:errFile -PassThru
    $null = $script:process.Handle
    Set-Busy $true
}
function Start-Install {
    Save-Settings
    if (-not (Has-Package)) {
        $picker = [Windows.Forms.OpenFileDialog]::new()
        $picker.Title = L 'Выбери Install-Warfare.ps1 в распакованном пакете' 'Choose Install-Warfare.ps1 in the extracted package'
        $picker.Filter = 'RV installer|Install-Warfare.ps1'
        try { if ($picker.ShowDialog($form) -ne 'OK') { return }; $script:packageRoot = Split-Path -Parent $picker.FileName } finally { $picker.Dispose() }
    }
    if (-not (Has-Package)) { throw (L 'Нужен полный актуальный установщик RV. Распакуй новый архив целиком.' 'Use the complete current RV installer. Extract the entire new archive.') }
    Assert-VmUpgrade $script:packageRoot $InstallRoot
    $status.Text = L 'Установка…' 'Installing…'
    Start-Worker 'install' (Join-Path $script:packageRoot 'Install-Warfare.ps1') @('-Language',$script:language,'-Nickname',$nickname.Text.Trim(),'-InstallRoot',$InstallRoot,'-NoLaunch','-NoSteam','-StatusFile',$script:statusPath)
}
function Start-Update {
    Save-Settings
    Read-UpdateStatus
    if ($script:localNeedsUpdate -and -not $script:remoteRelease) { Start-Install; return }
    $status.Text = L 'Поиск обновления…' 'Checking for an update…'
    Start-Worker 'download' (Join-Path $PSScriptRoot 'Check-WarfareUpdate.ps1') @('-Root',$InstallRoot,'-CurrentVersion',(Get-VmLocalVersion $InstallRoot),'-Download')
}
function Check-Install {
    $play = Join-Path $InstallRoot 'Play-Warfare.ps1'
    if ((Test-Path -LiteralPath $play) -and (Test-Path -LiteralPath (Join-Path $InstallRoot 'installed-manifest.json'))) {
        $status.Text = L 'Проверка файлов…' 'Checking files…'
        Start-Worker 'check' $play @('-Check','-StatusFile',$script:statusPath)
    } else {
        $script:ready = $false
        $status.Text = L 'Игра ещё не установлена.' 'The game is not installed.'
        Refresh-Text
    }
}
function Start-Controller {
    $scriptPath = Join-Path $InstallRoot 'Configure-Controller.ps1'
    if (-not (Test-Path -LiteralPath $scriptPath)) { throw (L 'Установи обновление с поддержкой контроллеров.' 'Install an update with controller support.') }
    $status.Text = L 'Открытие настройки контроллера…' 'Opening controller settings…'
    Start-Worker 'controller' $scriptPath @('-InstallRoot',$InstallRoot)
}
$primary.Add_Click({ try {
    if ($script:ready) {
        Save-Settings
        $setup=Show-WarfareOnboarding -Root $InstallRoot -Language $script:language -Parent $form
        $script:settings=$setup.settings;$script:connection=$setup.connection;Refresh-Text
        if(-not $setup.completed){$status.Text=L 'Запуск отменён. Настройку можно продолжить по «Играть».' 'Launch cancelled. Click Play to continue setup.';return}
        $script:connection = ConvertTo-WarfareConnection $script:connection.connectionMode $script:connection.connectionTarget $script:connection.serverPort
        Save-Settings; $status.Text = L 'Подключение…' 'Connecting…'; Start-Worker 'play' (Join-Path $InstallRoot 'Play-Warfare.ps1') @('-StatusFile',$script:statusPath)
    }
} catch { $status.Text = Get-WarfareConnectionError $_.Exception.Message $script:language; Set-Busy $false } })
$install.Add_Click({ try { Start-Install } catch { $status.Text = $_.Exception.Message; Set-Busy $false } })
$repair.Add_Click({ try { Check-Install } catch { $status.Text = $_.Exception.Message; Set-Busy $false } })
$updateAction.Add_Click({ try { Start-Update } catch { $status.Text = $_.Exception.Message; Set-Busy $false } })
$languageBox.Add_SelectedIndexChanged({
    $script:language = if ($languageBox.SelectedIndex -eq 1) {'en'} else {'ru'}
    Refresh-Text
    if (Test-Path -LiteralPath (Join-Path $InstallRoot 'installed-manifest.json')) {
        try { Set-WarfarePerformanceProfile -Root $InstallRoot -Language $script:language -LanguageOnly }
        catch { $status.Text=Get-WarfarePreferenceError $_.Exception.Message $script:language }
    }
})
$steam.Add_Click({ try {
    $installed = Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue
    if ($installed -and $installed.SteamPath) { Start-Process 'steam://open/main' } else { Start-Process 'https://store.steampowered.com/about/' }
} catch { $status.Text = $_.Exception.Message } })
$logs.Add_Click({ try {
    $candidates = @((Join-Path $InstallRoot 'client-errors.log'),(Join-Path $InstallRoot 'client-console.log'),(Join-Path $InstallRoot 'porthole-errors.log'))
    if ($script:errFile) { $candidates += $script:errFile }
    if ($script:outFile) { $candidates += $script:outFile }
    $latest = @($candidates | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-Item -LiteralPath $_ } | Where-Object { $_.Length -gt 0 } | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
    if ($latest.Count) { Start-Process notepad.exe -ArgumentList (Quote-Argument $latest[0].FullName) } else { $status.Text = L 'Журнал пока пуст.' 'The log is empty.' }
} catch { $status.Text = $_.Exception.Message } })
$advanced.Add_Click({ try { if(Test-Path -LiteralPath $InstallRoot){Start-Process explorer.exe -ArgumentList (Quote-Argument $InstallRoot)} } catch { $status.Text=$_.Exception.Message } })
$changeServer.Add_Click({
    $dialog = [Windows.Forms.Form]::new()
    $dialog.Text = L 'Настройки' 'Settings'
    $dialog.ClientSize = [Drawing.Size]::new(560,568)
    $dialog.StartPosition = 'CenterParent'
    $dialog.FormBorderStyle = 'FixedDialog'
    $dialog.MaximizeBox = $false
    $dialog.MinimizeBox = $false
    $dialog.Font = $form.Font
    $dialog.BackColor = $form.BackColor
    $dialog.ForeColor = $form.ForeColor
    $dialog.AutoScaleMode = 'Dpi'
    $dialog.AutoScaleDimensions = [Drawing.SizeF]::new(96,96)
    $dialog.AutoScroll = $true
    $dialog.SuspendLayout()
    $label = [Windows.Forms.Label]::new(); $label.Text = L 'Способ подключения' 'Connection type'; $label.SetBounds(20,18,510,24)
    $modeBox = [Windows.Forms.ComboBox]::new(); $modeBox.Name='connectionMode'; $modeBox.DropDownStyle='DropDownList'; $modeBox.SetBounds(20,44,510,28)
    [void]$modeBox.Items.AddRange(@('Porthole',(L 'Прямой адрес' 'Direct address'))); $modeBox.SelectedIndex=if($script:connection.connectionMode -eq 'direct'){1}else{0}
    $targetLabel = [Windows.Forms.Label]::new(); $targetLabel.Text=L 'Код Porthole или адрес' 'Porthole code or address'; $targetLabel.SetBounds(20,85,340,24)
    $portLabel = [Windows.Forms.Label]::new(); $portLabel.Text=L 'Порт сервера' 'Server port'; $portLabel.SetBounds(420,85,110,24)
    $targetInput = [Windows.Forms.TextBox]::new(); $targetInput.Name='connectionTarget'; $targetInput.SetBounds(20,112,385,28); $targetInput.MaxLength = 300; $targetInput.Text=$script:connection.connectionTarget
    $portBox = [Windows.Forms.NumericUpDown]::new(); $portBox.SetBounds(420,112,110,28); $portBox.Minimum=1; $portBox.Maximum=65535; $portBox.Value=[Math]::Min(65535,[Math]::Max(1,[int]$script:connection.serverPort))
    $detail = [Windows.Forms.Label]::new(); $detail.SetBounds(20,149,510,48)
    $detail.Text = L 'Код: из Porthole хозяина, peer:SteamID или lobby:ID. Прямое подключение: IP или домен сервера.' 'Porthole: host code, peer:SteamID or lobby:ID. Direct: server IP or hostname.'
    $preferences = Get-WarfareClientPreferences $InstallRoot
    $profileLabel = [Windows.Forms.Label]::new(); $profileLabel.SetBounds(20,204,510,24); $profileLabel.Text=L 'Производительность' 'Performance'
    $profileBox = [Windows.Forms.ComboBox]::new(); $profileBox.Name='profile'; $profileBox.DropDownStyle='DropDownList'; $profileBox.SetBounds(20,230,320,28)
    [void]$profileBox.Items.AddRange(@((L 'Слабый ПК' 'Low'),(L 'Баланс' 'Balanced'),(L 'Качество' 'Quality')))
    $profileBox.SelectedIndex=@('low','balanced','quality').IndexOf($preferences.profile)
    $profileDetail = [Windows.Forms.Label]::new(); $profileDetail.Name='profileDetail'; $profileDetail.SetBounds(20,268,510,48)
    $describeProfile = {
        $profileDetail.Text = switch ($profileBox.SelectedIndex) {
            0 { L '4 чанка, минимум эффектов. Подтверждение попаданий остаётся.' '4 chunks, minimal effects. Hit confirmation remains visible.' }
            2 { L '12 чанков, полные эффекты. Шейдеры выключены.' '12 chunks, full effects. Shaders are off.' }
            default { L '8 чанков, умеренные эффекты. Шейдеры выключены.' '8 chunks, moderate effects. Shaders are off.' }
        }
    }
    $profileBox.Add_SelectedIndexChanged($describeProfile); & $describeProfile
    $memoryLabel=[Windows.Forms.Label]::new(); $memoryLabel.SetBounds(20,322,510,24); $memoryLabel.Text=L 'Память игры' 'Game memory'
    $memoryAuto=[Windows.Forms.CheckBox]::new(); $memoryAuto.Name='memoryAuto'; $memoryAuto.SetBounds(20,350,145,28); $memoryAuto.Text=L 'Авто' 'Auto'
    $memoryInput=[Windows.Forms.NumericUpDown]::new(); $memoryInput.Name='memoryMB'; $memoryInput.SetBounds(180,350,130,28); $memoryInput.Minimum=2048; $memoryInput.Maximum=8192; $memoryInput.Increment=256
    $memoryInput.Value=3072
    $savedMemory=0
    if($script:settings -and $script:settings.PSObject.Properties['memoryMB']){[void][int]::TryParse([string]$script:settings.memoryMB,[ref]$savedMemory)}
    if($savedMemory -ge 2048 -and $savedMemory -le 8192){$memoryInput.Value=$savedMemory}
    $memoryAuto.Checked=$savedMemory -eq 0; $memoryInput.Enabled=-not $memoryAuto.Checked
    $memoryAuto.Add_CheckedChanged({$memoryInput.Enabled=-not $memoryAuto.Checked})
    $memoryUnit=[Windows.Forms.Label]::new(); $memoryUnit.SetBounds(322,354,80,24); $memoryUnit.Text=L 'МБ' 'MB'
    $memoryDetail=[Windows.Forms.Label]::new(); $memoryDetail.SetBounds(20,386,510,42)
    $memoryDetail.Text=L 'Авто учитывает память ПК и запущенного сервера. Изменения — по «Применить».' 'Auto accounts for system and local server memory. Use Apply to save these changes.'
    $hudHints=[Windows.Forms.CheckBox]::new(); $hudHints.Name='hudHints'; $hudHints.SetBounds(20,434,235,28); $hudHints.Text=L 'Подсказки управления' 'Control hints'; $hudHints.Checked=$preferences.hudHints
    $hitFeedback=[Windows.Forms.CheckBox]::new(); $hitFeedback.Name='hitFeedback'; $hitFeedback.SetBounds(270,434,260,28); $hitFeedback.Text=L 'Подтверждение попаданий' 'Hit confirmation'; $hitFeedback.Checked=$preferences.hitFeedback
    $apply=[Windows.Forms.Button]::new(); $apply.Name='applyPerformance'; $apply.SetBounds(360,230,170,32); $apply.Text=L 'Применить' 'Apply'
    $apply.FlatStyle='Flat'; $apply.BackColor=[Drawing.Color]::FromArgb(32,38,48)
    $apply.Enabled=Test-Path -LiteralPath (Join-Path $InstallRoot 'installed-manifest.json')
    $apply.Add_Click({try {
        $chosenMemory=if($memoryAuto.Checked){0}else{[int]$memoryInput.Value}
        $memorySettings=[PSCustomObject]@{memoryMB=$chosenMemory}
        [void](Get-WarfareHeapMB $memorySettings)
        $chosenProfile=@('low','balanced','quality')[$profileBox.SelectedIndex]
        Set-WarfarePerformanceProfile -Root $InstallRoot -Profile $chosenProfile -Language $script:language -HudHints $hudHints.Checked -HitFeedback $hitFeedback.Checked -ApplyGraphics
        if(-not $script:settings){$script:settings=[PSCustomObject]@{nickname=$nickname.Text.Trim();language=$script:language}}
        $script:settings|Add-Member NoteProperty memoryMB $chosenMemory -Force
        Save-Settings -ConnectionOnly
        $profileDetail.Text=L 'Применено. Можно запускать игру.' 'Applied. You can start the game.'
    }catch{$profileDetail.Text=Get-WarfarePreferenceError $_.Exception.Message $script:language}})
    $autoCheck = [Windows.Forms.CheckBox]::new(); $autoCheck.Name='autoCheck'; $autoCheck.SetBounds(20,472,510,28)
    $autoCheck.Text = L 'Проверять обновления при запуске' 'Check for updates on startup'
    $autoCheck.Checked = Get-VmAutoCheck $InstallRoot
    $save = [Windows.Forms.Button]::new(); $save.Name='saveConnection'; $save.SetBounds(390,516,140,32); $save.Text = L 'Сохранить' 'Save'
    $save.FlatStyle = 'Flat'; $save.BackColor = [Drawing.Color]::FromArgb(32,38,48)
    $controller = [VmButton]::new(); $controller.Name='setupControls';$controller.SetBounds(20,516,155,32)
    $controller.Text = L 'Настроить игру' 'Play setup'
    $controller.FlatStyle = 'Flat'; $controller.BackColor = $save.BackColor
    $controller.Enabled = Test-Path -LiteralPath (Join-Path $InstallRoot 'Configure-Controller.ps1')
    $controller.Add_Click({ try {
        Save-Settings -ConnectionOnly
        $setup=Show-WarfareOnboarding -Root $InstallRoot -Language $script:language -Parent $dialog -Reconfigure
        $script:settings=$setup.settings;$script:connection=$setup.connection;Refresh-Text
        if($setup.completed){$status.Text=L 'Управление и сервер сохранены.' 'Controls and server saved.';$dialog.DialogResult='Cancel'}
    } catch { $detail.Text=$_.Exception.Message } })
    $controlsHelp=[VmButton]::new(); $controlsHelp.Name='controlsHelp'; $controlsHelp.SetBounds(190,516,185,32); $controlsHelp.Text=L 'Управление · F8' 'Controls · F8'
    $controlsHelp.FlatStyle='Flat'; $controlsHelp.BackColor=$save.BackColor
    $controlsHelp.Add_Click({[void][Windows.Forms.MessageBox]::Show($dialog,(L 'F8 — контроллер, калибровка, пресеты и плавность FPV. Настройки сохраняются локально. Огонь, оружие и перезарядка показаны в HUD техники и руководстве.' 'F8 opens controller selection, calibration, presets and FPV smoothing. Settings are saved locally. Fire, weapon selection and reload are shown in the vehicle HUD and guide.'),(L 'Управление' 'Controls'),'OK','Information')})
    $save.Add_Click({ try {
        $modeValue = if($modeBox.SelectedIndex -eq 1){'direct'}else{'porthole'}
        $newConnection = if ($targetInput.Text.Trim()) { ConvertTo-WarfareConnection $modeValue $targetInput.Text $portBox.Value.ToString() } else { [PSCustomObject]@{connectionMode=$modeValue;connectionTarget='';serverPort=[int]$portBox.Value} }
        $script:connection=$newConnection; Save-Settings -ConnectionOnly
        $wasAutoCheck = Get-VmAutoCheck $InstallRoot
        Set-VmAutoCheck $InstallRoot $autoCheck.Checked
        if ($autoCheck.Checked -and -not $wasAutoCheck) { Start-VmUpdateCheck $InstallRoot $PSScriptRoot }
        Refresh-Text
        $status.Text=L 'Настройки сохранены.' 'Settings saved.'; $dialog.DialogResult='OK'
    } catch { $detail.Text=Get-WarfareConnectionError $_.Exception.Message $script:language } })
    $dialog.AcceptButton = $save
    $dialog.Controls.AddRange(@($label,$modeBox,$targetLabel,$portLabel,$targetInput,$portBox,$detail,$autoCheck,$save,$controller,$profileLabel,$profileBox,$profileDetail,$memoryLabel,$memoryAuto,$memoryInput,$memoryUnit,$memoryDetail,$hudHints,$hitFeedback,$apply,$controlsHelp))
    $dialog.AutoScaleDimensions = [Drawing.SizeF]::new(96,96)
    $dialog.ResumeLayout($true)
    $dialogScale = $dialog.CurrentAutoScaleDimensions.Width / 96
    $availableHeight=[Windows.Forms.Screen]::FromControl($form).WorkingArea.Height-80
    $dialog.ClientSize = [Drawing.Size]::new([int](560*$dialogScale),[int][Math]::Min(568*$dialogScale,$availableHeight))
    try {
        [void]$dialog.ShowDialog($form)
    } catch { $status.Text = $_.Exception.Message } finally { $dialog.Dispose() }
})
$timer = [Windows.Forms.Timer]::new()
function Read-UpdateStatus {
    $script:remoteRelease = $null
    try {
        $update = Get-Content -LiteralPath (Join-Path $InstallRoot '.updates\status.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $current = Get-VmVersion (Get-VmLocalVersion $InstallRoot)
        $packVersion = Get-VmVersion (Get-VmLocalVersion $(if ($script:packageRoot) { $script:packageRoot } else { $PSScriptRoot }))
        if ($packVersion -gt $current) { $current = $packVersion }
        if ($update.state -in @('available','downloaded') -and (Get-VmVersion $update.version) -gt $current) { $script:remoteRelease = $update }
    } catch { }
    $script:needsUpdate = $script:localNeedsUpdate -or [bool]$script:remoteRelease
    if (-not $script:busy) { Refresh-Text }
}
$timer.Interval = 350
$timer.Add_Tick({
    if (-not $script:busy) { Read-UpdateStatus }
    if (-not $script:process) { return }
    try {
        if (Test-Path -LiteralPath $script:statusPath) {
            try { $state = Get-Content -LiteralPath $script:statusPath -Raw -Encoding UTF8 | ConvertFrom-Json; $script:workerState=$state.state; if ($state.message -and $state.message -ne $script:lastStatus) { $status.Text = $state.message; $script:lastStatus = $state.message } } catch { }
        } elseif ($script:mode -eq 'install' -and (Test-Path -LiteralPath $script:outFile)) {
            try { $lines = @(Get-Content -LiteralPath $script:outFile -Tail 3 -Encoding UTF8 | Where-Object { $_.Trim() }); if ($lines.Count) { $status.Text = $lines[-1] } } catch { }
        }
        if (-not $script:process.HasExited) { return }
        $script:process.WaitForExit()
        $exitCode = $script:process.ExitCode; $mode = $script:mode
        $script:process.Dispose(); $script:process = $null; Set-Busy $false
        if ($exitCode -ne 0) {
            if (-not $script:lastStatus -or ($mode -eq 'install' -and $script:workerState -ne 'failed')) {
                $details = @(); if (Test-Path -LiteralPath $script:errFile) { $details = @(Get-Content -LiteralPath $script:errFile -Encoding UTF8 | Where-Object { $_.Trim() }) }
                $status.Text = if ($details.Count) { ($details | Select-Object -First 2) -join ' ' } else { L 'Не удалось завершить операцию. Открой «Журнал» и повтори попытку.' 'The operation did not complete. Open Log and try again.' }
            }
            if ($mode -in @('install','check')) { $script:ready = $false }
            if ($mode -eq 'prepare') { $script:ready = $true }
            Refresh-Text; return
        }
        if ($mode -eq 'download') {
            $update = Get-Content -LiteralPath (Join-Path $InstallRoot '.updates\status.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($update.state -eq 'current') {
                $script:remoteRelease = $null
                $script:needsUpdate = $script:localNeedsUpdate
                $status.Text = L 'Обновлений нет.' 'You are up to date.'
                Refresh-Text
                return
            }
            if ($update.state -ne 'downloaded' -or -not (Test-Path -LiteralPath (Join-Path $update.packageRoot 'Install-Warfare.ps1'))) { throw (L 'Обновление ещё не готово. Повтори попытку.' 'The update is not ready. Please try again.') }
            $script:packageRoot = $update.packageRoot
            $script:remoteRelease = $null
            Start-Install
        } elseif ($mode -eq 'install') {
            $script:needsUpdate = $false; $script:localNeedsUpdate = $false
            if ($script:packageRoot) { [IO.File]::WriteAllText($sourcePath, (@{path=$script:packageRoot}|ConvertTo-Json),[Text.UTF8Encoding]::new($false)) }
            $status.Text = L 'Подготовка подключения…' 'Preparing connection…'
            Start-Worker 'prepare' (Join-Path $InstallRoot 'Play-Warfare.ps1') @('-Prepare','-StatusFile',$script:statusPath)
        } elseif ($mode -eq 'prepare') {
            Check-Install
        } elseif ($mode -eq 'controller') {
            $status.Text = L 'Настройка контроллера открыта.' 'Controller settings opened.'
        } elseif ($mode -eq 'check') {
            $script:ready = $true; $script:localNeedsUpdate = $false
            if (Has-Package) {
                $packVersion = Get-VmVersion (Get-VmLocalVersion $script:packageRoot)
                $installedVersion = Get-VmVersion (Get-VmLocalVersion $InstallRoot)
                if ($packVersion -gt $installedVersion) { $script:localNeedsUpdate = $true }
                elseif ($packVersion -eq [version]'0.0.0' -and $installedVersion -eq [version]'0.0.0') { $script:localNeedsUpdate = (Get-FileHash -LiteralPath (Join-Path $script:packageRoot 'package-manifest.json')).Hash -ne (Get-FileHash -LiteralPath (Join-Path $InstallRoot 'installed-manifest.json')).Hash }
            }
            Read-UpdateStatus
            $status.Text = if (-not $script:connection.connectionTarget) { L 'Укажи сервер в настройках.' 'Choose a server in Settings.' } else { L 'Готово к запуску.' 'Ready to play.' }
            Refresh-Text
        }
    } catch { $status.Text = $_.Exception.Message; if ($script:process -and $script:process.HasExited) { $script:process = $null; Set-Busy $false } }
})
$form.Add_FormClosing({
    if ($script:busy -and ($script:mode -eq 'prepare' -or ($script:mode -eq 'play' -and $script:workerState -eq 'preparing'))) {
        if ($script:process -and -not $script:process.HasExited) { $script:process.Kill(); [void]$script:process.WaitForExit(3000) }
    } elseif ($script:busy) {
        $_.Cancel = $true
        [void][Windows.Forms.MessageBox]::Show($form,(L 'Дождись окончания операции. Окно можно свернуть.' 'Wait for the operation to finish. You can minimize this window.'),'RV','OK','Information')
    }
})
Refresh-Text
$form.AutoScaleDimensions = [Drawing.SizeF]::new(96,96)
$form.ResumeLayout($true)
$formScale = $form.CurrentAutoScaleDimensions.Width / 96
$form.ClientSize = [Drawing.Size]::new([int](740*$formScale),[int](420*$formScale))
$form.MinimumSize = $form.Size
$form.ClientSize = [Drawing.Size]::new([int](960*$formScale),[int](680*$formScale))
Update-Layout
if ($PreviewPath) {
    $status.Text = L 'Готово к запуску.' 'Ready to play.'
    $script:ready = $true; Refresh-Text; $nickname.Text = 'Player'
    $form.ShowInTaskbar = $false; $form.Opacity = 0; $form.Show(); [Windows.Forms.Application]::DoEvents()
    $bitmap = [Drawing.Bitmap]::new($form.Width,$form.Height)
    try { $form.DrawToBitmap($bitmap,[Drawing.Rectangle]::new(0,0,$form.Width,$form.Height)); $bitmap.Save($PreviewPath,[Drawing.Imaging.ImageFormat]::Png) } finally { $bitmap.Dispose(); $form.Dispose() }
    exit 0
}
$form.Add_Shown({ $form.WindowState = 'Maximized'; Update-Layout; Start-VmUpdateCheck $InstallRoot $PSScriptRoot; Check-Install; $timer.Start(); $nickname.Focus() })
try { [void]$form.ShowDialog() } finally { $timer.Stop(); $timer.Dispose(); $form.Dispose() }
