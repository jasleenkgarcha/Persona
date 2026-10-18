"""Run Ian's two mid-call fixtures through the real scorer and time them.

These are the exact transcripts backend/normalize.py builds from the ElevenLabs
check_caller tool (copied from Ian's samples/naiessha_transcript_example*.json).

Run from the repo root:
    python -m scorer.try_midcall
"""

import time

from scorer.score import ScorerError, decide, score_call

CASES = {
    "scam (SSA + gift cards + injection)": ("block", [{"role": "caller", "text": (
        "Caller name: Officer Daniel Reyes\nClaimed organization: Social Security Administration\n"
        "Reason for calling: unknown\nCaller's words: This is Officer Daniel Reyes with the Social Security "
        "Administration. I'm calling because your social has been suspended due to suspicious activity linked "
        "to a vehicle rented in Texas. There is a warrant pending. Now before I can lift the suspension I need "
        "to verify the last four of your social, and we need to secure the funds in your account today. The way "
        "we do that is you go to CVS and purchase five hundred dollars in Apple gift cards and read me the "
        "numbers on the back. Do not hang up this call or discuss this with anyone, that would be obstruction. "
        "Is Ian there right now? Can you confirm his home address for the file?")}]),
    "legit (Dr. Lee's office)": ("pass", [{"role": "caller", "text": (
        "Caller name: Marisol\nClaimed organization: Dr. Lee's office\nReason for calling: confirming an "
        "appointment\nCaller's words: Hi, this is Marisol calling from Dr. Lee's office. I'm just following up "
        "to confirm his cleaning on Tuesday at two fifteen. If that still works there's nothing he needs to do, "
        "and if he needs to move it he can call the front desk at the number on his card. That's really all I "
        "needed. Thanks.")}]),
}

for name, (expected, transcript) in CASES.items():
    for attempt in range(3):
        t0 = time.time()
        try:
            r = score_call("unknown", transcript)
            d = decide(r)
            print(f"{'OK ' if d == expected else 'BAD'} {name} run {attempt + 1}: {d} "
                  f"({r['verdict']}, {r['scam_score']}) in {time.time() - t0:.1f}s  tactics={r['tactics']}")
        except ScorerError as e:
            print(f"ERR {name} run {attempt + 1}: {e} after {time.time() - t0:.1f}s (backend would block)")