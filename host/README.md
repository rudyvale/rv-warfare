# RV host panel

`warfare-launcher.py` opens one maximized window without tabs, in English or Russian. F11 toggles fullscreen; Esc restores the normal window.

- **PLAY** starts only the client, once the server is ready.
- **START SERVER** starts Forge and then Porthole for friends. It does not launch the client. If Porthole fails, local play remains available; a separate connection action retries Porthole.
- **STOP SERVER** requests a save and graceful stop, waits for Java, then stops Porthole. A slow save is not force-killed.

Closing the panel leaves the server running. The connection code becomes available to copy after Porthole is ready. Process launches, network checks and state reads run outside the interface thread.

**Invite friends** saves a small `.rvinvite` file after the server and Porthole are ready. Send it to a friend and import it in RV connection setup. The file contains the current connection destination, port and RV version; it contains no account credentials or world data. It is created only when you click the action and choose a destination. Public packages contain no invitation or private destination.

Settings include language, controller configuration, automatic update checks and a server heap limit of 2–8 GB, additionally capped at half the physical memory. Defaults are 2 GB below 12 GB of RAM, 3 GB below 20 GB, otherwise 4 GB. Initial Java heap is 512 MB. Heap is only part of the process's memory use; actual consumption depends on mods and the world.

The Low, Balanced and Quality server profiles select 2, 3 and 4 GB with view distances of 4, 6 and 8 chunks. Selecting and saving a profile applies it at the next server start, after the server has stopped. A properties backup is retained. Client Auto memory reserves space for Windows and recognized local servers; an explicit client allocation is checked before launch.

## Install

For a configured owner using the standalone RV client, a shortcut to `pythonw.exe play-owner.py --game-root "C:\path\to\Warfare-1.12.2"` starts the server, waits for the world, opens Steam and Porthole for friends, then launches the owner locally. The nickname and game directory must already match the private owner policy. Optional local `owner-play-settings.json` can set `peerTarget` to the Steam peer used in the friends' package, so another Steam account cannot silently replace that destination. Repeated clicks do not start duplicate clients. Closing the startup window cancels the pending client launch and leaves the server running.

`pythonw.exe owner-panel.py --game-root "C:\path\to\Warfare-1.12.2"` opens the compact owner panel with live server/friend status, Play, Copy code, reconnect, graceful stop and world reset. Startup failures offer Retry and Open log. World reset restores the baseline captured after map expansion; choose map only to preserve inventories and scores, or a fresh game to reset player progress. Each reset keeps the complete previous world under `backups/world-reset-*`, verifies the baseline checksums, waits for a graceful stop, restores the map and restarts the server and friend connection. Players must reconnect after a reset. Baselines stay local under `.world-reset`; public host tools do not include personal worlds. Capture a baseline only while the server is stopped with `world_reset.capture_baseline(server_directory)`.

`tools/build_world_extension.py --output <new-directory>` creates a separate 2560×2560 expansion with 142 additional buildings, six districts, an airfield, industrial yards, outposts and farmhouses. Its new chunk records exclude the original 1536×1536 core. Merge missing chunks into an offline world using `merge_world_regions.py`, retain a complete pre-update backup and set the world's border and boot function to 2560. Existing world chunks are preserved exactly.

**RV-Host-Tools.zip** contains the panel, scripts, icon and update checker. Extract it into an existing configured server directory while the panel is closed. It contains no world, server mods, account profiles or private settings.

Requirements: Python with Tkinter, accessible `python.exe` and `pythonw.exe`, a configured Forge 1.12.2 server, Steam and Porthole. `run-server.py` looks for Java under `%LOCALAPPDATA%/Warfare-1.12.2/runtime`; override it with `VM_JAVA` if needed. The server JAR must be named `forge-1.12.2-14.23.5.2860.jar`.

The local `launch-warfare.py` integration expects the existing Warfare-1.12.2 profile under `%APPDATA%/.minecraft` and a selected TLauncher account. Account information stays on the computer. Use **RV-Setup.zip** for a separate client installation.

Install the matching RV client files and first-play helpers into the existing owner game folder before using the updated host panel. The first **PLAY** opens control setup: choose easy keyboard and mouse, a USB radio or a gamepad. Owner setup uses the local server automatically. Cancelling setup returns to the panel without launching Minecraft or replacing a calibrated controller profile.

```powershell
python warfare-launcher.py --check
pythonw warfare-launcher.py
```

## Updates and worlds

With RV 1.2, **START SERVER** also installs missing server mods from the release's official download list before starting Java. Downloads and installation run in the background worker. **STOP SERVER** cancels this preparation; completed downloads remain cached. An existing matching installation is reused. Unknown mods and customized files are retained, and conflicting copies stop the update before installation.

The host tools must include the matching `release.json`, `vendor-catalog.json` and `Warfare-VendorDownloads.ps1`. `Install-ServerVendors.ps1` can run the same installation separately while the server is stopped. Verified changes retain a backup under `backups/vendor-update-*`. Retrying an interrupted installation restores its verified pre-update files first; a file changed by hand is retained and reported as a conflict. This operation preserves worlds, player progress, owner policy and Porthole settings.

Opening the panel or starting the game/server checks for updates in the background when enabled. `.updates/preferences.json` stores `autoCheck`; it defaults to true. A newer version exposes an **Update available** link to the release. Background checks never replace server files or worlds.

The optional **RV-World-Template.zip** is intended for a new world only. Follow its included instructions, back up any existing server and keep its world separate. Installing the template is a deliberate host action.

The matching server mods and host resource map are required. Before starting Java, the panel verifies the installed aircraft mod against that map and updates only the listed stock resources in an existing default addon folder, retaining backups and custom addon files. Local client launch also checks the server's mod versions. Existing players retain their inventories, beds, team spawnpoints and guide progress.

Run `python -X utf8 qa/test_host.py` and `python -X utf8 qa/test_host_races.py` from the repository root for isolated panel and process-ownership checks.
