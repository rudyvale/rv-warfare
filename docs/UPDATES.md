# Updates

RV reads stable release metadata from `https://api.github.com/repos/rudyvale/rv-warfare/releases/latest`. The request contains no nickname, server address, Steam ID, settings or game files. No GitHub token is needed on a player's computer.

## Behaviour

- Opening the client launcher starts a hidden `Check-WarfareUpdate.ps1` process.
- Direct calls to `Play-Warfare.ps1` and `Install-Warfare.ps1` also start a check.
- The host panel checks when opening and when starting the server or game.
- The metadata request has an eight-second timeout; the interface does not wait for it.
- A per-installation file lock prevents overlapping checks.
- **Settings** can disable automatic checks. `.updates/preferences.json` stores `{"autoCheck":false}`; installation preserves this choice. Checks are enabled by default. Manual updates still work.
- Results are written atomically to `.updates/status.json`; failures are recorded in `.updates/last-error.json`.
- Background checks do not install anything. The client downloads and installs through **Update**. The host panel offers a release link.
- Versions are compared numerically: `1.10.0` is newer than `1.9.0`. Prereleases and older versions are not offered.
- Rechecking preserves an already downloaded package with the same version and checksum.

The downloader checks the asset size and SHA-256 against GitHub's release asset `digest`. It then validates ZIP paths, duplicate entries, extraction limits, required files and `release.json`. Failed verification leaves the current installation untouched. HTTPS and SHA-256 verify that the bytes match the published artifact; version 1.0.0 does not use a separate publisher signature.

Packages starting with 1.1.0 must include the performance and first-play helpers, source notices and the advertised MC Heli version in `release.json` before extraction. The launcher checks the required mod versions against the server's status response before starting Java. Version 1.0.0 packages remain compatible without these additions.

## Release contract

The repository is `rudyvale/rv-warfare`; the client asset is **RV-Setup.zip**, containing the **RV-Setup/** root directory. Releases use stable `vMAJOR.MINOR.PATCH` tags matching `src/release.json`.

1. Freeze and independently verify the gameplay binaries, source changes, world and manifests.
2. Update `src/release.json` and `CHANGELOG.md`; record the actual advertised mod versions for 1.1.0 and newer.
3. Run the checks and build with `tools/build_release.py` into a fresh candidate directory.
4. Push the corresponding source commit and tag.
5. Stage **RV-Setup.zip**, **RV-Host-Tools.zip**, **SHA256SUMS.txt**, the required **RV-Third-Party-Sources.zip** for 1.1.0 and newer, and, when included, **RV-World-Template.zip** in a draft release.
6. Verify the uploaded asset sizes and SHA-256 digests before publishing as latest.

Do not replace an already published version with different bytes. Corrections need a new version. The checker uses the [official GitHub Releases API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release).

For a new local binary base, build the archives, push the matching tag, then run:

```powershell
python tools/publish_release.py --directory .local/releases/candidate-public --notes .local/release-notes.md --publish
```

Without `--publish`, the tool leaves a verified draft. It requires committed sources matching the pushed release tag and, for new versions, a matching public `.release-candidate.json`. It rejects private candidates or changed archive bytes before authentication or API writes. Keep temporary release notes under `.local`. It uses `GH_TOKEN`, `GITHUB_TOKEN` or the Git Credential Manager login, without writing tokens to files. Retrying resumes only when existing assets have matching checksums. After public verification, it marks the local output as published and immutable. `tools/verify_release.py --directory .local/releases/candidate-public --tag vX.Y.Z --remote` verifies the public release and latest pointer.

The **Publish release** workflow rebuilds launcher and source updates from an existing verified release using `tag` and `base_tag`. It downloads and validates the baseline with `tools/download_release_base.py` and uses the same candidate and publication gates as the local publisher. Gameplay changes need a newly integrated and tested binary base, followed by the local publishing command above. The workflow does not compile third-party mods from upstream sources. It generates a clean world, integrates the tracked menus and player book, validates them and includes the world archive in the release.

For 1.1.0 and newer, the workflow also downloads the pinned original upstream source archives, validates their sizes, hashes and licenses, and builds the separate source release asset. The publisher verifies and uploads it with the same candidate and remote checksum gates as the binaries. Players' background checks still download only **RV-Setup.zip** when they choose Update.

For isolated tests, set `VM_SKIP_UPDATE_CHECK=1` in the test process. The legacy environment variable and internal `Get-Vm*` helper names remain for compatibility; ordinary shortcuts do not disable checks.
