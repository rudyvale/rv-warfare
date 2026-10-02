# Development

## Run checks on Windows

Use Windows PowerShell 5.1 and Python 3.12 or newer. Launcher checks use Python's standard library.

```powershell
$env:VM_SKIP_UPDATE_CHECK = '1'
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_updates.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_connection.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_gui.ps1
python -X utf8 qa/test_connection_launch.py
python -X utf8 qa/test_launcher.py
python -X utf8 qa/test_host.py
python -X utf8 qa/test_host_races.py
python -X utf8 host/warfare-launcher.py --check
```

Launch-flow tests substitute Steam, Porthole and Java. Protocol tests use a local test socket. They do not establish a connection between two physical computers. Full installation tests need an extracted release package and create isolated test directories under `qa`.

## Build a release

Extract a published **RV-Setup.zip** into a separate directory. Its `payload.zip` and `runtime.zip` form the binary base; hashes are checked against that directory's `package-manifest.json`. The copy in `pack` records the released package contents.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_icon.ps1
python tools/build_world_template.py
python qa/test_world_template.py --full
python tools/build_release.py --base C:/Build/RV-Setup --output dist --world-template dist/RV-World-Template.zip
python tools/verify_release.py --directory dist
python qa/validate_package.py dist/RV-Setup.zip
python qa/test_release_install.py --package dist/RV-Setup
```

The world generator refuses to overwrite existing output. Use a fresh checkout for a clean build. Omit `--world-template` when intentionally building without the optional map.

The release contains **RV-Setup.zip**, **RV-Host-Tools.zip**, **SHA256SUMS.txt** and the optional world template. Public packages have an empty server destination. Existing user settings are preserved during installation.

A personal package can use `--private --defaults C:/Private/server-defaults.json`. Its default output is `dist-private`; never publish this archive or add its defaults to Git. Installing a public update over it preserves the user's selected destination.

See [UPDATES.md](UPDATES.md) for publishing and remote verification.

## Mod changes

`patches/java` contains source snapshots used while modifying MC Heli CE and Techguns, including `WarfareFpv` and `WarfareQuickUav`. `patches/controls` contains controller changes. `patches/build` holds audio, patch and world preparation tools.

These are modification materials, not complete upstream checkouts. Rebuilding mods requires the matching upstream sources, Forge dependencies, compiler and prepared classes. Individual Java snapshots are not a standalone Gradle project.

The client archive can be assembled from the published binary base and this repository. Byte-for-byte reproducibility of recompiled third-party mods is not claimed.
