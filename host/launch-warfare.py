import argparse
import json
import os
import pathlib
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('--server', default='127.0.0.1')
parser.add_argument('--port', type=int, default=25565)
options = parser.parse_args()
root = pathlib.Path(__file__).resolve().parent
mc = pathlib.Path(os.environ['APPDATA']) / '.minecraft'
game = mc / 'versions' / 'Warfare-1.12.2'
version = json.loads((game / 'Warfare-1.12.2.json').read_text(encoding='utf-8-sig'))
profiles = json.loads((mc / 'TlauncherProfiles.json').read_text(encoding='utf-8-sig'))
account = profiles['accounts'].get(profiles.get('selectedAccountUUID'))
if account is None:
    raise SystemExit('Select an account in TLauncher first')
kind = account.get('type', '').lower()
token = account.get('accessToken', '')
user_type = 'legacy'
if kind in ('microsoft', 'msa', 'mojang'):
    if not token or token == '0':
        raise SystemExit('Sign in again in TLauncher to refresh the Minecraft session')
    user_type = 'mojang'
elif kind == 'free':
    token = '0'
else:
    raise SystemExit('Use TLauncher to launch this account type')
libraries = []
for library in version['libraries']:
    allowed = 'rules' not in library
    for rule in library.get('rules', []):
        if rule.get('os', {}).get('name', 'windows') == 'windows':
            allowed = rule['action'] == 'allow'
    artifact = library.get('artifact', {})
    if allowed and artifact.get('path'):
        relative = artifact['path'].replace('\\', '/')
        libraries.append(mc / relative if relative.startswith('libraries/') else mc / 'libraries' / relative)
libraries.append(game / 'Warfare-1.12.2.jar')
if any(not path.is_file() for path in libraries):
    raise SystemExit('Missing Warfare libraries')
java = mc / 'runtime' / 'temurin8' / 'jdk8u504-b01-jre' / 'bin' / 'java.exe'
arguments = [str(java), '-Dfile.encoding=UTF-8', '-Xms1G', '-Xmx4G', '-Djava.library.path=' + str(game / 'natives'), '-Dminecraft.launcher.brand=TLauncher', '-Dminecraft.launcher.version=2.9378', '-cp', ';'.join(map(str, libraries)), version['mainClass'], '--username', account.get('displayName') or 'Player', '--version', version['id'], '--gameDir', str(game), '--assetsDir', str(mc / 'assets'), '--assetIndex', version['assetIndex']['id'], '--uuid', account.get('uuid', '00000000-0000-0000-0000-000000000000'), '--accessToken', token, '--userType', user_type, '--tweakClass', 'net.minecraftforge.fml.common.launcher.FMLTweaker', '--versionType', 'Forge', '--server', options.server, '--port', str(options.port)]
with (root / 'client-console.log').open('w', encoding='utf-8') as output:
    process = subprocess.Popen(arguments, cwd=game, stdout=output, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    (root / 'client-state.json').write_text(json.dumps({'pid': process.pid, 'server': options.server, 'port': options.port, 'started': time.time()}), encoding='utf-8')
print(json.dumps({'state': 'running', 'pid': process.pid}))
