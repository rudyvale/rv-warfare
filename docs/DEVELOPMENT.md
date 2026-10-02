# Development

## Run checks on Windows

Use Windows PowerShell 5.1 and Python 3.12 or newer. Launcher checks use Python's standard library.

```powershell
$env:VM_SKIP_UPDATE_CHECK = '1'
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_updates.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_connection.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_performance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_duplicate_mods.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_onboarding.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File qa/test_gui.ps1
python -X utf8 qa/test_connection_launch.py
python -X utf8 qa/test_launcher.py
python -X utf8 qa/test_host.py
python -X utf8 qa/test_host_races.py
python -X utf8 qa/test_release_contract.py
python -X utf8 qa/test_addon_release_contract.py
python -X utf8 qa/test_release_output.py
python -X utf8 qa/test_release_candidate.py
python -X utf8 qa/test_release_base.py
python -X utf8 qa/test_release_verifier.py
python -X utf8 qa/test_release_sources.py
python -X utf8 qa/test_third_party_sources.py
python -X utf8 qa/test_payload_repack.py
python -X utf8 host/warfare-launcher.py --check
```

Launch-flow tests substitute Steam, Porthole and Java. Protocol tests use a local test socket. They do not establish a connection between two physical computers. Full installation tests need an extracted release package and create isolated test directories under `qa`.

## Build a release

Download a published **RV-Setup.zip** into a fresh directory with `tools/download_release_base.py --tag v1.0.0 --output .local/baseline-v1.0.0`. The tool checks GitHub's asset origin, size and digest, package metadata, ZIP paths and all nested archive and managed-file hashes. It creates an extracted `RV-Setup` directory and `baseline-report.json`. It refuses an existing output directory.

The base's `payload.zip` and `runtime.zip` must match the frozen gameplay manifest in `pack`. A new gameplay release needs a newly integrated and independently verified binary base; downloading the previous release does not create one.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build_icon.ps1
python tools/build_world_template.py
python qa/test_world_template.py --full
python -m pip install -r requirements-world.txt
python tools/build_player_guide.py
python tools/build_server_gameplay.py --output .local/server-gameplay --book .local/player-guide/warfare
python qa/test_player_guide.py --functions .local/server-gameplay/warfare
python tools/stage_world_template.py --template .local/world-template/Battlefield-Extended --functions .local/server-gameplay/warfare --output .local/release-world
python tools/package_world_template.py --stage .local/release-world --output .local/RV-World-Template.zip
python tools/build_third_party_sources.py --output .local/RV-Third-Party-Sources.zip
python tools/build_release.py --base C:/Build/RV-Setup --output .local/releases/candidate-public --world-template .local/RV-World-Template.zip --third-party-sources .local/RV-Third-Party-Sources.zip
python tools/verify_release.py --directory .local/releases/candidate-public
python qa/validate_package.py .local/releases/candidate-public/RV-Setup.zip
python qa/test_release_install.py --package .local/releases/candidate-public/RV-Setup
```

The world generator and integrated world packager refuse to overwrite existing output. Use a fresh checkout for a clean build. World integration is tested with Python 3.14, nbtlib 2.0.4 and NumPy 2.5.3; the pinned dependencies are separate from the launcher. The generic functions in `pack/server-functions/warfare` contain no owner policy or player records. Omit `--world-template` when intentionally building without the optional map.

The release contains **RV-Setup.zip**, **RV-Host-Tools.zip**, **SHA256SUMS.txt** and the optional world template. Starting with 1.1.0, it also includes **RV-Third-Party-Sources.zip**. The verified original source archives and license texts are pinned in `pack/third-party-sources.json`; the packager verifies their association with the exact unmodified vendor JAR hashes in the payload. Source notices are included at the root of both tool archives and as a managed file in the installed client. Public packages have an empty server destination. Existing user settings are preserved during installation.

Each build records its version, public/private type and asset hashes in `.release-candidate.json`. Use a fresh output for a new version. `--replace-candidate` can rebuild only an unpublished candidate of the same version and type. Published outputs and legacy directories containing release archives cannot be overwritten. Keep the marker with the candidate; it is not uploaded to GitHub.

A personal package can use `--private --defaults C:/Private/server-defaults.json --output .local/releases/candidate-private`. Never publish this archive or add its defaults to Git. The publisher rejects private candidate markers. Installing a public update over it preserves the user's selected destination.

See [UPDATES.md](UPDATES.md) for publishing and remote verification.

## Mod changes

The packager requires the exact managed file list, hashes, preservation policies, mod retirement patterns and OptiFine checksum from the tracked manifest, plus the runtime archive hash. Only `READ-ME.md` may change during guide replacement. A previous gameplay base cannot be used for a new gameplay release. Update the tracked manifest only from the frozen, independently verified integration candidate.

Starting with 1.1.0, both packages include `Warfare-Connection.ps1`, `Warfare-Performance.ps1`, `Warfare-Onboarding.ps1` and `Configure-FirstPlay.ps1`. The first-play setup uses the same implementation for the client and host; owner mode receives the actual owner game directory. Host tools also include `Porthole-Host.ps1` and `Get-ClientMemory.ps1`; the latter uses the shared client memory calculation and saved settings. `release.json` records the actual advertised server mod versions in `requiredMods`; these values must come from a status response from the final Forge server. The verifier compares packaged client and host sources, public defaults and the icon with the frozen checkout. Validation remains active under Python's optimized mode.

MC Heli keeps previously extracted default content. A new JAR alone does not refresh those models and textures. `pack/rv-addon-assets.json` records the exact approved builtin resource paths and hashes from the frozen JAR. Native addon entries must use `existingOnly=true`, match that map exactly and contain the same bytes as the corresponding JAR resources. The installer updates this bounded set with backups while preserving unrelated files and custom addons. The host archive includes an identical `rv-addon-assets.json` at its root for the server's bounded updater. The release verifier checks its exact bytes against the frozen source. Cold installations let MC Heli extract the complete default content. Final upgrade acceptance must check actual loaded geometry, textures, HUD and new aircraft with an old extracted default addon present.

`patches/java` contains source snapshots used while modifying MC Heli CE and Techguns, including `WarfareFpv` and `WarfareQuickUav`. `patches/controls` contains controller changes. `patches/build` holds audio, patch and world preparation tools.

These are modification materials, not complete upstream checkouts. Rebuilding mods requires the matching upstream sources, Forge dependencies, compiler and prepared classes. Individual Java snapshots are not a standalone Gradle project.

The build and runtime-check tools accept explicit game, compiler and server-base paths. Their local defaults can also be set through `RV_GAME_ROOT`, `RV_ECJ_JAR`, `RV_SERVER_BASE` and `RV_COMBAT_AUDIO`. Build dependencies and temporary artifacts stay in the ignored `.local` cache; no developer-specific paths are required.

The client archive can be assembled from the published binary base and this repository. Byte-for-byte reproducibility of recompiled third-party mods is not claimed.
