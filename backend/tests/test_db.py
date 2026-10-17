"""Tests for backend/db.py. Run against the real Supabase project.

    pytest backend/tests/test_db.py -v

Needs SUPABASE_URL and SUPABASE_SERVICE_KEY in .env. Every test uses a unique
'pytest_...' conversation_id and deletes its rows afterwards, so the seed data
and real calls are never touched.
"""
import os
import uuid

import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY")),
    reason="SUPABASE_URL / SUPABASE_SERVICE_KEY not set",
)

from backend import db  # noqa: E402


@pytest.fixture
def cid():
    """A fresh conversation_id that is removed after the test."""
    conversation_id = f"pytest_{uuid.uuid4().hex[:12]}"
    yield conversation_id
    db._get_client().table(db.TABLE).delete().eq(
        "conversation_id", conversation_id
    ).execute()


def test_get_missing_returns_none():
    assert db.get_call(f"pytest_missing_{uuid.uuid4().hex[:8]}") is None


def test_insert_uses_defaults(cid):
    row = db.upsert_call(cid, {"caller_number": "+15551230001"})
    assert row["conversation_id"] == cid
    assert row["caller_number"] == "+15551230001"
    assert row["status"] == "pending"
    assert row["imessage_sent"] is False


def test_partial_update_keeps_other_fields(cid):
    """Mid-call write then post-call write must not wipe each other."""
    db.upsert_call(cid, {"caller_number": "+15551230002", "mid_call_decision": "block"})
    transcript = [
        {"role": "agent", "text": "Who's calling and why?"},
        {"role": "caller", "text": "This is your bank."},
    ]
    db.upsert_call(cid, {"transcript": transcript})
    row = db.get_call(cid)
    assert row["caller_number"] == "+15551230002"
    assert row["mid_call_decision"] == "block"
    assert row["transcript"] == transcript


def test_mark_scored(cid):
    db.upsert_call(cid, {"caller_number": "+15551230003"})
    row = db.mark_scored(
        cid,
        {
            "verdict": "scam",
            "scam_score": 91,
            "reasons": ["Asked for gift cards"],
            "tactics": ["urgency", "impersonation"],
            "summary": "Caller posed as the IRS.",
        },
    )
    assert row["status"] == "scored"
    assert row["verdict"] == "scam"
    assert row["scam_score"] == 91
    assert row["caller_number"] == "+15551230003"
    assert db.get_call(cid)["tactics"] == ["urgency", "impersonation"]


def test_mark_scored_without_prior_row(cid):
    """Scoring a call we never saw mid-call should still create the row."""
    row = db.mark_scored(cid, {"verdict": "legit", "scam_score": 4})
    assert row["status"] == "scored"
    assert row["reasons"] == []
    assert row["summary"] == ""


def test_unknown_fields_are_ignored(cid):
    row = db.upsert_call(cid, {"caller_number": "+15551230004", "not_a_column": 1})
    assert row["caller_number"] == "+15551230004"
    assert "not_a_column" not in row


def test_check_constraint_rejects_bad_verdict(cid):
    with pytest.raises(Exception):
        db.upsert_call(cid, {"verdict": "maybe"})


def test_double_upsert_is_one_row(cid):
    db.upsert_call(cid, {"caller_number": "+15551230005"})
    db.upsert_call(cid, {"caller_number": "+15551230005"})
    resp = (
        db._get_client()
        .table(db.TABLE)
        .select("conversation_id")
        .eq("conversation_id", cid)
        .execute()
    )
    assert len(resp.data) == 1
