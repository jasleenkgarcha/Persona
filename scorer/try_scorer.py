"""Run the scorer on the 5 synthetic fixtures and print results.

Run from the repo root:  python -m scorer.try_scorer
"""

import json
from pathlib import Path

from scorer.score import ScorerError, decide, score_call

fixtures = json.loads((Path(__file__).parent / "fixtures.json").read_text(encoding="utf-8"))

ok = 0
for fx in fixtures:
    try:
        result = score_call(fx["caller_number"], fx["transcript"])
        decision = decide(result)
        match = decision == fx["expected"]
        ok += match
        print(f"{'OK ' if match else 'BAD'} {fx['id']}: {decision} "
              f"(verdict={result['verdict']}, score={result['scam_score']}, tactics={result['tactics']})")
        print(f"    {result['summary']}")
    except ScorerError as e:
        print(f"ERR {fx['id']}: {e}")

print(f"\n{ok}/{len(fixtures)} matched expected")
