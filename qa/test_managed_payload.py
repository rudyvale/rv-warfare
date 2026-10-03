import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from freeze_managed_mods import freeze
from stage_managed_payload import stage
from vendor_catalog import sha256_file


class ManagedPayloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rv-owned-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'pack').mkdir()
        shutil.copyfile(ROOT / 'pack/vendor-catalog.json', self.root / 'pack/vendor-catalog.json')
        self.catalog = json.loads((self.root / 'pack/vendor-catalog.json').read_text())
        self.build = self.root / 'build'
        (self.build / 'mods').mkdir(parents=True)
        self.spec = {'schema': 1, 'mods': [], 'nativeReceipts': {side: 'qa/evidence/' + side + '.json' for side in ('client', 'server')}}
        self.data = {}
        for modid, stem, version in (('rvcompat', 'rv-vehicle-compat', '1.2.0'), ('rvexperience', 'rv-experience', '2.0.0')):
            name = 'mods/' + stem + '-' + version + '.jar'
            artifact = self.build / name
            with zipfile.ZipFile(artifact, 'w') as archive:
                archive.writestr('rv/' + modid + '/Fixture.class', b'\xca\xfe\xba\xbe\x00\x00\x00\x34')
                archive.writestr('mcmod.info', json.dumps([{'modid': modid, 'version': version}]))
            source = self.root / 'patches' / modid / 'Fixture.java'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'class Fixture {}\n')
            self.spec['mods'].append({'id': modid, 'path': name, 'fileVersion': version, 'side': 'both', 'fml': {modid: version}, 'sourceFiles': {source.relative_to(self.root).as_posix(): sha256_file(source)}, 'artifact': str(artifact)})
            self.data[name] = artifact.read_bytes()
        self.native = {'success': True, 'mods': {'rvcompat': '1.2.0', 'rvexperience': '2.0.0'}, 'artifacts': {name: hashlib.sha256(data).hexdigest() for name, data in self.data.items()}}
        for name in self.spec['nativeReceipts'].values():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(json.dumps(self.native).encode())
        self.spec_path = self.root / 'spec.json'
        self.spec_path.write_bytes(json.dumps(self.spec).encode())
        self.proof = self.root / 'proof.json'
        self.output = self.root / 'staged'

    def baseline(self):
        freeze(self.spec_path, self.root, self.proof)
        document = json.loads(self.proof.read_text())
        previous = {**document, 'mods': document['mods'][:1]}
        base = self.root / 'base'
        base.mkdir()
        (base / 'rv-managed-mods.json').write_bytes(json.dumps(previous).encode())
        (base / 'release.json').write_bytes(json.dumps({'version': '1.2.1', 'managedModsSha256': sha256_file(base / 'rv-managed-mods.json')}).encode())
        files = {'mods/rv-vehicle-compat-1.2.0.jar': self.data['mods/rv-vehicle-compat-1.2.0.jar'], 'config/keep.cfg': b'keep exact\r\n', 'mods/rv-experience-my-addon.jar': b'unknown user fixture'}
        with zipfile.ZipFile(base / 'payload.zip', 'w') as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        with zipfile.ZipFile(base / 'runtime.zip', 'w') as archive:
            archive.writestr('runtime/fixture.bin', b'Java runtime fixture')
        (base / 'installer-files.json').write_bytes(b'{"fixture":"keep"}\n')
        manifest = {'version': '1.2.1', 'archives': [{'path': name, 'sha256': sha256_file(base / name)} for name in ('payload.zip', 'runtime.zip')], 'managedFiles': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'fixturePolicy': 'keep'} for name, data in files.items()] + [{'path': entry['path'], 'sha256': entry['sha256']} for entry in self.catalog['files']], 'managedModPatterns': ['^old-owned-fixture-[0-9]+\\.jar$']}
        (base / 'package-manifest.json').write_bytes(json.dumps(manifest).encode())
        (self.build / 'mods/rv-vehicle-compat-1.2.0.jar').unlink()
        return base, files

    def test_complete_union_freezes_from_build_and_both_native_sides(self):
        result = freeze(self.spec_path, self.root, self.proof)
        self.assertEqual(result['mods'], self.native['mods'])
        self.assertEqual(result['nativeSides'], ['client', 'server'])
        self.assertNotIn(b'\r', self.proof.read_bytes())
        self.assertNotIn(str(self.build), self.proof.read_text())

    def test_wrong_loaded_artifact_or_missing_module_rejected(self):
        for data in ({**self.native, 'artifacts': {**self.native['artifacts'], 'mods/rv-experience-2.0.0.jar': '0' * 64}}, {**self.native, 'mods': {'rvcompat': '1.2.0'}}):
            with self.subTest(data=data):
                (self.root / self.spec['nativeReceipts']['server']).write_bytes(json.dumps(data).encode())
                with self.assertRaisesRegex(ValueError, 'complete owned module union|loaded native binary'):
                    freeze(self.spec_path, self.root, self.proof)
                self.assertFalse(self.proof.exists())

    def test_private_fields_cannot_enter_native_projection(self):
        (self.root / self.spec['nativeReceipts']['client']).write_bytes(json.dumps({**self.native, 'privateInvite': 'fixture'}).encode())
        with self.assertRaisesRegex(ValueError, 'only successful FML identities'):
            freeze(self.spec_path, self.root, self.proof)

    def test_changed_source_after_build_rejected(self):
        (self.root / 'patches/rvexperience/Fixture.java').write_bytes(b'class Changed {}\n')
        with self.assertRaisesRegex(ValueError, 'source differs from its frozen closure'):
            freeze(self.spec_path, self.root, self.proof)

    def test_stage_preserves_baseline_and_adds_only_proven_owned_artifacts(self):
        base, files = self.baseline()
        before = {path.name: sha256_file(path) for path in base.iterdir()}
        result = stage(base, self.build, self.proof, self.root, self.output, '2.0.0')
        self.assertEqual(result['mods'], self.native['mods'])
        self.assertEqual({path.name: sha256_file(path) for path in base.iterdir()}, before)
        self.assertEqual(result['runtimeSha256'], before['runtime.zip'])
        self.assertEqual((self.output / 'installer-files.json').read_bytes(), (base / 'installer-files.json').read_bytes())
        with zipfile.ZipFile(self.output / 'payload.zip') as archive:
            for name, data in {**files, **self.data}.items():
                self.assertEqual(archive.read(name), data)
            self.assertTrue(all(entry['path'] not in archive.namelist() for entry in self.catalog['files']))
        manifest = json.loads((self.output / 'package-manifest.json').read_text())
        self.assertEqual(manifest['managedFiles'][0]['fixturePolicy'], 'keep')
        self.assertIn('^rv\\-experience\\-[0-9]+\\.[0-9]+\\.[0-9]+\\.jar$', manifest['managedModPatterns'])

    def test_changed_native_receipt_aborts_without_partial_output(self):
        base, _ = self.baseline()
        (self.root / self.spec['nativeReceipts']['server']).write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'receipt changed'):
            stage(base, self.build, self.proof, self.root, self.output, '2.0.0')
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob('.staged-stage-*')), [])

    def test_changed_built_artifact_rejected_before_staging(self):
        base, _ = self.baseline()
        (self.build / 'mods/rv-experience-2.0.0.jar').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum or size mismatch'):
            stage(base, self.build, self.proof, self.root, self.output, '2.0.0')
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
