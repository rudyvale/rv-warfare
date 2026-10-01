$ErrorActionPreference='Stop'
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'src\Warfare-Connection.ps1')
$cases=@(
    @('porthole',' abc1234 ','25565','ABC1234',25565),
    @('porthole','peer:10000000000000000','25570','peer:10000000000000000',25570),
    @('porthole','lobby:123456789012345678','25580','lobby:123456789012345678',25580),
    @('direct','Example.COM:25571','25565','example.com',25571),
    @('direct','192.168.1.23','25572','192.168.1.23',25572),
    @('direct','[::1]:25573','25565','::1',25573),
    @('direct','2001:db8::2','25574','2001:db8::2',25574)
)
foreach($case in $cases){
    $result=ConvertTo-WarfareConnection $case[0] $case[1] $case[2]
    if($result.connectionTarget -ne $case[3] -or $result.serverPort -ne $case[4]){throw ('Wrong connection: '+($case -join ', '))}
}
$invalid=@(
    @('porthole','','25565'),@('porthole','foo; calc','25565'),@('porthole','peer:0','25565'),
    @('porthole','lobby:18446744073709551616','25565'),@('direct','http://example.com','25565'),
    @('direct','example.com/x','25565'),@('direct','999.999.1.1','25565'),@('direct','a..example','25565'),
    @('direct','example.com','0'),@('direct','example.com:65536','25565'),@('other','abc','25565')
)
foreach($case in $invalid){$rejected=$false;try{ConvertTo-WarfareConnection $case[0] $case[1] $case[2]|Out-Null}catch{$rejected=$true};if(-not $rejected){throw ('Invalid connection accepted: '+($case -join ', '))}}
$defaults=[PSCustomObject]@{connectionMode='porthole';connectionTarget='DEFAULT';serverPort=25565}
$old=[PSCustomObject]@{nickname='Tester';language='ru';shareCode='USERCODE';host='127.0.0.1';port=25570;otherSetting='keep'}
$migrated=Get-WarfareConnection $old $defaults
if($migrated.connectionTarget -ne 'USERCODE' -or $migrated.serverPort -ne 25570){throw 'Legacy user choice lost'}
$updated=Set-WarfareConnection $old (ConvertTo-WarfareConnection 'direct' 'new.example:25580' 25565)
$read=Get-WarfareConnection $updated $defaults
if($read.connectionMode -ne 'direct' -or $read.connectionTarget -ne 'new.example' -or $read.serverPort -ne 25580 -or $updated.otherSetting -ne 'keep'){throw 'Updated choice lost'}
$fresh=Get-WarfareConnection $null
if($fresh.connectionTarget){throw 'Hardcoded default server'}
'7 valid targets, 11 invalid targets, migration, replacement and empty defaults: PASS'
