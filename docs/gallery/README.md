# RV game captures

## RV 2.0.3 Preview menu captures

These original 960 × 600 captures show the actual menu in an isolated Minecraft 1.12.2 Forge session with two ordinary players and quorum 2. The loaded experience module is `a665f1fae8e738a91dc87423288aaa7b443b3160a424fd0b09632d22ba586007`, component version 2.0.0. Both client and server loaded-artifact projections are in `qa/evidence/rv2-owned-client.json` and `qa/evidence/rv2-owned-server.json`. The captures are copied byte for byte from the native pair run; no crop, retouch or compositing was applied.

| File | Original capture | SHA-256 |
| :--- | :--- | :--- |
| `rv201-gear.png` | `recovery-red-before-confirm.png` | `a71166d8e79c3bfb0f6da80cfad694b417efbcc9245830ac71495a5bccf4e36d` |
| `rv201-session.png` | `14-active-red.png` | `25fe4334c800451ebcb706f3b8c503cbd2ab1aaf23f1fbb347214cf698159cb9` |

Confirmed gameplay scope includes the two-player menu flow and separately recorded capacity-denial checks for zero and one free inventory slots. Forced rollback, the complete inventory matrix, physical controllers, cross-mod combat and performance acceptance remain pending. The controls and combat binaries require their separate native evidence; these menu captures identify the experience component.

## RV 2.0.0 Preview captures

These original 960 × 600 PNG files were captured in an isolated Minecraft 1.12.2 Forge client at GUI scale 2, without shaders. They show the actual player menu, equipment choices, flight-feel settings and readiness cancellation. No image was composited, cropped or retouched.

The loaded RV experience module is `7f4368fa7906bcd71d1fe65f04a5e18ceef3e30394f6289e55c7837875666969`, version 2.0.0. Matching client and server loaded-module projections are preserved in the [RV 2.0.0 tagged evidence](https://github.com/rudyvale/rv-warfare/tree/v2.0.0/qa/evidence). The actor and world were isolated test fixtures.

Native checks confirmed one player's equipment confirmation, existing-item preservation, readiness cancellation, RU/EN guide delivery and travel destinations. These images do not establish two-player voting, physical controller support, full-inventory rollback, vendor combat or an FPS guarantee. The controls screen explicitly has no USB signal.

| Published file | Original capture | SHA-256 |
| :--- | :--- | :--- |
| `rv2-gear.png` | `05-english-gear.png` | `d3d76b06c8550b661b2d84668dcd6953b3e0a0b44fcf12166ba22e45f9056ef0` |
| `rv2-controls.png` | `08-native-feel-settings.png` | `d4ac34d19a04895a0b5d02d5cb9c460762c94db47dcfe103b8a89fc686ff5c43` |
| `rv2-session.png` | `14-readiness-cancelled.png` | `111ecff259e2af8b43b42a81fc853d1146c806bd48179b30c496e8a2bf272994` |

`rv2-menu-preview.png` is a historical preliminary capture from module `65ae42b5f627a37d4d1d401a1e99f7fa80c97a79ebe4d538243baadabf832e31`; it is not final RV 2 evidence.
