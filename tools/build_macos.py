import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import plistlib
import re
import stat
import subprocess
import tarfile
import urllib.parse
import urllib.request
import zipfile

from download_release_base import safe_entries
from release_contract import validate_base


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DOWNLOAD_HOSTS = ['libraries.minecraft.net', 'maven.minecraftforge.net', 'piston-data.mojang.com',
                          'piston-meta.mojang.com', 'resources.download.minecraft.net', 'cdn.modrinth.com',
                          'edge.forgecdn.net', 'mediafilez.forgecdn.net']


def digest(data, algorithm='sha256'):
    return hashlib.new(algorithm, data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def obtain(entry, cache, algorithm):
    name = entry[algorithm]
    path = cache / name
    if not path.exists():
        url = entry['url']
        parsed = urllib.parse.urlsplit(url)
        allowed = {'piston-meta.mojang.com', 'piston-data.mojang.com', 'libraries.minecraft.net', 'github.com', 'archive.eclipse.org'}
        if parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.username or parsed.password:
            raise ValueError('Unapproved platform download')
        request = urllib.request.Request(url, headers={'User-Agent': 'RV-platform-builder'})
        temporary = path.with_suffix('.partial')
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open('wb') as stream:
            total = 0
            limit = entry.get('size', 64 * 1024 * 1024)
            while True:
                data = response.read(1024 * 1024)
                if not data:
                    break
                total += len(data)
                if total > limit:
                    raise ValueError('Platform download exceeds its size')
                stream.write(data)
        temporary.replace(path)
    data = path.read_bytes()
    if digest(data, algorithm) != name or 'size' in entry and len(data) != entry['size']:
        raise ValueError('Platform download digest mismatch')
    return data


def osx_allowed(library):
    rules = library.get('rules')
    if rules is None:
        return True
    allowed = False
    for rule in rules:
        os = rule.get('os', {})
        if os.get('name', 'osx') != 'osx':
            continue
        if 'version' in os and not re.search(os['version'], '10.13.0'):
            continue
        if 'arch' in os and not re.search(os['arch'], 'x86_64'):
            continue
        if rule.get('features'):
            continue
        allowed = rule['action'] == 'allow'
    return allowed


def installer_for_macos(installer, minecraft):
    old = {entry['path']: entry for entry in installer['files']}
    vanilla_paths = set()
    additions = {}
    platform_classpath = []
    for library in minecraft['libraries']:
        downloads = library.get('downloads', {})
        artifact = downloads.get('artifact')
        if artifact:
            vanilla_paths.add('libraries/' + artifact['path'])
        for item in downloads.get('classifiers', {}).values():
            vanilla_paths.add('libraries/' + item['path'])
        if not osx_allowed(library):
            continue
        if artifact:
            path = 'libraries/' + artifact['path']
            additions[path] = dict(path=path, url=artifact['url'], sha1=artifact['sha1'], native=False)
            if path not in platform_classpath:
                platform_classpath.append(path)
        classifier = library.get('natives', {}).get('osx')
        if classifier:
            item = downloads['classifiers'][classifier.replace('${arch}', '64')]
            path = 'libraries/' + item['path']
            additions[path] = dict(path=path, url=item['url'], sha1=item['sha1'], native=True)
    files = {name: entry for name, entry in old.items() if name not in vanilla_paths and not entry.get('native')}
    files.update(additions)
    classpath = platform_classpath + [name for name in installer['classpath'] if name not in vanilla_paths]
    return dict(mainClass=installer['mainClass'], assetIndex=installer['assetIndex'],
                files=[files[name] for name in sorted(files)], classpath=classpath)


def put(archive, name, data, mode=0o644):
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ('', '.', '..') for part in path.parts) or ':' in name or '\\' in name:
        raise ValueError('Unsafe macOS package path')
    info = zipfile.ZipInfo(name, date_time=(2026, 10, 4, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def launcher_jar(source, java, compiler, gson, output):
    pins = read_json(ROOT / 'pack/macos-platform.json')
    for path, name in ((compiler, 'compiler'), (gson, 'gson')):
        if digest(path.read_bytes()) != pins[name]['sha256'] or path.stat().st_size != pins[name]['size']:
            raise ValueError('Unpinned launcher build dependency: ' + name)
    if output.exists():
        raise ValueError('Launcher build output already exists')
    output.mkdir(parents=True)
    classes = output / 'classes'
    classes.mkdir()
    inputs = sorted(source.rglob('*.java'))
    if not inputs:
        raise ValueError('macOS launcher source is missing')
    compile_dependency = output / 'gson-2.8.0.jar'
    compile_dependency.write_bytes(gson.read_bytes())
    command = [str(java), '-jar', str(compiler), '-source', '1.8', '-target', '1.8', '-encoding', 'UTF-8',
               '-cp', str(compile_dependency), '-d', str(classes), *map(str, inputs)]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    (output / 'compiler.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise ValueError('macOS launcher Java 8 compilation failed: ' + result.stdout + result.stderr)
    jar = output / 'rv-launcher.jar'
    with zipfile.ZipFile(jar, 'x', zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
        put(archive, 'META-INF/MANIFEST.MF', b'Manifest-Version: 1.0\r\nMain-Class: RVLauncher\r\n\r\n')
        for file in sorted(classes.rglob('*.class')):
            data = file.read_bytes()
            if int.from_bytes(data[6:8], 'big') != 52:
                raise ValueError('Launcher class is not Java 8')
            put(archive, file.relative_to(classes).as_posix(), data)
        with zipfile.ZipFile(gson) as dependency:
            safe_entries(dependency)
            for name in sorted(dependency.namelist()):
                if name.startswith('com/google/gson/') and not name.endswith('/'):
                    put(archive, name, dependency.read(name))
        put(archive, 'META-INF/RV-NOTICE.txt', b'RV Warfare launcher. Includes Gson 2.8.0, Copyright Google Inc., Apache License 2.0.\nhttps://github.com/google/gson/blob/gson-parent-2.8.0/LICENSE\n')
        put(archive, 'META-INF/GSON-LICENSE.txt', (ROOT / 'platform/macos/GSON-LICENSE.txt').read_bytes())
    (output / 'build.json').write_text(json.dumps(dict(javaTarget=8, sourceHashes={file.relative_to(source).as_posix(): digest(file.read_bytes()) for file in inputs}, gsonSha256=digest(gson.read_bytes()), jarSha256=digest(jar.read_bytes())), indent=2) + '\n', encoding='utf-8')
    return jar


def build(base, launcher, output, cache, runtime_archive=None, world=None, version='2.0.4'):
    if output.exists():
        raise ValueError('macOS package output already exists')
    platform = read_json(ROOT / 'pack/macos-platform.json')
    manifest = validate_base(base, ROOT / 'pack/package-manifest.json')
    installer = read_json(base / 'installer-files.json')
    cache.mkdir(parents=True, exist_ok=True)
    minecraft = json.loads(obtain(platform['minecraftMetadata'], cache, 'sha1'))
    mac_installer = installer_for_macos(installer, minecraft)
    runtime = runtime_archive.read_bytes() if runtime_archive else obtain(platform['runtime'], cache, 'sha256')
    if digest(runtime) != platform['runtime']['sha256'] or len(runtime) != platform['runtime']['size']:
        raise ValueError('Mac runtime does not match its pin')
    native_hashes = {}
    for entry in mac_installer['files']:
        if entry.get('native'):
            data = obtain(entry, cache, 'sha1')
            native_hashes[entry['path']] = digest(data)
            with zipfile.ZipFile(cache / entry['sha1']) as archive:
                safe_entries(archive)
                if archive.testzip() is not None or not any(name.endswith(('.dylib', '.jnilib')) for name in archive.namelist()):
                    raise ValueError('Mac native library is missing')
    payload = (base / 'payload.zip').read_bytes()
    with zipfile.ZipFile(base / 'payload.zip') as archive:
        safe_entries(archive)
        if archive.testzip() is not None or any(name.lower().endswith(('.exe', '.dll')) for name in archive.namelist()):
            raise ValueError('Payload is corrupt or contains Windows executables')
    guide = (ROOT / 'pack/READ-ME.md').read_bytes()
    rewritten = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(payload)) as old, zipfile.ZipFile(rewritten, 'w', zipfile.ZIP_DEFLATED, compresslevel=4) as new:
        for entry in old.infolist():
            new.writestr(entry, guide if entry.filename == 'READ-ME.md' else old.read(entry.filename))
    payload = rewritten.getvalue()
    for entry in manifest['managedFiles']:
        if entry['path'] == 'READ-ME.md':
            entry['sha256'] = digest(guide)
    manifest['version'] = version
    manifest['archives'] = [dict(path='payload.zip', sha256=digest(payload))]
    metadata = dict(schema=1, version=version, gameplayVersion=read_json(base / 'package-manifest.json')['version'],
                    payloadSha256=digest(payload), runtimePlatform='mac-x64', javaVersion=platform['runtime']['version'],
                    server=platform['server'], serverMainClass='net.minecraftforge.fml.relauncher.ServerLaunchWrapper',
                    allowedDownloadHosts=ALLOWED_DOWNLOAD_HOSTS)
    if world:
        if digest(world.read_bytes()) != platform['worldTemplate']['sha256'] or world.stat().st_size != platform['worldTemplate']['size']:
            raise ValueError('World template differs from the frozen clean map')
        metadata['worldTemplateSha256'] = digest(world.read_bytes())
    output.mkdir(parents=True)
    package = output / 'RV-Mac-Setup.zip'
    prefix = 'RV.app/Contents/'
    shell = (ROOT / 'platform/macos/RVLauncher.sh').read_text()
    plist = dict(CFBundleName='RV', CFBundleDisplayName='RV Warfare', CFBundleIdentifier='com.rudyvale.rvwarfare',
                 CFBundleExecutable='RVLauncher', CFBundlePackageType='APPL', CFBundleShortVersionString=version,
                 CFBundleVersion=version, LSMinimumSystemVersion=platform['minimumSystemVersion'], NSHighResolutionCapable=True)
    with zipfile.ZipFile(package, 'x', zipfile.ZIP_DEFLATED, compresslevel=4) as archive:
        put(archive, prefix + 'Info.plist', plistlib.dumps(plist))
        put(archive, prefix + 'MacOS/RVLauncher', shell.encode(), 0o755)
        with tarfile.open(runtime_archive or cache / platform['runtime']['sha256'], 'r:gz') as tar:
            found_java = False
            for member in tar:
                if member.isdir():
                    continue
                if not member.isfile() or not member.name.startswith(platform['runtime']['prefix']):
                    raise ValueError('Unexpected runtime archive entry')
                relative = member.name[len(platform['runtime']['prefix']):]
                data = tar.extractfile(member).read()
                put(archive, prefix + 'runtime/' + relative, data, member.mode & 0o777)
                found_java |= relative == 'Contents/Home/bin/java'
            if not found_java:
                raise ValueError('Mac Java executable is missing')
        resources = {'rv-launcher.jar': launcher.read_bytes(), 'payload.zip': payload,
                     'installer-files.json': (json.dumps(mac_installer, indent=2) + '\n').encode(),
                     'package-manifest.json': (json.dumps(manifest, indent=2) + '\n').encode()}
        for name in ('vendor-catalog.json', 'rv-managed-mods.json', 'release.json', 'THIRD-PARTY-NOTICES.md'):
            file = ROOT / ('src' if name == 'release.json' else 'pack') / name
            resources[name] = file.read_bytes()
        release = read_json(ROOT / 'src/release.json')
        release['version'] = version
        resources['release.json'] = (json.dumps(release, indent=2) + '\n').encode()
        resources['macos-package.json'] = (json.dumps(metadata, indent=2) + '\n').encode()
        if world:
            resources['world-template.zip'] = world.read_bytes()
        for name, data in resources.items():
            put(archive, prefix + 'Resources/' + name, data)
        readme = ROOT / 'platform/macos/README.md'
        if readme.exists():
            put(archive, 'READ-ME.md', readme.read_bytes())
        put(archive, 'Open RV.command', (ROOT / 'platform/macos/Open RV.command').read_bytes(), 0o755)
    with zipfile.ZipFile(package) as archive:
        safe_entries(archive)
        if archive.testzip() is not None:
            raise ValueError('Built macOS package failed CRC')
    receipt = dict(version=version, packageSha256=digest(package.read_bytes()), bytes=package.stat().st_size,
                   launcherSha256=digest(launcher.read_bytes()), payloadSha256=digest(payload),
                   runtimeSha256=platform['runtime']['sha256'], nativeArchiveSha256=native_hashes,
                   nativeMacRuntimeTested=False, gameplayBinariesUnchanged=True)
    (output / 'macos-build.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    (output / 'MAC-SHA256SUMS.txt').write_text(receipt['packageSha256'] + '  RV-Mac-Setup.zip\n', encoding='ascii')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--launcher', type=Path)
    parser.add_argument('--compile-source', type=Path)
    parser.add_argument('--java', type=Path)
    parser.add_argument('--compiler', type=Path)
    parser.add_argument('--gson', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=ROOT / '.local/macos-platform-cache')
    parser.add_argument('--runtime-archive', type=Path)
    parser.add_argument('--world', type=Path)
    parser.add_argument('--version', default='2.0.4')
    args = parser.parse_args()
    jar = args.launcher
    if args.compile_source:
        if not args.java:
            parser.error('Compilation requires --java')
        pins = read_json(ROOT / 'pack/macos-platform.json')
        args.cache.mkdir(parents=True, exist_ok=True)
        for name in ('compiler', 'gson'):
            if getattr(args, name) is None:
                obtain(pins[name], args.cache, 'sha256')
                setattr(args, name, args.cache / pins[name]['sha256'])
        jar = launcher_jar(args.compile_source, args.java, args.compiler, args.gson, args.output.with_name(args.output.name + '-launcher'))
    if not jar:
        parser.error('Supply --launcher or --compile-source')
    print(json.dumps(build(args.base, jar, args.output, args.cache, args.runtime_archive, args.world, args.version)))
