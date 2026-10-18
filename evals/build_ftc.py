r"""Build evals/data/ftc_robocalls.jsonl from the public FTC/NCSU robocall dataset.

Source: github.com/wspr-ncsu/robocall-audio-dataset (metadata.csv, public domain).
These are real one-way robocalls the FTC took action against, so every row is expected "block".

Run from the repo root:
    python -m evals.build_ftc                      # downloads metadata.csv
    python -m evals.build_ftc --csv path\to\metadata.csv
"""

import argparse
import csv
import io
import json
import random
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/wspr-ncsu/robocall-audio-dataset/main/metadata.csv"
OUT = Path(__file__).parent / "data" / "ftc_robocalls.jsonl"
GREETING = "Hi, you've reached Margaret's line. May I ask who's calling and what it's about?"


def load_rows(csv_path: str | None) -> list[dict]:
    if csv_path:
        text = Path(csv_path).read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(URL, timeout=30) as r:
            text = r.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", help="local metadata.csv (otherwise downloaded)")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--min-words", type=int, default=15)
    p.add_argument("--max-words", type=int, default=250)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    seen, pool = set(), []
    for row in load_rows(args.csv):
        text = " ".join((row.get("transcript") or "").split())
        if row.get("language") != "en":
            continue
        if not (args.min_words <= len(text.split()) <= args.max_words):
            continue
        key = text.lower()[:120]  # near-duplicate robocalls share the same opening
        if key in seen:
            continue
        seen.add(key)
        pool.append((row, text))

    random.Random(args.seed).shuffle(pool)
    picked = pool[: args.n]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for i, (row, text) in enumerate(picked, 1):
            f.write(json.dumps({
                "id": f"ftc{i:02d}",
                "source": "ftc",
                "category": "ftc_robocall",
                "expected": "block",
                "caller_number": "unknown",
                "case": row.get("case_details", ""),
                "transcript": [
                    {"role": "agent", "text": GREETING},
                    {"role": "caller", "text": text},
                ],
            }, ensure_ascii=False) + "\n")
    print(f"wrote {len(picked)} rows (from {len(pool)} eligible) -> {OUT}")


if __name__ == "__main__":
    main()
