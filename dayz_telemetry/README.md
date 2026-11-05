# CDS Telemetry — server-only development addon

This addon reports read-only DayZ server telemetry to CruzDoodelZ Server Studio. Clients do not need it. Use `-serverMod`, not a client mod list. It does not change player inventory, loot settings or persistence.

Recommended installation: stop the selected server, open Studio → Live analytics → Collection settings, enable collection, then choose Install / update server-only bridge. Restart the server. Each profile gets a bridge ID and config under `<profiles>/CDSTelemetry/config.json`.

The bridge writes alternating `snapshot0.json` and `snapshot1.json` files. The local agent validates source, schema, freshness, sizes and coordinates. No Discord token, web service or client RPC is used. Engine FPS uses native GetAvgFPS/GetMinFPS/GetMaxFPS with 64-frame windows. Script-update rate/frame times are measured separately from MissionServer.OnUpdate; network tick rate is not guessed.

Collection interval is 2–60 seconds. Positions are optional; display names and local loot scanning are off by default. Temporary session slots are used instead of Steam IDs. Optional loot sampling covers one rotating player's area every 15 seconds, radius 25–200 m, up to 250 ground items. It reports sample age and truncation. Counts of infected and vehicles refer only to that area, not the entire server.

Manual use: extract @CDSTelemetry to the server folder, load it using -serverMod, and copy the example config to the profiles folder as CDSTelemetry/config.json. Set BridgeId to a unique 32-character hexadecimal value and Enabled to true. Enable matching collection in Studio. Studio's installer normally handles this automatically.

Build the PBO from source with `python scripts/build_telemetry.py` in the Studio repository. The PBO is an uncompressed container; no private signing key is required for server-only use. Enforce compilation and operation must be checked on a DayZ test server before production use.
