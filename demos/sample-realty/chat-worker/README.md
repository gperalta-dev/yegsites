# Sample Realty chat server

The realty demo's "Ask about this home" chat runs on Claude Haiku (`claude-haiku-5-5`) through this Cloudflare Worker.
The page can't call Claude itself, because the API key would be public. The Worker holds the key as a secret, keeps the
listing facts and the rules in its prompt (`PROMPT` in `worker.mjs`), and passes only the reply's text back as it streams.

- The page sends the conversation (the last 11 turns, questions cut to 500 characters) and the Pricing section's rate,
  years and how often you pay. The Worker works out the three plans with the same maths as the page, so the AI quotes
  what the visitor sees.
- Spending limits are kept by one Durable Object (`Budget`): `DAILY_CAP_USD` (US$0.30 a UTC day, about $9 a month at
  most) and `PER_IP_HOUR` (30 questions per visitor per hour). Each reply is counted at its real token cost.
  One reply costs about US$0.0001 with the cached prompt.
- Visitors are counted by a hash of their IP and the date. Nothing they type is stored or logged.
- Only pages from `ALLOWED_ORIGINS` can call it. `CHAT_OFF = "1"` switches the AI off.
- When the Worker answers 429 (limits) or 503 (off), or doesn't answer at all, the page falls back to its built-in
  answers and says so in the chat. With `CHAT_URL` empty in `index.html`, the page only uses the built-in answers.

Keep `PROMPT` in step with the page when the listing changes. Prices in `PRICES` are for `claude-haiku-5-5`; change
them together with `MODEL`.

## Deploy (Cloudflare Workers free plan)

Live since Oct 29 2026 at https://sample-realty-chat.southsites.workers.dev (Gabriel's Cloudflare account, workers.dev
name `southsites`, key from `CLAUDE_API_KEY_FOR_AGENTS`). After a change to `worker.mjs` or `wrangler.toml`, run
`npx --yes wrangler@4 deploy` in this folder. The page waits 5 seconds for the first words, then uses its built-in answer.

First time on a new account:

1. A Cloudflare account. Open Workers & Pages once so it gets a workers.dev address.
2. Optional: a separate Claude API key for the chat, `REALTY_CHAT_API_KEY=...` in Money Town's `.env`, so its spending
   shows on its own in the Console. Without it the script uses `CLAUDE_API_KEY_FOR_AGENTS`.
3. `pwsh -File deploy.ps1`. The first run downloads wrangler and opens the browser to log in. It deploys, gives the
   Worker the key as a secret (piped, never printed), writes the address into `CHAT_URL` in `../index.html` and asks
   one test question.
4. Commit `index.html` and push.

## Check

`node test.mjs` runs the Worker against a fake API stream (no network, no key): origins, the conversation rules, the
pricing maths, the per-hour and daily limits, refusals, and the fallbacks.
