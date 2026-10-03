param(
    [string]$ServerRoot=$PSScriptRoot,
    [string]$CacheRoot=(Join-Path $env:LOCALAPPDATA 'RV/vendor-cache'),
    [string]$CancelPath,
    [string]$PreparedStage,
    [switch]$StageOnly,
    [ValidateSet('ru','en')][string]$Language='en'
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Warfare-VendorDownloads.ps1')
$python=(Get-Command python.exe -ErrorAction Stop).Source
$worker=Join-Path $PSScriptRoot 'server_vendors.py'
try {
    if ($StageOnly) {
        $snapshot=Get-Content -LiteralPath (Join-Path $PreparedStage 'prepare.json') -Raw -Encoding UTF8|ConvertFrom-Json
        $release=Get-Content -LiteralPath (Join-Path $ServerRoot 'release.json') -Raw -Encoding UTF8|ConvertFrom-Json
        if ($snapshot.catalogSha256 -cne $release.vendorCatalogSha256) { throw 'RV_VENDOR_CATALOG_DIGEST' }
        $plan=[PSCustomObject]@{catalogPath=(Join-Path $ServerRoot 'vendor-catalog.json');catalogSha256=$release.vendorCatalogSha256;stage=$PreparedStage;files=@($snapshot.actions|Where-Object {$_.file.delivery -cne 'host-owned'}).Count}
    } else {
        $prepared=& $python -X utf8 $worker prepare --server-root $ServerRoot
        if ($LASTEXITCODE -ne 0) { throw 'RV_VENDOR_PREPARE' }
        $plan=$prepared|ConvertFrom-Json
    }
    $progress={param($value) Write-Progress -Activity $value.name -Status $value.state -PercentComplete ([Math]::Min(100,[int](100*$value.received/[Math]::Max(1,$value.total))))}
    $saved=@(Save-WarfareVendorFiles -CatalogPath $plan.catalogPath -ExpectedCatalogSha256 $plan.catalogSha256 -StageRoot $plan.stage -CacheRoot $CacheRoot -Side server -CancelPath $CancelPath -ProgressCallback $progress)
    if ($saved.Count -ne $plan.files) { throw 'RV_VENDOR_CATALOG' }
    if ($StageOnly) { [PSCustomObject]@{state='staged';files=$saved.Count}|ConvertTo-Json -Compress; exit 0 }
    $arguments=@('-X','utf8',$worker,'apply','--server-root',$ServerRoot,'--stage',$plan.stage)
    if ($CancelPath) { $arguments+=@('--cancel-path',$CancelPath) }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw 'RV_VENDOR_APPLY' }
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    Write-Error (Get-WarfareVendorError -Message $_.Exception.Message -Language $Language)
    exit 1
} finally {
    Write-Progress -Activity 'RV' -Completed
}
