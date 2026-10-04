import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

from build_macos import ROOT, launcher_jar, obtain, read_json


def check(java, cache, runtime_check=False):
    pins = read_json(ROOT / 'pack/macos-platform.json')
    cache.mkdir(parents=True, exist_ok=True)
    for name in ('compiler', 'gson'):
        obtain(pins[name], cache, 'sha256')
    with tempfile.TemporaryDirectory(prefix='rv-mac-source-') as temporary:
        output = Path(temporary) / 'launcher'
        jar = launcher_jar(ROOT / 'platform/macos/src', java, cache / pins['compiler']['sha256'], cache / pins['gson']['sha256'], output)
        receipt = read_json(output / 'build.json')
        frozen = read_json(ROOT / 'pack/macos-launcher.json')
        if receipt != frozen:
            raise ValueError('Compiled Mac launcher differs from frozen source build')
        tests = ROOT / 'platform/macos/tests'
        if tests.exists():
            files = sorted(tests.rglob('*.java'))
            if files:
                result = subprocess.run([str(java), '-jar', str(cache / pins['compiler']['sha256']), '-source', '1.8', '-target', '1.8', '-encoding', 'UTF-8', '-cp', str(jar), '-d', str(output / 'tests'), *map(str, files)], capture_output=True, text=True)
                if result.returncode:
                    raise ValueError('Mac launcher test compilation failed: ' + result.stderr)
                result = subprocess.run([str(java), '-Djava.awt.headless=true', '-cp', str(output / 'tests') + os.pathsep + str(jar), 'RVLauncherSelfTest'], capture_output=True, text=True, timeout=60)
                if result.returncode:
                    raise ValueError('Mac launcher component checks failed: ' + result.stdout + result.stderr)
        runtime_started = False
        if runtime_check:
            if sys.platform != 'darwin':
                raise ValueError('The bundled Mac runtime must be tested on macOS')
            obtain(pins['runtime'], cache, 'sha256')
            runtime_root = Path(temporary) / 'runtime'
            with tarfile.open(cache / pins['runtime']['sha256'], 'r:gz') as archive:
                for entry in archive:
                    if entry.isdir():
                        continue
                    if not entry.isfile() or not entry.name.startswith(pins['runtime']['prefix']):
                        raise ValueError('Unsafe runtime entry')
                    name = entry.name[len(pins['runtime']['prefix']):]
                    if any(part in ('', '.', '..') for part in name.split('/')):
                        raise ValueError('Unsafe runtime path')
                    target = runtime_root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(entry).read())
                    target.chmod(entry.mode & 0o777)
            result = subprocess.run([str(runtime_root / 'Contents/Home/bin/java'), '-version'], capture_output=True, text=True, timeout=20)
            if result.returncode or pins['runtime']['version'] not in result.stderr:
                raise ValueError('Bundled Mac Java did not start at the pinned version')
            runtime_started = True
        return dict(success=True, javaTarget=8, sourceFiles=len(receipt['sourceHashes']), launcherSha256=receipt['jarSha256'], bundledMacRuntimeStarted=runtime_started, nativeMacGameTested=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--java', type=Path, default=Path(shutil.which('java') or 'java'))
    parser.add_argument('--cache', type=Path, default=ROOT / '.local/macos-platform-cache')
    parser.add_argument('--runtime-check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.java, args.cache, args.runtime_check)))
