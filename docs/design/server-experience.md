# Server experience references

Reviewed on October 4, 2026 for RV Warfare players joining a friend's server. This comparison covers installation, invitation handling, equipment choice and the presentation of military models. It does not establish another server's current uptime, FPS, damage behavior or device compatibility.

## Observed references

| Reference | Observed behavior | Decision for RV |
| --- | --- | --- |
| [Flan's Mod Factions Pack](https://www.curseforge.com/minecraft/modpacks/flans-mod-factions-pack) | The author lists a Forge 1.12.2 modpack for its official server, an app installation action and a server destination. The inspected gallery contains no images. | Keep one matching client/server version and one installation entry point; do not treat a server listing as gameplay or visual evidence. |
| [CurseForge server invitations](https://blog.curseforge.com/the-easiest-way-to-play-modded-minecraft-with-your-friends-curseforge-servers-are-here/) | The provider describes an invitation that installs the modpack, launches Minecraft and connects to the server. | Remove repeated address entry and manual Java/mod setup. Verify the complete invitation journey, including cancellation and a server that is unavailable. |
| [Modrinth content management](https://modrinth.com/news/article/content-management-overhaul/) | The provider keeps app/server content management consistent and separates modpack content, with dependency and client-side handling. | Keep client/host release identity consistent and preserve personal settings and extra files during managed updates. |
| [ModularWarfare gallery](https://www.curseforge.com/minecraft/mc-mods/modularwarfare/gallery) | The inspected six-image gallery shows scopes, weapon skins, armor/backpacks, inventory, flashlights and attachment controls. Models and equipment are visible in ordinary Minecraft scenes. | Show actual models and their controls with shaders disabled as well as optional shader captures. Use RV game captures; do not reuse third-party screenshots as RV evidence. |

## Current RV journey and confirmed gaps

The installer already manages Java, Forge, libraries and the exact mod downloads. The host can export a `.rvinvite` file, and first-play setup imports it without typing the destination. Source inspection shows that a successful first-play setup continues the original Play action. Import remains a manual file-selection step; a native invitation-to-game connection has not yet been established on two separate computers.

The exact 2.0.3 package completed a fresh installation in empty isolated application-data directories without Java on PATH. Bundled Java 8 ran, all 1,347 manifest files matched their SHA-1 digests, and the installed Check action passed. A second installation preserved settings, an unfinished first-play draft, the selected port, update preference and a test world. These checks do not establish physical device setup or an external connection.

Players can preview equipment, keep their existing gear, confirm a selected loadout, choose teams and vote for a round. The menu must expose the same server permissions it enforces. The two-player path, tagged-bandage stacking and rollback after a post-write failure before container packet forwarding have native evidence. Recovery after partial packet delivery and the third-player voting path require separate acceptance.

The gear capture exposes a central seam in wide vanilla button backgrounds. The next rendering change uses the existing RV panel colors and preserves button actions, click sounds, hover, disabled state and keyboard focus. Native captures in both languages and at multiple resolutions are required before this UI is accepted.

The main download remains stable RV 1.2.1, while the player-menu screenshots describe Preview 2.0.3. Preview instructions now link the corresponding release explicitly so a player does not install the stable version expecting the Preview menu.

## Quality acceptance

Use one complete installer, a matching host version and a host-generated invitation. A player chooses input and graphics once; later launches retain that choice. Offline update checks leave the installed game usable. No player should need to copy Java arguments, edit mod configuration files or type equipment commands for the normal menu flow.

The Low graphics profile and shaders-disabled captures remain first-class references. Detailed models must retain readable silhouettes, intact textures and useful controls without requiring shaders. Screenshots demonstrate appearance only; weak-PC suitability requires measured FPS, server tick time and memory during flight, combat and destruction in the actual map.
