# Considerations & Design Notes

A running list of things to think about as the project grows. Each section is a topic; each item is a decision or gotcha worth remembering before building that part. Add to this whenever a non-obvious tradeoff or "I'd never have thought of that" detail comes up.

---

## Booking redirect (predict → book loop)

**1. Fallback chain when the live API fetch fails.**
The live booking fetch will fail sometimes — rate limits, partner downtime, network blips. Three options, in order of UX quality:
- Show the prediction with no booking link → worst, users bounce.
- Show the link from the most recent stored offer → decent, but caveat "price as of yesterday."
- Show a generic search URL with the route+date filled in → user re-searches manually but at least lands on a working booking site.

Build option 3 as the universal fallback. It's a one-line URL template, never fails.

**2. Always show the booking link, even when the model says "wait."**
Don't hide the link behind the prediction. Show:
- "Current cheapest: $X — book now" (always visible)
- "Our recommendation: wait 7 days" (alongside, never gating)

Hiding options the model disagrees with is paternalistic, loses bookings, and erodes user trust. Let the user decide.

**3. Outbound link disclosure (regulatory).**
If your booking links are referral links of any kind, US/Canada regulations require visible disclosure. A small footer line covers it — keep it small but present, not buried in a ToS.

**4. Live fetch is on the critical path of the user request.**
Plan for its failure modes from day one. Timeout aggressively (e.g., 5 seconds), then fall back. Don't let a slow third-party API hold the user's whole page hostage.

**5. Stale-price warnings.**
If you show a stored offer rather than a fresh one, mark it: "This price was last seen yesterday — current price may differ." Trust is hard to rebuild after a "you said $232 but it's $310" moment.

---

## Data collection

**1. The API's `limit` parameter is a ceiling, not a target.**
The API returns whatever it has, capped at your limit. Setting `limit=1000` doesn't generate offers — sparse routes still return 3 offers. Don't treat low row counts as a bug.

**2. Specific dates beat months for time-series modeling.**
Querying `departure_at=2026-08` gives you the cheapest offer per day in that month. Querying `departure_at=2026-08-15` gives you depth — many airlines/times for one specific date. The price predictor needs depth, not breadth.

**3. Lead times are the real x-axis of the model.**
Same flight, different days-until-departure produces wildly different prices. Collect at fixed lead times (14, 30, 60, 90, 120, 180 days from today) so you can build a price-vs-lead-time curve per route.

**4. `captured_at` is the most important column in the table.**
It's "today's date" — but the entire point of daily collection is that the same flight gets re-observed many times, and the only thing distinguishing duplicate rows is when they were captured. Without `captured_at`, all your time-series data collapses into indistinguishable junk.

**5. Always store `raw_offer` as JSON text.**
This is the escape hatch when you realize 3 months in that you should have captured a field you skipped. Storing the full original dict means nothing is ever truly lost — you can re-parse it later and pull missing fields.

**6. Store all timestamps in UTC.**
Convert to local only for display. Mixing timezones in the database is a debugging nightmare months later. UTC is monotonic; local time has DST gaps and ambiguity.

**7. Curate routes, don't enumerate.**
There are 10,000+ commercial city pairs. You can't and shouldn't collect all of them. Start with ~120 quality routes that align with target users. Add more based on evidence (which routes are sparse vs juicy), not aspiration.

**8. Sparse routes are noise, not signal.**
A route returning 0-2 offers per day teaches the model nothing useful and bloats the daily run. Prune routes that show <5 offers averaged over 14 days.

---

## Schema & database

**1. The `.db` file and the `schema.sql` file are independent.**
Editing `schema.sql` does NOT change the live db. Use `ALTER TABLE` to apply schema changes to existing data. Keep both in sync manually — or delete the db and re-run the schema when iterating early.

**2. SQLite's `ALTER TABLE` is limited.**
You can `ADD COLUMN`, `RENAME COLUMN`, `RENAME TABLE`, and (3.35+) `DROP COLUMN`. You can't change a column's type or constraints in place — you'd recreate the table and copy data. Plan column types deliberately upfront.

**3. One database, many tables.**
Don't fragment into `flights.db`, `routes.db`, `users.db`. Use one file with multiple tables and JOIN them. SQLite handles 100M+ rows on a laptop, so size is not a reason to split.

