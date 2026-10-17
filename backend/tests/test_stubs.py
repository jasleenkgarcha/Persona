from fastapi.testclient import TestClient

from backend import db
from backend.main import app
from backend.normalize import extract_caller_number, normalize_transcript
from backend.photon_send import send_imessage
from scorer.score import ScoreResult, decide, score_call

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"ok": True}


def test_scorer_stub_validates_and_blocks():
    result = score_call("+15550001111", [{"role": "caller", "text": "hi"}])
    ScoreResult(**result)
    assert decide(result) == "block"


def test_decide_pass_only_for_low_legit():
    assert decide({"verdict": "legit", "scam_score": 10}) == "pass"
    assert decide({"verdict": "legit", "scam_score": 90}) == "block"
    assert decide({"verdict": "unsure", "scam_score": 0}) == "block"


def test_normalize():
    raw = [{"role": "user", "message": "hi"}, {"role": "agent", "message": "hello"}, {"role": "tool", "message": "x"}]
    assert normalize_transcript(raw) == [{"role": "caller", "text": "hi"}, {"role": "agent", "text": "hello"}]


def test_caller_id_extraction():
    payload = {"data": {"conversation_initiation_client_data": {"dynamic_variables": {"system__caller_id": "+15551234567"}}}}
    assert extract_caller_number(payload) == "+15551234567"
    assert extract_caller_number({}) is None


def test_db_roundtrip():
    db.upsert_call("c1", {"caller_number": "+1"})
    assert db.get_call("c1")["caller_number"] == "+1"
    assert db.mark_scored("c1", {"verdict": "scam", "scam_score": 90})["status"] == "scored"


def test_send_imessage_stub():
    assert send_imessage("+1", "hi") is False


def test_check_caller_requires_secret(monkeypatch):
    monkeypatch.setenv("TOOL_SHARED_SECRET", "s3cret")
    assert client.post("/tool/check_caller", json={}).status_code == 401
    r = client.post("/tool/check_caller", json={"conversation_id": "t1"}, headers={"X-Tool-Secret": "s3cret"})
    assert r.json() == {"decision": "block"}
