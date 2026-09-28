# Spec review A — data & analysis (DATA-001..003, ANL-001..004)

**Reviewer:** spec reviewer A (read-only)
**Date:** 2026-09-28
**Suite state:** `uv run pytest -q` → **82 passed** (green).
**Scope:** DATA-001, DATA-002, DATA-003, ANL-001, ANL-002, ANL-003, ANL-004 — all currently `passes: true`.

All checks below were re-derived independently from the cached raw JSON
(`data/scores/results.json`, `data/tracks/replay_*.json`,
`data/weather_era5_oschatz.json`) rather than from the pipeline's own outputs.

## Verdicts

| Spec | Verdict | One-line reason |
|---|---|---|
| DATA-001 | **PASS** | 17 flights / 38 pilots / 12,562 / rank 22 all re-derived from the raw tree; four tests cover it directly. |
| DATA-002 | **PASS-WITH-GAPS** | Implementation is correct for all 17 groups (incl. multi-start), but nothing in `tests/` asserts leader presence or multi-start isolation beyond one round. |
| DATA-003 | **PASS-WITH-GAPS** | Every flight maps to a weather row in-window, but `cape` is null for all 144 hours and the wind cross-check is a manual 2-flight script with no test and no persisted artefact. |
| ANL-001 | **PASS-WITH-GAPS** | Laps/speed/scores reconcile for all 34 rows, but they are *copied* from the API (near-tautological test), the spec's "~3% of API distance fields" check does not exist and is unsupportable, and `PERIMETER_M = 1050` contradicts ADR-008's 1,690 m. |
| ANL-002 | **PASS-WITH-GAPS** | The claimed sum property holds *exactly* (error 0.0 s) and speedruns are excluded — but the named test does not exist. |
| ANL-003 | **PASS-WITH-GAPS** | The headline score correlation is computed over **all 17** rounds (incl. the 3 speed sprints) while the report caption states "n ≈ 14 distance rounds"; the spec step requires 14. No test. |
| ANL-004 | **PASS-WITH-GAPS** | Ordering and both series verified correct, but untested, and the prose calls Round 7 "a first-day flight" when it is 5 Aug (day 3 of 6). |

---

## DATA-001 — standings and heat/group tree — PASS

**Verified independently** from `data/scores/results.json`:

- Bill appears in exactly 17 groups; 38 distinct `userGuid`s in the tree.
- Total under the drop-worst-round rule = **12,562**; rank by total = **22**; winner total = **15,449**. All three match PRD §2/§7 and the report.
- Landings: 600 on 14 rounds, 0 on rounds 4/10/16.

**Test coverage** (`tests/test_data_reconciliation.py:28,33,38,43,67,74`) covers total, rank,
flight count, the 14 clean landings, the per-round score list and the three
zero-landing speedruns. This is the best-covered spec in the batch.

**Minor note (not a gap in the spec):** `scripts/fetch_data.py:13` hard-codes an
absolute output path (`/Users/twm/code/projects/...`), unlike every other script
which derives `ROOT` from `__file__`. Re-fetch is not reproducible on another
machine. Fix: `ROOT = Path(__file__).resolve().parent.parent`.

## DATA-002 — per-group replay tracks, scoring flight, same-air leader — PASS-WITH-GAPS

**Verified independently:**

- All 17 `data/tracks/replay_<gid>.json` exist, and Bill's `userGuid` is present in every one.
- `data.full_tracks_for_round(n)` returns non-empty Bill **and** leader rows for all 17 rounds.
- **Multi-start handling is correct.** `data.scored_start` (`scripts/build/data.py:479`)
  picks the STA that begins the longest run. I compared its T0 against the
  authoritative `gpsTriangleStats` entry with the largest `timeElapsedSeconds`
  for Bill and the leader in all 17 rounds: **0 mismatches out of 34** (max
  delta < 2 s). Multi-start is real in this data — 101 of 225 pilot-flights have
  more than one STA, and rounds 1/5/7/9 have Bill or the leader at 3–6 STAs.
- Leader rows in `analysis/per_round_metrics.csv` reconcile to the results tree
  on laps, `speed`, `rawScore` and `score` (0 mismatches over all 34 rows).

