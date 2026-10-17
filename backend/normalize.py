"""Turns ElevenLabs data into the normalized transcript the scorer expects.

DRAFT written before we have a real payload. Pablo: check this against
samples/elevenlabs_post_call.json once Ian commits it, and fix what differs.
"""
from typing import Optional

_ROLE_MAP = {"user": "caller", "agent": "agent"}


def normalize_transcript(raw: list[dict]) -> list[dict]:
    """ElevenLabs turns -> [{"role": "caller"|"agent", "text": str}].

    "user" becomes "caller", "agent" stays "agent", other roles (tool) and
    empty turns are dropped.
    """
    out = []
    for turn in raw or []:
        role = _ROLE_MAP.get(turn.get("role"))
        text = turn.get("message") or turn.get("text")
        if role and text and str(text).strip():
            out.append({"role": role, "text": str(text).strip()})
    return out


def tool_fields_to_transcript(fields: dict) -> list[dict]:
    """Mid-call check: the agent's tool fields become one caller entry."""
    parts = []
    if fields.get("caller_name"):
        parts.append(f"Caller name: {fields['caller_name']}")
    if fields.get("claimed_org"):
        parts.append(f"Claimed organization: {fields['claimed_org']}")
    if fields.get("reason"):
        parts.append(f"Reason for calling: {fields['reason']}")
    if fields.get("verbatim_quotes"):
        parts.append(f"Caller's words: {fields['verbatim_quotes']}")
    return [{"role": "caller", "text": "\n".join(parts)}] if parts else []


def extract_caller_number(payload: dict) -> Optional[str]:
    """Find system__caller_id in a post-call webhook payload, if present.

    Not yet verified against a real Photon call. Returns None if missing.
    """
    for root in (payload, payload.get("data") or {}):
        init = root.get("conversation_initiation_client_data") or {}
        number = (init.get("dynamic_variables") or {}).get("system__caller_id")
        if number:
            return str(number)
    return None
