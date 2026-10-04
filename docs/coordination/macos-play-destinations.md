# macOS package and play destinations

## Objective

Add a macOS client package and explicit launcher choices: Local, Friends, Owner and Host my server. Keep the current gameplay binaries, map, graphics, sound and equipment unchanged. No destination is mandatory or embedded in a public package.

## Ownership

- Coordinator: this handoff, macOS package inputs, package builder, serial integration and release decisions.
- Client maintainer: Windows destination selection and launch dispatch in `src/`, excluding the separately assigned self-host helper; focused destination checks.
- Gameplay maintainer: a Java 8 macOS launcher in `platform/macos/`, including its focused component checks, in an isolated worktree. No gameplay or rendering changes.
- Host maintainer: `src/Warfare-SelfHost.ps1` and its focused checks in an isolated worktree. No existing host source or private owner policies.
- QA reviewer: read-only review after source and artifacts freeze.
- Release maintainer: Windows packaging after implementation and review, preserving existing published releases.

## Contract

Local launches Minecraft without a server argument or Steam/Porthole requirement. Friends and Owner have independently saved destinations; neither is a fallback for the other. Existing saved connections migrate without deletion. Host my server starts an independently owned Forge server, allows a local player to join, provides a shareable destination and has an explicit graceful stop action. It preserves its own world across runs and never modifies an existing owner's server or player data.

The macOS package uses the same frozen mod content as 2.0.3 and platform-specific Java 8 and native libraries. Intel and Apple Silicon compatibility must be stated accurately; do not claim native macOS runtime acceptance from Windows checks. Keep public connection defaults empty, preserve settings and worlds, pin downloads to approved origins and digests, and reject unsafe archive paths.

## Acceptance

Verify each mode's actual command and isolated process behavior, missing destinations, cancellation, persistence, duplicate start, graceful stop, occupied ports and package contents. Run focused installer corruption/preservation checks and compile Java 8 sources. A real Mac runtime and external friend connection remain explicit gates if the available environment cannot run them. Do not change the published 2.0.3 assets.

## Current state

Implementation starts from the published 2.0.3 Preview source plus its documentation closure. Isolated worktrees keep Windows dispatch, self-hosting, the macOS launcher and GitHub presentation separate. Integration is serial. The presentation files have been integrated; implementation source is awaiting final checks. The new application version is 2.0.4; gameplay modules, sound and the clean world remain frozen to 2.0.3.

The Mac verifier now requires the complete pinned installer manifest, a 146-file runtime inventory, exact launcher/source digests, managed preservation policies, source-bound entry scripts and metadata, and the clean-world hash and privacy checks. GitHub CI includes an Intel macOS job for Java compilation, focused headless checks and the actual bundled Java version; this does not establish native game or GUI acceptance. Windows packages deliver both mode helpers and the pinned self-host descriptor and clean template. First hosting requires the product EULA confirmation. No personal owner address is shipped.

Publication is explicitly authorized by the user when the candidate is ready. Publish 2.0.4 as a Preview with make_latest=false. Keep 2.0.3 immutable and 1.2.1 as the stable update target. A separate docs-only default-branch change can present the Preview without merging the broader gameplay draft. Do not publish from the coordinator checkout while unrelated files remain dirty or untracked; use a clean checkout of the frozen source.

Current validation: Mac package component tests 4 pass; release contract tests 16 pass; release candidate tests 12 pass, including missing or modified Mac asset rejection. Source compilation and source/CRC/privacy checks do not establish native gameplay acceptance. Final source, package, isolated host lifecycle, cold install, CI and actual public download gates remain pending.

## Mac integration evidence

The coordinator integrated the Mac source and tests serially, then preserved existing config/* and ModularWarfare/mod_config.json on every Play and restored the host stop action after cancelled or failed graceful stops. Native Windows Forge testing exposed literal console formatting; Mac readiness now uses its own current logs/latest.log and the selected listening port, rejecting a previous run readiness marker. QA independently reviewed these changes with no remaining P1 in that scope.

Candidate Mac archive SHA-256: cbb16a8c90442ea887e08667c8489c0a348074b92f6c3dcc8e646bc1d28d0da3. Launcher SHA-256: 4135c219580daad8d0456ed07698cf4eab3b0005f8ee829d43682bfa321cde32. Java 8 compilation and headless checks pass, including a constructor and server-content selection against the actual packaged Resources. Full runtime verification checks all 146 files against the original pinned tar archive, 1349 download records and three Mac native classifiers. Package and source pins agree. Six corruption/privacy mutation cases were rejected. These checks establish package and component evidence only; native Mac Java CI, GUI, game and external connection gates remain separate.

Windows app-only VM text retains an explicit human request reported verbatim by the launcher maintainer; GitHub, repository and release branding remain RV. No gameplay source or binary changes are part of this task.

Native Windows presentation: the launcher rendered its Local mode through the existing PreviewPath entry point under PowerShell 5.1, without the GUI harness, game, Steam or update checks. The original 1462 x 1075 bitmap is assets/launcher.png. It confirms layout rendering only; commands and host lifecycle have separate acceptance.

## Windows source freeze

The self-host helper is frozen at SHA-256 3df30a56876a1119263b5ebf0835ab09b9b53b61c15733d2057ac462e2abfe0b. A file-specific Git attribute preserves those exact script bytes across checkouts for candidate and native-fixture agreement. It binds its own server to available interfaces for LAN sharing and reads only the current bounded Forge log for readiness. Focused self-host checks pass. The real Forge fixture and cold final Windows candidate remain the next gate.

The first cold installer exposed a stale helper call after all 1347 downloads: Install-FreshWarfareWorld was undefined. Serial integration changed that call to the actually defined Install-WarfareWorldTemplate. The isolated debug retry installed successfully; final candidate cold installation must repeat without substituting source.

Foreign controller-combat edits made concurrently in the coordinator checkout are preserved but excluded. Publication uses a clean checkout containing frozen gameplay sources and only this task changes.

## Final package evidence

Final Setup SHA-256 3064d7e2c4014ce03ac39c91da2421b411357b2b034121689502736bb581a47d and Host Tools SHA-256 e32f17675481ca2f3e802616fa04b53d6697535c69e6336a54c270677217a92c passed full verification from a clean checkout. The exact Setup archive passed cold install (77.41 s), reinstall (10.81 s), all 1347 downloaded SHA-1 pins, helper/data bytes, saved Friends/Owner separation, existing world and update opt-out preservation, and installed Play Check. No game, Steam, shortcuts or real installed worlds were involved.

The native helper fixture used the exact frozen 3df30a source, reached Forge readiness with ten required mod versions, preserved its PID on duplicate start, saved world chunks and stopped with exit code zero. Independent postmortem found world/level.dat, the installed pinned-world marker, 158 files, no owned processes and a free port. The whole one-off runner did not pass: its map assertion contradicted these saved operands. Keep this distinction in QA and Preview notes rather than claiming complete native acceptance.

The first Intel Mac CI run failed its rebuilt JAR container digest. Build evidence now records every JAR entry digest, and the cross-platform source check requires those complete contents, source digests, Java target and pinned Gson; only ZIP compression differences may vary. Public package verification still requires the exact full JAR digest and entry set. Mac source, launcher and archive bytes did not change. The next gate is the corrected Intel Mac CI and public release download verification.
