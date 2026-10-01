$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Start-Server.ps1')
& (Join-Path $PSScriptRoot 'Start-Porthole.ps1')
