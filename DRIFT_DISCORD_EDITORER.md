# DZSA Tools — operations, Discord and editors

## Agent and Windows service

Close an older panel before launching a new release. The background agent reuses existing DayZ processes only when their executable, creation time and arguments can be verified. A process is never adopted solely because its PID matches. Panel and agent version/build numbers appear at the bottom of the window. Use **Program updates → Update / repair background agent** when the agent is older. Wait for SteamCMD, backups and queued work before upgrading. Confirmed DayZ processes remain running during an agent upgrade.

A normal agent process continues after the panel closes. For operation after Windows/RDP logout and startup with Windows, choose **Discord / service → Install / update Windows service** and accept the administrator prompt. The service retains the compatible technical name `TaldrisServerStudioAgent` and uses the panel's data folder. Windows SCM restarts a crashed agent. Previously requested running servers may restart when the agent starts, but failed maintenance must be resolved first.

The service runs as LocalSystem. Use local paths; mapped network drives generally are not available in the service session. Owners and local administrators must be trusted administrators of the machine. Agent access is loopback-only, authenticated with a random key and protected by Windows ACLs. The Discord token uses machine DPAPI and access restrictions. No cloud service is required.

The Windows installer creates desktop and Start menu shortcuts, an Installed apps entry and a stable launcher in `%LOCALAPPDATA%/Programs/TaldrisServerStudio`. Data and side-by-side versions remain in `%LOCALAPPDATA%/TaldrisServerStudio`, or the chosen `--home`. Upgrades preserve server folders. Uninstallation preserves data and running processes; stop servers and remove the service separately before deleting operational data.

## Discord setup

Create your own application/bot at https://discord.com/developers/applications.

1. Paste the bot token into the application's hidden token field. Do not publish it in source control or a Discord channel.
2. Invite the bot with the `bot` and `applications.commands` scopes.
3. Allow View Channel, Send Messages, Read Message History and Attach Files in the operations channel. Discord Administrator permission is unnecessary. Message Content and Members privileged intents are not required.
4. Enable Discord Developer Mode and copy the guild/server ID, operations channel ID and your user ID.
5. Configure at least one owner ID, comma-separated. Owners have full bot access within the configured guild.
6. Configure roles per permission. Optional per-DayZ-server role settings replace the corresponding global settings for that server.
7. Select **Save and connect Discord**. The event stream reports connection success or errors.

Permissions:

| Permission | Operations |
| --- | --- |
| `read` | Status, players, mods and logs |
| `control` | Start, stop, restart, lock and unlock |
| `moderate` | Messages, kick and ban |
| `maintenance` | Updates and backups |
| `config` | Mod lists, operations settings and access lists |
| Owner | Restore, file access, cloning, force-stop and application updates |

Discord's general Administrator role does not automatically grant bot access. Use a private operations channel for staff notifications. Replace example strings with actual numeric role IDs:

```json
{
  "read": ["READ_ROLE_ID"],
  "control": ["CONTROL_ROLE_ID"],
  "moderate": ["MODERATOR_ROLE_ID"],
  "maintenance": ["MAINTENANCE_ROLE_ID"],
  "config": ["CONFIG_ROLE_ID"]
}
```

### English Discord commands

The command group retains `/taldris` for compatibility. Its subcommands and parameter names are English:

- `/taldris servers`: servers you can view, with IDs and process status.
- `/taldris status server`: current server status.
- `/taldris panel server`: persistent buttons in the configured operations channel, with periodic status refresh.
- `/taldris start server`, `/taldris restart server minutes`, `/taldris stop server minutes`: process control and announced RCon countdowns.
- `/taldris players server`, `/taldris message server message`: player list and broadcast message.
- `/taldris action server action parameters`: other supported actions, with JSON parameters.
- `/taldris help`: action and JSON examples.
- `/taldris job id`: result of a job you can access. Short results may also arrive privately after completion; long results can be attachments.
- `/taldris file server path`: privately download a configuration and its current SHA (owner only).
- `/taldris savefile server path sha attachment`: upload an edited UTF-8 configuration. Owner confirmation, validation, current-SHA verification and backup precede writing.

