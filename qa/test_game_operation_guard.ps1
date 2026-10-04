$ErrorActionPreference='Stop'
$rootPath=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$helperPath=Join-Path $rootPath 'src\Warfare-Performance.ps1'
$fixture=Join-Path $env:TEMP ('rv-game-operation-' + [Guid]::NewGuid().ToString('N'))
$gameRoot=Join-Path $fixture 'client root'
$readyPath=Join-Path $fixture 'java-ready'
$releasePath=Join-Path $fixture 'java-release'
$fakeJavaPath=Join-Path $fixture 'java.exe'
$sentinelPath=Join-Path $gameRoot 'saves\keep.dat'
$fakeJava=$null
$child=$null
$held=$null
function Wait-File([string]$Path,[int]$TimeoutMilliseconds=5000) {
    $timer=[Diagnostics.Stopwatch]::StartNew()
    while(-not(Test-Path -LiteralPath $Path)){
        if($timer.ElapsedMilliseconds -ge $TimeoutMilliseconds){throw ('Timed out waiting for ' + $Path)}
        Start-Sleep -Milliseconds 20
    }
    $timer.Stop()
}
function Start-FakeJava([string[]]$Arguments,[string]$Ready,[string]$Release) {
    $info=[Diagnostics.ProcessStartInfo]::new()
    $info.FileName=$fakeJavaPath
    $info.Arguments=$Arguments -join ' '
    $info.UseShellExecute=$false
    $info.CreateNoWindow=$true
    $info.WindowStyle='Hidden'
    $info.EnvironmentVariables['RV_TEST_READY']=$Ready
    $info.EnvironmentVariables['RV_TEST_RELEASE']=$Release
    return [Diagnostics.Process]::Start($info)
}
function Stop-OwnedProcess($Process,[string]$Release) {
    if($Process -and -not $Process.HasExited){[IO.File]::WriteAllText($Release,'release');if(-not $Process.WaitForExit(5000)){$Process.Kill();[void]$Process.WaitForExit(3000)}}
    if($Process){$Process.Dispose()}
}
function Start-GuardChild([string]$Marker,[string]$ResultPath) {
    $childPath=Join-Path $fixture 'guard-child.ps1'
    $childSource=@'
param([string]$Helper,[string]$Root,[string]$Marker,[string]$ResultPath)
$ErrorActionPreference='Stop'
. $Helper
$script:guardQueries=0
function Get-CimInstance {
    param($ClassName,$Filter,$ErrorAction)
    $script:guardQueries++
    if($script:guardQueries -eq 1){[IO.File]::WriteAllText($Marker,'checked');return @()}
    return @(Get-WmiObject -Class $ClassName -Filter $Filter -ErrorAction Stop | Select-Object -Property CommandLine)
}
$lease=$null
$outcome=try{$lease=Enter-WarfareClientOperation $Root 5000;'acquired'}catch{$_.Exception.Message}
if($lease){Exit-WarfareClientOperation $lease}
[IO.File]::WriteAllText($ResultPath,$outcome)
'@
    [IO.File]::WriteAllText($childPath,$childSource,[Text.UTF8Encoding]::new($false))
    $quote={param([string]$Value) '"'+$Value.Replace('"','\"')+'"'}
    $args=@('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',(& $quote $childPath),(& $quote $helperPath),(& $quote $gameRoot),(& $quote $Marker),(& $quote $ResultPath)) -join ' '
    $info=[Diagnostics.ProcessStartInfo]::new()
    $info.FileName=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $info.Arguments=$args
    $info.UseShellExecute=$false
    $info.CreateNoWindow=$true
    $info.WindowStyle='Hidden'
    return [Diagnostics.Process]::Start($info)
}
try {
    [void][IO.Directory]::CreateDirectory((Split-Path -Parent $sentinelPath))
    [IO.File]::WriteAllText($sentinelPath,'world fixture')
    [IO.File]::WriteAllText((Join-Path $gameRoot 'warfare-settings.json'),'settings fixture')
    $sentinelHash=(Get-FileHash -LiteralPath $sentinelPath).Hash
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Threading;
public class FixtureJava {
    public static int Main(string[] args) {
        File.WriteAllText(Environment.GetEnvironmentVariable("RV_TEST_READY"), "ready");
        string release = Environment.GetEnvironmentVariable("RV_TEST_RELEASE");
        while (!File.Exists(release)) Thread.Sleep(20);
        return 0;
    }
}
'@ -OutputAssembly $fakeJavaPath -OutputType ConsoleApplication
    . $helperPath
    $runspace=[Management.Automation.PowerShell]::Create()
    $runspaceLease=$null
    try {
        [void]$runspace.AddScript('param($helper,$root);. $helper;Enter-WarfareClientOperation $root 3000')
        [void]$runspace.AddArgument($helperPath)
        [void]$runspace.AddArgument($gameRoot)
        $async=$runspace.BeginInvoke()
        $timer=[Diagnostics.Stopwatch]::StartNew()
        while(-not $async.IsCompleted){if($timer.ElapsedMilliseconds -gt 5000){throw 'The asynchronous GUI preflight timed out.'};Start-Sleep -Milliseconds 20}
        $timer.Stop()
        $asyncResult=@($runspace.EndInvoke($async))
        if($runspace.Streams.Error.Count -gt 0 -or $asyncResult.Count -ne 1){throw 'The asynchronous GUI preflight failed.'}
        $runspaceLease=$asyncResult[0]
        if($runspaceLease -isnot [IO.FileStream]){throw 'The asynchronous GUI preflight did not return a native lock lease.'}
        $failure=''
        try{$null=Enter-WarfareClientOperation $gameRoot 0}catch{$failure=$_.Exception.Message}
        if($failure -ne 'RV_OPERATION_BUSY'){throw 'The asynchronous GUI preflight did not retain the shared lock.'}
    } finally {
        if($runspaceLease){Exit-WarfareClientOperation $runspaceLease}
        $runspace.Dispose()
    }
    $probe=Enter-WarfareClientOperation $gameRoot 0
    Exit-WarfareClientOperation $probe
    Remove-Item -LiteralPath (Join-Path $gameRoot '.install.lock') -Force
    $fakeJava=Start-FakeJava @('--gameDir',('"'+$gameRoot+'"'),'--username','Fixture') $readyPath $releasePath
    Wait-File $readyPath
    $failure=''
    try{$null=Enter-WarfareClientOperation $gameRoot 0}catch{$failure=$_.Exception.Message}
    if($failure -ne 'RV_GAME_RUNNING'){throw ('Expected RV_GAME_RUNNING, got ' + $failure)}
    if(Test-Path -LiteralPath (Join-Path $gameRoot '.install.lock')){throw 'The active-client rejection created the operation lock.'}
    if((Get-FileHash -LiteralPath $sentinelPath).Hash -ne $sentinelHash -or [IO.File]::ReadAllText((Join-Path $gameRoot 'warfare-settings.json')) -ne 'settings fixture'){throw 'The active-client rejection modified fixture data.'}
    Stop-OwnedProcess $fakeJava $releasePath;$fakeJava=$null
    Remove-Item -LiteralPath $readyPath,$releasePath -Force -ErrorAction SilentlyContinue
    $held=Enter-WarfareClientOperation $gameRoot 0
    $failure=''
    try{$null=Enter-WarfareClientOperation $gameRoot 0}catch{$failure=$_.Exception.Message}
    if($failure -ne 'RV_OPERATION_BUSY'){throw ('Expected RV_OPERATION_BUSY, got ' + $failure)}
    $marker=Join-Path $fixture 'wait-query'
    $resultPath=Join-Path $fixture 'wait-result'
    $child=Start-GuardChild $marker $resultPath
    Wait-File $marker
    Start-Sleep -Milliseconds 200
    if($child.HasExited -or (Test-Path -LiteralPath $resultPath)){throw 'The waiting operation did not wait for the held lock.'}
    Exit-WarfareClientOperation $held;$held=$null
    if(-not $child.WaitForExit(7000)){throw 'The waiting operation did not finish after lock release.'}
    if([IO.File]::ReadAllText($resultPath) -ne 'acquired'){throw 'The operation did not acquire the released lock.'}
    $child.Dispose();$child=$null
    Remove-Item -LiteralPath $marker,$resultPath -Force
    $held=Enter-WarfareClientOperation $gameRoot 0
    $marker=Join-Path $fixture 'race-query'
    $resultPath=Join-Path $fixture 'race-result'
    $child=Start-GuardChild $marker $resultPath
    Wait-File $marker
    Start-Sleep -Milliseconds 200
    if($child.HasExited -or (Test-Path -LiteralPath $resultPath)){throw 'The launch preflight did not wait on the held lock.'}
    $readyPath=Join-Path $fixture 'race-java-ready'
    $releasePath=Join-Path $fixture 'race-java-release'
    $fakeJava=Start-FakeJava @('--gameDir',('"'+$gameRoot+'"'),'--username','Fixture') $readyPath $releasePath
    Wait-File $readyPath
    Exit-WarfareClientOperation $held;$held=$null
    if(-not $child.WaitForExit(7000)){throw 'The operation did not finish after a client appeared.'}
    if([IO.File]::ReadAllText($resultPath) -ne 'RV_GAME_RUNNING'){throw 'The under-lock recheck did not reject the newly started client.'}
    $child.Dispose();$child=$null
    Stop-OwnedProcess $fakeJava $releasePath;$fakeJava=$null
    Remove-Item -LiteralPath $marker,$resultPath -Force
    $readyPath=Join-Path $fixture 'server-ready'
    $releasePath=Join-Path $fixture 'server-release'
    $fakeJava=Start-FakeJava @('-Xmx4G','-jar','server.jar') $readyPath $releasePath
    Wait-File $readyPath
    $held=Enter-WarfareClientOperation $gameRoot 0
    Exit-WarfareClientOperation $held;$held=$null
    Stop-OwnedProcess $fakeJava $releasePath;$fakeJava=$null
    if((Get-FileHash -LiteralPath $sentinelPath).Hash -ne $sentinelHash){throw 'The guard modified the fixture world.'}
    Write-Output '5 game operation guard scenarios passed'
} finally {
    if($held){Exit-WarfareClientOperation $held}
    if($child -and -not $child.HasExited){$child.Kill();[void]$child.WaitForExit(3000)}
    if($child){$child.Dispose()}
    if($fakeJava){Stop-OwnedProcess $fakeJava $releasePath}
    if(Test-Path -LiteralPath $fixture){Remove-Item -LiteralPath $fixture -Recurse -Force -ErrorAction SilentlyContinue}
}
