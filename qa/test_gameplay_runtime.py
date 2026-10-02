import argparse
import collections
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid


parser = argparse.ArgumentParser()
parser.add_argument('--server-source', type=Path, required=True)
parser.add_argument('--client', type=Path, required=True)
parser.add_argument('--world-template', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--python-libs', type=Path)
parser.add_argument('--guide-pages', type=int, default=10)
parser.add_argument('--guide-version', type=int, default=1)
parser.add_argument('--edition-upgrade', action='store_true')
parser.add_argument('--expanded', action='store_true')
parser.add_argument('--medical', action='store_true')
parser.add_argument('--medical-only', action='store_true')
parser.add_argument('--mcheli', type=Path)
parser.add_argument('--spawn-helper', type=Path)
parser.add_argument('--comfort-mods', type=Path)
parser.add_argument('--comfort-config', type=Path)
args = parser.parse_args()
if args.python_libs:
    sys.path.insert(0, str(args.python_libs))
import nbtlib

root = args.output.resolve()
root.mkdir(parents=True, exist_ok=False)
server = root / 'server'
server.mkdir()
game = args.client.resolve()
name = 'MenuTester'
player_uuid = uuid.UUID(bytes=hashlib.md5(('OfflinePlayer:' + name).encode()).digest(), version=3)
checks = []
process = None
client = None
server_log = None
client_log = None


def link(source, destination):
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    return destination


def wait_for(predicate, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError('Server exited unexpectedly')
        time.sleep(0.1)
    raise TimeoutError('Runtime condition timed out')


def check(value, label):
    checks.append({'name': label, 'passed': bool(value)})
    print(('PASS ' if value else 'FAIL ') + label, flush=True)
    if not value:
        raise AssertionError(label)


def commands(*values, delay=0.25):
    process.stdin.write('\n'.join(values) + '\n')
    process.stdin.flush()
    time.sleep(delay)


def player_data():
    path = server / 'Battlefield-Extended/playerdata' / (str(player_uuid) + '.dat')
    previous = path.stat().st_mtime_ns if path.exists() else 0
    commands('save-all')
    wait_for(lambda: path.exists() and path.stat().st_mtime_ns != previous, 10)
    return nbtlib.load(path)


def scores():
    data = nbtlib.load(server / 'Battlefield-Extended/data/scoreboard.dat')['data']
    return {str(item['Objective']): int(item['Score']) for item in data['PlayerScores'] if str(item['Name']) == name}


def counts(data):
    found = collections.Counter()
    for item in data['Inventory']:
        found[(str(item['id']), int(item.get('Damage', 0)))] += int(item['Count'])
    return found


def books(data, edition=None):
    edition = args.guide_version if edition is None else edition
    return [item for item in data['Inventory'] if str(item['id']) == 'minecraft:written_book' and int(item.get('tag', {}).get('rvGuide', 0)) == 1 and int(item.get('tag', {}).get('rvGuideVersion', 0)) == edition]


def respawn():
    result = game / 'rv-qa-respawn-result.txt'
    previous = result.stat().st_mtime_ns if result.exists() else 0
    commands('kill ' + name, delay=0.4)
    (game / 'rv-qa-respawn.txt').write_text('MenuTester', encoding='ascii')
    wait_for(lambda: result.exists() and result.stat().st_mtime_ns != previous, 15)
    time.sleep(1)
    return player_data()


def near(data, point, radius=2):
    return all(abs(float(value)-expected) <= radius for value,expected in zip(data['Pos'],point))


def medical_space_checks():
    for index in range(36):
        slot = 'slot.hotbar.' + str(index) if index < 9 else 'slot.inventory.' + str(index - 9)
        commands('replaceitem entity ' + name + ' ' + slot + ' minecraft:dirt 64', delay=0)
    commands('execute ' + name + ' ~ ~ ~ function warfare:item_bandage', 'execute ' + name + ' ~ ~ ~ function warfare:item_plaster')
    medical_full = player_data()
    check(counts(medical_full)[('firstaid:bandage', 0)] == 0 and counts(medical_full)[('firstaid:plaster', 0)] == 0, 'full inventory receives no medical supplies')
    commands('replaceitem entity ' + name + ' slot.hotbar.0 minecraft:air', 'execute ' + name + ' ~ ~ ~ function warfare:item_bandage', 'execute ' + name + ' ~ ~ ~ function warfare:item_plaster')
    medical_one = player_data()
    check(counts(medical_one)[('firstaid:bandage', 0)] == 4 and counts(medical_one)[('firstaid:plaster', 0)] == 0 and len([item for item in medical_one['Inventory'] if 0 <= int(item['Slot']) <= 35]) == 36, 'one free slot receives one bounded medical stack')
    commands('testfor @e[type=item]')
    lines = (server / 'integration.log').read_text(encoding='utf-8', errors='replace').splitlines()
    check(not any('Found Item' in line for line in lines[-8:]), 'medical resupply never spills stacks on the ground')


def save_medical_stacks():
    commands('clear ' + name + ' firstaid:bandage', 'clear ' + name + ' firstaid:plaster', 'replaceitem entity ' + name + ' slot.hotbar.2 firstaid:bandage 4 0 {display:{Name:"RV QA saved bandage"}}', 'replaceitem entity ' + name + ' slot.hotbar.3 firstaid:plaster 4 0 {display:{Name:"RV QA saved plaster"}}')


def check_saved_medical_stacks():
    commands('execute ' + name + ' ~ ~ ~ function warfare:kit')
    restored = player_data()
    check(counts(restored)[('firstaid:bandage', 0)] == 4 and counts(restored)[('firstaid:plaster', 0)] == 4 and all(any(str(item['id']) == 'firstaid:' + item_id and str(item.get('tag', {}).get('display', {}).get('Name', '')) == 'RV QA saved ' + item_id for item in restored['Inventory']) for item_id in ('bandage', 'plaster')), 'medical caps and personal NBT survive save/restart/reconnect')


def start():
    global process, server_log
    server_log = (server / 'integration.log').open('w', encoding='utf-8')
    process = subprocess.Popen([str(game / 'runtime/bin/java.exe'), '-Dfile.encoding=UTF-8', '-Xms256M', '-Xmx2G', '-jar', 'forge-1.12.2-14.23.5.2860.jar', 'nogui'], cwd=server, stdin=subprocess.PIPE, stdout=server_log, stderr=subprocess.STDOUT, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
    wait_for(lambda: 'Done (' in (server / 'integration.log').read_text(encoding='utf-8', errors='replace'))
    commands('function warfare:boot', delay=0.4)
    print('Isolated Forge ready on loopback25577', flush=True)


def join():
    global client, client_log
    plan = json.loads((game / 'installer-files.json').read_text(encoding='utf-8-sig'))
    classpath = os.pathsep.join(str(game / item) for item in plan['classpath'])
    client_log = (root / ('client-' + str(len(checks)) + '.log')).open('w', encoding='utf-8')
    client = subprocess.Popen([str(game / 'runtime/bin/java.exe'), '-Dfile.encoding=UTF-8', '-Xms256M', '-Xmx2G', '-Djava.library.path=' + str(game / 'natives'), '-cp', classpath, plan['mainClass'], '--username', name, '--version', 'RV-gameplay-QA', '--gameDir', str(game), '--assetsDir', str(game / 'assets'), '--assetIndex', plan['assetIndex'], '--uuid', player_uuid.hex, '--accessToken', '0', '--userType', 'legacy', '--tweakClass', 'net.minecraftforge.fml.common.launcher.FMLTweaker', '--server', '127.0.0.1', '--port', '25577', '--width', '854', '--height', '480'], cwd=game, stdout=client_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    wait_for(lambda: name + ' joined the game' in (server / 'integration.log').read_text(encoding='utf-8', errors='replace'))
    time.sleep(1.2)


def leave():
    global client, client_log
    if client is not None and client.poll() is None:
        commands('kick ' + name + ' RV QA reconnect', delay=0.4)
        client.terminate()
        client.wait(timeout=15)
    client = None
    if client_log:
        client_log.close()
        client_log = None


def stop():
    global process, server_log
    if process is not None and process.poll() is None:
        commands('save-all', 'stop', delay=0)
        process.wait(timeout=60)
    if server_log:
        server_log.close()
    process = None


try:
    shutil.copytree(args.server_source / 'libraries', server / 'libraries', copy_function=link)
    shutil.copytree(args.server_source / 'mods', server / 'mods', copy_function=link)
    if args.mcheli:
        destination = server / 'mods/mcheli-ce-1.5.1-rv.jar'
        temporary = destination.with_suffix('.rv-qa-new')
        shutil.copy2(args.mcheli, temporary)
        temporary.replace(destination)
    if args.spawn_helper:
        shutil.copy2(args.spawn_helper, server / 'mods/rv-spawn-qa.jar')
    shutil.copytree(args.server_source / 'config', server / 'config')
    if args.comfort_mods:
        vendor = json.loads((args.comfort_mods / 'verified-mods.json').read_text(encoding='utf-8-sig'))
        for entry in vendor['mods']:
            source = args.comfort_mods / entry['file']
            if source.name != entry['file'] or source.stat().st_size != entry['size'] or hashlib.sha256(source.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError('Vendor source changed: ' + entry['file'])
            shutil.copy2(source, server / 'mods' / entry['file'])
    if args.comfort_config:
        for filename in ('firstaid.cfg', 'enhancedvisuals.json', 'enhancedvisuals-client.json'):
            shutil.copy2(args.comfort_config / filename, server / 'config' / filename)
    for filename in ('forge-1.12.2-14.23.5.2860.jar', 'minecraft_server.1.12.2.jar', 'eula.txt'):
        link(args.server_source / filename, server / filename)
    shutil.copytree(args.world_template, server / 'Battlefield-Extended')
    (server / 'server.properties').write_text('server-ip=127.0.0.1\nserver-port=25577\nonline-mode=false\nlevel-name=Battlefield-Extended\nview-distance=3\nmax-players=2\nspawn-protection=0\nspawn-monsters=false\nspawn-animals=false\nallow-flight=true\ngamemode=0\n', encoding='ascii')
    start()
    join()
    initial = player_data()
    check(counts(initial)[('techguns:m4', 0)] == 1, 'new non-op receives one M4')
    check(counts(initial)[('techguns:itemshared', 13)] == 16, 'new non-op receives16 rifle magazines')
    if args.expanded:
        check(counts(initial)[('minecraft:cooked_beef', 0)] == 16, 'new non-op receives16 food')
        check(counts(initial)[('mcheli:rc-goblin-bomb', 0)] == 3 and counts(initial)[('mcheli:rv_geran', 0)] == 1 and counts(initial)[('mcheli:rv_fp1', 0)] == 1 and counts(initial)[('mcheli:uav_tablet', 0)] == 1, 'native starter registry supplies3 FPV, Geran, FP-1 and tablet')
        if args.medical:
            check(counts(initial)[('firstaid:bandage', 0)] == 4 and counts(initial)[('firstaid:plaster', 0)] == 4, 'new non-op receives four native bandages and four plasters')
        check(near(initial,(0,65,-210)), 'new non-op first join is at common safe hub')
        commands('tp ' + name + ' 40 65 -210', delay=0.3)
        unbound = respawn()
        check(near(unbound,(0,65,-210)), 'native client death respawn uses common hub when unbound')
        commands('execute ' + name + ' ~ ~ ~ function warfare:blue', delay=0.3)
        blue = player_data()
        bed_keys = ('SpawnX','SpawnY','SpawnZ','SpawnForced')
        before = {key:int(blue.get(key,0)) for key in bed_keys}
        blue_point = tuple(before[key] for key in ('SpawnX','SpawnY','SpawnZ'))
        commands('execute ' + name + ' ~ ~ ~ function warfare:spawn', delay=0.3)
        hub = player_data()
        check(near(hub,(0,65,-210)) and {key:int(hub.get(key,0)) for key in bed_keys} == before, 'spawn action teleports without resetting selected team spawnpoint')
        check(near(respawn(),blue_point), 'explicit blue team spawnpoint survives native death respawn')
        commands('setblock 10 65 -210 minecraft:bed 0', 'setblock 10 65 -209 minecraft:bed 8', delay=0.3)
        (server / 'rv-qa-bed.txt').write_text('MenuTester',encoding='ascii')
        wait_for(lambda: (server / 'rv-qa-bed-result.txt').exists(),15)
        bed = player_data()
        check(int(bed.get('SpawnForced',1)) == 0 and int(bed['SpawnX']) == 10, 'real bed spawn stored with native unforced semantics')
        commands('execute ' + name + ' ~ ~ ~ function warfare:spawn', delay=0.3)
        hub = player_data()
        check(int(hub.get('SpawnForced',1)) == 0 and int(hub['SpawnX']) == 10 and near(hub,(0,65,-210)), 'spawn command preserves saved bed and team selection')
        check(near(respawn(),(10,65,-210),radius=3), 'saved actual bed takes priority over common world spawn')
    check(not books(initial), 'book waits for language selection')
    commands('replaceitem entity ' + name + ' slot.armor.head minecraft:diamond_helmet 1 0 {display:{Name:"RV QA personal"}}', 'give ' + name + ' techguns:m4 1 0 {display:{Name:"RV QA custom"}}', 'execute ' + name + ' ~ ~ ~ function warfare:kit', 'execute ' + name + ' ~ ~ ~ function warfare:kit')
    supplied = player_data()
    check(counts(supplied)[('techguns:itemshared', 13)] == 16, 'AffectedItems count-zero query bounds repeated resupply')
    check(counts(supplied)[('techguns:m4', 0)] == 2, 'repeated kit preserves both existing guns without duplication')
    if args.expanded:
        check(counts(supplied)[('mcheli:rc-goblin-bomb',0)] == 3 and counts(supplied)[('mcheli:rv_geran',0)] == 1 and counts(supplied)[('mcheli:rv_fp1',0)] == 1, 'repeated expanded kit keeps aircraft quantities bounded')
    if args.medical:
        check(counts(supplied)[('firstaid:bandage', 0)] == 4 and counts(supplied)[('firstaid:plaster', 0)] == 4, 'repeated kit keeps medical quantities bounded')
        commands('clear ' + name + ' firstaid:bandage', 'clear ' + name + ' firstaid:plaster', 'give ' + name + ' firstaid:bandage 2 0 {display:{Name:"RV QA personal bandage"}}', 'replaceitem entity ' + name + ' slot.weapon.offhand firstaid:bandage 1', 'give ' + name + ' firstaid:plaster 3 0 {display:{Name:"RV QA personal plaster"}}', 'execute ' + name + ' ~ ~ ~ function warfare:kit')
        medical = player_data()
        check(counts(medical)[('firstaid:bandage', 0)] == 4 and counts(medical)[('firstaid:plaster', 0)] == 4, 'medical top-up counts custom stacks and the offhand')
        check(any(str(item['id']) == 'firstaid:bandage' and int(item['Count']) == 2 and str(item.get('tag', {}).get('display', {}).get('Name', '')) == 'RV QA personal bandage' for item in medical['Inventory']) and any(str(item['id']) == 'firstaid:plaster' and int(item['Count']) == 3 and str(item.get('tag', {}).get('display', {}).get('Name', '')) == 'RV QA personal plaster' for item in medical['Inventory']), 'medical top-up preserves personal stack NBT')
        commands('replaceitem entity ' + name + ' slot.weapon.offhand minecraft:air')
    check(any(int(item['Slot']) == 103 and str(item['id']) == 'minecraft:diamond_helmet' and str(item.get('tag', {}).get('display', {}).get('Name', '')) == 'RV QA personal' for item in supplied['Inventory']), 'personal armour and NBT retained')
    if args.medical_only:
        if not args.medical:
            raise ValueError('--medical-only requires --medical')
        medical_space_checks()
        save_medical_stacks()
        leave()
        stop()
        start()
        join()
        check_saved_medical_stacks()
        raise SystemExit(0)
    for index in range(36):
        slot = 'slot.hotbar.' + str(index) if index < 9 else 'slot.inventory.' + str(index - 9)
        commands('replaceitem entity ' + name + ' ' + slot + ' minecraft:dirt 64', delay=0)
    commands('execute ' + name + ' ~ ~ ~ function warfare:lang_en', 'execute ' + name + ' ~ ~ ~ function warfare:kit', delay=1.3)
    full = player_data()
    check(len([item for item in full['Inventory'] if 0 <= int(item['Slot']) <= 35]) == 36 and not books(full), 'full main inventory receives no dropped book')
    check(scores().get('wbOnce') == 0 and scores().get('wbPending') == 1, 'full inventory leaves guide pending')
    commands('replaceitem entity ' + name + ' slot.hotbar.0 minecraft:air', delay=1.3)
    delivered = player_data()
    check(len(books(delivered)) == 1 and len(books(delivered)[0]['tag']['pages']) == args.guide_pages, 'one free slot receives the complete English guide')
    check(scores().get('wbOnce') == 1 and scores().get('wbPending') == 0, 'book completion confirmed from actual item NBT')
    commands('execute ' + name + ' ~ ~ ~ function warfare:lang_ru', 'execute ' + name + ' ~ ~ ~ function warfare:book_request', delay=1.3)
    unchanged = player_data()
    check(len(books(unchanged)) == 1 and str(books(unchanged)[0]['tag']['title']) == str(books(delivered)[0]['tag']['title']), 'locale switch and explicit request preserve existing guide')
    commands('clear ' + name + ' minecraft:written_book', 'execute ' + name + ' ~ ~ ~ function warfare:book_request', delay=1.3)
    replaced = player_data()
    check(len(books(replaced)) == 1 and str(books(replaced)[0]['tag']['title']) != str(books(delivered)[0]['tag']['title']), 'lost guide replaced in selected Russian locale')
    commands('scoreboard players set ' + name + ' loadout 999', 'scoreboard players set ' + name + ' ui_admin 1', delay=0.3)
    player_data()
    check(scores().get('loadout') == 0 and scores().get('ui_admin') == 0, 'invalid class and non-op admin trigger reset')
    commands('testfor @e[type=item]')
    lines = (server / 'integration.log').read_text(encoding='utf-8', errors='replace').splitlines()
    check(not any('Found Item' in line for line in lines[-8:]), 'full inventory does not spill supplies on the ground')
    if args.medical:
        medical_space_checks()
    if args.edition_upgrade:
        give = (server / 'Battlefield-Extended/data/functions/warfare/book_give_ru.mcfunction').read_text(encoding='utf-8').splitlines()[0]
        current_tag = re.search(r'minecraft:written_book 1 0 (\{.*\})$', give)[1]
        commands('clear ' + name + ' minecraft:written_book', delay=0)
        for index in range(36):
            slot = 'slot.hotbar.' + str(index) if index < 9 else 'slot.inventory.' + str(index - 9)
            commands('replaceitem entity ' + name + ' ' + slot + ' minecraft:dirt 64', delay=0)
        commands('replaceitem entity ' + name + ' slot.hotbar.0 minecraft:written_book 1 0 {rvGuide:1b,rvGuideVersion:1,title:"RV legacy",author:"RV",pages:["{\\"text\\":\\"Legacy guide\\"}"]}', 'scoreboard players set ' + name + ' wbOnce 1', 'scoreboard players set ' + name + ' wbEdition 1', 'scoreboard players set ' + name + ' wbPending 0', delay=1.3)
        legacy_full = player_data()
        check(len(books(legacy_full, 1)) == 1 and not books(legacy_full), 'old edition remains intact while full inventory waits for upgrade')
        check(scores().get('wbOnce') == 1 and scores().get('wbEdition') == 1 and scores().get('wbPending') == 1, 'edition upgrade preserves persistent completion and stays pending')
        commands('replaceitem entity ' + name + ' slot.hotbar.1 minecraft:air', delay=1.3)
        upgraded = player_data()
        check(len(books(upgraded, 1)) == 1 and len(books(upgraded)) == 1 and len(books(upgraded)[0]['tag']['pages']) == args.guide_pages, 'one free slot receives current edition without deleting old guide')
        check(scores().get('wbEdition') == args.guide_version and scores().get('wbPending') == 0, 'new edition confirmed from actual item NBT')
        commands('replaceitem entity ' + name + ' slot.hotbar.1 minecraft:air', 'replaceitem entity ' + name + ' slot.weapon.offhand minecraft:written_book 1 0 ' + current_tag, 'scoreboard players set ' + name + ' wbEdition 1', 'scoreboard players set ' + name + ' wbPending 0', delay=1.3)
        offhand = player_data()
        check(len(books(offhand)) == 1 and int(books(offhand)[0]['Slot']) == -106 and len(books(offhand, 1)) == 1, 'current guide in offhand confirms upgrade without another main-inventory copy')
        check(scores().get('wbEdition') == args.guide_version, 'offhand edition confirmation persists')
    if args.medical:
        save_medical_stacks()
    leave()
    stop()
    start()
    join()
    restored = player_data()
    check(len(books(restored)) == 1 and scores().get('wbOnce') == 1, 'book and completion survive save/restart/reconnect')
    check(any(int(item['Slot']) == 103 and str(item['id']) == 'minecraft:diamond_helmet' for item in restored['Inventory']), 'personal armour survives save/restart')
    if args.edition_upgrade:
        check(len(books(restored, 1)) == 1 and scores().get('wbEdition') == args.guide_version, 'both guide editions and upgrade state survive actual server restart')
    if args.medical:
        check_saved_medical_stacks()
finally:
    try:
        leave()
    finally:
        stop()
    report = {'passed': bool(checks) and all(item['passed'] for item in checks), 'checks': checks, 'serverPort': 25577, 'ordinaryClients': 1, 'functions': len(list((server / 'Battlefield-Extended/data/functions/warfare').glob('*.mcfunction'))), 'medical': args.medical, 'medicalOnly': args.medical_only, 'mcheliSha256': hashlib.sha256(args.mcheli.read_bytes()).hexdigest() if args.mcheli else None}
    (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
