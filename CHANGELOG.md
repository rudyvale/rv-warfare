# Changelog

## 2.0.0 Preview

- Adds a native player menu for sessions, equipment and controls, with decisions validated by the server.
- Previews equipment before confirmation, preserves existing items, and supports withdrawing readiness.
- Configures missing keyboard controls automatically and supports local connection profiles and host invitations.
- Delivers the 30-page RU or EN field guide through the ordinary player's selected language.
- Binds owned modules to exact sources and actual client/server loaded-artifact digests; public archives reject private invitations and connection defaults.
- Publishes as a preview while stable 1.2.1 remains the update target. Two-player sessions, full-inventory rollback, physical controllers and new vendor combat require further testing.

## 1.2.1

- Fix server startup preparation so stock addon updates and pending graphics profiles run before the runner publishes its starting state. The vendor download mutex, port reservation and stop handling remain active.
- All mod binaries, the clean battlefield, player guide, audio and data preservation policies are unchanged.

## 1.2.0

- Eight pinned official downloads: AmbientSounds, Mouse Tweaks, Biomes O' Plenty, Immersive Vehicles, IAV, VEB, ModularWarfare and MCglTF. The installer verifies all files before applying a transaction and preserves unknown mods and user data.
- Shared server downloads run in the background with cache reuse, backups and rollback. Client checks also recognize renamed IAV and VEB content packs.
- A 2560 × 2560 clean battlefield with more roads, buildings and destructible cover, plus a 28-page field guide in English and Russian.
- Lower ambient sound settings in the Low profile and a focused combat audio overlay using existing RV sounds.
- RV's small compatibility module corrects three exact vehicle sound paths through the public IV API; original vendor archives remain unchanged.
- Reload on R follows the held ModularWarfare or Techguns weapon, keeping both input handlers available.
- The standard equipment menus keep the tested MC Heli, Techguns and FPV sets. New IV cannon firing, ModularWarfare hit and wall behavior, cross-mod damage and physical audio direction remain unverified.
- English repository documentation, quiet optional GitHub checks and the RV code icon remain in place.

## 1.1.0

- First-play setup for mouse and keyboard, FPV radios and gamepads, followed by server selection; cancelled setup preserves existing choices and calibration.
- Easy quadcopter flight with movement keys and hover braking; Geran and FP-1 throttle, bank, takeoff and exit controls.
- Updated aircraft models and textures, with bounded updates to known default addon assets that preserve custom addons.
- Tank firing respects current key bindings; server-confirmed feedback reports hits, damage and destroyed targets.
- First Aid wounds and timed healing, Enhanced Visuals and CreativeCore, plus explicit Low, Balanced and Quality graphics profiles.
- An expanded clean battlefield template, destructible props, spawn and equipment menus, and a 24-page field guide in English and Russian.
- Revised FPV motor audio and an Apache burst event correction; all other existing audio files are preserved.
- Duplicate gameplay-mod checks before Java starts, including renamed copies, with relative paths for resolving the conflict.
- Updated installer and updater package checks, model asset verification, and a separate archive of original third-party sources and notices.
- Actual game screenshots with shaders off and optional BSL shaders.

## 1.0.0

Initial RV Warfare release.

- Windows client launcher with separate Play, Install, Check and Update actions.
- English and Russian interfaces, adaptive layouts and a code icon.
- Host panel with separate Play, Start server and Stop server buttons.
- Porthole and direct connections configured through Settings.
- Quiet GitHub update checks, a persistent opt-out and verified downloads.
- Installer backups, preservation of player data and downgrade protection.
- FPV flight and impact detonation, projectile damage and controller configuration.
- Combat audio with complete sound references and saved-setting migration.
- Separate clean world template with bilingual menus and a ten-page player book.
- Starting kits preserve personal equipment and wait for available inventory space.
- Fresh installations start with shaders disabled; the bundled shader remains selectable.
- Source materials, automated checks and release tooling.
