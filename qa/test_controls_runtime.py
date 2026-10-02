import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile
import argparse

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--client',action='store_true')
parser.add_argument('--gallery',action='store_true')
parser.add_argument('--apache-audio',action='store_true')
parser.add_argument('--wing-input',action='store_true')
parser.add_argument('--wing',choices=['geran','fp1'])
parser.add_argument('--comfort-mods',type=Path)
parser.add_argument('--comfort-config',type=Path)
parser.add_argument('--guide',type=Path)
parser.add_argument('--legacy-addon',type=Path)
parser.add_argument('--legacy-config',type=Path)
parser.add_argument('--missing-addon-meta',action='store_true')
parser.add_argument('--performance',choices=['low','balanced','quality'])
parser.add_argument('--world',type=Path)
parser.add_argument('--origin',default='0,4,0')
parser.add_argument('--shader',default='OFF')
parser.add_argument('--game',type=Path,default=Path(os.environ.get('RV_GAME_ROOT',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Warfare-1.12.2'))))
parser.add_argument('--compiler',type=Path,default=Path(os.environ.get('RV_ECJ_JAR',str(root/'.local/tools/ecj-4.6.1.jar'))))
parser.add_argument('--server-base',type=Path,default=Path(os.environ.get('RV_SERVER_BASE',str(root/'.local/server-base'))))
parser.add_argument('--audio',type=Path,default=Path(os.environ.get('RV_COMBAT_AUDIO',str(root/'.local/controls/audio/Warfare-Combat-Audio.zip'))))
parser.add_argument('--work',type=Path,default=root/'.local/controls')
options=parser.parse_args()
if options.gallery or options.wing_input or options.apache_audio:options.client=True

work=options.work.resolve()
work.mkdir(parents=True,exist_ok=True)
game=options.game
original=options.server_base
server=work/'server'
server.mkdir(exist_ok=True)
test_world=(server/'ControlsTest').resolve()
assert test_world.parent==server.resolve() and test_world.is_relative_to(work.resolve())
if test_world.exists():shutil.rmtree(test_world)
if options.world:shutil.copytree(options.world.resolve(strict=True),test_world)
def link(src,dst):
    if not Path(dst).exists():
        try:os.link(src,dst)
        except OSError:shutil.copy2(src,dst)
    return dst
def comfort(destination):
    if not options.comfort_mods:return
    manifest=json.loads((options.comfort_mods/'verified-mods.json').read_text(encoding='utf-8-sig'))
    for item in manifest['mods']:
        source=options.comfort_mods/item['file']
        assert hashlib.sha256(source.read_bytes()).hexdigest()==item['sha256']
        shutil.copy2(source,destination/item['file'])
legacy_snapshots={}
def migrate_addon(destination):
    if not options.legacy_addon:return
    source=options.legacy_addon.resolve(strict=True)
    target=(destination/'mcheli_addons/default').resolve()
    assert target.is_relative_to(work.resolve())
    if target.exists():shutil.rmtree(target)
    shutil.copytree(source,target)
    if options.missing_addon_meta:(target/'pack.mcmeta').unlink(missing_ok=True)
    resources=root/'patches/controls/resources'
    assets=[p for p in sorted(resources.rglob('*')) if p.is_file()]
    assert len(assets)==21
    managed={p.relative_to(resources).as_posix() for p in assets}
    legacy_snapshots[destination.name]={
        'files':{p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file() and p.relative_to(source).as_posix() not in managed|{'pack.mcmeta','assets/mcheli/sounds.json'}},
        'sounds':json.loads((source/'assets/mcheli/sounds.json').read_text(encoding='utf-8-sig'))
    }
    with zipfile.ZipFile(work/'mcheli-ce-1.5.1-vm-controls1.jar') as archive:
        for asset in assets:
            member=asset.relative_to(resources).as_posix();path=target/member;assert path.resolve().is_relative_to(target)
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():shutil.copy2(path,path.with_name(path.name+'.qa-backup'))
            assert archive.read(member)==asset.read_bytes()
            path.write_bytes(archive.read(member))
def verify_migration():
    if not legacy_snapshots:return
    results={}
    resources=root/'patches/controls/resources'
    for side,snapshot in legacy_snapshots.items():
        target=work/side/'mcheli_addons/default'
        sounds=json.loads((target/'assets/mcheli/sounds.json').read_text(encoding='utf-8-sig'))
        results[side]={
            'legacyUnmanagedAssets':len(snapshot['files']),
            'legacyUnmanagedBytesPreserved':all((target/name).is_file() and hashlib.sha256((target/name).read_bytes()).hexdigest()==expected for name,expected in snapshot['files'].items()),
            'nativeSoundOldEntriesPreserved':all(sounds.get(name)==value for name,value in snapshot['sounds'].items()),
            'managedAssets':21,
            'managedMatches':all((target/p.relative_to(resources)).read_bytes()==p.read_bytes() for p in resources.rglob('*') if p.is_file()),
            'metadataAfterStartup':(target/'pack.mcmeta').exists()
        }
    passed=all(value['legacyUnmanagedBytesPreserved'] and value['nativeSoundOldEntriesPreserved'] and value['managedMatches'] for value in results.values())
    (work/'legacy-upgrade-result.json').write_text(json.dumps({'success':passed,'metadataBeforeStartup':not options.missing_addon_meta,'candidateMcheliSha256':hashlib.sha256(mod.read_bytes()).hexdigest(),'result':results},indent=2),encoding='utf-8')
    assert passed,'Legacy addon migration lost an asset or existing sound event'
shutil.copytree(original/'libraries',server/'libraries',dirs_exist_ok=True,copy_function=link)
for name in ['forge-1.12.2-14.23.5.2860.jar','minecraft_server.1.12.2.jar','eula.txt']:
    link(original/name,server/name)
(server/'mods').mkdir(exist_ok=True)
for mod in (original/'mods').glob('*.jar'):
    if not mod.name.startswith(('mcheli','techguns')):link(mod,server/'mods'/mod.name)
comfort(server/'mods')
migrate_addon(server)
if options.legacy_config:
    (server/'config').mkdir(exist_ok=True)
    shutil.copy2(options.legacy_config.resolve(strict=True),server/'config/mcheli.cfg')
if options.comfort_config:
    (server/'config').mkdir(exist_ok=True)
    for name in ('firstaid.cfg','enhancedvisuals.json'):shutil.copy2(options.comfort_config/name,server/'config'/name)
props=work/'techguns-1.12.2-2.0.2.0-rv-gameplay.jar'
if props.exists():
    for prior in (server/'mods').glob('techguns*.jar'):prior.unlink()
    shutil.copy2(props,server/'mods'/props.name)
else:
    for mod in (original/'mods').glob('techguns*.jar'):link(mod,server/'mods'/mod.name)
java=game/'runtime/bin/java.exe'
libraries=list((game/'libraries').rglob('*.jar'))
asm=next(p for p in libraries if p.name=='asm-debug-all-5.2.jar')
classes=work/'runtime-test-classes'
classes.mkdir(exist_ok=True)
mod=work/'mcheli-ce-1.5.1-vm-controls1.jar'
compile_cp=os.pathsep.join([str(mod),*(str(p) for p in libraries)])
sources=[root/'qa/VMControlsRuntime.java',root/'qa/VMControlsClientRuntime.java']
acceptance=root/'qa/RVCombatAcceptance.java'
if acceptance.exists():sources.append(acceptance)
subprocess.run([str(java),'-jar',str(options.compiler),'-1.8','-encoding','UTF-8','-nowarn','-cp',compile_cp,'-d',str(classes),*map(str,sources)],check=True)
cp=os.pathsep.join([str(game/'runtime/lib/ext/nashorn.jar'),str(asm)])
subprocess.run([str(java),'-cp',cp,'jdk.nashorn.tools.Shell',str(root/'qa/patch-controls-test.js'),'--',str(mod),str(classes),'wing' if options.wing_input else 'normal'],check=True)
with zipfile.ZipFile(mod) as z,zipfile.ZipFile(server/'mods/mcheli-controls-test.jar','w',zipfile.ZIP_DEFLATED) as out:
    for item in z.infolist():
        changed=classes/item.filename
        out.writestr(item,changed.read_bytes() if changed.is_file() else z.read(item.filename))
    out.write(classes/'VMControlsRuntime.class','VMControlsRuntime.class')
    out.write(classes/'VMControlsClientRuntime.class','VMControlsClientRuntime.class')
    if acceptance.exists():
        for helper in classes.glob('RVCombatAcceptance*.class'):out.write(helper,helper.name)
(server/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=25576\nonline-mode=false\nlevel-name=ControlsTest\nlevel-type=FLAT\ngenerator-settings=3;minecraft:bedrock,2*minecraft:dirt,minecraft:grass;1;\nview-distance=3\nmax-players=2\nspawn-protection=0\nspawn-monsters=false\nspawn-animals=false\nallow-flight=true\ngamemode=1\n',encoding='ascii')
log=server/'integration.log'
with log.open('w',encoding='utf-8') as stream:
    process=subprocess.Popen([str(java),'-Xms256M','-Xmx2G','-Dvm.controls.integration=true','-Drv.gallery.origin='+options.origin,'-Dlog4j2.formatMsgNoLookups=true','-jar','forge-1.12.2-14.23.5.2860.jar','nogui'],cwd=server,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    print('Started isolated Forge server on 127.0.0.1:25576',flush=True)
    try:
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            content=log.read_text(encoding='utf-8',errors='replace')
            if 'Done (' in content:break
            if process.poll() is not None:raise RuntimeError('Server exited. See '+str(log))
            time.sleep(.25)
        else:raise TimeoutError('Server startup timeout')
        if not options.gallery and not options.wing_input and not options.apache_audio:
            print('Forge server ready; invoking real entity/sound/particle checks',flush=True)
            process.stdin.write('mcheli vmcontrolscheck\n');process.stdin.flush()
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                content=log.read_text(encoding='utf-8',errors='replace')
                if '[VM integration] COMPLETE' in content or '[VM integration] FAILED' in content:break
                time.sleep(.2)
            issues=[line for line in content.splitlines() if '[VM ' in line]
            print('\n'.join(issues),flush=True)
            ok='[VM integration] COMPLETE' in content and '[VM integration] FAILED' not in content and not any('Exception' in line for line in issues)
            report={'success':ok,'log':str(log),'artifact_sha256':hashlib.sha256(mod.read_bytes()).hexdigest(),'props_sha256':hashlib.sha256(props.read_bytes()).hexdigest() if props.exists() else None,'checks':issues}
            if acceptance.exists():report['acceptance_source_sha256']=hashlib.sha256(acceptance.read_bytes()).hexdigest()
            (work/'runtime-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            if not ok:raise RuntimeError('Runtime checks failed')
        if options.client:
            client=work/'client';client.mkdir(exist_ok=True)
            (client/'mods').mkdir(exist_ok=True)
            for item in (game/'mods').glob('*.jar'):
                if not item.name.startswith(('mcheli','techguns')):link(item,client/'mods'/item.name)
            comfort(client/'mods')
            migrate_addon(client)
            if props.exists():
                for prior in (client/'mods').glob('techguns*.jar'):prior.unlink()
                shutil.copy2(props,client/'mods'/props.name)
            else:
                for item in (game/'mods').glob('techguns*.jar'):link(item,client/'mods'/item.name)
            shutil.copy2(server/'mods/mcheli-controls-test.jar',client/'mods/mcheli-controls-test.jar')
            shutil.copytree(game/'config',client/'config',dirs_exist_ok=True)
            if options.comfort_config:
                for name in ('firstaid.cfg','enhancedvisuals-client.json','enhancedvisuals.json'):shutil.copy2(options.comfort_config/name,client/'config'/name)
            guide=options.guide
            guide_provenance={}
            for locale in ('en','ru'):
                if guide is None:continue
                source=guide/f'book_give_{locale}.mcfunction'
                if source.exists():
                    guide_provenance[locale]=hashlib.sha256(source.read_bytes()).hexdigest()
                    line=source.read_text(encoding='utf-8').splitlines()[0]
                    pages=json.loads(line.split('pages:',1)[1][:-1])
                    (client/f'qa-book-{locale}.json').write_text(json.dumps(pages,ensure_ascii=False),encoding='utf-8')
            if guide is not None:(client/'guide-font-provenance.json').write_text(json.dumps({'functionsSha256':guide_provenance,'mcheliSha256':hashlib.sha256(mod.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
            (client/'resourcepacks').mkdir(exist_ok=True)
            audio=options.audio
            shutil.copy2(audio,client/'resourcepacks'/audio.name)
            ui_pack=game/'resourcepacks/Warfare-UI-fixes.zip'
            if ui_pack.exists():shutil.copy2(ui_pack,client/'resourcepacks'/ui_pack.name)
            (client/'config/vm-controller.properties').write_text('enabled=false\nflight=angle\n')
            (client/'options.txt').write_text('renderDistance:3\nfancyGraphics:false\nmaxFps:60\nfullscreen:false\npauseOnLostFocus:false\nsoundCategory_master:0.2\nresourcePacks:["Warfare-UI-fixes.zip","Warfare-Combat-Audio.zip"]\n')
            (client/'optionsshaders.txt').write_text('shaderPack='+options.shader+'\n',encoding='utf-8')
            if options.performance:
                apply=work/'apply-profile.ps1'
                apply.write_text("param([string]$Root,[string]$Profile)\n. '"+str(root/'src/Warfare-Performance.ps1').replace("'","''")+"'\nSet-WarfarePerformanceProfile -Root $Root -Profile $Profile -Language en -ApplyGraphics\n",encoding='utf-8-sig')
                subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(apply),'-Root',str(client),'-Profile',options.performance],check=True)
                (client/'optionsshaders.txt').write_text('shaderPack='+options.shader+'\n',encoding='utf-8')
            if options.shader!='OFF':
                (client/'shaderpacks').mkdir(exist_ok=True)
                shutil.copy2(game/'shaderpacks'/options.shader,client/'shaderpacks'/options.shader)
            downloads=json.loads((game/'installer-files.json').read_text(encoding='utf-8-sig'))
            client_cp=os.pathsep.join(str(game/p) for p in downloads['classpath'])
            client_log=client/'integration.log'
            with client_log.open('w',encoding='utf-8') as client_stream:
                client_process=subprocess.Popen([str(java),'-Xms256M','-Xmx3G','-Dvm.controls.integration=true','-Drv.apache.audio='+str(options.apache_audio).lower(),'-Drv.effects.profile='+str(options.performance or 'balanced'),'-Drv.guide.check='+str(options.guide is not None).lower(),'-Drv.gallery.capture='+str(options.gallery).lower(),'-Drv.wing.input='+str(options.wing_input).lower(),'-Drv.gallery.shaders='+str(options.shader!='OFF').lower(),'-Drv.gallery.origin='+options.origin,'-Dlog4j2.formatMsgNoLookups=true',f'-Djava.library.path={game / "natives"}','-cp',client_cp,downloads['mainClass'],'--username','VMControlsTest','--version','VM-controls-test','--gameDir',str(client),'--assetsDir',str(game/'assets'),'--assetIndex',downloads['assetIndex'],'--uuid','a735f1a045e4471c99426b651bf267c8','--accessToken','0','--userType','legacy','--tweakClass','net.minecraftforge.fml.common.launcher.FMLTweaker','--server','127.0.0.1','--port','25576','--width','1920' if options.gallery else '960','--height','1080' if options.gallery else '600'],cwd=client,stdout=client_stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                print('Started isolated Minecraft client for render/sound/control hooks',flush=True)
                try:
                    deadline=time.monotonic()+180
                    while time.monotonic()<deadline:
                        server_text=log.read_text(encoding='utf-8',errors='replace')
                        if 'VMControlsTest joined the game' in server_text:break
                        if client_process.poll() is not None:raise RuntimeError('Client startup failed')
                        if 'Fatally missing registry entries' in client_log.read_text(encoding='utf-8',errors='replace'):raise RuntimeError('Client registry mismatch')
                        time.sleep(.5)
                    else:raise TimeoutError('Client join timeout')
                    if options.wing_input:
                        wing_results={}
                        for name in ([options.wing] if options.wing else ['geran','fp1']):
                            process.stdin.write('mcheli vmcontrolswinglaunch'+name+'\n');process.stdin.flush()
                            deadline=time.monotonic()+60
                            while time.monotonic()<deadline:
                                wing_text=client_log.read_text(encoding='utf-8',errors='replace')
                                if '[VM wing input] COMPLETE rv_'+name in wing_text or '[VM wing input] FAILED' in wing_text:break
                                if client_process.poll() is not None:raise RuntimeError('Wing client exited')
                                time.sleep(.25)
                            assert '[VM wing input] COMPLETE rv_'+name in wing_text and '[VM wing input] FAILED' not in wing_text,'Wing input failed; see '+str(client_log)
                            native=json.loads((server/f'wing-launch-server-rv_{name}.json').read_text(encoding='utf-8'))
                            inputs=json.loads((client/f'wing-launch-client-rv_{name}.json').read_text(encoding='utf-8'))
                            samples=inputs['samples'];actual=native['samples']
                            at=lambda tick:next(value for value in samples if value['tick']==tick)
                            bank=min(value['roll'] for value in samples if 135<=value['tick']<=155)
                            cases={
                                'nativeGroundPlacement':abs(native['startY']-4)<.01 and min(value['y'] for value in actual[:5])<4.5,
                                'wRaisesThrottle':max(value['throttle'] for value in samples[:34])>=.9,
                                'groundTakeoff':max(value['y'] for value in actual)-native['startY']>=5,
                                'nativeForwardTravel':max(abs(value['x']-native['startX'])+abs(value['z']-native['startZ']) for value in actual)>=30,
                                'mouseChangesPitch':abs(at(175)['pitch']-at(50)['pitch'])>2,
                                'aBanksLeft':at(135)['roll']<-5,
                                'dReversesBank':at(175)['roll']-bank>8,
                                'sLowersThrottle':at(190)['throttle']<at(170)['throttle']-.2,
                                'yDisconnectsLivingAircraft':any(not value['controlled'] and not value['dead'] and value['throttle']==0 for value in actual),
                                'nativeFocusedInput':all(value['focus'] and value['active'] and value.get('screen') is None for value in samples if value['tick']<=195)
                            }
                            assert all(cases.values()),f'Native wing oracle failed: {name} {cases}'
                            wing_results[name]=cases
                        print('\n'.join(line for line in wing_text.splitlines() if '[VM wing input]' in line),flush=True)
                        (work/'wing-result.json').write_text(json.dumps({'success':True,'artifact_sha256':hashlib.sha256(mod.read_bytes()).hexdigest(),'physicalDeviceTested':False,'cases':wing_results},indent=2),encoding='utf-8')
                    elif options.gallery:
                        process.stdin.write('gamerule doDaylightCycle false\nweather clear\ntime set 6000\nmcheli vmcontrolsgallery\n');process.stdin.flush()
                        deadline=time.monotonic()+180
                        while time.monotonic()<deadline:
                            gallery_text=client_log.read_text(encoding='utf-8',errors='replace')
                            if '[VM gallery] COMPLETE' in gallery_text or '[VM gallery] FAILED' in gallery_text:break
                            if client_process.poll() is not None:raise RuntimeError('Gallery client exited')
                            time.sleep(.25)
                        assert '[VM gallery] COMPLETE' in gallery_text and '[VM gallery] FAILED' not in gallery_text,'Gallery capture failed; see '+str(client_log)
                        print('\n'.join(line for line in gallery_text.splitlines() if '[VM gallery]' in line),flush=True)
                        (work/'gallery-result.json').write_text(json.dumps({'success':True,'artifact_sha256':hashlib.sha256(mod.read_bytes()).hexdigest(),'shader':options.shader,'world':str(options.world),'origin':options.origin},indent=2),encoding='utf-8')
                    elif options.apache_audio:
                        deadline=time.monotonic()+30
                        while time.monotonic()<deadline:
                            audio_text=client_log.read_text(encoding='utf-8',errors='replace')
                            if '[VM apache audio] COMPLETE' in audio_text or '[VM apache audio] FAILED' in audio_text:break
                            time.sleep(.25)
                        assert '[VM apache audio] COMPLETE' in audio_text and '[VM apache audio] FAILED' not in audio_text,'Native Apache audio mapping failed'
                        print('\n'.join(line for line in audio_text.splitlines() if '[VM apache audio]' in line),flush=True)
                    else:
                        process.stdin.write('mcheli vmcontrolsride\n');process.stdin.flush()
                    if not options.gallery and not options.wing_input and not options.apache_audio:
                        deadline=time.monotonic()+30
                        while time.monotonic()<deadline:
                            client_text=client_log.read_text(encoding='utf-8',errors='replace')
                            if '[VM client integration] COMPLETE' in client_text or '[VM client integration] FAILED' in client_text:break
                            time.sleep(.25)
                        lines=[line for line in client_text.splitlines() if '[VM ' in line]
                        print('\n'.join(lines),flush=True)
                        client_ok='[VM client integration] COMPLETE' in client_text and '[VM client integration] FAILED' not in client_text and not any('Exception' in line or 'Error' in line for line in lines)
                        (work/'client-result.json').write_text(json.dumps({'success':client_ok,'artifact_sha256':hashlib.sha256(mod.read_bytes()).hexdigest(),'checks':lines},ensure_ascii=False,indent=2),encoding='utf-8')
                        if not client_ok:raise RuntimeError('Client integration failed; see '+str(client_log))
                        process.stdin.write('mcheli vmcontrolscombat\n');process.stdin.flush()
                        deadline=time.monotonic()+30
                        while time.monotonic()<deadline:
                            server_text=log.read_text(encoding='utf-8',errors='replace')
                            if '[VM combat integration] COMPLETE' in server_text or '[VM combat integration] FAILED' in server_text:break
                            time.sleep(.25)
                        combat_lines=[line for line in server_text.splitlines() if '[VM ' in line or '[RV combat QA]' in line]
                        print('\n'.join(combat_lines[-10:]),flush=True)
                        combat_ok='[VM combat integration] COMPLETE' in server_text and '[VM combat integration] FAILED' not in server_text and not any('Exception' in line or 'Error' in line for line in combat_lines)
                        (work/'combat-result.json').write_text(json.dumps({'success':combat_ok,'artifact_sha256':hashlib.sha256(mod.read_bytes()).hexdigest(),'props_sha256':hashlib.sha256(props.read_bytes()).hexdigest() if props.exists() else None,'acceptance_source_sha256':hashlib.sha256(acceptance.read_bytes()).hexdigest() if acceptance.exists() else None,'checks':combat_lines},ensure_ascii=False,indent=2),encoding='utf-8')
                        if not combat_ok:raise RuntimeError('Actual collision/damage checks failed; see '+str(log))
                    verify_migration()
                finally:
                    if client_process.poll() is None:client_process.terminate();client_process.wait(timeout=20)
    finally:
        if process.poll() is None:
            process.stdin.write('stop\n');process.stdin.flush()
            try:process.wait(timeout=25)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=10)
