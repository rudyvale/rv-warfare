import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.request
import zipfile


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from download_vendor_files import ApprovedRedirects, fetch
from vendor_catalog import BASE_COMMIT, BASE_SETUP_SHA256, audit_public_files, external_managed_files, files_for_side, first_party_proof_path, protocol_maps, safe_path, safe_url, validate_catalog, validate_release_catalog, verify_artifact, verify_first_party_proof, verify_managed_delivery


def artifact(members=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_STORED) as archive:
        for name, data in (members or {'example/Main.class': b'\xca\xfe\xba\xbe\x00\x00\x00\x34'}).items():
            archive.writestr(name, data)
    return stream.getvalue()


def entry(component='example', side='both', delivery='official-download', data=None):
    data = data or artifact()
    digest = hashlib.sha256(data).hexdigest()
    page = 'https://www.curseforge.com/minecraft/mc-mods/' + component
    return {'id': component, 'name': component, 'path': 'mods/' + component + '.jar', 'kind': 'mod', 'side': side, 'fileVersion': '1.0', 'projectId': 100, 'fileId': 3558882, 'projectUrl': page, 'filePageUrl': page + '/files/3558882', 'officialUrls': ['https://edge.forgecdn.net/files/3558/882/' + component + '.jar'], 'size': len(data), 'sha256': digest, 'delivery': delivery, 'expectedModIds': [component.replace('-', '_')], 'fml': {component.replace('-', '_'): '1.0'}, 'requires': [], 'rights': {'license': 'Test fixture', 'reviewedSha256': digest, 'rehostAllowed': delivery == 'bundle', 'evidence': [{'kind': 'archive-license', 'url': page, 'sha256': 'a' * 64, 'appliesToSha256': digest}]}}


def catalog(*files):
    return {'schema': 1, 'state': 'pinned', 'minecraft': '1.12.2', 'loader': 'forge', 'javaMajor': 8, 'baseline': {'version': '1.1.0', 'sourceCommit': BASE_COMMIT, 'setupSha256': BASE_SETUP_SHA256, 'files': []}, 'files': list(files or [entry()])}


class Response(io.BytesIO):
    def __init__(self, data, url, declared=None):
        super().__init__(data)
        self.url = url
        self.headers = {'Content-Length': str(len(data) if declared is None else declared)}

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, data, url=None, declared=None):
        self.data, self.url, self.declared, self.calls = data, url, declared, 0

    def open(self, request, timeout):
        self.calls += 1
        return Response(self.data, self.url or request.full_url, self.declared)


