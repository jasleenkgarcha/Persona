"""FastAPI app. Owner: Pablo (glue). Real implementation of the endpoints in CONTRACTS.md.

Endpoints:
  GET  /health
  POST /tool/check_caller   -> {"decision": "pass"|"block"}   (mid-call; never fails open)
  POST /webhook/elevenlabs  -> 200 always once the signature is valid

Rules this file follows:
  * Anything that goes wrong while deciding a call means "block".
  * A valid webhook always gets a 200, so ElevenLabs does not retry forever.
  * A call that was already scored is never scored (or texted) twice.
"""
import hashlib
import hmac
import json
import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from backend import db
from backend.normalize import extract_caller_number, normalize_transcript, tool_fields_to_transcript
from backend.photon_send import send_imessage
from scorer.score import decide, score_call

load_dotenv()
log = logging.getLogger("backend")
app = FastAPI(title="Scam call screener")

# ElevenLabs signs "<timestamp>.<raw body>"; ignore anything older than this.
SIGNATURE_TOLERANCE_SECONDS = 30 * 60
FALLBACK_TEXT = "Call received, review needed."


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# ---------------------------------------------------------------- mid-call check


def _secrets_match(given: str, expected: str) -> bool:
    return bool(expected) and hmac.compare_digest(given.encode(), expected.encode())


@app.post("/tool/check_caller")
async def check_caller(request: Request, x_tool_secret: str = Header(default="")) -> dict:
    if not _secrets_match(x_tool_secret, os.getenv("TOOL_SHARED_SECRET", "")):
        raise HTTPException(status_code=401, detail="bad secret")

    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    conversation_id = body.get("conversation_id") or "unknown"
    caller_number = body.get("caller_number") or ""

    try:
        result = await run_in_threadpool(score_call, caller_number, tool_fields_to_transcript(body))
        decision = decide(result)
    except Exception:  # ScorerError, timeouts, anything: unsure means block
        log.exception("scorer failed during check_caller; blocking")
        decision = "block"

    # TEST OVERRIDE for Ian's transfer tests (STUB_DECISION=pass). Unset before the demo.
    forced = os.getenv("STUB_DECISION")
    if forced in ("pass", "block"):
        log.warning("STUB_DECISION is set; forcing decision=%s", forced)
        decision = forced

    fields = {"mid_call_decision": decision}
    if caller_number:
        fields["caller_number"] = caller_number
    try:
        await run_in_threadpool(db.upsert_call, conversation_id, fields)
    except Exception:
        log.exception("could not save mid-call decision (answering anyway)")

    return {"decision": decision}


# ------------------------------------------------------------ post-call webhook


def _signature_is_valid(raw: bytes, header: str) -> bool:
    """Check the ElevenLabs-Signature header: "t=<unix time>,v0=<hex hmac-sha256>"."""
    secret = os.getenv("ELEVENLABS_WEBHOOK_SECRET", "")
    if not secret:
        # Fail closed. Only skip the check when someone deliberately asks for it locally.
        if os.getenv("ALLOW_UNSIGNED_WEBHOOK") == "1":
            log.warning("no ELEVENLABS_WEBHOOK_SECRET; accepting unsigned webhook (local testing)")
            return True
        return False

    timestamp = None
    signatures = []
    for item in (header or "").split(","):
        key, _, value = item.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key.startswith("v") and value:
            signatures.append(value)
    if not timestamp or not signatures:
        return False
    try:
        if abs(time.time() - int(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
            return False
    except ValueError:
        return False

    expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in signatures)


def _save_raw(raw: bytes) -> None:
    """Lets Ian capture the first real payload (set RAW_WEBHOOK_PATH to move it)."""
    path = os.getenv("RAW_WEBHOOK_PATH", "samples/last_webhook_raw.json")
    try:
        with open(path, "wb") as f:
            f.write(raw)
    except OSError:
        log.warning("could not save raw webhook")


async def _notify(conversation_id: str, text: str) -> None:
    """Text the owner. A failed text never breaks the webhook."""
    try:
        sent = await run_in_threadpool(send_imessage, os.getenv("OWNER_PHONE", ""), text)
    except Exception:
        log.exception("send_imessage failed")
        return
    if sent:
        try:
            await run_in_threadpool(db.upsert_call, conversation_id, {"imessage_sent": True})
        except Exception:
            log.exception("could not record imessage_sent")


async def _process_call(raw: bytes) -> dict:
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        return {"ok": True, "note": "bad json"}
    if not isinstance(payload, dict):
        return {"ok": True, "note": "bad payload"}

    event_type = payload.get("type")
    if event_type and event_type != "post_call_transcription":
        return {"ok": True, "note": f"ignored {event_type}"}

    data = payload.get("data") or payload
    conversation_id = data.get("conversation_id")
    if not conversation_id:
        return {"ok": True, "note": "no conversation_id"}

    existing = await run_in_threadpool(db.get_call, conversation_id)
    if existing and existing.get("status") == "scored":
        return {"ok": True, "note": "duplicate"}

    # Prefer the number in the payload; fall back to the one saved during the call.
    number = extract_caller_number(payload) or (existing or {}).get("caller_number") or ""
    transcript = normalize_transcript(data.get("transcript"))
    fields = {"transcript": transcript}
    if number:
        fields["caller_number"] = number
    await run_in_threadpool(db.upsert_call, conversation_id, fields)

    try:
        result = await run_in_threadpool(score_call, number, transcript)
    except Exception:  # ScorerError, timeouts, anything
        log.exception("scorer failed after call; saving as pending")
        await run_in_threadpool(db.upsert_call, conversation_id, {"status": "pending"})
        await _notify(conversation_id, FALLBACK_TEXT)
        return {"ok": True, "note": "pending"}

    await run_in_threadpool(db.mark_scored, conversation_id, result)
    await _notify(
        conversation_id,
        f"{result.get('verdict')} ({result.get('scam_score')}): {result.get('summary', '')}",
    )
    return {"ok": True}


@app.post("/webhook/elevenlabs")
async def elevenlabs_webhook(request: Request) -> dict:
    raw = await request.body()
    _save_raw(raw)
    if not _signature_is_valid(raw, request.headers.get("elevenlabs-signature", "")):
        raise HTTPException(status_code=401, detail="bad signature")
    try:
        return await _process_call(raw)
    except Exception:
        # Valid signature means a 200, always (CONTRACTS.md). Log it so we can see it.
        log.exception("webhook handler failed")
        return {"ok": True, "note": "error"}
