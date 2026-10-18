r"""Local eval harness (the fallback if Chalk Evals isn't available). Same dataset, same metrics.

Calls the real scorer through the Chalk AI Gateway, runs the keyword baseline on the same rows,
and writes evals/results.json (team contract) plus a copy in evals/runs/.

Run from the repo root (after: python -m evals.build_ftc ; python -m evals.build_dataset):
    python -m evals.run_local --split tuning                       # iterate on the prompt here
    python -m evals.run_local --split heldout --repeat 3           # the number you report
    python -m evals.run_local --split tuning --prompt-file evals\prompts\v2.txt --label v2

--prompt-file swaps the system prompt for this run only (score.py is not changed), so you can
compare prompt v1 vs v2. The threshold sweep re-applies decide() at different MAX_PASS_SCORE
values using the stored results, with no extra model calls. Use it to pick the cutoff.
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from scorer import config
from scorer import score as scorer_mod
from evals.keyword_baseline import keyword_decide
from evals.metrics import flip_rate, misses, summarize

EVALS = Path(__file__).parent
DATASET = EVALS / "data" / "labeled.jsonl"


def load(split: str) -> list[dict]:
    rows = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows if split == "all" else [r for r in rows if r["split"] == split]


def run_one(row: dict) -> dict:
    rec = {k: row.get(k) for k in ("id", "category", "source", "split", "expected")}
    t0 = time.time()
    try:
        result = scorer_mod.score_call(row["caller_number"], row["transcript"])
        rec.update(decision=scorer_mod.decide(result), verdict=result["verdict"],
                   scam_score=result["scam_score"], tactics=result["tactics"], reasons=result["reasons"])
    except scorer_mod.ScorerError as e:
        rec.update(decision="error", error=str(e))
    rec["seconds"] = round(time.time() - t0, 2)
    return rec


def decide_at(rec: dict, cutoff: int) -> str:
    if rec["decision"] == "error":
        return "error"
    if rec["verdict"] != "legit" or rec["scam_score"] > cutoff:
        return "block"
    if scorer_mod.HARD_BLOCK_TACTICS.intersection(rec.get("tactics", [])):
        return "block"
    return "pass"


def threshold_sweep(records: list[dict]) -> list[dict]:
    out = []
    for cutoff in (10, 15, 20, 25, 30, 40, 50, 60):
        s = summarize([{**r, "decision": decide_at(r, cutoff)} for r in records])
        out.append({"max_pass_score": cutoff, "accuracy": s["accuracy"],
                    "false_positive_rate": s["false_positive_rate"],
                    "false_negative_rate": s["false_negative_rate"]})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=["tuning", "heldout", "all"], default="tuning")
    p.add_argument("--repeat", type=int, default=1, help="runs per case (3 for reported numbers)")
    p.add_argument("--workers", type=int, default=4, help="parallel calls; lower it if rate-limited")
    p.add_argument("--prompt-file", help="use this system prompt instead of the one in score.py")
    p.add_argument("--label", default="v1", help="name for this prompt version, e.g. v1, v2")
    p.add_argument("--limit", type=int, help="only the first N rows (quick smoke test)")
    p.add_argument("--no-results", action="store_true", help="don't overwrite evals/results.json")
    args = p.parse_args()

    if args.prompt_file:
        scorer_mod.SYSTEM_PROMPT = Path(args.prompt_file).read_text(encoding="utf-8")
    rows = load(args.split)[: args.limit]
    jobs = [r for r in rows for _ in range(args.repeat)]
    print(f"{len(rows)} cases x {args.repeat} = {len(jobs)} runs | split={args.split} "
          f"prompt={args.label} model={config.SCORER_MODEL}")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = []
        for i, rec in enumerate(pool.map(run_one, jobs), 1):
            records.append(rec)
            mark = "OK " if (rec["decision"] if rec["decision"] != "error" else "block") == rec["expected"] else "BAD"
            if mark == "BAD" or i % 10 == 0:
                print(f"  [{i}/{len(jobs)}] {mark} {rec['id']}: {rec['decision']} (expected {rec['expected']})")

    baseline = [{**{k: r.get(k) for k in ("id", "category", "source", "split", "expected")},
                 "decision": keyword_decide(r["transcript"])} for r in rows]
    s, b = summarize(records), summarize(baseline)
    fr, flipped = flip_rate(records)

    results = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": config.SCORER_MODEL,
        "n_total": s["n_total"],
        "accuracy": s["accuracy"],
        "false_positive_rate": s["false_positive_rate"],
        "false_negative_rate": s["false_negative_rate"],
        "misses": misses(records),
        # extras (allowed by the contract)
        "split": args.split,
        "prompt_version": args.label,
        "repeats": args.repeat,
        "n_cases": len(rows),
        "max_pass_score": config.MAX_PASS_SCORE,
        "n_errors": s["n_errors"],
        "flip_rate": fr,
        "flipped_cases": flipped,
        "avg_seconds_per_call": round(sum(r["seconds"] for r in records) / max(len(records), 1), 2),
        "by_category": s["by_category"],
        "by_source": s["by_source"],
        "baseline_keyword": {k: b[k] for k in ("accuracy", "false_positive_rate", "false_negative_rate")},
        "threshold_sweep": threshold_sweep(records),
        "eval_runner": "local",
    }

    runs_dir = EVALS / "runs"
    runs_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%m%d_%H%M")
    (runs_dir / f"{args.label}_{args.split}_{stamp}.json").write_text(json.dumps(
        {**results, "records": records}, indent=2, ensure_ascii=False), encoding="utf-8")
    if not args.no_results:
        (EVALS / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n=== {args.label} on {args.split} ({time.time() - t0:.0f}s) ===")
    print(f"                 scorer   keyword baseline")
    print(f"accuracy         {s['accuracy']:.0%}      {b['accuracy']:.0%}")
    print(f"false alarms     {s['false_positive_rate']:.0%}      {b['false_positive_rate']:.0%}   (legit calls blocked)")
    print(f"missed scams     {s['false_negative_rate']:.0%}      {b['false_negative_rate']:.0%}   (scams passed)")
    print(f"errors {s['n_errors']} | flip rate {fr:.0%} {flipped if flipped else ''}")
    print("\nBy category:")
    for cat, v in s["by_category"].items():
        print(f"  {cat:20} {v['correct']}/{v['total']}")
    print("\nMAX_PASS_SCORE sweep (acc / false alarms / missed):")
    for t in results["threshold_sweep"]:
        print(f"  {t['max_pass_score']:3}  {t['accuracy']:.0%} / {t['false_positive_rate']:.0%} / {t['false_negative_rate']:.0%}")
    print(f"\nsaved runs/{args.label}_{args.split}_{stamp}.json"
          + ("" if args.no_results else " and results.json"))


if __name__ == "__main__":
    main()
