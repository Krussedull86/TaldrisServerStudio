# CruzDoodelZ Server Studio

A Windows desktop application for installing, configuring and managing DayZ servers. The interface, application messages, Discord commands and bundled user guides are in English.

- Install or update DayZ Server with SteamCMD and an integrated login/download console.
- Search Steam Workshop, import collections and deploy downloaded mods.
- Load local development @mods directly from their build folders.
- Select client (`-mod`), server (`-serverMod`) or both for each mod.
- Manage multiple server profiles, shared installations, logs, backups and restart schedules.
- Use a background agent, optional Windows service, Discord controls and BattlEye RCon.
- Edit CFG/JSON/XML, loot tables and map coordinates with backup and change review.
- Use the integrated DZSA Loot Editor with import/export and direct active-mission editing.
- Install application updates from separate dev/stable release channels.

## Download and launch

Download a Windows installer or ZIP from [Releases](https://github.com/Krussedull86/TaldrisServerStudio/releases). The packaged EXE does not require Python. Use `CruzDoodelZServerStudio-Setup.exe` for installation, or extract the ZIP and run `TaldrisServerStudio.exe`.

For source-code use, install Python 3.12 or newer and run `START.bat`. The first launch creates a local virtual environment and installs dependencies. `BUILD_EXE.bat` creates `dist/TaldrisServerStudio.exe` on Windows.

## Guides

- [Getting started](LES_MEG.md)
- [Operations, Discord, RCon and editors](DRIFT_DISCORD_EDITORER.md)
- [GitHub publishing and updates](GITHUB_OPPSETT.md)
- [Integrated loot editor](FUSION_0.9.md)

## Releases

Pushes to `dev` build a Windows prerelease. Normal runs also execute automated checks. Commits explicitly marked `[build only]` skip test steps, as requested for the current publishing workflow. `[skip ci]` prevents building and therefore does not create an application update.

Stable is promoted manually from an exact dev tag, using the same verified Windows package. A push to `main` does not publish stable. See the publishing guide for details.

## Current changes

0.9.1 improved SteamCMD startup, console handling, result tracking and cancellation; added responsive overview controls and the CDS icon. 0.9.2 updates installed and matching pinned shortcuts to use the CDS icon and application identity. 0.9.3 translates the complete application interface, managed messages, Discord commands, launch scripts and bundled guides to English.

Existing user profile names, server content, paths and saved configuration values are preserved. Existing technical service, executable and data-folder names remain compatible with older installations.

## Validation and scope

Python syntax compilation and offscreen window previews have been performed for these changes. Automated test suites are skipped for the requested build-only releases. Actual Steam login, Steam Guard, DayZ downloads, Windows service operation and player connections must be verified on the target Windows setup. A running process or a Steam query reply alone does not confirm that a player can join.

For development checks:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -v
```

The application does not provide live player positions without an additional integration, configure router/NAT rules, automatically resolve every mod dependency, or perform automatic world wipes.

## 0.10.0 — per-server workspace and analytics

Server tabs, CPU/priority/memory controls, native engine FPS and frame-time telemetry, local history, live player/loot overlays, occupancy heatmaps and a configurable community Discord link. See [0.10.0 setup and limits](CHANGES_0.10.0.md). The new server-only addon is a development build and needs DayZ test-server verification.
