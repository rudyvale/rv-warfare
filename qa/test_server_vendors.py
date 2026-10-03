from contextlib import nullcontext
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
spec = importlib.util.spec_from_file_location('server_vendors', ROOT / 'host/server_vendors.py')
vendor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vendor)


def jar(modid, content=b'content'):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('mcmod.info', json.dumps([{'modid': modid}]))
        archive.writestr('content.dat', content)
    return stream.getvalue()


class ServerVendorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = self.root / 'server'
        self.server.mkdir()
        self.bytes = {'bop': jar('biomesoplenty'), 'mw': jar('modularwarfare'), 'ambient': jar('ambientsounds')}
        self.files = [self.file('bop', 'mods/bop.jar', 'both', 'biomesoplenty'), self.file('mw', 'mods/mw.jar', 'both', 'modularwarfare'), self.file('ambient', 'mods/ambient.jar', 'client', 'ambientsounds')]
        self.catalog()
        (self.server / 'server.properties').write_text('server-port=25565\nlevel-name=Battlefield\n')
        for name, data in {'Battlefield/region/r.0.0.mca': b'world', 'Battlefield/playerdata/player.dat': b'player', 'Battlefield/data/scoreboard.dat': b'scores', 'owner-auth.json': b'private account', 'porthole.json': b'private connection', 'mods/custom.jar': jar('unknownmod')}.items():
            path = self.server / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.originals = {path.relative_to(self.server): path.read_bytes() for path in self.server.rglob('*') if path.is_file()}
        self.lock = patch.object(vendor, 'maintenance', lambda root: nullcontext())
        self.lock.start()

    def tearDown(self):
        self.lock.stop()
        self.temp.cleanup()

    def file(self, name, path, side, modid):
        data = self.bytes[name]
        return {'id': name, 'path': path, 'side': side, 'delivery': 'official-download', 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'expectedModIds': [modid]}

    def catalog(self):
        path = self.server / 'vendor-catalog.json'
        path.write_text(json.dumps({'schema': 1, 'state': 'pinned', 'minecraft': '1.12.2', 'loader': 'forge', 'javaMajor': 8, 'files': self.files}))
        (self.server / 'release.json').write_text(json.dumps({'version': '1.2.0', 'vendorCatalogSha256': vendor.digest(path)}))

    def stage(self):
        result = vendor.prepare(self.server)
        stage = Path(result['stage'])
        for item in self.files:
            if item['side'] != 'client':
                path = stage / item['path']
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(self.bytes[item['id']])
        return stage

    def test_install_preserves_world_accounts_connection_and_unknown_mods(self):
        result = vendor.apply(self.server, self.stage())
        self.assertEqual(result['changed'], 2)
        self.assertFalse((self.server / 'mods/ambient.jar').exists())
        for name, data in self.originals.items():
            self.assertEqual((self.server / name).read_bytes(), data)
        self.assertEqual(vendor.check_ready(self.server)['files'], 2)

    def test_unknown_file_conflict_is_rejected_before_stage_or_backup(self):
        (self.server / 'mods/bop.jar').write_bytes(b'custom same filename')
        with self.assertRaisesRegex(ValueError, 'CONFLICT'):
            vendor.prepare(self.server)
        self.assertFalse((self.server / '.vendor-stage').exists())
        self.assertFalse((self.server / 'backups').exists())

    def test_exact_installed_bytes_are_reused_in_staging(self):
        (self.server / 'mods/bop.jar').write_bytes(self.bytes['bop'])
        result = vendor.prepare(self.server)
        self.assertEqual(result['reused'], 1)
        self.assertEqual((Path(result['stage']) / 'mods/bop.jar').read_bytes(), self.bytes['bop'])

    def test_failed_second_write_rolls_back_new_files(self):
        stage = self.stage()
        original = vendor.replace_bytes
        def replace(path, data):
            if path == self.server / 'mods/mw.jar':
                raise OSError('fixture file lock')
            original(path, data)
        with patch.object(vendor, 'replace_bytes', replace), self.assertRaises(OSError):
            vendor.apply(self.server, stage)
        self.assertFalse((self.server / 'mods/bop.jar').exists())
        self.assertFalse((self.server / vendor.MANIFEST).exists())
        self.assertEqual(vendor.read(self.server / vendor.JOURNAL)['state'], 'rolled-back')

    def test_owned_version_upgrade_keeps_verified_backup_and_removes_only_owned_old_version(self):
        vendor.apply(self.server, self.stage())
        old = self.bytes['bop']
        self.bytes['bop'] = jar('biomesoplenty', b'new version')
        self.files[0] = self.file('bop', 'mods/bop-new.jar', 'both', 'biomesoplenty')
        self.catalog()
        result = vendor.apply(self.server, self.stage())
        self.assertEqual(result['removedOwned'], 1)
        self.assertFalse((self.server / 'mods/bop.jar').exists())
        self.assertEqual((Path(result['backup']) / 'mods/bop.jar').read_bytes(), old)
        self.assertTrue((self.server / 'mods/custom.jar').exists())

    def test_modified_owned_file_stops_upgrade(self):
        vendor.apply(self.server, self.stage())
        (self.server / 'mods/bop.jar').write_bytes(b'custom replacement')
        self.files[0] = self.file('bop', 'mods/bop-new.jar', 'both', 'biomesoplenty')
        self.catalog()
        with self.assertRaisesRegex(ValueError, 'CONFLICT'):
            vendor.prepare(self.server)

    def test_changed_target_after_download_stops_before_backup(self):
        stage = self.stage()
        (self.server / 'mods/bop.jar').write_bytes(self.bytes['bop'])
        with self.assertRaisesRegex(ValueError, 'STALE'):
            vendor.apply(self.server, stage)
        self.assertFalse((self.server / 'backups').exists())

    def test_bad_download_digest_stops_before_backup(self):
        stage = self.stage()
        (stage / 'mods/bop.jar').write_bytes(b'partial download')
        with self.assertRaisesRegex(ValueError, 'DIGEST'):
            vendor.apply(self.server, stage)
        self.assertFalse((self.server / 'backups').exists())

    def test_catalog_without_matching_release_hash_is_rejected(self):
        with (self.server / 'vendor-catalog.json').open('a') as stream:
            stream.write(' ')
        with self.assertRaisesRegex(ValueError, 'CATALOG_DIGEST'):
            vendor.prepare(self.server)

    def test_renamed_duplicate_mod_is_preserved_and_install_refused(self):
        (self.server / 'mods/renamed.jar').write_bytes(self.bytes['bop'])
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
            vendor.prepare(self.server)
        self.assertEqual((self.server / 'mods/renamed.jar').read_bytes(), self.bytes['bop'])

    def test_other_version_of_same_mod_in_versioned_mod_directory_is_detected(self):
        (self.server / 'mods/1.12.2').mkdir()
        (self.server / 'mods/1.12.2/old-version.jar').write_bytes(jar('biomesoplenty', b'other'))
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
            vendor.prepare(self.server)

    def test_cancel_after_download_never_changes_mods(self):
        stage = self.stage()
        cancel = self.root / 'cancel'
        cancel.write_text('cancel')
        with self.assertRaisesRegex(RuntimeError, 'CANCELLED'):
            vendor.apply(self.server, stage, cancel)
        self.assertFalse((self.server / 'mods/bop.jar').exists())
        self.assertFalse((self.server / 'backups').exists())

    def test_server_lock_rejection_prevents_staging(self):
        with patch.object(vendor, 'maintenance', side_effect=RuntimeError('server active')), self.assertRaises(RuntimeError):
            vendor.prepare(self.server)
        self.assertFalse((self.server / '.vendor-stage').exists())

    def test_interrupted_update_blocks_startup(self):
        vendor.atomic_json(self.server / vendor.JOURNAL, {'state': 'applying'})
        with self.assertRaisesRegex(RuntimeError, 'RECOVERY'):
            vendor.check_ready(self.server)

    def test_traversal_staging_is_rejected(self):
        stage = self.root / 'different-location'
        stage.mkdir()
        with self.assertRaisesRegex(ValueError, 'PATH'):
            vendor.apply(self.server, stage)

    def test_deep_path_is_rejected_before_download_stage_or_backup(self):
        server = self.server / ('x' * 160)
        server.mkdir()
        for name in ('release.json', 'vendor-catalog.json', 'server.properties'):
            shutil.copy2(self.server / name, server / name)
        with self.assertRaisesRegex(ValueError, 'PATH_LENGTH'):
            vendor.prepare(server)
        self.assertFalse((server / '.vendor-stage').exists())
        self.assertFalse((server / 'backups').exists())

    def test_new_release_without_catalog_binding_cannot_start(self):
        (self.server / 'release.json').write_text(json.dumps({'version': '1.2.0'}))
        with self.assertRaisesRegex(ValueError, 'CATALOG_DIGEST'):
            vendor.check_ready(self.server)

    def test_pre_vendor_release_does_not_require_new_catalog(self):
        (self.server / 'release.json').write_text(json.dumps({'version': '1.1.0'}))
        self.assertFalse(vendor.check_ready(self.server)['required'])

    def interrupted(self):
        stage = self.stage()
        original = vendor.replace_bytes
        def replace(path, data):
            if path == self.server / 'mods/mw.jar':
                raise OSError('fixture file lock')
            original(path, data)
        with patch.object(vendor, 'replace_bytes', replace), self.assertRaises(OSError):
            vendor.apply(self.server, stage)
        journal = vendor.read(self.server / vendor.JOURNAL)
        journal['state'] = 'applying'
        vendor.atomic_json(self.server / vendor.JOURNAL, journal)
        (self.server / 'mods/bop.jar').write_bytes(self.bytes['bop'])
        return journal

    def test_interrupted_installation_is_recovered_before_retry(self):
        self.interrupted()
        result = vendor.prepare(self.server)
        self.assertEqual(result['reused'], 0)
        self.assertFalse((self.server / 'mods/bop.jar').exists())
        self.assertTrue((self.server / 'mods/custom.jar').exists())
        self.assertEqual(vendor.read(self.server / vendor.JOURNAL)['state'], 'rolled-back')

    def test_interrupted_recovery_cannot_overwrite_new_custom_file(self):
        self.interrupted()
        (self.server / 'mods/bop.jar').write_bytes(b'new custom file')
        with self.assertRaisesRegex(ValueError, 'CONFLICT'):
            vendor.recover(self.server)
        self.assertEqual((self.server / 'mods/bop.jar').read_bytes(), b'new custom file')

    def test_recovery_cannot_target_world_or_private_files(self):
        journal = self.interrupted()
        journal['preimages']['Battlefield/region/r.0.0.mca'] = None
        vendor.atomic_json(self.server / vendor.JOURNAL, journal)
        with self.assertRaisesRegex(ValueError, 'PATH'):
            vendor.recover(self.server)
        self.assertEqual((self.server / 'Battlefield/region/r.0.0.mca').read_bytes(), b'world')

    def test_recovery_backup_must_remain_in_the_same_server(self):
        journal = self.interrupted()
        journal['backup'] = str(self.root / 'other-server')
        vendor.atomic_json(self.server / vendor.JOURNAL, journal)
        with self.assertRaisesRegex(ValueError, 'PATH'):
            vendor.recover(self.server)

    def process_fixture(self, command, **kwargs):
        stage = Path(command[command.index('-PreparedStage') + 1])
        for item in self.files:
            if item['side'] != 'client':
                path = stage / item['path']
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(self.bytes[item['id']])
        class Process:
            returncode = 0
            polls = 0
            def poll(self):
                self.polls += 1
                return None if self.polls < 3 else 0
        return Process()

    def test_worker_reports_progress_and_applies_after_download_process(self):
        pulses = []
        with patch.object(vendor.subprocess, 'Popen', self.process_fixture), patch.object(vendor.time, 'sleep'):
            result = vendor.install_for_runner(self.server, lambda: pulses.append('heartbeat') or False)
        self.assertEqual(result['state'], 'committed')
        self.assertGreaterEqual(len(pulses), 3)
        self.assertEqual((self.server / 'mods/bop.jar').read_bytes(), self.bytes['bop'])

    def test_worker_cancel_during_download_never_installs_mods(self):
        with patch.object(vendor.subprocess, 'Popen', self.process_fixture), patch.object(vendor.time, 'sleep'), self.assertRaisesRegex(RuntimeError, 'CANCELLED'):
            vendor.install_for_runner(self.server, lambda: True)
        self.assertFalse((self.server / 'mods/bop.jar').exists())
        self.assertFalse((self.server / 'backups').exists())

    def owned_bundle(self):
        data = jar('rvcompat')
        item = {'id': 'rvcompat', 'path': 'mods/rv-vehicle-compat-1.2.0.jar', 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'side': 'both', 'expectedModIds': ['rvcompat']}
        source = self.server / 'host-owned' / item['path']
        source.parent.mkdir(parents=True)
        source.write_bytes(data)
        registry = self.server / 'rv-managed-mods.json'
        registry.write_text(json.dumps({'schema': 1, 'mods': [item]}))
        release = vendor.read(self.server / 'release.json')
        release['managedModsSha256'] = vendor.digest(registry)
        vendor.atomic_json(self.server / 'release.json', release)
        return item, data

    def test_owned_rv_module_is_staged_and_installed_with_foreign_download_transaction(self):
        item, data = self.owned_bundle()
        result = vendor.apply(self.server, self.stage())
        self.assertEqual(result['files'], 3)
        self.assertEqual((self.server / item['path']).read_bytes(), data)
        self.assertEqual(vendor.check_ready(self.server)['files'], 3)

    def test_owned_rv_module_cannot_overwrite_unknown_same_filename(self):
        item, _ = self.owned_bundle()
        (self.server / item['path']).write_bytes(b'custom same filename')
        with self.assertRaisesRegex(ValueError, 'CONFLICT'):
            vendor.prepare(self.server)

    def test_owned_rv_registry_requires_release_hash(self):
        self.owned_bundle()
        with (self.server / 'rv-managed-mods.json').open('a') as stream:
            stream.write(' ')
        with self.assertRaisesRegex(ValueError, 'MANAGED_DIGEST'):
            vendor.prepare(self.server)


if __name__ == '__main__':
    unittest.main()
