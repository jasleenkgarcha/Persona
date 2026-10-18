# Scorer evals (Naiessha)

## Data: `evals/data/labeled.jsonl` (88 calls)
| Source | Rows | Expected |
|---|---|---|
| `edge_cases.json`, hand-written edge cases | 24 | 8 pass / 16 block |
| `synthetic_extra.json`: injection, tricky legit, more scam types, mid-call | 24 | 8 pass / 16 block |
| `ftc_robocalls.jsonl`: real FTC robocall transcripts (NCSU dataset, public domain) | 40 | all block |

Totals: 8 injection attempts, 8 tricky legit calls. Every row has `split` = `tuning` or `heldout`.
**Tune the prompt on tuning only, and report heldout only.**

Rebuild after editing any source file:
```
python -m evals.build_ftc          # re-download and re-sample the FTC rows (seed 42)
python -m evals.build_dataset      # merge, validate, split -> labeled.jsonl
```

## Run
```
python -m scorer.try_scorer evals\data\edge_cases.json        # quick check, prints every case
python -m evals.run_local --split tuning --limit 5             # smoke test
python -m evals.run_local --split tuning                       # tune loop
python -m evals.run_local --split heldout --repeat 3           # reported numbers -> evals/results.json
python -m evals.chalk_eval --split heldout --repeat 3          # same, on Chalk Agent Evals
```
Prompt v2: copy `SYSTEM_PROMPT` into `evals\prompts\v2.txt`, edit it, then run
`python -m evals.run_local --split tuning --prompt-file evals\prompts\v2.txt --label v2`.
Once v2 wins on tuning, paste it into `score.py`.

## What results.json reports
These contract fields come first: `run_at, model, n_total, accuracy, false_positive_rate, false_negative_rate, misses`.
Extra fields: `by_category`, `by_source` (synthetic vs real FTC), `flip_rate` (decisions that change across the 3 runs,
since the model has no temperature setting), `baseline_keyword` (a no-LLM keyword filter on the same rows),
and `threshold_sweep` (accuracy and errors at each `MAX_PASS_SCORE`, used to pick the cutoff).

- **false_positive_rate**: share of legit calls blocked (false alarms)
- **false_negative_rate**: share of scams passed (missed scams)
- A scorer error counts as **block**, because that's what the backend does.

## Caveats (say these in the pitch, judges reward it)
- There are only 16 legit calls, so the false-alarm rate is coarse: 8 heldout legit calls means each one is about 12%.
- The FTC calls are one-way robocalls (all scams), with no real legit calls from that source.
- The keyword baseline was written after seeing the synthetic cases, so it's an optimistic baseline.
