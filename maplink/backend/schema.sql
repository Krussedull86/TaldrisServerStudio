-- RPVerse MapLink v0.1 schema. Run on a dedicated PostgreSQL database.
CREATE TABLE IF NOT EXISTS servers (
    id text PRIMARY KEY,
    display_name text NOT NULL,
    map_name text NOT NULL,
    host text NOT NULL,
    game_port integer NOT NULL CHECK (game_port BETWEEN 1 AND 65535),
    api_key_hash text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS tickets (
    id text PRIMARY KEY,
    name text NOT NULL,
    classname text NOT NULL,
    quantity integer NOT NULL DEFAULT 1 CHECK (quantity > 0),
    consume_on_departure boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS videos (
    id text PRIMARY KEY,
    name text NOT NULL,
    departure_asset text NOT NULL DEFAULT '',
    arrival_asset text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS routes (
    id text PRIMARY KEY,
    name text NOT NULL,
    source_server_id text NOT NULL REFERENCES servers(id),
    target_server_id text NOT NULL REFERENCES servers(id),
    ticket_id text REFERENCES tickets(id),
    video_id text REFERENCES videos(id),
    currency_classname text,
    price integer NOT NULL DEFAULT 0 CHECK (price >= 0),
    spawn_x double precision NOT NULL DEFAULT 0,
    spawn_y double precision NOT NULL DEFAULT 0,
    spawn_z double precision NOT NULL DEFAULT 0,
    enabled boolean NOT NULL DEFAULT true,
    CHECK (source_server_id <> target_server_id)
);
CREATE TABLE IF NOT EXISTS terminals (
    id text PRIMARY KEY,
    server_id text NOT NULL REFERENCES servers(id),
    name text NOT NULL,
    classname text NOT NULL,
    x double precision NOT NULL,
    y double precision NOT NULL,
    z double precision NOT NULL,
    radius double precision NOT NULL DEFAULT 3 CHECK (radius > 0 AND radius <= 25),
    auto_spawn boolean NOT NULL DEFAULT false,
    enabled boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS terminal_routes (
    terminal_id text NOT NULL REFERENCES terminals(id) ON DELETE CASCADE,
    route_id text NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    PRIMARY KEY (terminal_id, route_id)
);
CREATE TABLE IF NOT EXISTS characters (
    steam_id text PRIMARY KEY,
    owner_server_id text REFERENCES servers(id),
    transfer_locked boolean NOT NULL DEFAULT false,
    snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    version bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS transfers (
    id uuid PRIMARY KEY,
    steam_id text NOT NULL REFERENCES characters(steam_id),
    route_id text NOT NULL REFERENCES routes(id),
    source_server_id text NOT NULL REFERENCES servers(id),
    target_server_id text NOT NULL REFERENCES servers(id),
    state text NOT NULL CHECK (state IN ('PREPARED','READY','CLAIMED','COMPLETE','CANCELLED')),
    snapshot jsonb NOT NULL,
    snapshot_sha256 text NOT NULL,
    ticket_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    claim_attempts integer NOT NULL DEFAULT 0
);
-- Prevent double transfer even across process/server crashes.
CREATE UNIQUE INDEX IF NOT EXISTS uq_one_active_transfer_per_character
 ON transfers(steam_id) WHERE state IN ('PREPARED', 'READY', 'CLAIMED');
CREATE INDEX IF NOT EXISTS ix_transfers_recent ON transfers(created_at DESC);
CREATE TABLE IF NOT EXISTS audit_events (
    id bigserial PRIMARY KEY,
    transfer_id uuid REFERENCES transfers(id),
    kind text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS discord_outbox (
    id bigserial PRIMARY KEY,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    delivered_at timestamptz,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);
