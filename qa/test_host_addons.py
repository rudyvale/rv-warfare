import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rv_stock_addons', ROOT / 'host/host_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class StockAddons(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rv-host-addon-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.default = self.root / 'mcheli_addons/default'
        self.default.mkdir(parents=True)
        self.old = self.default / 'assets/mcheli/helicopters/rc-goblin.yml'
        self.old.parent.mkdir(parents=True)
        self.old.write_bytes(b'old-stock-with-personal-adjustment')
        self.unknown = self.default / 'assets/mcheli/helicopters/custom.yml'
        self.unknown.write_bytes(b'unknown-must-stay')
        self.resources = {'assets/mcheli/helicopters/rc-goblin.yml': b'new-stock', 'assets/mcheli/planes/rv_geran.yml': b'new-plane'}
        self.manifest = {'schema':1,'resources':{name:hashlib.sha256(data).hexdigest() for name,data in self.resources.items()}}
        (self.root / 'mods').mkdir()
        with zipfile.ZipFile(self.root / 'mods/mcheli-ce-1.5.1-rv.jar','w') as archive:
            for name,data in self.resources.items(): archive.writestr(name,data)
        self.manifest['mcheliSha256'] = hashlib.sha256((self.root / 'mods/mcheli-ce-1.5.1-rv.jar').read_bytes()).hexdigest()
        runtime.write_json(self.root / 'rv-addon-assets.json',self.manifest)

    def test_updates_only_known_assets_without_requiring_pack_metadata(self):
        result = runtime.update_stock_addons(self.root)
        self.assertEqual(result['updated'],2)
        self.assertEqual(self.old.read_bytes(),b'new-stock')
        self.assertEqual((self.default / 'assets/mcheli/planes/rv_geran.yml').read_bytes(),b'new-plane')
        self.assertEqual(self.unknown.read_bytes(),b'unknown-must-stay')
        backup = Path(result['backup']) / self.old.relative_to(self.root)
        self.assertEqual(backup.read_bytes(),b'old-stock-with-personal-adjustment')
        self.assertFalse((self.default / 'pack.mcmeta').exists())
        self.assertEqual(runtime.update_stock_addons(self.root)['updated'],0)
        self.assertEqual(len(list((self.root / 'backups').iterdir())),1)

    def test_cold_missing_default_skips_instead_of_creating_partial_addon(self):
        with tempfile.TemporaryDirectory(prefix='rv-cold-addon-') as folder:
            root = Path(folder)
            self.assertEqual(runtime.update_stock_addons(root),{'updated':0,'existingDefault':False})
            self.assertFalse((root / 'mcheli_addons').exists())

    def test_bad_checksum_rejects_entire_update_before_any_write(self):
        self.manifest['resources']['assets/mcheli/planes/rv_geran.yml'] = '0'*64
        runtime.write_json(self.root / 'rv-addon-assets.json',self.manifest)
        with self.assertRaises(ValueError): runtime.update_stock_addons(self.root)
        self.assertEqual(self.old.read_bytes(),b'old-stock-with-personal-adjustment')
        self.assertFalse((self.root / 'backups').exists())
        self.assertFalse((self.default / 'assets/mcheli/planes').exists())

    def test_path_traversal_and_case_aliases_rejected_before_any_write(self):
        for name in ('assets/mcheli/../../server.properties','assets\\mcheli\\plane.yml','assets/mcheli/C:/plane.yml','/assets/mcheli/plane.yml'):
            with self.subTest(name=name):
                runtime.write_json(self.root / 'rv-addon-assets.json',{'schema':1,'resources':{name:'0'*64}})
                with self.assertRaises(ValueError): runtime.update_stock_addons(self.root)
                self.assertEqual(self.old.read_bytes(),b'old-stock-with-personal-adjustment')

    def test_running_server_never_mutates_loaded_addons(self):
        with patch.object(runtime,'server_status',return_value={'state':'running'}):
            with self.assertRaises(RuntimeError): runtime.update_stock_addons(self.root)
        self.assertEqual(self.old.read_bytes(),b'old-stock-with-personal-adjustment')

    def test_whole_mod_version_and_case_aliases_reject_before_write(self):
        self.manifest['mcheliSha256'] = '0'*64
        runtime.write_json(self.root / 'rv-addon-assets.json',self.manifest)
        with self.assertRaises(ValueError): runtime.update_stock_addons(self.root)
        self.manifest['mcheliSha256'] = hashlib.sha256((self.root / 'mods/mcheli-ce-1.5.1-rv.jar').read_bytes()).hexdigest()
        self.manifest['resources']['assets/mcheli/helicopters/RC-GOBLIN.yml'] = hashlib.sha256(b'new-stock').hexdigest()
        runtime.write_json(self.root / 'rv-addon-assets.json',self.manifest)
        with self.assertRaises(ValueError): runtime.update_stock_addons(self.root)
        self.assertEqual(self.old.read_bytes(),b'old-stock-with-personal-adjustment')

    def test_new_host_requires_matching_asset_map_for_existing_default(self):
        (self.root / 'rv-addon-assets.json').unlink()
        runtime.write_json(self.root / 'release.json',{'version':'1.1.0'})
        with self.assertRaises(ValueError): runtime.update_stock_addons(self.root)
        self.assertEqual(self.old.read_bytes(),b'old-stock-with-personal-adjustment')


if __name__ == '__main__':
    unittest.main()
