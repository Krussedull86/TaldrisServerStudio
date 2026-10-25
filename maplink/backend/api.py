"""RPVerse MapLink API v0.1: admin CRUD and crash-conscious two-server transfers.

This is the coordination service, NOT a DayZ inventory serializer or PBO.
All endpoints are private by default; place behind TLS/VPN, never expose DB.
"""
import hashlib
import hmac
import json
import os
import secrets
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from psycopg.types.json import Jsonb

from .db import transaction
from .logic import next_state, same_secret, sha256_secret, snapshot_digest, validate_steam_id, validate_uuid, TransitionError
from .models import ServerIn, TicketIn, VideoIn, RouteIn, TerminalIn, PrepareIn, ResolveIn

app = FastAPI(title="RPVerse MapLink Hive", version="0.1.0", docs_url=None, redoc_url=None)
UI_FILE = Path(__file__).resolve().parent.parent / "web" / "index.html"


def admin(authorization: Annotated[str | None, Header()] = None):
    configured = os.getenv("MAPLINK_ADMIN_TOKEN", "")
    if len(configured) < 32:
        raise HTTPException(503, "MAPLINK_ADMIN_TOKEN must be set to 32+ characters")
    if not authorization or not hmac.compare_digest(authorization, "Bearer " + configured):
        raise HTTPException(401, "Admin authorization required")
    return True


def server_auth(
    x_rpv_server_id: Annotated[str | None, Header()] = None,
    x_rpv_server_key: Annotated[str | None, Header()] = None,
):
    if not x_rpv_server_id or not x_rpv_server_key:
        raise HTTPException(401, "Server credentials required")
    with transaction() as cur:
        cur.execute("SELECT api_key_hash, enabled FROM servers WHERE id=%s", (x_rpv_server_id,))
        row = cur.fetchone()
    if not row or not row["enabled"] or not same_secret(x_rpv_server_key, row["api_key_hash"]):
        raise HTTPException(401, "Invalid server credentials")
    return x_rpv_server_id


def audit(cur, transfer_id, kind, details=None):
    cur.execute("INSERT INTO audit_events(transfer_id,kind,details) VALUES (%s,%s,%s)",
                (transfer_id, kind, Jsonb(details or {})))


def enqueue(cur, event_type, data):
    cur.execute("INSERT INTO discord_outbox(event_type,payload) VALUES (%s,%s)", (event_type, Jsonb(data)))


def require_state(row, state):
    if not row or row["state"] != state:
        raise HTTPException(409, f"Transfer must be in {state} state")


@app.get("/health")
def health():
    with transaction() as cur:
        cur.execute("SELECT 1 AS ok")
        cur.fetchone()
    return {"status": "ok", "service": "maplink-hive", "version": "0.1.0"}


@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(UI_FILE)


@app.get("/admin/overview", dependencies=[Depends(admin)])
def overview():
    with transaction() as cur:
        cur.execute("SELECT COUNT(*) AS count FROM servers WHERE enabled")
        servers = cur.fetchone()["count"]
        cur.execute("SELECT COUNT(*) AS count FROM routes WHERE enabled")
        routes = cur.fetchone()["count"]
        cur.execute("SELECT state,COUNT(*) AS count FROM transfers GROUP BY state")
        transfers = {r["state"]: r["count"] for r in cur.fetchall()}
    return {"servers": servers, "routes": routes, "transfers": transfers}


@app.get("/admin/servers", dependencies=[Depends(admin)])
def list_servers():
    with transaction() as cur:
        cur.execute("SELECT id,display_name,map_name,host,game_port,enabled FROM servers ORDER BY id")
        return cur.fetchall()


@app.post("/admin/servers", dependencies=[Depends(admin)], status_code=201)
def new_server(item: ServerIn):
    key = secrets.token_urlsafe(48)
    with transaction() as cur:
        cur.execute("""INSERT INTO servers(id,display_name,map_name,host,game_port,api_key_hash)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (item.id, item.display_name, item.map_name, item.host, item.game_port, sha256_secret(key)))
    return {"id": item.id, "api_key_once": key, "warning": "Copy now; only the hash is stored"}


@app.get("/admin/tickets", dependencies=[Depends(admin)])
def list_tickets():
    with transaction() as cur:
        cur.execute("SELECT * FROM tickets ORDER BY id")
        return cur.fetchall()


@app.post("/admin/tickets", dependencies=[Depends(admin)], status_code=201)
def new_ticket(item: TicketIn):
    with transaction() as cur:
        cur.execute("""INSERT INTO tickets(id,name,classname,quantity,consume_on_departure)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (item.id,item.name,item.classname,item.quantity,item.consume_on_departure))
    return {"id": item.id}


