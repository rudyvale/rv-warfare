function Get-WarfareAmbienceSha256([string]$Path) {
    $stream=[IO.File]::OpenRead($Path)
    $hash=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose();$stream.Dispose() }
}
function Update-WarfareForgeCategory([string]$Contents,[string]$Category,$Values) {
    $lines=[Collections.Generic.List[string]]::new()
    $seen=@{}
    $depth=0; $active=$false; $found=$false
    foreach ($line in [regex]::Split($Contents.TrimEnd("`r","`n"),'\r?\n')) {
        $trimmed=$line.Trim()
        if ($trimmed -match '^#' -or -not $trimmed) { $lines.Add($line); continue }
        if ($trimmed -match '^(?:"([^"]+)"|([a-zA-Z0-9_. -]+))\s*\{$') {
            $name=if ($Matches[1]) { $Matches[1] } else { $Matches[2].Trim() }
            if ($depth -eq 0 -and $name -ceq $Category) {
                if ($found) { throw 'RV_AMBIENCE_CONFIG' }
                $active=$true; $found=$true
            }
            $depth++
            $lines.Add($line)
            continue
        }
        if ($trimmed -eq '}') {
            if ($depth -le 0) { throw 'RV_AMBIENCE_CONFIG' }
            if ($active -and $depth -eq 1) {
                foreach ($key in $Values.Keys) { if (-not $seen.ContainsKey($key)) { $lines.Add('    '+$key+'='+$Values[$key]) } }
                $active=$false
            }
            $depth--
            $lines.Add($line)
            continue
        }
        $match=[regex]::Match($trimmed,'^([BIDS]:[^=]+)\s*=')
        if ($active -and $depth -eq 1 -and $match.Success -and $Values.Keys -ccontains $match.Groups[1].Value.Trim()) {
            $key=$match.Groups[1].Value.Trim()
            if (-not $seen.ContainsKey($key)) { $lines.Add('    '+$key+'='+$Values[$key]); $seen[$key]=$true }
        } else { $lines.Add($line) }
    }
    if ($depth -ne 0) { throw 'RV_AMBIENCE_CONFIG' }
    if (-not $found) {
        $lines.Add($Category+' {')
        foreach ($key in $Values.Keys) { $lines.Add('    '+$key+'='+$Values[$key]) }
        $lines.Add('}')
    }
    return ($lines -join "`r`n")+"`r`n"
}
function ConvertFrom-WarfareAmbientJson([string]$Contents) {
    $clean=[regex]::Replace($Contents,'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/',[Text.RegularExpressions.MatchEvaluator]{param($m) if ($m.Value.StartsWith('"')) { return $m.Value }; return ''})
    return $clean|ConvertFrom-Json
}
function Get-WarfareAmbienceChanges([string]$Root,[ValidateSet('low','balanced','quality')][string]$Profile) {
    $changes=[ordered]@{}
    $jar=$null
    foreach ($directory in @((Join-Path $Root 'mods'),(Join-Path $Root 'mods/1.12.2'))) {
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) { continue }
        foreach ($candidate in @(Get-ChildItem -LiteralPath $directory -Filter '*.jar' -File|Where-Object {$_.Length -eq 76507814})) {
            if ((Get-WarfareAmbienceSha256 $candidate.FullName) -ceq '8f9ea1605d2a141b269bbfd5e9c98ae06c7f47d13283454c75258e68e381d9ed') { $jar=$candidate.FullName }
        }
    }
    if (-not $jar) { return $changes }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive=$null; $reader=$null
    try {
        $archive=[IO.Compression.ZipFile]::OpenRead($jar)
        $entry=$archive.GetEntry('assets/ambientsounds/engine.json')
        if (-not $entry -or $entry.Length -gt 2MB) { throw 'RV_AMBIENCE_CONFIG' }
        $reader=[IO.StreamReader]::new($entry.Open(),[Text.Encoding]::UTF8)
        $vendorEngine=ConvertFrom-WarfareAmbientJson $reader.ReadToEnd()
    } catch { throw 'RV_AMBIENCE_CONFIG' } finally { if ($reader) { $reader.Dispose() }; if ($archive) { $archive.Dispose() } }
    $profiles=@{
        low=@{streaming=3;normal=29;volume='0.18';environment=80;blockDistance=24;heightCount=3;biomeCount=2}
        balanced=@{streaming=4;normal=28;volume='0.30';environment=60;blockDistance=32;heightCount=4;biomeCount=3}
        quality=@{streaming=6;normal=26;volume='0.40';environment=40;blockDistance=40;heightCount=5;biomeCount=3}
    }
    $profileValues=$profiles[$Profile]
    $enginePath=Join-Path $Root 'resourcepacks/RV-Ambience/assets/ambientsounds/engine.json'
    $engine=$vendorEngine
    if (Test-Path -LiteralPath $enginePath -PathType Leaf) {
        try { $engine=ConvertFrom-WarfareAmbientJson ([IO.File]::ReadAllText($enginePath)) } catch { throw 'RV_AMBIENCE_CONFIG' }
        if ($engine -isnot [PSCustomObject] -or -not $engine.dimensions) { throw 'RV_AMBIENCE_CONFIG' }
    }
    $engineValues=[ordered]@{'enviroment-tick-time'=$profileValues.environment;'sound-tick-time'=4;'block-scan-distance'=$profileValues.blockDistance;'average-height-scan-distance'=2;'average-height-scan-count'=$profileValues.heightCount;'biome-scan-distance'=5;'biome-scan-count'=$profileValues.biomeCount}
    foreach ($key in $engineValues.Keys) { $engine|Add-Member NoteProperty $key $engineValues[$key] -Force }
    $changes[$enginePath]=($engine|ConvertTo-Json -Depth 64)+"`r`n"
    $metadataPath=Join-Path $Root 'resourcepacks/RV-Ambience/pack.mcmeta'
    if (-not (Test-Path -LiteralPath $metadataPath)) { $changes[$metadataPath]='{"pack":{"pack_format":3,"description":"RV"}}'+"`r`n" }
    $configPath=Join-Path $Root 'config/ambientsounds.cfg'
    $contents=if (Test-Path -LiteralPath $configPath -PathType Leaf) { [IO.File]::ReadAllText($configPath) } else { '' }
    $contents=Update-WarfareForgeCategory $contents 'engine' ([ordered]@{'I:streamingChannels'=$profileValues.streaming;'I:normalChannels'=$profileValues.normal})
    $regions=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($region in @($vendorEngine.regions)+@($vendorEngine.dimensions|ForEach-Object {$_.regions})) {
        if ($region -and $region.name -is [string] -and $region.name -match '^[A-Za-z0-9_. -]+$') { [void]$regions.Add($region.name) }
    }
    $volumes=[ordered]@{}
    foreach ($region in @($regions|Sort-Object)) {
        $key=if ($region -match '\s') { 'S:"'+$region+'"' } else { 'S:'+$region }
        $volumes[$key]=$profileValues.volume
    }
    $changes[$configPath]=Update-WarfareForgeCategory $contents 'volume' $volumes
    return $changes
}
function Add-WarfareAmbiencePack([string]$Contents) {
    $match=[regex]::Match($Contents,'(?m)^resourcePacks:([^\r\n]*)')
    $packs=@()
    if ($match.Success) {
        try { $decoded=ConvertFrom-Json -InputObject $match.Groups[1].Value.Trim() } catch { throw 'RV_AMBIENCE_CONFIG' }
        foreach ($pack in $decoded) { if ($pack -isnot [string]) { throw 'RV_AMBIENCE_CONFIG' }; $packs+=$pack }
    }
    if ('RV-Ambience' -cnotin $packs) { $packs+='RV-Ambience' }
    $line='resourcePacks:'+ (ConvertTo-Json -InputObject @($packs) -Compress)
    if ($match.Success) { return [regex]::Replace($Contents,'(?m)^resourcePacks:[^\r\n]*',[Text.RegularExpressions.MatchEvaluator]{param($m) $line}) }
    return $Contents.TrimEnd("`r","`n")+"`r`n"+$line+"`r`n"
}
