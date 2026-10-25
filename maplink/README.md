# RPVerse MapLink · foundation v0.1

> **Development-only foundation.** Not yet a complete or safe DayZ character transfer mod. Do not run on a production server or with real player inventories.

This is the first self-contained MapLink module for [TaldrisServerStudio](../README.md). It separates coordination and persistence (FastAPI + PostgreSQL), route and ticket administration (web UI), Discord event notifications and a DayZ script integration prototype. Nothing here replaces DayZ's native world persistence.

## Implemented

- PostgreSQL schema for **servers, routes, terminal objects, ticket items, video profiles, characters, travel states, audit events and Discord outbox**.
- Admin authenticated REST endpoints to register servers (one-time secret shown), routes, tickets, videos and terminals with XYZ coordinates and route associations.
- Browser UI at `http://127.0.0.1:8907/ui` for configuration, recent transfers and dashboard overview.
- Separate server-key authentication, including a `/v1/manifest` endpoint without sensitive credentials.
- Transfer coordinator: `prepare → commit → claim → complete`. `PREPARED` can be cancelled; claims are intentionally single-use. Database-level uniqueness blocks simultaneous active transfers for one Steam64 ID.
- `/v1/characters/{steam_id}/entry` guard endpoint (to be called by a real DayZ player-login hook).
- Independent Discord webhook outbox worker; optional read-only Discord slash-command bot.
- Manifest sync CLI that writes into the DayZ server profile; preliminary DayZ PBO source tree with an interactive terminal action placeholder.
- Model / transition tests. CI workflow intentionally not added to the existing release system until reviewed.

## Start locally (Docker Desktop)

1. Copy `.env.example` to `.env` and replace the **two mandatory** password/token placeholders with long random secrets (at least 32 chars for the admin token).
2. Run `docker compose up --build -d` from this directory.
3. Visit `http://127.0.0.1:8907/ui` and paste your admin token into **Tilkobling**. Register both servers first, then tickets/videos, routes and terminals.
4. Store each new server's `api_key_once` securely; it will not be shown again.
5. To sync config to a test DayZ server profile, run (PowerShell example):

```powershell
$env:MAPLINK_SERVER_ID = 'nasdara'
$env:MAPLINK_SERVER_KEY = '<the one-time server key>'
$env:MAPLINK_URL = 'http://127.0.0.1:8907'
python -m backend.sync_config --profile 'C:\DayZServer\SC'
```

Run in `maplink/` with dependencies from `backend/requirements.txt`. This only writes config. It doesn't enable the DayZ transfer mod.

## Transfer protocol

| Transition | Called by | Preconditions | Effect |
|---|---|---|---|
| prepare | origin server | valid route, server owns character, ticket/payment verified by trusted origin | immutable snapshot + character lock |
| commit | origin server | character safely removed and disallowed from rejoining source | mark transfer READY, owner null |
| claim | destination server | READY, matching destination credentials | mark CLAIMED, return snapshot once |
| complete | destination server | restore has succeeded and durable journal recorded | store snapshot, change ownership and unlock |
| cancel | origin server | only PREPARED | cancel lock |

**Critical:** A CLAIMED transfer is not automatically retried or rolled back; manual investigation is needed after a crash to avoid dupes. The DayZ mod must provide freeze/despawn/restore and a durable journal, none of which is fully implemented yet. All clients must be stopped from spawning owned/locked characters outside their designated server.

## Discord

Set `MAPLINK_DISCORD_WEBHOOK` (server-side only) in `.env` to enable `travel_started` and `travel_completed` notifications from the independent dispatcher. For read-only slash commands, install `backend/requirements-bot.txt`, set `MAPLINK_DISCORD_BOT_TOKEN`, `MAPLINK_ADMIN_TOKEN` and `MAPLINK_URL`, run `python -m backend.discord_bot`. The bot currently supports `/maplink_status` and `/maplink_routes` (ephemeral). No real players/online data are available yet.

## Security and deployment notes

- **Local-only binding** in Compose by default (`127.0.0.1:8907`). To connect multiple physical machines, deploy a secured HTTPS reverse proxy or private VPN such as WireGuard/Tailscale. Do not open the PostgreSQL port to the Internet.
- Use one `discord_worker` instance. This alpha's outbox worker does not lease records for horizontal dispatch; parallel instances could duplicate Discord messages.
- DB credentials and webhook must remain server side. The admin token is only held in browser memory for the open tab, never stored in localStorage.
- Ticket/payment booleans are **claims from a trusted game server**, not proof. Real anti-cheat depends on implementing the server-side DayZ inventory validation and consumption before commit.
- Files in `dayz/` need build and game-engine testing. See [dayz/server/README.md](dayz/server/README.md).
- Character snapshots currently have a 500 KiB maximum. Serialization schema and mod compatibility are not complete.
- No automatic server reconnect, actual MP4 video widget, item integration for arbitrary classnames, persistent object reconciliation, or Windows `.exe` packaging in this version.

## Run tests

```sh
python -m pip install -r backend/requirements.txt
python -m unittest discover -s tests -v
```

## Next priorities

1. DayZ 1.30 server-side snapshot + terminal action / item inventory verification, first on two local test servers with matching mods.
2. Reliable local bridge and crash journal before enabling `commit` on the live server.
3. Full travel menu + videos, terminal placement via map view and server owner confirmation.
4. Native TaldrisServerStudio desktop tab to embed API-driven MapLink management.
5. Integration tests using disposable PostgreSQL and dedicated DayZ test servers.
