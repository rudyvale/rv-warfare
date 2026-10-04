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

The unreleased 2.0.1 candidate was rejected after an actual 105-mm impact exposed incompatible VMProps hook descriptors. The 2.0.2 correction passed linkage and packaging checks, but its native retry exposed a separate dedicated-server fire error. Preserve both existing tags as unreleased source checkpoints. The next corrected candidate is 2.0.3. Keep the stable update target unchanged. The experimental MTS damage bridge and all test helpers are excluded from public packages.

## Changes and artifact identifiers

The rejected 2.0.2 controls JAR has SHA-256 `d6b305e11c0ecc0cdf599039e888af96bd9911ca90e82979c671f5a641b16f60`. Relative to the earlier rejected candidate, only `VMPropsTransformer.class` changes; the other 4,599 members remain byte-identical. The three hooks call the actual Object-based VMProps method descriptors.

The native-tested controls candidate has SHA-256 `3b35d78725238c9d0c5107ce185a2cec2e06ba030e376a66485a93906f665efb`. It replaces the two Forge event calls with cached, typed MethodHandles. Actual pinned Forge bytecode and its SRG mappings confirm the exact signatures: Entity to EntityPlaceEvent for placement and EntityPlayerMP for the break event. Only `VMProps.class` differs from the previous d6 candidate; the other 4,599 archive members remain byte-identical. The source capture for this binary records `VMProps.java` SHA-256 `ce3278a370ea049e72336cb1c4400d9e1605ff18a3989970e731784781b81674`.

The selected player menu module has SHA-256 `a665f1fae8e738a91dc87423288aaa7b443b3160a424fd0b09632d22ba586007`. The final audio archive has SHA-256 `2b5ac7eb54493bacfa339c21fc121e9c579adf240a5ef8e88ed96fce2437e6ae`.

## Validation evidence

The native-tested controls JAR passed Java 8 compilation, explicit bytecode checks against the selected Techguns JAR, and Forge API guardrails. Its isolated Forge server and client integrations completed; the 75-check combat suite passed with zero failures. The 105-mm round stopped at a tank and changed HP from 330 to 260; APFSDS changed it from 330 to 247. Actual glass breaking, wooden prop destruction, fire placement, bedrock protection, item hits and FPV contacts all passed. Exact Forge method lookup removed the dedicated-server `ITooltipFlag` error. The earlier d6 failure remains recorded as a regression that the new candidate fixes.

The private prop fixture advances the test world's `WorldInfo` total-time value between quota-sensitive groups. This exercises the four-block budget rollover without changing the production cap; it is not evidence of elapsed server ticks or performance. Client checks confirmed positional sound, muzzle, recoil and tracer hooks were invoked, but did not measure audible playback or save an impact screenshot.

Two ordinary players exercised equipment preview, preservation, confirmation, readiness, cancellation, disconnect and restart persistence on the selected menu module. Native full-inventory checks covered all 41 slots, cursor and selected slot: zero or one free main slot returned inventory_full without changing items or dropping them.

Eight native WinForms message-loop cases covered launcher action completion and cancellation using isolated workers. The full audio registry resolved 2,257 file references and 33 event links; 1,673 clips decoded. These checks do not establish audible playback. Gallery captures show the tested menu at 960 by 600 with shaders disabled.

## Open gaps and next gate

Before publication, integrate the exact native-tested candidate into the next release, independently verify the exact five final assets, frozen source closure, nested checksums, vendor exclusions and public GitHub state. The 30-minute deadline at 11:07:39 UTC on 2026-10-04 was missed; neither rejected package was uploaded.

The 75-check isolated combat suite covers its listed fixtures, not every weapon or vehicle. Physical controller models, audible playback, visible impact output, an external friend's connection and the final performance matrix remain unverified. Fault-injection rollback and the third-player inventory case also remain open. The release must remain a Preview and must not claim those checks passed.
