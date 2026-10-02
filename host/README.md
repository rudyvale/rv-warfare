# RV host panel

`warfare-launcher.py` opens one maximized window without tabs, in English or Russian. F11 toggles fullscreen; Esc restores the normal window.

- **PLAY** starts only the client, once the server is ready.
- **START SERVER** starts Forge and then Porthole for friends. It does not launch the client. If Porthole fails, local play remains available; a separate connection action retries Porthole.
- **STOP SERVER** requests a save and graceful stop, waits for Java, then stops Porthole. A slow save is not force-killed.

Closing the panel leaves the server running. The connection code becomes available to copy after Porthole is ready. Process launches, network checks and state reads run outside the interface thread.

Settings include language, controller configuration, automatic update checks and a server heap limit of 2–8 GB, additionally capped at half the physical memory. Defaults are 2 GB below 12 GB of RAM, 3 GB below 20 GB, otherwise 4 GB. Initial Java heap is 512 MB. Heap is only part of the process's memory use; actual consumption depends on mods and the world.

## Install

**RV-Host-Tools.zip** contains the panel, scripts, icon and update checker. Extract it into an existing configured server directory while the panel is closed. It contains no world, server mods, account profiles or private settings.

Requirements: Python with Tkinter, accessible `python.exe` and `pythonw.exe`, a configured Forge 1.12.2 server, Steam and Porthole. `run-server.py` looks for Java under `%LOCALAPPDATA%/Warfare-1.12.2/runtime`; override it with `VM_JAVA` if needed. The server JAR must be named `forge-1.12.2-14.23.5.2860.jar`.

The local `launch-warfare.py` integration expects the existing Warfare-1.12.2 profile under `%APPDATA%/.minecraft` and a selected TLauncher account. Account information stays on the computer. Use **RV-Setup.zip** for a separate client installation.

```powershell
python warfare-launcher.py --check
pythonw warfare-launcher.py
```

## Updates and worlds

Opening the panel or starting the game/server checks for updates in the background when enabled. `.updates/preferences.json` stores `autoCheck`; it defaults to true. A newer version exposes an **Update available** link to the release. Background checks never replace server files or worlds.

The optional **RV-World-Template.zip** is intended for a new world only. Follow its included instructions, back up any existing server and keep its world separate. Installing the template is a deliberate host action.

Run `python -X utf8 qa/test_host.py` and `python -X utf8 qa/test_host_races.py` from the repository root for isolated panel and process-ownership checks.
