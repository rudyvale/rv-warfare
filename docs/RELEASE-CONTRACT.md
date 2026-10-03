# RV release contract

RV uses one Windows player package and a separate host package. The player package includes its Java runtime. Players receive managed mods through the installer; they do not copy JAR files or configure Java.

## Public assets

| Asset | Contents |
| --- | --- |
| `RV-Setup.zip` | `RV-Setup/` launcher, installer, verified payload and runtime |
| `RV-Host-Tools.zip` | Host tools and verified first-party modules under `host-owned/mods/` |
| `RV-World-Template.zip` | Clean world template without player records |
| `RV-Third-Party-Sources.zip` | Original sources and notices required by the bundled components |
| `SHA256SUMS.txt` | SHA-256 checksums of the four archives |

The asset names and `RV-Setup/` directory remain compatible with older RV updaters. `release.json` must fit within 4096 bytes. Published versions are immutable: a correction receives a new version.

A new shared mod requires matching client and server versions. Keep the current stable package available while the new host is being validated. A review draft or prerelease must not replace the stable update target; GitHub excludes drafts and prereleases from its latest release selection. See [GitHub release parameters](https://docs.github.com/en/rest/releases/releases#create-a-release).

Public packages contain empty connection defaults. Host invitations and personal connection profiles are generated and stored locally. Account records, private peers, tokens, logs and used worlds are excluded from public assets.

## First-party modules

`pack/rv-managed-mods.json` binds every owned module to its filename, size, SHA-256, actual FML identity, source and build-recipe digests. The shared protocol is the union of those identities and the pinned common mods. The application version and individual mod versions may differ.

Each frozen registry requires native client and server projections. A projection contains only `success`, `mods` and `artifacts`; artifact digests come from the JAR sources actually loaded by Forge. Compilation, source checks and synthetic fixtures do not establish native acceptance.

`tools/freeze_managed_mods.py` validates build descriptors, source digests, Java 8 bytecode and both native projections before writing a new registry. `tools/stage_managed_payload.py` adds the proven modules to a new payload, preserves the baseline runtime and other managed files, and retires only previous owned paths and bounded RV module filenames. Both tools leave the original base intact.

RV 2 packages require the shared `rvexperience` module and the client controls and connection profiles helpers. The canonical helper list is `client_source_names()` in `tools/release_contract.py`; the builder and verifier use the same list.

## Vendor downloads

The eight pinned vendor archives are acquired from their approved official origins. Their identities, sizes and SHA-256 values are checked before installation. These archives and their embedded content are excluded from public release assets. See [compatibility and distribution rights](COMPATIBILITY.md).

## Release evidence

Release checks cover source agreement, complete module delivery, recursive archive inspection, privacy, checksums and the public GitHub state. Gameplay, inventory preservation, player authority, visible menus and performance require separate tests on the actual candidate. Gallery images must show the tested game build, with shader settings and test scope stated accurately.