class CatalogTests(unittest.TestCase):
    def reject(self, data, expression):
        with self.assertRaisesRegex(ValueError, expression):
            validate_catalog(data)

    def test_pinned_and_immutable_baseline(self):
        self.assertEqual(validate_catalog(catalog())['state'], 'pinned')
        data = catalog()
        data['state'] = 'draft'
        self.reject(data, 'Draft')
        self.assertEqual(validate_catalog(data, allow_draft=True)['state'], 'draft')
        data['state'] = 'pinned'
        data['baseline']['sourceCommit'] = 'f' * 40
        self.reject(data, 'immutable')

    def test_windows_paths_and_origins(self):
        for name in ('../outside.jar', 'C:/outside.jar', '/outside.jar', 'mods\\x.jar', 'mods/NUL.jar', 'mods/a.jar.', 'mods/a.jar ', 'mods/a:secret.jar'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_path(name)
        for url in ('http://edge.forgecdn.net/x', 'https://evil.example/x', 'https://user:secret@edge.forgecdn.net/x', 'https://edge.forgecdn.net:444/x', 'https://edge.forgecdn.net/x#fragment', 'https://edge.forgecdn.net.evil.example/x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                safe_url(url)

    def test_exact_curseforge_file_path(self):
        data = catalog()
        data['files'][0]['officialUrls'][0] = 'https://edge.forgecdn.net/files/3558/883/example.jar'
        self.reject(data, 'pinned file')

    def test_duplicate_windows_targets(self):
        first, second = entry('example'), entry('second')
        second['path'] = 'mods/EXAMPLE.jar'
        second['officialUrls'] = ['https://cdn.modrinth.com/data/test/file.jar']
        self.reject(catalog(first, second), 'Duplicate Windows')

    def test_duplicate_declared_identity_even_before_native_receipt(self):
        first, second = entry(), entry('second')
        first['fml'] = {}
        second['expectedModIds'] = ['example']
        second['fml'] = {}
        self.reject(catalog(first, second), 'Duplicate declared')
        first['expectedModIds'] = ['second']
        second['expectedModIds'] = ['second']
        data = catalog(first)
        data['baseline']['files'] = [second]
        self.reject(data, 'Duplicate declared')

    def test_actual_native_version_required_for_protocol(self):
        data = catalog()
        data['files'][0]['fml'] = {}
        validate_catalog(data)
        with self.assertRaisesRegex(ValueError, 'Actual native'):
            protocol_maps(data)

    def test_client_only_outside_common_protocol(self):
        data = catalog(entry(), entry('mouse', side='client'), entry('server-tool', side='server'))
        validate_catalog(data)
        self.assertEqual(protocol_maps(data), {'requiredMods': {'example': '1.0'}, 'clientRequiredMods': {'example': '1.0', 'mouse': '1.0'}})
        self.assertEqual([x['id'] for x in files_for_side(data, 'server')], ['example', 'server-tool'])

    def test_dependencies_missing_changed_version_or_wrong_side(self):
        first, second = entry(), entry('library', side='client')
        first['requires'] = [{'id': 'missing', 'fileVersion': '1.0', 'side': 'both'}]
        self.reject(catalog(first, second), 'Missing')
        first['requires'][0]['id'] = 'library'
        first['requires'][0]['fileVersion'] = '2.0'
        self.reject(catalog(first, second), 'pinned version')
        first['requires'][0]['fileVersion'] = '1.0'
        self.reject(catalog(first, second), 'Client-only dependency')

    def test_dependency_cycle(self):
        first, second = entry(), entry('library')
        first['requires'] = [{'id': 'library', 'fileVersion': '1.0', 'side': 'both'}]
        second['requires'] = [{'id': 'example', 'fileVersion': '1.0', 'side': 'both'}]
        self.reject(catalog(first, second), 'cycle')

    def test_exact_historical_license_scope(self):
        data = catalog(entry(delivery='bundle'))
        data['files'][0]['rights']['rehostAllowed'] = False
        self.reject(data, 'redistribution')
        data = catalog()
        data['files'][0]['rights']['reviewedSha256'] = 'b' * 64
        self.reject(data, 'exact vendor bytes')
        data['files'][0]['rights']['reviewedSha256'] = data['files'][0]['sha256']
        data['files'][0]['rights']['evidence'][0]['appliesToSha256'] = 'b' * 64
        self.reject(data, 'Unbound rights')

    def test_content_packs_need_real_definition_hash(self):
        pack = entry('content')
        pack['kind'], pack['expectedModIds'], pack['fml'] = 'content-pack', [], {}
        self.reject(catalog(pack), 'definition hashes')
        pack['definitionHashes'] = {'assets/content/packdefinition.json': 'a' * 64}
        validate_catalog(catalog(pack))

    def test_renamed_and_embedded_bytes_cannot_be_rehosted(self):
        vendor = entry()
        vendor['embedded'] = [{'member': 'packs/inside.zip', 'path': 'modularwarfare/inside.zip', 'size': 10, 'sha256': 'c' * 64}]
        data = catalog(vendor)
        for digest in (vendor['sha256'], 'c' * 64):
            with self.subTest(digest=digest), self.assertRaisesRegex(ValueError, 'leaked'):
                audit_public_files(data, {'random/renamed.bin': digest}, 'client')

    def test_bundled_bytes_required_only_on_selected_side(self):
        vendor = entry(side='client', delivery='bundle')
        data = catalog(vendor)
        self.assertTrue(audit_public_files(data, {}, 'server'))
        with self.assertRaisesRegex(ValueError, 'missing'):
            audit_public_files(data, {}, 'client')
        self.assertTrue(audit_public_files(data, {vendor['path']: vendor['sha256']}, 'client'))
        with self.assertRaisesRegex(ValueError, 'other side'):
            audit_public_files(data, {vendor['path']: vendor['sha256']}, 'server')


class ArtifactTests(unittest.TestCase):
    def audit(self, data, pins=None):
        vendor = entry(data=data)
        vendor.update(pins or {})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vendor.jar'
            path.write_bytes(data)
            return verify_artifact(vendor, path)

    def test_exact_size_digest_crc_and_java8(self):
        data = artifact()
        self.assertEqual(self.audit(data)['maxJavaClassMajor'], 52)
        for change in ({'size': len(data) + 1}, {'sha256': 'f' * 64}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'checksum or size'):
                self.audit(data, change)

    def test_java17_and_zip_traversal(self):
        with self.assertRaisesRegex(ValueError, 'newer than Java 8'):
            self.audit(artifact({'example/Main.class': b'\xca\xfe\xba\xbe\x00\x00\x00\x3d'}))
        with self.assertRaisesRegex(ValueError, 'Unsafe vendor path'):
            self.audit(artifact({'../escape': b'x'}))

    def test_crc_corruption_is_rejected_even_with_pinned_outer_digest(self):
        data = bytearray(artifact({'plain.txt': b'correct payload'}))
        offset = data.index(b'correct payload')
        data[offset] ^= 1
        with self.assertRaisesRegex(ValueError, 'CRC failed'):
            self.audit(bytes(data))

    def test_definitions_and_embedded_archives_match(self):
        nested = artifact({'model.json': b'{}'})
        data = artifact({'pack.json': b'{}', 'inside.zip': nested})
        pins = {'definitionHashes': {'pack.json': hashlib.sha256(b'{}').hexdigest()}, 'embedded': [{'member': 'inside.zip', 'size': len(nested), 'sha256': hashlib.sha256(nested).hexdigest()}]}
        self.assertTrue(self.audit(data, pins)['crcPassed'])
        pins['embedded'][0]['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'Embedded content checksum'):
            self.audit(data, pins)


class DeliveryTests(unittest.TestCase):
    def test_external_files_owned_in_manifest_but_absent_from_payload(self):
        vendor = entry()
        data = catalog(vendor)
        bundled = b'RV configuration'
        manifest = {'managedFiles': [{'path': vendor['path'], 'sha256': vendor['sha256']}, {'path': 'config/rv.properties', 'sha256': hashlib.sha256(bundled).hexdigest()}]}
        with zipfile.ZipFile(io.BytesIO(artifact({'config/rv.properties': bundled}))) as archive:
            self.assertEqual(verify_managed_delivery(data, manifest, archive, 'client'), {vendor['path']: vendor['sha256']})
        with zipfile.ZipFile(io.BytesIO(artifact({'other.txt': b'x'}))) as archive, self.assertRaisesRegex(ValueError, 'Bundled managed file is missing'):
            verify_managed_delivery(data, manifest, archive, 'client')

    def test_external_manifest_cannot_omit_change_or_preserve_only_vendor(self):
        vendor, data = entry(), catalog()
        for files in ([], [{'path': vendor['path'], 'sha256': 'f' * 64}], [{'path': vendor['path'], 'sha256': vendor['sha256'], 'existingOnly': True}]):
            with self.subTest(files=files), self.assertRaisesRegex(ValueError, 'Acquired vendor pin'):
                external_managed_files(data, {'managedFiles': files}, 'client')

    def test_official_vendor_cannot_be_bundled_to_bypass_acquisition(self):
        vendor, data = entry(), catalog()
        manifest = {'managedFiles': [{'path': vendor['path'], 'sha256': vendor['sha256']}]}
        with zipfile.ZipFile(io.BytesIO(artifact({vendor['path']: artifact()}))) as archive, self.assertRaisesRegex(ValueError, 'Official-download vendor path'):
            verify_managed_delivery(data, manifest, archive, 'client')

    def test_server_manifest_rejects_client_only_artifact(self):
        vendor = entry(side='client')
        manifest = {'managedFiles': [{'path': vendor['path'], 'sha256': vendor['sha256']}]}
        with self.assertRaisesRegex(ValueError, 'Client-only vendor'):
            external_managed_files(catalog(vendor), manifest, 'server')

    def test_release_metadata_binds_native_versions_and_older_updater_size(self):
        data = catalog()
        metadata = {'version': '1.2.0', 'vendorCatalogSha256': 'a' * 64, **protocol_maps(data)}
        validate_release_catalog(data, metadata, 'a' * 64)
        with self.assertRaisesRegex(ValueError, 'digest differs'):
            validate_release_catalog(data, metadata, 'b' * 64)
        metadata['clientRequiredMods'] = {'example': 'file-label-instead-of-native'}
        with self.assertRaisesRegex(ValueError, 'native catalog versions'):
            validate_release_catalog(data, metadata, 'a' * 64)
        metadata.update(protocol_maps(data))
        metadata['padding'] = 'x' * 4096
        with self.assertRaisesRegex(ValueError, 'older updater limit'):
            validate_release_catalog(data, metadata, 'a' * 64)


class FirstPartyTests(unittest.TestCase):
    def fixture(self, root):
        binary = artifact()
        sha = hashlib.sha256(binary).hexdigest()
        source_path = 'patches/compat/RVVehicleCompat.java'
        source = root / source_path
        source.parent.mkdir(parents=True)
        source.write_bytes(b'public class RVVehicleCompat {}')
        records = []
        for side in ('client', 'server'):
            path = 'qa/evidence/rv-compat-' + side + '.json'
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps({'success': True, 'mods': {'rvcompat': '1.2.0'}, 'artifacts': {'mods/rv-compat.jar': sha}}), encoding='utf-8')
            records.append({'side': side, 'path': path, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        mod = {'id': 'rv-compat', 'path': 'mods/rv-compat.jar', 'size': len(binary), 'sha256': sha, 'side': 'both', 'fileVersion': '1.2.0', 'expectedModIds': ['rvcompat'], 'fml': {'rvcompat': '1.2.0'}, 'nativeReceiptSha256': records[0]['sha256'], 'sourceFiles': {source_path: hashlib.sha256(source.read_bytes()).hexdigest()}}
        proof = {'schema': 1, 'mods': [mod], 'nativeReceipts': records}
        path = root / 'pack/rv-managed-mods.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(proof), encoding='utf-8')
        vendor = entry()
        manifest = {'managedFiles': [{'path': vendor['path'], 'sha256': vendor['sha256']}, {'path': mod['path'], 'sha256': sha}]}
        return path, proof, manifest, artifact({mod['path']: binary})

    def test_frozen_registry_source_binary_native_and_protocol_union(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, proof, manifest, payload = self.fixture(root)
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(first_party_proof_path({'managedModsSha256': sha}, root), path)
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                first_party = verify_first_party_proof(path, catalog(), manifest, archive, root)
            self.assertEqual(first_party, {'rvcompat': '1.2.0'})
            maps = protocol_maps(catalog())
            for values in maps.values():
                values.update(first_party)
            metadata = {'vendorCatalogSha256': 'a' * 64, **maps}
            validate_release_catalog(catalog(), metadata, 'a' * 64, first_party)
            with self.assertRaisesRegex(ValueError, 'native catalog versions'):
                validate_release_catalog(catalog(), metadata, 'a' * 64)

    def test_registry_digest_and_source_changes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, proof, manifest, payload = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'release digest'):
                first_party_proof_path({}, root)
            with self.assertRaisesRegex(ValueError, 'release digest'):
                first_party_proof_path({'managedModsSha256': 'f' * 64}, root)
            source_path = next(iter(proof['mods'][0]['sourceFiles']))
            (root / source_path).write_bytes(b'changed source')
            with zipfile.ZipFile(io.BytesIO(payload)) as archive, self.assertRaisesRegex(ValueError, 'frozen closure'):
                verify_first_party_proof(path, catalog(), manifest, archive, root)

    def test_same_version_with_wrong_loaded_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, proof, manifest, payload = self.fixture(root)
            receipt = proof['nativeReceipts'][1]
            target = root / receipt['path']
            data = json.loads(target.read_bytes())
            data['artifacts']['mods/rv-compat.jar'] = 'f' * 64
            target.write_text(json.dumps(data), encoding='utf-8')
            receipt['sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
            path.write_text(json.dumps(proof), encoding='utf-8')
            with zipfile.ZipFile(io.BytesIO(payload)) as archive, self.assertRaisesRegex(ValueError, 'loaded native binary'):
                verify_first_party_proof(path, catalog(), manifest, archive, root)

    def test_manual_proof_cannot_add_private_fields_or_unknown_identities(self):
        changes = (('privatePeer', {'privatePeer': 'fixture'}), ('mods', {'mods': {'rvcompat': '1.2.0', 'unknown': '1.0'}}), ('artifacts', {'artifacts': {'mods/rv-compat.jar': 'a' * 64, 'logs/private.log': 'b' * 64}}))
        for name, change in changes:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, proof, manifest, payload = self.fixture(root)
                receipt = proof['nativeReceipts'][1]
                target = root / receipt['path']
                data = {**json.loads(target.read_bytes()), **change}
                target.write_bytes(json.dumps(data).encode())
                receipt['sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
                path.write_bytes(json.dumps(proof).encode())
                with zipfile.ZipFile(io.BytesIO(payload)) as archive, self.assertRaisesRegex(ValueError, 'only successful FML identities|complete owned module union'):
                    verify_first_party_proof(path, catalog(), manifest, archive, root)

    def test_manual_proof_cannot_reference_private_evidence_location(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, proof, manifest, payload = self.fixture(root)
            receipt = proof['nativeReceipts'][1]
            original = root / receipt['path']
            receipt['path'] = '.local/private-native.json'
            target = root / receipt['path']
            target.parent.mkdir()
            target.write_bytes(original.read_bytes())
            path.write_bytes(json.dumps(proof).encode())
            with zipfile.ZipFile(io.BytesIO(payload)) as archive, self.assertRaisesRegex(ValueError, 'scrubbed public evidence path'):
                verify_first_party_proof(path, catalog(), manifest, archive, root)

    def test_manual_proof_requires_exactly_two_native_sides(self):
        for count in (0, 1, 3):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path, proof, manifest, payload = self.fixture(root)
                proof['nativeReceipts'] = (proof['nativeReceipts'] * 2)[:count]
                path.write_bytes(json.dumps(proof).encode())
                with zipfile.ZipFile(io.BytesIO(payload)) as archive, self.assertRaisesRegex(ValueError, 'Both first-party native runtime receipts'):
                    verify_first_party_proof(path, catalog(), manifest, archive, root)


class DownloadTests(unittest.TestCase):
    def test_verified_cache_and_unknown_target_preserved(self):
        data, vendor = artifact(), entry()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            opener = Opener(data)
            self.assertFalse(fetch(vendor, root, opener)['reused'])
            self.assertTrue(fetch(vendor, root, opener)['reused'])
            self.assertEqual(opener.calls, 1)
            target = root / vendor['path']
            target.write_bytes(b'unknown user mod')
            with self.assertRaisesRegex(ValueError, 'checksum or size'):
                fetch(vendor, root, opener)
            self.assertEqual(target.read_bytes(), b'unknown user mod')
            self.assertFalse(list(root.rglob('*.part')))

    def test_bad_size_digest_and_unapproved_redirect_leave_no_target(self):
        data, vendor = artifact(), entry()
        for opener in (Opener(data, declared=len(data) + 1), Opener(b'x' * len(data)), Opener(data, url='https://evil.example/file.jar')):
            with self.subTest(opener=opener), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaisesRegex(ValueError, 'download failed'):
                    fetch(vendor, root, opener)
                self.assertFalse((root / vendor['path']).exists())
                self.assertFalse(list(root.rglob('*.part')))

    def test_redirect_is_rejected_before_request_is_created(self):
        request = urllib.request.Request('https://edge.forgecdn.net/pinned.jar')
        with self.assertRaisesRegex(ValueError, 'Unapproved'):
            ApprovedRedirects().redirect_request(request, None, 302, 'Found', {}, 'https://evil.example/file.jar')
        approved = ApprovedRedirects().redirect_request(request, None, 302, 'Found', {}, 'https://mediafilez.forgecdn.net/files/3558/882/example.jar')
        self.assertEqual(approved.full_url, 'https://mediafilez.forgecdn.net/files/3558/882/example.jar')

    def test_manual_pin_gives_actionable_page_without_network_or_writes(self):
        vendor, opener = entry(delivery='manual'), Opener(artifact())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'official page'):
                fetch(vendor, root, opener)
            self.assertEqual(opener.calls, 0)
            self.assertEqual(list(root.iterdir()), [])

    def test_fetch_rejects_escape_path_before_writes(self):
        vendor = entry()
        vendor['path'] = '../escape.jar'
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, 'Unsafe'):
            fetch(vendor, directory, Opener(artifact()))


if __name__ == '__main__':
    unittest.main()