**4. Avoid Python reserved words as column names.**
`class` and similar reserved words make Python access (`offer["class"]`) painful. Prefix or rename: `flight_class`, `trip_class`.

**5. `NOT NULL` columns reject rows that omit them.**
If the API doesn't reliably return a field but the schema marks it `NOT NULL`, every insert fails. Either compute the field yourself (e.g., `captured_at`) or remove the constraint.

**6. `AUTOINCREMENT` creates a `sqlite_sequence` table automatically.**
Normal, ignore it. Most use cases don't actually need `AUTOINCREMENT` — plain `INTEGER PRIMARY KEY` reuses ids of deleted rows, which is fine. Worth knowing for next time.

**7. Always use parameterized queries (`?` placeholders).**
Never build SQL with string formatting / f-strings. Reasons: SQL injection, type coercion bugs, statement caching performance. This rule is universal across every database in every language.

**8. `CREATE TABLE` does NOT overwrite — it errors if the table exists.**
SQL is paranoid about destroying data. Running `schema.sql` twice against the same db throws "table already exists." Three options for handling re-runs:
- Plain `CREATE TABLE` → errors if exists. Forces you to think.
- `CREATE TABLE IF NOT EXISTS` → does nothing if exists. Safe to re-run, but the *original* schema sticks even if you edit the file later (silent file/db drift).
- `DROP TABLE IF EXISTS X; CREATE TABLE X (...)` → destroys all rows, rebuilds fresh. Dev-only.

**9. `schema.sql` and the live db are independent — keep them in sync manually.**
Two distinct modes:
- `schema.sql` is the blueprint for a *fresh* database. Run once when the db doesn't exist yet.
- `ALTER TABLE` (run via CLI) is for modifying an existing database that has rows you want to keep.

When you change the schema, do BOTH: update `schema.sql` (so future fresh builds include the change) AND run an `ALTER` against the live db (so your existing data file gets the change). Forgetting one creates drift — usually discovered weeks later when "columns from schema" aren't actually there.

**10. The grown-up version: migrations.**
A `migrations/` folder with numbered files (`0001_create_offers.sql`, `0002_add_flight_class.sql`, ...). A small script tracks which have run and applies missing ones. Replayable, version-controlled, multi-environment safe. Overkill for one developer on one machine — but the right answer once the project deploys, has staging/prod, or other people clone it.

---

## Modeling architecture

**1. Single global tree-based model, not per-route models.**
A global model with rich features (distance, region, hub size, lead time, day-of-week, month, airline) auto-discovers route similarity. Per-route models hit cold-start on unseen routes and need much more data per route.

**2. Feature engineering beats model architecture for this problem.**
Adding `distance_km` and `origin_region` to a Random Forest beats switching to a fancier model with worse features. Spend time on features first.

**3. Lead time is the strongest single predictor.**
Same flight, 14 days out vs 180 days out can differ 3-5x in price. Whatever else the model does, it must see lead time prominently.

**4. The model output is not a number, it's a structured object.**
Plan for `(prediction, confidence, current_best_price, booking_link)` — not just `predicted_price`. Confidence is what enables the cold-start UX ("we don't have much data on this route — low confidence").

**5. Don't get pulled into perfecting the model.**
A mediocre model + a great app gets users. A great model + no app gets you nothing. Spend month 4 on the app and deployment.

**6. Predict actionable things, not just prices.**
Users don't want a number — they want "should I book now or wait, and how confident are you?" Frame the model output around the user decision.

---

## ML training & inference (model serving)

**1. Train offline, predict online.**
Training happens in a separate script (`train.py`), runs on a schedule (weekly via launchd), reads all rows from SQLite, fits the model, saves it as a file. The app NEVER trains during a user request — too slow, wastes work, users won't wait.

**2. The model is just a function.**
Mental model: trained model = a function. User inputs (origin, destination, departure date) are arguments. Output is a predicted number. Training built that function; inference just calls it.

**3. `.pkl` (pickle) is how the model lives between training and serving.**
`pickle.dump(model, f)` saves a trained Python object to disk. `pickle.load(f)` reads it back. Lets you train once (slow) and predict many times (fast) without re-fitting. `joblib` is a slightly better alternative for sklearn models — same idea.

