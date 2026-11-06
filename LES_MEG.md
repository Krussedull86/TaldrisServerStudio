# DZSA Tools — user guide

## Install or launch

Download `CruzDoodelZServerStudio-Setup.exe` from the project's GitHub Releases page. Installation creates desktop and Start menu shortcuts and a Windows Installed apps entry. A ZIP build offers installation or portable mode on first launch. The packaged application does not require Python.

Source-code users need Python 3.12 or newer. Extract or clone the complete project and run `START.bat`. The first launch requires internet access to install dependencies in `.venv`. `BUILD_EXE.bat` creates a Windows executable locally.

Application data defaults to `%LOCALAPPDATA%/TaldrisServerStudio`. The installed launcher is in `%LOCALAPPDATA%/Programs/TaldrisServerStudio`. Server folders remain where you selected them. Existing technical names are retained for compatibility; the visible product name is DZSA Tools.

## Create a server

1. Open **Get started** and enter a server name, server folder and SteamCMD folder.
2. Choose **Anonymous** or **Steam account**. Enter the Steam username when using an account.
3. Select the player count and mission. The mission must actually exist in the server installation. Available maps may require additional game data or access.
4. Click **Install & prepare**. Missing SteamCMD is downloaded from Valve. The application installs/validates DayZ Server (app 223350), downloads enabled Workshop mods (app 221100), deploys confirmed downloads and public signing keys, and creates a missing server configuration.
5. Enter a password or Steam Guard code in **SteamCMD console** only when Steam requests it. Click **Send to SteamCMD**.
6. If **Start the server after a successful install** is enabled, the server starts after the required steps succeed.
7. Check **Startup log** and the current RPT to confirm startup. A running process alone does not prove the server is ready for players.

The wizard preserves an existing configuration. Edit an existing server through **Configuration**. **Start existing server** uses the saved profile.

Steam decides download access. Anonymous login does not guarantee permission to download the server or Workshop content. If access is denied, select **Steam account** and use an account with the required access. **Test login** confirms login for that session, not download rights. SteamCMD can reuse its own cached login data.

The application does not save submitted passwords or Guard codes in profile/activity logs and masks them in its console. SteamCMD may store its own login data in its folder. **Cancel job** stops the download; incomplete files can be resumed on a later attempt. Cancelled or unconfirmed jobs do not automatically deploy mods or start the server.

## Mods

Use **Steam Workshop** to search, add a mod by ID/link or import a public collection. Inspect dependencies and load order on each mod's page. Collection import follows collection order and supports up to 100 direct items, without nested collections. Importing a mod into a profile does not subscribe your Steam account to it.

Choose client (`-mod`), server (`-serverMod`) or both for each mod. Both uses the same folder in both argument lists and downloads it once. Load order is preserved. CF must precede mods that depend on CF.

Use **Mod library → Browse local @mods** for local or development mods. Select a parent folder or an individual @mod. Optional recursive scanning finds projects below a parent folder. Local mods keep absolute source paths; PBO files are not copied or replaced by Workshop updates. Folders without packed PBOs can be imported but remain disabled until built and enabled. Build into `@YourMod/Addons` and restart to use changes; this is not hot reload of unpacked scripts.

Public `.bikey` files are copied to the server's keys folder on startup. Signature requirements are not weakened automatically. Removing a mod from the profile does not delete its source files. Workshop deployment uses staging and retains one previous version; a failure can leave earlier mods deployed, but prevents automatic server startup.

## Existing servers and multiple profiles

Import a `.bat` or `.cmd` launch script with **Import existing server from BAT / CMD**. Review and correct the server folder, CFG, profiles, game port, extra arguments and mod paths before confirming. The script is read without execution. Imported mods are local sources and are not automatically replaced by Workshop downloads.

Use **New server** for additional profiles. Profiles have separate settings, mods, backups and automation. Shared installations require distinct game/query ports, profiles folders and persistence: use separate missions or separate `instanceId` values in each CFG. Independent native restart schedules require separate mission folders because they write mission `db/messages.xml`.

