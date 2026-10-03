function Get-WarfareClientModSha256([string]$Path) {
    $stream=[IO.File]::OpenRead($Path)
    $hash=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose();$stream.Dispose() }
}
function Get-WarfareClientModCatalog([string]$Root) {
    $known=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($id in @('mcheli','techguns','firstaid','creativecore','enhancedvisuals')) { [void]$known.Add($id) }
    $artifacts=[Collections.Generic.List[object]]::new()
    $packs=[Collections.Generic.List[object]]::new()
    $releasePath=Join-Path $Root 'release.json'
    $catalogPath=Join-Path $Root 'vendor-catalog.json'
    if (Test-Path -LiteralPath $releasePath -PathType Leaf) {
        try { $release=Get-Content -LiteralPath $releasePath -Raw -Encoding UTF8|ConvertFrom-Json } catch { throw 'connection_package' }
        foreach ($property in @($release.clientRequiredMods.PSObject.Properties|Where-Object {$_})) {
            if (-not $property -or $property.Name -cnotmatch '^[a-z0-9_]+$' -or $property.Value -isnot [string] -or $property.Value.Length -lt 1 -or $property.Value.Length -gt 128 -or $property.Value -match '\s') { throw 'connection_package' }
            [void]$known.Add($property.Name)
        }
        if ($release.vendorCatalogSha256) {
            if ($release.vendorCatalogSha256 -cnotmatch '^[a-f0-9]{64}$' -or -not (Test-Path -LiteralPath $catalogPath -PathType Leaf) -or (Get-Item -LiteralPath $catalogPath).Length -gt 2MB -or (Get-WarfareClientModSha256 $catalogPath) -cne $release.vendorCatalogSha256) { throw 'connection_package' }
            try { $catalog=Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8|ConvertFrom-Json } catch { throw 'connection_package' }
            if ($catalog.schema -ne 1 -or $catalog.state -cne 'pinned' -or $catalog.minecraft -cne '1.12.2' -or $catalog.loader -cne 'forge' -or $catalog.javaMajor -ne 8) { throw 'connection_package' }
            foreach ($file in @($catalog.files)) {
                if ($file.side -cnotin @('client','both')) { continue }
                $ids=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
                foreach ($id in @($file.expectedModIds)+@($file.fml.PSObject.Properties|ForEach-Object {$_.Name})) {
                    if ($id -isnot [string] -or $id -cnotmatch '^[a-z0-9_]+$') { throw 'connection_package' }
                    [void]$known.Add($id)
                    [void]$ids.Add($id)
                }
                if ($ids.Count) {
                    if ($file.sha256 -cnotmatch '^[a-f0-9]{64}$' -or $file.size -lt 1 -or $file.size -gt 1GB) { throw 'connection_package' }
                    $artifacts.Add([PSCustomObject]@{sha256=$file.sha256;size=[long]$file.size;ids=@($ids)})
                }
                if ($file.kind -ceq 'content-pack') {
                    foreach ($definition in @($file.definitionHashes.PSObject.Properties)) {
                        if (-not $definition) { throw 'connection_package' }
                        $memberMatch=[regex]::Match($definition.Name,'^assets/([a-z0-9_]+)/packdefinition\.json$')
                        if (-not $memberMatch.Success -or $definition.Value -cnotmatch '^[a-f0-9]{64}$') { throw 'connection_package' }
                        $packId=$memberMatch.Groups[1].Value
                        $packs.Add([PSCustomObject]@{packId=$packId;member=$definition.Name;sha256=$definition.Value})
                    }
                }
            }
        } elseif ($release.version -match '^([0-9]+)\.([0-9]+)\.([0-9]+)$' -and [version]$release.version -ge [version]'1.2.0') { throw 'connection_package' }
    }
    return [PSCustomObject]@{ids=@($known);artifacts=$artifacts.ToArray();packs=$packs.ToArray()}
}
function Get-WarfareDuplicateClientMods([string]$Root) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $catalog=Get-WarfareClientModCatalog $Root
    $known=$catalog.ids
    $found=@{}
    $foundPacks=@{}
    foreach ($directory in @((Join-Path $Root 'mods'),(Join-Path $Root 'mods/1.12.2'))) {
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) { continue }
        foreach ($file in @(Get-ChildItem -LiteralPath $directory -Filter '*.jar' -File)) {
            $ids=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
            $archive=$null; $reader=$null
            try {
                $archive=[IO.Compression.ZipFile]::OpenRead($file.FullName)
                $entry=$archive.GetEntry('mcmod.info')
                if ($entry -and $entry.Length -le 65536) {
                    $reader=[IO.StreamReader]::new($entry.Open(),[Text.Encoding]::UTF8)
                    $metadata=$reader.ReadToEnd()|ConvertFrom-Json
                    $records=if ($metadata -is [PSCustomObject] -and $metadata.PSObject.Properties['modList']) { $metadata.modList } else { $metadata }
                    foreach ($record in $records) { if ($record.modid -cin $known) { [void]$ids.Add([string]$record.modid) } }
                }
                foreach ($definition in $catalog.packs) {
                    $packEntry=$archive.GetEntry($definition.member)
                    if (-not $packEntry -or $packEntry.Length -gt 65536) { continue }
                    $packReader=$null
                    try {
                        $packReader=[IO.StreamReader]::new($packEntry.Open(),[Text.Encoding]::UTF8)
                        $pack=$packReader.ReadToEnd()|ConvertFrom-Json
                        $field=@($pack.PSObject.Properties|Where-Object {$_.Name -ceq 'packID'})
                        if ($field.Count -ne 1 -or $field[0].Value -cne $definition.packId) { continue }
                        if (-not $foundPacks.ContainsKey($definition.packId)) { $foundPacks[$definition.packId]=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase) }
                        [void]$foundPacks[$definition.packId].Add($file.FullName)
                    } catch {} finally { if ($packReader) { $packReader.Dispose() } }
                }
            } catch {} finally { if ($reader) { $reader.Dispose() }; if ($archive) { $archive.Dispose() } }
            $matching=@($catalog.artifacts|Where-Object {$_.size -eq $file.Length})
            if ($matching.Count) {
                $digest=(Get-WarfareClientModSha256 $file.FullName)
                foreach ($artifact in $matching) { if ($artifact.sha256 -ceq $digest) { foreach ($id in $artifact.ids) { [void]$ids.Add($id) } } }
            }
            foreach ($id in $ids) {
                if (-not $found.ContainsKey($id)) { $found[$id]=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase) }
                [void]$found[$id].Add($file.FullName)
            }
        }
    }
    foreach ($id in @($found.Keys|Sort-Object)) { if ($found[$id].Count -gt 1) { [PSCustomObject]@{kind='mod';modid=$id;paths=@($found[$id]|Sort-Object)} } }
    foreach ($packId in @($foundPacks.Keys|Sort-Object)) { if ($foundPacks[$packId].Count -gt 1) { [PSCustomObject]@{kind='content-pack';packId=$packId;paths=@($foundPacks[$packId]|Sort-Object)} } }
}
