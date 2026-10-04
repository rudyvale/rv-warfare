# RV 2 Preview release closure

## Objective and acceptance

Produce a public Preview with matching source, client and host packages, clean world template, verified checksums, genuine game captures and empty connection defaults. Preserve the stable release and existing player data. Full gameplay acceptance remains a separate gate.

## Owners and paths

- Coordinator: scope, integration decisions and this handoff.
- Client maintainer: launcher lifecycle, onboarding and audio builder.
- Gameplay maintainer: controls patches and their bytecode regression checks.
- Host maintainer: server and inventory runtime evidence.
- QA reviewer: independent checks of the selected binaries and final archives.
- Release integrator: versions, manifests, source freeze, packaging and GitHub publication.

## Decisions and dependencies

The unreleased 2.0.1 candidate was rejected after an actual 105-mm impact exposed incompatible VMProps hook descriptors. Preserve its existing tag as a source checkpoint; publish the correction as 2.0.2. Keep the stable update target unchanged. The experimental MTS damage bridge and all test helpers are excluded from public packages.

## Changes and artifact identifiers

The corrected controls JAR has SHA-256 `d6b305e11c0ecc0cdf599039e888af96bd9911ca90e82979c671f5a641b16f60`. Relative to the rejected candidate, only `VMPropsTransformer.class` changes; the other 4,599 members remain byte-identical. The three hooks now call the actual Object-based VMProps method descriptors.

The selected player menu module has SHA-256 `a665f1fae8e738a91dc87423288aaa7b443b3160a424fd0b09632d22ba586007`. The final audio archive has SHA-256 `2b5ac7eb54493bacfa339c21fc121e9c579adf240a5ef8e88ed96fce2437e6ae`.

## Validation evidence

The new controls JAR passed Java 8 compilation and explicit bytecode checks against the selected Techguns JAR, including three comparisons between emitted hook descriptors and actual helper methods. This is a linkage regression check; Minecraft combat was not rerun after the correction.

Two ordinary players exercised equipment preview, preservation, confirmation, readiness, cancellation, disconnect and restart persistence on the selected menu module. Native full-inventory checks covered all 41 slots, cursor and selected slot: zero or one free main slot returned inventory_full without changing items or dropping them.

Eight native WinForms message-loop cases covered launcher action completion and cancellation using isolated workers. The full audio registry resolved 2,257 file references and 33 event links; 1,673 clips decoded. These checks do not establish audible playback. Gallery captures show the tested menu at 960 by 600 with shaders disabled.

## Open gaps and next gate

Before publication, independently verify the exact five final assets, frozen source closure, nested checksums, vendor exclusions and public GitHub state. The 30-minute deadline at 11:07:39 UTC on 2026-10-04 was missed; the rejected package was not uploaded.

Full combat and projectile stopping, the boosted FPV flight behavior in Minecraft, physical controllers, an external friend's connection and the final performance matrix remain unverified. Fault-injection rollback and the third-player inventory case also remain open. The release must remain a Preview and must not claim those checks passed.
