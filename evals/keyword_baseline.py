"""Keyword baseline: the 'dumb' screener we compare the LLM scorer against.

Blocks if the caller says any classic scam phrase, otherwise passes.
This is roughly what a rules-only call filter does. If the LLM can't beat this, it isn't earning its keep.
"""

import re

SCAM_PATTERNS = [
    r"gift ?cards?", r"prepaid card", r"wire (transfer|money|it)", r"western union", r"bitcoin", r"crypto",
    r"\bzelle\b", r"\bcode\b", r"\botp\b", r"\bpin\b", r"password", r"social security", r"\bssn\b",
    r"medicare number", r"card number", r"warrant", r"arrest", r"suspended", r"press (1|one|2|two)",
    r"anydesk", r"teamviewer", r"remote(ly)? access", r"\bwon\b", r"winner", r"sweepstakes", r"lottery", r"\bprize\b",
    r"guaranteed", r"final notice", r"extended warranty", r"disconnected", r"don'?t (tell|mention)",
    r"keep this between", r"processing fee", r"release fee", r"\bkyc\b", r"override", r"ignore (your|the|apne)",
    r"system administrator", r"note to the ai", r"verify (her|your) (identity|account)", r"safe account",
]
_RX = re.compile("|".join(SCAM_PATTERNS), re.IGNORECASE)


def keyword_decide(transcript: list[dict]) -> str:
    caller_text = " ".join(t["text"] for t in transcript if t["role"] == "caller")
    if len(caller_text.split()) < 4:
        return "block"  # same 'too little info' rule as the real scorer
    return "block" if _RX.search(caller_text) else "pass"
