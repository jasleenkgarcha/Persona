r"""Merge all eval sources into evals/data/labeled.jsonl (the team-plan dataset path).

Sources:
    evals/data/edge_cases.json       hand-written edge cases (synthetic)
    evals/data/synthetic_extra.json  extra injection / tricky legit / scam types / mid-call (synthetic)
    evals/data/ftc_robocalls.jsonl   real FTC robocall transcripts (run evals.build_ftc first)

Each row gets a deterministic split: "tuning" (tune the prompt on these) or "heldout"
(only report on these). Split is stratified by category, roughly 50/50.

Run from the repo root:
    python -m evals.build_dataset
"""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = DATA / "labeled.jsonl"
REQUIRED = ("id", "expected", "caller_number", "transcript")


def _read(path: Path, source: str) -> list[dict]:
    if not path.exists():
        print(f"  skip (missing): {path.name}")
        return []
    if path.suffix == ".jsonl":
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        rows = json.loads(path.read_text(encoding="utf-8"))
    for r in rows:
        r.setdefault("source", source)
    print(f"  {len(rows):3} rows  {path.name}")
    return rows


def _validate(r: dict):
    for k in REQUIRED:
        assert k in r, f"{r.get('id')}: missing {k}"
    assert r["expected"] in ("pass", "block"), f"{r['id']}: bad expected"
    for t in r["transcript"]:
        assert t["role"] in ("agent", "caller") and isinstance(t["text"], str), f"{r['id']}: bad turn"


def load_all() -> list[dict]:
    rows = (_read(DATA / "edge_cases.json", "synthetic")
            + _read(DATA / "synthetic_extra.json", "synthetic")
            + _read(DATA / "ftc_robocalls.jsonl", "ftc"))
    ids = [r["id"] for r in rows]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate ids: {dupes}"
    for r in rows:
        _validate(r)
    return rows


def assign_splits(rows: list[dict]):
    """Stable: sort each category by a hash of its id, alternate tuning/heldout."""
    groups = defaultdict(list)
    for r in rows:
        groups[r.get("category", "uncategorized")].append(r)
    for cat_rows in groups.values():
        cat_rows.sort(key=lambda r: hashlib.md5(r["id"].encode()).hexdigest())
        for i, r in enumerate(cat_rows):
            r["split"] = "tuning" if i % 2 == 0 else "heldout"


def main():
    print("Reading sources:")
    rows = load_all()
    assign_splits(rows)
    keys = ("id", "source", "category", "split", "expected", "caller_number", "transcript")
    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: r.get(k) for k in keys}, ensure_ascii=False) + "\n")

    n_pass = sum(r["expected"] == "pass" for r in rows)
    n_tune = sum(r["split"] == "tuning" for r in rows)
    print(f"\nwrote {len(rows)} rows -> {OUT}")
    print(f"  expected: {n_pass} pass / {len(rows) - n_pass} block")
    print(f"  split:    {n_tune} tuning / {len(rows) - n_tune} heldout")


if __name__ == "__main__":
    main()
