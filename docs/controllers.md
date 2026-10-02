# Controllers and flight

Open **Controller** in the launcher or press F8 in game. Input support targets devices Windows exposes as game controllers: USB radios, PlayStation and Xbox gamepads, and similar devices. Individual models still need testing with physical hardware.

FPV quads use Easy keyboard and mouse flight by default. The mouse turns the quad and looks up or down. W/S move forward or backward, A/D move sideways, Space starts the motors and climbs, Ctrl descends, and Shift exits the tablet connection. Movement follows the quad's heading. Releasing movement keys brakes and holds height. These actions follow the player's current Minecraft movement, jump, sprint and sneak bindings. Losing focus or opening a menu stops the motors and the quad descends; press Space after returning to resume. F8 also offers professional keyboard flight and controller Angle/Acro settings.

1. Connect a radio in USB Joystick mode, or a gamepad over USB or Windows Bluetooth. Click **Refresh devices** and select it.
2. Choose **Radio** or **Gamepad**. Assign four different axes: roll, pitch, yaw and throttle. Indicators show stick movement.
3. Centre every axis, including a radio's throttle, and capture the centre. Move each axis through its full range and finish calibration.
4. Check inversion: raising throttle must increase its value. Assign fire, precise aim, weapon switching, reload, weapon mode, zoom, brake, exit and flight-mode switching to suitable buttons or switches.
5. Enable controller input, save and lower a radio's throttle. On a gamepad, release the throttle stick to the centre.

Stabilized mode levels the FPV quad when you release the sticks and limits tilt to 35 degrees by default. Acro retains tilt and allows flips. Start with stabilized mode, 35% exponential response and 110 degrees per second. A dead zone suppresses stick jitter. The calm, responsive and freestyle presets adjust response while preserving calibration. Separate stick and throttle smoothing, throttle response, stabilized tilt and camera roll controls let each player tune the quad. Geran and FP-1 use the mod's native fixed-wing flight controls; the quad's Angle and Acro modes do not change their physics. On tanks, roll and pitch control aim while yaw turns the hull. Precise aim reduces aiming speed.

Radio throttle is absolute: low stops the quad motors; mid-stick is approximately hover when level. A gamepad's centred stick holds the selected throttle, while up and down adjust it at a configurable rate. Disconnecting the controller, opening a menu or losing window focus cuts UAV throttle. On return, lower the radio throttle or centre the gamepad stick. Disabling controller input in F8 restores keyboard and mouse controls.

Calibration is stored locally in `config/vm-controller.properties` under the selected game directory. Each player has independent settings. Client and server must use gameplay protocol `1.5.1-rv-controls3`; older clients with a previous control packet format are rejected. The first-play wizard uses the same calibration window and waits for Save or Cancel before proceeding.

The mod adds brief camera recoil, projectile trails and impact particles for tanks and helicopters. Recoil does not alter the hull direction or the quad's attitude. The HUD shows the current fire binding, ammo, reload state and server-confirmed hit, damage or destruction. Low reduces particle range and counts while preserving confirmed hit feedback. The combat sound pack is `Warfare-Combat-Audio.zip`, version 1.5. Quad motor volume and pitch follow throttle through the existing vehicle sound channel.

FirstAid damage feedback reads the actual limb health and critical death state. Its world-load hook preserves each world's saved natural-regeneration rule. The supplied medical configuration allows food regeneration when that rule is enabled. EnhancedVisuals keeps on-foot effects, with reduced obstruction and disabled blur; its screen effects are suppressed while using an MC Heli vehicle or FPV camera so the sight and medical HUD stay readable.
