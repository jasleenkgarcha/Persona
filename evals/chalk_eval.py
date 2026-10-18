r"""Run the scam-scorer evals on Chalk Agent Evals (datasets, tasks, scorers, runs, Evaluations page).

What it does:
  1. Uploads evals/data/labeled.jsonl to Chalk as two datasets: scam-calls-tuning and scam-calls-heldout.
  2. Deploys a TASK (`screen_call`) that runs our real scorer (score_call + decide) inside Chalk,
     calling GPT through the same Chalk AI Gateway. It also deploys the keyword baseline as a second task.
  3. Deploys SCORERS: built-in json_match on "decision", json_valid, and our own `screen_outcome`
     (labels every row true_block / true_pass / false_alarm / missed_scam).
  4. Creates evaluations in one suite ("scam-screener") and runs each one N times (metadata: prompt, split).
  5. Reads the result dataset back, computes the same metrics as run_local, and writes evals/results.json.

Compare runs, view charts and per-row traces at chalk.ai, under Evaluations.

Setup (once; needs Chalk Compute credentials for YOUR project/env, separate from the router key):
  PowerShell:
      $env:CHALK_CLIENT_ID="..."; $env:CHALK_CLIENT_SECRET="..."; $env:CHALK_ENVIRONMENT_ID="nssh424679a9"
  (or run `chalk login` inside WSL). CHALK_API_KEY etc. come from .env and are sent as a Chalk Secret,
  never written into the image.

Run from the repo root:
    python -m evals.chalk_eval --split tuning --repeat 1      # smoke test
    python -m evals.chalk_eval --split heldout --repeat 3     # reported numbers -> results.json

If Chalk evals don't work in our env (no function queue, the router can't be reached from inside Chalk),
use `python -m evals.run_local`. Same dataset, same metrics.
"""

import json
from pathlib import Path

import chalkcompute
from chalkcompute import scorers
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Module scope: Chalk's worker imports this file, so the tasks/scorers must live here.
# ---------------------------------------------------------------------------

IMAGE = (
    chalkcompute.Image.debian_slim(python_version="3.12")
    .pip_install(["openai", "pydantic", "python-dotenv"])
    .add_local_python_source("scorer", "evals")
)

ROUTER_ENV = {
    "CHALK_API_KEY": chalkcompute.Secret.from_local_env("CHALK_API_KEY"),  # secret, never baked in
    "CHALK_ROUTER_URL": "https://api.chalk.ai/v1/router",
    "CHALK_ENV_ID": "clkdcdaf84e",
    "SCORER_MODEL": "openai/gpt-6.1-sol",
}


@chalkcompute.function(image=IMAGE, env=ROUTER_ENV, call_timeout=90.0)
def screen_call(caller_number: str, transcript_json: str) -> str:
    """TASK: our live scorer, unchanged. Returns JSON so json_match can read 'decision'."""
    from scorer.score import ScorerError, decide, score_call

    try:
        result = score_call(caller_number, json.loads(transcript_json))
        return json.dumps({"decision": decide(result), "verdict": result["verdict"],
                           "scam_score": result["scam_score"], "tactics": result["tactics"],
                           "reasons": result["reasons"]})
    except ScorerError as e:
        # backend blocks on scorer failure, so the eval does too
        return json.dumps({"decision": "block", "verdict": "error", "error": str(e)})


@chalkcompute.function(image=IMAGE, call_timeout=30.0)
def keyword_screen(transcript_json: str) -> str:
    """BASELINE TASK: keyword rules only, no LLM."""
    from evals.keyword_baseline import keyword_decide

    return json.dumps({"decision": keyword_decide(json.loads(transcript_json))})


@chalkcompute.function(image=IMAGE, call_timeout=30.0)
def screen_outcome(output: str, expected_decision: str) -> chalkcompute.EvaluationScorerResult:
    """CUSTOM SCORER: 1.0 if correct. Metadata says which kind of right/wrong (for the dashboard filters)."""
    try:
        got = json.loads(output).get("decision", "block")
    except Exception:
        got = "block"
    outcome = {("block", "block"): "true_block", ("pass", "pass"): "true_pass",
               ("block", "pass"): "false_alarm", ("pass", "block"): "missed_scam"}[(got, expected_decision)]
    return chalkcompute.EvaluationScorerResult(
        score=1.0 if got == expected_decision else 0.0,
        metadata={"outcome": outcome, "false_alarm": outcome == "false_alarm",
                  "missed_scam": outcome == "missed_scam"},
    )


DECISION_MATCH = scorers.json_match(name="decision-match", inputs=("output", "expected"), paths=["decision"])
VALID_JSON = scorers.json_valid(name="valid-json", inputs=("output",))


# ---------------------------------------------------------------------------
# Script part: only runs on your laptop.
# ---------------------------------------------------------------------------

