param([int]$LocalPort,[string]$Nickname)
$ErrorActionPreference = 'Stop'
try {
    if ($LocalPort -lt 1 -or $LocalPort -gt 65535 -or $Nickname -notmatch '^[A-Za-z0-9_]{3,16}$') { throw 'Invalid owner request.' }
    $env:PSModulePath = (Join-Path $PSHOME 'Modules') + ';' + $env:PSModulePath
    $policy = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'vm-owner.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Nickname -cne $policy.nickname) { throw 'Owner mismatch.' }
    $connections = @(Get-NetTCPConnection -State Established -LocalPort $LocalPort -RemotePort $policy.serverPort -ErrorAction Stop | Where-Object { $_.LocalAddress -in @('127.0.0.1','::1') -and $_.RemoteAddress -in @('127.0.0.1','::1') })
    if ($connections.Count -ne 1) { throw 'Owner connection not found.' }
    $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $connections[0].OwningProcess)
    if (-not $process -or $process.Name -notin @('java.exe','javaw.exe') -or $process.CommandLine -notmatch 'net\.minecraft\.launchwrapper\.Launch') { throw 'Not a local Minecraft client.' }
    $nameMatch = [regex]::Match($process.CommandLine, '(?:^|\s)--username\s+(?:"([^"]+)"|(\S+))')
    $gameMatch = [regex]::Match($process.CommandLine, '(?:^|\s)--gameDir\s+(?:"([^"]+)"|(\S+))')
    $name = if ($nameMatch.Groups[1].Success) { $nameMatch.Groups[1].Value } else { $nameMatch.Groups[2].Value }
    $game = if ($gameMatch.Groups[1].Success) { $gameMatch.Groups[1].Value } else { $gameMatch.Groups[2].Value }
    if (-not $nameMatch.Success -or -not $gameMatch.Success -or $name -cne $policy.nickname) { throw 'Client identity mismatch.' }
    $resolvedGame = [IO.Path]::GetFullPath($game).TrimEnd('\')
    $allowed = @($policy.allowedGameDirs | Where-Object { [IO.Path]::GetFullPath([string]$_).TrimEnd('\') -eq $resolvedGame })
    if ($allowed.Count -eq 0) { throw 'Client directory is not trusted.' }
    Write-Output 'true'
} catch {
    Write-Output 'false'
}
