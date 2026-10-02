# RV player guide

Extract the archive and open **INSTALL.cmd**. Enter a nickname, click **Install**, then **Play**. The installer sets up Minecraft, Java and the mods. Installation requires internet access. Steam is needed only for Porthole.

Open **Settings** and enter the host's Porthole code or direct address. Add the host as a Steam friend for Porthole. If Porthole is missing, the launcher opens its Steam installation.

If the host sends different connection details, open **Settings**:

- **Porthole** — the current connection code and server port. Sign in to Steam; the launcher opens the Porthole installation if needed.
- **Direct address** — the server IP or hostname and port.

Change the code, address and port here without reinstalling. Update the details if the host changes Steam accounts, too. Save and click **Play**. The server must be running.

RV checks GitHub quietly on startup and installation. Disable automatic checks in **Settings** if desired. Click **Update** to install a new version; the download is verified with SHA-256. You can also extract a new archive and open **INSTALL.cmd**. Your worlds, settings and connection details are kept. Replaced files are saved in `backups`.

## In game

T: chat; `/trigger menu set 1`: menu. Left click: fire, right click: aim, R: reload. J: map, E: inventory.

UAV: place it, hold the tablet or controller, then right-click the UAV. W/S adjusts throttle, A/D turns, the mouse tilts, Shift exits. Throttle resets when you connect. Shift + right-click with the tablet resets an unoccupied UAV on the ground after a flip.

Keyboard throttle stays where you leave it. Stabilized mode levels the UAV when you release the controls; Acro keeps the tilt until you correct it. About 50% throttle holds altitude when level. Press F8 to choose the flight mode or calibrate a USB controller. Lower the throttle before connecting. Loss of controller input or window focus cuts controller throttle.

For higher FPS, lower render distance or disable shaders in Video Settings.

## Credits

MC Heli CE — [Warfactory / EMB4](https://github.com/Warfactory-Official/McHeliCE).
Techguns — [pWn3d_1337](https://www.curseforge.com/minecraft/mc-mods/techguns).
[Forge](https://files.minecraftforge.net/), WorldEdit — EngineHub, WorldEdit CUI — Forge Edition 3.
JourneyMap — TeamJM; JEI — mezz.
BSL — CaptTatsu; [OptiFine — sp614x](https://optifine.net/).
Java — Eclipse Temurin. License and third-party notices are included.
