param([Parameter(Mandatory=$true)][string]$Root, [string]$CurrentVersion = '0.0.0', [switch]$Download)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Warfare-Updates.ps1')
if (-not $Download -and -not (Get-VmAutoCheck $Root)) { exit 0 }
$lock = $null
$partial = $null
try {
    $directory = Join-Path ([IO.Path]::GetFullPath($Root)) '.updates'
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $statusPath = Join-Path $directory 'status.json'
    try { $lock = [IO.File]::Open((Join-Path $directory 'check.lock'), 'OpenOrCreate', 'ReadWrite', 'None') } catch { if ($Download) { throw 'Update check is already running. Try again.' }; exit 0 }
    $release = ConvertTo-VmRelease (Get-VmRelease) $CurrentVersion
    if (-not $Download -and $release.state -eq 'available' -and (Test-Path -LiteralPath $statusPath)) {
        try {
            $previous = Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($previous.state -eq 'downloaded' -and $previous.version -eq $release.version -and $previous.sha256 -eq $release.sha256 -and (Test-Path -LiteralPath (Join-Path $previous.packageRoot 'Install-Warfare.ps1'))) {
                $release.state = 'downloaded'
                $release.packageRoot = $previous.packageRoot
            }
        } catch { }
    }
    Write-VmJson $statusPath $release
    if ($Download -and $release.state -eq 'available') {
        $partial = Join-Path $directory ([Guid]::NewGuid().ToString('N') + '.zip.part')
        $request = [Net.HttpWebRequest]::Create($release.url)
        $request.UserAgent = 'VM-Warfare-Update'
        $request.Timeout = 15000
        $request.ReadWriteTimeout = 20000
        $response = $request.GetResponse()
        try {
            $stream = $response.GetResponseStream()
            $output = [IO.File]::Create($partial)
            try {
                $buffer = New-Object byte[] 131072
                $total = [long]0
                $deadline = [DateTime]::UtcNow.AddMinutes(10)
                while (($count = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $total += $count
                    if ($total -gt $release.size -or [DateTime]::UtcNow -gt $deadline) { throw 'Download exceeded its limit.' }
                    $output.Write($buffer, 0, $count)
                }
                if ($total -ne $release.size) { throw 'Download is incomplete.' }
            } finally { $output.Dispose(); $stream.Dispose() }
        } finally { $response.Dispose() }
        Test-VmPackageHash $partial $release.sha256
        $destination = Join-Path $directory ('packages\' + $release.tag + '-' + [Guid]::NewGuid().ToString('N'))
        $package = Expand-VmPackage $partial $destination $release.version
        $release.state = 'downloaded'
        $release.packageRoot = $package
        Write-VmJson $statusPath $release
    }
} catch {
    if ($statusPath) {
        try { Write-VmJson (Join-Path $directory 'last-error.json') @{state='unavailable';checkedAt=[DateTime]::UtcNow.ToString('o');reason=$_.Exception.GetType().Name} } catch { }
    }
    if ($Download) { Write-Error 'Update could not be downloaded or verified. Your current installation is unchanged.'; exit 1 }
} finally {
    if ($partial -and (Test-Path -LiteralPath $partial)) { Remove-Item -LiteralPath $partial -Force }
    if ($lock) { $lock.Dispose() }
}