**4. The app loads the model once, at startup — not per request.**
Loading `model.pkl` takes ~100ms-1s. Calling `model.predict()` takes ~1-5ms. Load once into memory; reuse across thousands of requests.

**5. Feature drift between training and inference is the #1 bug to avoid.**
If `train.py` builds features one way and the app builds them another way, the model returns garbage and no error is raised. Put feature-building logic in ONE shared module (`features.py`) imported by both `train.py` and the app. This is non-negotiable.

**6. Inference is fast; the live API call is the slow part.**
A user request takes ~200-2000ms total. The model accounts for ~1-5ms of that. The bottleneck is the live API fetch for current prices. Optimize there if anywhere.

**7. The full request flow:**
```
1. User submits route + date
2. App builds feature row (lead_time_days, distance, region, etc.) — must match training
3. App calls model.predict(features) → predicted price
4. App fetches live API for current real price
5. App compares predicted vs current → "buy now" or "wait"
6. App returns JSON: {current, predicted, recommendation, booking_link, confidence}
```

**8. Retrain weekly, version the model files.**
Save versioned files (`model_2026-09-01.pkl`) so you can roll back if a new model is worse than the old one. Symlink `model.pkl` → latest. Keep ~4 weeks of history.

**9. Track which model version made each prediction.**
Log model version + features + prediction per request. Otherwise you can't debug "why did the model say buy on this request?" months later. A `predictions` table or just JSON logs.

**10. Confidence matters as much as the prediction.**
"Buy now (90% confident)" vs "buy now (40% confident)" are very different UX. Tree models can return prediction intervals; use them. Low confidence → show a less assertive recommendation ("we don't have much data on this route — current price is X, decide for yourself").

---

## Backend (web app server)

**1. Framework choice: Flask or FastAPI.**
Flask is simpler and beginner-friendly — pick it if you've never built a web app. FastAPI is what most modern ML-serving projects use: async I/O (good for slow live API calls), automatic input validation via Pydantic, and auto-generated docs at `/docs`. Both work; FastAPI scales better past v1. Don't use Django — it's overkill and pulls in things you don't need.

**2. Endpoint design — keep it small.**
v1 needs maybe three endpoints:
- `GET /predict?origin=JFK&destination=LHR&departure=2026-08-28` — the main one
- `GET /health` — returns 200, used by hosting platforms to check the app is alive
- `GET /` — serves the frontend HTML

Don't build endpoints "in case." Add when needed.

**3. Load the model at startup, not per request.**
Read `model.pkl` into a global variable when the app boots. Every request reuses that in-memory object. Re-loading per request would add 100ms-1s of unnecessary latency.

**4. The app rarely needs SQLite for predictions.**
The model is trained on SQLite history, but once trained it carries those patterns inside itself. Predictions are: features (built from user input) → `model.predict()` → number. No SQLite read needed for the core prediction.

The app DOES read SQLite for non-prediction extras: coverage/confidence ("we've seen this route 90 days"), live-API fallback (most recent stored offer when API fails), and UI features (price-trend chart, "lowest seen price"). The app NEVER writes to SQLite — only `collect.py` writes.

**4a. The current price comes from the same external API that `collect.py` uses — just called fresh at request time.**
`collect.py` hits the partner API daily and writes results to SQLite for training. The app hits the same partner API on demand, when a user searches, to get the right-now price. Both the price (for comparison) and the booking link (for the redirect) come from this single live call.

Hierarchy of where the current price comes from, in order of preference:

1. **Live API call (fresh):** happy path — gives "right now" price + working booking link.
2. **Most recent row in `flights.db`:** fallback when the live API fails — show with "price as of yesterday" caveat.
3. **Generic partner search URL:** last resort — no price shown, but the user lands on a working search page filled in with their route + date.

The app always shows the user something. Never returns "we couldn't find anything" if any of the three layers work. SQLite's role here is purely fallback insurance — it's the same data source the model was trained on, but in the app context it's a backup, not a primary read path.

**5. Cache live API responses for short windows.**
If two users search "JFK→LHR Aug 28" within a few minutes, hit the API once and serve both. A simple in-memory dict with TTL (or `cachetools`) is enough for v1. Cuts API quota usage and latency. TTL of 5-15 minutes is reasonable.