**Gap 1 — the spec's stated test does not exist.** Step 3 claims "Bill and leader
present in all 17 groups; parsed laps/speed reconcile to the results tree".
`tests/test_data_reconciliation.py` only checks *Bill*, and only via
`index.json` (`:50`, `:58`). Nothing asserts the leader at all, and
`tests/test_shared_foundation.py:56` exercises `full_tracks_for_round` for
**round 6 only** — a round where neither pilot is a multi-start case, so the
hardest part of DATA-002 is untested.

*Fix:* add to `tests/test_data_reconciliation.py`:
```python
def test_leader_laps_and_speed_reconcile():   # loop 1..17, leader = max rawScore
def test_bill_and_leader_tracks_present_all_rounds():  # full_tracks_for_round(n) non-empty
def test_scored_start_matches_api_scored_stats():
    # for each round, each of {bill, leader}:
    #   best = max(pilot["gpsTriangleStats"], key=lambda s: s["timeElapsedSeconds"])
    #   assert scored_start(pilot["events"]) == _parse_iso(best["flightStart"])
```
The third one is the valuable assertion — it is an independent check against the
API's own scoring record, and it would have caught a regression that
`test_scored_start_isolates_longest_run_window` cannot.

**Gap 2 — silent leader fallback.** `scripts/build/data.py:582-584` matches the
leader by lowercased `"name surname"` and falls back to `lead_rows = []` when no
match is found, so a name-formatting change would silently blank the leader from
every full-resolution chart instead of failing.
*Fix:* match on `userGuid` (store it in `round_data/index.json` alongside
`leader_name`), or raise instead of returning `[]`.

## DATA-003 — ERA5 weather enrichment — PASS-WITH-GAPS

**Verified independently:** all 17 rows of `analysis/weather_per_flight.csv`
carry a `wx_hour_local` inside `2026-08-03T00:00 .. 2026-08-08T23:00`, and the
nearest-hour rounding in `scripts/weather_per_flight.py:44-57` is correct
(e.g. R01 12:55 → 13:00, R02 16:25 → 16:00, R14 14:30 → 15:00). Local-time
conversion uses the payload's own `utc_offset_seconds` (7200), which is the
right way to do it.

**Gap 1 — `cape` is null for every hour.** Spec step 1 names CAPE as one of the
fetched variables. The ERA5 archive returns the key but all 144 values are
`None`, so the `cape` column in `weather_per_flight.csv` is empty on all 17
rows. `scripts/analyse_weather.py:115` already prints "CAPE all-null in ERA5
archive", so this is known but the spec still claims it. Nothing reader-facing
breaks (`cape` never reaches the report — 0 occurrences in the HTML), but the
spec overstates what was obtained.
*Fix:* amend DATA-003 step 1 to "(wind, temp, cloud, radiation; CAPE requested
but returned null by the ERA5 archive — boundary-layer height used as the
secondary thermal proxy)", and drop the always-empty `cape` column from the CSV
writer (`scripts/weather_per_flight.py:130`).

**Gap 2 — the wind cross-check is not a test and covers 2 of 17 flights.**
`scripts/gps_wind_check.py` is a manual print-only script; the ERA5 comparison
values are **hard-coded** at `:19` (`{"Heat 12 (R12)": (16.9, None), "Heat 17
(R17)": (8.3, None)}`) rather than read from `weather_per_flight.csv`, so it
will silently go stale if the weather is re-fetched. Its output is not written
to `analysis/` and nothing asserts on it. Running it today: R12 GPS/ERA5 ratio
**1.14** with direction 285° vs ERA5 262° (good); R17 ratio **1.40** with
direction 135° vs ERA5 72° (**63° apart** — the speed is the right order of
magnitude, the bearing is not).
*Fix:* read the ERA5 row from `weather_per_flight.csv` instead of the hard-coded
dict, run it over all 14 distance rounds, write
`analysis/wind_crosscheck.csv`, and add
`test_era5_wind_within_order_of_magnitude_of_gps_drift` asserting
`0.4 <= gps_kmh / era5_kmh <= 2.5` per round. Add
`test_every_flight_has_weather_row_in_event_window` for step 2.

