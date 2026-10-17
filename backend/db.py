"""Database layer. Owner: Pablo. Real Supabase implementation.

Keep these three function names and signatures. Table schema is in
supabase/schema.sql. Uses SUPABASE_SERVICE_KEY (backend only, never the
dashboard). The service key bypasses RLS, so only the backend may hold it.
"""
import os
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

TABLE = "calls"

# Columns a caller is allowed to write. Anything else is dropped so a typo or
# an extra key from the webhook payload can never break an upsert.
_ALLOWED = {
    "caller_number",
    "transcript",
    "mid_call_decision",
    "verdict",
    "scam_score",
    "reasons",
    "tactics",
    "summary",
    "status",
    "imessage_sent",
}

_client: Optional[Client] = None


def _get_client() -> Client:
    """Create the Supabase client once, on first use."""
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set (see .env.example)"
            )
        _client = create_client(url, key)
    return _client


def upsert_call(conversation_id: str, fields: dict) -> dict:
    """Create or update a row keyed by conversation_id. Returns the row.

    Only the fields you pass are written. On an update, columns you leave out
    keep their current values, so the mid-call write (caller_number,
    mid_call_decision) and the post-call write (transcript) never wipe each
    other. On a first insert, omitted columns get the table defaults
    (status 'pending', imessage_sent false).
    """
    payload = {k: v for k, v in (fields or {}).items() if k in _ALLOWED}
    payload["conversation_id"] = conversation_id
    resp = (
        _get_client()
        .table(TABLE)
        .upsert(payload, on_conflict="conversation_id")
        .execute()
    )
    if resp.data:
        return resp.data[0]
    # Some client versions return no body from an upsert; read the row back.
    return get_call(conversation_id) or payload


def get_call(conversation_id: str) -> Optional[dict]:
    """Return the row, or None if it does not exist."""
    resp = (
        _get_client()
        .table(TABLE)
        .select("*")
        .eq("conversation_id", conversation_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def mark_scored(conversation_id: str, result: dict) -> dict:
    """Save a scorer result and set status to "scored". Returns the row."""
    return upsert_call(
        conversation_id,
        {
            "verdict": result["verdict"],
            "scam_score": result["scam_score"],
            "reasons": result.get("reasons", []),
            "tactics": result.get("tactics", []),
            "summary": result.get("summary", ""),
            "status": "scored",
        },
    )
