param([string]$InstallRoot,[ValidateSet('ru','en')][string]$Language='ru',[switch]$Reconfigure,[switch]$Owner)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Warfare-Connection.ps1')
. (Join-Path $PSScriptRoot 'Warfare-Onboarding.ps1')
if(-not $InstallRoot){$InstallRoot=Join-Path $env:LOCALAPPDATA 'Warfare-1.12.2'}
try {
    if($Owner){Assert-WarfareUniqueMods $InstallRoot}
    $result=Show-WarfareOnboarding -Root $InstallRoot -Language $Language -Reconfigure:$Reconfigure -Owner:$Owner
    if(-not $result.completed){exit 2}
    exit 0
} catch { Write-Error (Get-WarfareConnectionError $_.Exception.Message $Language);exit 1 }
