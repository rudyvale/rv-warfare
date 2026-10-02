import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--game',type=Path,default=Path(os.environ.get('RV_GAME_ROOT',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'Warfare-1.12.2'))))
parser.add_argument('--base-jar',type=Path,required=True)
parser.add_argument('--output',type=Path,default=root/'.local/controls')
args=parser.parse_args()
game=args.game
output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
asm=next((game/'libraries').rglob('asm-debug-all-5.2.jar'))
cp=os.pathsep.join([str(game/'runtime/lib/ext/nashorn.jar'),str(asm)])
with tempfile.TemporaryDirectory(prefix='props-',dir=output) as folder:
    result=subprocess.run([str(game/'runtime/bin/java.exe'),'-cp',cp,'jdk.nashorn.tools.Shell',str(root/'patches/controls/patch-props.js'),'--',str(args.base_jar),folder],capture_output=True,text=True)
    if result.returncode:print(result.stderr)
    result.check_returncode()
    target=output/'techguns-1.12.2-2.0.2.0-rv-gameplay.jar'
    with zipfile.ZipFile(args.base_jar) as old,zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for item in old.infolist():
            changed=Path(folder)/item.filename
            archive.writestr(item,changed.read_bytes() if changed.is_file() else old.read(item.filename))
    with zipfile.ZipFile(target) as archive:assert archive.testzip() is None
report={'jar':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'base_sha256':hashlib.sha256(args.base_jar.read_bytes()).hexdigest(),'hooks':json.loads(result.stdout),'requires_mcheli_version':'1.5.1-rv-controls1'}
(output/'props-build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
