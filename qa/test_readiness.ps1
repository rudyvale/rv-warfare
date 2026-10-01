$ErrorActionPreference='Stop'
$root=Join-Path $PSScriptRoot 'Cold game'
$shell=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$manifestPath=Join-Path $root 'installed-manifest.json'
$bytes=[IO.File]::ReadAllBytes($manifestPath)
$fixture=Join-Path $root 'optional-qa.yml'
$statusFile=Join-Path $PSScriptRoot 'lock-status.json'
function Check([int]$Expected) {
    & $shell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Play-Warfare.ps1') -Check | Out-Null
    if(($LASTEXITCODE -eq 0) -ne ($Expected -eq 0)){throw 'Unexpected readiness result'}
}
try {
    $data=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    [IO.File]::WriteAllText($fixture,'optional-value',[Text.UTF8Encoding]::new($false))
    $hash=(Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash
    Remove-Item -LiteralPath $fixture
    $data.managedFiles+=@([PSCustomObject]@{path='optional-qa.yml';sha256=$hash;existingOnly=$true})
    [IO.File]::WriteAllText($manifestPath,($data|ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
    Check 0
    'optional missing allowed: PASS'
    [IO.File]::WriteAllText($fixture,'corrupt',[Text.UTF8Encoding]::new($false))
    Check 1
    'optional corrupt rejected: PASS'
    [IO.File]::WriteAllText($fixture,'optional-value',[Text.UTF8Encoding]::new($false))
    Check 0
    'optional valid allowed: PASS'
    $lock=[IO.File]::Open((Join-Path $root '.install.lock'),'OpenOrCreate','ReadWrite','None')
    try {
        & $shell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'Play-Warfare.ps1') -SkipTunnel -StatusFile $statusFile | Out-Null
        if($LASTEXITCODE -eq 0){throw 'Game launched during install'}
        if((Get-Content -LiteralPath $statusFile -Raw -Encoding UTF8 | ConvertFrom-Json).state -ne 'error'){throw 'Lock error status missing'}
    } finally {$lock.Dispose()}
    'launch blocked by installation lock: PASS'
} finally {
    [IO.File]::WriteAllBytes($manifestPath,$bytes)
    if(Test-Path -LiteralPath $fixture){Remove-Item -LiteralPath $fixture}
}
