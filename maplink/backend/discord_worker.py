"""Deliver DB outbox events to Discord webhooks. Runs independently from game transfers."""
import asyncio
import logging
import os
import httpx
from .db import transaction

log = logging.getLogger("maplink.discord")

async def drain_once(client: httpx.AsyncClient):
    webhook=os.getenv("MAPLINK_DISCORD_WEBHOOK", "")
    if not webhook:
        return 0
    with transaction() as cur:
        cur.execute("""SELECT id,event_type,payload,attempts FROM discord_outbox
                       WHERE delivered_at IS NULL AND next_attempt_at <= now() AND attempts < 12
                       ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 10""")
        rows=cur.fetchall()
        # Lock is released at end of fetch transaction; one dispatcher process should be used initially.
    n=0
    for row in rows:
        message=f"**RPVerse MapLink | {row['event_type']}**\n" + "\n".join(f"{k}: `{v}`" for k,v in row["payload"].items())
        try:
            response=await client.post(webhook,json={"content":message[:2000],"allowed_mentions":{"parse":[]}},timeout=15)
            response.raise_for_status()
            with transaction() as cur:
                cur.execute("UPDATE discord_outbox SET delivered_at=now(),attempts=attempts+1 WHERE id=%s AND delivered_at IS NULL",(row["id"],))
            n+=1
        except (httpx.HTTPError, ValueError):
            log.exception("Discord webhook failed for event %s",row["id"])
            with transaction() as cur:
                cur.execute("""UPDATE discord_outbox SET attempts=attempts+1,
                             next_attempt_at=now() + (INTERVAL '15 seconds' * LEAST(POWER(2,attempts),240))
                             WHERE id=%s AND delivered_at IS NULL""",(row["id"],))
    return n

async def main():
    logging.basicConfig(level=logging.INFO)
    async with httpx.AsyncClient() as client:
        while True:
            await drain_once(client)
            await asyncio.sleep(8)

if __name__ == "__main__":
    asyncio.run(main())
