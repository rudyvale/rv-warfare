param([string]$InstallRoot, [switch]$Probe, [ValidateSet('Probe','Keyboard','Configure')][string]$WizardAction, [string]$ReportPath, [ValidateSet('easy','radio','gamepad')][string]$Kind, [string]$DeviceId, [string]$Brand, [string]$CancelPath)
$ErrorActionPreference = 'Stop'
if (-not $InstallRoot) { $InstallRoot = Join-Path $env:LOCALAPPDATA 'Warfare-1.12.2' }
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
$java = Join-Path $InstallRoot 'runtime\bin\java.exe'
$sharedRoot = Join-Path $env:LOCALAPPDATA 'Warfare-1.12.2'
if (-not (Test-Path -LiteralPath $java)) { $java = Join-Path $sharedRoot 'runtime\bin\java.exe' }
if (-not (Test-Path -LiteralPath $java)) { throw 'Для настройки нужен установленный runtime RV.' }
$mod = @(Get-ChildItem -LiteralPath (Join-Path $InstallRoot 'mods') -Filter 'mcheli*.jar' -File)
if ($mod.Count -ne 1) { throw 'Ожидается один мод MC Heli. Нажми «Проверить» в RV.' }
$libraryRoot = Join-Path $InstallRoot 'libraries'
if (-not (Test-Path -LiteralPath $libraryRoot)) { $libraryRoot = Join-Path $env:APPDATA '.minecraft\libraries' }
if (-not (Test-Path -LiteralPath $libraryRoot)) { $libraryRoot = Join-Path $sharedRoot 'libraries' }
$classpath = @($mod[0].FullName) + @(Get-ChildItem -LiteralPath $libraryRoot -Recurse -Filter '*.jar' -File | Where-Object { $_.Name -match '^(jinput-2\.|jutils-|lwjgl-2\.|gson-)' } | ForEach-Object FullName)
function Quote-ControllerArgument([string]$Value) { '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"' }
$nativePath = Join-Path $InstallRoot 'natives'
if (-not (Test-Path -LiteralPath (Join-Path $nativePath 'jinput-dx8_64.dll'))) { $nativePath = Join-Path $sharedRoot 'natives' }
$entry = if ($Probe -or $WizardAction -in @('Probe','Keyboard')) { 'com.norwood.mcheli.vm.VMController' } else { 'com.norwood.mcheli.vm.VMCalibration' }
$arguments = @('-Dfile.encoding=UTF-8',('-Djava.library.path=' + $nativePath),('-Dnet.java.games.input.librarypath=' + $nativePath),'-cp',($classpath -join ';'),$entry,$InstallRoot)
if ($WizardAction) {
    if (-not $ReportPath) { throw 'Для мастера нужен путь отчёта.' }
    $ReportPath = [IO.Path]::GetFullPath($ReportPath)
    if ($WizardAction -eq 'Configure') {
        if (-not $DeviceId -or $Kind -notin @('radio','gamepad')) { throw 'Выбери подключённое устройство и его тип.' }
        $arguments += @('--wizard',$ReportPath,$DeviceId,$Kind)
    } else { $arguments += @($(if ($WizardAction -eq 'Keyboard') { '--keyboard' } else { '--report' }),$ReportPath) }
    $process = Start-Process -FilePath $java -ArgumentList (($arguments | ForEach-Object { Quote-ControllerArgument $_ }) -join ' ') -WorkingDirectory $InstallRoot -WindowStyle Hidden -PassThru
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $cancelled = $false
    $timedOut = $false
    try {
        while (-not $process.WaitForExit(150)) {
            $cancelled = $CancelPath -and (Test-Path -LiteralPath $CancelPath -PathType Leaf)
            $timedOut = $WizardAction -ne 'Configure' -and $timer.Elapsed.TotalSeconds -ge 15
            if ($cancelled -or $timedOut) {
                if (-not $process.HasExited) { $process.Kill(); $null = $process.WaitForExit(5000) }
                $report = [ordered]@{ schema = 1; outcome = $(if ($cancelled) { 'cancelled' } else { 'error' }); devices = @(); profile = $null; inputMode = $null; error = $(if ($timedOut) { 'Controller probe timed out' } else { '' }) }
                [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($ReportPath)) | Out-Null
                [IO.File]::WriteAllText($ReportPath, ($report | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
                return
            }
        }
    } finally { if (-not $process.HasExited) { $process.Kill(); $null = $process.WaitForExit(5000) }; $timer.Stop() }
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $ReportPath -PathType Leaf)) { throw 'Настройка контроллера завершилась без отчёта.' }
    return
}
if ($Probe) { & $java @arguments; if ($LASTEXITCODE -ne 0) { throw 'Проверка контроллеров завершилась с ошибкой.' }; return }
Start-Process -FilePath $java -ArgumentList (($arguments | ForEach-Object { Quote-ControllerArgument $_ }) -join ' ') -WorkingDirectory $InstallRoot -WindowStyle Hidden
