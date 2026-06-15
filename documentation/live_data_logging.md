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

One bad day was noise; two in a row with today qualitatively worse is signal. Added retry-with-backoff around the requests.get call in collect.py — wrapped it in a loop that retries up to 3 times on connection errors, with exponential backoff (2s, then 4s) between attempts. Two new constants at the top (MAX_ATTEMPTS = 3, BASE_BACKOFF = 2) make the knobs easy to tweak. Also narrowed the except clause from bare Exception to requests.exceptions.RequestException so unrelated bugs don't get silently swallowed as retry-eligible.

This should salvage yesterday's failure mode (sparse transient errors scattered through the run) but won't help with today's (DNS dead for ~800 consecutive calls — retries just make a dead run longer). If today's pattern repeats, next step is a circuit breaker that bails the whole run after N consecutive failures. Holding off on that until I see whether retries alone change the picture.

---

## May 14, 2026

Run 7 went clean: 0 failures, 4043 offers inserted, ~7 minute runtime. Right back to the May 10-11 baseline after two rough days. Cumulative dataset now 28,428 rows. NULL audit still clean across all key fields, value ranges still sane.

Couldn't actually test yesterday's retry code though. Grepped the log for "retrying in" and "FAILED after" — zero matches. Every API call succeeded on first attempt because the network just had a healthy day, so the retry path never got exercised. The code is in place and didn't break the run, but it hasn't been stress-tested in the wild yet. Next time conditions degrade I'll see retry log lines and be able to judge whether it actually salvages calls or not.

Worth keeping in mind for tomorrow's run too — if everything keeps going smoothly the retry logic could sit unverified for a while. That's fine, but the moment it does fire, the log lines are the signal to watch for.

---

## May 15, 2026

Run 8 finished while I wasn't looking. Final numbers: 3220 API calls, 4022 offers inserted, 0 final failures, ~5h 20m runtime (10:04 → 15:24 UTC). Cumulative dataset now 32,450 rows across 8 runs. NULL audit still clean across all key fields, value ranges still sane.

Two things worth recording. First, the slow-API pattern from May 12/13 was back. 5+ hours of runtime with the script's actual CPU time at well under a minute — the entire run was spent waiting on slow network responses to successful calls. Not a thing I can fix on my end; the TravelPayouts API was just slow today.

Second and more importantly: this is the first time the retry-with-backoff code has actually fired in the wild, and it worked exactly as designed. 13 retry events in the log, 0 final failures. Those 13 calls would have been hard losses on May 12 and contributed to the wave on May 13. Today they were saves, and the offer count came in at the normal ~4,000 instead of the 2,892 disaster from May 13. Counts the retry logic as validated in real conditions.

(Self-correction: I originally noted the run as starting unusually early at 3:04 AM. Reviewing all 8 runs' captured_at timestamps, every launchd-triggered run since May 10 has fired at ~10:00 UTC consistently, and today's is no exception. The 3:04 AM observation was either a timezone misread or me confusing myself — the run actually started at the normal time. No anomaly there.)

---

## May 16, 2026

Run 9 came in: 3220 API calls, 3933 offers inserted, 0 final failures, 18 retry events. Cumulative dataset now 36,383 rows across 9 runs. NULL audit still clean, value ranges still sane.

Two things worth recording. First, the API slowness has officially become a pattern rather than an anomaly. Today's runtime was 6h 36m — the longest yet — and 4 of the last 5 days (May 12, 13, 15, 16) have had 5+ hour runs. May 14 was the only fast day in that stretch. The morning collection window is now eating into half the workday. Not a data-quality issue but worth flagging if it keeps drifting upward.

Second, the retry code keeps earning its keep. 18 saves today on top of 13 yesterday — 31 calls over two days that would have been losses on May 12 or part of the wave on May 13. Validates the decision to ship the retry logic when I did.

One thing to keep an eye on: offer count came in at 3,933, slightly below the recent ~4,000-4,300 range. Could be normal day-to-day API cache variance, could be TravelPayouts thinning their cached offers. If it keeps trending down across the next few runs, that's a real signal worth investigating — sparser cache would mean fewer training rows per route over time.

---

## May 17, 2026

Run 10 broke the slow-API streak — back to a normal ~7.5 minute runtime with 0 failures, 0 retry events, and 3921 offers inserted. First fast day since May 14. Cumulative dataset crossed 40,000 rows for the first time (40,304 across 10 runs). NULL audit still clean.

The four-out-of-five slow days from May 12-16 weren't a permanent regression in the TravelPayouts API — they come and go based on whatever's happening server-side on their end. Means I can't predict when slow days hit, but the retry code handles them when they do.

Worth flagging: the offer-count drift I noted yesterday is continuing very slowly. Three runs in a row now at 4022 → 3933 → 3921, vs the early-May baseline of ~4,300. Three points isn't a real trend yet, but if it keeps drifting downward over the next week while runtime stays healthy, that points to TravelPayouts thinning their cache rather than network issues. Sparser cache means fewer training rows per (route, date) snapshot — worth investigating before it gets material.

---

## May 18, 2026

Run 11: 3963 offers, 0 failures, 0 retries, ~8 min runtime. Second consecutive clean fast day. Cumulative dataset now 44,267 rows across 11 runs. NULL audit still clean.

API is fully back to normal — the May 12/13/15/16 slow streak really was a transient TravelPayouts server-side thing, not anything in my pipeline. Two fast days in a row argues it's resolved.

The offer-count drift I flagged earlier (4022 → 3933 → 3921) bounced up slightly today to 3963. Not a clear continuation of the downward trend. Probably just day-to-day variance rather than a permanent cache thinning. De-prioritizing the concern but will keep watching.

---

## May 19, 2026

Run 12: 3968 offers, 0 failures, ~7m 53s runtime. Third consecutive clean fast day — the slow-API streak from May 12-16 is fully behind us. Cumulative dataset now 48,235 rows across 12 runs. NULL audit still clean.

Offer count trend has flattened: 3921 → 3963 → 3968. The downward drift I flagged a few days ago isn't continuing. Calling that concern resolved.

First production run of the iCloud backup pipeline. The shutil.copy line shipped yesterday silently refreshed flights.db (~70 MB) in the iCloud folder at 08:12 local right after the collector run finished. Worked exactly as designed — no manual intervention needed. Laptop loss is no longer an existential risk to the dataset.

Halfway to the 96K-row target for modeling start on May 31. On track.

---

## May 20, 2026

Run 13: 4014 offers, 0 failures, ~7m 39s runtime. Fourth straight clean fast day. Cumulative dataset now 52,249 rows across 13 runs. NULL audit still clean, offer count slightly above the recent baseline (3933 → 3921 → 3963 → 3968 → 4014).

Two things worth recording today.

First, five routes that had been showing up consistently (8 of the previous 9 days) went missing from today's pull: NYC→PHL, OAK→AUS, ONT→ORL, SFO→AMS, SJC→SEA. Five new routes also appeared that hadn't been in the prior six days. Some route churn is normal from TravelPayouts' cache, but the missing-stable-route count is something to watch — if those five keep not showing up for another day or two, worth checking whether the request log is even hitting them or whether TravelPayouts has dropped aggregated prices for those metro pairs.