The bot synchronizes command names on connection; previous Norwegian subcommand names are replaced. Files must remain within the selected server folder. Existing persistent control panels are checked against their stored message/server mapping and permissions.

Actions include `mods`, `backups`, `files`, `logs`, `file_history`, `file_restore`, `schedule_set`, `players`, `bans`, `lock`, `unlock`, `say`, `kick`, `ban`, `unban`, `backup`, `restore`, `rollback_mods`, `maintenance`, `steam`, `check_mods`, `workshop_search`, `mod_add`, `mod_collection`, `mod_remove`, `mod_mode`, `mod_move`, `local_mod_scan`, `local_mod_add`, `list_add`, `clone`, `force_stop`, `cancel_restart` and `program_prepare`.

Example parameter objects:

```json
{"player": 3, "minutes": 60, "reason": "Rule violation"}
```

```json
{"kind": "mods"}
```

```json
{"id": "123456789", "mode": "both"}
```

```json
{"scheduled_restart": true, "restart_mode": "clock", "restart_times": "00:00, 06:00, 12:00, 18:00"}
```

Mod indexes start at 0. `client` means `-mod`, `server` means `-serverMod`, and `both` uses both lists. Mod files are replaced only while the server is stopped. Local development mods are never replaced by Workshop downloads.

## RCon and status

Select the active `BEServer_x64.cfg` under **RCon & players**. It needs `RConPort` and `RConPassword`; the RCon port must differ from game/query ports. The password is read locally when connecting and is not sent to Discord. The application requires a reply before reporting success. A shutdown timeout remains unconfirmed: the process is monitored without automatically force-stopping it.

RCon supports player lists, kick, timed/permanent bans, unban, broadcasts, lock and unlock. Player IDs can change, so fetch a current list before moderation. Ban/unban changes are written to the BattlEye ban list.

Status distinguishes process creation from a Steam query reply. Neither alone confirms that a player can finish joining. Operations displays uptime, RAM, CPU and free disk. CPU can exceed 100% for processes using multiple cores. Split/compressed query responses are not currently decoded.

## Configuration center

**Configuration → Find server files** discovers UTF-8 CFG, JSON, XML and TXT inside the server folder, including missions and generated mod settings under profiles. Large cache/game-data/@mod directories are skipped. The editor accepts files up to 8 MB.

- **Visual editor** displays scalar CFG fields and complete JSON/XML structures. Known booleans use checkboxes. Passwords are masked in visual fields; **Raw text** displays the original file.
- Right-click an XML node to add a child/attribute, duplicate or delete it. The root cannot be duplicated or deleted.
- **Types / loot** supports filtering, numeric fields and category/usage/value/tag editing. Separate multiple names with semicolons. Suggestions remain editable for custom mod values.
- **Import types** can retain or replace matching classes. Structured changes preserve unknown XML fields, attributes and comments. **Bulk edit** applies a multiplier to selected rows; quantity -1 remains unchanged during scaling.
- **Changes** reviews differences. **Validate and save** requires confirmation and stores the original bytes as a backup before writing through the agent. Files changed by another client are rejected instead of silently overwritten.
- **History** restores an older version into the editor; it is not written until you save explicitly.

Covered files include serverDZ.cfg, cfggameplay.json, types.xml, events.xml, globals.xml, economy.xml, cfgeconomycore.xml, cfgspawnabletypes.xml, cfgrandompresets.xml, messages.xml, spawn/territory XML, BattlEye settings and supported mod files. Syntax checks are not a complete semantic validator for every DayZ/mod setting. Changes normally require a server restart.

## Map workshop

