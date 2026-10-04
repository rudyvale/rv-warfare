import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_controls_overlay as overlay


def fixture_class(name, major=52):
    def utf8(value):
        data = value.encode('ascii')
        return b'\x01' + struct.pack('>H', len(data)) + data
    pool = utf8(name) + b'\x07\x00\x01' + utf8('java/lang/Object') + b'\x07\x00\x03'
    return b'\xca\xfe\xba\xbe' + struct.pack('>HHH', 0, major, 5) + pool + struct.pack('>HHHHHHH', 0x21, 2, 4, 0, 0, 0, 0)


class ControlsOverlayTests(unittest.TestCase):
    SOURCES = ['VMEasy.java', 'VMImpact.java']
    RESOURCES = ['assets/mcheli/helicopters/rc-goblin.yml', 'assets/mcheli/helicopters/rc-goblin-bomb.yml']

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='rv-controls-overlay-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / 'fixture-game'
        self.java = self.game / 'runtime/bin/java.exe'
        self.java.parent.mkdir(parents=True)
        self.java.write_bytes(b'fixture Java 8 executable')
        library = self.game / 'libraries/fixture-api.jar'
        library.parent.mkdir(parents=True)
        library.write_bytes(b'fixture compile library')
        self.compiler = self.root / 'fixture-ecj.jar'
        self.compiler.write_bytes(b'fixture pinned compiler')
        self.original = {overlay.PACKAGE + 'VMEasy.class': fixture_class(overlay.PACKAGE + 'VMEasy') + b'original easy', overlay.PACKAGE + 'VMImpact.class': fixture_class(overlay.PACKAGE + 'VMImpact') + b'original impact', 'other/mch/Hook.class': b'untouched ASM hook bytes', 'META-INF/MANIFEST.MF': b'Manifest-Version: 1.0\nFMLCorePlugin: ExistingPlugin\n'}
        for name in self.RESOURCES:
            self.original[name] = b'original resource ' + name.encode()
        self.base = self.root / 'base.jar'
        self.write_base(self.original.items())
        for name in self.SOURCES:
            path = self.root / 'patches/controls' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('package com.norwood.mcheli.vm; public final class ' + Path(name).stem + ' {}\n').encode())
        for name in self.RESOURCES:
            path = self.root / 'patches/controls/resources' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'captured replacement resource ' + name.encode())
        self.compiled = {overlay.PACKAGE + Path(name).stem + '.class': fixture_class(overlay.PACKAGE + Path(name).stem) for name in self.SOURCES}
        self.compile_callback = None
        self.commands = []
        self.patch('BASE_SHA256', overlay.file_digest(self.base))
        self.patch('COMPILER_SHA256', overlay.file_digest(self.compiler))
        runner = patch('build_controls_overlay.subprocess.run', side_effect=self.run_java)
        runner.start()
        self.addCleanup(runner.stop)

    def patch(self, name, value):
        changed = patch.object(overlay, name, value)
        changed.start()
        self.addCleanup(changed.stop)

    def write_base(self, entries):
        with zipfile.ZipFile(self.base, 'w') as archive:
            archive.comment = b'preserved archive comment'
            for name, data in entries:
                info = zipfile.ZipInfo(name, (2025, 1, 2, 3, 4, 6))
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)

    def run_java(self, command, **options):
        self.commands.append(command)
        if command[1:] == ['-version']:
            return subprocess.CompletedProcess(command, 0, '', 'java version "1.8.0_412"\n')
        classes = Path(command[command.index('-d') + 1])
        capture_path = classes.parent / 'capture.json'
        self.assertTrue(capture_path.is_file())
        capture = json.loads(capture_path.read_text())
        for name, expected in capture['inputFiles'].items():
            self.assertEqual(overlay.file_digest(classes.parent / name), expected)
        self.assertIn('-1.8', command)
        self.assertIn('-proc:none', command)
        self.assertFalse(any('patch-controls.js' in part or 'patch-props.js' in part for part in command))
        if self.compile_callback is not None:
            self.compile_callback(command, capture)
        for name, data in self.compiled.items():
            path = classes / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return subprocess.CompletedProcess(command, 0, '', '')

    def build(self, output=None, **options):
        return overlay.build(self.root, self.game, self.base, self.compiler, output or self.root / '.local/overlay-candidate', **{'sources': self.SOURCES, 'resources': self.RESOURCES, **options})

    def test_overlay_preserves_unrelated_bytes_metadata_order_and_comment(self):
        proof = self.build()
        output = self.root / '.local/overlay-candidate'
        with zipfile.ZipFile(self.base) as before, zipfile.ZipFile(output / proof['candidate']) as after:
            self.assertEqual(before.namelist(), after.namelist())
            self.assertEqual(before.comment, after.comment)
            for name in ('other/mch/Hook.class', 'META-INF/MANIFEST.MF'):
                self.assertEqual(before.read(name), after.read(name))
                self.assertEqual(before.getinfo(name).date_time, after.getinfo(name).date_time)
                self.assertEqual(before.getinfo(name).external_attr, after.getinfo(name).external_attr)
            self.assertIsNone(after.testzip())
        self.assertEqual(set(proof['changedArchiveMembers']), set(self.compiled) | set(self.RESOURCES))
        self.assertTrue(proof['unrelatedArchiveMembersBytePreserved'])
        self.assertFalse(proof['asmReapplied'])
        self.assertFalse(proof['nativeVerified'])
        self.assertFalse(proof['published'])

    def test_identical_captured_inputs_produce_identical_jar_bytes(self):
        first = self.build(self.root / '.local/repro-a')
        second = self.build(self.root / '.local/repro-b')
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual((self.root / '.local/repro-a' / first['candidate']).read_bytes(), (self.root / '.local/repro-b' / second['candidate']).read_bytes())

    def test_source_change_during_compile_uses_only_the_precompile_snapshot(self):
        source = self.root / 'patches/controls/VMEasy.java'
        expected = overlay.file_digest(source)
        def mutate(command, capture):
            source.write_bytes(b'changed checkout after capture')
            selected = [Path(value) for value in command if value.endswith('.java')]
            self.assertTrue(all(path.is_relative_to(self.root / '.local/overlay-candidate/captured-source') for path in selected))
        self.compile_callback = mutate
        proof = self.build()
        self.assertEqual(proof['sourceFiles']['patches/controls/VMEasy.java'], expected)

    def test_captured_input_mutation_fails_before_candidate_archive(self):
        def mutate(command, capture):
            path = self.root / '.local/overlay-candidate/captured-source/patches/controls/VMEasy.java'
            path.write_bytes(b'modified captured compile input')
        self.compile_callback = mutate
        with self.assertRaisesRegex(ValueError, 'compile input changed'):
            self.build()
        self.assertFalse((self.root / '.local/overlay-candidate/mcheli-controls-overlay.jar').exists())

    def test_pinned_base_and_compiler_mismatch_fail_before_output_or_compile(self):
        for path in (self.base, self.compiler):
            with self.subTest(path=path):
                old = path.read_bytes()
                path.write_bytes(old + b'changed')
                with self.assertRaisesRegex(ValueError, 'pinned'):
                    self.build()
                path.write_bytes(old)
                self.assertEqual(self.commands, [])
                self.assertFalse((self.root / '.local').exists())

    def test_missing_source_and_wrong_source_identity_fail_before_output(self):
        source = self.root / 'patches/controls/VMEasy.java'
        source.unlink()
        with self.assertRaises(FileNotFoundError):
            self.build()
        source.write_bytes(b'package another.namespace; public class VMEasy {}')
        with self.assertRaisesRegex(ValueError, 'source identity'):
            self.build()
        self.assertEqual(self.commands, [])
        self.assertFalse((self.root / '.local').exists())

    def test_source_override_is_captured_under_the_canonical_source_key(self):
        override = self.root / 'approved-easy.java'
        override.write_bytes(b'package com.norwood.mcheli.vm; public final class VMEasy { public int changed = 1; }')
        proof = self.build(overrides={'patches/controls/VMEasy.java': override})
        self.assertEqual(proof['sourceFiles']['patches/controls/VMEasy.java'], overlay.file_digest(override))
        capture = json.loads((self.root / '.local/overlay-candidate/capture.json').read_text())
        self.assertEqual(capture['sourceOverrides'], ['patches/controls/VMEasy.java'])

    def test_fpv_resource_lf_policy_preserves_raw_source_proof(self):
        name = self.RESOURCES[0]
        source = self.root / 'patches/controls/resources' / name
        raw = b'name: FPV\r\nvelocity: 0.60\r\n'
        source.write_bytes(raw)
        proof = self.build()
        output = self.root / '.local/overlay-candidate'
        capture = json.loads((output / 'capture.json').read_text())
        self.assertEqual(proof['sourceFiles']['patches/controls/resources/' + name], overlay.digest(raw))
        self.assertEqual(capture['resourceNormalization'][name], 'CRLF to LF')
        self.assertEqual(capture['resourceOverlaySha256'][name], overlay.digest(raw.replace(b'\r\n', b'\n')))
        with zipfile.ZipFile(output / proof['candidate']) as archive:
            self.assertEqual(archive.read(name), raw.replace(b'\r\n', b'\n'))
        self.assertEqual(source.read_bytes(), raw)

    def test_other_resource_bytes_are_never_normalized(self):
        name = 'assets/mcheli/planes/rv_fp1.yml'
        raw = b'name: original wing\r\nvelocity: unchanged\r\n'
        self.original[name] = raw
        self.write_base(self.original.items())
        self.patch('BASE_SHA256', overlay.file_digest(self.base))
        source = self.root / 'patches/controls/resources' / name
        source.parent.mkdir(parents=True)
        source.write_bytes(raw)
        proof = self.build(resources=self.RESOURCES + [name])
        with zipfile.ZipFile(self.root / '.local/overlay-candidate' / proof['candidate']) as archive:
            self.assertEqual(archive.read(name), raw)
        self.assertNotIn(name, proof['changedArchiveMembers'])
        self.assertNotIn(name, proof['resourceNormalization'])

    def test_unselected_override_unknown_source_and_unknown_resource_are_rejected(self):
        cases = ({'overrides': {'patches/controls/VMProps.java': self.root / 'other.java'}}, {'sources': self.SOURCES + ['Unexpected.java']}, {'resources': self.RESOURCES + ['assets/mcheli/secret.yml']}, {'sources': self.SOURCES + self.SOURCES})
        for options in cases:
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.build(**options)
        self.assertEqual(self.commands, [])

    def test_existing_public_installed_or_world_output_is_refused(self):
        existing = self.root / '.local/existing'
        existing.mkdir(parents=True)
        paths = (existing, self.root / 'public-output', self.game / '.local/candidate', self.root / '.local/native/world/candidate', self.root / '.local/releases/private-candidate', self.root / '.local/public/candidate')
        for path in paths:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.build(path)
        world = self.root / '.local/custom-world-name'
        world.mkdir()
        (world / 'level.dat').write_bytes(b'private existing world')
        with self.assertRaisesRegex(ValueError, 'private world'):
            self.build(world / 'candidate')
        self.assertEqual(self.commands, [])

    def test_duplicate_case_colliding_and_unsafe_archive_members_are_refused(self):
        for entries in ([('one', b'a'), ('one', b'b')], [('One', b'a'), ('one', b'b')], [('../escape', b'a')], [('folder\\escape', b'a')], [('/absolute', b'a')], [('C:escape', b'a')]):
            with self.subTest(entries=entries):
                buffer = io.BytesIO()
                with warnings.catch_warnings(), zipfile.ZipFile(buffer, 'w') as archive:
                    warnings.simplefilter('ignore', UserWarning)
                    for name, data in entries:
                        archive.writestr(name, data)
                data = buffer.getvalue()
                if entries[0][0] == 'folder\\escape':
                    data = data.replace(b'folder/escape', b'folder\\escape')
                with self.assertRaises(ValueError):
                    overlay.read_archive(data)

    def test_corrupt_crc_archive_fails_closed(self):
        data = self.base.read_bytes()
        corrupted = data.replace(b'untouched ASM hook bytes', b'corrupted ASM hook bytes')
        self.assertNotEqual(corrupted, data)
        with self.assertRaises(zipfile.BadZipFile):
            overlay.read_archive(corrupted)

    def test_unexpected_emitted_class_or_resource_is_refused(self):
        for name, data in (('com/norwood/mcheli/NativeHook.class', fixture_class('com/norwood/mcheli/NativeHook')), (overlay.PACKAGE + 'Unexpected.class', fixture_class(overlay.PACKAGE + 'Unexpected')), ('assets/mcheli/not-source.yml', b'unexpected resource')):
            with self.subTest(name=name):
                self.compiled[name] = data
                with self.assertRaisesRegex(ValueError, 'unexpected overlay member'):
                    self.build(self.root / '.local' / ('bad-output-' + str(len(self.commands))))
                del self.compiled[name]

    def test_wrong_major_truncated_class_and_wrong_internal_name_are_rejected(self):
        name = overlay.PACKAGE + 'VMEasy.class'
        cases = (fixture_class(overlay.PACKAGE + 'VMEasy', major=53), fixture_class(overlay.PACKAGE + 'VMEasy')[:15], fixture_class(overlay.PACKAGE + 'VMImpact'))
        for data in cases:
            with self.subTest(data=data):
                self.compiled[name] = data
                with self.assertRaises(ValueError):
                    self.build(self.root / '.local' / ('bad-class-' + str(len(self.commands))))

    def test_missing_required_class_is_not_replaced_with_old_binary(self):
        del self.compiled[overlay.PACKAGE + 'VMImpact.class']
        with self.assertRaisesRegex(ValueError, 'missing or unexpected members'):
            self.build()
        self.assertFalse((self.root / '.local/overlay-candidate/mcheli-controls-overlay.jar').exists())

    def test_new_transformer_is_allowed_only_if_its_source_was_captured(self):
        source = self.root / 'patches/controls/VMPropsTransformer.java'
        source.write_bytes(b'package com.norwood.mcheli.vm; public final class VMPropsTransformer {}')
        name = overlay.PACKAGE + 'VMPropsTransformer.class'
        self.compiled[name] = fixture_class(overlay.PACKAGE + 'VMPropsTransformer')
        with self.assertRaisesRegex(ValueError, 'unexpected overlay member'):
            self.build(self.root / '.local/helper-not-selected')
        proof = self.build(self.root / '.local/helper-selected', sources=self.SOURCES + ['VMPropsTransformer.java'])
        self.assertEqual(proof['addedArchiveMembers'], [name])
        self.assertIn('patches/controls/VMPropsTransformer.java', proof['sourceFiles'])

    def test_missing_base_and_full_source_list_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'Canonical controls source list'):
            self.build(sources=None)
        self.base.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing pinned base'):
            self.build()
        self.assertEqual(self.commands, [])

    def test_java_version_and_compiler_failure_do_not_produce_candidate(self):
        runner = patch('build_controls_overlay.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '', 'java version "17.0.2"'))
        with runner, self.assertRaisesRegex(ValueError, 'Java 8 runtime'):
            self.build()
        def fail(command, **options):
            if command[1:] == ['-version']:
                return subprocess.CompletedProcess(command, 0, '', 'java version "1.8.0_412"')
            return subprocess.CompletedProcess(command, 1, '', 'fixture compile failed')
        with patch('build_controls_overlay.subprocess.run', side_effect=fail), self.assertRaises(subprocess.CalledProcessError):
            self.build()
        self.assertFalse((self.root / '.local/overlay-candidate/mcheli-controls-overlay.jar').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
