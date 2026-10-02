import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from release_contract import load_addon_map, validate_addon_resources


def archive(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as result:
        for name, data in entries.items():
            result.writestr(name, data)
    stream.seek(0)
    return zipfile.ZipFile(stream)


class AddonReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.resources = {'assets/mcheli/models/planes/rv_fp1.mqo': b'new plane', 'assets/mcheli/helicopters/rc-goblin.yml': b'new quad'}
        self.required = {name: hashlib.sha256(data).hexdigest() for name, data in self.resources.items()}
        self.payload = {'mcheli_addons/default/' + name: data for name, data in self.resources.items()}
        self.manifest = {'managedFiles': [{'path': 'mcheli_addons/default/' + name, 'sha256': digest, 'existingOnly': True} for name, digest in self.required.items()]}

    def check(self):
        with archive(self.payload) as payload, archive(self.resources) as builtin:
            return validate_addon_resources(self.manifest, payload, builtin, self.required)

    def test_frozen_native_bundle_matches_jar(self):
        self.assertEqual(self.check(), self.required)

    def test_old_native_model_rejected_even_with_matching_manifest(self):
        entry = self.manifest['managedFiles'][0]
        old = b'old helicopter'
        self.payload[entry['path']] = old
        entry['sha256'] = hashlib.sha256(old).hexdigest()
        with self.assertRaisesRegex(ValueError, 'differs from the builtin'):
            self.check()

    def test_cold_partial_default_creation_rejected(self):
        self.manifest['managedFiles'][0]['existingOnly'] = False
        with self.assertRaisesRegex(ValueError, 'existingOnly=true'):
            self.check()

    def test_custom_addon_cannot_be_managed(self):
        self.manifest['managedFiles'][0]['path'] = self.manifest['managedFiles'][0]['path'].replace('/default/', '/personal-addon/')
        with self.assertRaisesRegex(ValueError, 'bounded default'):
            self.check()

    def test_omitted_new_plane_rejected(self):
        self.manifest['managedFiles'].pop(0)
        with self.assertRaisesRegex(ValueError, 'frozen resource map'):
            self.check()

    def test_missing_builtin_resource_rejected(self):
        self.resources.pop('assets/mcheli/models/planes/rv_fp1.mqo')
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.check()

    def test_unapproved_extra_stock_resource_rejected(self):
        name = 'assets/mcheli/models/tanks/unrelated.mqo'
        data = b'unrelated existing tank'
        self.resources[name] = data
        self.payload['mcheli_addons/default/' + name] = data
        self.manifest['managedFiles'].append({'path': 'mcheli_addons/default/' + name, 'sha256': hashlib.sha256(data).hexdigest(), 'existingOnly': True})
        with self.assertRaisesRegex(ValueError, 'frozen resource map'):
            self.check()

    def load(self, changes=None, expected='a' * 64):
        data = {'schema': 1, 'mcheliSha256': 'a' * 64, 'resources': self.required}
        data.update(changes or {})
        with tempfile.TemporaryDirectory(prefix='rv-addon-map-') as temporary:
            path = Path(temporary) / 'map.json'
            path.write_text(json.dumps(data))
            return load_addon_map(path, expected)

    def test_frozen_map_bound_to_exact_jar(self):
        self.assertEqual(self.load(), self.required)

    def test_map_from_another_jar_rejected(self):
        with self.assertRaisesRegex(ValueError, 'another MCHeli JAR'):
            self.load(expected='b' * 64)

    def test_unknown_map_schema_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Invalid frozen addon resource map'):
            self.load({'schema': 2})

    def test_unsafe_or_duplicate_map_path_rejected(self):
        for name in ('assets/mcheli/../personal.cfg', 'assets/mcheli/model:stream', 'mcheli_addons/personal/model.mqo'):
            with self.assertRaisesRegex(ValueError, 'resource path'):
                self.load({'resources': {name: 'a' * 64}})
        with self.assertRaisesRegex(ValueError, 'resource path'):
            self.load({'resources': {'assets/mcheli/models/rv_fp1.mqo': 'a' * 64, 'assets/mcheli/models/RV_FP1.mqo': 'b' * 64}})

    def test_invalid_map_checksum_rejected(self):
        with self.assertRaisesRegex(ValueError, 'resource checksum'):
            self.load({'resources': {'assets/mcheli/models/planes/rv_fp1.mqo': 'invalid'}})


if __name__ == '__main__':
    unittest.main(verbosity=2)
