# Independent Review of `data_model_audit_2026-06-01.md`

**Reviewer:** second-pass analyst (Opus 4.8). **Date:** 2026-06-01.
**Method:** every claim in the prior audit was treated as an unverified hypothesis
and re-run from the live DB (97,608 rows). Analysis only — no code or data changed.

**One-line verdict:** the audit's *measurements* mostly hold up (and its headline
XGB>LR result is more robust than it claimed), but its *recommendations* are
partly wrong — the "duration is a big lever" claim is overstated, and, more
importantly, **the entire XGB-wins / features-get-us-to-0.12 story is an
in-distribution result that does NOT survive the deployment-like split.** The
real open question is the evaluation regime, not the model or the features.

Facts and interpretation are separated. My own uncertainties are flagged in §D.

---

## A. Prior claims — confirmed, corrected, or refuted (with evidence)

### Confirmed
1. **Reproduction is exact.** Chronological split: LR 0.166 / XGB 0.181.
   Grouped-random (seed 42): LR 0.180 / XGB 0.141. Matches the audit to 3 dp.
2. **XGB > LR under grouped-random is robust — *more* than the audit showed.**
   The audit reported a single seed. Across **8 seeds**: LR 0.179±0.003,
   XGB 0.139±0.002, XGB wins **8/8**, mean gap 0.039. **5-fold GroupKFold:**
   LR 0.179±0.003, XGB 0.139±0.002, XGB wins **5/5**. Not noise.
3. **Lead-time confound is real.** train lead 0–72, val 50–113, test 91–213
   (minimal overlap). `captured_at` spans only 22 days (2026-05-10..06-01) while
   departures run to 2026-12-31, so late departures currently exist *only* at
   long lead — confirming the young-data mechanism the audit described.
4. **The task is near-deterministic given coarse itinerary keys.** Oracle MAPE
   from predicting group means: flight-key 0.032; route+date+airline+stops 0.033;
   route-only 0.192. So large headroom exists below today's ~0.14–0.18.
5. **MAPE is safe here.** Price min $35, p1 $129, only 0.05% < $50. Low-denominator
   instability (an audit open question) is a non-issue.

### Corrected / challenged
6. **The audit's "3 unused high-corr features are a big lever" is overstated.**
   Its §5 headroom (duration alone → 0.173) is real but *misleading*: it omitted
   route/airline, so `duration` was acting as a **route/distance/airline proxy**.
   Added on top of the full feature set (corrected, grouped seed 42), the trio
   `duration`+`return_transfers`+`trip_duration_days` moves **XGB 0.142 → 0.136**
   and **LR 0.180 → 0.179** — a small gain, not the implied transformation.
   *(Caution: my first attempt to show this was itself wrong — see §C-3 — the
   corrected numbers here passed an A-reproduces-0.142 sanity check.)*
7. **"XGBoost is the better model" is regime-dependent and does NOT generalize
   to the deployment-like split.** This is the key correction. Under the
   chronological split, the rich-feature and native-categorical configs that win
   in-distribution **collapse**:

   | Config | Grouped-random | Chronological |
   |---|---|---|
   | baseline-v1 | LR 0.180 / XGB 0.142 | LR 0.166 / XGB 0.178 |
   | + date + route×month + extras | LR 0.160 / XGB **0.130** | LR 0.161 / XGB 0.175 |
   | native-cat XGB | **0.122** | 0.164 |

   Native-cat XGB looks like it hits the 0.12 target — but only when val flights
   resemble train flights. For genuinely later-departing flights it is 0.164,
   *worse than plain baseline LR (0.166)*. So the audit's optimism ("XGB + features
   → 0.12") is only true in-distribution; for temporal generalization, model and
   features barely matter and everything plateaus at ~0.16–0.18.

### Note
8. The audit already *retracted* its earlier "signal is essentially linear"
   claim. That retraction is correct **in-distribution** (trees win there), but
   the linear-vs-tree question is itself split-dependent: under the temporal
   split LR ties or beats XGB. Neither "linear" nor "trees" is universally right.

---

## B. Holes / risks the prior analysis missed

1. **Within-flight price is essentially constant — the dataset is mostly
   re-collected duplicates.** Within each flight key, price CV: **median 0.000,
   77% of flights have CV = 0**, 82% < 0.02. The ~6.7×/flight re-collection adds
   almost no new information; **effective sample ≈ 14,613 flights, not 97,608**.
   Consequences the audit didn't draw: (a) the "price vs lead_time" curve in the
   audit is a *between-flight* artifact, not a booking curve — `lead_time` carries
   little within-flight signal; (b) any **random** (non-grouped) split would leak
   massively via identical-price twins — grouped/chronological splits are
   mandatory; (c) variance/CI estimates should be computed at the flight level.
2. **The grouped-vs-chronological gap is the whole story, and it's a *regime*
   question, not a "rigged split."** The audit framed the chronological result as
   an artifact to dismiss. In fact it measures a different and possibly
   deployment-relevant thing (temporal/extrapolation generalization), and all the
   feature/model gains evaporate under it (§A-7). Optimizing on grouped-random and
   shipping for temporal use would be a silent failure.
