# Controllers and flight

Open **Controller** in the launcher or press F8 in game. Input support targets devices Windows exposes as game controllers: USB radios, PlayStation and Xbox gamepads, and similar devices. Individual models still need testing with physical hardware.

1. Connect a radio in USB Joystick mode, or a gamepad over USB or Windows Bluetooth. Click **Refresh devices** and select it.
2. Choose **Radio** or **Gamepad**. Assign four different axes: roll, pitch, yaw and throttle. Indicators show stick movement.
3. Centre every axis, including a radio's throttle, and capture the centre. Move each axis through its full range and finish calibration.
4. Check inversion: raising throttle must increase its value. Assign fire, precise aim, weapon switching, brake, exit and flight-mode switching to suitable buttons or switches.
5. Enable controller input, save and lower a radio's throttle. On a gamepad, release the throttle stick to the centre.

Stabilized mode levels the FPV drone when you release the sticks and limits tilt to 35 degrees. Acro retains tilt and allows flips. Start with stabilized mode, 35% exponential response and 110 degrees per second. A dead zone suppresses stick jitter. On tanks, roll and pitch control aim while yaw turns the hull. Precise aim reduces aiming speed.

Radio throttle is absolute: low stops the motors; mid-stick is approximately hover when level. A gamepad's centred stick holds the selected throttle, while up and down adjust it. Disconnecting the controller, opening a menu or losing window focus cuts FPV throttle. On return, lower the radio throttle or centre the gamepad stick. Disabling controller input in F8 restores keyboard and mouse controls.

Calibration is stored locally in `config/vm-controller.properties` under the selected game directory. Each player has independent settings. Client and server must use the same gameplay mod version; older clients with the previous throttle packet format are rejected.

The mod adds brief camera recoil, projectile trails and impact particles for tanks and helicopters. Recoil does not alter the hull direction. The combat sound pack is `Warfare-Combat-Audio.zip`, version 1.3.
