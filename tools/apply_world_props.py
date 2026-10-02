import argparse
import json
from pathlib import Path
import socket
import sys
import time
import zipfile

from decorate_world import Terrain, apply, empty_footprint, geometry, player_chunks, protected_chunks


parser = argparse.ArgumentParser()
parser.add_argument('--server-root',type=Path,required=True)
parser.add_argument('--world',type=Path,required=True)
parser.add_argument('--props-report',type=Path,required=True)
parser.add_argument('--preservation-report',type=Path,required=True)
parser.add_argument('--output-report',type=Path,required=True)
parser.add_argument('--python-libs',type=Path,required=True)
parser.add_argument('--apply',action='store_true')
args = parser.parse_args()
sys.path.insert(0,str(args.python_libs))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
import host_runtime

server,world = args.server_root.resolve(strict=True),args.world.resolve(strict=True)
if world.parent != server or args.output_report.resolve().is_relative_to(world):
    raise ValueError('The world must be a direct child of the named server; report stays outside it')
props = json.loads(args.props_report.read_text(encoding='utf-8'))['props']
if not isinstance(props,list) or not 1 <= len(props) <= 48:
    raise ValueError('Invalid bounded prop plan')
seen = set()
for prop in props:
    x,y,z = prop['x'],prop['y'],prop['z']
    if any(type(value) is not int for value in (x,y,z)) or y != 65 or not 320 <= max(abs(x),abs(z)) <= 600 or (x,z) in seen:
        raise ValueError('Prop plan lies outside verified outer staging bounds')
    seen.add((x,z))
    if prop['blocks'] != len(geometry(prop['type'],x,z)):
        raise ValueError('Prop geometry differs from its declared budget')
protected = protected_chunks(json.loads(args.preservation_report.read_text(encoding='utf-8')))
lock = host_runtime.acquire_lock(server)
if lock is None or host_runtime.server_status(server).get('state') in ('starting','running','stopping'):
    raise RuntimeError('Save and stop the server before preparing world changes')
with socket.socket() as listener:
    if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
        listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
    listener.bind(('127.0.0.1',host_runtime.server_port(server)))
    reserved = protected | player_chunks(world)
    terrain = Terrain(world)
    selected = [prop for prop in props if empty_footprint(terrain,prop['x'],prop['z'],reserved)]
    report = {'applied':args.apply,'plannedProps':len(props),'safeProps':len(selected),'skippedProps':len(props)-len(selected),'protectedLegacyChunks':len(protected),'snapshot':None}
    if args.apply and selected:
        backup = server/'backups'/('world-props-'+str(time.time_ns()))
        backup.mkdir(parents=True)
        snapshot = backup/'world-before.zip'
        with zipfile.ZipFile(snapshot,'x',zipfile.ZIP_DEFLATED,compresslevel=4) as archive:
            for path in sorted(world.rglob('*')):
                if path.is_file():
                    if not path.resolve().is_relative_to(world):
                        raise ValueError('World snapshot contains a path outside the named world')
                    archive.write(path,world.name+'/'+path.relative_to(world).as_posix())
            for name in ('server.properties','vm-owner.properties','vm-owner.json','ops.json','whitelist.json'):
                path = server/name
                if path.is_file():archive.write(path,name)
        with zipfile.ZipFile(snapshot) as archive:
            if archive.testzip() is not None:
                raise ValueError('World snapshot failed verification')
        report.update(apply(world,selected,protected))
        report['snapshot']=str(snapshot)
args.output_report.parent.mkdir(parents=True,exist_ok=True)
args.output_report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({key:value for key,value in report.items() if key!='props'}))
