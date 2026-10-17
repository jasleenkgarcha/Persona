"""FastAPI app. Owner: Pablo (glue). STUB: returns fixed values so Ian can deploy and test now.

Endpoints (see CONTRACTS.md):
  GET  /health
  POST /tool/check_caller   -> {"decision": "pass"|"block"}
  POST /webhook/elevenlabs  -> 200 always once the signature is valid
"""
import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request

from backend import db
from backend.normalize import extract_caller_number, normalize_transcript, tool_fields_to_transcript
from backend.photon_send import send_imessage
from scorer.score import ScorerError, decide, score_call

load_dotenv()
log = logging.getLogger("backend")
app = FastAPI(title="Scam call screener")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/tool/check_caller")
async def check_caller(request: Request, x_tool_secret: str = Header(default="")) -> dict:
    expected = os.getenv("TOOL_SHARED_SECRET", "")
    if not expected or x_tool_secret != expected:
        raise HTTPException(status_code=401, detail="bad secret")
    body = await request.json()
    conversation_id = body.get("conversation_id") or "unknown"
    try:
        result = score_call(body.get("caller_number", ""), tool_fields_to_transcript(body))
        decision = decide(result)
    except ScorerError:
        decision = "block"
    # STUB override so Ian can test the transfer: set STUB_DECISION=pass. Remove when real.
    decision = os.getenv("STUB_DECISION", decision) if os.getenv("STUB_DECISION") else decision
    db.upsert_call(conversation_id, {"caller_number": body.get("caller_number"), "mid_call_decision": decision})
    return {"decision": decision}


@app.post("/webhook/elevenlabs")
async def elevenlabs_webhook(request: Request) -> dict:
    # STUB: signature check (ElevenLabs-Signature, ELEVENLABS_WEBHOOK_SECRET) goes here.
    raw = await request.body()
    path = os.getenv("RAW_WEBHOOK_PATH", "samples/last_webhook_raw.json")
    try:
        with open(path, "wb") as f:
            f.write(raw)  # lets Ian capture the first real payload
    except OSError:
        log.warning("could not save raw webhook")
    payload = json.loads(raw or b"{}")
    data = payload.get("data") or payload
    conversation_id = data.get("conversation_id")
    if not conversation_id:
        return {"ok": True, "note": "no conversation_id"}
    existing = db.get_call(conversation_id)
    if existing and existing.get("status") == "scored":
        return {"ok": True, "note": "duplicate"}
    number = extract_caller_number(payload) or ""
    transcript = normalize_transcript(data.get("transcript"))
    db.upsert_call(conversation_id, {"caller_number": number, "transcript": transcript})
    try:
        result = score_call(number, transcript)
        db.mark_scored(conversation_id, result)
        send_imessage(os.getenv("OWNER_PHONE", ""), f"{result['verdict']} ({result['scam_score']}): {result['summary']}")
    except ScorerError:
        db.upsert_call(conversation_id, {"status": "pending"})
        send_imessage(os.getenv("OWNER_PHONE", ""), "Call received, review needed.")
    return {"ok": True}
