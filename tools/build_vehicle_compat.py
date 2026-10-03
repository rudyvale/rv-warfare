import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--game', type=Path, default=Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Warfare-1.12.2')
parser.add_argument('--iv-jar', type=Path, required=True)
parser.add_argument('--output', type=Path, default=root / '.local/rv-1.2.0/vehicle-weapons/compat')
parser.add_argument('--compiler', type=Path, default=root / '.local/tools/ecj-4.6.1.jar')
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
sources = sorted((root / 'patches/compat').rglob('*.java'))
libraries = sorted((args.game / 'libraries').rglob('*.jar'))
classpath = os.pathsep.join(map(str, [args.iv_jar.resolve(strict=True), *libraries]))
with tempfile.TemporaryDirectory(prefix='compile-', dir=output) as directory:
    classes = Path(directory)
    subprocess.run([str(args.game / 'runtime/bin/java.exe'), '-jar', str(args.compiler), '-1.8', '-encoding', 'UTF-8', '-nowarn', '-cp', classpath, '-d', str(classes), *map(str, sources)], check=True)
    target = output / 'rv-vehicle-compat-1.2.0.jar'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(classes.rglob('*.class')):
            info = zipfile.ZipInfo(path.relative_to(classes).as_posix(), (2026, 10, 3, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo('META-INF/MANIFEST.MF', (2026, 10, 3, 0, 0, 0))
        archive.writestr(info, 'Manifest-Version: 1.0\r\n\r\n')
        info = zipfile.ZipInfo('NOTICE.txt', (2026, 10, 3, 0, 0, 0))
        archive.writestr(info, (root / 'patches/compat/NOTICE.txt').read_bytes())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert all(int.from_bytes(archive.read(name)[6:8], 'big') <= 52 for name in archive.namelist() if name.endswith('.class'))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = {'file': str(target), 'size': target.stat().st_size, 'sha256': digest(target), 'fmlId': 'rvcompat', 'version': '1.2.0', 'side': 'both', 'license': 'First-party RV; all rights retained', 'noticeSha256': digest(root / 'patches/compat/NOTICE.txt'), 'dependencies': {'optional': ['mts'], 'mandatory': []}, 'sources': [{'path': p.relative_to(root).as_posix(), 'sha256': digest(p)} for p in sources], 'recipe': {'path': Path(__file__).relative_to(root).as_posix(), 'sha256': digest(Path(__file__))}, 'compilerSha256': digest(args.compiler), 'ivCompileSha256': digest(args.iv_jar), 'javaTarget': 8, 'runtimeVerified': False}
    (output / 'build.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
