import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
import tkinter as tk
import uuid


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
import host_runtime
spec = importlib.util.spec_from_file_location('rv_host_native_onboarding', ROOT / 'host/warfare-launcher.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)
parser = argparse.ArgumentParser()
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--server-root', type=Path, required=True)
parser.add_argument('--missing-helper', action='store_true')
args = parser.parse_args()
production_before = host_runtime.server_status(args.server_root)
if production_before.get('state') != 'running' or not production_before.get('ready'):
    raise RuntimeError('This read-only status fixture needs the already-running production server')
root = ROOT / '.local/rv-1.1.0' / ('host-onboarding-native-' + uuid.uuid4().hex)
actual = root / 'actual-host'
actual.mkdir(parents=True)
for name in ('Join-Server.ps1', 'Launch-Warfare.ps1', 'host_runtime.py', 'porthole-status.py'):
    shutil.copy2(ROOT / 'host' / name, actual / name)
for name in ('Configure-Controller.ps1', 'Configure-FirstPlay.ps1', 'Warfare-Onboarding.ps1', 'Warfare-Connection.ps1', 'Warfare-Performance.ps1'):
    shutil.copy2(ROOT / 'src' / name, actual / name)
host_runtime.write_json(actual / 'server-state.json', production_before)
host_runtime.write_json(root / 'server-state.json', production_before)
fake_appdata = root / 'appdata'
game = fake_appdata / '.minecraft/versions/Warfare-1.12.2'
(game / 'mods').mkdir(parents=True)
(game / 'config').mkdir()
shutil.copy2(args.candidate, game / 'mods/mcheli.jar')
for name in ('Configure-Controller.ps1', 'Configure-FirstPlay.ps1', 'Warfare-Onboarding.ps1', 'Warfare-Connection.ps1'):
    if args.missing_helper and name == 'Configure-Controller.ps1':
        continue
    shutil.copy2(ROOT / 'src' / name, game / name)
profile = game / 'config/vm-controller.properties'
profile_bytes = b'enabled=true\r\nkind=radio\r\nkeyboardFlight=pro\r\nunknown=preserve\r\nroll.axis=3\r\n'
profile.write_bytes(profile_bytes)
legacy = game / 'Warfare-1.12.2.json'
legacy_bytes = b'{"id":"Warfare-1.12.2","unknown":"preserve"}\n'
legacy.write_bytes(legacy_bytes)
native_driver = r'''$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
[Windows.Forms.Application]::SetUnhandledExceptionMode([Windows.Forms.UnhandledExceptionMode]::ThrowException)
$global:rvHostNativeDriverState=[PSCustomObject]@{phase=0;deadline=[DateTime]::UtcNow.AddSeconds(45);root=$PSScriptRoot;driver=[Windows.Forms.Timer]::new()}
$self=Get-Process -Id $PID
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'driver-process.json'),(@{pid=$PID;started=$self.StartTime.ToUniversalTime().ToString('o');executable=$self.Path}|ConvertTo-Json -Compress))
function global:Fail-RVHostNativeDriver($Window,[string]$Reason){
    $global:rvHostNativeDriverState.driver.Stop()
    [IO.File]::WriteAllText((Join-Path $global:rvHostNativeDriverState.root 'native-result.json'),(@{actualRadioProbe=$false;nativeCancel=$false;error=$Reason}|ConvertTo-Json -Compress))
    try{@($Window.Controls.Find('setupCancel',$true))[0].PerformClick()}catch{$Window.Close()}
}
$global:rvHostNativeDriverState.driver.Interval=100
$global:rvHostNativeDriverState.driver.Add_Tick({
    $window=@([Windows.Forms.Application]::OpenForms|Where-Object Name -eq firstPlay)|Select-Object -First 1
    if(-not $window){return}
    try{
    $window.Opacity=0
    if([DateTime]::UtcNow -gt $global:rvHostNativeDriverState.deadline){Fail-RVHostNativeDriver $window 'native_deadline';return}
    if($global:rvHostNativeDriverState.phase -eq 0){
        @($window.Controls.Find('inputRadio',$true))[0].Checked=$true
        @($window.Controls.Find('setupNext',$true))[0].PerformClick()
        $global:rvHostNativeDriverState.phase=1
        return
    }
    if(@($window.Controls.Find('setupPage1',$true))[0].Visible -and @($window.Controls.Find('setupRescan',$true))[0].Enabled){
        $reports=@(Get-ChildItem -LiteralPath (Join-Path $env:APPDATA '.minecraft/versions/Warfare-1.12.2') -Filter '*.json' -Recurse -File|Where-Object {$_.Name -notin @('Warfare-1.12.2.json','warfare-settings.json')})
        $probe=$null
        foreach($file in $reports){try{$data=Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8|ConvertFrom-Json;if($data.schema -eq 1 -and $data.PSObject.Properties['devices']){$probe=$data;break}}catch{}}
        if(-not $probe){return}
        if($probe.outcome -eq 'error'){Fail-RVHostNativeDriver $window 'radio_probe_error';return}
        $bitmap=[Drawing.Bitmap]::new($window.Width,$window.Height)
        try{$window.DrawToBitmap($bitmap,[Drawing.Rectangle]::new(0,0,$window.Width,$window.Height));$bitmap.Save((Join-Path $global:rvHostNativeDriverState.root 'wizard.png'))}finally{$bitmap.Dispose()}
        [IO.File]::WriteAllText((Join-Path $global:rvHostNativeDriverState.root 'native-result.json'),'{"actualRadioProbe":true,"nativeCancel":true}')
        $global:rvHostNativeDriverState.driver.Stop()
        @($window.Controls.Find('setupCancel',$true))[0].PerformClick()
    }
    }catch{Fail-RVHostNativeDriver $window $_.Exception.Message}
})
$global:rvHostNativeDriverState.driver.Start()
& (Join-Path $PSScriptRoot 'actual-host/Join-Server.ps1')
exit $LASTEXITCODE
'''
if args.missing_helper:
    native_driver = native_driver.replace('AddSeconds(45)', 'AddSeconds(8)')
(root / 'Join-Server.ps1').write_text(native_driver, encoding='utf-8-sig')
original_appdata = os.environ.get('APPDATA')
original_skip = os.environ.get('VM_SKIP_UPDATE_CHECK')
os.environ['APPDATA'] = str(fake_appdata)
os.environ['VM_SKIP_UPDATE_CHECK'] = '1'
window = None
app = None
try:
    window = tk.Tk()
    window.withdraw()
    app = ui.Launcher(window, root, monitor=False)
    app.script = lambda name, timeout=180, arguments=(): ui.Launcher.script(app, name, timeout=55, arguments=arguments)
    app.server = production_before
    app.render()
    app.play_button.invoke()
    ticks = 0
    deadline = time.monotonic() + 60
    while app.client_job and time.monotonic() < deadline:
        window.update()
        ticks += 1
        time.sleep(0.02)
    if app.client_job:
        raise TimeoutError('Host first-play cancellation did not finish')
    native = json.loads((root / 'native-result.json').read_text())
    driver = json.loads((root / 'driver-process.json').read_text())
    owned_driver_exited = host_runtime.porthole.process_identity(driver['pid']) is None
    production_after = host_runtime.server_status(args.server_root)
    checks = {'nativeRadioProbe': native['actualRadioProbe'], 'nativeCancel': native['nativeCancel'], 'hostReturnedCancelled': app.status_key == 'cancelled', 'playEnabledAgain': app.play_button.cget('state') == 'normal', 'tkResponsiveWhileWizardOpen': ticks >= 10, 'profileBytesPreserved': profile.read_bytes() == profile_bytes, 'legacyProfilePreserved': legacy.read_bytes() == legacy_bytes, 'noGameLaunch': not (actual / 'client-state.json').exists(), 'ownedDriverExited': owned_driver_exited, 'sameProductionServer': production_before.get('pid') == production_after.get('pid') and production_before.get('processStartedAt') == production_after.get('processStartedAt') and production_after.get('ready') is True}
    if args.missing_helper:
        del checks['nativeRadioProbe']
        del checks['nativeCancel']
        checks['deadlineFailedStructurally'] = native.get('error') == 'native_deadline' and native['actualRadioProbe'] is False and native['nativeCancel'] is False
    report = {'passed': all(checks.values()), 'scenario': 'missing_helper_deadline' if args.missing_helper else 'native_radio_cancel', 'checks': checks, 'productionReadOnly': True, 'candidateSha256': hashlib.sha256(args.candidate.read_bytes()).hexdigest(), 'sourceSha256': {str(path.relative_to(actual)): hashlib.sha256(path.read_bytes()).hexdigest() for path in actual.iterdir() if path.suffix in ('.ps1', '.py')}, 'tkTicks': ticks, 'physicalDeviceTested': False}
    (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(root / 'report.json'), **report}, indent=2))
    if not report['passed']:
        raise AssertionError('Host first-play native cancellation failed')
finally:
    if app:
        app.close()
    elif window:
        window.destroy()
    for key, previous in (('APPDATA', original_appdata), ('VM_SKIP_UPDATE_CHECK', original_skip)):
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
