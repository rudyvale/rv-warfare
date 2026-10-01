$ErrorActionPreference='Stop'
$env:VM_SKIP_UPDATE_CHECK='1'
$workspace=Split-Path -Parent $PSScriptRoot
$InstallRoot=Join-Path $PSScriptRoot 'encoding-ui'
$PackageRoot=$null
$Language='ru'
$PreviewPath=''
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
$source=[IO.File]::ReadAllText((Join-Path $workspace 'src\Warfare-Launcher.ps1'))
$source=$source.Substring($source.IndexOf('$ErrorActionPreference'))
$source=$source.Replace('$PSScriptRoot',("'"+(Join-Path $workspace 'src')+"'"))
$source=$source.Replace('try { [void]$form.ShowDialog() } finally { $timer.Stop(); $timer.Dispose(); $form.Dispose() }','')
Invoke-Expression $source
$message='Распаковка сборки и Java 8…'
$probe=Join-Path $InstallRoot 'progress.ps1'
$child="[Console]::OutputEncoding=[Text.Encoding]::GetEncoding(866)`r`n. '"+(Join-Path $workspace 'src\Warfare-Connection.ps1')+"'`r`nWrite-Host '"+$message+"'`r`nStart-Sleep -Seconds 2`r`n"
[IO.File]::WriteAllText($probe,$child,[Text.UTF8Encoding]::new($true))
$tick=$timer.GetType().GetMethod('OnTick',[Reflection.BindingFlags]'Instance,NonPublic')
try {
    Start-Worker 'install' $probe @()
    $deadline=[DateTime]::UtcNow.AddSeconds(5)
    $seen=$false
    while([DateTime]::UtcNow -lt $deadline -and $script:process -and -not $script:process.HasExited){
        Start-Sleep -Milliseconds 80
        $tick.Invoke($timer,@([EventArgs]::Empty))|Out-Null
        if($status.Text -eq $message){$seen=$true;break}
    }
    if(-not $seen){throw ('Russian progress not shown: '+$status.Text)}
    'real GUI worker displays exact Russian progress: PASS'
} finally {
    if($script:process){[void]$script:process.WaitForExit(5000);$script:process.Dispose()}
    $timer.Dispose();$form.Dispose()
}
