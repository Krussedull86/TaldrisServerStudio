# DayZ server integration, alpha

- Build `addons/RPVerseMapLink` with DayZ Tools/Add-on Builder using the virtual P: drive prefix `RPVerseMapLink`.
- Mount PBO on **both client and server** with `-mod=@RPVerseMapLink` after signing it.
- `RPV_TravelTerminal` and `RPV_FerryTicket` are sample classnames. Their model inherits a vanilla placeholder; replace with licensed custom models later.
- `backend.sync_config` writes `$profile:RPVerseMapLink/terminals.json` from the admin-created definitions.
- DayZ Enforce code is an early integration prototype **NOT compiled or verified in DayZ**. It currently loads the manifest and exposes a placeholder terminal interaction. It cannot transfer characters or play videos yet.
- Existing/third-party classnames need adapter actions and safe object spawning; arbitrary objects are stored in the manifest but not automatically turned into interactive terminals.
- Never store server API keys in a client PBO or a published mission file. A trusted local bridge should communicate with the authenticated Hive API.

## Must implement before production

1. Snapshot serializer/deserializer including nested cargo, attachments, magazines, health and supported mod-state.
2. Atomic source-side freeze, inventory ticket/currency check, remove/despawn, and `prepare`/`commit` calls through local trusted bridge.
3. Destination restore, fingerprint verification, `claim`/`complete` and durable per-transfer journal to survive crashes.
4. Entry guard for all connected servers via `/v1/characters/{steam_id}/entry` to prevent return-to-source duplication.
5. Client travel UI and video widget playback, fallback when client mods differ, localization.
6. DayZ Tools script compilation, 1.30 test server and dedicated-server crash/reconnect verification.
