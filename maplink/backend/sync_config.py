"""Publish server-specific config to the DayZ profile from RPVerse Hive.

Run manually or with Windows Task Scheduler. Never store server keys in workshop/PBO.
"""
import argparse
import json
import os
import pathlib
import tempfile
import httpx


def sync(api_url: str, server_id: str, server_key: str, profile_dir: pathlib.Path):
    url = api_url.rstrip("/") + "/v1/manifest"
    response = httpx.get(url, headers={"X-RPV-Server-ID":server_id, "X-RPV-Server-Key":server_key}, timeout=15)
    response.raise_for_status()
    manifest = response.json()
    if manifest.get("server_id") != server_id:
        raise RuntimeError("Mismatched server manifest")
    directory = profile_dir / "RPVerseMapLink"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "terminals.json"
    # Do not store auth tokens in files visible to clients.
    payload = {"version":1,"terminals":manifest["terminals"],"routes":manifest["routes"],"terminal_routes":manifest["terminal_routes"]}
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=directory,delete=False,suffix=".tmp") as handle:
        json.dump(payload,handle,ensure_ascii=False,indent=2)
        handle.flush()
        os.fsync(handle.fileno())
        temp_name = handle.name
    os.replace(temp_name,path)
    return path

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",default=os.getenv("MAPLINK_URL","http://127.0.0.1:8907"))
    parser.add_argument("--id",default=os.getenv("MAPLINK_SERVER_ID"),required=not bool(os.getenv("MAPLINK_SERVER_ID")))
    parser.add_argument("--profile",required=True,help="DayZ server profile path, e.g. C:\\DayZServer\\SC")
    options=parser.parse_args()
    key=os.environ.get("MAPLINK_SERVER_KEY","")
    if not key:parser.error("MAPLINK_SERVER_KEY environment variable required")
    print(sync(options.url, options.id, key, pathlib.Path(options.profile)))
