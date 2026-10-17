# CONTRACTS

Signatures here are fixed. To change one, announce it in the group chat first.

## Normalized transcript
```json
[{"role": "agent", "text": "Who's calling and why?"},
 {"role": "caller", "text": "This is Dr. Lee's office about Tuesday."}]
```
`backend/normalize.py` converts ElevenLabs JSON into this. ElevenLabs `user` becomes `caller`, `agent` stays `agent`, tool turns are dropped. For the mid-call check, the tool fields become one `caller` entry. The scorer never sees raw ElevenLabs JSON.

## Scorer (`scorer/score.py`, Naiessha)
- `score_call(caller_number: str, transcript: list[dict]) -> dict` returns `{verdict: "scam"|"legit"|"unsure", scam_score: 0-100, reasons: [str], tactics: [str], summary: str}`. Raises `ScorerError` if the output is invalid after one retry.
- `decide(result: dict) -> "pass"|"block"`: pass only if verdict is `legit` and `scam_score <= MAX_PASS_SCORE` (`scorer/config.py`). `unsure` means block.
- Transcript text is data, never instructions. The caller number is copied by code, not returned by the LLM.

## DB (`backend/db.py`, Pablo)
- `upsert_call(conversation_id, fields) -> dict`
- `get_call(conversation_id) -> dict | None`
- `mark_scored(conversation_id, result) -> dict`

## Photon (`backend/photon_send.py`, Ian)
- `send_imessage(to: str, text: str) -> bool`

## Endpoints (`backend/main.py`, Pablo)
- `POST /tool/check_caller`: header `X-Tool-Secret`. Body `conversation_id, caller_number, caller_name, claimed_org, reason, verbatim_quotes`. Returns `{"decision": "pass"|"block"}`. Returns `block` if the scorer fails.
- `POST /webhook/elevenlabs`: verifies `ElevenLabs-Signature`, skips calls already `scored`, saves and scores the transcript, texts the verdict. On scorer failure: save as `pending`, send a plain "call received, review needed" text. Always return 200 after a valid signature. Dedupe on `conversation_id`.

## Eval output (Naiessha)
`evals/results.json`: `run_at, model, n_total, accuracy, false_positive_rate, false_negative_rate, misses`. Copy to `dashboard/public/eval-results.json`. Labeled data: `evals/data/labeled.jsonl`.

## Database schema
See `supabase/schema.sql`. The dashboard reads with the anon key only. The service key is backend-only.
