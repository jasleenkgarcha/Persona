r"""Run the scorer on a file of test calls and report how it did.

Run from the repo root:
    python -m scorer.try_scorer                                   # the 5 built-in fixtures
    python -m scorer.try_scorer evals\data\edge_cases.json             # the edge-case suite
    python -m scorer.try_scorer evals\data\edge_cases.json --repeat 3  # each case 3x, checks consistency

Each case needs: id, expected ("pass" or "block"), caller_number, transcript.
Optional: category (used for the per-category summary).
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from scorer.score import ScorerError, decide, score_call

parser = argparse.ArgumentParser()
parser.add_argument("path", nargs="?", default=str(Path(__file__).parent / "fixtures.json"))
parser.add_argument("--repeat", type=int, default=1, help="run each case this many times")
args = parser.parse_args()

cases = json.loads(Path(args.path).read_text(encoding="utf-8"))
total_runs = correct_runs = errors = 0
false_alarms = missed_scams = 0
legit_runs = scam_runs = 0
flaky = []
by_category = defaultdict(lambda: [0, 0])  # category -> [correct, total]

for case in cases:
    decisions = []
    for _ in range(args.repeat):
        total_runs += 1
        cat = case.get("category", "uncategorized")
        by_category[cat][1] += 1
        if case["expected"] == "pass":
            legit_runs += 1
        else:
            scam_runs += 1
        try:
            result = score_call(case["caller_number"], case["transcript"])
        except ScorerError as e:
            errors += 1
            decisions.append("error")
            print(f"ERR {case['id']}: {e}")
            continue
        decision = decide(result)
        decisions.append(decision)
        ok = decision == case["expected"]
        correct_runs += ok
        by_category[cat][0] += ok
        if not ok and case["expected"] == "pass":
            false_alarms += 1
        if not ok and case["expected"] == "block":
            missed_scams += 1
        if not ok or args.repeat == 1:
            print(f"{'OK ' if ok else 'BAD'} {case['id']}: {decision} "
                  f"(expected {case['expected']}, verdict={result['verdict']}, "
                  f"score={result['scam_score']}, tactics={result['tactics']})")
            if not ok:
                print(f"    reasons: {result['reasons']}")
    if len(set(decisions)) > 1:
        flaky.append((case["id"], decisions))

print("\n=== Summary ===")
print(f"Correct:        {correct_runs}/{total_runs} runs ({100 * correct_runs / max(total_runs, 1):.0f}%)")
print(f"False alarms:   {false_alarms}/{legit_runs} legit runs blocked")
print(f"Missed scams:   {missed_scams}/{scam_runs} scam runs passed")
print(f"Errors:         {errors}")
print("\nBy category:")
for cat, (ok, n) in sorted(by_category.items()):
    print(f"  {cat:20} {ok}/{n}")
if args.repeat > 1:
    print(f"\nInconsistent across {args.repeat} runs: {len(flaky)} case(s)")
    for cid, ds in flaky:
        print(f"  {cid}: {ds}")
