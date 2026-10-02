# Third-party sources and notices

RV Warfare 1.1.0 includes the following original, unmodified vendor JARs for Minecraft 1.12.2. These components retain their authors' licenses and notices.

| Component | Vendor file version | Original source commit |
| :--- | :--- | :--- |
| First Aid | 1.6.22 | [e9f977ad099d](https://github.com/ichttt/FirstAid/tree/e9f977ad099d54558a720a2ee967e75269e7b364) |
| Enhanced Visuals | 1.4.4 | [da84fc1406f7](https://github.com/CreativeMD/EnhancedVisuals/tree/da84fc1406f737f25ecd87d2bae4f0baf5647c2e) |
| CreativeCore | 1.10.71 | [fd410b278a3d](https://github.com/CreativeMD/CreativeCore/tree/fd410b278a3d3fd1237773708c52a4bebac440b6) |

Download [RV-Third-Party-Sources.zip for this release](https://github.com/rudyvale/rv-warfare/releases/download/v1.1.0/RV-Third-Party-Sources.zip). It contains the original source archives, license texts and a `components.json` record of exact binary and source checksums. The source ZIPs are preserved byte for byte. The archive is available alongside the binaries without a separate account or charge.

First Aid's main source has GPL-3.0-or-later notices; its API has separate LGPL-2.1 notices. Its original README also preserves the credit and Attribution 3.0 notice for the heartbeat sound. The original Minecraft 1.12 source trees of Enhanced Visuals and CreativeCore contain GNU GPL version 3 license texts. The complete original licenses, copyright and warranty notices are retained in the source archives and copied into the source bundle's `licenses` directory. RV does not replace those licenses with a project-wide license.

First Aid's source archive includes the author's Gradle build scripts and wrapper. Enhanced Visuals and CreativeCore's original 1.12 source archives contain Java code and assets but no Gradle build scripts. CreativeCore's README links the author's [development setup guide](https://www.youtube.com/watch?v=7Ahshi_QjM4). Use the matching Forge 1.12.2 development environment and upstream dependencies; RV does not claim byte-for-byte reproducibility of a vendor rebuild.

Vendor file versions differ from the embedded Forge mod versions of Enhanced Visuals and CreativeCore. RV's connection checks use the separately verified runtime mod versions.

Other bundled components retain their own notices. See the repository's [component credits](https://github.com/rudyvale/rv-warfare/blob/main/THIRD_PARTY.md), the runtime archive's Java notices and each upstream project. Minecraft belongs to Mojang Studios / Microsoft.
