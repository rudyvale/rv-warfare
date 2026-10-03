param([Parameter(Mandatory=$true)][string]$CacheRoot,[Parameter(Mandatory=$true)][string]$WorkRoot,[Parameter(Mandatory=$true)][string]$ReportPath)
$ErrorActionPreference='Stop'
$workspace=Split-Path -Parent $PSScriptRoot
. (Join-Path $workspace 'src/Warfare-VendorDownloads.ps1')
$catalogPath=Join-Path $workspace 'src/vendor-catalog.json'
$digest=Get-WarfareVendorSha256 $catalogPath
$events=[Collections.Generic.List[object]]::new()
$callback={param($value) $events.Add($value)}
$cases=[Collections.Generic.List[object]]::new()
foreach($side in @('client','server')){
    $stage=Join-Path $WorkRoot $side
    $arguments=@{CatalogPath=$catalogPath;ExpectedCatalogSha256=$digest;StageRoot=$stage;CacheRoot=$CacheRoot;Side=$side;ProgressCallback=$callback}
    if($PSVersionTable.PSVersion -ge [version]'7.4'){$arguments.ProgressAction='SilentlyContinue'}
    $saved=@(Save-WarfareVendorFiles @arguments)
    $expected=if($side -eq 'client'){8}else{5}
    if($saved.Count -ne $expected){throw 'Unexpected acquired file count'}
    foreach($row in $saved){if((Get-WarfareVendorSha256 (Join-Path $stage $row.path)) -cne $row.sha256){throw 'Installed vendor SHA differs'}}
    $cases.Add([PSCustomObject]@{name=$side;files=$saved.Count;actualFileHashesVerified=$true})
}
if(-not $events.Count -or @($events|Where-Object {$_.received -lt 0 -or $_.received -gt $_.total -or $_.total -lt 1}).Count){throw 'Progress callback bounds differ'}
$failed=$false
try{Save-WarfareVendorFiles -CatalogPath $catalogPath -ExpectedCatalogSha256 ('0'*64) -StageRoot (Join-Path $WorkRoot 'bad-digest') -CacheRoot $CacheRoot -ProgressCallback $callback|Out-Null}catch{$failed=$_.Exception.Message -eq 'RV_VENDOR_CATALOG_DIGEST'}
if(-not $failed){throw 'Digest validation was bypassed'}
$parameters=(Get-Command Save-WarfareVendorFiles).Parameters
if(-not $parameters['ExpectedCatalogSha256'].Attributes.Where({$_ -is [Management.Automation.ParameterAttribute] -and $_.Mandatory}).Count){throw 'Mandatory digest parameter changed'}
if($parameters['ProgressCallback'].ParameterType -ne [scriptblock]){throw 'Callback type differs'}
$report=[PSCustomObject]@{success=$true;shell=$PSVersionTable.PSVersion.ToString();catalogSha256=$digest;cases=@($cases);callbackEvents=$events.Count;mandatoryDigestPreserved=$true;commonProgressActionSupported=($PSVersionTable.PSVersion -ge [version]'7.4');scope='actual official vendor files from verified cache to isolated staging; no game or GUI launched'}
[IO.File]::WriteAllText($ReportPath,($report|ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
$report|ConvertTo-Json -Depth 12
