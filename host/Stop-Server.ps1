$ErrorActionPreference = 'Stop'
& (Get-Command python.exe -ErrorAction Stop).Source (Join-Path $PSScriptRoot 'host_runtime.py') stop
if ($LASTEXITCODE -ne 0) { throw 'Server has not stopped yet. Check console.log.' }
