import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--game', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'Warfare-1.12.2')
parser.add_argument('--output', type=Path, default=root / '.local/rv-2.0.0/role4/build')
parser.add_argument('--compiler', type=Path, default=root / '.local/tools/ecj-4.6.1.jar')
parser.add_argument('--stubs', type=Path, default=root / 'patches/experience-api')
parser.add_argument('--controls-jar', type=Path)
parser.add_argument('--server-only', action='store_true')
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
sources = sorted((root / 'patches/experience').rglob('*.java'))
if args.server_only:
    sources = [path for path in sources if 'client' not in path.relative_to(root / 'patches/experience').parts]
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
captured = {path.relative_to(root).as_posix(): digest(path) for path in sources}
captured['patches/experience/NOTICE.txt'] = digest(root / 'patches/experience/NOTICE.txt')
captured['tools/build_experience.py'] = digest(Path(__file__))
stub_sources = sorted(args.stubs.rglob('*.java'))
if not args.server_only and not stub_sources:
    raise ValueError('The client build requires the compile-only API sources')
api_sources = {path.relative_to(args.stubs).as_posix(): digest(path) for path in stub_sources}
for path in stub_sources:
    if path.resolve().is_relative_to(root):
        captured[path.resolve().relative_to(root).as_posix()] = digest(path)
libraries = sorted((args.game / 'libraries').rglob('*.jar'))
controls = (args.controls_jar or args.game / 'mods/mcheli-ce-1.5.1-rv.jar').resolve(strict=True)
libraries.insert(0, controls)
classpath = os.pathsep.join(str(path) for path in libraries)
java = args.game / 'runtime/bin/java.exe'
with tempfile.TemporaryDirectory(prefix='compile-', dir=output) as temporary:
    classes = Path(temporary)
    stub_classes = classes / 'compile-api'
    if stub_sources:
        subprocess.run([str(java), '-jar', str(args.compiler), '-1.8', '-encoding', 'UTF-8', '-nowarn', '-cp', classpath, '-d', str(stub_classes), *map(str, stub_sources)], check=True)
        classpath = str(stub_classes) + os.pathsep + classpath
    target_classes = classes / 'artifact'
    subprocess.run([str(java), '-jar', str(args.compiler), '-1.8', '-encoding', 'UTF-8', '-nowarn', '-cp', classpath, '-d', str(target_classes), *map(str, sources)], check=True)
    if not all(digest(root / name) == checksum for name, checksum in captured.items()) or not all(digest(args.stubs / name) == checksum for name, checksum in api_sources.items()):
        raise ValueError('Source changed during build')
    target = output / 'mods/rv-experience-2.0.0.jar'
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(target_classes.rglob('*.class')):
            name = path.relative_to(target_classes).as_posix()
            if not name.startswith('rv/experience/'):
                raise ValueError('Compile-only API leaked into artifact')
            data = path.read_bytes()
            if int.from_bytes(data[6:8], 'big') > 52:
                raise ValueError('The artifact contains a class newer than Java 8')
            info = zipfile.ZipInfo(name, (2026, 10, 3, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
        archive.writestr(zipfile.ZipInfo('META-INF/MANIFEST.MF', (2026, 10, 3, 0, 0, 0)), 'Manifest-Version: 1.0\r\n\r\n')
        archive.writestr(zipfile.ZipInfo('NOTICE.txt', (2026, 10, 3, 0, 0, 0)), (root / 'patches/experience/NOTICE.txt').read_bytes())
    receipt = {'schema': 1, 'id': 'rvexperience', 'version': '2.0.0', 'side': 'server' if args.server_only else 'both', 'path': str(target), 'size': target.stat().st_size, 'sha256': digest(target), 'sourceFiles': captured, 'compileApiSources': api_sources, 'compilerSha256': digest(args.compiler), 'controlsCompileSha256': digest(controls), 'javaTarget': 8, 'compileOnlyApiExcluded': True, 'nativeVerified': False}
    (output / 'build.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'path': str(target), 'size': receipt['size'], 'sha256': receipt['sha256'], 'sourceFiles': len(captured), 'side': receipt['side']}))
