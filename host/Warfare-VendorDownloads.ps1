function Get-WarfareVendorSha256([string]$Path) {
    $stream=[IO.File]::OpenRead($Path)
    $hash=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose();$stream.Dispose() }
}
function Resolve-WarfareVendorPath {
    param([string]$Root,[string]$Relative)
    if ($Relative -cnotmatch '^(?:mods/[A-Za-z0-9][A-Za-z0-9._+ -]*\.jar|[Mm]odular[Ww]arfare/[A-Za-z0-9][A-Za-z0-9._+ -]*\.(?:zip|jar))$' -or $Relative -match '(?:^|/)(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)' -or $Relative -match '[/\\]\.\.') { throw 'RV_VENDOR_PATH' }
    $absoluteRoot=[IO.Path]::GetFullPath($Root).TrimEnd('\')
    $absolute=[IO.Path]::GetFullPath((Join-Path $absoluteRoot $Relative))
    if (-not $absolute.StartsWith($absoluteRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'RV_VENDOR_PATH' }
    Assert-WarfareVendorDirectory $absolute
    return $absolute
}
function Assert-WarfareVendorDirectory([string]$Path) {
    $current=[IO.Path]::GetFullPath($Path)
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            $item=Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'RV_VENDOR_PATH' }
        }
        $parent=[IO.Path]::GetDirectoryName($current)
        if ($parent -eq $current) { break }
        $current=$parent
    }
}
function Assert-WarfareVendorUrl([string]$Url) {
    $uri=$null
    if (-not [Uri]::TryCreate($Url,[UriKind]::Absolute,[ref]$uri) -or $uri.Scheme -cne 'https' -or $uri.Port -ne 443 -or $uri.UserInfo -or $uri.Fragment) { throw 'RV_VENDOR_URL' }
    $hosts=@('edge.forgecdn.net','mediafilez.forgecdn.net','media.forgecdn.net','www.curseforge.com','curseforge.com','github.com','objects.githubusercontent.com','release-assets.githubusercontent.com','cdn.modrinth.com')
    if ($uri.DnsSafeHost.ToLowerInvariant() -cnotin $hosts) { throw 'RV_VENDOR_URL' }
    return $uri
}
function Get-WarfareVendorCatalog {
    param([string]$CatalogPath,[ValidateSet('client','server')][string]$Side='client',[string]$ExpectedSha256)
    if (-not (Test-Path -LiteralPath $CatalogPath -PathType Leaf) -or (Get-Item -LiteralPath $CatalogPath).Length -gt 2MB) { throw 'RV_VENDOR_CATALOG' }
    if ($ExpectedSha256 -and ($ExpectedSha256 -cnotmatch '^[a-f0-9]{64}$' -or (Get-WarfareVendorSha256 $CatalogPath) -cne $ExpectedSha256)) { throw 'RV_VENDOR_CATALOG_DIGEST' }
    try { $catalog=Get-Content -LiteralPath $CatalogPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { throw 'RV_VENDOR_CATALOG' }
    if ($catalog.schema -ne 1 -or $catalog.state -cne 'pinned' -or $catalog.minecraft -cne '1.12.2' -or $catalog.loader -cne 'forge' -or $catalog.javaMajor -ne 8 -or -not $catalog.PSObject.Properties['files']) { throw 'RV_VENDOR_CATALOG' }
    $ids=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $paths=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $selected=[Collections.Generic.List[object]]::new()
    foreach ($file in @($catalog.files)) {
        if ($null -eq $file -or $file.id -cnotmatch '^[a-z0-9][a-z0-9-]*$' -or -not $ids.Add([string]$file.id) -or $file.name -isnot [string] -or $file.name.Length -lt 1 -or $file.name.Length -gt 128 -or $file.name -match '[\r\n]' -or $file.kind -cnotin @('mod','content-pack') -or $file.side -cnotin @('client','server','both') -or $file.delivery -cnotin @('bundle','official-download','manual')) { throw 'RV_VENDOR_CATALOG' }
        [void](Resolve-WarfareVendorPath -Root ([IO.Path]::GetTempPath()) -Relative ([string]$file.path))
        if (-not $paths.Add([string]$file.path) -or $file.sha256 -isnot [string] -or $file.sha256 -cnotmatch '^[a-f0-9]{64}$') { throw 'RV_VENDOR_CATALOG' }
        $size=[long]0
        if (-not [long]::TryParse([string]$file.size,[ref]$size) -or $size -lt 1 -or $size -gt 1GB) { throw 'RV_VENDOR_CATALOG' }
        if ($file.delivery -ceq 'official-download' -and @($file.officialUrls).Count -eq 0) { throw 'RV_VENDOR_CATALOG' }
        foreach ($url in @($file.officialUrls)) { [void](Assert-WarfareVendorUrl ([string]$url)) }
        if ($file.side -ceq 'both' -or $file.side -ceq $Side) { $selected.Add($file) }
    }
    foreach ($file in $selected) {
        foreach ($dependency in @($file.requires)) {
            if (-not $dependency -or $dependency.id -cnotmatch '^[a-z0-9][a-z0-9-]*$') { throw 'RV_VENDOR_CATALOG' }
            if ($dependency.side -and $dependency.side -cnotin @('client','server','both')) { throw 'RV_VENDOR_CATALOG' }
        }
    }
    return [PSCustomObject]@{catalog=$catalog;files=$selected.ToArray()}
}
function Test-WarfareVendorFile([string]$Path,[long]$Size,[string]$Sha256) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf) -or (Get-Item -LiteralPath $Path).Length -ne $Size) { return $false }
    return (Get-WarfareVendorSha256 $Path) -ceq $Sha256
}
function Assert-WarfareVendorCancellation([string]$CancelPath) {
    if ($CancelPath -and (Test-Path -LiteralPath $CancelPath)) { throw 'RV_VENDOR_CANCELLED' }
}
function Send-WarfareVendorProgress($Action,$File,[long]$Received,[long]$Total,[int]$Index,[int]$Count,[string]$State) {
    if ($Action) { & $Action ([PSCustomObject]@{id=$File.id;name=$File.name;received=$Received;total=$Total;index=$Index;count=$Count;state=$State}) | Out-Null }
}
function Open-WarfareVendorResponse {
    param([Uri]$Uri,[long]$Offset,[string]$CancelPath)
    $visited=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    for ($redirect=0;$redirect -le 5;$redirect++) {
        [void](Assert-WarfareVendorUrl $Uri.AbsoluteUri)
        if (-not $visited.Add($Uri.AbsoluteUri)) { throw 'RV_VENDOR_REDIRECT' }
        Assert-WarfareVendorCancellation $CancelPath
        $request=[Net.HttpWebRequest]::CreateHttp($Uri)
        $request.AllowAutoRedirect=$false
        $request.UserAgent='RV/1.2'
        $request.Timeout=30000
        $request.ReadWriteTimeout=30000
        $request.AutomaticDecompression=[Net.DecompressionMethods]::None
        if ($Offset -gt 0) { $request.AddRange($Offset) }
        $response=$null
        try {
            $task=$request.GetResponseAsync()
            $deadline=[DateTime]::UtcNow.AddSeconds(30)
            while (-not $task.IsCompleted) {
                Assert-WarfareVendorCancellation $CancelPath
                if ([DateTime]::UtcNow -gt $deadline) { throw 'RV_VENDOR_TIMEOUT' }
                Start-Sleep -Milliseconds 80
            }
            $response=$task.GetAwaiter().GetResult()
            $code=[int]$response.StatusCode
            if ($code -in @(301,302,303,307,308)) {
                $next=$null
                if (-not $response.Headers['Location'] -or -not [Uri]::TryCreate($Uri,[string]$response.Headers['Location'],[ref]$next)) { throw 'RV_VENDOR_REDIRECT' }
                [void](Assert-WarfareVendorUrl $next.AbsoluteUri)
                $Uri=$next
                $response.Dispose()
                $response=$null
                continue
            }
            return [PSCustomObject]@{response=$response;request=$request;url=$Uri.AbsoluteUri}
        } catch {
            if ($response) { $response.Dispose() }
            $request.Abort()
            throw
        }
    }
    throw 'RV_VENDOR_REDIRECT'
}
function Receive-WarfareVendorFile {
    param($File,[string]$PartPath,[Uri]$Uri,[string]$CancelPath,$ProgressAction,[int]$Index,[int]$Count)
    $offset=if (Test-Path -LiteralPath $PartPath -PathType Leaf) { (Get-Item -LiteralPath $PartPath).Length } else { 0L }
    if ($offset -ge [long]$File.size) { Remove-Item -LiteralPath $PartPath -Force; $offset=0L }
    $opened=$null; $downloadStream=$null; $output=$null
    try {
        $opened=Open-WarfareVendorResponse -Uri $Uri -Offset $offset -CancelPath $CancelPath
        $response=$opened.response
        $code=[int]$response.StatusCode
        if ($code -eq 206) {
            $range=[regex]::Match([string]$response.Headers['Content-Range'],'^bytes ([0-9]+)-([0-9]+)/([0-9]+)$')
            if (-not $range.Success -or [long]$range.Groups[1].Value -ne $offset -or [long]$range.Groups[2].Value -ne [long]$File.size-1 -or [long]$range.Groups[3].Value -ne [long]$File.size) { throw 'RV_VENDOR_RANGE' }
        } elseif ($code -eq 200) { $offset=0L }
        else { throw 'RV_VENDOR_HTTP' }
        $expected=[long]$File.size-$offset
        if ($response.ContentLength -ge 0 -and $response.ContentLength -ne $expected) { throw 'RV_VENDOR_SIZE' }
        if ($response.Headers['Content-Encoding'] -and $response.Headers['Content-Encoding'] -cne 'identity') { throw 'RV_VENDOR_ENCODING' }
        Assert-WarfareVendorCancellation $CancelPath
        $downloadStream=$response.GetResponseStream()
        if ($downloadStream.CanTimeout) { $downloadStream.ReadTimeout=5000 }
        $mode=if ($offset -gt 0) { [IO.FileMode]::Append } else { [IO.FileMode]::Create }
        $output=[IO.File]::Open($PartPath,$mode,[IO.FileAccess]::Write,[IO.FileShare]::None)
        $buffer=New-Object byte[] 65536
        $received=$offset
        $lastProgress=[DateTime]::MinValue
        while ($true) {
            Assert-WarfareVendorCancellation $CancelPath
            $read=$downloadStream.Read($buffer,0,$buffer.Length)
            if ($read -eq 0) { break }
            if ($received+$read -gt [long]$File.size) { throw 'RV_VENDOR_SIZE' }
            $output.Write($buffer,0,$read)
            $received+=$read
            if (([DateTime]::UtcNow-$lastProgress).TotalMilliseconds -ge 250) {
                Send-WarfareVendorProgress $ProgressAction $File $received ([long]$File.size) $Index $Count 'downloading'
                $lastProgress=[DateTime]::UtcNow
            }
        }
        $output.Flush($true)
        if ($received -ne [long]$File.size) { throw 'RV_VENDOR_INCOMPLETE' }
    } finally {
        if ($output) { $output.Dispose() }
        if ($opened -and $opened.request) { $opened.request.Abort() }
        if ($downloadStream) { $downloadStream.Dispose() }
        if ($opened -and $opened.response) { $opened.response.Dispose() }
    }
}
function Save-WarfareVendorFiles {
    param([string]$CatalogPath,[Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedCatalogSha256,[string]$StageRoot,[string]$CacheRoot,[ValidateSet('client','server')][string]$Side='client',[string]$CancelPath,$ProgressAction)
    $selection=Get-WarfareVendorCatalog -CatalogPath $CatalogPath -Side $Side -ExpectedSha256 $ExpectedCatalogSha256
    $files=@($selection.files)
    $stageRoot=[IO.Path]::GetFullPath($StageRoot).TrimEnd('\')
    $cacheRoot=[IO.Path]::GetFullPath($CacheRoot).TrimEnd('\')
    if ($stageRoot.Equals($cacheRoot,[StringComparison]::OrdinalIgnoreCase) -or $stageRoot.StartsWith($cacheRoot+'\',[StringComparison]::OrdinalIgnoreCase) -or $cacheRoot.StartsWith($stageRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'RV_VENDOR_PATH' }
    Assert-WarfareVendorDirectory $cacheRoot
    $plan=[Collections.Generic.List[object]]::new()
    foreach ($file in $files) {
        Assert-WarfareVendorCancellation $CancelPath
        $target=Resolve-WarfareVendorPath -Root $stageRoot -Relative $file.path
        $exists=Test-Path -LiteralPath $target
        $verified=Test-WarfareVendorFile $target ([long]$file.size) $file.sha256
        if ($exists -and -not $verified) { throw ('RV_VENDOR_CONFLICT:'+ $file.path) }
        if ($file.delivery -ceq 'manual' -and -not $verified) { throw ('RV_VENDOR_MANUAL:'+ $file.name) }
        if ($file.delivery -ceq 'bundle' -and -not $verified) { throw ('RV_VENDOR_BUNDLE:'+ $file.name) }
        $cache=Join-Path $cacheRoot ($file.sha256+'\'+[IO.Path]::GetFileName($file.path))
        Assert-WarfareVendorDirectory $cache
        $plan.Add([PSCustomObject]@{file=$file;target=$target;cache=$cache;verified=$verified})
    }
    $cacheGuard=$null
    if (@($plan|Where-Object {-not $_.verified}).Count) {
        New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
        try { $cacheGuard=[IO.File]::Open((Join-Path $cacheRoot '.vendor-download.lock'),'OpenOrCreate','ReadWrite','None') } catch { throw 'RV_VENDOR_BUSY' }
    }
    try {
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
    $index=0
    foreach ($item in $plan) {
        $index++
        Assert-WarfareVendorCancellation $CancelPath
        if ($item.verified) { Send-WarfareVendorProgress $ProgressAction $item.file ([long]$item.file.size) ([long]$item.file.size) $index $plan.Count 'verified'; continue }
        if (Test-WarfareVendorFile $item.cache ([long]$item.file.size) $item.file.sha256) { Send-WarfareVendorProgress $ProgressAction $item.file ([long]$item.file.size) ([long]$item.file.size) $index $plan.Count 'cached'; continue }
        New-Item -ItemType Directory -Path (Split-Path -Parent $item.cache) -Force | Out-Null
        $part=$item.cache+'.part'
        Assert-WarfareVendorDirectory $part
        $complete=$false
        $urls=@($item.file.officialUrls)
        $lastError=''
        for ($attempt=0;$attempt -lt 3;$attempt++) {
            Assert-WarfareVendorCancellation $CancelPath
            try {
                if (-not (Test-WarfareVendorFile $part ([long]$item.file.size) $item.file.sha256)) {
                    $uri=Assert-WarfareVendorUrl $urls[$attempt % $urls.Count]
                    Receive-WarfareVendorFile -File $item.file -PartPath $part -Uri $uri -CancelPath $CancelPath -ProgressAction $ProgressAction -Index $index -Count $plan.Count
                }
                if (-not (Test-WarfareVendorFile $part ([long]$item.file.size) $item.file.sha256)) { throw 'RV_VENDOR_DIGEST' }
                Assert-WarfareVendorCancellation $CancelPath
                Move-Item -LiteralPath $part -Destination $item.cache -Force
                $complete=$true
                break
            } catch {
                $lastError=$_.Exception.Message
                if ($lastError -eq 'RV_VENDOR_CANCELLED') { throw }
                if ($lastError -in @('RV_VENDOR_RANGE','RV_VENDOR_DIGEST','RV_VENDOR_SIZE','RV_VENDOR_ENCODING') -and (Test-Path -LiteralPath $part)) { Remove-Item -LiteralPath $part -Force }
                if ($attempt -lt 2) {
                    Send-WarfareVendorProgress $ProgressAction $item.file 0 ([long]$item.file.size) $index $plan.Count 'retrying'
                    for ($delay=0;$delay -lt 10*($attempt+1);$delay++) { Assert-WarfareVendorCancellation $CancelPath; Start-Sleep -Milliseconds 100 }
                }
            }
        }
        if (-not $complete) { throw ('RV_VENDOR_DOWNLOAD:'+ $item.file.name+':'+$lastError) }
    }
    Assert-WarfareVendorCancellation $CancelPath
    foreach ($item in $plan) {
        if ($item.verified) { continue }
        [void](Resolve-WarfareVendorPath -Root $stageRoot -Relative $item.file.path)
        if (-not (Test-WarfareVendorFile $item.cache ([long]$item.file.size) $item.file.sha256)) { throw 'RV_VENDOR_DIGEST' }
        if (Test-Path -LiteralPath $item.target) { throw ('RV_VENDOR_CONFLICT:'+ $item.file.path) }
    }
    $written=[Collections.Generic.List[string]]::new()
    try {
        foreach ($item in $plan) {
            Assert-WarfareVendorCancellation $CancelPath
            if (-not $item.verified) {
                New-Item -ItemType Directory -Path (Split-Path -Parent $item.target) -Force | Out-Null
                $temporary=$item.target+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
                try {
                    Copy-Item -LiteralPath $item.cache -Destination $temporary
                    if (-not (Test-WarfareVendorFile $temporary ([long]$item.file.size) $item.file.sha256)) { throw 'RV_VENDOR_DIGEST' }
                    if (Test-Path -LiteralPath $item.target) { throw ('RV_VENDOR_CONFLICT:'+ $item.file.path) }
                    Move-Item -LiteralPath $temporary -Destination $item.target
                    $written.Add($item.target)
                } finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
            }
            Send-WarfareVendorProgress $ProgressAction $item.file ([long]$item.file.size) ([long]$item.file.size) 0 $plan.Count 'ready'
        }
    } catch {
        foreach ($path in $written) { if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force } }
        throw
    }
    return @($plan | ForEach-Object { [PSCustomObject]@{id=$_.file.id;path=$_.file.path;size=$_.file.size;sha256=$_.file.sha256;target=$_.target;delivery=$_.file.delivery} })
    } finally { if ($cacheGuard) { $cacheGuard.Dispose() } }
}
function Initialize-WarfareVendorStage {
    param([string]$CatalogPath,[Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedCatalogSha256,[string]$InstallRoot,[string]$StageRoot,[string]$CacheRoot,[string]$CancelPath,$ProgressAction)
    $selection=Get-WarfareVendorCatalog -CatalogPath $CatalogPath -Side client -ExpectedSha256 $ExpectedCatalogSha256
    $oldPath=Join-Path $InstallRoot 'installed-manifest.json'
    $old=$null
    if (Test-Path -LiteralPath $oldPath -PathType Leaf) { try { $old=Get-Content -LiteralPath $oldPath -Raw -Encoding UTF8|ConvertFrom-Json } catch { throw 'RV_VENDOR_CATALOG' } }
    $reusable=[Collections.Generic.List[object]]::new()
    foreach ($file in @($selection.files)) {
        Assert-WarfareVendorCancellation $CancelPath
        $installed=Resolve-WarfareVendorPath -Root $InstallRoot -Relative $file.path
        $staged=Resolve-WarfareVendorPath -Root $StageRoot -Relative $file.path
        if (-not (Test-Path -LiteralPath $installed)) { continue }
        $verified=Test-WarfareVendorFile $installed ([long]$file.size) $file.sha256
        if (-not $verified) {
            $owned=@($old.managedFiles|Where-Object {$_.path -ceq $file.path -and $_.sha256 -cmatch '^[a-f0-9]{64}$'})
            if ($owned.Count -ne 1 -or -not (Test-Path -LiteralPath $installed -PathType Leaf) -or (Get-WarfareVendorSha256 $installed) -cne $owned[0].sha256) { throw ('RV_VENDOR_CONFLICT:'+$file.path) }
        } elseif (-not (Test-Path -LiteralPath $staged)) { $reusable.Add([PSCustomObject]@{source=$installed;target=$staged;file=$file}) }
    }
    foreach ($item in $reusable) {
        Assert-WarfareVendorCancellation $CancelPath
        New-Item -ItemType Directory -Path (Split-Path -Parent $item.target) -Force|Out-Null
        Copy-Item -LiteralPath $item.source -Destination $item.target
        if (-not (Test-WarfareVendorFile $item.target ([long]$item.file.size) $item.file.sha256)) { throw 'RV_VENDOR_DIGEST' }
    }
    return Save-WarfareVendorFiles -CatalogPath $CatalogPath -ExpectedCatalogSha256 $ExpectedCatalogSha256 -StageRoot $StageRoot -CacheRoot $CacheRoot -Side client -CancelPath $CancelPath -ProgressAction $ProgressAction
}
function Get-WarfareVendorError([string]$Message,[ValidateSet('ru','en')][string]$Language='en') {
    $ru=$Language -eq 'ru'
    switch -Regex ($Message) {
        '^RV_VENDOR_BUSY$' { if ($ru) { return 'Дождись окончания другой загрузки.' }; return 'Wait for the other download to finish.' }
        '^RV_VENDOR_CANCELLED$' { if ($ru) { return 'Загрузка отменена.' }; return 'Download cancelled.' }
        '^RV_VENDOR_CONFLICT:(.+)$' { if ($ru) { return ('Файл уже существует: '+$Matches[1]+'. Перемести его и повтори установку.') }; return ('File already exists: '+$Matches[1]+'. Move it and try again.') }
        '^RV_VENDOR_MANUAL:(.+)$' { if ($ru) { return ('Нужен файл '+$Matches[1]+'. Открой папку сборки и проверь загрузки.') }; return ('The '+$Matches[1]+' file is missing. Open the package folder and check downloads.') }
        '^RV_VENDOR_DOWNLOAD:' { if ($ru) { return 'Не удалось загрузить мод. Проверь интернет и нажми «Установить» ещё раз. Загруженные файлы сохранены.' }; return 'A mod could not be downloaded. Check your connection and select Install again. Downloaded files were saved.' }
        default { if ($ru) { return 'Проверь файлы сборки и повтори установку.' }; return 'Check the package files and try again.' }
    }
}
