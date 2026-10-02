param([string]$InstallRoot, [switch]$Probe)
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
$classpath = @($mod[0].FullName) + @(Get-ChildItem -LiteralPath $libraryRoot -Recurse -Filter '*.jar' -File | Where-Object { $_.Name -match '^(jinput-2\.|jutils-|lwjgl-2\.)' } | ForEach-Object FullName)
function Quote-ControllerArgument([string]$Value) { '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"' }
$nativePath = Join-Path $InstallRoot 'natives'
if (-not (Test-Path -LiteralPath (Join-Path $nativePath 'jinput-dx8_64.dll'))) { $nativePath = Join-Path $sharedRoot 'natives' }
$entry = if ($Probe) { 'com.norwood.mcheli.vm.VMController' } else { 'com.norwood.mcheli.vm.VMCalibration' }
$arguments = @('-Dfile.encoding=UTF-8',('-Djava.library.path=' + $nativePath),('-Dnet.java.games.input.librarypath=' + $nativePath),'-cp',($classpath -join ';'),$entry,$InstallRoot)
if ($Probe) { & $java @arguments; if ($LASTEXITCODE -ne 0) { throw 'Проверка контроллеров завершилась с ошибкой.' }; return }
Start-Process -FilePath $java -ArgumentList (($arguments | ForEach-Object { Quote-ControllerArgument $_ }) -join ' ') -WorkingDirectory $InstallRoot -WindowStyle Hidden
