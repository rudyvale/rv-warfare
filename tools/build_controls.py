import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--game', type=Path, default=Path(os.environ.get('RV_GAME_ROOT',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Warfare-1.12.2'))))
parser.add_argument('--base-jar', type=Path, required=True)
parser.add_argument('--owner-source', type=Path)
parser.add_argument('--output', type=Path, default=root/'.local/controls')
parser.add_argument('--compiler', type=Path, default=Path(os.environ.get('RV_ECJ_JAR',str(root/'.local/tools/ecj-4.6.1.jar'))))
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
compile_directory = tempfile.TemporaryDirectory(prefix='compile-',dir=output)
classes = Path(compile_directory.name)
java = args.game/'runtime/bin/java.exe'
base = args.base_jar
libraries = list((args.game/'libraries').rglob('*.jar'))
cp = os.pathsep.join(str(p) for p in libraries)
sources = sorted((root/'patches/controls').glob('*.java'))
if args.owner_source:
    sources.append(args.owner_source.resolve(strict=True))
subprocess.run([str(java), '-jar', str(args.compiler), '-1.8', '-encoding', 'UTF-8', '-nowarn', '-classpath', cp, '-d', str(classes), *map(str, sources)], check=True)
asm = next(p for p in libraries if p.name == 'asm-debug-all-5.2.jar')
nashorn_cp = os.pathsep.join([str(args.game/'runtime/lib/ext/nashorn.jar'),str(asm)])
result=subprocess.run([str(java), '-cp', nashorn_cp, 'jdk.nashorn.tools.Shell', str(root/'patches/controls/patch-controls.js'), '--', str(base), str(classes), 'owner' if args.owner_source else 'controls'],text=True,capture_output=True)
if result.returncode:print(result.stderr)
result.check_returncode()
print(result.stdout)
resources=root/'patches/controls/resources'
if resources.exists():
    shutil.copytree(resources,classes,dirs_exist_ok=True)
target=output/'mcheli-ce-1.5.1-vm-controls1.jar'
with zipfile.ZipFile(base) as old, zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
    prior=set(old.namelist())
    for item in old.infolist():
        replacement=classes/item.filename
        archive.writestr(item,replacement.read_bytes() if replacement.is_file() else old.read(item.filename))
    for source in sorted(classes.rglob('*')):
        if not source.is_file():continue
        name=source.relative_to(classes).as_posix()
        if name not in prior:archive.write(source,name)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert len(archive.namelist())==len(set(archive.namelist()))
report={'jar':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'base_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'hooks':json.loads(result.stdout),'hardware_tested':False}
if args.owner_source:report['owner_source_sha256']=hashlib.sha256(args.owner_source.read_bytes()).hexdigest()
(output/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
