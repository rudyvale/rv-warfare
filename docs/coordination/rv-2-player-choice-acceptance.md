# Player equipment and session acceptance

## Objective and acceptance

Players choose their equipment and session readiness without administrator commands. Failed equipment grants must preserve inventory contents, tags, cursor, selected slot, equipment choices, confirmation flags and cooldown, and must create no dropped items. Tagged medical supplies must stack only with matching tags. Session voting must also work with a third ordinary player.

## Owners and paths

- Coordinator: this handoff, acceptance decisions and serial integration.
- Host and network maintainer: isolated native inventory fixture and its private evidence only. No production files, installed game or live server changes.
- Client maintainer: isolated cold installation of the exact published 2.0.3 package, without a game launch or user-profile changes; read-only invitation journey audit.
- Gameplay maintainer: `patches/experience/client/ExperienceScreen.java` in an isolated worktree for the confirmed wide-button rendering defect. Equipment/server files remain unassigned for production edits until a defect is reproduced.
- QA reviewer: independent read-only review of frozen native receipts and the exact loaded module.
- Release integrator: published Preview closure only; no new package until the next implementation is frozen and reviewed.

## Decisions and dependencies

RV 2.0.3 Preview remains immutable. The equipment module under test is `a665f1fae8e738a91dc87423288aaa7b443b3160a424fd0b09632d22ba586007`. Tests use isolated application-data directories, a private desktop and owned Java processes. One native supervisor owns runtime mutations. Revalidate process identity, test ports and available memory before starting; keep the fixture bounded to one server and two clients initially. Extend to a third ordinary actor only after the transaction checks close.

## Changes and artifact identifiers

Do not substitute a patched production module to obtain a passing transaction result. A test request rejected by the client before transmission does not exercise server rollback.

The published gear capture shows a dark central seam in wide weapon buttons. The next UI candidate should paint those controls with the existing panel colors while preserving native hit testing, sounds, action identity and server behavior. Keep this rendering change separate from the unchanged equipment module used for transaction acceptance.

## Validation evidence

The existing two-player native run covers equipment preview, preservation, confirmation without newly occupied slots, duplicate avoidance, readiness, cancellation, disconnect and restart persistence. Zero-free-slot and one-free-slot capacity denials preserve all 41 inventory slots and create no dropped items.

An independent component check executed the exact released SessionEngine classes: 19 boundary assertions and 88 setup assertions passed. It covers three-player 2:1-team quorum, a non-voting participant, disconnect and choice-change cancellation, a five-player quorum boundary and equipment-error state preservation. Its Inventory implementation is a test double; this does not establish native third-client or actual inventory rollback acceptance.

The published Setup ZIP `7513fd652268df7a6e8db5f2b6aee1160c2375564025eee42f2cd56ad0bc38c2` completed a cold installation without Java on PATH. Its bundled OpenJDK 1.8.0_504 ran, all 1,347 downloaded manifest files matched SHA-1, and the installed Play Check passed. Reinstallation preserved settings, unfinished first-play state, an empty connection destination, a custom port, update preference and a test world. The receipt digest is `37b5fcf9efaa051c07202ec3a25e70566c2462d026360051b0cb00f19a0fbc0a`. No game, Steam or Porthole was launched by this installation test.

The first post-write rollback attempt was inconclusive because the private probe reported `private_request_busy` before transmission. A corrected private probe subsequently sent the confirmation request to the actual Forge server. Tagged-bandage stacking passed: compatible supplies merged, unmatched tags and counts remained intact, and no duplicate or dropped items appeared. The injected post-write container failure returned `inventory_error` and restored inventory, cursor, selected slot, choice state, confirmation flags and cooldown. The native summary digest is `c87370ed85c4e8826ad758971b2b08d65215daff97e53db67a62248933ca2777`. The fixture restored its saved inventories; its server, client and supervisor exited, and its test port was no longer listening.

The separate wide-button candidate compiled for Java 8. Its source digest is `0619d633aa37cee833fbc3ebc53e71bf8be678c2f53572f02a091ec81889a16d` and JAR digest is `c20b11d7c1642210ed6e295661681e42b6596eac962737db18a39324bece4f38`. Independent review confirmed that only `ExperienceScreen.class` changes; all 17 server and 8 protocol classes remain byte-identical. Hit testing, click sound and actions are unchanged. Native captures have not been taken, so this candidate remains isolated and is not included in published 2.0.3.

## Open gaps and next gate

The post-write failure fixture throws before forwarding container packets. It proves server rollback and unchanged client inventory for that boundary; it does not prove recovery after partial packet delivery. Preserve this distinction in later tests and review both server rollback and client resynchronization before assigning a production transaction fix.

At the user's request to finish, no further runtime or release build is started in this cycle. The next UI gate is real client captures at 960 by 600 and 1920 by 1080, in both languages and with enabled, disabled, hover and keyboard-focus states. The third-player readiness and voting matrix and hardware, external connection and performance acceptance remain separate gates. Published Preview files remain immutable.
