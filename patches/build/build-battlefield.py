import io
import json
import math
import pathlib
import random
import struct
import sys
import time
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).parent / 'python-libs'))
import numpy as np
import nbtlib as n

root = pathlib.Path(__file__).parent
destination = root / 'battlefield-region'
destination.mkdir(exist_ok=True)
size = 640
offset = size // 2
blocks = np.zeros((112, size, size), dtype=np.uint8)
meta = np.zeros_like(blocks)
blocks[0] = 7
blocks[1:61] = 1
blocks[61:64] = 3
blocks[64] = 2
tiles = {}
rng = random.Random(1122)

def box(x1, y1, z1, x2, y2, z2, block, data=0):
    x1, x2 = max(-offset, x1), min(offset - 1, x2)
    z1, z2 = max(-offset, z1), min(offset - 1, z2)
    if x1 > x2 or z1 > z2:
        return
    blocks[y1:y2+1, z1+offset:z2+offset+1, x1+offset:x2+offset+1] = block
    meta[y1:y2+1, z1+offset:z2+offset+1, x1+offset:x2+offset+1] = data

def sign(x, y, z, lines, facing=2):
    box(x, y, z, x, y, z, 68, facing)
    tile = n.Compound({'id': n.String('minecraft:sign'), 'x': n.Int(x), 'y': n.Int(y), 'z': n.Int(z)})
    for i in range(4):
        tile['Text' + str(i+1)] = n.String(json.dumps({'text': lines[i] if i < len(lines) else ''}))
    tiles.setdefault((x//16, z//16), []).append(tile)

def crate(x, y, z, items):
    box(x, y, z, x, y, z, 54, 2)
    inventory = []
    for slot, (item, count, damage) in enumerate(items):
        inventory.append(n.Compound({'Slot': n.Byte(slot), 'id': n.String(item), 'Count': n.Byte(count), 'Damage': n.Short(damage)}))
    tiles.setdefault((x//16, z//16), []).append(n.Compound({'id': n.String('minecraft:chest'), 'x': n.Int(x), 'y': n.Int(y), 'z': n.Int(z), 'Items': n.List[n.Compound](inventory)}))

for z in range(-offset, offset):
    river = 125 + int(8 * math.sin(z / 40))
    box(z, 60, river-7, z, 65, river+7, 0)
    box(z, 60, river-7, z, 60, river+7, 13)
    box(z, 61, river-6, z, 62, river+6, 9)
    box(z, 63, river-9, z, 64, river-8, 12)
    box(z, 63, river+8, z, 64, river+9, 12)

box(-285, 64, -6, 285, 64, 6, 251, 7)
box(-6, 64, -290, 6, 64, 285, 251, 7)
for x in range(-280, 281, 12):
    box(x, 64, 0, x+5, 64, 0, 251, 4)
for z in range(-280, 281, 12):
    box(0, 64, z, 0, 64, z+5, 251, 4)
box(-8, 64, 103, 8, 64, 147, 98)
box(-8, 65, 103, -8, 66, 147, 101)
box(8, 65, 103, 8, 66, 147, 101)
for z in [107, 140]:
    box(-8, 59, z, 8, 63, z+2, 98)

def building(x, z, width, depth, floors, material=98, damaged=False):
    box(x, 64, z, x+width, 64, z+depth, 98)
    for floor in range(floors):
        y = 65 + floor*5
        box(x, y, z, x+width, y+4, z+depth, material)
        box(x+1, y, z+1, x+width-1, y+3, z+depth-1, 0)
        box(x+1, y+4, z+1, x+width-1, y+4, z+depth-1, 5)
        for xx in range(x+3, x+width-1, 5):
            for zz in [z, z+depth]:
                box(xx, y+1, zz, xx+1, y+2, zz, 102)
        for zz in range(z+3, z+depth-1, 5):
            for xx in [x, x+width]:
                box(xx, y+1, zz, xx, y+2, zz+1, 102)
        for step in range(5):
            box(x+2+step, y+step, z+depth-3, x+2+step, y+step, z+depth-2, 5)
    box(x+width//2, 65, z, x+width//2+1, 67, z, 0)
    top = 65+floors*5
    box(x, top, z, x+width, top, z+depth, 44, 5)
    box(x, top+1, z, x+width, top+1, z+depth, 98)
    box(x+1, top+1, z+1, x+width-1, top+1, z+depth-1, 0)
    if damaged:
        box(x, top-7, z+depth-5, x+5, top+2, z+depth, 0)
        for _ in range(14):
            xx, zz = x+rng.randrange(width), z+depth+rng.randrange(1, 5)
            box(xx, 65, zz, xx, 65+rng.randrange(2), zz, 4)

for x in [-73, -43, 19, 50]:
    for z in [-75, -42, 21, 52]:
        building(x, z, 21, 20, rng.choice([2, 3]), rng.choice([98, 45, 251]), rng.random()<0.4)
for x in [-82, 84]:
    for z in range(-88, 97, 28):
        box(x, 65, z, x, 70, z, 139)
        box(x, 71, z, x, 71, z, 89)

def base(cx, color, label):
    box(cx-59, 64, -120, cx+59, 64, 115, 13)
    box(cx-59, 65, -120, cx+59, 68, -120, 98)
    box(cx-59, 65, 115, cx+59, 68, 115, 98)
    box(cx-59, 65, -120, cx-59, 68, 115, 98)
    box(cx+59, 65, -120, cx+59, 68, 115, 98)
    box(cx-59, 65, -6, cx+59, 68, 6, 0)
    box(cx-10, 64, -112, cx+10, 64, 104, 251, 7)
    for z in range(-104, 100, 16):
        box(cx-1, 64, z, cx+1, 64, z+7, 251, 0)
    for z in [-106, 90]:
        for x in [-8, -4, 0, 4, 8]:
            box(cx+x, 64, z, cx+x+1, 64, z+9, 251, 0)
    for z in [-103, 36]:
        box(cx-50, 65, z, cx-19, 81, z+51, 251, 8)
        box(cx-49, 65, z+1, cx-20, 80, z+50, 0)
        box(cx-47, 65, z, cx-22, 77, z, 0)
        box(cx-48, 64, z, cx-20, 64, z+49, 251, 7)
    building(cx+20, -93, 24, 25, 2, 98)
    building(cx+20, 45, 24, 25, 1, 98)
    box(cx+23, 65, -40, cx+43, 72, -20, 251, color)
    box(cx+24, 65, -39, cx+42, 71, -21, 0)
    box(cx+29, 65, -20, cx+33, 68, -20, 0)
    for zz in [-50, 17, 90]:
        box(cx+34, 64, zz, cx+48, 64, zz+14, 251, 7)
        box(cx+41, 64, zz+3, cx+41, 64, zz+11, 251, 0)
        box(cx+37, 64, zz+7, cx+45, 64, zz+7, 251, 0)
    for x in [cx-56, cx+54]:
        for z in [-117, 101]:
            box(x, 65, z, x+5, 77, z+5, 98)
            box(x-1, 77, z-1, x+6, 77, z+6, 251, color)
            box(x-1, 78, z-1, x+6, 80, z+6, 85)
            box(x, 78, z, x+5, 80, z+5, 0)
    box(cx+37, 65, -9, cx+37, 81, -9, 101)
    box(cx+38, 77, -9, cx+45, 81, -9, 35, color)
    sign(cx+30, 69, -20, [label+' BASE', '/trigger kit', '/trigger help', 'UAV + VEHICLES'])
    crate(cx+25, 65, -25, [('minecraft:bread',64,0), ('minecraft:iron_helmet',1,0), ('minecraft:iron_chestplate',1,0), ('minecraft:iron_leggings',1,0), ('minecraft:iron_boots',1,0)])

base(-220, 11, 'BLUE')
base(220, 14, 'RED')
for x in [-115, 112]:
    box(x, 62, -105, x+3, 65, 103, 0)
    box(x-1, 62, -105, x-1, 64, 103, 17)
    box(x+4, 62, -105, x+4, 64, 103, 17)
    for z in range(-90, 101, 24):
        box(x-2, 65, z, x+5, 66, z+6, 12)
        box(x, 62, z, x+3, 65, z+6, 0)
for x in [-110, 99]:
    for z in [-128, 148]:
        box(x, 65, z, x+13, 72, z+12, 251, 8)
        box(x+1, 65, z+1, x+12, 70, z+11, 0)
        box(x+2, 68, z, x+11, 68, z, 0)
        box(x+5, 65, z+12, x+7, 67, z+12, 0)

for _ in range(410):
    x, z = rng.randrange(-309,310), rng.randrange(-309,310)
    if (abs(z)<151 and abs(x)>155) or (abs(x)<145 and abs(z)<158) or abs(x)<14 or abs(z)<15 or 105<z<147:
        continue
    y=65
    height=rng.randrange(5,9)
    box(x-2, y+height-3, z-2, x+2, y+height-1, z+2, 18)
    box(x-1, y+height, z-1, x+1, y+height, z+1, 18)
    box(x, y, z, x, y+height-1, z, 17)

box(-25, 64, -234, 25, 64, -186, 98)
box(-25, 65, -234, 25, 65, -234, 98)
box(-25, 65, -186, 25, 65, -186, 98)
for x in [-25,25]:
    box(x, 65, -234, x, 65, -186, 98)
    for z in [-234,-186]:
        box(x, 66, z, x, 74, z, 98)
        box(x-1, 75, z-1, x+1, 75, z+1, 89)
box(-9, 65, -233, 9, 72, -230, 98)
box(-8, 66, -229, 8, 71, -229, 35, 7)
sign(0, 69, -228, ['WARFARE 1.12.2', 'Welcome!', '/trigger help', 'Choose a team'])
sign(-6, 67, -228, ['BLUE TEAM', '/trigger blue', 'Base: -220 65 0', 'Guns + UAV'])
sign(6, 67, -228, ['RED TEAM', '/trigger red', 'Base: 220 65 0', 'Guns + UAV'])
for x in [-14,14]:
    box(x, 65, -211, x+2, 66, -204, 53)

regions = {}
for cz in range(-20, 20):
    for cx in range(-20, 20):
        bz, bx = cz*16+offset, cx*16+offset
        chunk = blocks[:, bz:bz+16, bx:bx+16]
        chunk_meta = meta[:, bz:bz+16, bx:bx+16]
        sections=[]
        heights=np.zeros((16,16),dtype=np.int32)
        for y in range(112):
            heights[chunk[y]!=0]=y+1
        for sy in range(7):
            data=chunk[sy*16:(sy+1)*16].reshape(-1)
            if not np.any(data):
                continue
            nibble=chunk_meta[sy*16:(sy+1)*16].reshape(-1)
            packed=(nibble[::2] | (nibble[1::2]<<4)).astype(np.int8)
            sky=np.zeros((16,16,16),dtype=np.uint8)
            for yy in range(16):
                sky[yy]=np.where(sy*16+yy >= heights, 15, 0)
            sky=sky.reshape(-1)
            packed_sky=(sky[::2]|(sky[1::2]<<4)).astype(np.int8)
            sections.append(n.Compound({'Y':n.Byte(sy),'Blocks':n.ByteArray(data.view(np.int8)), 'Data':n.ByteArray(packed),'SkyLight':n.ByteArray(packed_sky),'BlockLight':n.ByteArray(np.zeros(2048,dtype=np.int8))}))
        level=n.Compound({'xPos':n.Int(cx),'zPos':n.Int(cz),'LastUpdate':n.Long(0),'InhabitedTime':n.Long(0),'TerrainPopulated':n.Byte(1),'LightPopulated':n.Byte(1),'V':n.Byte(1),'Biomes':n.ByteArray(np.ones(256,dtype=np.int8)),'HeightMap':n.IntArray(heights.reshape(-1)), 'Sections':n.List[n.Compound](sections),'Entities':n.List[n.Compound]([]),'TileEntities':n.List[n.Compound](tiles.get((cx,cz),[])),'TileTicks':n.List[n.Compound]([])})
        stream=io.BytesIO()
        n.File({'DataVersion':n.Int(1343),'Level':level}).write(stream)
        compressed=zlib.compress(stream.getvalue(),6)
        record=struct.pack('>I',len(compressed)+1)+b'\x02'+compressed
        record+=bytes((-len(record))%4096)
        regions.setdefault((cx//32,cz//32),{})[(cx%32)+(cz%32)*32]=record
for (rx,rz), entries in regions.items():
    header=bytearray(8192)
    data=bytearray()
    sector=2
    for index, record in sorted(entries.items()):
        count=len(record)//4096
        header[index*4:index*4+4]=(sector<<8|count).to_bytes(4,'big')
        header[4096+index*4:4100+index*4]=int(time.time()).to_bytes(4,'big')
        data.extend(record)
        sector+=count
    (destination/f'r.{rx}.{rz}.mca').write_bytes(header+data)
(root/'battlefield-manifest.json').write_text(json.dumps({'name':'Crossfire Valley','size':[640,640],'chunks':1600,'blue':[-220,65,0],'red':[220,65,0],'spawn':[0,65,-210],'features':['two airfields','four hangars','six helipads','sixteen buildings','trenches','bunkers','river and bridge','forest','lobby']},indent=2))
print(json.dumps({'regions':len(regions),'chunks':1600,'size_bytes':sum(p.stat().st_size for p in destination.glob('*.mca'))}))
