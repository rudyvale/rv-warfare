# Components and credits

Third-party components retain their own licenses and notices. This repository does not transfer ownership of Minecraft, mods, shaders, names or other authors' work. There is no single license covering every bundled component.

| Component | Author or source |
| :--- | :--- |
| Minecraft | [Mojang Studios / Microsoft](https://www.minecraft.net/) |
| Forge | [MinecraftForge](https://github.com/MinecraftForge/MinecraftForge) |
| MC Heli CE | [Warfactory / EMB4](https://github.com/Warfactory-Official/McHeliCE) |
| Techguns | [pWn3d_1337](https://www.curseforge.com/minecraft/mc-mods/techguns) |
| First Aid | [ichttt / TechnikforLife](https://github.com/ichttt/FirstAid) |
| Enhanced Visuals | [Sonicjumper / CreativeMD](https://github.com/CreativeMD/EnhancedVisuals) |
| CreativeCore | [CreativeMD / N247S](https://github.com/CreativeMD/CreativeCore) |
| Java 8 | [Eclipse Temurin](https://adoptium.net/) — notices included in `runtime.zip` |
| WorldEdit | [EngineHub](https://github.com/EngineHub/WorldEdit) |
| JEI | [mezz](https://github.com/mezz/JustEnoughItems) |
| JourneyMap | [TeamJM](https://www.curseforge.com/minecraft/mc-mods/journeymap) |
| MixinBooter | [CleanroomMC](https://github.com/CleanroomMC/MixinBooter) |
| ModularUI | [CleanroomMC](https://github.com/CleanroomMC/ModularUI) |
| FoamFix | [asiekierka](https://github.com/asiekierka/FoamFix) |
| BSL Shaders | [CaptTatsu](https://www.curseforge.com/minecraft/shaders/bsl-shaders) |
| OptiFine | [sp614x](https://optifine.net/) — not bundled; the installer may reuse a local copy |
| Porthole | Separate Steam application; not bundled |

`pack/package-manifest.json` lists managed files and hashes. The installer retrieves Minecraft and Forge libraries from the addresses in `pack/installer-files.json` and checks their SHA-1 hashes. Audio and Java modification materials are under `patches`.

Starting with RV 1.1.0, the separate **RV-Third-Party-Sources.zip** release asset contains the pinned original source archives and license texts for First Aid, Enhanced Visuals and CreativeCore. Their vendor JARs are unmodified. See [source notices and exact commits](pack/THIRD-PARTY-NOTICES.md) and [binary/source checksums](pack/third-party-sources.json). Notices are also distributed with the setup and installed game.
