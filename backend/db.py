"""Database layer. Owner: Pablo. STUB: in-memory, replace with Supabase.

Keep these three function names and signatures. Table schema is in
supabase/schema.sql. Use SUPABASE_SERVICE_KEY here (backend only).
"""
from typing import Optional

_CALLS: dict[str, dict] = {}


def upsert_call(conversation_id: str, fields: dict) -> dict:
    """Create or update a row keyed by conversation_id. Returns the row."""
    row = _CALLS.setdefault(
        conversation_id,
        {"conversation_id": conversation_id, "status": "pending", "imessage_sent": False},
    )
    row.update(fields)
    return dict(row)


def get_call(conversation_id: str) -> Optional[dict]:
    """Return the row, or None if it does not exist."""
    row = _CALLS.get(conversation_id)
    return dict(row) if row else None


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