3. **The feature pipeline is alignment-fragile.** `build_features` calls
   `df.merge(...)`, which **resets the index**, and it also `dropna`s rows. Any
   downstream code that attaches new features by the original index will silently
   misalign targets/features. I hit exactly this bug mid-review (baseline jumped
   to 0.57 — an instant tell). The current code only survives because `prepare_xy`
   keeps X and y together. **This will corrupt the planned baseline-v2** unless
   `build_features` is made index-safe first.
4. **`route_mean_log_price` is an in-fold target encoding** (each train row is
   included in its own route's mean). No cross-val leakage, but it inflates train
   fit, and it's strong enough that XGB doesn't need it at all (dropping it:
   XGB 0.142 → 0.142; LR 0.180 → 0.208). Worth replacing with out-of-fold/smoothed
   encoding if kept.
5. **The 0.032–0.033 oracle is an in-sample memorization ceiling, not an
   achievable floor for novel route+dates.** Only 5.2% of grouped-val rows share
   an exact route+date with train, so the model must generalize across dates; the
   realistic floor for novel dates is unknown and the observed temporal plateau
   (~0.16) suggests it is much higher than 0.033.

---

## C. What actually moved the metric (corrected, grouped seed 42, XGB n400/d6/lr.05)

| Change | LR | XGB |
|---|---|---|
| baseline-v1 (sanity) | 0.180 | 0.142 |
| + duration/returns/trip_dur | 0.179 | 0.136 |
| + fine date (day-of-month, week-of-year, dep ordinal) | 0.180 | 0.137 |
| + route×month target-encode | 0.161 | 0.141 |
| + all of the above | 0.160 | 0.130 |
| native-categorical XGB (raw origin/dest as categories, no route_mean) | — | **0.122** |

Reading: the levers are **route×month encoding** (helps LR most), **date
granularity**, and **native categorical route encoding** (helps XGB most) — *not*
the itinerary-duration features the audit highlighted. All gains are
in-distribution only (§A-7).

---

## D. My own uncertainties / limits

- The chronological split is deterministic, so §A-7 is single-shot (no seed band);
  only the grouped result has 8-seed/5-fold CIs.
- `route×month` encoding used a quick fallback scheme, not cross-fitted — possibly
  optimistic.
- Native-cat XGB params were not tuned; treat 0.122 as indicative, not final.
- I did not audit `dedupe.py`, the test set, or non-economy data (all rows are
  `flight_class=0`, `currency=usd`).
- All metrics are MAPE on the raw (offer-level, re-collection-inflated) rows.

---

## E. Recommended plan (prioritized, de-risked)

**P1 — Settle the evaluation regime before any modeling.** This is the real
fork, and it dominates model/feature choices:
  - Write down the deployment query precisely. If it's "price a flight similar to
    recently-seen ones" → grouped-CV is the right metric → native-cat XGB already
    reaches ~0.122. If it's "price genuinely future/long-lead flights" → the
    binding constraint is **temporal extrapolation**, where today nothing beats
    ~0.16 and LR ≈ XGB.
  - Build and **report both** evals every run: (a) GroupKFold by flight,
    (b) a `captured_at`-forward split (train on earlier capture dates, test on
    later captures of overlapping departures) to isolate *temporal* generalization
    from the lead-time-range confound.
  - Validation experiment: confirm whether the lead-time confound is the cause by
    restricting train/val to a shared lead-time band and re-comparing models.

**P2 — Fix data accounting.** Decide offer-level vs flight-level modeling;
collapse or weight the near-duplicate re-collections (77% CV=0); drop/handle the
1,104 exact dups. Recompute all metrics on the de-duplicated basis and report
effective N. Many current numbers may shift.

**P3 — Harden `build_features` (before baseline-v2).** Make it index-stable
(carry the offer `id` / avoid silent reindex) so feature additions can't
misalign. Add an assertion that `len(X)==len(y)` and indices match. (Implementation
task; flagged, not done here.)

**P4 — Feature work, validated under the chosen regime.** Add `route×month`
encoding (out-of-fold), date-granularity features, and native categorical route
encoding — the levers that actually moved XGB to 0.122 in-distribution. Include
duration/returns/trip_duration but expect only ~0.005. **Gate every addition on
the temporal eval, not just grouped-CV.**

**P5 — Model choice follows the regime.** In-distribution: native-categorical
XGBoost, robustly > LR (8/8, 5/5). Temporal: LR ≈ XGB ≈ 0.16; prefer the simpler
LR and revisit once `captured_at` history is long enough to remove the lead-time
confound (weeks-to-months of further collection).

**P6 — Re-examine target & metric.** Confirm offer-level price is the intended
target; quantify the achievable floor for *novel* route+dates (not the in-sample
0.033); consider a median-based error metric as a robustness cross-check.
