import gzip
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import shutil
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from package_world_template import package
from stage_world_template import stage


class WorldPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rv-world-package-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.stage = self.root / 'stage'
        self.name = 'Battlefield-Extended'
        self.world = self.stage / self.name
        for path in ('region', 'data/functions/warfare'):
            (self.world / path).mkdir(parents=True, exist_ok=True)
        (self.world / 'region/r.0.0.mca').write_bytes(b'region-fixture')
        (self.world / 'level.dat').write_bytes(gzip.compress(b'level-fixture', mtime=123))
        (self.world / 'data/scoreboard.dat').write_bytes(gzip.compress(b'scoreboard-fixture', mtime=123))
        for name in ('tick', 'boot', 'book_tick', 'book_setup', 'book_give_en', 'book_give_ru'):
            (self.world / 'data/functions/warfare' / (name + '.mcfunction')).write_text('fixture\n')
        (self.stage / 'INSTALL-NEW-WORLD.md').write_text('Fixture guide')
        self.manifest = {'name': self.name, 'functionsIncluded': True, 'playerBookIncluded': True, 'scoreboardIncluded': True, 'scoreboardPlayerEntries': 0, 'regions': [{}], 'functionCount': 6}
        self.refresh()

    def refresh(self):
        self.manifest['files'] = {p.relative_to(self.stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.world.rglob('*') if p.is_file()}
        (self.stage / 'world-template-manifest.json').write_text(json.dumps(self.manifest))

    def test_archive_checksums_and_nbt_bytes(self):
        archive = self.root / 'one.zip'
        package(self.stage, archive)
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(gzip.decompress(z.read(self.name + '/level.dat')), b'level-fixture')
            manifest = json.loads(z.read('world-template-manifest.json'))
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), digest)

    def test_gzip_timestamp_does_not_change_archive(self):
        first, second = self.root / 'one.zip', self.root / 'two.zip'
        package(self.stage, first)
        (self.world / 'level.dat').write_bytes(gzip.compress(b'level-fixture', mtime=456))
        self.refresh()
        package(self.stage, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_modified_stage_rejected_without_output(self):
        (self.world / 'region/r.0.0.mca').write_bytes(b'changed')
        output = self.root / 'bad.zip'
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            package(self.stage, output)
        self.assertFalse(output.exists())

    def test_unlisted_private_file_rejected(self):
        (self.world / 'playerdata').mkdir()
        (self.world / 'playerdata/player.dat').write_bytes(b'private')
        self.refresh()
        with self.assertRaisesRegex(ValueError, 'Unexpected world stage file'):
            package(self.stage, self.root / 'bad.zip')

    def test_geometry_only_rejected(self):
        self.manifest['functionsIncluded'] = False
        self.refresh()
        with self.assertRaisesRegex(ValueError, 'complete integrated'):
            package(self.stage, self.root / 'bad.zip')

    def test_existing_output_preserved(self):
        output = self.root / 'existing.zip'
        output.write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            package(self.stage, output)
        self.assertEqual(output.read_bytes(), b'keep')

    def test_only_complete_curated_decoration_functions_are_allowed(self):
        directory = self.world / 'data/functions/rvmap'
        directory.mkdir()
        for name in ['tree_' + str(number).zfill(2) for number in range(1, 13)] + ['plants']:
            (directory / (name + '.mcfunction')).write_text('fixture\n')
        self.manifest['functionCount'] = 19
        self.refresh()
        package(self.stage, self.root / 'curated.zip')
        (directory / 'tree_12.mcfunction').unlink()
        self.manifest['functionCount'] = 18
        self.refresh()
        with self.assertRaisesRegex(ValueError, 'decoration functions are incomplete'):
            package(self.stage, self.root / 'incomplete.zip')

    def test_arbitrary_map_function_namespace_or_tree_is_rejected(self):
        for name in ('data/functions/rvmap/tree_13.mcfunction', 'data/functions/rvmap/arbitrary.mcfunction', 'data/functions/unrelated/plants.mcfunction'):
            with self.subTest(name=name):
                path = self.world / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture\n')
                self.refresh()
                with self.assertRaisesRegex(ValueError, 'Unexpected world stage file'):
                    package(self.stage, self.root / 'bad.zip')
                path.unlink()

    @unittest.skipUnless(importlib.util.find_spec('nbtlib'), 'Run with the world build dependencies')
    def test_staging_and_packaging_preserve_authoritative_team_functions(self):
        import nbtlib
        nbtlib.File({'Data': nbtlib.Compound({'GameRules': nbtlib.Compound({})})}).save(self.world / 'level.dat', gzipped=True)
        functions = self.root / 'supplied-functions'
        functions.mkdir()
        for source in (self.world / 'data/functions/warfare').glob('*.mcfunction'):
            shutil.copy2(source, functions / source.name)
        canonical = Path(__file__).resolve().parents[1] / 'pack/server-functions/warfare'
        supplied = {name: (canonical / (name + '.mcfunction')).read_bytes() for name in ('blue', 'red')}
        for name, data in supplied.items():
            self.assertIn(b'rvx team ', data)
            self.assertNotIn(b'tp @s', data)
            self.assertNotIn(b'spawnpoint @s', data)
            (functions / (name + '.mcfunction')).write_bytes(data)
        frozen = self.root / 'frozen-world'
        stage(self.world, functions, frozen)
        archive = self.root / 'authority-preserved.zip'
        package(frozen, archive)
        with zipfile.ZipFile(archive) as content:
            for name, data in supplied.items():
                relative = self.name + '/data/functions/warfare/' + name + '.mcfunction'
                self.assertEqual((frozen / relative).read_bytes(), data)
                self.assertEqual(content.read(relative), data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
