# RV Warfare for macOS

Extract `RV-Mac-Setup.zip`, keep `RV.app` and `Open RV.command` together, and open RV. The package includes Java 8. Installation downloads Minecraft libraries and the pinned optional mods from their official sources.

The Preview application is not notarized. If macOS blocks the first opening because the developer cannot be verified, follow Apple's [per-application opening instructions](https://support.apple.com/102445) in System Settings → Privacy & Security → Open Anyway.

| Play mode | Destination |
| --- | --- |
| Local | Your single-player worlds; no server or Steam required |
| Friends | Your friend's address or Porthole invitation |
| Owner | An independently saved owner's address |
| Host my server | Your own server and persistent world |

Enter your nickname and choose a mode. Friends and Owner store separate destinations. No owner's address is included. Hosting asks for Minecraft EULA acceptance on first use; Stop server saves and closes your own server.

This Preview bundles an Intel x64 runtime and Minecraft 1.12.2 native libraries. Apple Silicon requires Apple's Rosetta 2. Porthole for macOS requires Apple Silicon and Steam; Intel users can use a direct address or LAN. Direct play and local worlds do not require Steam.

Game files and settings live in `~/Library/Application Support/RV-1.12.2`. Reinstalling the application keeps this folder. Existing worlds are preserved; the supplied clean map is copied only when absent.

Java compilation, package integrity and focused component checks are recorded separately from native macOS acceptance. The actual Mac game, GUI, controllers and external friend connection have not yet been accepted on a physical Mac. This is an experimental Preview, not a verified stable Mac release.

See the [RV releases](https://github.com/rudyvale/rv-warfare/releases) for updates and SHA-256 checksums.
