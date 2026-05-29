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
