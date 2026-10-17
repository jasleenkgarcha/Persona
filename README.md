# Scam-call screener (HackHarvard 2026)

A caller dials our Photon number. An ElevenLabs voice agent screens them and calls `check_caller` on our backend. The scorer (LLM via Chalk AI Router) returns pass or block. Pass transfers the call to Ian's phone. After the call, the transcript is re-scored, saved to Supabase, and the verdict is iMessaged via Photon. The dashboard shows calls live.

## Layout and owners
| Folder | Owner |
|---|---|
| `telephony/` | Ian |
| `backend/` | Pablo (glue); `photon_send.py` is Ian's |
| `scorer/`, `evals/` | Naiessha |
| `dashboard/` | Jasleen |
| `supabase/` | Pablo |

Read `CONTRACTS.md` first. All stubs return fixed values so imports work from minute one.

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # fill in values you own; never commit .env
pytest                   # should pass on a fresh clone
```

## Run
```bash
uvicorn backend.main:app --reload --port 8000
curl localhost:8000/health
```
Dashboard: see `dashboard/README.md` (copy `dashboard/.env.local.example` to `.env.local`).

## Test with ngrok
```bash
ngrok http 8000
```
Use the HTTPS URL for the ElevenLabs tool (`/tool/check_caller`, header `X-Tool-Secret`) and webhook (`/webhook/elevenlabs`). Photon and ElevenLabs only reach public HTTPS. The stub saves the last raw webhook to `samples/last_webhook_raw.json` (gitignored); copy it to `samples/elevenlabs_post_call.json` and commit it for Pablo.
Set `STUB_DECISION=pass` in `.env` only for the transfer test, then set it back to `block`.

## Deploy backend (Render)
New Web Service from this repo; `render.yaml` and `Procfile` configure it. Set env vars from `.env.example` in the dashboard. Health check: `/health`. Railway also works with the Procfile.

## Rules
1. Edit only your own folder.
2. Stub signatures are fixed; announce contract changes in the group chat.
3. No secrets in git. Share by DM or a password manager.
4. Pull before push. Keep commits small.
5. The Supabase service key is backend-only; the dashboard uses the anon key.
