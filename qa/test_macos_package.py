import importlib.util
import io
from pathlib import Path
import sys
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_macos import installer_for_macos, osx_allowed, put


class MacPackageTests(unittest.TestCase):
    def test_mojang_disallow_rule_removes_windows_lwjgl(self):
        self.assertFalse(osx_allowed({'rules': [{'action': 'allow'}, {'action': 'disallow', 'os': {'name': 'osx'}}]}))
        self.assertTrue(osx_allowed({'rules': [{'action': 'allow', 'os': {'name': 'osx'}}]}))
        self.assertFalse(osx_allowed({'rules': [{'action': 'allow', 'os': {'name': 'windows'}}]}))

    def test_conversion_preserves_forge_and_assets_but_replaces_native_platform(self):
        vanilla = {'libraries': [
            {'downloads': {'artifact': {'path': 'lwjgl/new.jar', 'url': 'https://libraries.minecraft.net/new', 'sha1': '1' * 40}}, 'rules': [{'action': 'allow'}, {'action': 'disallow', 'os': {'name': 'osx'}}]},
            {'downloads': {'artifact': {'path': 'lwjgl/mac.jar', 'url': 'https://libraries.minecraft.net/mac', 'sha1': '2' * 40}, 'classifiers': {'natives-osx': {'path': 'lwjgl/natives-osx.jar', 'url': 'https://libraries.minecraft.net/native', 'sha1': '3' * 40}}}, 'natives': {'osx': 'natives-osx'}, 'rules': [{'action': 'allow', 'os': {'name': 'osx'}}]}
        ]}
        forge = dict(path='libraries/forge.jar', url='https://maven.minecraftforge.net/forge', sha1='4' * 40, native=False)
        asset = dict(path='assets/objects/aa/' + 'a' * 40, url='https://resources.download.minecraft.net/a', sha1='a' * 40, native=False)
        installer = dict(mainClass='net.minecraft.launchwrapper.Launch', assetIndex='1.12', classpath=['libraries/lwjgl/new.jar', forge['path']], files=[forge, asset, dict(path='libraries/lwjgl/new.jar', native=False), dict(path='libraries/natives-windows.jar', native=True)])
        result = installer_for_macos(installer, vanilla)
        self.assertEqual(result['classpath'], ['libraries/lwjgl/mac.jar', forge['path']])
        self.assertIn(forge, result['files'])
        self.assertIn(asset, result['files'])
        self.assertEqual([x['path'] for x in result['files'] if x.get('native')], ['libraries/lwjgl/natives-osx.jar'])
        self.assertFalse(any('windows' in x['path'] for x in result['files']))

    def test_archive_path_escape_is_rejected(self):
        for name in ('../evil', '/evil', 'a/../evil', 'C:/evil', 'a\\evil'):
            with self.subTest(name=name), zipfile.ZipFile(io.BytesIO(), 'w') as archive:
                with self.assertRaises(ValueError):
                    put(archive, name, b'bad')

    def test_mac_executable_permission_survives_windows_builder(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            put(archive, 'RV.app/Contents/MacOS/RVLauncher', b'#!/bin/sh\n', 0o755)
        with zipfile.ZipFile(stream) as archive:
            entry = archive.getinfo('RV.app/Contents/MacOS/RVLauncher')
            self.assertEqual(entry.create_system, 3)
            self.assertEqual((entry.external_attr >> 16) & 0o777, 0o755)


if __name__ == '__main__':
    unittest.main()
