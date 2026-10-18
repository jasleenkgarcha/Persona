"""Tests for the two endpoints in backend/main.py.

No internet or Supabase needed: the database, the scorer and the text sender are
replaced with fakes. Run:  pytest backend\\tests\\test_endpoints.py -v
"""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import db, main

TOOL_SECRET = "tool-secret"
HOOK_SECRET = "hook-secret"
OWNER = "+15550001111"


class FakeDB:
    def __init__(self):
        self.rows = {}

    def upsert_call(self, conversation_id, fields):
        row = self.rows.setdefault(
            conversation_id,
            {"conversation_id": conversation_id, "status": "pending", "imessage_sent": False},
        )
        row.update(fields)
        return dict(row)

    def get_call(self, conversation_id):
        row = self.rows.get(conversation_id)
        return dict(row) if row else None

    def mark_scored(self, conversation_id, result):
        return self.upsert_call(
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


LEGIT = {"verdict": "legit", "scam_score": 5, "reasons": ["ok"], "tactics": [], "summary": "Dentist."}
SCAM = {"verdict": "scam", "scam_score": 95, "reasons": ["gift cards"], "tactics": ["urgency"], "summary": "IRS scam."}


def fake_decide(result):
    return "pass" if result["verdict"] == "legit" and result["scam_score"] <= 25 else "block"


@pytest.fixture
def env(monkeypatch, tmp_path):
    fake = FakeDB()
    texts = []
    scorer_calls = []
    state = SimpleNamespace(result=LEGIT, error=None)

    def fake_score(number, transcript):
        scorer_calls.append((number, transcript))
        if state.error:
            raise state.error
        return state.result

    monkeypatch.setattr(db, "upsert_call", fake.upsert_call)
    monkeypatch.setattr(db, "get_call", fake.get_call)
    monkeypatch.setattr(db, "mark_scored", fake.mark_scored)
    monkeypatch.setattr(main, "score_call", fake_score)
    monkeypatch.setattr(main, "decide", fake_decide)
    monkeypatch.setattr(main, "send_imessage", lambda to, text: texts.append((to, text)) or True)
    monkeypatch.setenv("TOOL_SHARED_SECRET", TOOL_SECRET)
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", HOOK_SECRET)
    monkeypatch.setenv("OWNER_PHONE", OWNER)
    monkeypatch.setenv("RAW_WEBHOOK_PATH", str(tmp_path / "raw.json"))
    monkeypatch.delenv("STUB_DECISION", raising=False)
    monkeypatch.delenv("ALLOW_UNSIGNED_WEBHOOK", raising=False)
    return SimpleNamespace(
        db=fake, texts=texts, scorer_calls=scorer_calls, state=state, client=TestClient(main.app)
    )


# ----------------------------------------------------------------- helpers


def tool_post(env, body=None, secret=TOOL_SECRET):
    headers = {"X-Tool-Secret": secret} if secret is not None else {}
    return env.client.post(
        "/tool/check_caller",
        json=body or {"conversation_id": "c1", "caller_number": "+15551230000", "reason": "appointment"},
        headers=headers,
    )


def call_payload(conversation_id="c1", number="+15551230000", event_type="post_call_transcription"):
    data = {
        "conversation_id": conversation_id,
        "transcript": [
            {"role": "agent", "message": "Who's calling and why?"},
            {"role": "user", "message": "This is Dr. Lee's office."},
            {"role": "tool", "message": "check_caller()"},
        ],
    }
    if number:
        data["conversation_initiation_client_data"] = {"dynamic_variables": {"system__caller_id": number}}
    return {"type": event_type, "data": data}


def signature(raw, secret=HOOK_SECRET, ts=None):
    ts = int(time.time()) if ts is None else ts
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return f"t={ts},v0={digest}"


def hook_post(env, payload, secret=HOOK_SECRET, ts=None, header=None):
    raw = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    headers["ElevenLabs-Signature"] = header if header is not None else signature(raw, secret, ts)
    return env.client.post("/webhook/elevenlabs", content=raw, headers=headers)


# ------------------------------------------------------------- /tool/check_caller


def test_health(env):
    assert env.client.get("/health").json() == {"ok": True}


def test_check_caller_rejects_bad_secret(env):
    assert tool_post(env, secret="wrong").status_code == 401
    assert tool_post(env, secret=None).status_code == 401
    assert env.db.rows == {}


def test_check_caller_passes_legit_and_saves(env):
    r = tool_post(env)
    assert r.json() == {"decision": "pass"}
    row = env.db.rows["c1"]
    assert row["mid_call_decision"] == "pass"
    assert row["caller_number"] == "+15551230000"


def test_check_caller_blocks_scam(env):
    env.state.result = SCAM
    assert tool_post(env).json() == {"decision": "block"}


def test_check_caller_blocks_when_scorer_errors(env):
    env.state.error = RuntimeError("bad output")
    assert tool_post(env).json() == {"decision": "block"}
    assert env.db.rows["c1"]["mid_call_decision"] == "block"


def test_check_caller_blocks_on_scorer_timeout(env):
    env.state.error = TimeoutError()
    assert tool_post(env).json() == {"decision": "block"}


def test_check_caller_still_answers_if_database_is_down(env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "upsert_call", boom)
    assert tool_post(env).json() == {"decision": "pass"}


def test_check_caller_handles_garbage_body(env):
    r = env.client.post(
        "/tool/check_caller", content=b"not json", headers={"X-Tool-Secret": TOOL_SECRET}
    )
    assert r.status_code == 200
    assert r.json()["decision"] in ("pass", "block")


def test_stub_decision_override(env, monkeypatch):
    env.state.result = SCAM
    monkeypatch.setenv("STUB_DECISION", "pass")
    assert tool_post(env).json() == {"decision": "pass"}
    monkeypatch.setenv("STUB_DECISION", "banana")  # ignored
    assert tool_post(env).json() == {"decision": "block"}


# -------------------------------------------------------- /webhook/elevenlabs


def test_webhook_rejects_bad_signature(env):
    assert hook_post(env, call_payload(), secret="wrong").status_code == 401
    assert env.db.rows == {}
    assert env.texts == []


def test_webhook_rejects_missing_or_garbled_signature(env):
    assert hook_post(env, call_payload(), header="").status_code == 401
    assert hook_post(env, call_payload(), header="garbage").status_code == 401
    assert hook_post(env, call_payload(), header="t=abc,v0=123").status_code == 401


def test_webhook_rejects_old_timestamp(env):
    old = int(time.time()) - 31 * 60
    assert hook_post(env, call_payload(), ts=old).status_code == 401


def test_webhook_without_secret_fails_closed(env, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_WEBHOOK_SECRET")
    assert hook_post(env, call_payload()).status_code == 401
    monkeypatch.setenv("ALLOW_UNSIGNED_WEBHOOK", "1")
    assert hook_post(env, call_payload()).status_code == 200


def test_webhook_scores_saves_and_texts(env):
    r = hook_post(env, call_payload())
    assert r.status_code == 200
    row = env.db.rows["c1"]
    assert row["status"] == "scored"
    assert row["verdict"] == "legit"
    assert row["caller_number"] == "+15551230000"
    assert row["transcript"] == [
        {"role": "agent", "text": "Who's calling and why?"},
        {"role": "caller", "text": "This is Dr. Lee's office."},
    ]
    assert row["imessage_sent"] is True
    assert env.texts == [(OWNER, "legit (5): Dentist.")]


def test_webhook_duplicate_is_ignored(env):
    hook_post(env, call_payload())
    r = hook_post(env, call_payload())
    assert r.status_code == 200
    assert r.json()["note"] == "duplicate"
    assert len(env.scorer_calls) == 1
    assert len(env.texts) == 1


def test_webhook_scorer_failure_saves_pending_and_sends_fallback(env):
    env.state.error = RuntimeError("bad output")
    r = hook_post(env, call_payload())
    assert r.status_code == 200
    assert env.db.rows["c1"]["status"] == "pending"
    assert env.db.rows["c1"]["transcript"]  # transcript still saved
    assert env.texts == [(OWNER, "Call received, review needed.")]


def test_webhook_scorer_timeout_same_as_failure(env):
    env.state.error = TimeoutError()
    assert hook_post(env, call_payload()).status_code == 200
    assert env.db.rows["c1"]["status"] == "pending"
    assert env.texts == [(OWNER, "Call received, review needed.")]


def test_webhook_pending_call_can_be_scored_on_retry(env):
    env.state.error = RuntimeError("bad output")
    hook_post(env, call_payload())
    env.state.error = None
    hook_post(env, call_payload())
    assert env.db.rows["c1"]["status"] == "scored"


def test_webhook_ignores_other_event_types(env):
    r = hook_post(env, call_payload(event_type="post_call_audio"))
    assert r.status_code == 200
    assert env.db.rows == {}
    assert env.texts == []


def test_webhook_keeps_mid_call_number_when_payload_has_none(env):
    env.db.upsert_call("c1", {"caller_number": "+15559998888", "mid_call_decision": "pass"})
    hook_post(env, call_payload(number=None))
    assert env.scorer_calls[0][0] == "+15559998888"
    row = env.db.rows["c1"]
    assert row["caller_number"] == "+15559998888"
    assert row["mid_call_decision"] == "pass"


def test_webhook_returns_200_even_if_database_breaks(env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "upsert_call", boom)
    assert hook_post(env, call_payload()).status_code == 200


def test_webhook_text_failure_does_not_break_scoring(env, monkeypatch):
    def boom(to, text):
        raise RuntimeError("photon down")

    monkeypatch.setattr(main, "send_imessage", boom)
    assert hook_post(env, call_payload()).status_code == 200
    row = env.db.rows["c1"]
    assert row["status"] == "scored"
    assert row["imessage_sent"] is False


def test_webhook_garbage_body_with_valid_signature(env):
    raw = b"not json at all"
    r = env.client.post(
        "/webhook/elevenlabs", content=raw, headers={"ElevenLabs-Signature": signature(raw)}
    )
    assert r.status_code == 200
