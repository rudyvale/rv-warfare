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

## Release contract

The repository is `rudyvale/rv-warfare`; the client asset is **RV-Setup.zip**, containing the **RV-Setup/** root directory. Releases use stable `vMAJOR.MINOR.PATCH` tags matching `src/release.json`.

1. Update `src/release.json` and `CHANGELOG.md`.
2. Prepare and verify the binary base, source changes and manifests.
3. Run the checks and build with `tools/build_release.py`.
4. Push the corresponding source commit and tag.
5. Stage **RV-Setup.zip**, **RV-Host-Tools.zip**, **SHA256SUMS.txt** and, when included, **RV-World-Template.zip** in a draft release.
6. Verify the uploaded asset sizes and SHA-256 digests before publishing as latest.

Do not replace an already published version with different bytes. Corrections need a new version. The checker uses the [official GitHub Releases API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release).

For a new local binary base, build the archives, push the matching tag, then run:

```powershell
python tools/publish_release.py --directory dist --notes release-notes.md --publish
```

Without `--publish`, the tool leaves a verified draft. It requires committed sources matching the pushed release tag. Keep temporary release notes under `.local`. It uses `GH_TOKEN`, `GITHUB_TOKEN` or the Git Credential Manager login, without writing tokens to files. Retrying resumes only when existing assets have matching checksums. `tools/verify_release.py --directory dist --tag vX.Y.Z --remote` verifies the public release and latest pointer.

The **Publish release** workflow rebuilds launcher and source updates from an existing verified release using `tag` and `base_tag`. Gameplay changes need a newly integrated and tested binary base, followed by the local publishing command above. The workflow does not compile third-party mods from upstream sources. The optional world is generated separately from its source generator.

For isolated tests, set `VM_SKIP_UPDATE_CHECK=1` in the test process. The legacy environment variable and internal `Get-Vm*` helper names remain for compatibility; ordinary shortcuts do not disable checks.