@app.get("/admin/videos", dependencies=[Depends(admin)])
def list_videos():
    with transaction() as cur:
        cur.execute("SELECT * FROM videos ORDER BY id")
        return cur.fetchall()


@app.post("/admin/videos", dependencies=[Depends(admin)], status_code=201)
def new_video(item: VideoIn):
    with transaction() as cur:
        cur.execute("INSERT INTO videos(id,name,departure_asset,arrival_asset) VALUES (%s,%s,%s,%s)",
                    (item.id,item.name,item.departure_asset,item.arrival_asset))
    return {"id":item.id}


@app.get("/admin/routes", dependencies=[Depends(admin)])
def list_routes():
    with transaction() as cur:
        cur.execute("SELECT * FROM routes ORDER BY name")
        return cur.fetchall()


@app.post("/admin/routes", dependencies=[Depends(admin)], status_code=201)
def new_route(item: RouteIn):
    with transaction() as cur:
        cur.execute("""INSERT INTO routes(id,name,source_server_id,target_server_id,ticket_id,video_id,
                        currency_classname,price,spawn_x,spawn_y,spawn_z,enabled)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (item.id,item.name,item.source_server_id,item.target_server_id,item.ticket_id,item.video_id,
                     item.currency_classname,item.price,item.spawn_x,item.spawn_y,item.spawn_z,item.enabled))
    return {"id": item.id}


@app.get("/admin/terminals", dependencies=[Depends(admin)])
def list_terminals():
    with transaction() as cur:
        cur.execute("""SELECT t.*, COALESCE(array_agg(tr.route_id) FILTER (WHERE tr.route_id IS NOT NULL),'{}') AS route_ids
                       FROM terminals t LEFT JOIN terminal_routes tr ON tr.terminal_id=t.id
                       GROUP BY t.id ORDER BY t.name""")
        return cur.fetchall()


@app.post("/admin/terminals", dependencies=[Depends(admin)], status_code=201)
def new_terminal(item: TerminalIn):
    with transaction() as cur:
        cur.execute("""INSERT INTO terminals(id,server_id,name,classname,x,y,z,radius,auto_spawn,enabled)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (item.id,item.server_id,item.name,item.classname,item.x,item.y,item.z,item.radius,item.auto_spawn,item.enabled))
        for route_id in set(item.route_ids):
            cur.execute("SELECT source_server_id FROM routes WHERE id=%s", (route_id,))
            row = cur.fetchone()
            if not row or row["source_server_id"] != item.server_id:
                raise HTTPException(422, f"Route {route_id} is not on terminal's source server")
            cur.execute("INSERT INTO terminal_routes(terminal_id,route_id) VALUES (%s,%s)", (item.id,route_id))
    return {"id": item.id}


@app.get("/admin/transfers", dependencies=[Depends(admin)])
def list_transfers(limit: int = Query(default=60, ge=1, le=500)):
    with transaction() as cur:
        cur.execute("""SELECT id,steam_id,route_id,source_server_id,target_server_id,state,created_at,updated_at
                       FROM transfers ORDER BY created_at DESC LIMIT %s""", (limit,))
        return cur.fetchall()


@app.post("/admin/transfers/{transfer_id}/resolve", dependencies=[Depends(admin)])
def resolve(transfer_id: str, request: ResolveIn):
    tid = validate_uuid(transfer_id)
    with transaction() as cur:
        cur.execute("SELECT * FROM transfers WHERE id=%s FOR UPDATE", (tid,))
        transfer = cur.fetchone()
        require_state(transfer,"PREPARED")
        if request.action != "cancel_prepared":
            raise HTTPException(422,"Unsupported operation")
        cur.execute("UPDATE transfers SET state='CANCELLED', updated_at=now() WHERE id=%s", (tid,))
        cur.execute("UPDATE characters SET transfer_locked=false WHERE steam_id=%s", (transfer["steam_id"],))
        audit(cur,tid,"admin_cancel_prepared")
    return {"id":tid,"state":"CANCELLED"}


