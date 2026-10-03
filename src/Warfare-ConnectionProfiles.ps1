function ConvertFrom-WarfareInvite {
    param([string]$Path,[string]$Json)
    if($Path){
        if(-not(Test-Path -LiteralPath $Path -PathType Leaf) -or (Get-Item -LiteralPath $Path).Length -gt 4096){throw 'invite_invalid'}
        try{$Json=[Text.UTF8Encoding]::new($false,$true).GetString([IO.File]::ReadAllBytes($Path))}catch{throw 'invite_invalid'}
    }
    if(-not $Json -or [Text.Encoding]::UTF8.GetByteCount($Json) -gt 4096){throw 'invite_invalid'}
    $text=$Json.TrimStart([char]0xfeff);$cursor=@{index=0}
    $skip={while($cursor.index -lt $text.Length -and $text[$cursor.index] -in @([char]32,[char]9,[char]10,[char]13)){$cursor.index++}}
    $readString={
        if($cursor.index -ge $text.Length -or $text[$cursor.index] -ne '"'){throw 'invite_invalid'}
        $start=$cursor.index;$cursor.index++
        while($cursor.index -lt $text.Length){
            $value=$text[$cursor.index]
            if([int]$value -lt 32){throw 'invite_invalid'}
            if($value -eq '\'){$cursor.index+=2;continue}
            $cursor.index++
            if($value -eq '"'){
                try{return [string](('{'+'"v":'+$text.Substring($start,$cursor.index-$start)+'}')|ConvertFrom-Json).v}catch{throw 'invite_invalid'}
            }
        }
        throw 'invite_invalid'
    }
    $allowed=@('schema','product','transport','target','port','version','label')
    $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    & $skip
    if($cursor.index -ge $text.Length -or $text[$cursor.index] -ne '{'){throw 'invite_invalid'}
    $cursor.index++;& $skip
    while($cursor.index -lt $text.Length -and $text[$cursor.index] -ne '}'){
        $key=& $readString
        if($key -cnotin $allowed -or -not $seen.Add($key)){throw 'invite_invalid'}
        & $skip
        if($cursor.index -ge $text.Length -or $text[$cursor.index] -ne ':'){throw 'invite_invalid'}
        $cursor.index++;& $skip
        if($cursor.index -ge $text.Length){throw 'invite_invalid'}
        if($text[$cursor.index] -eq '"'){$null=& $readString}else{
            $start=$cursor.index
            while($cursor.index -lt $text.Length -and $text[$cursor.index] -notin @([char]',',[char]'}',[char]32,[char]9,[char]10,[char]13)){$cursor.index++}
            if($text.Substring($start,$cursor.index-$start) -cnotmatch '^(?:-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[Ee][+-]?[0-9]+)?|true|false|null)$'){throw 'invite_invalid'}
        }
        & $skip
        if($cursor.index -lt $text.Length -and $text[$cursor.index] -eq ','){
            $cursor.index++;& $skip
            if($cursor.index -ge $text.Length -or $text[$cursor.index] -eq '}'){throw 'invite_invalid'}
        }elseif($cursor.index -ge $text.Length -or $text[$cursor.index] -ne '}'){throw 'invite_invalid'}
    }
    if($cursor.index -ge $text.Length -or $text[$cursor.index] -ne '}'){throw 'invite_invalid'}
    $cursor.index++;& $skip
    if($cursor.index -ne $text.Length -or @($allowed[0..5]|Where-Object {-not $seen.Contains($_)}).Count){throw 'invite_invalid'}
    try{$data=$text|ConvertFrom-Json}catch{throw 'invite_invalid'}
    if(($data.schema -isnot [int] -and $data.schema -isnot [long]) -or $data.schema -ne 1 -or $data.product -cne 'RV' -or $data.transport -cne 'porthole'){throw 'invite_invalid'}
    if(($data.port -isnot [int] -and $data.port -isnot [long]) -or $data.port -lt 1 -or $data.port -gt 65535){throw 'invite_invalid'}
    if($data.target -isnot [string] -or $data.target -cnotmatch '^(?:peer:[0-9]{17}|[A-Z0-9]{4,16})$'){throw 'invite_invalid'}
    if($data.version -isnot [string] -or $data.version.Length -gt 128 -or $data.version -cnotmatch '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$'){throw 'invite_invalid'}
    if($seen.Contains('label') -and ($data.label -isnot [string] -or $data.label.Length -gt 64 -or $data.label -match '[\x00-\x1f\x7f]|://|^[\/]|[A-Za-z]:[\/]')){throw 'invite_invalid'}
    $connection=ConvertTo-WarfareConnection 'porthole' $data.target ([string]$data.port)
    return [PSCustomObject]@{schema=1;product='RV';version=$data.version;label=$(if($data.label){$data.label}else{'RV'});connection=$connection}
}