## ANL-001 — per-round metric bundle — PASS-WITH-GAPS

**Verified independently:** every one of the 34 rows in
`analysis/per_round_metrics.csv` matches the results tree on `laps`,
`avg_speed_kmh` (within 0.11 km/h of `speed * 3.6`), `rawScore` and `score` — 0
mismatches. Entry metrics also reconcile to the API (`startEntryAlti` 386.3 →
`entry_alt_m` 386.3; `startEntrySpeed` 20.8487 m/s → `entry_speed_kmh` 75.1).

**Gap 1 — the reconciliation is near-tautological.** `laps` and
`avg_speed_kmh` are *read* from the API (`scripts/compute_metrics.py:319-321`:
`"laps": st["laps"]`, `"avg_speed_kmh": st["allTrianglesAvgSpeed"] * MS_TO_KMH`),
not computed from the track. The tests at
`tests/test_data_reconciliation.py:50,58` therefore prove the values survive the
CSV/JSON round-trip, not that any track-derived computation is right. This is
weaker than the spec's wording ("computed laps and avg speed equal the
authoritative results").
*Fix:* reconcile a genuinely track-derived value. Both are available:
`len(round_data[role]["lap_durations_s"]) == official laps`, and
`1689.9 * laps / aloft_time_s * 3.6 ≈ official speed_kmh`. I confirmed the
second holds to 0.1 km/h on all 17 rounds.

**Gap 2 — step 2's distance check does not exist and cannot be done as written.**
Nothing in `scripts/` or `tests/` references `distanceCovered`, `lapStats` or
`taskLength`. Inspecting the raw replays, `gpsTriangleStats[i]["distanceCovered"]`
and `["distance"]` are **0** and `lapStats` is **empty** for every flight, so
"distances within ~3% of API distance fields" is unsupportable against those
fields. (The only non-zero API distance is the flight-level `distanceSummary`;
a naive haversine sum over the full tail runs 2–19% above it, so that is not a
3% check either.)
*Fix:* replace the step-2 wording with the check the data does support — the
API-implied scoring lap distance. `allTrianglesAvgSpeed * timeElapsedSeconds /
laps = 1689.9 m` for **all 17** of Bill's rounds, exactly `350 * (2 + 2√2)`.
Assert that, which validates the course geometry and the unit conversions
together.

**Gap 3 — `PERIMETER_M = 1050` contradicts ADR-008 (real bug).**
`scripts/compute_metrics.py:32` (and the docstring at `:16`) and
`scripts/trajectory_poc.py:35` use `3 * 350 = 1050 m` as the lap perimeter. ADR-008
(`docs/ADR.md:56-61`) explicitly *rejects* "equilateral 350 m legs" and fixes the
perimeter at ~1,690 m, and the API confirms 1689.9 m exactly (above).
Consequences in `analysis/per_round_metrics.csv` / `.md`:
- `fastest_clean_lap_speed_kmh` is understated by ×0.621 (R1 Bill reads 32.5 km/h;
  the true ground speed over that 116 s lap is ≈ 58.8 km/h),
