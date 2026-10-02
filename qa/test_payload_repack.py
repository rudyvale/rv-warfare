import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rv_payload_repack', ROOT / 'tools/repack_client_payload.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RepackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rv-payload-')
        self.root = Path(self.temp.name)
        self.base = self.root / 'baseline'
        self.base.mkdir()
        self.original = {'mods/unknown-user-mod.jar': b'unknown untouched', 'config/personal.cfg': b'private fixture settings', 'config/mcheli.cfg': b'Explosion_FlamingBlock=true\r\n', 'mods/mcheli-ce-old.jar': b'old owned mod'}
        with zipfile.ZipFile(self.base / 'payload.zip', 'w') as archive:
            for name, data in self.original.items():
                archive.writestr(name, data)
        with zipfile.ZipFile(self.base / 'runtime.zip', 'w') as archive:
            archive.writestr('runtime/sentinel.bin', b'baseline runtime')
        (self.base / 'installer-files.json').write_bytes(b'{"unknown":"retained"}\n')
        self.manifest = {'version': '1.0.0', 'unknown': {'preserve': True}, 'archives': [{'path': name, 'sha256': module.digest(self.base / name)} for name in ('payload.zip', 'runtime.zip')], 'managedFiles': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'customMetadata': 'keep'} for name, data in self.original.items()]}
        (self.base / 'package-manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        self.jar = self.root / 'mcheli.jar'
        self.resources = {'assets/mcheli/models/fixture' + str(index) + '.mqo': ('native resource' + str(index)).encode() for index in range(21)}
        with zipfile.ZipFile(self.jar, 'w') as archive:
            for name in ('com/norwood/mcheli/uav/WarfareOwnerAuth.class', 'com/norwood/mcheli/vm/VMVec2f.class', 'com/norwood/mcheli/vm/VMImpact.class'):
                archive.writestr(name, b'class fixture')
            for name, data in self.resources.items():
                archive.writestr(name, data)
        self.mapping = self.root / 'assets.json'
        self.map_data = {'schema': 1, 'mcheliSha256': module.digest(self.jar), 'resources': {name: hashlib.sha256(data).hexdigest() for name, data in self.resources.items()}}
        self.mapping.write_text(json.dumps(self.map_data), encoding='utf-8')
        self.vendors = self.root / 'vendors'
        self.vendors.mkdir()
        self.registry = self.root / 'registry.json'
        components = []
        for modid in ('firstaid', 'creativecore', 'enhancedvisuals'):
            path = self.vendors / (modid + '.jar')
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('mcmod.info', json.dumps([{'modid': modid}]))
            components.append({'modId': modid, 'binaryFile': path.name, 'binarySize': path.stat().st_size, 'binarySha256': module.digest(path)})
        self.registry.write_text(json.dumps({'schema': 1, 'components': components}), encoding='utf-8')
        self.config = self.root / 'config'
        self.config.mkdir()
        for name in ('firstaid.cfg', 'enhancedvisuals.json', 'enhancedvisuals-client.json'):
            (self.config / name).write_text('frozen config ' + name, encoding='utf-8')
        self.notices = self.root / 'NOTICES.md'
        self.notices.write_bytes(b'Exact third-party notices\r\n')
        self.tg = self.root / 'techguns.jar'
        self.audio = self.root / 'audio.zip'
        self.tg.write_bytes(b'final techguns')
        self.audio.write_bytes(b'final audio')

    def tearDown(self):
        self.temp.cleanup()

    def repack(self, output=None):
        return module.repack(self.base, output or self.root / 'candidate', self.jar, self.tg, self.audio, '1.1.0', self.mapping, self.vendors, self.registry, self.config, self.notices)

    def test_final_closure_and_baseline_preservation(self):
        before = {path.name: module.digest(path) for path in self.base.iterdir()}
        report = self.repack()
        output = Path(report['base'])
        manifest = json.loads((output / 'package-manifest.json').read_text())
        self.assertEqual(manifest['version'], '1.1.0')
        self.assertEqual(manifest['unknown'], self.manifest['unknown'])
        self.assertEqual(module.digest(output / 'runtime.zip'), before['runtime.zip'])
        self.assertEqual((output / 'installer-files.json').read_bytes(), (self.base / 'installer-files.json').read_bytes())
        self.assertEqual({path.name: module.digest(path) for path in self.base.iterdir()}, before)
        with zipfile.ZipFile(output / 'payload.zip') as archive:
            self.assertEqual(archive.read('mods/unknown-user-mod.jar'), self.original['mods/unknown-user-mod.jar'])
            self.assertEqual(archive.read('config/personal.cfg'), self.original['config/personal.cfg'])
            self.assertNotIn('mods/mcheli-ce-old.jar', archive.namelist())
            self.assertEqual(archive.read('THIRD-PARTY-NOTICES.md'), self.notices.read_bytes())
            for name, data in self.resources.items():
                self.assertEqual(archive.read('mcheli_addons/default/' + name), data)
        managed = {entry['path']: entry for entry in manifest['managedFiles']}
        self.assertEqual(managed['config/personal.cfg']['customMetadata'], 'keep')
        self.assertEqual(len([entry for entry in managed.values() if entry.get('existingOnly') is True]), 21)
        self.assertNotIn('config/enhancedvisuals-low.json', managed)
        self.assertEqual(len(report['vendorMods']), 3)

    def test_addon_whole_jar_and_resource_hashes_are_required(self):
        self.map_data['mcheliSha256'] = '0' * 64
        self.mapping.write_text(json.dumps(self.map_data))
        with self.assertRaises(ValueError):
            self.repack()
        self.map_data['mcheliSha256'] = module.digest(self.jar)
        self.map_data['resources'][next(iter(self.resources))] = '0' * 64
        self.mapping.write_text(json.dumps(self.map_data))
        with self.assertRaises(ValueError):
            self.repack()
        self.assertFalse((self.root / 'candidate').exists())

    def test_addon_path_traversal_and_incomplete_map_are_rejected(self):
        self.map_data['resources']['assets/mcheli/../escape.mqo'] = self.map_data['resources'].pop(next(iter(self.resources)))
        self.mapping.write_text(json.dumps(self.map_data))
        with self.assertRaises(ValueError):
            self.repack()
        self.map_data['resources'].pop('assets/mcheli/../escape.mqo')
        self.mapping.write_text(json.dumps(self.map_data))
        with self.assertRaises(ValueError):
            self.repack()

    def test_vendor_corruption_rejected_before_output(self):
        (self.vendors / 'firstaid.jar').write_bytes(b'corrupt vendor')
        with self.assertRaises(ValueError):
            self.repack()
        self.assertFalse((self.root / 'candidate').exists())

    def test_baseline_corruption_and_existing_output_rejected(self):
        with self.assertRaises(ValueError):
            self.repack(self.base)
        with (self.base / 'runtime.zip').open('ab') as stream:
            stream.write(b'changed baseline')
        with self.assertRaises(ValueError):
            self.repack()


if __name__ == '__main__':
    unittest.main(verbosity=2)
