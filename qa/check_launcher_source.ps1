$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$sources = @(Get-ChildItem -LiteralPath (Join-Path $workspace 'src') -Filter '*.ps1' -File)
if ($sources.Count -eq 0) { throw 'Launcher sources are missing' }
foreach ($source in $sources) {
    $tokens = $null
    $parseErrors = $null
    $tree = [System.Management.Automation.Language.Parser]::ParseFile($source.FullName, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count) {
        throw ($source.Name + ': ' + (($parseErrors | ForEach-Object { $_.Message }) -join '; '))
    }
    $commands = @($tree.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] }, $true))
    foreach ($command in $commands) {
        if ($command.GetCommandName() -in @('Invoke-Expression', 'iex')) {
            throw ($source.Name + ': expression execution is not allowed')
        }
    }
}
Write-Output ('PowerShell source syntax: PASS (' + $sources.Count + ' files); GUI behavior requires separate native verification')
