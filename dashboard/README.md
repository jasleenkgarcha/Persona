# goodcall dashboard

Jasleen's piece of the scam-call screener. It reads the `calls` table and `public/eval-results.json`. Until the Supabase anon key is in `.env.local`, the desk shows seven sample calls.

## Run

```bash
cd dashboard
npm install
npm run dev
```

Open http://localhost:3000.

## Live data

Create `dashboard/.env.local` (never commit it):

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

Restart the dev server. The pill in the header switches from "Sample data" to "Live", and new rows show up without a refresh.

## Eval slide

`/evals` reads `dashboard/public/eval-results.json`. Replace that file with Naiessha's `evals/results.json` when it lands. Leave off `"sample": true` so the sample banner goes away.

## Deploy

From `dashboard/`, run `npx vercel` and set the same two `NEXT_PUBLIC_` variables in the project settings.
