# CruzDoodelZ Server Studio 0.10.0 — server workspaces and analytics

## Included

- A server tab bar for selecting each profile's workspace. Existing configuration/map caches preserve per-server edits. The file editor identifies its server and continues to create original-file backups before saving.
- Performance controls per profile: logical CPU selection, process priority, DayZ parallel worker count, server FPS ceiling, Windows CPU budget, RAM warnings and an optional private committed-memory ceiling.
- Separate live-apply and saved settings. Worker count/FPS ceiling require restart. Process controls apply to the selected managed PID; access failures are reported. The app does not overclock CPUs or reserve physical cores/RAM.
- A server-only CDS Telemetry addon, built into a PBO and supplied separately as a mod ZIP. Install/update it from Live analytics while the selected server is stopped, then restart DayZ.
- Native engine FPS averages/min/max over 64 frames, measured script-update rate, mean/peak update frame times, slow frames, player count, optional player positions/names, ping and health.
- Read-only ground-loot samples around one rotating player area every 15 seconds, with nearby infected/vehicle counts, radius, age and truncation indication. This is not a whole-world economy census.
- Local SQLite history with configurable retention (1–30 days), engine-FPS/CPU/RAM charts, and 100 m player-occupancy heatmaps. Player identities use temporary session slots; Steam IDs are not exported. Display names are opt-in.
- Live player, historical heatmap and sampled-loot overlays in the existing map workshop. Stale live data is hidden. Historical heat remains available for the chosen period. Map calibration stays per profile.
- Discord `/taldris analytics` reports aggregate measurements to authorized users. Existing optional bot notifications include rate-limited resource/FPS warnings.
- A configurable community Discord invite under Discord / service and an optional startup welcome. No invite is assumed and no browser opens without a user click.

## CPU and RAM semantics

Process priority changes Windows scheduling preference. CPU affinity chooses eligible logical processors; it does not give exclusive ownership. `-cpuCount` chooses DayZ's parallel worker count and is not a guarantee that every game task runs in parallel. The CPU budget is a Windows Job Object scheduling ceiling expressed as a percentage of system CPU time.

The hard memory ceiling limits private committed process memory, not just resident working-set RAM. Allocations above it can fail and DayZ may stop/crash. It is disabled by default and requires a product confirmation when changed. A warning-only threshold is available. Limits below current private committed memory are rejected. Job objects never use kill-on-close, so agent upgrades do not intentionally terminate server processes. Existing named jobs are reopened after an agent upgrade. Failed live changes attempt to restore previous process/job settings; a startup failure applying requested controls stops the newly created process rather than silently running uncapped.

## Telemetry setup

1. Select the server tab and open Live analytics → Collection settings.
2. Stop the DayZ server. Enable telemetry and choose collection options. Names and loot scanning are off by default.
3. Click Install / update server-only bridge. The application adds @CDSTelemetry as a local server-only mod and writes its profile-specific config.
4. Restart DayZ. Fresh snapshot status appears under Live analytics; choose overlays in Map & markers.
5. Use your existing Discord bot configuration for `/taldris analytics`. The bridge itself contains no Discord token and makes no HTTP/RPC calls.

The native FPS methods follow Bohemia's current script API. Update rate is measured from MissionServer.OnUpdate and is not presented as a separately measured network tick rate. The frame window includes bridge work in later updates rather than claiming a full engine profiler. Snapshots alternate between two bounded JSON files under the selected DayZ profiles folder. Partial, stale, mismatched and malformed samples are rejected. History is scoped by server ID.

## Inspiration

Feature organization was informed by mr-guard/dayz-server-manager (status, metrics and operations) and the CFTools DayZ feature overview (per-server monitoring, maps and analysis). This implementation uses the existing CDS desktop/agent architecture and does not depend on either service or copy their interface/source.

- https://github.com/mr-guard/dayz-server-manager
- https://cftools.com/title/dayz
- https://github.com/BohemiaInteractive/DayZ-Script-Diff
- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects

## Verification and remaining limits

Python syntax and local collector data flow are checked. Offscreen UI previews cover the new views. A successful Windows build is not proof that live CPU/memory controls or the DayZ addon work on the target server. The PBO container can be validated locally; actual Enforce compilation and native FPS behavior require a DayZ test server. This is a development release. Automated test suites are skipped for the requested build-only publishing workflow.

No automatic ban/wipe, remote cloud backend, global player database or exhaustive map-wide entity scan is added. File editing and backups continue through the existing guarded configuration workflow.

## 0.10.1 hotfix

Renames the telemetry snapshot field World to WorldName to avoid the built-in Enforce World type. The collector accepts both names for compatibility. Reinstall/update the server-only bridge while the server is stopped to replace the PBO.

## 0.10.2 hotfix

Prefixes every player, loot and snapshot DTO member with CDS, including the engine type collision Slot. The collector normalizes the prefixed fields and still accepts older snapshots. Existing bridge configuration is preserved. Reinstall/update the server-only bridge after updating Studio.
