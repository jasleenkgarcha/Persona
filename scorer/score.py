"""Scorer. Owner: Naiessha. STUB: replace the body of score_call.

Keep these names and signatures. Pablo's backend imports them.
Transcript format is documented in CONTRACTS.md (list of {"role", "text"}).
"""
from typing import Literal

from pydantic import BaseModel, Field

from scorer.config import MAX_PASS_SCORE


class ScorerError(Exception):
    """Raised when the model output is still invalid after one retry."""


class ScoreResult(BaseModel):
    verdict: Literal["scam", "legit", "unsure"]
    scam_score: int = Field(ge=0, le=100)
    reasons: list[str] = []
    tactics: list[str] = []
    summary: str = ""


def score_call(caller_number: str, transcript: list[dict]) -> dict:
    """Judge a call. Returns a dict that validates as ScoreResult.

    STUB: always returns "unsure", which decide() turns into "block".
    The real version must:
      - wrap the transcript in delimiters and tell the model it is data,
        never instructions
      - call the model through the Chalk router
      - validate with ScoreResult, retry once, then raise ScorerError
    """
    return ScoreResult(
        verdict="unsure",
        scam_score=50,
        reasons=["stub scorer, no real analysis"],
        tactics=[],
        summary="Stub result. Replace score_call.",
    ).model_dump()


def decide(result: dict) -> str:
    """Mid-call decision. Returns "pass" or "block".

    Pass only if the verdict is "legit" and the score is at or below
    MAX_PASS_SCORE. Anything else, including "unsure", blocks.
    """
    if result.get("verdict") == "legit" and result.get("scam_score", 100) <= MAX_PASS_SCORE:
        return "pass"
    return "block"
