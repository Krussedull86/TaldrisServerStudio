"""Pure transfer rules. The database is authoritative for state transitions."""
import hashlib
import hmac
import json
import re
import uuid

STATES = ("PREPARED", "READY", "CLAIMED", "COMPLETE", "CANCELLED")
TRANSITIONS = {
    ("PREPARED", "commit"): "READY",
    ("PREPARED", "cancel"): "CANCELLED",
    ("READY", "claim"): "CLAIMED",
    ("CLAIMED", "complete"): "COMPLETE",
}

class TransitionError(ValueError):
    pass

def next_state(state: str, action: str) -> str:
    try:
        return TRANSITIONS[(state, action)]
    except KeyError as exc:
        raise TransitionError(f"Transition not allowed: {state} -> {action}") from exc

def sha256_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()

def same_secret(candidate: str, expected_hash: str) -> bool:
    return hmac.compare_digest(sha256_secret(candidate), expected_hash)

def validate_uuid(value: str) -> str:
    return str(uuid.UUID(value))

def snapshot_digest(snapshot: dict) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def validate_steam_id(value: str) -> str:
    # DayZ Steam 64 bit IDs are 17 digits; configurable external identity schemes can be added later.
    if not re.fullmatch(r"\d{17}", value):
        raise ValueError("steam_id must be a 17-digit Steam64 ID")
    return value
