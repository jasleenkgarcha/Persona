"""Turn a list of per-run records into the numbers that go in evals/results.json.

A record is: {"id", "category", "source", "split", "expected", "decision"}  (decision: pass|block|error)
Errors count as "block" for accuracy, because the backend blocks when the scorer fails.

Definitions (positive class = scam = "block"):
    false_positive_rate = legit runs that got blocked / legit runs      (false alarms)
    false_negative_rate = scam runs that got passed  / scam runs        (missed scams)
"""

from collections import defaultdict


def _effective(decision: str) -> str:
    return "block" if decision == "error" else decision


def summarize(records: list[dict]) -> dict:
    n = len(records)
    correct = sum(_effective(r["decision"]) == r["expected"] for r in records)
    legit = [r for r in records if r["expected"] == "pass"]
    scam = [r for r in records if r["expected"] == "block"]
    fp = sum(_effective(r["decision"]) == "block" for r in legit)
    fn = sum(_effective(r["decision"]) == "pass" for r in scam)

    def group(key):
        out = defaultdict(lambda: {"correct": 0, "total": 0})
        for r in records:
            g = out[r.get(key) or "unknown"]
            g["total"] += 1
            g["correct"] += _effective(r["decision"]) == r["expected"]
        return {k: {**v, "accuracy": round(v["correct"] / v["total"], 3)} for k, v in sorted(out.items())}

    return {
        "n_total": n,
        "accuracy": round(correct / n, 3) if n else 0.0,
        "false_positive_rate": round(fp / len(legit), 3) if legit else 0.0,
        "false_negative_rate": round(fn / len(scam), 3) if scam else 0.0,
        "n_legit": len(legit),
        "n_scam": len(scam),
        "n_errors": sum(r["decision"] == "error" for r in records),
        "by_category": group("category"),
        "by_source": group("source"),
    }


def flip_rate(records: list[dict]) -> tuple[float, list[str]]:
    """Share of cases whose decision changed across repeated runs (the model has no temperature control)."""
    by_id = defaultdict(set)
    for r in records:
        by_id[r["id"]].add(_effective(r["decision"]))
    flipped = sorted(i for i, ds in by_id.items() if len(ds) > 1)
    return (round(len(flipped) / len(by_id), 3) if by_id else 0.0), flipped


def misses(records: list[dict], limit: int = 25) -> list[dict]:
    """Wrong cases for the dashboard, one entry per case id (with how many runs were wrong)."""
    out = {}
    for r in records:
        if _effective(r["decision"]) == r["expected"]:
            continue
        m = out.setdefault(r["id"], {
            "id": r["id"], "category": r.get("category"), "source": r.get("source"),
            "expected": r["expected"], "got": _effective(r["decision"]),
            "verdict": r.get("verdict"), "scam_score": r.get("scam_score"),
            "reasons": r.get("reasons", []), "wrong_runs": 0,
        })
        m["wrong_runs"] += 1
    return sorted(out.values(), key=lambda m: -m["wrong_runs"])[:limit]