@app.get("/v1/manifest", dependencies=[])
def manifest(server_id: str = Depends(server_auth)):
    # Server-to-server API only, never include secret hashes.
    with transaction() as cur:
        cur.execute("""SELECT id,name,classname,x,y,z,radius,auto_spawn FROM terminals
                       WHERE server_id=%s AND enabled ORDER BY id""", (server_id,))
        terminals = cur.fetchall()
        cur.execute("""SELECT r.id,r.name,r.source_server_id,r.target_server_id,r.ticket_id,r.video_id,
                       r.currency_classname,r.price,r.spawn_x,r.spawn_y,r.spawn_z,
                       t.classname AS ticket_classname,t.quantity AS ticket_quantity,
                       t.consume_on_departure,v.departure_asset,v.arrival_asset
                       FROM routes r LEFT JOIN tickets t ON t.id=r.ticket_id
                       LEFT JOIN videos v ON v.id=r.video_id
                       WHERE r.source_server_id=%s AND r.enabled ORDER BY r.name""", (server_id,))
        routes = cur.fetchall()
        cur.execute("SELECT terminal_id,route_id FROM terminal_routes WHERE terminal_id IN (SELECT id FROM terminals WHERE server_id=%s)", (server_id,))
        links = cur.fetchall()
    return {"server_id":server_id,"terminals":terminals,"routes":routes,"terminal_routes":links}


def checked_transfer_id(tid: str):
    try:
        return validate_uuid(tid)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422,"Invalid transfer UUID") from exc