Choose a square map image and correct world size per profile. North is up, X increases rightward and Z upward. Scroll to zoom and drag to pan.

**+ XML layer** opens elements with `x` and `z` coordinates. Show/hide multiple layers, select a layer and group, drag points, double-click to add from the group's point template, or enter coordinates. Y, rotation and other attributes are preserved. Existing `r`/`radius` attributes can be shown as circles and edited in meters.

Undo/redo retains up to 50 edits per open layer, including profile switches during the session. **Validate and save layer** displays a diff and saves with backup. The map does not calculate terrain height or update Y automatically. It shows configured points, not live players or actual loot spawns. Arbitrary JSON coordinates and polygon tools are not supported.

## Backup, rollback and test servers

Restore selects an archive from that server's backup folder, creates a fresh backup, and swaps complete persistence directories. A transaction journal makes interrupted swaps recoverable on the next agent start. Manual restore leaves the server stopped. Archives can include passwords and player data.

Workshop deployment retains one `.previous` version. **Roll back Workshop mods** swaps to it while stopped. This does not roll back players' Workshop clients; older mods may be incompatible with newer persistence. Local mods are preserved.

**Clone to test server** uses a new folder and suggests separate ports. Standard `storage_*`, logs and previous mod versions are skipped. Copied BattlEye settings receive a new RCon port and random password. Local mod paths can still point to the same development source.

## Restart schedules and maintenance

Under **Automation**, enable automatic Steam updates, choose the check interval and whether to include DayZ server files. Enable a restart schedule with fixed local Windows times or an interval since server start. Save operations settings. The native schedule is written to mission `db/messages.xml` with backup and applies from the next server start. Other messages are preserved; conflicting shutdown schedules are rejected.

DayZ handles its native countdown, saving and clean exit. The agent then performs selected backups, SteamCMD updates, confirmed deployment and restart. Manual maintenance requires a stopped server. Steam login or Guard may require console input. Update/deployment/backup failures leave the server stopped for review. Automatic backups rotate by configured count; manual backups are preserved. Optional crash recovery waits 30 seconds and is limited to 3 attempts per 15 minutes.

For update-triggered restarts, enable **Announce a restart when a Workshop mod has an update** and set a 1–1440 minute delay. Working RCon is required for player warnings and graceful shutdown. An existing countdown is not overwritten or extended by later checks; a native restart already due within the delay is used instead. Cancelling postpones reconsideration for at least one check interval. Disabling automatic updates/mod restarts cancels an ongoing update countdown before shutdown.

Local mods are excluded from Workshop downloads/checks. If another running server shares the installation, file maintenance and update restarts are postponed. Other profiles are not automatically stopped. Coordinate shared-folder maintenance yourself. Independent native schedules require separate mission folders.

## Log rotation

The **Log rotation** tab archives closed `.RPT`, `.LOG` and `.ADM` files at the profiles folder's top level into data-folder `log_archives/<profile-ID>`. After successful archiving, unchanged originals are removed. Changed, locked or inaccessible files are kept; symlinks are not followed. Manual rotation is blocked for active/shared active log folders. Active logs are never truncated.

Choose retention days, archive count and total MB. Limits apply when rotation runs; the newest archive is always retained, even when a single session exceeds the size limit. Only archives created with this feature's naming scheme are cleaned. Rotation is optional and disabled by default.

## Companion EXEs

Select the server profile above the EXE list, then **Add EXE**. Configure a name, executable, arguments, optional working directory and whether checks apply on normal start, restart/crash recovery, or both. An empty working directory uses the executable's folder.

The agent reuses a matching full executable path and, when specified, arguments. A different executable with the same filename is not a match. Required programs cancel server startup when they fail to start or exit during the configured 0–120 second wait. Optional failures are logged and startup continues. PID/status confirms a process, not API readiness.

