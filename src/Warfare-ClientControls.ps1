function Test-WarfareKeyboardDefaultsReady([string]$Root) {
    $path=Join-Path $Root 'config/vm-controller.properties'
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){return $true}
    if((Get-Item -LiteralPath $path).Length -gt 262144){throw 'control_profile_invalid'}
    $values=@{enabled='false';keyboardFlight='easy'}
    foreach($line in [IO.File]::ReadAllLines($path)){
        if($line -cmatch '^\s*(enabled|keyboardFlight)\s*[=:]\s*(.*?)\s*$'){$values[$Matches[1]]=$Matches[2]}
    }
    return $values.enabled -ine 'true' -and $values.keyboardFlight -ceq 'easy'
}
function Add-WarfareMissingOptionDefaults {
    param([string]$Root,[Collections.IDictionary]$Defaults)
    $rootPath=[IO.Path]::GetFullPath($Root).TrimEnd('\')
    $path=Join-Path $rootPath 'options.txt'
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){return [PSCustomObject]@{changed=$false;state='missing_options';addedKeys=@()}}
    $current=$path
    while($current){
        if((Test-Path -LiteralPath $current) -and ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'control_path_invalid'}
        $current=[IO.Path]::GetDirectoryName($current)
    }
    if((Get-Item -LiteralPath $path).Length -gt 1048576){throw 'control_options_invalid'}
    $guard=$null;$temporary=''
    try{
        try{$guard=[IO.File]::Open((Join-Path $rootPath '.controls.lock'),'OpenOrCreate','ReadWrite','None')}catch{throw 'control_busy'}
        $original=[IO.File]::ReadAllBytes($path)
        $text=[Text.UTF8Encoding]::new($false,$true).GetString($original).TrimStart([char]0xfeff)
        $added=[Collections.Generic.List[string]]::new()
        foreach($entry in $Defaults.GetEnumerator()){
            $value=0
            if($entry.Key -isnot [string] -or $entry.Key -cnotmatch '^key_[A-Za-z0-9_.-]{1,96}$' -or -not[int]::TryParse([string]$entry.Value,[ref]$value) -or $value -lt -100 -or $value -gt 255){throw 'control_default_invalid'}
            if(-not[regex]::IsMatch($text,'(?m)^'+[regex]::Escape($entry.Key)+':')){$added.Add($entry.Key+':'+$value.ToString([Globalization.CultureInfo]::InvariantCulture))}
        }
        if(-not $added.Count){return [PSCustomObject]@{changed=$false;state='preserved';addedKeys=@()}}
        $newline=if($text.Contains("`r`n")){"`r`n"}else{"`n"}
        $prefix=if($original.Length -eq 0 -or $original[$original.Length-1] -in @(10,13)){''}else{$newline}
        $suffix=[Text.UTF8Encoding]::new($false).GetBytes($prefix+($added -join $newline)+$newline)
        $bytes=New-Object byte[] ($original.Length+$suffix.Length)
        [Array]::Copy($original,0,$bytes,0,$original.Length);[Array]::Copy($suffix,0,$bytes,$original.Length,$suffix.Length)
        $temporary=$path+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
        [IO.File]::WriteAllBytes($temporary,$bytes)
        if([Convert]::ToBase64String([IO.File]::ReadAllBytes($path)) -cne [Convert]::ToBase64String($original)){throw 'control_changed'}
        Move-Item -LiteralPath $temporary -Destination $path -Force
        return [PSCustomObject]@{changed=$true;state='added_missing';addedKeys=@($added|ForEach-Object {$_.Split(':')[0]});originalBytesPreserved=$true}
    }finally{
        if($temporary -and (Test-Path -LiteralPath $temporary)){Remove-Item -LiteralPath $temporary -Force}
        if($guard){$guard.Dispose()}
    }
}
function Initialize-WarfareClientControls([string]$Root,[string]$ReleasePath) {
    if(-not $ReleasePath){$ReleasePath=Join-Path $Root 'release.json'}
    $defaults=[ordered]@{}
    if(Test-Path -LiteralPath $ReleasePath -PathType Leaf){
        try{$release=[IO.File]::ReadAllText($ReleasePath)|ConvertFrom-Json}catch{throw 'connection_package'}
        if($release.clientRequiredMods -and $release.clientRequiredMods.PSObject.Properties['modularwarfare']){$defaults['key_Flashlight']=64}
    }
    if(-not $defaults.Count){return [PSCustomObject]@{changed=$false;state='no_managed_bindings';addedKeys=@()}}
    return Add-WarfareMissingOptionDefaults -Root $Root -Defaults $defaults
}
