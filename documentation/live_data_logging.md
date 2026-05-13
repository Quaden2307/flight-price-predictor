# Live Data Collection — Run Log

Running log of daily collector runs and any anomalies worth remembering. Not a per-day journal — only entries when something is worth noting.

---

## May 12, 2026

First non-clean run since launchd went live. The previous two days (May 10 and May 11) had four runs total, all 0 failures, ~17K rows of clean data. Today: 15 failures out of 3220 calls, ~4186 offers inserted, runtime ballooned from ~8 minutes to ~5 hours.

Looked at logs/collector.out.log to figure out what happened. The 15 failures break down as ~10 read timeouts, ~5 RemoteDisconnected errors, and one DNS NameResolutionError on api.travelpayouts.com. The DNS one is the classic "computer just woke up and the resolver isn't ready yet" symptom — so opening the laptop late probably caused that single failure. The rest are different though: timeouts and dropped TCP connections, which is the API itself misbehaving.

The 5-hour runtime is the bigger anomaly and isn't explained by waking late. collect.py has no retry logic — failed calls just continue — so 15 failures cost at most 2.5 minutes. The remaining time means individual successful calls were averaging ~5 seconds each (3220 × 5s ≈ 4.5h) versus the sub-second responses on previous runs. TravelPayouts' API was just slow today.

Data itself is fine. NULL audit clean across price, airline, departure_at, return_at, trip_duration_days, lead_time_days. Value ranges sane. No real duplicates once return_at is included in the grouping key (the 246 "dup groups" I initially saw were legitimate same-outbound-different-return round-trip pairs).

Nothing to fix in the code right now — one bad day isn't enough signal. If transient network/API failures repeat, worth adding a small retry-with-backoff around the requests.get call so flaky route-months aren't permanently lost.

---

## May 13, 2026

Second bad day in a row, and worse than yesterday. 856 failures out of 3220 calls (27%), only 2892 offers inserted (~33% below the normal ~4300), runtime ~5.5 hours. Cumulative dataset is now 24,385 rows across 6 runs.

Failure breakdown is qualitatively different from yesterday: 841 of the 856 failures are NameResolutionError (DNS), with 10 read timeouts, 3 RemoteDisconnected, and 2 ConnectionResetError making up the rest. Yesterday was mostly API slowness; today is local network dying.

Shape of the failures matters. The first ~2400 calls ran normally — mix of successful pulls and legitimate "0 offers" responses. Then around call 2400 the run hit a wall of consecutive DNS failures and never recovered for the remaining ~800 calls. So this wasn't a startup-only blip from waking the laptop late — DNS resolution went sideways mid-run and stayed broken. WiFi dropping, the resolver getting confused, or the laptop briefly sleeping mid-run would all fit the pattern.

Data integrity itself is still clean: 0 NULLs across price, airline, departure_at, return_at, trip_duration_days, lead_time_days. Price range $44-$2436, trip durations 0-57d, lead times 0-204d. Volume is what's suffering, not quality.

One bad day was noise; two in a row with today qualitatively worse is signal. Plan is to add retry-with-backoff around the requests.get call in collect.py — wrap it in a small loop that retries 2-3 times on connection errors with a few seconds of sleep between attempts. That covers both the startup-not-ready case and the mid-run network drop case. Want to write this myself rather than have it scaffolded, since this is exactly the kind of plumbing I'm trying to learn.
