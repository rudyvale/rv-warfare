import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


parser = argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--decorated',type=Path,required=True)
parser.add_argument('--preservation-report',type=Path,required=True)
parser.add_argument('--python-libs',type=Path,required=True)
args,rest = parser.parse_known_args()
sys.path.insert(0,str(args.python_libs))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import nbtlib
import decorate_world as props
from merge_world_regions import records


class WorldProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((args.decorated.parent/'props-report.json').read_text(encoding='utf-8'))
        cls.protected = props.protected_chunks(json.loads(args.preservation_report.read_text(encoding='utf-8')))

    def test_all_original_and_unmodified_region_records_are_exact(self):
        changed = set()
        untouched = 0
        for path in sorted((args.source/'region').glob('r.*.*.mca')):
            before,after = records(path.read_bytes()),records((args.decorated/'region'/path.name).read_bytes())
            self.assertEqual(set(before),set(after))
            _,rx,rz,_ = path.name.split('.')
            for index,record in before.items():
                key = int(rx)*32+index%32,int(rz)*32+index//32
                if record != after[index]:
                    changed.add(key)
                    self.assertNotIn(key,self.protected)
                else:
                    untouched += 1
        self.assertEqual(len(self.protected),2239)
        self.assertEqual(len(changed),self.report['modifiedChunks'])
        self.assertEqual(untouched,self.report['untouchedChunkRecordsExact'])

    def test_deterministic_plan_is_bounded_and_has_no_ticking_entities(self):
        self.assertEqual(props.plan(args.source,self.protected),self.report['props'])
        self.assertGreaterEqual(len(self.report['props']),20)
        self.assertLessEqual(len(self.report['props']),48)
        self.assertLessEqual(self.report['blocks'],1500)
        self.assertEqual(self.report['addedEntities'],0)
        self.assertEqual(self.report['addedTileEntities'],0)
        self.assertEqual({item['type'] for item in self.report['props']},{'sandbag_cover','supply_crates','wreck','checkpoint','barricade'})

    def test_world_manifest_describes_the_exact_decorated_files(self):
        manifest = json.loads((args.decorated.parent/'world-template-manifest.json').read_text(encoding='utf-8'))
        actual = {args.decorated.name+'/'+path.relative_to(args.decorated).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in args.decorated.rglob('*') if path.is_file()}
        self.assertEqual(manifest['files'],actual)
        self.assertEqual(manifest['props']['count'],len(self.report['props']))
        for region in manifest['regions']:
            path = args.decorated.parent/region['path']
            self.assertEqual(region['bytes'],path.stat().st_size)
            self.assertEqual(region['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(region['chunks'],len(records(path.read_bytes())))
        self.assertEqual((args.source.parent/'INSTALL-NEW-WORLD.md').read_bytes(),(args.decorated.parent/'INSTALL-NEW-WORLD.md').read_bytes())

    def test_each_block_matches_plan_and_no_existing_ground_was_changed(self):
        original,decorated = props.Terrain(args.source),props.Terrain(args.decorated)
        for prop in self.report['props']:
            x,z = prop['x'],prop['z']
            self.assertTrue(props.empty_footprint(original,x,z,self.protected))
            self.assertFalse(props.empty_footprint(decorated,x,z,self.protected))
            for (xx,yy,zz),(value,metadata) in props.geometry(prop['type'],x,z).items():
                self.assertEqual(props.block(original.chunk(xx,zz),xx,yy,zz),0)
                chunk = decorated.chunk(xx,zz)
                self.assertEqual(props.block(chunk,xx,yy,zz),value)
                section = next(item for item in chunk['Level']['Sections'] if int(item['Y'])==yy//16)
                index=(yy%16)*256+(zz%16)*16+xx%16
                self.assertEqual((int(section['Data'][index//2])&255)>>(4*(index%2))&15,metadata)
                self.assertEqual(props.block(chunk,xx,64,zz),props.block(original.chunk(xx,zz),xx,64,zz))
                self.assertFalse(chunk['Level'].get('Entities'))
                self.assertFalse(chunk['Level'].get('TileEntities'))

    def test_unknown_chunk_fields_and_adjacent_metadata_survive_edit(self):
        prop=self.report['props'][0]
        terrain=props.Terrain(args.source)
        chunk=terrain.chunk(prop['x'],prop['z'])
        chunk['Level']['RVUnknownField']=nbtlib.Compound({'name':nbtlib.String('preserve'),'number':nbtlib.Long(123456789)})
        data_before=next(item for item in chunk['Level']['Sections'] if int(item['Y'])==4)['Data'].copy()
        props.set_block(chunk,prop['x'],65,prop['z'],251,7)
        stream=io.BytesIO();chunk.write(stream)
        restored=nbtlib.File.parse(io.BytesIO(stream.getvalue()))
        self.assertEqual(restored['Level']['RVUnknownField'],chunk['Level']['RVUnknownField'])
        self.assertFalse(restored['Level']['LightPopulated'])
        section=next(item for item in restored['Level']['Sections'] if int(item['Y'])==4)
        index=256+(prop['z']%16)*16+prop['x']%16
        for number,(old,new) in enumerate(zip(data_before,section['Data'])):
            if number!=index//2:self.assertEqual(int(old),int(new))
        other=4*(1-index%2)
        self.assertEqual((int(data_before[index//2])&255)>>(other)&15,(int(section['Data'][index//2])&255)>>(other)&15)

    def test_offline_players_reserve_padded_chunks_without_changing_saves(self):
        with tempfile.TemporaryDirectory(prefix='rv-props-player-') as temporary:
            world=Path(temporary)
            (world/'playerdata').mkdir()
            save=world/'playerdata/qa.dat'
            nbtlib.File({'Dimension':nbtlib.Int(0),'Pos':nbtlib.List[nbtlib.Double]([nbtlib.Double(-160.5),nbtlib.Double(65),nbtlib.Double(560.5)]),'Unknown':nbtlib.String('keep')}).save(save,gzipped=True)
            original=save.read_bytes()
            protected=props.player_chunks(world)
            self.assertIn((-11,35),protected)
            self.assertIn((-10,34),protected)
            self.assertEqual(save.read_bytes(),original)


unittest.main(argv=[sys.argv[0],*rest])
