$ErrorActionPreference = 'Stop'
$snapshot = & (Get-Command python.exe -ErrorAction Stop).Source (Join-Path $PSScriptRoot 'host_runtime.py') status
if ($LASTEXITCODE -ne 0) { throw 'Could not read the server status.' }
$state = $snapshot | ConvertFrom-Json
if ($state.state -ne 'running' -or -not $state.ready) { throw 'Start the server and wait until it is ready before playing.' }
& (Join-Path $PSScriptRoot 'Launch-Warfare.ps1') -Server '127.0.0.1' -Port ([int]$state.port)
