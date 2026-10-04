# Verification scope

## RV 2 Preview verification

The selected player menu module `a665f1fae8e738a91dc87423288aaa7b443b3160a424fd0b09632d22ba586007` was loaded by an actual Forge client and dedicated server. Public projections contain only owned module identities and loaded artifact digests. All 21 build source digests match the frozen source, and the compilation-only GUI API is excluded from the production JAR.

Two ordinary players exercised the reviewed equipment and session flow, including confirmation, preservation, readiness, cancellation, disconnect and restart persistence. Native zero- and one-free-slot capacity denials preserved all 41 inventory slots, cursor, selection and equipment choices, with no dropped items. These checks do not complete the fault-injection rollback or third-player matrix. Original menu captures show 960 by 600 with shaders disabled.

The earlier RV 2.0.0 module `7f4368fa7906bcd71d1fe65f04a5e18ceef3e30394f6289e55c7837875666969` had separate single-player checks for equipment, guides and training. Its controls capture remains historical evidence; it does not prove the later menu or controls binaries.

Eight native WinForms message-loop cases exercised isolated launcher workers, action completion and cancellation. They do not establish a fresh installation or physical device compatibility. The configured two-contentpack sound registry resolved 2,257 file references and 33 event links; 1,673 clips decoded. The corrected silent cue reuses an existing valid silence sample, and all 106 RV sound files remain byte-identical. Audible playback remains unverified.

Packaging checks cover exact source and artifact closure, managed files, recursive vendor and invitation privacy inspection, ZIP paths and CRC, checksums, immutable outputs and preview publication policy. The third-party source registry is pinned as raw bytes so a fresh checkout agrees with the frozen source bundle. These checks do not establish Minecraft combat or multiplayer acceptance.

RV 2.0.1 and 2.0.2 candidates remain unpublished. Actual projectile impact exposed incompatible hook descriptors in the first candidate. The 2.0.2 correction then exposed a dedicated-server fire error when reflection resolved an unrelated client-only tooltip class.

The selected 2.0.3 controls JAR `3b35d78725238c9d0c5107ce185a2cec2e06ba030e376a66485a93906f665efb` calls the two Forge protection hooks through exact cached method handles. Its 39 captured controls inputs match the frozen source. All five VMProps classes and the transformer are byte-identical to those loaded by the isolated server and client test. That instrumented fixture completed 25 impact checks and 75 combat assertions with zero failures, including projectile stopping, tank HP changes, glass, wooden props and managed fire. No ITooltipFlag or helper-descriptor error was observed. Quota-sensitive groups explicitly advance the WorldInfo total-time counter; these checks do not establish elapsed server ticks, real-time fire expiry or performance. Test helpers are excluded from the public JAR. This is a scoped regression result, not full-modpack combat acceptance.

Physical controllers, an external friend's connection, cross-mod damage, full-inventory rollback, audible playback and the final TPS/FPS/RAM matrix remain open. The experimental MTS damage bridge and acceptance-test helpers are excluded from public packages. Historical results below apply to their named earlier releases.

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

The historical RV 1.1.0 gameplay candidate was checked on actual Forge server and client runtimes. Independent combat checks covered damage and entity state, including tank destruction and a single FPV detonation. The final audio pack was decoded and audited against the combined sound registry. Production JARs exclude the acceptance-test classes.

The 1.1.0 component checks also exercised Easy flight and lost-focus input, malformed network input, current tank bindings, First Aid wounds and healing, and actual Low/Balanced effect values. Both 24-page books were parsed by Minecraft and checked against the native font renderer. The new Apache burst event was resolved through the actual loaded sound registry; codec and byte comparisons covered the updated audio archive.

The 1.0.0 installer was also run with empty application-data directories and no Java on PATH. It verified 1,347 downloaded Minecraft files, ran the bundled Java 8 and passed the installed-file check. Separate upgrade tests preserved Unicode settings, personal mods, worlds and the server list, and backed up the retired managed JAR.

The `live_owner_runtime.py` and `live_host_gui.py` helpers run manual acceptance checks against explicit server/client directories. They are separate from CI and use the configured local server and owner policy.

Launch-flow tests substitute external processes. A passing test is not evidence of a connection between two physical computers. A local IPv6 test was skipped on the development machine because Windows rejected loopback traffic with Winsock error 10013; live IPv6 connectivity remains unverified.

Controller math and software runtime checks do not establish compatibility with every physical radio or USB controller. Flight feel, network conditions, server capacity and FPS depend on the hardware, world and player count.

Installation timings from a developer machine are not treated as performance guarantees. Actual release archives are checked separately before publication; GitHub Actions source checks do not launch a complete interactive game session.