@app.post("/v1/transfers/prepare")
def prepare(body: PrepareIn, server_id: str = Depends(server_auth)):
    tid = checked_transfer_id(body.transfer_id)
    try:
        steam = validate_steam_id(body.steam_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    raw = json.dumps(body.snapshot,ensure_ascii=False,separators=(",",":"))
    if not body.snapshot or len(raw.encode("utf8")) > 512_000:
        raise HTTPException(422,"Snapshot must be nonempty and <= 500 KiB")
    digest = snapshot_digest(body.snapshot)
    with transaction() as cur:
        cur.execute("SELECT * FROM routes WHERE id=%s AND enabled FOR SHARE", (body.route_id,))
        route = cur.fetchone()
        if not route or route["source_server_id"] != server_id:
            raise HTTPException(403,"Route unavailable for this server")
        if route["ticket_id"] and not body.ticket_verified:
            raise HTTPException(409,"Ticket verification required from source server")
        if route["price"] and not body.payment_verified:
            raise HTTPException(409,"Payment verification required from source server")
        # Lock the character row before testing uniqueness. New players are inserted idempotently.
        cur.execute("INSERT INTO characters(steam_id,owner_server_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (steam,server_id))
        cur.execute("SELECT * FROM characters WHERE steam_id=%s FOR UPDATE", (steam,))
        char = cur.fetchone()
        cur.execute("SELECT id,route_id,snapshot_sha256,state FROM transfers WHERE id=%s", (tid,))
        prior = cur.fetchone()
        if prior:
            if prior["state"] == "PREPARED" and prior["route_id"] == body.route_id and prior["snapshot_sha256"] == digest:
                return {"id":tid,"state":"PREPARED", "idempotent":True}
            raise HTTPException(409,"Transfer id already used")
        if char["transfer_locked"] or char["owner_server_id"] != server_id:
            raise HTTPException(409,"Character locked or owned by another server")
        cur.execute("""INSERT INTO transfers(id,steam_id,route_id,source_server_id,target_server_id,state,
                       snapshot,snapshot_sha256,ticket_evidence)
                       VALUES (%s,%s,%s,%s,%s,'PREPARED',%s,%s,%s)""",
                    (tid,steam,body.route_id,server_id,route["target_server_id"],
                     Jsonb(body.snapshot),digest,Jsonb({"ticket_verified":body.ticket_verified,"payment_verified":body.payment_verified})))
        cur.execute("UPDATE characters SET transfer_locked=true WHERE steam_id=%s", (steam,))
        audit(cur,tid,"prepared",{"route":body.route_id})
    return {"id":tid,"state":"PREPARED"}


@app.post("/v1/transfers/{transfer_id}/commit")
def commit(transfer_id: str, server_id: str = Depends(server_auth)):
    tid = checked_transfer_id(transfer_id)
    with transaction() as cur:
        cur.execute("SELECT * FROM transfers WHERE id=%s FOR UPDATE",(tid,))
        tr=cur.fetchone()
        if not tr or tr["source_server_id"] != server_id:
            raise HTTPException(403,"Transfer does not belong to source server")
        if tr["state"] == "READY":
            return {"id":tid,"state":"READY", "idempotent":True}
        require_state(tr,"PREPARED")
        cur.execute("UPDATE transfers SET state='READY',updated_at=now() WHERE id=%s",(tid,))
        cur.execute("UPDATE characters SET owner_server_id=NULL,updated_at=now() WHERE steam_id=%s",(tr["steam_id"],))
        audit(cur,tid,"committed")
        enqueue(cur,"travel_started",{"steam_id":tr["steam_id"],"from":tr["source_server_id"],"to":tr["target_server_id"]})
    return {"id":tid,"state":"READY"}


@app.post("/v1/transfers/{transfer_id}/claim")
def claim(transfer_id: str, server_id: str = Depends(server_auth)):
    tid = checked_transfer_id(transfer_id)
    with transaction() as cur:
        cur.execute("SELECT * FROM transfers WHERE id=%s FOR UPDATE",(tid,))
        tr=cur.fetchone()
        if not tr or tr["target_server_id"] != server_id:
            raise HTTPException(403,"Transfer does not belong to target server")
        # No automatic repeat claim: prevents duplicate inventory spawning on network retries.
        require_state(tr,"READY")
        cur.execute("UPDATE transfers SET state='CLAIMED',claim_attempts=claim_attempts+1,updated_at=now() WHERE id=%s",(tid,))
        audit(cur,tid,"claimed",{"destination":server_id})
        return {"id":tid,"state":"CLAIMED","steam_id":tr["steam_id"],"snapshot":tr["snapshot"],
                "snapshot_sha256":tr["snapshot_sha256"]}


@app.post("/v1/transfers/{transfer_id}/complete")
def complete(transfer_id: str, server_id: str = Depends(server_auth)):
    tid=checked_transfer_id(transfer_id)
    with transaction() as cur:
        cur.execute("SELECT * FROM transfers WHERE id=%s FOR UPDATE",(tid,))
        tr=cur.fetchone()
        if not tr or tr["target_server_id"] != server_id:
            raise HTTPException(403,"Transfer does not belong to target server")
        if tr["state"] == "COMPLETE":
            return {"id":tid,"state":"COMPLETE", "idempotent":True}
        require_state(tr,"CLAIMED")
        cur.execute("UPDATE transfers SET state='COMPLETE',updated_at=now(),completed_at=now() WHERE id=%s",(tid,))
        cur.execute("""UPDATE characters SET owner_server_id=%s,snapshot=%s,transfer_locked=false,
                       version=version+1,updated_at=now() WHERE steam_id=%s""",
                    (server_id,Jsonb(tr["snapshot"]),tr["steam_id"]))
        audit(cur,tid,"completed")
        enqueue(cur,"travel_completed",{"steam_id":tr["steam_id"],"from":tr["source_server_id"],"to":server_id})
    return {"id":tid,"state":"COMPLETE"}


@app.post("/v1/transfers/{transfer_id}/cancel")
def cancel(transfer_id: str, server_id: str = Depends(server_auth)):
    tid=checked_transfer_id(transfer_id)
    with transaction() as cur:
        cur.execute("SELECT * FROM transfers WHERE id=%s FOR UPDATE",(tid,))
        tr=cur.fetchone()
        if not tr or tr["source_server_id"] != server_id:
            raise HTTPException(403,"Transfer does not belong to source server")
        require_state(tr,"PREPARED")
        cur.execute("UPDATE transfers SET state='CANCELLED',updated_at=now() WHERE id=%s",(tid,))
        cur.execute("UPDATE characters SET transfer_locked=false WHERE steam_id=%s",(tr["steam_id"],))
        audit(cur,tid,"cancelled")
    return {"id":tid,"state":"CANCELLED"}


@app.get("/v1/characters/{steam_id}/entry")
def entry(steam_id: str, server_id: str = Depends(server_auth)):
    try:
        steam_id=validate_steam_id(steam_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    with transaction() as cur:
        cur.execute("SELECT owner_server_id,transfer_locked FROM characters WHERE steam_id=%s",(steam_id,))
        char=cur.fetchone()
        cur.execute("SELECT id,state,target_server_id FROM transfers WHERE steam_id=%s AND state IN ('PREPARED','READY','CLAIMED')",(steam_id,))
        tr=cur.fetchone()
    if tr:
        return {"allowed":False,"reason":"transfer_pending","transfer_id":str(tr["id"]),"state":tr["state"]}
    # A never-seen player can start at any server. Once owned, one destination only.
    allowed = not char or (char["owner_server_id"] == server_id and not char["transfer_locked"])
    return {"allowed":allowed,"reason":"ok" if allowed else "owned_by_other_server"}