**6. Use timeouts on every external call.**
Default `requests.get(url)` waits forever. Always set `timeout=5` on the live API call. If it times out, fall through to the fallback chain (stored offer → generic search URL).

**7. Async I/O matters more than you'd think.**
With FastAPI + `httpx`, multiple user requests can wait on the live API in parallel — one slow request doesn't block the next user. With Flask sync, each request blocks a worker. Not a v1-blocker, but a v2-painpoint if traffic grows.

**8. Validate user input before using it.**
Bad inputs to guard against: airport codes that don't exist, dates in the past, dates >365 days out, non-string injections. With FastAPI + Pydantic, this is a few lines of model definition. With Flask, do it manually. Return 400 with a clear message; don't let bad input reach the model or DB.

**9. Don't leak internal errors to users.**
A 500 with a stack trace is bad UX and a security risk. Wrap the request handler in try/except, log the full error server-side, return a sanitized message ("Something went wrong, try again") to the user.

**10. Rate-limit per IP.**
Even one bored teenager can spam your `/predict` endpoint and burn through your API quota. Use `slowapi` (FastAPI) or `flask-limiter` (Flask). Start permissive (60 req/min/IP), tighten if abused.

**11. Log every request.**
Minimum log fields: timestamp, route searched, lead time, current price, predicted price, recommendation, latency, model version. Use these for debugging "why did it say buy?" and for monitoring drift over time.

**12. Static frontend can live in the same app or be split.**
v1 simplest: Flask/FastAPI serves a single HTML file with embedded JS (or templated HTML). Later you might split — backend becomes a pure JSON API, frontend deploys to Vercel/Netlify as a static site. Don't split prematurely.

**13. Environment variables for everything that varies between environments.**
API URL, API token, DB path, model file path, log level — all in env vars, not hardcoded. Same `.env` pattern as `collect.py`. Means deploying to a new environment is "set the env vars and run."

**14. SQLite + multiple processes can deadlock if you're not careful.**
The app reads while `collect.py` writes nightly. SQLite handles this via WAL mode, which is on by default in modern Python — but if you ever see "database is locked" errors, that's the cause. Run `PRAGMA journal_mode=WAL;` once on the db to be safe.

**15. Health check should verify model and DB.**
A `/health` endpoint that just returns "ok" lies when the model is missing or the DB is corrupt. Have it actually load a small thing from each: `model.predict(dummy_features)` succeeds, `cur.execute("SELECT 1")` succeeds. Fail-fast checks.

**16. CORS only matters if frontend is on a different origin.**
If backend serves the frontend (same domain), no CORS config needed. If they're split (api.yourdomain.com vs yourdomain.com, or local dev with Vite on :5173), configure CORS to allow your frontend origin only — never `*` in production.

---

## Routes

**1. ~120 routes is plenty for v1.**
Diminishing returns past that. Routes 121-200 add maintenance burden without much signal.

**2. Maintain a route quality threshold.**
Define what makes a route worth keeping (e.g., ≥5 offers average per day over 14 days). Drop routes that fall below.

**3. Promote routes from a Python list to a `routes` table when:**
- You want to enable/disable routes without editing code
- You want to track per-route metadata (date added, category, active flag)
- You have ≥100 routes and the list is annoying to scroll

Until then, a Python list is simpler and faster.

**4. Map the route list to your real users.**
Toronto-rooted (dogfood) + NYC/SF heavy (target user concentration) > geographically uniform coverage. Friends-and-family testing comes first.

---

## Auth, API, and rate limits

**1. Secrets in `.env`, never in code.**
`.env` is gitignored. Reference via `os.environ["..."]`. Same applies to API URLs if you don't want the provider known publicly.

**2. Header auth is preferred over query-param auth.**
URLs land in server logs and proxy caches; headers usually don't. If the API supports both, send the token in a header.

**3. Rate limit (verified): 600 requests per 60-second window.**
Confirmed via response headers (`X-Rate-Limit: 600`, `X-Rate-Limit-Reset: 60`). Plenty of headroom for the project's foreseeable scale — even 200 routes × 7 months = 1,400 calls completes in under 3 minutes. If you ever hit a 429 error, the response includes the wait time.

