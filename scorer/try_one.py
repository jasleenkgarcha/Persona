r"""Run the scorer on ONE transcript and print everything it decided.

Usage (from the scam-scorer folder):
    python -m scorer.try_one evals\samples\grandparent.txt     # a transcript file
    python -m scorer.try_one                              # paste a transcript, then a blank line

Transcript format: one line per turn, starting with "Agent:" or "Caller:".
A line with no prefix is treated as the caller speaking.
"""

import json
import sys

from scorer.score import ScorerError, decide, score_call


def parse(text: str) -> list[dict]:
    turns = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("agent:"):
            turns.append({"role": "agent", "text": line[6:].strip()})
        elif low.startswith("caller:"):
            turns.append({"role": "caller", "text": line[7:].strip()})
        else:
            turns.append({"role": "caller", "text": line})
    return turns


def read_input() -> str:
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            return f.read()
    print("Paste a transcript (Agent: / Caller: lines). Press Enter on an empty line to finish:")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    transcript = parse(read_input())
    if not transcript:
        sys.exit("No transcript given.")

    print("\nTranscript the scorer sees:")
    for t in transcript:
        print(f"  {t['role'].upper():6} {t['text']}")

    try:
        result = score_call("unknown", transcript)
    except ScorerError as e:
        sys.exit(f"\nScorer failed: {e}")

    print(f"\nDECISION:  {decide(result).upper()}")
    print(f"Verdict:   {result['verdict']}   (scam score {result['scam_score']}/100)")
    print(f"Tactics:   {', '.join(result['tactics']) or 'none'}")
    print("Reasons:")
    for r in result["reasons"]:
        print(f"  - {r}")
    print(f"Summary:   {result['summary']}")
    print("\nRaw JSON:")
    print(json.dumps(result, indent=2))
