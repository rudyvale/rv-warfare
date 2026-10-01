$ErrorActionPreference = 'Stop'
& (Get-Command python.exe -ErrorAction Stop).Source (Join-Path $PSScriptRoot 'host_runtime.py') start
if ($LASTEXITCODE -ne 0) { throw 'Could not start the server. Check server-state.json and console.log.' }