def _dataset_rows(split: str) -> list[dict]:
    path = Path(__file__).parent / "data" / "labeled.jsonl"
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [{
        "id": r["id"], "category": r["category"], "source": r["source"], "split": r["split"],
        "caller_number": r["caller_number"] or "unknown",
        "transcript_json": json.dumps(r["transcript"], ensure_ascii=False),
        "expected": json.dumps({"decision": r["expected"]}),   # for json_match
        "expected_decision": r["expected"],                     # for screen_outcome
    } for r in rows if r["split"] == split]


def _get_suite(name: str):
    for s in chalkcompute.EvaluationSuite.list_all():
        if s.name == name:
            return s
    return chalkcompute.EvaluationSuite.create(name)


def _records_from_results(run, uploaded: list[dict]) -> list[dict]:
    table = chalkcompute.DatasetClient().read(run.result_dataset)
    out_rows = table.to_pylist() if hasattr(table, "to_pylist") else list(table)
    by_id = {r["id"]: r for r in uploaded}
    records = []
    for i, row in enumerate(out_rows):
        src = by_id.get(row.get("id")) or uploaded[i]
        try:
            o = json.loads(row.get("output") or "{}")
        except Exception:
            o = {}
        decision = o.get("decision", "error") if o.get("verdict") != "error" else "error"
        records.append({"id": src["id"], "category": src["category"], "source": src["source"],
                        "split": src["split"], "expected": src["expected_decision"],
                        "decision": decision, "verdict": o.get("verdict"),
                        "scam_score": o.get("scam_score"), "tactics": o.get("tactics", []),
                        "reasons": o.get("reasons", []), "seconds": 0})
    return records


def main():
    import argparse
    from datetime import datetime, timezone

    from evals.metrics import flip_rate, misses, summarize
    from evals.run_local import threshold_sweep
    from scorer import config

    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=["tuning", "heldout"], default="tuning")
    p.add_argument("--repeat", type=int, default=3)
    p.add_argument("--label", default="v1", help="prompt version, stored as run metadata")
    p.add_argument("--no-baseline", action="store_true")
    p.add_argument("--no-results", action="store_true")
    args = p.parse_args()

    rows = _dataset_rows(args.split)
    print(f"Uploading {len(rows)} rows as dataset scam-calls-{args.split} ...")
    dataset = chalkcompute.DatasetClient().upload(f"scam-calls-{args.split}", rows)
    suite = _get_suite("scam-screener")

    ev = chalkcompute.Evaluation.create(
        f"scorer-{args.label}-{args.split}", dataset=dataset, task=screen_call,
        scorers=[DECISION_MATCH, VALID_JSON, screen_outcome],
        metadata={"prompt": args.label, "split": args.split, "model": config.SCORER_MODEL},
        suite_id=suite.id,
    )
    records = []
    for i in range(args.repeat):
        print(f"Run {i + 1}/{args.repeat} ...")
        run = ev.run(metadata={"prompt": args.label, "split": args.split, "repeat": i + 1})
        run.wait(timeout=900.0)
        records += _records_from_results(run, rows)

    baseline = None
    if not args.no_baseline:
        bev = chalkcompute.Evaluation.create(
            f"keyword-baseline-{args.split}", dataset=dataset, task=keyword_screen,
            scorers=[DECISION_MATCH, screen_outcome],
            metadata={"prompt": "keyword-baseline", "split": args.split}, suite_id=suite.id,
        )
        brun = bev.run(metadata={"prompt": "keyword-baseline", "split": args.split})
        brun.wait(timeout=600.0)
        baseline = summarize(_records_from_results(brun, rows))

    s = summarize(records)
    fr, flipped = flip_rate(records)
    results = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": config.SCORER_MODEL,
        "n_total": s["n_total"],
        "accuracy": s["accuracy"],
        "false_positive_rate": s["false_positive_rate"],
        "false_negative_rate": s["false_negative_rate"],
        "misses": misses(records),
        "split": args.split, "prompt_version": args.label, "repeats": args.repeat,
        "n_cases": len(rows), "max_pass_score": config.MAX_PASS_SCORE,
        "n_errors": s["n_errors"], "flip_rate": flip_rate(records)[0], "flipped_cases": flipped,
        "by_category": s["by_category"], "by_source": s["by_source"],
        "baseline_keyword": ({k: baseline[k] for k in ("accuracy", "false_positive_rate", "false_negative_rate")}
                             if baseline else None),
        "threshold_sweep": threshold_sweep(records),
        "eval_runner": "chalk",
        "chalk_suite": "scam-screener",
    }
    if not args.no_results:
        Path(__file__).parent.joinpath("results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\naccuracy {s['accuracy']:.0%} | false alarms {s['false_positive_rate']:.0%} | "
          f"missed scams {s['false_negative_rate']:.0%} | flip rate {fr:.0%}")
    if baseline:
        print(f"keyword baseline: accuracy {baseline['accuracy']:.0%} | false alarms "
              f"{baseline['false_positive_rate']:.0%} | missed {baseline['false_negative_rate']:.0%}")
    print("Open chalk.ai, then Evaluations, then the scam-screener suite to compare runs and see traces.")


if __name__ == "__main__":
    main()
