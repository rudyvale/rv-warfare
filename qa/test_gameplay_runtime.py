import argparse
import collections
import hashlib
import json
import os
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


def books(data):
    return [item for item in data['Inventory'] if str(item['id']) == 'minecraft:written_book' and int(item.get('tag', {}).get('rvGuide', 0)) == 1]


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
    shutil.copytree(args.server_source / 'config', server / 'config')
    for filename in ('forge-1.12.2-14.23.5.2860.jar', 'minecraft_server.1.12.2.jar', 'eula.txt'):
        link(args.server_source / filename, server / filename)
    shutil.copytree(args.world_template, server / 'Battlefield-Extended')
    (server / 'server.properties').write_text('server-ip=127.0.0.1\nserver-port=25577\nonline-mode=false\nlevel-name=Battlefield-Extended\nview-distance=3\nmax-players=2\nspawn-protection=0\nspawn-monsters=false\nspawn-animals=false\nallow-flight=true\ngamemode=0\n', encoding='ascii')
    start()
    join()
    initial = player_data()
    check(counts(initial)[('techguns:m4', 0)] == 1, 'new non-op receives one M4')
    check(counts(initial)[('techguns:itemshared', 13)] == 16, 'new non-op receives16 rifle magazines')
    check(not books(initial), 'book waits for language selection')
    commands('replaceitem entity ' + name + ' slot.armor.head minecraft:diamond_helmet 1 0 {display:{Name:"RV QA personal"}}', 'give ' + name + ' techguns:m4 1 0 {display:{Name:"RV QA custom"}}', 'execute ' + name + ' ~ ~ ~ function warfare:kit', 'execute ' + name + ' ~ ~ ~ function warfare:kit')
    supplied = player_data()
    check(counts(supplied)[('techguns:itemshared', 13)] == 16, 'AffectedItems count-zero query bounds repeated resupply')
    check(counts(supplied)[('techguns:m4', 0)] == 2, 'repeated kit preserves both existing guns without duplication')
    check(any(int(item['Slot']) == 103 and str(item['id']) == 'minecraft:diamond_helmet' and str(item.get('tag', {}).get('display', {}).get('Name', '')) == 'RV QA personal' for item in supplied['Inventory']), 'personal armour and NBT retained')
    for index in range(36):
        slot = 'slot.hotbar.' + str(index) if index < 9 else 'slot.inventory.' + str(index - 9)
        commands('replaceitem entity ' + name + ' ' + slot + ' minecraft:dirt 64', delay=0)
    commands('execute ' + name + ' ~ ~ ~ function warfare:lang_en', 'execute ' + name + ' ~ ~ ~ function warfare:kit', delay=1.3)
    full = player_data()
    check(len([item for item in full['Inventory'] if 0 <= int(item['Slot']) <= 35]) == 36 and not books(full), 'full main inventory receives no dropped book')
    check(scores().get('wbOnce') == 0 and scores().get('wbPending') == 1, 'full inventory leaves guide pending')
    commands('replaceitem entity ' + name + ' slot.hotbar.0 minecraft:air', delay=1.3)
    delivered = player_data()
    check(len(books(delivered)) == 1 and len(books(delivered)[0]['tag']['pages']) == 10, 'one free slot receives one10-page English guide')
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
    leave()
    stop()
    start()
    join()
    restored = player_data()
    check(len(books(restored)) == 1 and scores().get('wbOnce') == 1, 'book and completion survive save/restart/reconnect')
    check(any(int(item['Slot']) == 103 and str(item['id']) == 'minecraft:diamond_helmet' for item in restored['Inventory']), 'personal armour survives save/restart')
finally:
    try:
        leave()
    finally:
        stop()
    report = {'passed': bool(checks) and all(item['passed'] for item in checks), 'checks': checks, 'serverPort': 25577, 'ordinaryClients': 1, 'functions': len(list((server / 'Battlefield-Extended/data/functions/warfare').glob('*.mcfunction')))}
    (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
