function Get-WarfareClientPreferences([string]$Root) {
    $values = @{schema='1';profile='balanced';language='en';hudHints='true';hitFeedback='true'}
    $path = Join-Path $Root 'config\rv-client.properties'
    if (Test-Path -LiteralPath $path) {
        foreach ($line in [IO.File]::ReadAllLines($path)) {
            $match = [regex]::Match($line, '^\s*(schema|profile|language|hudHints|hitFeedback)\s*[=:]\s*([^\s]+)\s*$')
            if ($match.Success) { $values[$match.Groups[1].Value] = $match.Groups[2].Value }
        }
    }
    if ($values.profile -notin @('low','balanced','quality')) { $values.profile='balanced' }
    if ($values.language -notin @('ru','en')) { $values.language='en' }
    return [PSCustomObject]@{schema=1;profile=$values.profile;language=$values.language;hudHints=($values.hudHints -ne 'false');hitFeedback=($values.hitFeedback -ne 'false')}
}
function Test-WarfareGameProcess([string]$CommandLine,[string]$Root) {
    $argument=[regex]::Match($CommandLine,'(?i)(?:^|\s)--gameDir\s+(?:"([^"\r\n]+)"|([^\s"]+))')
    if(-not $argument.Success){return $false}
    $path=if($argument.Groups[1].Success){$argument.Groups[1].Value}else{$argument.Groups[2].Value}
    if(-not [IO.Path]::IsPathRooted($path)){return $false}
    try { return [IO.Path]::GetFullPath($path).TrimEnd('\').Equals([IO.Path]::GetFullPath($Root).TrimEnd('\'),[StringComparison]::OrdinalIgnoreCase) } catch { return $false }
}
function Get-WarfareHardwareFacts {
    $ramMB = 0; $logicalProcessors = 0; $serverHeapMB = 0
    try { $ramMB = [int]([double](Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).TotalPhysicalMemory / 1MB) } catch { }
    try { $logicalProcessors = [int](@(Get-CimInstance Win32_Processor -ErrorAction Stop | Measure-Object NumberOfLogicalProcessors -Sum)[0].Sum) } catch { }
    try {
        foreach ($process in @(Get-CimInstance Win32_Process -Filter "Name='java.exe' OR Name='javaw.exe'" -ErrorAction Stop)) {
            if (-not (Test-WarfareServerCommand $process.CommandLine)) { continue }
            $heap = [regex]::Match($process.CommandLine, '(?i)(?:^|\s)-Xmx([0-9]+)([kmg])(?:\s|$)')
            if ($heap.Success) {
                $amount = [double]$heap.Groups[1].Value
                switch ($heap.Groups[2].Value.ToLowerInvariant()) { 'g' {$amount*=1024}; 'k' {$amount/=1024} }
                $serverHeapMB += [int]$amount
            }
        }
    } catch { }
    return [PSCustomObject]@{ramMB=$ramMB;logicalProcessors=$logicalProcessors;serverHeapMB=$serverHeapMB}
}
function Test-WarfareServerCommand([string]$CommandLine) {
    if ($CommandLine -match '(?i)(?:^|\s)(?:net\.minecraft\.server\.MinecraftServer|net\.minecraftforge\.fml\.relauncher\.ServerLaunchWrapper)(?:\s|$)') { return $true }
    $jar=[regex]::Match($CommandLine,'(?i)(?:^|\s)-jar\s+(?:"([^"\r\n]+)"|([^\s"]+))')
    if(-not $jar.Success){return $false}
    $path=if($jar.Groups[1].Success){$jar.Groups[1].Value}else{$jar.Groups[2].Value}
    if(-not [IO.Path]::IsPathRooted($path) -or -not (Test-Path -LiteralPath $path -PathType Leaf)){return $false}
    $archive=$null; $reader=$null
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive=[IO.Compression.ZipFile]::OpenRead($path)
        $entry=$archive.GetEntry('META-INF/MANIFEST.MF')
        if(-not $entry -or $entry.Length -gt 65536){return $false}
        $reader=[IO.StreamReader]::new($entry.Open())
        return $reader.ReadToEnd() -match '(?im)^Main-Class:\s*(?:net\.minecraft\.server\.MinecraftServer|net\.minecraftforge\.fml\.relauncher\.ServerLaunchWrapper)\s*$'
    }catch{return $false}finally{if($reader){$reader.Dispose()};if($archive){$archive.Dispose()}}
}
function Get-WarfareInitialProfile($Facts) {
    if (-not $Facts) { $Facts = Get-WarfareHardwareFacts }
    if (($Facts.ramMB -gt 0 -and $Facts.ramMB -le 8192) -or ($Facts.logicalProcessors -gt 0 -and $Facts.logicalProcessors -le 2)) { return 'low' }
    return 'balanced'
}
function Get-WarfareHeapMB($Settings, $Facts) {
    if (-not $Facts) { $Facts = Get-WarfareHardwareFacts }
    $override = 0
    if ($Settings -and $Settings.PSObject.Properties['memoryMB']) {
        if (-not [int]::TryParse([string]$Settings.memoryMB, [ref]$override) -or ($override -ne 0 -and ($override -lt 2048 -or $override -gt 8192))) { throw 'RV_MEMORY_INVALID' }
    }
    if ($Facts.ramMB -le 0) { if ($override) { return $override }; return 3072 }
    $budget = [int]($Facts.ramMB - 1536 - $Facts.serverHeapMB)
    if ($budget -lt 2048) { throw 'RV_MEMORY_LOW' }
    if ($override) {
        if ($override -gt $budget) { throw 'RV_MEMORY_BUDGET' }
        return $override
    }
    $target = [Math]::Min(4096, [Math]::Min($budget, [Math]::Max(2048, [int]($Facts.ramMB * 0.45))))
    return [int]([Math]::Floor($target / 256) * 256)
}
function Update-WarfarePreferenceLines([string]$Contents, $Values, [string]$Separator) {
    $lines = [Collections.Generic.List[string]]::new()
    $seen = @{}
    if ($Contents) {
        foreach ($line in [regex]::Split($Contents.TrimEnd("`r","`n"), '\r?\n')) {
            $match = [regex]::Match($line, '^\s*([^#!\s:=]+)\s*[:=]')
            $key = if ($match.Success) { $match.Groups[1].Value } else { '' }
            if ($key -and $Values.Keys -ccontains $key) {
                if (-not $seen.ContainsKey($key)) { $lines.Add($key + $Separator + $Values[$key]); $seen[$key]=$true }
            } else { $lines.Add($line) }
        }
    }
    foreach ($key in $Values.Keys) { if (-not $seen.ContainsKey($key)) { $lines.Add($key + $Separator + $Values[$key]) } }
    return ($lines -join "`r`n") + "`r`n"
}
function Set-WarfareEffectProperty($Document,[string[]]$Path,$Value) {
    $node=$Document
    for($i=0;$i -lt $Path.Count;$i++){
        if($node -isnot [PSCustomObject]){throw 'RV_EFFECTS_CONFIG'}
        $name=$Path[$i]
        $exact=@($node.PSObject.Properties|Where-Object {$_.Name -ceq $name})
        if(-not $exact.Count -and $node.PSObject.Properties[$name]){throw 'RV_EFFECTS_CONFIG'}
        if($i -eq $Path.Count-1){$node|Add-Member NoteProperty $name $Value -Force;return}
        if(-not $exact.Count){$node|Add-Member NoteProperty $name ([PSCustomObject]@{})}
        $node=$node.$name
    }
}
function Set-WarfarePerformanceProfile {
    param([string]$Root, [ValidateSet('low','balanced','quality')][string]$Profile,
        [ValidateSet('ru','en')][string]$Language, [bool]$HudHints=$true, [bool]$HitFeedback=$true,
        [switch]$ApplyGraphics, [switch]$Installer, [switch]$LanguageOnly)
    $Root = [IO.Path]::GetFullPath($Root)
    New-Item -ItemType Directory -Path $Root -Force | Out-Null
    $guard = $null
    try {
        if (-not $Installer) {
            try { $guard = [IO.File]::Open((Join-Path $Root '.install.lock'), 'OpenOrCreate', 'ReadWrite', 'None') } catch { throw 'RV_SETTINGS_BUSY' }
            $active = @(Get-CimInstance Win32_Process -Filter "Name='java.exe' OR Name='javaw.exe'" -ErrorAction SilentlyContinue | Where-Object { Test-WarfareGameProcess $_.CommandLine $Root })
            if ($active.Count -and -not $LanguageOnly) { throw 'RV_SETTINGS_RUNNING' }
        }
        $changes = [ordered]@{}
        $preferences = Join-Path $Root 'config\rv-client.properties'
        $contents = if (Test-Path -LiteralPath $preferences) { [IO.File]::ReadAllText($preferences) } else { '' }
        $values = if ($LanguageOnly) { [ordered]@{language=$Language} } else { [ordered]@{schema='1';profile=$Profile;language=$Language;hudHints=$HudHints.ToString().ToLowerInvariant();hitFeedback=$HitFeedback.ToString().ToLowerInvariant()} }
        $changes[$preferences] = Update-WarfarePreferenceLines $contents $values '='
        if ($ApplyGraphics) {
            $profiles = @{
                low=[ordered]@{renderDistance='4';fancyGraphics='false';particles='2';ao='0';mipmapLevels='0';renderClouds='false'}
                balanced=[ordered]@{renderDistance='8';fancyGraphics='false';particles='1';ao='1';mipmapLevels='2';renderClouds='fast'}
                quality=[ordered]@{renderDistance='12';fancyGraphics='true';particles='0';ao='2';mipmapLevels='4';renderClouds='true'}
            }
            $options = Join-Path $Root 'options.txt'
            $contents = if (Test-Path -LiteralPath $options) { [IO.File]::ReadAllText($options) } else { '' }
            $changes[$options] = Update-WarfarePreferenceLines $contents $profiles[$Profile] ':'
            $shaders = Join-Path $Root 'optionsshaders.txt'
            $contents = if (Test-Path -LiteralPath $shaders) { [IO.File]::ReadAllText($shaders) } else { '' }
            $changes[$shaders] = Update-WarfarePreferenceLines $contents ([ordered]@{shaderPack='OFF'}) '='
            $effectsPath=Join-Path $Root 'config\enhancedvisuals-client.json'
            if(Test-Path -LiteralPath $effectsPath -PathType Leaf){
                try{$effects=[IO.File]::ReadAllText($effectsPath)|ConvertFrom-Json}catch{throw 'RV_EFFECTS_CONFIG'}
                $effectValues=[ordered]@{
                    'handlers.explosion.blur.disabled'=$true
                    'handlers.splash.blur.disabled'=$true
                    'handlers.heartbeat.blur.disabled'=$true
                    'handlers.explosion.dust.disabled'=($Profile -eq 'low')
                    'handlers.damage.opacity'=$(if($Profile -eq 'low'){0.2}else{0.35})
                    'handlers.heartbeat.lowhealth.opacity'=$(if($Profile -eq 'low'){0.2}else{0.25})
                }
                foreach($key in $effectValues.Keys){Set-WarfareEffectProperty $effects $key.Split('.') $effectValues[$key]}
                $changes[$effectsPath]=($effects|ConvertTo-Json -Depth 64)+"`r`n"
            }
        }
        $backupRoot = Join-Path $Root ('backups\profile-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N'))
        $written = [Collections.Generic.List[object]]::new()
        try {
            foreach ($path in $changes.Keys) {
                $exists = Test-Path -LiteralPath $path
                $saved = Join-Path $backupRoot $path.Substring($Root.TrimEnd('\').Length+1)
                if ($exists) { New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null; Copy-Item -LiteralPath $path -Destination $saved }
                New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
                $temp = $path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
                try {
                    [IO.File]::WriteAllText($temp, $changes[$path], [Text.UTF8Encoding]::new($false))
                    $written.Add([PSCustomObject]@{path=$path;saved=$saved;existed=$exists})
                    Move-Item -LiteralPath $temp -Destination $path -Force
                } finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp } }
            }
        } catch {
            for ($index=$written.Count-1; $index -ge 0; $index--) {
                $item = $written[$index]
                if ($item.existed) {
                    $unchanged=(Test-Path -LiteralPath $item.path -PathType Leaf) -and [Convert]::ToBase64String([IO.File]::ReadAllBytes($item.path)) -ceq [Convert]::ToBase64String([IO.File]::ReadAllBytes($item.saved))
                    if(-not $unchanged){Copy-Item -LiteralPath $item.saved -Destination $item.path -Force}
                }
                elseif (Test-Path -LiteralPath $item.path) { Remove-Item -LiteralPath $item.path }
            }
            throw
        }
    } finally { if ($guard) { $guard.Dispose() } }
}
function Get-WarfarePreferenceError([string]$Message, [string]$Language) {
    $ru = $Language -eq 'ru'
    switch ($Message) {
        'RV_SETTINGS_BUSY' { if($ru){return 'Дождись окончания установки или запуска.'}; return 'Wait for the installation or launch to finish.' }
        'RV_SETTINGS_RUNNING' { if($ru){return 'Закрой игру перед применением настроек.'}; return 'Close the game before applying settings.' }
        'RV_MEMORY_INVALID' { if($ru){return 'Память: авто или от 2048 до 8192 МБ. Проверь настройки.'}; return 'Memory must be Auto or 2048 to 8192 MB. Check Settings.' }
        'RV_MEMORY_LOW' { if($ru){return 'Недостаточно ОЗУ для игры. Если на этом ПК запущен сервер, закрой его или уменьши его память.'}; return 'Not enough system memory for the game. If a local server is running, close it or reduce its memory allocation.' }
        'RV_MEMORY_BUDGET' { if($ru){return 'Выбрано слишком много памяти для игры. Поставь «Авто» или уменьши значение.'}; return 'The selected game memory exceeds the available budget. Choose Auto or reduce it.' }
        'RV_EFFECTS_CONFIG' { if($ru){return 'Проверь файл config/enhancedvisuals-client.json. Настройки не применены.'}; return 'Check config/enhancedvisuals-client.json. Settings were not applied.' }
        default { return $Message }
    }
}