Add/edit/remove/enable changes are saved automatically. Right-click a row for Start, Restart or Stop, including while DayZ runs. Stop/restart can affect other profiles using that same matching process. Companion programs are not automatically stopped with DayZ, profile deletion or agent upgrades. A program that exits later is checked again on the next server start/restart, not continuously restarted.

When the agent runs as a Windows service, companion programs use the service account/session and have no visible user-desktop windows. Use suitable background programs and explicit configuration paths. Inaccessible processes can be reported as unknown rather than duplicated.

## BAT import and shared installations

**Get started** and **Settings** provide static BAT/CMD import. Review each launch candidate, fields, extra arguments and mod sources. Supported forms include ordinary `set`, `%~dp0`, `%cd%`, `cd /d`, `start` titles and `/D`, direct EXE launches, `call` directly to an EXE and `^` continuations. Dynamic conditions, nested scripts, pipes/redirection, `&&`, delayed `!variable!` expansion and restart loops are not adopted; unresolved content is reported.

Imported mods are local sources, even when folder names resemble Workshop IDs. No files are moved, CFG/world data is untouched and no server starts. The EXE and configuration must exist under the selected root. Paths outside that root must be corrected. The preview supports client/server/both modes and disabling missing mods.

Extra arguments support `-name`, `-cpuCount`, `-maxMem`, `-limitFPS`, `-BEpath`, `-filePatching`, `-netlog`, `-doSimulate`, `-noSound`, `-noSplash`, `-noPause` and `-scrAllowFileWrite`. Unknown options are reported. Config, mods, profiles and ports have dedicated fields; `-dologs`, `-adminlog` and `-freezecheck` are supplied by the application.

**Save mission to CFG** writes the selected template into the existing CFG with backup. Missions are discovered from mpmissions and CFG, with editable custom names and standard suggestions including Nasdara. A shared installation can use separate inactive CFG files, but active/shared active configurations cannot be edited. Set ports/profiles in Settings and persistence `instanceId` in Configuration; the application does not silently move worlds.

## Local DayZ client

**Connect locally** opens client setup for the selected profile/game port. Choose the folder containing `DayZ_x64.exe` and `DayZ_BE.exe`. Launch uses app 221100, `-connect=127.0.0.1`, the selected `-port`, and one absolute-path client mod list. Enabled client/both mods retain profile order; server-only/disabled mods are excluded. Steam Query is not required. Double-click to override a mod's local path. Missing mods block launch and are not automatically subscribed/downloaded. The client settings are local to the desktop, not managed by the Windows service.

## Application updates and integrated loot editor

**Program updates → Save and check** stages a newer release after SHA-256/size verification and switches the panel when jobs and unsaved edits permit. DayZ remains running. The agent upgrades separately and reconnects verified processes. Discord `program_prepare` stages an agent update even without an open panel; owner confirmation is required. Stable is promoted manually.

The integrated DZSA editor opens the selected profile's actual CFG to resolve its active mission and registered CE type files. Import/export projects are detached. Saving a project revision or autosaving does not change mission files. **Save to mission** uses stopped-server checks, target/digest verification and backup. Export uses a separate folder. Unknown XML fields/comments are preserved, but game semantics are not completely validated. No loot reset or persistence wipe is performed. Templates for Chernarus, Livonia, Sakhal and Nasdara are bundled reference data, not automatic live game updates. Credits: CruzDoodelz & NoSignal; original DZSA Tools by NIXON.

## Validation and references

The current build-only releases skip automated suites at the user's request. Local verification includes Python syntax compilation and offscreen window previews. Real Discord roles, Steam Guard, downloads, Windows service installation and player login still require target-machine verification.

- https://www.battleye.com/downloads/BERConProtocol.txt
- https://www.battleye.com/support/documentation/
- https://discord.com/developers/docs/interactions/receiving-and-responding
- https://community.bistudio.com/wiki/DayZ:Central_Economy_Configuration
- https://community.bistudio.com/wiki/DayZ:Central_Economy_mission_files_modding
- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
