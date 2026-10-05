# RV player guide

Extract the entire **RV-Setup.zip**, open **INSTALL.cmd**, enter a nickname and click **Install**. RV sets up Java, Minecraft, Forge and the mods. Internet access is needed for installation.

Русская страница проекта: [README-RU.md](https://github.com/rudyvale/rv-warfare/blob/main/README-RU.md). Instructions for optional vehicle add-ons: [VEHICLES.md](https://github.com/rudyvale/rv-warfare/blob/main/docs/VEHICLES.md).

On the first **Play**, choose **Mouse and keyboard**, **FPV radio** or **Gamepad**. For a controller, select the actual connected device, check its axes and complete calibration. Then choose your server. RV saves your choice; setup remains available in the launcher.

## Connect and update

- **Porthole**: enter the host's current connection code or Steam details and server port. Sign in to Steam. RV opens Porthole's Steam installation if it is missing.
- **Direct address**: enter the server's IP or hostname and port. Steam is not needed.

The host's server must be running. Change connection details in **Settings** without reinstalling. The public installer has no personal server destination; a friend package can preselect the host's details.

RV checks GitHub in the background when opening, installing or launching. **Settings** can disable automatic checks. Use **Update** to install a newer stable version; RV verifies its size, SHA-256 and archive contents. Close the game before replacing files. Installation preserves worlds, saved settings and connection details and backs up replaced files.

If RV reports duplicate gameplay mods, use the relative paths shown in the error to resolve the duplicate copies before playing. The check preserves your files and stops before starting Java.

## Menu and equipment

**T** opens chat, **E** opens inventory and **J** opens the map. Use `/trigger menu set 1` for the RV menu. Restore the field guide through **Menu → Book** or `/trigger wbook set 1`.

On an RV server, **Kit** or `/trigger kit set 1` supplies weapons, ammunition, food, armour, a tablet and medical supplies. `/trigger drone set 1` replenishes up to three combat FPV drones; `/trigger wing set 1` supplies Geran and FP-1. Leave free inventory slots and wait five seconds between requests. Use **Spawn** or `/trigger spawn set 1` to return to the shared spawn.

## FPV quadcopter

Place the quadcopter on clear, level ground. Hold the tablet and right-click the drone to take control. **Easy** is the default for mouse and keyboard.

| Input | Action |
| :--- | :--- |
| Mouse | Look and turn |
| W / S | Move forward / backward |
| A / D | Move left / right |
| Space | Rise and take off |
| Left Ctrl | Descend |
| Shift | Leave FPV control |

Release the movement keys to brake and hover. Losing window focus cuts motor input and the drone descends; return to the game and press **Space** to resume flight. After takeoff, a combat FPV detonates on contact with a vehicle or blocks. Use the training area for your first flights.

To right a flipped drone, leave control and **Shift + right-click** it with the tablet. This works on an unoccupied drone on the ground.

## Geran and FP-1

Use a clear, level runway. Place the aircraft, hold the tablet and right-click it. **W** increases throttle, **S** reduces it, the **mouse** controls pitch and **A / D** banks left or right. **Y** exits. Fixed-wing aircraft need speed and cannot hover. Leaving control cuts throttle; the aircraft continues moving and descends.

## Radio and gamepad

Connect a USB radio in **Joystick** mode. **F8** opens device selection, axis mapping, calibration and flight options. Map roll, pitch, yaw and throttle; calibrate centre and full travel, check inversion and save. **Angle** levels the quad when you release the sticks. **Acro** keeps the tilt until you correct it.

Before connecting, lower a radio's throttle fully or centre a gamepad's throttle stick. Losing USB input or window focus cuts throttle. If the device is missing, check Joystick mode and F8; mouse and keyboard remain available. Calibration and sensitivity are saved locally for each player.

## Weapons and tanks

On foot, **left-click** fires, **right-click** aims and **R** reloads.

For a tank, **right-click** enters, **W / A / S / D** drives, the **mouse** aims and **left-click** fires. **G / middle-click** selects a weapon, **Z** zooms, **R** reloads, **I** opens cargo and **Y** exits. A passenger seat may not control the gun. These are defaults; the vehicle HUD shows current bindings and ammunition.

Server-confirmed feedback distinguishes a hit without HP loss, the amount of damage and a destroyed target.

## Wounds and healing

Leave the vehicle and press **H** to inspect wounds. First Aid tracks the head, body, arms and legs separately. Check **Options → Controls → First Aid** if the key has been changed.

Hold a bandage or plaster and **right-click**, then hold the button for the wounded body part until the countdown finishes. Healing takes time. Replenish medical supplies through **Kit**.

## Graphics and performance

Choose **Low**, **Balanced** or **Quality** in **Settings → Profile** and explicitly apply it. Low reduces effects. Existing graphics choices survive ordinary updates. Language selection changes the language without applying a graphics profile.

If FPS is low, start with Low, shaders off, a render distance of 4–6 chunks and reduced particles. Check FPS with **F3** and change one setting at a time. A smooth picture with delayed actions or returning blocks points to the connection or server. Optional shader screenshots do not establish an FPS guarantee.

## Credits and sources

MC Heli CE — [Warfactory / EMB4](https://github.com/Warfactory-Official/McHeliCE); Techguns — [pWn3d_1337](https://www.curseforge.com/minecraft/mc-mods/techguns); First Aid — [ichttt / TechnikforLife](https://github.com/ichttt/FirstAid); Enhanced Visuals and CreativeCore — [CreativeMD](https://github.com/CreativeMD).

Forge — MinecraftForge; WorldEdit — EngineHub; JourneyMap — TeamJM; JEI — mezz; BSL — CaptTatsu; [OptiFine — sp614x](https://optifine.net/); Java — Eclipse Temurin. Components retain their original licenses. See the installed [third-party sources and notices](THIRD-PARTY-NOTICES.md) and Java's bundled notices.