Second, ran a same-flight price comparison from yesterday to today: matched 3,250 flights by (origin, destination, departure_at, return_at, airline, flight#), and only 49 of them (1.5%) had any price change at all. Average delta $0.02. Biggest mover was NYC→LON on FI dropping $181. Doing the same check across the full 11-day capture window: of 9,155 unique flights seen on 2+ days, only 516 (5.6%) ever changed price. This is a real finding for modeling — TravelPayouts is mostly serving stable cached snapshots, so almost all of the day-over-day variation in the dataset comes from the flight set churning (new flights appearing, old ones falling out), not from prices on existing flights actually moving. Worth thinking about whether the target should really be "predict the price of a flight appearing on day X" rather than "predict how the price of a known flight will move." The latter would be modeling a signal that barely exists in this data source.

---

## May 21, 2026

Run 14 is still in progress while I'm writing this. Started at 10:07 UTC same as every prior run, ~5h 20m in, 2,231 of 3,220 calls completed (~69%). DB is locked so no row-level checks yet — these notes are from the log only. Projected finish around 12-13 UTC, putting today in the same slow-API neighborhood as May 15/16. Retry code firing modestly: 12 attempt-1 retries so far (6 ReadTimeout, 6 ConnectionError), all recovered on the first retry. No attempt-2 retries, no FAILED-after-3 lines.

Real anomaly today is timing. The launchd plist is Hour=6 with no explicit timezone, so it fires at 6 AM local. The laptop's clock currently reads PDT, which means 6 AM local would be 13 UTC — but today's run started at 10 UTC, the same UTC slot every prior run has used. That puts the process start at 3:07 AM local under PDT.

This conflicts with the self-correction I wrote in the May 15 entry. At the time I dismissed a 3:04 AM observation as a timezone misread and concluded the run was firing at the normal 6 AM local. That conclusion may have been correct when the laptop was on EDT (10 UTC = 6 AM EDT) but isn't anymore. Two possibilities to disambiguate once the run finishes:

1. Laptop was on EDT for runs 1-13 and is now on PDT. launchd may have kept the cached fire time for today and will re-anchor to current local 6 AM tomorrow — meaning tomorrow's run shifts to 13 UTC. If that happens, fine, but the dataset will have a 3-hour break in the capture cadence to flag in the modeling.
2. The plist was firing at 10 UTC the whole time independent of local time (e.g. launchd interpreting the plist in UTC for some reason, or another scheduler running it). In that case the May 15 self-correction was wrong from the start.

Final numbers once the run finished: 4,047 offers, 0 failures, 5h 22m runtime (10:07 → 15:29 UTC). NULL audit clean. Retry code did its job — 12 attempt-1 retries, none escalated.

Timezone question is mostly resolved by today's run (see May 22 below): the May 22 run also fired at 10:07 UTC despite the laptop still being on PDT. That means launchd is NOT computing "Hour=6 local" against current local time — it's been firing at a fixed UTC slot the whole time. The May 15 self-correction was wrong. Most likely the plist was loaded when the machine was elsewhere (or launchd cached a fire time against the original local timezone) and the schedule has stayed pinned to that UTC instant ever since. Not urgent to fix because the slot is still a reasonable morning window, but worth re-anchoring later if I want it to actually fire at 6 AM local going forward.

---

## May 22, 2026

Run 15 is in progress and going very badly. Started 10:07 UTC same as always, but 5h 9m in only 798 of 3,220 calls have completed (~24%). At the current pace the run projects to roughly 21 hours total. For comparison, yesterday at the same elapsed time was at 67%, and the previously-worst slow day (May 16) finished in 6h 36m. Today is a different magnitude.

Per-call latency is ~23 seconds today vs ~5 seconds yesterday — about 5x slower on the wire. This isn't retry-induced: only 11 attempt-1 retries so far (7 ReadTimeout, 4 ConnectionError), all recovered, 0 final failures. The TravelPayouts API itself is just unusually slow.

Concrete risk worth tracking: if today's pace holds, the run finishes around 06 UTC on May 23 — only ~4 hours before tomorrow's run is scheduled to start at 10 UTC. If today's run hasn't completed by then, two collectors will fight over the SQLite write lock and at least one will fail (or launchd may skip the new run entirely if it sees the old PID still alive). Watching through the afternoon. If the pace doesn't pick up materially by early evening, will kill the run before tomorrow's window opens rather than risk a tangled overlap.

DB is locked while the run is in flight, so no row-level checks yet. Will update with final numbers once it finishes (or once I kill it).

Update: the run finished cleanly — 3,992 offers, 0 failures, 5h 15m runtime (10:07 → 15:22 UTC). My 21-hour projection at the 5h 9m mark was badly wrong. API response speed picked up sharply after the first quarter of calls and the back half ran at normal pace. Self-correction: linearly extrapolating a slow-day finish time from the first segment isn't reliable for this API — slow stretches and fast stretches mix within the same run. Future slow-day projections should wait until at least 50-60% completion before estimating, or just not estimate at all.

---

## May 25, 2026

Run 18: 3,814 offers, 0 failures, 5h 5m runtime. Cumulative dataset now 71,833 rows. Skipped detailed entries for May 23 (6h 23m, 3,870 offers, 0 failures) and May 24 (8h 28m, 3,861 offers, 0 failures — slowest run on record but retry code handled the slow API fine, no drops).

Two things worth recording today.

First, a single offer came in at \$5,647 — NYC→PAR on Air France, June 5 depart 01:00 ET and return same day 20:30 Paris local, nonstop both ways. Prior all-time max in the dataset was \$2,436, and only this one row exceeds it today. A same-day NYC↔Paris turn on a premium carrier at \$5,647 strongly looks like a business-class fare leaking into the feed even though `flight_class=0` for every row in the schema. Could be a one-off, but the outlier is far enough out that I want to look at the raw_offer JSON to see what TravelPayouts is actually saying. If they've started returning premium cabins without a class flag on these queries, the model will get polluted with mixed-cabin prices that the current cleaning step doesn't catch.

Second, 11 routes that normally show up (seen on ≥5 of the prior 6 days) went missing today — roughly double the May 20 count of 5. Could be normal cache shuffling on TravelPayouts' end, but if the gap stays elevated through the week it warrants checking whether the request log is actually hitting these metro-pairs and the API is returning empty, or whether requests are silently being dropped before the response.

Day-over-day price movement was 1.9% (62/3,281 matched flights changed) — still consistent with the cached-snapshot pattern from the earlier analysis. No update needed to the modeling-target thinking.

Final numbers: 3,992 offers, 0 failures, 5h 15m runtime (10:07 → 15:22 UTC). The 21-hour projection from mid-run was wrong — API latency recovered somewhere in the back half and the run finished comfortably before tomorrow's window. No overlap risk materialized. NULL audit clean. The "5x slower than yesterday" pattern I logged at the 5h mark didn't hold for the whole run, which is a useful lesson: per-call latency in a partial sample isn't a reliable extrapolation when the API can recover mid-run.

---

## May 23, 2026

Run 16: 3,870 offers, 0 failures, ~6h 23m runtime (10:04 → 16:27 UTC), ~15 retry events (all recovered on attempt 1). Cumulative dataset now 64,158 rows across 16 runs. NULL audit clean across price, airline, departure_at, return_at, trip_duration_days, lead_time_days. Value ranges sane (price $35-$5647, trip duration 0-58d, lead time 0-190d).

Three things worth recording.

First, slow-API runs are now the rule rather than the exception. 7 of the last 12 days (May 12, 13, 15, 16, 21, 22, 23) have been 5+ hour runs versus 5 fast days (May 14, 17, 18, 19, 20). The pattern's stable enough that I'd stop treating it as an anomaly — this is just how the API behaves now. Retry code handles it cleanly so there's no data-quality impact, but the mental model of "collection runs in the background while I sleep" needs updating: half the time it now runs deep into the workday.

Second, the offer-count drift I called resolved on May 19 is back. Today's 3,870 is the lowest single-run total in the 16-run history. Last 9 runs: 4022 → 3933 → 3921 → 3963 → 3968 → 4014 → 4047 → 3992 → 3870. The early-May ~4,300 baseline is gone and the bounce-back on May 18-19 looks like noise on top of a real downward drift. Cache thinning on the API side is the most likely explanation — nothing I can do about it on my end anyway. Not actionable yet; just worth knowing the per-day yield is trending down.

Third, on track but no buffer for the 96K-row modeling start on May 31. Need ~32K more rows in 8 days (~4K/day), almost exactly the current rate. If the drift continues even slightly, May 31 slips. Acceptable — that date is a target, not a deadline, and the pre-modeling structural work (features.py and split.py) is still in progress anyway.

---

## May 24, 2026

Run 17: 3,861 offers, 0 failures, ~8h 28m runtime (10:13 → 18:42 UTC). Cumulative dataset now 68,019 rows across 17 runs. Integrity check clean across NULLs, ranges, and the 3-day volume baseline.

Two things worth recording.

First, the offer-count drift I re-flagged yesterday is continuing. 3,861 is the new single-run low — third consecutive day under 4,000 (3,992 → 3,870 → 3,861). The volume-drop check didn't fire (today is ~97% of the 3-day baseline, well above the 75% threshold), but the trend itself is steady. Same explanation as yesterday — most likely cache thinning on the API side. Not actionable but worth knowing per-day yield keeps eroding.

Second, runtime is creeping up alongside the slow-API pattern. Last three days: 5h 15m → 6h 23m → 8h 28m. The 6 AM PDT start still leaves comfortable margin before the next 6 AM trigger (today finished at ~11:42 AM PDT), so no overlap risk yet. But if runtime keeps doubling, the safe margin disappears fast. Worth pre-thinking a circuit-breaker or earlier start time if runtime crosses ~16 hours, well before the actual overlap point.

Modeling-start math: need ~28K more rows in 7 days. At the current ~3,900/day rate that's right on the line. May 31 still feasible but increasingly tight.

---

## May 26, 2026

Run 19: 3,758 offers, 0 failures, 0 retry events, ~7m 51s runtime (10:00 → 10:08 UTC). Cumulative dataset now 75,591 rows across 19 runs. NULL audit clean, price $35-$5,647, trip duration 0-58d, lead time 0-188d.

Two things worth recording.

First, the slow-API stretch broke. After three 5-8h runs in a row (May 23/24/25), today finished in under 8 minutes — the fastest run since May 20. Consistent with the May 23 mental model that slow days and fast days mix unpredictably; one fast day doesn't mean the slow streak is over for good, but it confirms the API hasn't permanently shifted into slow-mode.

Second, the offer-count drift continues. 3,758 is a new single-run low. Last five runs: 3,992 → 3,870 → 3,861 → 3,814 → 3,758, all under 4,000, all monotonically declining. Five-in-a-row downward isn't noise anymore — there's a real per-day yield erosion happening on the TravelPayouts side. Still nothing actionable from my end (the request set hasn't changed), but the math on May 31 keeps getting tighter: at ~3,800/day I need ~5.4 more runs to hit 96K, which puts me at ~June 1 instead of May 31. Still close enough that I'd call it on-track-with-no-buffer rather than slipping.

The $5,647 outlier from yesterday is still in the daily max — same NYC→PAR Air France row carried forward in matched-flight comparisons, no new equivalent today. Haven't dug into the raw_offer JSON yet to confirm the business-class-leak hypothesis. Adding that to the queue for a quieter day.

---

## May 27, 2026

Run 20: 3,683 offers, 0 failures, 0 retry events, ~7m 41s runtime (10:00 → 10:08 UTC). Cumulative dataset now 79,274 rows across 20 runs. NULL audit clean, price $62-$5,647, trip duration 0-58d, lead time 0-187d.

Two things worth recording.

First, the offer-count drift is now six consecutive days, every day a new low: 3,992 → 3,870 → 3,861 → 3,814 → 3,758 → 3,683. Cumulative erosion is ~14% off the early-May ~4,300 baseline. Not noise — there's a real downward trend in per-day yield from TravelPayouts, almost certainly cache thinning on their side. Still nothing I can fix on my end since the request set is unchanged.

Setting an explicit alarm threshold going forward: **if daily offers drop to ~3,000 and stay there across 2+ consecutive runs, treat it as a real regression and investigate** — likely actions would be checking whether specific route-month combinations have stopped returning anything, comparing the response shape against earlier captures, and deciding whether to widen the request set to compensate. Today's 3,683 is still ~23% above that floor, but at the current ~50 offers/day decline rate, the threshold is ~14 days out if drift holds linearly. Probably won't be linear, but worth pre-committing to the trigger now rather than rationalizing it away when it hits.

Second, modeling-start math at 79,274 rows: need ~16,700 more to hit 96K. At today's 3,683/day, that's 4.5 more runs — June 1. May 31 target is officially slipping by one day given the drift; June 1 is the new working assumption unless the trend reverses. Still well within "target, not deadline" territory.

The $5,647 NYC→PAR outlier showed up again today (third consecutive day at that exact price). Strengthens the cached-row hypothesis — same Air France record is persisting in TravelPayouts' cache rather than being a coincidence of identical re-prices. Still need to look at raw_offer JSON to confirm the business-class-leak theory.

---

## May 28, 2026

Run 21 was still in progress when I checked — started 3:04 AM local, ~69% done (2,230 of ~3,220 route-months), 11 retries all recovered on attempt 1, 0 hard failures. Another slow-API day. DB write-locked so NULL/range/volume row checks are deferred to the next entry.

The headline today is not the collection — it's that **the iCloud backup has been silently broken for 5 days.**

Last successful backup was May 23. Every run since (May 24/25/26/27) failed the `shutil.copy` step with `OSError: [Errno 11] Resource deadlock avoided` — four identical tracebacks sitting in collector.err.log that I hadn't looked at because the collection itself kept reporting 0 failures. The runs_logs `failures` column only counts API failures, not post-collection steps, so the backup dying never showed up in the daily numbers.

Root cause, confirmed via `ls -O`: the backup file in iCloud is flagged `dataless` (compressed, evicted to cloud-only). iCloud's "Optimize Mac Storage" evicted it because the file is written once a day and never read back — textbook eviction candidate. When `shutil.copy` opens that cloud-only placeholder for write (`open(dst, 'wb')`), the file provider can't reconcile the write against materialization and throws EDEADLK. So the backup has been frozen at 93.8 MB / May 23 while the live DB grew to 120 MB / May 28 — five runs (~26 MB, ~18K rows) with no off-machine copy. The May 19 entry's "laptop loss is no longer an existential risk" was false from May 24 onward.

Fix shipped to collect.py: copy to `backup_path + ".tmp"` then `os.replace(tmp, backup_path)`. The atomic rename swaps the directory entry without ever opening the evicted placeholder, so EDEADLK can't fire even after iCloud re-evicts between runs. Bonus: the backup is now atomic — an interrupted copy can't leave a half-written DB in the backup folder. Didn't try to stop iCloud from evicting the file; with the rename approach eviction is harmless.

Two caveats I'm holding onto:

1. The fix takes effect on the **next** run (May 29). Today's collector loaded the old code into memory at 3:04 AM, so when run 21 reaches the backup step it will fail a 5th time. Expected, not a regression.

2. Need a manual one-off backup to close the 5-day gap — but only **after** run 21 finishes. Copying the DB mid-write would capture an inconsistent SQLite snapshot. Once the run completes and the lock releases, I'll run the temp+replace copy by hand so there's a current off-machine copy before tomorrow.

Lesson worth internalizing: a daily job reporting "0 failures" only means the part that counts failures succeeded. The backup, the dedup, and the audit are all post-commit steps whose failures don't touch runs_logs. Worth a glance at collector.err.log on every check-in, not just when the offer numbers look off.

---

## May 29, 2026

Run 22: 3,679 offers, 203 routes, 0 API failures, ~6h47m runtime (10:08 → 16:55 UTC). Cumulative dataset now 86,622 rows across 22 runs. Audit clean (0 NULLs, 0 range violations), 0 duplicates table-wide.

First good news: **the backup fix works.** This was the first run on the new temp+replace code, and the iCloud file came out at 126.7 MB / 09:55 local, byte-identical size and mtime to the live DB, no leftover `.tmp`. The 5-day gap closed on its own — no manual backup needed after all. EDEADLK did not recur. (The 5th EDEADLK traceback in collector.err.log, referencing old line 191, is yesterday's run failing on the in-memory old code — exactly as predicted, not a regression.)

Then the fix un-masked a second latent bug. For the last 5 days the backup crash was killing collect.py at the backup step, *before* execution ever reached the post-collection dedup and audit subprocess calls. With the backup now succeeding, the flow continued to those calls and immediately crashed with `FileNotFoundError: 'python'`. Both `subprocess.run` calls were spawning `"python"`, but the launchd environment only has `python3` / the venv interpreter — there is no bare `python` on PATH. Because FileNotFoundError is raised at process spawn, `check=False` doesn't suppress it; it propagates and kills the script.

Consequences, now understood:
- The audit has never run automatically. The absolute-floor alarm added May 27 has therefore never actually executed in production — it only "passes" because I run audit.py by hand during check-ins. Until today that was hidden behind the backup crash.
- The dedup has never run automatically either. No harm done: ran it dry today and the table is exact-key unique (0 dup groups). The 9-column key only collides on re-runs or partial-write artifacts, neither of which has happened, so there was nothing to remove.

(Open archaeology question I'm not chasing: on May 23 and earlier the backup succeeded, so the flow should have reached these subprocess calls and failed the same way — yet there's no pre-May-24 FileNotFoundError in the err log. Either the err log was truncated/rotated around then or the PATH situation is recent. Doesn't change the fix, so leaving it.)

Fix shipped to collect.py: added `import sys` and switched both subprocess calls from `"python"` to `sys.executable`, so they reuse the exact interpreter launchd invoked collect.py with — guaranteed to exist, same stdlib the scripts need. Verified by spawning `[sys.executable, "data_collector/audit.py"]` the same way collect.py will: exit 0, audit ran, clean stderr. Takes effect on the next run (May 30); tomorrow's check should be the first time dedup + audit + the floor alarm all run automatically end to end.

Offer-count trend: 3,683 → 3,669 → 3,679. The six-day monotonic decline broke today with a +10 uptick. Marginal and could just be noise, but the steady slide has at least paused. Still ~700 above the 3,000 floor, so even if it resumes there's runway before the alarm would trip.

---

## May 30, 2026

Run 23: 3,620 offers, 0 failures, 0 retry events, ~7m 54s runtime (10:00 → 10:08 UTC). Cumulative dataset now 90,242 rows across 23 runs. Audit clean (0 NULLs across all six modeling-critical fields), price $62-$5,855, trip duration 0-54d, lead time 0-184d.

The headline: **first end-to-end automated run.** collector.err.log hasn't grown since May 29 09:55 — meaning the backup, dedup, audit, and floor alarm all ran without crashing for the first time since the two bugs were stacked. The May 28 atomic-rename fix and the May 29 `sys.executable` fix both held in production. The pipeline is finally doing what the runs_logs `0 failures` column had been falsely implying all month.

Yesterday's +10 uptick was noise after all — today is a new floor at 3,620, the eighth new low in nine days. Drift continues. Still 620 above the 3,000 alarm threshold (~17% headroom), but the slope has not reversed. At the current ~50/day decline rate the alarm is ~12 days out if it stays linear.

Modeling-start math: 90,242 rows toward the 96K target, need 5,758 more. At today's pace that's ~1.6 days — June 1 is the working target. Holding to it unless tomorrow's run drops sharply.

Today's max price ($5,855, NYC→LON, AF) is higher than the persistent $5,647 NYC→PAR AF outlier from last week. Same airline, different long-haul route — looks like a second cached business-class-leak candidate rather than the same row carrying forward. Still on the "look at raw_offer JSON during a quieter day" queue.

---

## May 31, 2026

The headline today is **a duplicate run**, caused by relocating the project to a different parent directory (paths omitted here for privacy). The collector fired twice:

- Run 24 at **07:01 UTC** (≈3:01 AM local) → 3,622 offers, 0 failures
- Run 25 at **10:00 UTC** (the normal launchd slot) → 3,588 offers, 0 failures

Both succeeded, so `runs_logs` showed 0 failures as usual and the only visible symptom was the row count: 7,210 offers, ~2× a normal day. 3,515 of those offers appear in both runs — it's the same daily snapshot collected twice, not new data.

**Why dedupe.py wouldn't catch it:** its 9-column key includes `captured_at`, which differs between the two runs (07:01 vs 10:00). By the exact-key definition these aren't duplicates, so a dry run reports the table as clean even though the day is double-counted. This is exactly the brittleness flagged in CONTEXT.md's "Known issue" — relying on `captured_at` differing per run means semantic same-day duplicates slip through. Worth considering a `(date(captured_at), origin, destination, departure_at, return_at, airline, flight_number, price)` second-pass guard if folder moves / manual re-runs become a recurring source of doubles.

**Resolution:** deleted the 3,622 offers from the 07:01 run, kept the 10:00 run as the canonical snapshot (matches the ~10:00 UTC capture time every other day uses). `runs_logs` row 24 left intact as an honest audit record that the run happened — its `offers_inserted=3622` no longer matches the table on purpose; the discarded rows are documented here instead. Today's canonical count: **3,588 offers. Cumulative dataset 93,830 rows** (90,242 on May 30 + 3,588). Audit clean — 0 NULLs across all six modeling-critical fields, price $62–$5,855, trip duration 0–54d, lead time 0–182d.

**Root cause / state of launchd:** only one job is loaded (`local.flightpricepredictor.collector`), still `Hour=6` (fires at the pinned ~10:00 UTC slot), and its `WorkingDirectory` was correctly re-pointed to the new project location (plist edited May 30 23:53 local). So going forward it's back to one run/day — today's double was a one-time artifact of the move, most likely a load-time fire when the reconfigured job was reloaded. The 07:01 UTC timing (3 hours off the normal slot) fits a one-off reload rather than a new schedule. Watch tomorrow's run to confirm it's back to a single 10:00 UTC fire.

**Stale error-log note:** collector.err.log still ends with old tracebacks referencing the *previous* project location — the `Resource deadlock` backup error and the bare-`python` FileNotFoundError. Both predate the move and the `python`→`sys.executable` fix; they are not from today's runs. The May 29/30 fixes still hold. (The $5,855 NYC→LON AF business-class-leak candidate persists — still queued for a raw_offer JSON look.)

Lesson reinforced from May 28: "0 failures" in runs_logs says nothing about whether the *dataset* is clean. A duplicate run is invisible to the failure column and invisible to dedupe.py — only the daily row-count sanity check caught it. Glancing at offers-per-day, not just the failures column, stays on the check-in list.

---

## June 1, 2026

Run 26: 3,778 offers, 0 failures, 0 retry events, ~3h 37m runtime (10:09 → 13:46 UTC). Cumulative dataset now **97,608 rows across 24 canonical runs**. Audit clean — 0 NULLs across all six modeling-critical fields, price $62–$5,855, trip duration 0–54d, lead time 0–213d.

Three things worth recording.

**First, the folder move is fully settled.** Yesterday's double-run was a one-time artifact — today fired exactly once, at the normal ~10:00 UTC slot. collector.err.log hasn't grown since May 29 09:55, so backup + dedup + audit all ran end-to-end with no new tracebacks, and the new project location + new `Project Backups/` backup path are both working in production. The backup self-healed exactly as predicted: it now holds 97,608 rows, which is yesterday's deduped 93,830 + today's 3,778 — i.e. the duplicate snapshot I removed by hand is gone from the off-machine copy too (if it were still there the backup would read 101,230). No manual backup refresh was needed. (Backup file still shows as `dataless`/evicted with a misleading ~3h-stale mtime; the row count is the reliable currency check, not the mtime — same iCloud placeholder quirk as May 31.)

**Second, the offer-count drift broke upward.** 3,778 is the highest single-run total since May 26 (3,758) and a +190 jump over yesterday's deduped 3,588. The eight-ish-day monotonic decline from the early-May ~4,300 baseline has at least paused; could be noise or TravelPayouts' cache refilling. One day isn't a confirmed reversal, but the slide stopped. Still comfortably above the 3,000 floor alarm.

**Third — milestone: crossed the 96K modeling-start target.** At 97,608 rows the dataset is past the threshold the runs log had pinned for ~June 1. The data side is ready for XGBoost; modeling work moves to `src/train_xgb.py` (bar to beat from the LR baseline: val MAPE 0.257 — see `documentation/modeling_runs.md`). The collector keeps running daily in the background regardless; from here, dataset depth just keeps accruing while modeling proceeds.

---

## June 1, 2026

Run 26: 3,778 offers, **single run**, 0 failures, ~3h37m runtime (10:09 → 13:46 UTC — slow-API day, handled cleanly). Cumulative dataset now **97,608 rows**. Audit clean: 0 NULLs across all six modeling-critical fields, price $62–$5,855, trip duration 0–54d, lead time 0–213d.

**The folder-move loose ends are all closed:**

1. **No duplicate recurrence.** Today fired exactly once at the normal ~10:00 UTC slot, confirming yesterday's double was a one-time artifact of relocating the project (a load-time fire when the reconfigured launchd job reloaded), not a standing schedule problem. launchd is back to one run/day with no intervention.

2. **Backup is current and matches the live DB exactly.** The backup now holds 97,608 rows = the live total (93,830 after yesterday's dedup + 3,778 today), mtime ~06:46 local — written by today's run. Yesterday's caveat (the off-machine copy was momentarily *ahead*, carrying the duplicate rows I'd deleted) self-resolved: today's run overwrote it with the clean state, so the manual refresh was never needed. The file is still `compressed,dataless` (iCloud-evicted) but that's harmless under the atomic-rename fix, and reading it materialized it fine.

3. **Pipeline ran clean end to end.** collector.err.log hasn't grown since May 29 09:55 — backup, dedup, and audit all ran without crashing. The trailing `FileNotFoundError: 'python'` line in that log is the stale pre-fix entry, not from today.

Two milestones worth recording. First, **crossed the 96K modeling-start target** (97,608 rows) — the working goal that had slipped from May 31 to June 1 across the drift entries. Hit it on the June 1 estimate.

Second, **the offer-count drift reversed.** The recent slide was monotonic (… 3,679 → 3,620 → 3,588); today jumped to 3,778, a +190 single-day uptick — the largest in a while and the first clear break from the downward run. One day isn't a trend, but it argues against the cache-thinning hypothesis hardening into a permanent regression. Still well above the 3,000 alarm floor either way.

---

## June 2, 2026

Run 27: 3,902 offers, **single run**, 0 failures, 0 retry events, ~7m 46s runtime. Cumulative dataset now **101,510 rows** (97,608 + 3,902). Audit clean — 0 NULLs across all six modeling-critical fields, price $62–$5,855, trip duration 0–54d, lead time 0–212d.

Quiet, clean day — **third straight clean single-run since the folder move**, so the migration is firmly settled. Fired once at the normal 6 AM-local slot; collector.err.log still hasn't grown since May 29 09:55, so backup + dedup + audit all ran end to end with no new tracebacks. Backup matches the live DB exactly (101,510 rows, written by today's run on the `Project Backups/` path) — still self-syncing with no manual touch. The trailing `FileNotFoundError: 'python'` in the error log remains the stale pre-fix entry, not from today.

**Drift recovery continues.** 3,902 is +124 over yesterday's 3,778 — second straight up-day after the early-May slide (… 3,588 → 3,778 → 3,902). The downward run that once put the 3,000 floor ~12 days out has clearly broken; two consecutive jumps argue the cache-thinning was transient. Comfortable headroom over the alarm.

**Timing note (no action needed):** runs_logs now shows the run landing at ~13:00 UTC versus the ~10:00 UTC of the May entries. This is *not* a schedule change — the launchd job still fires at 6 AM **local** (file mtime ~06:07 local). The 3-hour UTC shift just reflects the machine clock now reading UTC-7 where May's runs were UTC-4; same daily slot in local terms. Flagging it only so the UTC stamps in runs_logs aren't misread as the schedule drifting.

---

## June 3, 2026

**Config change, not a run anomaly: route list expanded 230 → 300.** Added 70
busiest-route gaps in three tiers (Tier 1: Hawaii/Atlanta/Taipei/India/Denver/
Puerto Rico/Manila; Tier 2: Cancun-Mexico/Gulf/transatlantic fill/IST-LIS; Tier 3:
Caribbean & S. America leisure, ATL/CLT/Hawaii/Denver domestic, secondary Asia/
India/Europe). Rationale + full list in `route_expansion_proposal_2026-06-03.md`;
demand-ranked from 2024–25 OAG/traffic data. `populate_airports.py` re-run →
`airports` table 76 → 102 codes (all new codes were already in airports.csv).
Smoke-tested at each tier (routes load + 0 dupes → CSV coverage → populate → full
`train_lr` pipeline clean → collect.py parses). Committed + pushed.

**What to expect tomorrow (first 300-route run):**
- **Offers/day will jump** — ~30% more routes (API calls ~3,220 → ~4,200/day), so
  expect a step-up from the ~3,900 baseline. This is the expansion, *not* a drift
  reversal or a double-run; don't misread it.
- **Runtime grows ~30%** (per-minute API limit, not daily, so no wall).
- **⚠ Watch for newly-dropped city codes.** The API may return metro codes for some
  new international routes that aren't in the table yet (likeliest **Buenos Aires
  `EZE`→`BUE`**, Bangkok). Airport codes are covered; city codes can only be checked
  once real offers land. After tomorrow's run, re-run the coverage check and patch
  `populate_airports.py` `CITY_CODES` if any rows get `dropna`-silenced — same
  failure mode as the original 91%-row-drop bug.

---

## June 4, 2026

**First 300-route run.** Run 29: 5,026 offers, 4,200 API calls, **2 failures**, ~9h 52m runtime (13:00 → 22:52 UTC). Cumulative dataset now **110,507 rows** (105,481 after June 3 + today's 5,026). Audit clean — 0 NULLs across all six modeling-critical fields, price $49–$4,587, trip duration 0–53d, lead time 0–210d. Backup current and materialized (110,507 rows on the `Project Backups/` path, no longer evicted).

The June 3 predictions held. Offers stepped up to 5,026 (the expansion, not a drift reversal — exactly as flagged), api_calls landed at the predicted 4,200 (300 × 7 × 2), and yield held at 1.20 offers/call, same as pre-expansion — so the 70 new routes are productive, not empty. Runtime grew more than the predicted ~30%: ~9h 52m is among the slowest on record, because a slow-API day compounded the larger call volume. Still finished at 15:52 local with the next run not until 6 AM, so no overlap risk — but the more-routes × slow-day interaction is the thing that will eventually approach the ~16h overlap ceiling. Worth watching as routes grow further.

**Failures (first non-zero since mid-May, but trivial):** 7 attempt-1 retries fired, 5 recovered, 2 exhausted all 3 attempts → 2 final failures out of 4,200 (0.05%). All ReadTimeout/ConnectionError — transient network/API slowness, not route-specific. Notably several retries hit *new* expansion routes (JFK→TPE, SFO→BLR, ORD→MUC), but that's just slow-day noise landing on whichever calls happen to be in flight, not a problem with the new routes themselves.

**Coverage check (the pre-registered June 3 follow-up) — clean, after a false-alarm scare.** The feared city-code drops did **not** materialize: no `BUE` (Buenos Aires), no Bangkok metro code silently dropped. A first pass *looked* like a gap — 9 codes (`BUR`, `CLD`, `DAL`, `HHN`, `NLU`, `SAW`, `SNA`, `TLC`, `XNB`) appear in offers but aren't in the `airports` table, seemingly affecting ~1,662 rows all-time. But that pass checked the wrong columns: it matched against `origin_airport`/`destination_airport`, whereas `build_features()` merges the airports table on **`origin`/`destination`** (the city-level codes), and never touches the airport-level columns. Re-checked against the actual merge key: **zero** `origin`/`destination` codes are missing from the table, all have real coordinates, and **110,507/110,507 rows survive the `dropna`** — no loss, all-time or today. The 9 "missing" codes are alternate/secondary *airport* labels (Burbank, Orange County, Dallas-Love, Frankfurt-Hahn, Toluca, etc.) plus `XNB` (a Dubai surface/bus segment); none of them ever appear as a city code, so the pipeline correctly ignores them. The `CITY_CODES` map + CSV load already cover everything the merge needs, and the `BUE` addition made today was the only real coverage action required.

**No `populate_airports.py` change needed.** Lesson for next time: run the coverage check against the *merge key* `build_features()` actually uses (`origin`/`destination`), not the airport-level columns — checking the wrong column manufactured a 1,662-row "gap" that doesn't exist. (`distance_km` is computed downstream from the merge, so it isn't one of the six fields the daily NULL audit covers — worth a one-line post-build assertion that row count is preserved through `dropna`, so a *real* future coverage gap can't hide.)

**Timing (no action, per June 2):** runs_logs shows 13:00 UTC, still the 6 AM-local launchd slot — the machine is now on UTC-7. Not a schedule drift.

---

## June 5, 2026

**Run in progress at check time — row-level numbers deferred** (same as the May 21/22 mid-run checks). The collector (PID 30889) started at the normal 6 AM-local slot and was still running when I checked, holding the SQLite write lock — so offer count, audit, and runtime are unavailable until it finishes and releases the lock. Did **not** force the lock; interrupting a live run risks a partial write and there's no sign of trouble.

What's observable from the log files + backup (none of which need the locked DB):
- **Pipeline healthy so far** — `collector.err.log` unchanged since May 29 09:55 (the trailing `FileNotFoundError: 'python'` is the old stale traceback, not from today), so nothing is crashing. Backup/dedup/audit run only at the end, so a clean err.log mid-run is expected.
- **Likely another slow-API day** — still running well past the 6 AM start, consistent with the recurring TravelPayouts slowness pattern.
- **Last-known-good = 110,507 rows** (June 4's completed run, confirmed from the iCloud backup, which is a separate unlocked file; `dataless`/evicted but readable, mtime Jun 4 16:09).

**Update — run completed (numbers via backup + live DB, June 6):** run 30, **4,922 offers**, single run, **1 failure** (0.02%, transient), runtime **~2h 11m** (13:00:46 → 15:11:36 UTC). Audit clean — 0 NULLs, price $49–$4,587, trip 0–53d, lead 0–209d. Cumulative **115,429 rows**; backup refreshed to match. Correction: the mid-run "likely slow-API day" guess was wrong — 2h 11m is only moderately slow; it simply hadn't finished when I first checked.

---

## June 6, 2026

Run 31: **4,851 offers**, single run, **0 failures**, ~**6h 35m** runtime (13:00:12 → 19:35:21 UTC) — a genuine slow-API day this time. Cumulative **120,280 rows** (115,429 + 4,851). Audit clean — 0 NULLs across all six modeling-critical fields, price $49–$4,587, trip 0–54d, lead 0–208d. `collector.err.log` unchanged since May 29 (backup/dedup/audit ran clean end-to-end); backup self-refreshed to 120,280, byte-for-byte matching the live DB.

**Check-time note:** the run was still in flight when first queried (caught at ~6h35m elapsed, DB write-locked), then finished moments later. So both June 5's deferred numbers and today's were read from the iCloud backup's `runs_logs` (a separate, unlocked copy) and then re-confirmed against the live DB once the lock released. Reinforces the value of the backup as a read path when the live DB is locked mid-run.

**Volume holding steady post-expansion:** 5,026 → 4,922 → 4,851 across June 4–6. The early-May downward drift is firmly over; the 300-route set yields a stable ~4,800–5,000/day. Single clean run each day — no recurrence of the June 4 folder-move double.

---

## June 7, 2026

Run 32: **4,860 offers**, single run, **0 failures**, ~**3h 41m** runtime (13:12 → 16:52 UTC — note the ~12-min-late start vs the usual 13:00 slot; immaterial). Cumulative **125,140 rows** (120,280 + 4,860). Audit clean — 0 NULLs across all six modeling-critical fields, trip 0–54d, lead 0–207d. err.log unchanged since May 29; backup self-refreshed to 125,140, matching the live DB.

**No business-class outlier today** — max price $3,324, well below the recurring ~$5,855 NYC→LON Air France leak that's appeared most days. It simply wasn't in today's cache pull; nothing wrong, but worth noting the outlier is intermittent (cache churn), not a fixed row carried forward.

**Volume:** 5,026 → 4,922 → 4,851 → 4,860 across June 4–7 — settled into a reliable ~4,850–5,000/day on the 300-route set. Four straight single clean runs.

---

## June 8, 2026

Run 33: **4,844 offers**, single run, **5 failures**, **~11h 39m runtime** (13:14 UTC → 00:53 UTC next day) — **the longest run on record** (prior worst was June 4's 9h 52m). Cumulative **129,984 rows** (125,140 + 4,844). Audit clean — 0 NULLs across all six modeling-critical fields, price $49–$3,324, trip 0–54d, lead 0–206d. err.log unchanged since May 29 (backup/dedup/audit ran clean); backup self-refreshed to 129,984, matching the live DB.

Two things worth recording.

**First, the 5 failures were a transient DNS blip — not a real problem.** Lots of scattered attempt-1 retries fired (ReadTimeout/ConnectionError on international routes — normal slow-day noise, all recovered), but the **5 final failures cluster on consecutive `MIA→PUJ` / `MIA→LIM` calls** with `NameResolutionError: Failed to resolve 'api.travelpayouts.com'`. That's DNS going sideways for a short window mid-run — same symptom as **May 13**. Retries can't rescue calls during a dead-resolver stretch (retrying a dead DNS just fails again), so those ~5 route-months were lost. Negligible: 5 of 4,200 calls, and volume still came in normal at 4,844 with a clean audit. Not actionable unless the DNS pattern recurs across multiple days.

**Second, the runtime hit a new record (~11h 39m) and is eating into the overlap margin.** It finished at 17:53 local with the next run at 6 AM — ~12h headroom remains — but the **more-routes × slow-API-day** combination keeps stretching runtimes (8h28m May 24 → 9h52m June 4 → 11h39m today on the bad days). The May 24 entry set ~16h as the pre-overlap worry line; a bad day is now within striking distance. Pre-thinking the mitigation: a circuit-breaker that bails after N consecutive failures, or an earlier start, becomes worth implementing if a single run crosses ~14h. Watching; not urgent yet.

(Third minor note: start drifted to 13:14 UTC vs the usual 13:00 — third day running ~12 min late. Immaterial, but logging the drift in case it grows.)

---

## June 9, 2026

Run 34: **4,916 offers**, single run, **2 failures** (0.05%), ~**4h 26m** runtime (13:12 → 17:39 UTC). Cumulative dataset now **134,900 rows** (129,984 + 4,916). Audit clean — 0 NULLs across all six modeling-critical fields, price $49–$3,324, trip 0–54d, lead 0–205d. err.log unchanged since May 29 (backup/dedup/audit ran clean end-to-end); backup self-refreshed to match the live DB. 282 of 300 routes returned offers.

Two things worth recording.

**First, the DNS-cluster failure pattern recurred — second day in a row.** Today's 2 final failures are both consecutive `EWR→MIA` calls (Nov departures) with `NameResolutionError: Failed to resolve 'api.travelpayouts.com'` — same signature as yesterday's `MIA→PUJ`/`MIA→LIM` cluster and the original May 13 episode. 19 attempt-1 retries fired today and all but these 2 recovered; a dead resolver just can't be retried through. The June 8 entry set "recurs across multiple days" as the trigger to care, and technically it now has — but both days were tiny (5 then 2 final failures), on *different* routes, in short isolated windows, with normal volume and a clean audit each time. So I'm reading this as the same low-grade transient local-DNS flakiness surfacing intermittently, not a developing problem with TravelPayouts or with the new expansion routes. The bar for action stays where it was: a day where DNS kills a *large consecutive block* (May-13-scale, ~800 calls), not these handfuls. Still not worth a circuit breaker.

**Second, the slow-API streak broke — runtime back to normal.** 4h 26m today vs yesterday's record 11h 39m. The more-routes × slow-day runtime creep I flagged June 8 (which had crept 8h28m → 9h52m → 11h39m on the bad days) didn't continue; today was a moderately-slow-to-normal day, finished ~10:39 local with a full ~19h before the next 6 AM trigger. No overlap pressure. Consistent with the long-standing pattern that slow and fast days mix unpredictably — one record-long day doesn't mean the API has shifted into permanent slow-mode.

Volume holding steady post-expansion: 5,026 → 4,922 → 4,851 → 4,860 → 4,844 → 4,916 across June 4–9, six straight single clean runs in the ~4,850–5,000/day band. No business-class outlier today — max was $3,324 (NYC→SIN, UA); the recurring ~$5,855 NYC→LON AF leak wasn't in today's cache pull (intermittent cache churn, as noted June 7).

---

## June 10, 2026

Run 35: **4,527 offers**, single run, **165 failures**, ~**3h 09m** runtime (13:04 → 16:13 UTC). Cumulative **139,427 rows** (134,900 + 4,527). Audit clean — 0 NULLs across all six modeling-critical fields, price $79–$3,324, trip 0–54d, lead 0–204d. err.log unchanged since May 29 (run completed normally; per-call DNS failures are caught and counted in runs_logs, they don't crash the script). Backup self-refreshed to 139,427, matching the live DB.

**The DNS-cluster pattern escalated hard — this is the day the June 9 threshold was watching for.** Failures jumped **2 → 165** (a ~30× spike), and the diagnosis is unambiguous: **100% `NameResolutionError`**, and **clustered in one contiguous window** (out.log lines ~117.1k–117.6k of 120.7k), not scattered. It wiped **~11 consecutive whole routes** — every call of `EWR→{SFO,ORD,MIA,LAX}`, `LGA→{ATL,DFW,MCO,MIA,ORD}`, `SFO→{LAX,SAN,SEA,PDX}` (14/14 each), which are adjacent in the route list. So DNS died for one stretch (~the time to churn ~11 routes), then recovered and the rest of the run succeeded. June 9 set the action bar at "DNS kills a *large consecutive block* (May-13-scale)"; 165 isn't May-13-scale (856) but it's a genuine block — 11 whole routes — not the handfuls of June 8/9. Three consecutive DNS days (5 → 2 → 165), now escalating, clears my bar for acting.

**Why the run was *fast* (3h 09m) despite the most failures yet:** DNS failures fail fast (~6s through retries) vs. slow-API successful calls that wait on the wire. ~165 calls bailing quickly *shortened* the run. So a low runtime is not a "good day" signal here — it co-occurred with the worst failure count.

**Impact:** those ~11 routes have **no June 10 snapshot** (a one-day hole, not permanent — tomorrow's run resumes them). This fully accounts for the volume dip: 4,527 is ~320 below the ~4,850 baseline, ≈ 165 lost calls × ~2 offers/call. So the dip is *lost calls, not cache thinning* — don't misread it as the old drift returning. Updated volume line: 4,851 → 4,860 → 4,844 → 4,916 → **4,527** (June 6–10).

**Action (was "watch", now "do"):** the targeted fix is an **end-of-run retry sweep** — accumulate the failed `(route, depart_month, offset)` tuples during the main loop and re-attempt them after it finishes. DNS had fully recovered by run end (the back half of the run succeeded), so a second pass would have recovered nearly all 165 with negligible extra runtime. This is better than a circuit-breaker (which would only *stop* the run, not recover the data) and better than nothing (which leaves route-day holes). Secondary hardening if it persists: pin a reliable resolver (1.1.1.1 / 8.8.8.8) and/or prevent the machine sleeping mid-run. Logged as the next collector-side task.

---

## June 11, 2026

Run 36: **5,089 offers**, single run, **5 failures** (0.12%), ~**3h 12m** runtime (13:12 → 16:24 UTC). Cumulative dataset now **144,516 rows** (139,427 + 5,089). Audit clean — 0 NULLs across all six modeling-critical fields, 0 range violations, dedup found 0 duplicate groups. err.log unchanged since May 29 (backup/dedup/audit ran clean end-to-end); backup self-refreshed to 144,516 rows, matching the live DB exactly.

Two things worth recording.

**First, the DNS-cluster pattern is now four consecutive days (5 → 2 → 165 → 5), but today de-escalated back to a handful.** All 5 final failures are one contiguous block — five consecutive `JFK→HKG` calls (Aug–Oct months), 100% `NameResolutionError`, same signature as June 8/9/10. The resolver died for one short window and recovered; 24 attempt-1 retries fired across the run and everything outside the DNS window recovered. Impact: JFK→HKG is missing 5 of its 14 route-month calls for today — a partial one-day hole, resumed tomorrow. Yesterday's 165-failure spike did not recur, but four days running confirms this is a standing low-grade local-DNS flakiness, not one-off noise. **The end-of-run retry sweep logged June 10 remains the right fix and is still unimplemented** — today's 5 would all have been recovered by it, since DNS was healthy again well before run end.

**Second, 5,089 is the highest single-run offer count on record**, beating June 4's 5,026. Yesterday's 4,527 dip is fully explained as lost calls (the 165-failure block), not cache thinning — today's bounce-back confirms it. Volume line since expansion: 5,026 → 4,922 → 4,851 → 4,860 → 4,844 → 4,916 → 4,527 → **5,089**. The 300-route set is healthy.

(Minor: start time 13:12 UTC — the ~12-min-late start drift noted June 8 continues on most days, still immaterial. No business-class outlier today; max price within normal range.)

---

## June 12, 2026

Run 37: **5,165 offers**, single run, **10 failures** (all `NameResolutionError`), ~**4h 11m** runtime (13:06 → 17:17 UTC). Cumulative **149,681 rows** (144,516 + 5,165) — crossed 145k. Audit clean — 0 NULLs across all six modeling-critical fields, price $75–$3,324, trip 0–55d, lead 0–202d. err.log unchanged since May 29 (backup/dedup/audit ran clean); backup self-refreshed to 149,681, matching the live DB.

**The DNS failures are now a confirmed low-grade chronic pattern, not isolated incidents.** Five straight days, all `NameResolutionError`: 2 → **165** → 5 → 10 (Jun 8–12). The Jun 10 spike (165, ~11 routes wiped) was the outlier; since then it's a steady trickle of ~5–10 lost route-months/day. Volume is unaffected (today's 5,165 is the new post-expansion high, beating Jun 11's 5,089), so the cost is negligible — but the pattern is now persistent enough that the **end-of-run retry sweep** (logged as the collector task on Jun 10) is the right fix whenever collector-hardening resumes: it would recover essentially all of these, since DNS is back by run's end. Not urgent.

**Volume trending up, drift firmly dead.** Post-expansion line: 5,026 → 4,922 → 4,851 → 4,860 → 4,844 → 4,916 → 4,527 → 5,089 → **5,165**. The 300-route set is yielding ~5k/day and climbing.

(Minor: start 13:06 UTC — the ~12-min-late drift continues, immaterial. Project otherwise paused for the learning-project detour; collector remains fully hands-off.)

---

## June 13, 2026

Run 38: **5,327 offers**, single run, **0 failures**, ~**4h 48m** runtime (13:08 → 17:56 UTC). Cumulative **155,008 rows** — crossed 155k. Audit clean — 0 NULLs across all six modeling-critical fields, price $75–$3,324, trip 0–57d, lead 0–201d. err.log unchanged since May 29; backup self-refreshed to 155,008, matching the live DB.

Cleanest day in a week. **The DNS trickle stopped**: failures went 2 → 165 → 5 → 10 → **0** (Jun 8–13), confirming it was transient local-network flakiness, not a systemic issue — end-of-run retry sweep stays a nice-to-have, not urgent. **Volume hit a third straight post-expansion high**: 5,089 → 5,165 → **5,327**. The 300-route set is healthy and climbing.

**Storage note (not a data issue): the DB is now 216 MB and the `raw_offer` JSON column is ~110 MB = 50% of the file.** Per the 2026-06-11 audit, all 16 `raw_offer` keys are already extracted into typed columns (and `link` has its own column), so `raw_offer` is now pure redundancy — the original "escape hatch for un-extracted fields" turned out empty. Nulling it + `VACUUM` would roughly halve the file. Deferred (it's the documented escape hatch; decision for when modeling resumes), but it's the lever if GUI viewers keep hitting size limits.

---

## June 14, 2026

Run 39: **5,361 offers**, single run, **0 failures**, **4,200 api_calls**, ~**9m 51s** runtime (13:00:05 → 13:09:56 UTC). Cumulative **160,369 rows** (155,008 + 5,361) — crossed 160k. Audit clean — 0 NULLs across all six modeling-critical fields, price $71–$2,146, trip 0–57d, lead 0–200d, 280 distinct routes. err.log unchanged since May 29; backup self-refreshed to 160,369, matching the live DB exactly.

**The headline is runtime: ~10 minutes vs the usual 3–5 hours, for the highest offer count on record.** Run 38 did 5,327 offers in 4h48m; today did *more* (5,361) in under 10. Same 4,200 api_calls, all clean, no retry backoff (0 failures, DNS fully healthy — only ~1 retry the whole run). The most likely read is simply a fast-API day with zero failure-retry stalls, and the data is complete and valid (highest count ever, audit clean, 280 routes present), so this is not a data-quality concern — but a 25–30× swing is large enough to keep an eye on; if it persists it's worth confirming the collector isn't short-circuiting calls. Flagging, not alarming.

**Second straight zero-failure day; DNS trickle stays dead.** Failures: 165 → 5 → 10 → 0 → **0** (Jun 10–14). Two clean days running confirms the June 8–12 `NameResolutionError` cluster was transient local flakiness — end-of-run retry sweep remains a nice-to-have, not urgent.

**Fourth straight post-expansion volume high.** Line: 5,089 → 5,165 → 5,327 → **5,361**. The 300-route set keeps climbing. Top price $2,146 (SFO→TYO, AA, economy) — within normal range, no business-class outlier.

(Minor: start 13:00:05 UTC — the ~12-min-late drift noted since June 8 was *not* present today; run fired on schedule. Project otherwise paused for the learning-project detour; collector remains fully hands-off.)
