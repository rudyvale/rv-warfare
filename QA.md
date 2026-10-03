# Verification scope

## RV 2 Preview verification

The final preview module `7f4368fa7906bcd71d1fe65f04a5e18ceef3e30394f6289e55c7837875666969` was loaded by both an actual Forge client and dedicated server. Their public projections contain only owned module identities and loaded JAR digests. All 21 build source digests match the committed bytes; the compilation-only GUI API is excluded from the production JAR.

Native checks with one ordinary isolated player confirmed equipment preview versus delivery, existing-item preservation, readiness then cancellation, RU and EN edition-4 guides with 30 pages each, and training/lobby travel. The accepted captures have readable native buttons at 960 × 600 and GUI scale 2. Controller screens were opened without a physical USB device.

Packaging checks include 91 targeted cases, recursive vendor and invitation privacy inspection, source agreement, ZIP paths/CRC, immutable outputs and preview publication policy. Nine world package regressions verify that server authority guards survive staging. Component and fixture results do not establish native multiplayer behavior. Two-player voting, full-inventory rollback, physical controllers, new vendor combat and a full performance matrix remain unverified for RV 2. Historical acceptance below applies to its named earlier releases.

RV is developed on Windows using Windows PowerShell 5.1. Automated checks live in `qa`; the [Windows checks workflow](https://github.com/rudyvale/rv-warfare/actions/workflows/ci.yml) shows the result for each pushed source revision.

| Area | Checks |
| :--- | :--- |
| Update metadata | Stable version comparison, malformed responses, wrong repository, missing hashes and duplicate assets |
| Downloads | Size and SHA-256 verification, safe extraction paths, archive limits and required package metadata |
| Update behaviour | Offline operation, concurrent checks, persistent opt-out and downloaded-package reuse |
| Installation | Fresh install, repeated install, preservation of user settings/worlds, backups and downgrade rejection |
| Connections | Porthole and direct address parsing, migration, user-setting priority and invalid inputs |
| Launch flow | Steam/Porthole preparation, retry paths, connection switching and direct mode without Steam |
| Interface | English/Russian text, background operations, connection settings, update state and adaptive layouts |
| First-play setup | Saved choices, cancellation rollback, calibration preservation, bounded device scans and owned-worker cleanup |
| Mod upgrades | Exact vendor archives, duplicate mod IDs, bounded default addon updates and preservation of unknown files |
| Host panel | Separate actions, graceful stop, process ownership and concurrent start/stop handling |
| Protocol | Local Minecraft status requests, partial replies, unrelated TCP services and closed connections |
| Packaging | ZIP CRC, file allowlists, manifest hashes, public defaults and uploaded release digests |
| World template | Region headers, complete chunks, spawn access, lighting, borders and byte-identical source rebuild |
| Player book and menus | Both languages, non-operator delivery, full inventories, equipment preservation, reconnect and restart |
| Combat runtime | Dedicated server and client loading, rotated tank hulls, turret hits, projectile stopping, wall obstruction, FPV impact and prop damage |
| Owner access | Actual owner connection receives permissions; ordinary clients and a matching nickname from an untrusted directory are denied |

The frozen gameplay candidate was checked on actual Forge server and client runtimes. Independent combat checks covered damage and entity state, including tank destruction and a single FPV detonation. The final audio pack was decoded and audited against the combined sound registry. Production JARs exclude the acceptance-test classes.

The 1.1.0 component checks also exercised Easy flight and lost-focus input, malformed network input, current tank bindings, First Aid wounds and healing, and actual Low/Balanced effect values. Both 24-page books were parsed by Minecraft and checked against the native font renderer. The new Apache burst event was resolved through the actual loaded sound registry; codec and byte comparisons covered the updated audio archive.

The 1.0.0 installer was also run with empty application-data directories and no Java on PATH. It verified 1,347 downloaded Minecraft files, ran the bundled Java 8 and passed the installed-file check. Separate upgrade tests preserved Unicode settings, personal mods, worlds and the server list, and backed up the retired managed JAR.

The `live_owner_runtime.py` and `live_host_gui.py` helpers run manual acceptance checks against explicit server/client directories. They are separate from CI and use the configured local server and owner policy.

Launch-flow tests substitute external processes. A passing test is not evidence of a connection between two physical computers. A local IPv6 test was skipped on the development machine because Windows rejected loopback traffic with Winsock error 10013; live IPv6 connectivity remains unverified.

Controller math and software runtime checks do not establish compatibility with every physical radio or USB controller. Flight feel, network conditions, server capacity and FPS depend on the hardware, world and player count.

Installation timings from a developer machine are not treated as performance guarantees. Actual release archives are checked separately before publication; GitHub Actions source checks do not launch a complete interactive game session.
