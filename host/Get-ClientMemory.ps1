param([Parameter(Mandatory=$true)][string]$GameDir)
$ErrorActionPreference = 'Stop'
$module = Join-Path $PSScriptRoot 'Warfare-Performance.ps1'
if (-not (Test-Path -LiteralPath $module)) { $module = Join-Path (Split-Path -Parent $PSScriptRoot) 'src\Warfare-Performance.ps1' }
. $module
$settings = [pscustomobject]@{memoryMB=0}
$path = Join-Path $GameDir 'launcher-settings.json'
if (Test-Path -LiteralPath $path) { $settings = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json }
try { [Console]::WriteLine([string](Get-WarfareHeapMB $settings)) }
catch { [Console]::Error.WriteLine('Not enough free memory for the game and server. Stop other Java games or select the Low server profile, then restart the server.'); exit 1 }
