# Southsites chats

Two chats run on Claude Haiku (`claude-haiku-5-5`) through one Cloudflare Worker (`worker.mjs`):

- **Sample Realty** (`demos/sample-realty/`, "Ask about this home"): bot `realty`, the default. Its facts and rules are
  `PROMPT` in `worker.mjs`. The page also sends the Pricing section's rate, years and how often you pay, and the Worker
  works out the three plans with the same maths as the page, so the AI quotes what the visitor sees.
- **The landing page** (`index.html`, "Ask Southsites", a button in the bottom bar): bot `southsites`, prompt
  `SOUTHSITES`, facts from southsites.ca and /pricing. The page code is `southsites.js` in this folder, loaded with one
  script tag. It's also a live example of the AI chat assistant add-on.

The pages can't call Claude themselves, because the API key would be public. The Worker holds the key as a secret and
passes only the reply's text back as it streams.

- Each page sends the last 11 turns, questions cut to 500 characters.
- Spending limits are kept by one Durable Object (`Budget`), shared by both chats: `DAILY_CAP_USD` (US$0.30 a UTC day,
  about $9 a month at most) and `PER_IP_HOUR` (30 questions per visitor per hour). Each reply is counted at its real
  token cost. One reply costs about US$0.0001 with the cached prompt.
- Visitors are counted by a hash of their IP and the date. Nothing they type is stored or logged.
- Only pages from `ALLOWED_ORIGINS` can call it. `CHAT_OFF = "1"` switches the AI off for both.
- When the Worker answers 429 (limits) or 503 (off), says nothing for 5 seconds, or doesn't answer at all, the page
  falls back to its built-in answers and says so. The suggestion chips always use the built-in answers, so they're instant.

Keep `PROMPT` and `SOUTHSITES` (and the built-in answers in each page) in step with the pages when the listing or
the prices change. Prices in `PRICES` are for `claude-haiku-5-5`; change them together with `MODEL`.

## Deploy (Cloudflare Workers free plan)

Live since Oct 29 2026 at https://sample-realty-chat.southsites.workers.dev (Gabriel's Cloudflare account, workers.dev
name `southsites`, key from `CLAUDE_API_KEY_FOR_AGENTS`). After a change to `worker.mjs` or `wrangler.toml`, run
`npx --yes wrangler@4 deploy` in this folder.

First time on a new account:

1. A Cloudflare account. Open Workers & Pages once so it gets a workers.dev address.
2. Optional: a separate Claude API key for the chats, `REALTY_CHAT_API_KEY=...` in Money Town's `.env`, so their
   spending shows on its own in the Console. Without it the script uses `CLAUDE_API_KEY_FOR_AGENTS`.
3. `pwsh -File deploy.ps1`. The first run downloads wrangler and opens the browser to log in. It deploys, gives the
   Worker the key as a secret (piped, never printed) and asks one test question. If the address changed, put it in
   `CHAT_URL` in `demos/sample-realty/index.html` and `southsites.js`.

## Check

`node test.mjs` runs the Worker against a fake API stream (no network, no key): origins, both prompts, the conversation
rules, the pricing maths, the per-hour and daily limits, refusals, and the fallbacks.