- `fastest_clean_lap_eff_vs_1050` is inflated by ×1.61 (R1 reads 1.81, i.e. "81%
  extra distance flown"; against the correct perimeter it is ≈ 1.12).

**Blast radius is limited:** neither column reaches the report ("fastest clean
lap" has 0 occurrences in the HTML), and `line_eff_ratio_bill_vs_leader` is a
Bill/leader *ratio* so the wrong denominator cancels. The headline cruise-speed
numbers in PRD §7.1 come from `phase_summary.json`, not from these columns, and
are unaffected.
*Fix:* set `PERIMETER_M = 350 * (2 + 2 * math.sqrt(2))` in both scripts (or
import `data.course_geometry(...)["perimeter_m"]`), rename the column to
`fastest_clean_lap_eff_vs_perimeter`, regenerate the CSV/MD, and add a test
pinning `PERIMETER_M` to the API-implied 1689.9 m.

**Related stale geometry (same root cause):** `scripts/analyse_weather.py:87-94`
(`geometry()`) prints "leg length 350 m; **equilateral**" and a 120°-apart leg
convention, and the report captions say "**350 m-leg** course" (2 occurrences).
Per ADR-008, 350 m is the radius / half-base and the legs are ≈ 495 m. Worth a
wording fix in both places for consistency with the ADR (the report caption is
reader-facing; strictly an RPT-011 concern, flagged here because the cause is shared).

## ANL-002 — flight-phase decomposition — PASS-WITH-GAPS

**Verified independently** from `analysis/phase_perround_raw.json`:

- Rounds present = `[1,2,3,5,6,7,8,9,11,12,13,14,15,17]` — exactly 14, speedruns
  4/10/16 excluded, matching `phase_summary.json.meta.excluded_speedruns`.
- **`max |lap_t − (cruise_t + turn_t + climb_t)| = 0.0 s`** over every lap of
  both pilots in all 14 rounds.
- **`Σ lap_t == aloft_time_s` exactly** (0.0% error) for all 28 pilot-rounds, and
  `aloft_time_s` matches the API's `timeElapsedSeconds` (R1: 1712 vs 1711.951).
- The aggregate block reconciles to PRD §7 to the last decimal: cruise 61.85/67.40
  (§7.1 "61.9 vs 67.4"), glide 9.35/10.31, climb gain 40.66/63.09 (§7.2 "40.7 vs
  63.1"), radius 39.36/33.24, climb time 287.0/402.2, entry 70.83/94.53 with a
  49.2 km/h margin (§7.3), mean lap deficit 21.98 s with a 90.2% straight share
  (§7.1 "~90% of his 22 s/lap"), turn deficit 2.12 s and +15.4 m/lap (§7.4),
  `pace_effect_laps` 2.67 (§7.1 "≈ +2.7"). I re-derived the cruise, climb-count
  and climb-time aggregates from the `per_round` arrays and they match.

**Gap — the spec's named test does not exist.** No test in `tests/` touches
`phase_summary.json` or `phase_perround_raw.json`. The property is also true *by
construction* (laps partition the aloft window), so the assertion is a regression
guard rather than an independent check.
*Fix:* add `tests/test_phase_decomposition.py` with:
```python
def test_phase_times_sum_to_lap_time()        # abs(cruise+turn+climb - lap_t) < 1.0
def test_lap_times_sum_to_motor_off_duration()# Σ lap_t == aloft_time_s within 2 s
def test_speedrun_rounds_excluded()           # rounds == [1,2,3,5,6,7,8,9,11,12,13,14,15,17]
def test_aloft_time_matches_api_elapsed()     # independent: vs gpsTriangleStats timeElapsedSeconds
def test_phase_cost_ranking_is_cruise_climb_entry_turn()  # PRD §7.9
```
The fourth is the one that is not true by construction and is worth most.

## ANL-003 — condition-dependence analysis — PASS-WITH-GAPS

**Gap 1 (highest severity in this batch, reader-facing) — the headline
correlation is n = 17, not n = 14, and the report says otherwise.**

- `scripts/analyse_weather.py:118` computes the normalised-score target over
  `rows` (**all 17 flights**, including the three one-lap speed sprints whose
  normalised score is produced by a different scoring model and whose
  within-group ranks are 28/29/29). Only the `laps` / `speed_kmh` /
  `laps_deficit` targets use the 14 distance rounds. `analysis/weather_correlations.csv`
  is honest about this — the row is labelled `"normalised_score (all 17, …)"`,
  ρ = **0.608**, `n` = 17.
- `scripts/build/pages/overview.py:608` then takes `wx = ctx["weather"]`
  **unfiltered** (contrast `:367`, where the progression block correctly does
  `[r for r in ctx["weather"] if r.get("task_type") == "distance"]`). So the
  "Conditions Dependence" scatter plots **17** points.
- The same block states "Spearman ρ ≈ +0.6" (`:627`) and, three lines later,
  "Read this as suggestive only - n ≈ 14 distance rounds" (`:636`). The +0.6 is
  the n = 17 number. PRD §7.8 carries the same "ρ≈+0.61 … (n≈14)".
- Recomputed distance-only (n = 14): **Spearman ρ = 0.543, Pearson r = 0.425**.

The qualitative conclusion survives (thermal strength associates positively with
relative standing; wind does not), but the figure and its caption disagree, and
the spec step explicitly requires the 14 distance rounds.
*Fix:* filter to `task_type == "distance"` at `overview.py:608`; change "ρ ≈ +0.6"
to "ρ ≈ +0.5" (or quote 0.54 / 0.52); add the distance-only score target to
`analyse_weather.py` and to `weather_correlations.csv`; update PRD §7.8. Then
add `test_conditions_correlation_uses_14_distance_rounds` asserting the scatter's
point count is 14 and that the quoted ρ matches the n = 14 CSV row.

**Gap 2 — no test at all.** Nothing asserts the n, the subset, or the presence
of the "suggestive, not significant" caveat that step 2 requires. The caveat *is*
present in the report (`overview.py:636`) and in the script header, so step 2's
substance is met — it is just unguarded.
*Fix:* `test_conditions_caveat_present` (assert "suggestive" and "not a
significance claim" appear next to the conditions figure).

**Gap 3 (minor) — `sig_flag` is computed from Pearson only.**
`scripts/analyse_weather.py:135,142` pass `pr` to `crit_r`, so ρ = 0.608 (n = 17,
critical |r| ≈ 0.482) is left unflagged while its Pearson twin (0.405) is below
the threshold. Conservative in the right direction, but the column name implies
it covers the row. *Fix:* emit `sig_flag_pearson` and `sig_flag_spearman`, or
flag on `max(|r|, |ρ|)`.

## ANL-004 — week-long progression — PASS-WITH-GAPS

**Verified independently:** `analysis/weather_per_flight.csv` is already in
chronological order (`start_datetime_local` sorted, 2026-08-03 12:55 →
2026-08-08 13:25), every row carries both `normalised_score` and `laps`, and
`scripts/build/pages/overview.py:367-369` correctly filters to the 14 distance
rounds and re-sorts by `start_datetime_local` before plotting both series. Both
steps of the spec are genuinely satisfied.

**Gap 1 — untested.** No test asserts chronological ordering or that both series
are present for all 14 distance rounds.
*Fix:* `test_progression_is_chronological_over_14_distance_rounds` — assert the
filtered list has 14 entries, that its `start_datetime_local` values are sorted,
and that neither series contains `None`.

**Gap 2 (minor, factual) — "first-day" is wrong.**
`scripts/build/pages/overview.py:382-384`: "his two strongest normalised results
(Rounds 7 and 17) are a first-day and a last-day flight". Round 7 is
**2026-08-05**, day 3 of the six-day event (day 1 is 3 Aug, rounds 1–3). Rounds 7
and 17 are indeed his best two (998 and 999).
*Fix:* "a mid-week and a last-day flight".

---

## Cross-cutting observations

1. **Five of the seven specs name a test that does not exist.** Only DATA-001 (and
   the Bill half of ANL-001) is actually covered by `tests/`. The specs are
   flipped to `passes: true` on the strength of work that was verified
   interactively, not by an assertion in the suite. Everything I re-derived did
   hold, so this is a coverage/regression-guard problem, not a correctness one —
   but the SPEC currently overstates the verification.
2. **The strongest available assertions are independent API cross-checks** that
   nobody is making yet: `scored_start` vs the scored `gpsTriangleStats` entry
   (DATA-002), `aloft_time_s` vs `timeElapsedSeconds` (ANL-002), and the
   API-implied 1689.9 m lap distance (ANL-001). Each is a one-line assertion over
   cached data and each catches a class of bug the current tests cannot.
3. **`1050 m` vs `1690 m` is a live inconsistency across the repo**
   (`compute_metrics.py:32`, `trajectory_poc.py:35`, `analyse_weather.py:87`,
   two report captions, PRD §3) against a standing ADR (ADR-008) and against the
   API. Worth fixing everywhere in one pass.
