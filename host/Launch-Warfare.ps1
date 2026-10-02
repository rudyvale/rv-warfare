param([string]$Server = '127.0.0.1', [int]$Port = 25565)
$ErrorActionPreference = 'Stop'
$game = Join-Path $env:APPDATA '.minecraft\versions\Warfare-1.12.2'
$performance = Join-Path $PSScriptRoot 'Warfare-Performance.ps1'
if (-not (Test-Path -LiteralPath $performance)) { $performance = Join-Path (Split-Path -Parent $PSScriptRoot) 'src\Warfare-Performance.ps1' }
. $performance
$existing = Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^javaw?\.exe$' -and $_.CommandLine -match '(?:^|\s)net\.minecraft\.launchwrapper\.Launch(?:\s|$)' -and (Test-WarfareGameProcess $_.CommandLine $game) } | Select-Object -First 1
if ($existing) {
    [PSCustomObject]@{State='already_running';ProcessId=$existing.ProcessId} | ConvertTo-Json -Compress
    exit 0
}
$onboarding = Join-Path $PSScriptRoot 'Configure-FirstPlay.ps1'
if (-not (Test-Path -LiteralPath $onboarding)) { $onboarding = Join-Path (Split-Path -Parent $PSScriptRoot) 'src\Configure-FirstPlay.ps1' }
& $onboarding -InstallRoot $game -Owner
if ($LASTEXITCODE -eq 2) { exit 2 }
if ($LASTEXITCODE -ne 0) { throw 'Could not complete the first-play setup.' }
& (Get-Command python.exe -ErrorAction Stop).Source (Join-Path $PSScriptRoot 'launch-warfare.py') --server $Server --port $Port
if ($LASTEXITCODE -ne 0) { throw 'Could not launch Warfare' }