Updates and backups of a shared installation wait while another server uses it. Other servers are not stopped automatically. **Delete server** removes only the selected stopped profile after confirmation; server files and world data remain. Deleting the final profile creates an empty profile.

## Local client connection

**Connect locally** launches DayZ through `DayZ_BE.exe` on the desktop, using app 221100, the selected server game port and enabled client/both mods in profile order. Select the game folder, not the DayZServer folder. Steam must be logged in and the game must be closed before changing its mod list. Double-click a mod row to choose a different local path.

Missing client mods block launch. The application does not silently subscribe or download them for the client. Server-only and disabled mods are excluded. `127.0.0.1` connects to the machine running the client; this also applies during RDP use. A client PID confirms process creation, not successful login.

## Network and runtime dependencies

Automatic Windows Firewall rules can be enabled in **Settings**. Rules apply to the selected server executable and required UDP ports; Windows requests administrator permission when a rule needs changing. The application does not configure your router, NAT or hosting provider's firewall.

Set `steamQueryPort` in **Configuration** and save. New configurations default to game port +3. Separate instances need distinct port assignments. **Local test — start without requiring Steam Query** disables the application's query requirements and monitoring. It does not disable Steam authentication or BattlEye, bind the server to localhost, or make it private.

For `XAPOFX1_5.dll` errors, install Microsoft DirectX End-User Runtimes (June 2010): extract the package and run `DXSETUP.exe`. A manually copied DLL with the wrong architecture can cause `0xc000007b`; move it outside the server folder and install the official runtime. **Fix dependencies** checks DirectX and Visual C++ x64 and opens Microsoft's download links. The application does not silently replace runtime DLLs.

HTTPS uses the bundled CA certificates together with trusted system roots. Certificate and hostname verification remain enabled. Check system time, Windows updates and trusted proxy certificates if TLS requests fail.

## Background operation and tools

The background agent owns server processes independently of the window. Install the optional Windows service under **Discord / service** for operation after logout and automatic startup with Windows. RCon provides player lists, moderation and announced restart/stop countdowns. Automation manages restart schedules, maintenance, backup retention, optional crash recovery, companion EXEs and log rotation.

Configuration editors provide visual and raw CFG/JSON/XML editing, types tables, change review, backups and history. The map tool edits X/Z points in XML layers. The integrated **DZSA Loot Editor** supports XML import/export, saved projects, bundled map templates and guarded saves to the active mission. Saved project revisions do not write the mission until **Save to mission** is used.

See [Operations, Discord, RCon and editors](DRIFT_DISCORD_EDITORER.md) for detailed setup and limits.

## Application updates and CDS icon

Open **Program updates**, select `dev` or `stable`, then choose **Save and check**. A newer package is downloaded, checked against SHA-256 and installed in a separate version folder. The panel switches versions; DayZ processes remain running. Active jobs and unsaved editor changes must finish first. **Update / repair background agent** upgrades an older agent separately.

The CDS icon is embedded in the EXE and application windows. Installed desktop/Start menu shortcuts and matching existing taskbar shortcuts use a permanent CDS icon file and the same Windows application identity. The application does not automatically pin new items to the taskbar.

Uninstallation removes the launcher, shortcuts and Installed apps entry. It preserves application data, versions, servers and worlds and does not stop the agent, service or DayZ. Stop servers and remove the service separately before deleting operational data.

## Validation

The current English release is built without automated test suites, as requested. Python syntax checks and window previews cover local verification; Windows Steam login, Guard, downloads, service operation and actual player connections still require confirmation on the target machine. External game/mod content and user-created names retain their original text.

## Performance and Live analytics

Select a server tab, then use Performance for CPU affinity, priority, worker count, FPS ceiling, CPU budget and RAM settings. A hard private-commit memory ceiling may crash DayZ when reached; it is disabled by default. Use warning-only monitoring first.

For Live analytics, stop the server, enable collection settings, install/update the server-only bridge and restart. Native engine FPS and script-update timing are separate measurements; network tick rate is not inferred. Loot counts cover sampled player areas only. See the included 0.10.0 guide for setup, retention, Discord reporting and limitations. The community invite is configured separately under Discord / service.