**4. Add `try/except` per API call.**
One bad route shouldn't kill the run. Log the failure, increment a counter, continue.

**5. Use timeouts on every external call.**
Default `requests.get(url)` waits forever. Always set `timeout=10` (or whatever's reasonable) so a slow API can't hang the script.

**6. Cabin class affects price 4-10x.**
If you collect business class, store it in a `flight_class` column. Don't mix economy and business prices in one column without distinguishing — the model learns nothing useful from mixed data.

**7. The pricing API normalizes airport codes to city codes.**
You query `JFK → LHR`, the API stores responses with `origin = NYC, origin_airport = JFK`. This is fine for collection (both fields land in the DB) but matters for the app: when a user searches "JFK to LHR," the backend's SQL query must use `origin_airport = 'JFK'` (or translate to city code first) to find rows. Same for destination. Affects multi-airport cities most: NYC = {JFK, EWR, LGA}, LON = {LHR, LGW, STN, LCY}, TYO = {NRT, HND}.

---

## Pipeline & infrastructure

**1. Two data flows, not one.**
- Daily batch (`launchd` → collect script → API → SQLite) for history
- Live (user search → app → API + SQLite + model → response) for predictions

Same db, different triggers, different failure modes. Plan them separately.

**2. The daily script can fail without the app going down (and vice versa).**
This is a feature of the two-flow design. Don't accidentally couple them.

**3. Schedule daily runs at low-traffic hours.**
Pick a time (e.g., 3 AM local) when the API is fastest and you're least likely to compete with other users. Stagger if you ever run multiple collectors.

**4. Log every run.**
At minimum: timestamp, total routes attempted, total offers inserted, total failures. A `runs` table or a log file. You'll thank yourself when debugging "why did Tuesday have half the rows?"

**5. Backups.**
SQLite is one file. Copy it nightly to a second location (Dropbox, S3, anywhere). Losing 3 months of collected data because of a disk failure would be devastating and unrecoverable.

---

## Product & scope

**1. v1 is for individual price-shoppers, not corporate travel.**
Different products. Don't conflate.

**2. The "tech hub" framing is marketing, not a product feature.**
Use it for outreach (HN, Twitter, IH, college Slack). Don't let it constrain the actual route list.

**3. Pick the product shape early.**
Web app, email alerts, browser extension, SMS bot — these are wildly different builds. Decide in the first 2 weeks of building the app phase.

**4. Cold-start UX is critical.**
When a user searches a route you have no data for, give a confident-enough answer (global model + low-confidence flag) rather than "unsupported." Bouncing users is permanent; informing them is not.

**5. The 4-month milestone is for first users, not the ceiling.**
Don't over-build for v1. Don't under-think v2 either.

**6. Ship before perfecting.**
A live demo with rough edges beats a polished concept that never goes public. Friends-and-family is a real launch.

---

## Code & engineering

**1. Top-level script first, function later.**
Don't refactor into functions until the same logic needs to run multiple times. Premature abstraction costs more than it saves.

**2. One database connection per script run, not per loop iteration.**
Open once, commit once at the end, close once. Connection setup is cheap but not free.

**3. Compute "this run's" values once, outside loops.**
`captured_at = datetime.now(...)` should sit above the route loop, not inside. Same value for every row in this batch is the *correct* behavior.

**4. Use `.get()` for optional fields, `[]` for required ones.**
`offer["price"]` crashes if `price` is missing — fast feedback. `offer.get("airline")` returns `None` — graceful degradation. Pick deliberately.

**5. Don't write code you don't need yet.**
Comments, docstrings, type hints, error handlers — only when they earn their keep. Sparse code is easier to change than thorough code.

---

## Things still TBD

Topics to fill in as decisions come up:

- [ ] Web app framework (Flask vs FastAPI vs Django)
- [ ] Hosting (Render, Railway, Fly.io, Vercel)
- [ ] Auth (anon usage vs accounts vs email)
- [ ] Email alert system (SendGrid, Mailgun, Resend)
- [ ] Domain name + SSL
- [ ] Analytics (Plausible, PostHog, basic logs)
- [ ] Privacy policy + ToS
- [ ] Monitoring + alerting on the daily collection script
- [ ] Model retraining cadence (weekly? when N new rows?)
- [ ] How to A/B test predictions in the wild
