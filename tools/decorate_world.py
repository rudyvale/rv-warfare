import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import zlib

from merge_world_regions import records


def load_chunk(raw):
    import nbtlib
    length = struct.unpack_from('>I', raw)[0]
    decode = gzip.decompress if raw[4] == 1 else zlib.decompress
    chunk = nbtlib.File.parse(io.BytesIO(decode(raw[5:4 + length])))
    for section in chunk['Level']['Sections']:
        for name in ('Blocks','Data','BlockLight','SkyLight','Add'):
            if name in section:
                section[name] = nbtlib.ByteArray([int(value) for value in section[name]])
    if 'HeightMap' in chunk['Level']:
        chunk['Level']['HeightMap'] = nbtlib.IntArray([int(value) for value in chunk['Level']['HeightMap']])
    return chunk


def block(chunk, x, y, z):
    for section in chunk['Level']['Sections']:
        if int(section['Y']) == y // 16:
            index = (y % 16) * 256 + (z % 16) * 16 + x % 16
            value = int(section['Blocks'][index]) & 255
            if 'Add' in section:
                value |= ((int(section['Add'][index // 2]) & 255) >> (4 * (index % 2)) & 15) << 8
            return value
    return 0


def set_block(chunk, x, y, z, value, metadata):
    import nbtlib
    section = next((item for item in chunk['Level']['Sections'] if int(item['Y']) == y // 16), None)
    if section is None:
        section = nbtlib.Compound({'Y': nbtlib.Byte(y // 16), 'Blocks': nbtlib.ByteArray([0] * 4096), 'Data': nbtlib.ByteArray([0] * 2048), 'BlockLight': nbtlib.ByteArray([0] * 2048), 'SkyLight': nbtlib.ByteArray([-1] * 2048)})
        chunk['Level']['Sections'].append(section)
    index = (y % 16) * 256 + (z % 16) * 16 + x % 16
    section['Blocks'][index] = value if value < 128 else value - 256
    shift = 4 * (index % 2)
    encoded = ((int(section['Data'][index // 2]) & 255) & ~(15 << shift)) | metadata << shift
    section['Data'][index // 2] = encoded if encoded < 128 else encoded - 256
    if 'Add' in section:
        encoded = (int(section['Add'][index // 2]) & 255) & ~(15 << shift)
        section['Add'][index // 2] = encoded if encoded < 128 else encoded - 256
    heights = chunk['Level'].get('HeightMap')
    if heights is not None:
        column = (z % 16) * 16 + x % 16
        heights[column] = max(int(heights[column]), y + 1)
    chunk['Level']['LightPopulated'] = nbtlib.Byte(0)


def geometry(kind, x, z):
    cells = {}
    def box(x1, y1, z1, x2, y2, z2, material, data=0):
        for xx in range(x + x1, x + x2 + 1):
            for yy in range(y1, y2 + 1):
                for zz in range(z + z1, z + z2 + 1):
                    cells[xx, yy, zz] = material, data
    if kind == 'sandbag_cover':
        box(-4,65,-2,4,65,-2,24)
        box(-4,65,-1,-4,66,2,24)
        box(4,65,-1,4,66,2,24)
        box(-4,66,-2,-1,66,-2,44,1)
        box(1,66,-2,4,66,-2,44,1)
    elif kind == 'supply_crates':
        for xx, zz in [(-3,-2),(1,1)]:
            box(xx,65,zz,xx+1,66,zz+1,17)
            box(xx,66,zz,xx+1,66,zz+1,5)
    elif kind == 'wreck':
        box(-3,65,-1,3,65,1,42)
        box(-1,66,-1,2,66,1,101)
        box(0,67,-1,2,67,1,42)
        for xx in [-2,2]:
            for zz in [-2,2]:
                box(xx,65,zz,xx,65,zz,35,15)
    elif kind == 'checkpoint':
        box(-4,65,-2,-2,65,2,98,2)
        box(2,65,-2,4,65,2,98,2)
        box(-4,66,-2,-4,67,2,85)
        box(4,66,-2,4,67,2,85)
        box(-4,68,-2,-4,68,2,5)
        box(4,68,-2,4,68,2,5)
    elif kind == 'barricade':
        box(-4,65,0,4,65,0,98,2)
        for xx in [-4,-2,0,2,4]:
            box(xx,66,0,xx,66,0,53,2)
        box(-4,65,-2,-3,65,-2,5)
        box(3,65,2,4,65,2,5)
    else:
        raise ValueError('Unknown prop type')
    return cells


class Terrain:
    def __init__(self, world):
        self.world = Path(world)
        self.regions = {}
        self.chunks = {}
    def chunk(self, x, z):
        cx, cz = x // 16, z // 16
        key = cx, cz
        if key not in self.chunks:
            name = f'r.{cx//32}.{cz//32}.mca'
            if name not in self.regions:
                path = self.world / 'region' / name
                self.regions[name] = path.read_bytes(), records(path.read_bytes())
            record = self.regions[name][1].get(cx % 32 + (cz % 32) * 32)
            if record is None:
                raise ValueError('Prop would enter an ungenerated chunk')
            self.chunks[key] = load_chunk(record[2])
        return self.chunks[key]


def protected_chunks(report):
    result = set()
    for region in report['regions']:
        _, rx, rz, _ = region['file'].split('.')
        for index in region['originalRecords']:
            number = int(index)
            result.add((int(rx) * 32 + number % 32, int(rz) * 32 + number // 32))
    return result


def player_chunks(world):
    import nbtlib
    result = set()
    for path in (Path(world)/'playerdata').glob('*.dat'):
        player = nbtlib.load(path)
        if int(player.get('Dimension',0)) != 0:
            continue
        position = player.get('Pos')
        if position is None or len(position) != 3:
            raise ValueError('Cannot verify an offline player position')
        x,z = float(position[0]),float(position[2])
        import math
        for xx in range(math.floor(x-8)//16,math.floor(x+8)//16+1):
            for zz in range(math.floor(z-8)//16,math.floor(z+8)//16+1):
                result.add((xx,zz))
    return result


def empty_footprint(terrain, x, z, protected):
    chunks = {(xx//16,zz//16) for xx in range(x-7,x+8) for zz in range(z-7,z+8)}
    if chunks & protected:
        return False
    for xx in range(x-7,x+8):
        for zz in range(z-7,z+8):
            chunk = terrain.chunk(xx,zz)
            if block(chunk,xx,64,zz) != 2 or any(block(chunk,xx,y,zz) != 0 for y in range(65,72)):
                return False
    for cx,cz in chunks:
        level = terrain.chunk(cx*16,cz*16)['Level']
        for key in ('Entities','TileEntities','TileTicks'):
            if level.get(key):
                return False
    return True


def plan(world, protected):
    protected = protected | player_chunks(world)
    terrain = Terrain(world)
    kinds = ['sandbag_cover','supply_crates','wreck','checkpoint','barricade']
    props = []
    candidates = [(x,z) for z in range(-560,561,80) for x in range(-560,561,80) if max(abs(x),abs(z)) >= 320]
    candidates.sort(key=lambda at: hashlib.sha256(f'RV-1.1:{at[0]}:{at[1]}'.encode()).digest())
    for x,z in candidates:
        if empty_footprint(terrain,x,z,protected):
            kind = kinds[len(props)%len(kinds)]
            props.append({'type':kind,'x':x,'y':65,'z':z,'blocks':len(geometry(kind,x,z))})
            if len(props) == 48:
                break
    return props


def apply(world, props, protected):
    protected = protected | player_chunks(world)
    terrain = Terrain(world)
    modified = set()
    for prop in props:
        x,z = prop['x'],prop['z']
        if not empty_footprint(terrain,x,z,protected):
            raise ValueError('Prop footprint changed; no region files written')
        for (xx,yy,zz),(value,metadata) in geometry(prop['type'],x,z).items():
            if block(terrain.chunk(xx,zz),xx,yy,zz) != 0:
                raise ValueError('Prop would replace an existing block')
            set_block(terrain.chunk(xx,zz),xx,yy,zz,value,metadata)
            modified.add((xx//16,zz//16))
    files = []
    untouched = 0
    for path in sorted((Path(world)/'region').glob('r.*.*.mca')):
        old = path.read_bytes()
        before = records(old)
        _,rx,rz,_ = path.name.split('.')
        rx,rz = int(rx),int(rz)
        edits = {index:(rx*32+index%32,rz*32+index//32) for index in before if (rx*32+index%32,rz*32+index//32) in modified}
        if not edits:
            untouched += len(before)
            continue
        result = bytearray(old)
        for index,key in edits.items():
            stream = io.BytesIO()
            terrain.chunks[key].write(stream)
            encoded = zlib.compress(stream.getvalue(),9)
            raw = struct.pack('>I',len(encoded)+1) + b'\x02' + encoded
            count = (len(raw)+4095)//4096
            if count > 255 or len(result)//4096 > 0xFFFFFF:
                raise ValueError('Region allocation limit exceeded')
            result[index*4:index*4+4] = ((len(result)//4096<<8)|count).to_bytes(4,'big')
            result.extend(raw + bytes(count*4096-len(raw)))
        after = records(result)
        if any(after[index] != record for index,record in before.items() if index not in edits):
            raise ValueError('Unrelated chunk record changed')
        files.append((path,old,bytes(result),len(edits)))
        untouched += len(before)-len(edits)
    for path,old,result,_ in files:
        if path.read_bytes() != old:
            raise ValueError('World changed during staging; no files written')
    for path,_,result,_ in files:
        temporary = path.with_suffix('.mca.rv-props-new')
        with temporary.open('xb') as stream:
            stream.write(result)
        temporary.replace(path)
    return {'modifiedChunks':len(modified),'untouchedChunkRecordsExact':untouched,'addedEntities':0,'addedTileEntities':0,'props':props,'blocks':sum(prop['blocks'] for prop in props)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--template',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preservation-report',type=Path,required=True)
    parser.add_argument('--python-libs',type=Path)
    args = parser.parse_args()
    if args.python_libs:
        sys.path.insert(0,str(args.python_libs))
    source,output = args.template.resolve(strict=True),args.output.resolve()
    if output.exists() or source in output.parents or output in source.parents:
        raise ValueError('Output must be a new directory outside the source template')
    protected = protected_chunks(json.loads(args.preservation_report.read_text(encoding='utf-8')))
    props = plan(source,protected)
    if len(props) < 20:
        raise ValueError('Too few verified empty outer footprints')
    shutil.copytree(source,output)
    result = apply(output,props,protected)
    result['protectedLegacyChunks'] = len(protected)
    result['sourceWorld'] = str(source)
    result['files'] = {path.relative_to(output).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.rglob('*')) if path.is_file()}
    (output.parent/'props-report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    source_manifest = source.parent/'world-template-manifest.json'
    if source_manifest.is_file():
        manifest = json.loads(source_manifest.read_text(encoding='utf-8'))
        manifest['props'] = {'count':len(props),'blocks':result['blocks'],'types':sorted({prop['type'] for prop in props}),'addedEntities':0,'addedTileEntities':0,'protectedLegacyChunks':len(protected)}
        manifest['files'] = {output.name+'/'+name:digest for name,digest in result['files'].items()}
        for region in manifest.get('regions',[]):
            path = output/'region'/Path(region['path']).name
            region['path'] = output.name+'/region/'+path.name
            region['bytes'] = path.stat().st_size
            region['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        (output.parent/'world-template-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        instructions = source.parent/'INSTALL-NEW-WORLD.md'
        if instructions.is_file():
            shutil.copy2(instructions,output.parent/instructions.name)
    print(json.dumps({key:value for key,value in result.items() if key not in ('props','files')}))


if __name__ == '__main__':
    main()
