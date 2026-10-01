param([string]$Server = '127.0.0.1', [int]$Port = 25565)
$ErrorActionPreference = 'Stop'
$existing = Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^javaw?\.exe$' -and $_.CommandLine -match 'launchwrapper' -and $_.CommandLine -match 'Warfare-1\.12\.2' } | Select-Object -First 1
if ($existing) {
    [PSCustomObject]@{State='already_running';ProcessId=$existing.ProcessId} | ConvertTo-Json -Compress
    exit 0
}
& (Get-Command python.exe -ErrorAction Stop).Source (Join-Path $PSScriptRoot 'launch-warfare.py') --server $Server --port $Port
if ($LASTEXITCODE -ne 0) { throw 'Could not launch Warfare' }
