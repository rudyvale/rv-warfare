import argparse
import hashlib
import io
import json
from pathlib import Path
import plistlib
import stat
import tarfile
import zipfile

from download_release_base import safe_entries
from build_macos import ALLOWED_DOWNLOAD_HOSTS
from release_contract import managed_hashes, managed_policies, retirement_policy


ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'RV.app/Contents/'
RESOURCES = PREFIX + 'Resources/'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(package, version=None, runtime=None, launcher_sha=None):
    platform = json.loads((ROOT / 'pack/macos-platform.json').read_text())
    frozen = json.loads((ROOT / 'pack/package-manifest.json').read_text())
    owned = json.loads((ROOT / 'pack/rv-managed-mods.json').read_text())
    catalog = json.loads((ROOT / 'pack/vendor-catalog.json').read_text())
    downloads = {entry['path'] for entry in catalog['files'] if entry['delivery'] == 'official-download'}
    binding = json.loads((ROOT / 'pack/macos-launcher.json').read_text())
    expected_installer = json.loads((ROOT / 'pack/macos-installer.json').read_text())
    inventory = json.loads((ROOT / 'pack/macos-runtime-files.json').read_text())
    with zipfile.ZipFile(package) as archive:
        safe_entries(archive)
        require(archive.testzip() is None, 'Mac package failed CRC')
        names = set(archive.namelist())
        require(all(not stat.S_ISLNK(entry.external_attr >> 16) for entry in archive.infolist()), 'Mac package contains a symlink')
        private = {'warfare-settings.json', 'launcher-settings.json', 'owner-policy.json', 'ops.json',
                   'whitelist.json', 'usercache.json', 'banned-players.json', 'banned-ips.json'}
        require(not any(set(name.lower().split('/')) & private or name.endswith('.rvinvite') for name in names), 'Private file in Mac package')
        plist = plistlib.loads(archive.read(PREFIX + 'Info.plist'))
        metadata = json.loads(archive.read(RESOURCES + 'macos-package.json'))
        require(plist['CFBundleIdentifier'] == 'com.rudyvale.rvwarfare' and plist['CFBundleExecutable'] == 'RVLauncher', 'Mac application identity mismatch')
        require(plist['CFBundleShortVersionString'] == metadata['version'], 'Mac application version mismatch')
        require(plist == dict(CFBundleName='RV', CFBundleDisplayName='RV Warfare', CFBundleIdentifier='com.rudyvale.rvwarfare', CFBundleExecutable='RVLauncher', CFBundlePackageType='APPL', CFBundleShortVersionString=metadata['version'], CFBundleVersion=metadata['version'], LSMinimumSystemVersion=platform['minimumSystemVersion'], NSHighResolutionCapable=True), 'Mac application metadata differs from source')
        require(archive.read(PREFIX + 'MacOS/RVLauncher') == (ROOT / 'platform/macos/RVLauncher.sh').read_bytes(), 'Mac entry script differs from source')
        require(archive.read('Open RV.command') == (ROOT / 'platform/macos/Open RV.command').read_bytes(), 'Mac open command differs from source')
        require(archive.read('READ-ME.md') == (ROOT / 'platform/macos/README.md').read_bytes(), 'Mac guide differs from source')
        require(version is None or version == metadata['version'], 'Unexpected Mac package version')
        release = json.loads(archive.read(RESOURCES + 'release.json'))
        require(release['version'] == metadata['version'], 'Mac release metadata version mismatch')
        require(release == json.loads((ROOT / 'src/release.json').read_text()), 'Mac release differs from source')
        for name in ('vendor-catalog.json', 'rv-managed-mods.json', 'THIRD-PARTY-NOTICES.md'):
            require(archive.read(RESOURCES + name) == (ROOT / 'pack' / name).read_bytes(), 'Mac resource differs from source: ' + name)
        require(metadata['server'] == platform['server'] and metadata['runtimePlatform'] == 'mac-x64', 'Mac platform pins differ')
        require(metadata['javaVersion'] == platform['runtime']['version'] and metadata['serverMainClass'] == 'net.minecraftforge.fml.relauncher.ServerLaunchWrapper' and metadata['allowedDownloadHosts'] == ALLOWED_DOWNLOAD_HOSTS and metadata['gameplayVersion'] == platform['gameplayBaseVersion'], 'Mac launch or gameplay metadata differs from pins')
        manifest = json.loads(archive.read(RESOURCES + 'package-manifest.json'))
        require(managed_hashes(manifest) == managed_hashes(frozen), 'Mac gameplay differs from accepted gameplay')
        require(managed_policies(manifest) == managed_policies(frozen) and retirement_policy(manifest) == retirement_policy(frozen), 'Mac preservation policies differ')
        require(manifest['version'] == metadata['version'], 'Mac manifest version mismatch')
        payload = archive.read(RESOURCES + 'payload.zip')
        require(sha(payload) == metadata['payloadSha256'] == manifest['archives'][0]['sha256'], 'Mac payload hash mismatch')
        with zipfile.ZipFile(io.BytesIO(payload)) as game:
            safe_entries(game)
            require(game.testzip() is None, 'Mac payload failed CRC')
            for entry in manifest['managedFiles']:
                if entry['path'] in downloads:
                    require(entry['path'] not in game.namelist(), 'Official-download vendor was rehosted in Mac payload')
                    continue
                require(sha(game.read(entry['path'])) == entry['sha256'], 'Mac managed file hash mismatch: ' + entry['path'])
            for entry in owned['mods']:
                require(sha(game.read(entry['path'])) == entry['sha256'], 'Mac owned module differs: ' + entry['path'])
        installer = json.loads(archive.read(RESOURCES + 'installer-files.json'))
        require(installer == expected_installer, 'Mac installer differs from pinned platform manifest')
        files = {entry['path']: entry for entry in installer['files']}
        require(len(files) == len(installer['files']), 'Duplicate Mac download path')
        require(all(name in files for name in installer['classpath']), 'Mac classpath file missing from download manifest')
        require(not any('natives-windows' in name or name.endswith(('.exe', '.dll')) for name in files), 'Windows download in Mac manifest')
        natives = [entry for entry in files.values() if entry.get('native')]
        require(len(natives) >= 3 and all('natives-osx' in entry['path'] for entry in natives), 'Mac natives incomplete')
        require(any('/2.9.2-nightly-20140822/' in name for name in installer['classpath']) and not any('/2.9.4-nightly-20150209/' in name for name in installer['classpath']), 'Incorrect Mojang Mac LWJGL selection')
        for name in (PREFIX + 'MacOS/RVLauncher', PREFIX + 'runtime/Contents/Home/bin/java', 'Open RV.command'):
            require((archive.getinfo(name).external_attr >> 16) & stat.S_IXUSR, 'Mac executable bit missing: ' + name)
        java = archive.read(PREFIX + 'runtime/Contents/Home/bin/java')
        require(java[:4] in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe'), 'Mac Java is not Mach-O')
        jar = archive.read(RESOURCES + 'rv-launcher.jar')
        require(sha(jar) == binding['jarSha256'], 'Mac launcher differs from frozen source build')
        for name, expected in binding['sourceHashes'].items():
            require(sha((ROOT / 'platform/macos/src' / name).read_bytes()) == expected, 'Mac launcher source changed: ' + name)
        require(launcher_sha is None or sha(jar) == launcher_sha, 'Mac launcher hash mismatch')
        with zipfile.ZipFile(io.BytesIO(jar)) as compiled:
            safe_entries(compiled)
            require(compiled.testzip() is None, 'Mac launcher JAR failed CRC')
            require('RVLauncher.class' in compiled.namelist(), 'Mac launcher entry point missing')
            for name in compiled.namelist():
                if name.startswith('RVLauncher') and name.endswith('.class'):
                    require(int.from_bytes(compiled.read(name)[6:8], 'big') == 52, 'Mac launcher is not Java 8')
        if 'worldTemplateSha256' in metadata:
            world = archive.read(RESOURCES + 'world-template.zip')
            require(sha(world) == metadata['worldTemplateSha256'] == platform['worldTemplate']['sha256'], 'Mac world template mismatch')
            with zipfile.ZipFile(io.BytesIO(world)) as template:
                safe_entries(template)
                require(template.testzip() is None, 'Mac world is corrupt')
                forbidden = private | {'logs', 'playerdata', 'stats', 'advancements', 'usernamecache.json'}
                require(not any(set(name.lower().split('/')) & forbidden for name in template.namelist()), 'Private data in Mac world')
        runtime_names = {name for name in names if name.startswith(PREFIX + 'runtime/')}
        require(runtime_names == {PREFIX + 'runtime/' + name for name in inventory['files']}, 'Mac runtime file set differs from pin')
        require(inventory['archiveSha256'] == platform['runtime']['sha256'], 'Mac runtime inventory pin mismatch')
        for name, expected in inventory['files'].items():
            entry = archive.getinfo(PREFIX + 'runtime/' + name)
            require(sha(archive.read(entry)) == expected['sha256'] and entry.file_size == expected['size'] and (entry.external_attr >> 16) & 0o777 == expected['mode'], 'Mac runtime differs from pin: ' + name)
        if runtime:
            require(sha(runtime.read_bytes()) == platform['runtime']['sha256'], 'Runtime verification input is not pinned')
            expected = set()
            with tarfile.open(runtime, 'r:gz') as tar:
                for entry in tar:
                    if not entry.isfile():
                        continue
                    require(entry.name.startswith(platform['runtime']['prefix']), 'Runtime prefix differs')
                    name = PREFIX + 'runtime/' + entry.name[len(platform['runtime']['prefix']):]
                    expected.add(name)
                    require(archive.read(name) == tar.extractfile(entry).read(), 'Mac runtime bytes changed: ' + name)
            require({name for name in names if name.startswith(PREFIX + 'runtime/')} == expected, 'Mac runtime file set differs')
    return dict(success=True, version=metadata['version'], bytes=package.stat().st_size,
                sha256=sha(package.read_bytes()), ownedModulesUnchanged=True, nativeMacRuntimeTested=False,
                launcherSha256=sha(jar), downloadFiles=len(files), macNativeArchives=len(natives))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--version')
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--launcher-sha')
    args = parser.parse_args()
    print(json.dumps(verify(args.package, args.version, args.runtime, args.launcher_sha)))
