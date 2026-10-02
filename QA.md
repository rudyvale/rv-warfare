# Verification scope

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
| Host panel | Separate actions, graceful stop, process ownership and concurrent start/stop handling |
| Protocol | Local Minecraft status requests, partial replies, unrelated TCP services and closed connections |
| Packaging | ZIP CRC, file allowlists, manifest hashes, public defaults and uploaded release digests |

Launch-flow tests substitute external processes. A passing test is not evidence of a connection between two physical computers. A local IPv6 test was skipped on the development machine because Windows rejected loopback traffic with Winsock error 10013; live IPv6 connectivity remains unverified.

Controller math and software runtime checks do not establish compatibility with every physical radio or USB controller. Flight feel, network conditions, server capacity and FPS depend on the hardware, world and player count.

Installation timings from a developer machine are not treated as performance guarantees. Actual release archives are checked separately before publication; GitHub Actions source checks do not launch a complete interactive game session.
