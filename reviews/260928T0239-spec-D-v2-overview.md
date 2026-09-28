# Spec review D — RPT-017/018/019/021/022/023/024/025

**Reviewer:** spec reviewer D (read-only)
**Date:** 2026-09-28T02:39
**Artefacts reviewed:** `docs/SPEC.json`, `docs/PRD.md` §8, `docs/ADR.md`, `tests/`, `scripts/build/`,
built output `report/gps-triangle-world-masters-oschatz-2026.html`.

**Build state:** `uv run pytest -q` → **82 passed**. The committed report is byte-identical to a
fresh `assemble.build_html()` (2,839,459 bytes), so the output reviewed is the current build.

## Verdicts

| Spec | Verdict | One-line reason |
|---|---|---|
| RPT-017 | PASS | Nav title, `<title>`, Home h1 all read "GPS Triangle World Masters, Oschatz 2026"; Bill named on Home; file and gh remote renamed; old title absent. |
| RPT-018 | PASS | All 17 rounds render the stacked dual-panel on one shared x-axis, single title, legend-only, solid green/blue, smoothed speed, speed rounds fitted to flight duration. |
| RPT-019 | PASS-WITH-GAPS | No remote font requests and 174 KB inlined (in budget), but ~101 KB of it is redundant: the Source Sans 3 file is embedded 4× identically and a Spectral italic face is embedded but never used. |
| RPT-021 | PASS | All 17 rounds carry the 2×4 dashboard (violin, 4 bullets to spec, laps bars, rank text, wind card, solar bar) + square-swatch colour key; values reconcile to `per_round_metrics.csv` / `weather_per_flight.csv`. |
| RPT-022 | PASS-WITH-GAPS | Overall Read lead, section index and the four Title-Case sections are exactly in PRD order with the insights in the specified order; but the entry-speed/entry-altitude grouped bars carry 2 of 3 series and the Landings callout has neither visual nor source link. |
| RPT-023 | PASS-WITH-GAPS | Log-y-only density renders, floored above the axis, captioned, medians (46.8 / 37.0 m) reconcile exactly to `data.pooled_distance_from_course()`; but the lead calls the winner "bimodal" and the plotted density shows a single mode plus a heavy shoulder, not two modes. |
| RPT-024 | PASS | Both unfilled curves + dashed median markers, captioned; medians 38.0 / 29.2 m and "~30% wider" reconcile exactly to `data.pooled_turn_radius()` (ratio 1.301). |
| RPT-025 | FAIL | The report names only the Pike Paradigm; "Phantom", "SkyTouch" and "Apollo" appear **zero** times in the whole 2.8 MB file, so "the top field is a mix (Pike Paradigm, Phantom, SkyTouch, Apollo)" is asserted but never shown, and none of the cited specifics found in `analysis/airframe_note.md` are carried over. |

---

## RPT-017 — Retitle — PASS

Evidence (built output): `<title>` = `GPS Triangle World Masters, Oschatz 2026`; `.topnav-title`
identical; `#page-home` `<h1>` identical; Home body opens "This is a coaching analysis of **Bill
Maisey's** (Anglesey MAC) performance…". `"Bill's GPS Triangle Analysis 2026"` occurs 0 times.
Output path `scripts/build/assemble.py:25` → `report/gps-triangle-world-masters-oschatz-2026.html`.
`git remote -v` → `https://github.com/tmaisey/gps-triangle-world-masters-oschatz-2026.git` (correct
account after the twm105→tmaisey rename).

Test coverage: `tests/test_html_structure.py:54` (nav title) and `:149` (old title absent, whole
document) cover most of step 2. **Gap (minor):** no test asserts the **Home h1** specifically, which
step 2 names explicitly — `test_title_text_present` only inspects `.topnav-title`.

*Fix:* add one assertion to `test_title_text_present`:
`assert soup.select_one("#page-home h1").get_text(strip=True) == "GPS Triangle World Masters, Oschatz 2026"`.

## RPT-018 — Energy Management dual-panel — PASS

Evidence (`scripts/build/charts.py:1040-1203`, verified in output for all 17 rounds):
one `<svg>` per round at `#r{n}-fig-energy`, each with `Altitude (m)` and `Ground speed (km/h)`
rotated panel labels, exactly one `>Energy Management</text>`, 4 polylines (2 pilots × 2 panels),
no dasharray, strokes `#86BC25` / `#00A3E0`. Panels are laid at 80 % / 20 % of the plot box with a
30 px gap (`charts.py:1103-1109`) so they cannot overlap; one shared x-tick row and one x-axis title
below the bottom panel (`charts.py:1162-1168`). Text content of round 6 is legend-only — no line-end
labels. Speed smoothing = rolling mean 5 (`speed_smooth=5`). Traces are clipped at the last
turn-point crossing (`full_tracks_for_round(n, clip_to_last_tpc=True)`, `charts.py:1069`).
Speed-round exception verified: round 4 x-ticks run `0 … 0.8` min (fitted), rounds 1/2/…/17 run
`0 … 30`. No standalone altitude figure remains anywhere (`fig-altitude` = 0 hits).

Test coverage: `tests/test_shared_foundation.py:75` checks round 6 only; `tests/test_content_present.py:61`
checks the figure exists on all 17. **Gap (minor):** nothing tests the RPT-018 speed-round exception
(fitted x-axis) or the "legend only, no line-end labels" rule.

*Fix:* extend `test_energy_management_two_panels_both_pilots` with a speed-round case, e.g.
`svg = charts.energy_management(data.load_round(4)); assert ">30</text>" not in svg` (axis fitted,
not the 30-min window), and assert the pilot names appear exactly once each (legend only).

## RPT-019 — Fonts inlined — PASS-WITH-GAPS

Evidence: 8 `@font-face` rules, all `src:url(data:font/woff2;base64,…) format('woff2')`; 0 occurrences
of `fonts.googleapis.com` / `fonts.gstatic.com`; no `<link rel=stylesheet>`; the only remote `http(s)`
URLs in the file are the SVG namespace and 8 legitimate citation links. Total base64 font payload
≈ **174 KB**, inside the "~100-200 KB" budget. Fallback stacks retained (`design.py:47-51`).

**Gap 1 (waste, ~86 KB):** `scripts/build/assets/fonts/SourceSans3-{400,500,600,700}.woff2` are four
byte-identical 28,792-byte files (identical base64 md5 in the output) — one variable font saved four
times and declared under four fixed weights. Three copies are dead payload.

**Gap 2 (spec wording, ~15 KB):** `Spectral-400i.woff2` is embedded (`design.py:68`) but italic is
never used — `italic` appears exactly once in the whole document, inside its own `@font-face` rule
(`<em>` count 0; the 51 `<i>` elements are colour swatches with no text). The spec says "only the
weights used".

Together the payload could drop from ~174 KB to ~74 KB with no visual change.

*Fix:* in `design.py`, collapse the Source Sans 3 entries to a single face with a weight range
(`font-weight: 400 700`) pointing at one file, and drop the `Spectral-400i` entry (or add an italic
usage if one is intended). Then tighten `test_fonts_inlined_no_remote_link` to assert the payload
budget and no duplicate `src` hash, e.g. count distinct base64 blobs and
`assert total_font_bytes < 200_000`.

Test coverage: `tests/test_shared_foundation.py:168` and `tests/test_html_structure.py:102` cover
"no remote font / fonts are data URIs". **Gap:** neither asserts the size budget nor "only the weights
used" — which is why the duplication passed unnoticed.

## RPT-021 — Per-round dashboard — PASS

Verified across **all 17** rounds in the built output:
- 8 `.dash-cell`s in the specified order — row 1 `Group score`, `Entry speed`, `Entry altitude`,
  `Average speed` (`Single-lap speed` on rounds 4/10/16); row 2 `Laps`, `Within-group rank`, `Wind`,
  `Solar radiation`. Grid is `repeat(4, minmax(0,1fr))` (`design.py:371`) with a full-width divider,
  so the bottom row aligns to the top row's columns.
- Score violin: grey symmetric KDE (`fill="#D0D0CE"`), blue `Winner 1000` line at the top, green
  `Bill <score>` line over it (`dashboard.py:96-155`).
- Bullets: grey track top = 120 km/h / 400 m regs caps from the task, else a padded ceiling
  (`dashboard.py:365-377`); leader = blue line; Bill = green fill; Bill's value in green
  (`BILL_INK` `#5C8F10`) **to the right** of the bar; no amber/orange and no field density on the
  bullets (`dashboard.py:48-89`).
- Laps paired bars with value labels on top and no axis; rank as `N/field` text; wind compass with
  the arrow drawn from the source bearing **inward** plus km/h and a 16-point label; solar bar
  height and colour normalised across all 17 rounds, pastel-yellow → deep red, no scale.
- Colour key top-right (`justify-content: flex-end`), **square** 11×11 px swatches with 2 px radius
  (`design.py:368`), naming Bill Maisey, `Round Leader (<actual name>)` — verified different per
  round (e.g. R6 Oliver Ladach, R11 DANIEL AEBERLI) — and `Regs limit / Other pilots`.
- Placement: the dashboard is the first section after the summary, headed
  "Visual Overview of Performance", before `r{n}-energy` and `r{n}-track`.
- Lead-in text is round-specific key insights (5 insight sentences + 1 grounding line per round,
  quantified), not a description of the panel.

Reconciliation spot-checks: R1 bullets 75.1 / 101.4 km/h and 386 / 395 m and 24.9 / 34.1 km/h match
`analysis/per_round_metrics.csv` row 1; R1/R9/R17 wind (6.4 / 4.7 / 8.3 km/h, 072/171/072°) and solar
(785 / 110 / 811 W/m², min→pastel `rgb(250,224,139)`, max→`rgb(176,32,32)`) match
`analysis/weather_per_flight.csv`.

**Nit (copy, low):** the lead-ins render "Leader gained 1 lap(s) here" — a programmer plural passed
through from `scripts/compute_metrics.py:384` into `per_round_metrics.csv` and then into the prose.
42 occurrences in the report.

*Fix:* in the rounds page, post-process the note (or fix `compute_metrics.py:384` and re-run) so it
reads "1 lap" / "2 laps".

Test coverage: `tests/test_shared_foundation.py:124` (8 cells + key labels, round 17) and
`tests/test_content_present.py:58` (8 cells + key on all 17). **Gap (moderate):** the spec's own step-2
test text enumerates the violin colours, "green value on the right", "no orange", the paired bar, the
rank text, the wind card and the red-to-yellow solar bar; none of those are asserted anywhere. A
regression that, say, moved Bill's label onto the bar or reintroduced an orange cap line would stay
green.

*Fix:* add a component-level test per panel, e.g.
`assert PALETTE["attention"] not in dashboard.bullet(...)`, `assert 'text-anchor="start"' in bullet(...)`,
`assert "Winner 1000" in violin(...)`, and assert the solar fill is the pastel-yellow end at the
event-minimum radiation and the deep-red end at the maximum.

## RPT-022 — Overview structure — PASS-WITH-GAPS

Structure verified in `#view-overview`:
- `.summary#ov-top` (short lead + **4 anchor bullets**, one per section → `#ov-headline`,
  `#ov-scoring`, `#ov-start-energy`, `#ov-conditions`) — the required section index.
- `<p class="pee-point"><strong>The Overall Read.</strong> …` sits **before** the first section.
- `.section` ids in DOM order: `ov-headline`, `ov-scoring`, `ov-start-energy`, `ov-conditions` —
  exactly PRD §8 / ADR-004, all Title Case.
- Insight order inside each section matches the spec exactly:
  Headline — The Result (4 number cards) → Within-Group Rank → Gap Breakdown (waterfall) →
  Where The Ground Is Lost → Consistency: Floor vs Ceiling → Progression Across The Week →
  Landings: A Clean Sweep. Scoring — Score Per Round → Laps Per Round → Cruise Speed →
  Field Position & The Laps/Speed Scatter → Speed Gaps. Start Energy — Entry Speed → Entry
  Altitude → The Airframe Question. Conditions — Conditions Dependence → Trajectory Trends →
  Thermal Strength & Weather → Climb Geometry → Climb Rate → Thermalling Turn Radius →
  Round 12: A Worked Example.
- Each insight is `<strong>Title.</strong>` → insight prose → `<figure>` + captioned grounding.
- "Conditions Link" is gone (0 hits). The old Performance-Summary grouped bars now live in their
  thematic homes (`ov-fig-sum-score`, `-laps`, `-speed` in Scoring; `-entryspd`, `-entryalt` in Start
  Energy; `ov-fig-sum-solar` conditions strip in Conditions).

**Gap 1 (moderate):** RPT-022 step 1 asks for the three-series grouped bar (round winner / event
winner / Bill) rendered for score, laps, avg speed, **entry speed and entry altitude**. In the output
`ov-fig-sum-score`, `-laps`, `-speed` carry three series (blue/grey/green rect counts 18/18/18 and
15/14/15), but `ov-fig-sum-entryspd` and `ov-fig-sum-entryalt` carry only **two** (blue 18, green 18,
no grey event-winner series; legend reads "Round winner" only).

*Fix:* either add the event-winner series to the two Start-Energy grouped bars (`pages/overview.py`,
the `_sum_entryspd` / `_sum_entryalt` builders) for consistency with the other three, or — if the
omission is deliberate decluttering — record it in the RPT-022 description so spec and output agree.

**Gap 2 (minor):** the "Landings: A Clean Sweep" callout is the only Overview insight with neither a
visual nor a source link, while RPT-022 specifies Title → Insight → **Visual (+grounding)** →
recommendation and PRD §8 makes grounding mandatory ("a plot **and/or** a link to the source data").
Its claims (600 landing points on all 14 distance rounds, no penalties) are reconciled in
`tests/test_data_reconciliation.py:43` but nothing in the report points the reader at the source.

*Fix:* append the event-results link to that sentence, as the neighbouring insights do
(`_link(_EVENT_URL, "event results")`).

**Gap 3 (informational):** recommendations are attached per cluster (one "What to do." in Scoring,
one in Start Energy, one after Conditions Dependence, three in Headline) rather than after every
insight. Reads well; noting only because the spec's wording implies one per insight.

Test coverage: `tests/test_content_present.py:65` asserts the four section ids in order and the
Overall Read lead — good. `tests/test_shared_foundation.py:104` only exercises `grouped_bar_rounds`
with synthetic data. **Gap:** nothing asserts the five grouped-bar figures render in the Overview at
all, nor the section index links, nor the insight ordering inside each section.

*Fix:* extend the content test with
`for fid in ("ov-fig-sum-score","ov-fig-sum-laps","ov-fig-sum-speed","ov-fig-sum-entryspd","ov-fig-sum-entryalt"): assert view.select_one("#"+fid)`
and assert `#ov-top` carries an anchor to each of the four section ids.

## RPT-023 — Trajectory Trends — PASS-WITH-GAPS

Evidence: `#ov-fig-trajectory` renders a single log-y panel (no linear panel), y ticks
`10% / 1% / 0.1% / 0.01% / 0.001%`, x `0…600 m`, two unfilled polylines (`fill="none"`, green
`#86BC25` = Bill, blue `#00A3E0` = round winner), legend, x-title "Distance from the course
triangle (m)", y-title "Share of flight time (log)", non-empty caption with an rcmodelspot source
link. Floor requirement met: axis baseline is `y=296`, the green polyline's lowest point is
`y=284.7`, so Bill's line never touches the axis despite 4 genuinely empty bins — implemented as
`floor = 1.6e-5` above `ymin = 1e-5` (`charts.py:1481-1487`).

Reconciliation: the lead's "median 46.8 vs the winner's 37.0 m" is interpolated live from
`data.pooled_distance_from_course()` (`pages/overview.py:656-657`); recomputing gives Bill 46.80 m
(n=19,870 points) and winner 37.00 m (n=23,180) — exact.

**Gap (accuracy, minor but user-visible):** the lead states "The best pilots are **bimodal** —
tightest to the course most of the time, yet happy to range much further". The plotted winner density
has a single mode (0–40 m, 53.5 % of time) followed by a long, almost flat shoulder — no second mode.
What the figure does support is the contrast in the tail: the winner spends 5.9 % of flight time
beyond 300 m vs Bill's 1.9 %, and the winner is also tighter than Bill near the line. A reader who
looks for two humps will not find them.

*Fix:* reword to the evidenced claim, e.g. "the winner is tightest to the course most of the time yet
keeps a long tail of far excursions — 5.9 % of his flight time beyond 300 m against Bill's 1.9 % —
while Bill sits in a moderate mid-band (median 46.8 m vs 37.0 m)", computing the two tail shares from
the same density dict so they cannot drift.

Test coverage: `tests/test_content_present.py:89` only asserts the figure exists, is a `<figure>` and
has a non-empty caption. **Gap:** the two load-bearing RPT-023 properties — log-y **only** and the
floor keeping Bill above the axis — are untested.

*Fix:* add a chart test, e.g. build `charts.distance_from_course_density(density)` with a synthetic
density containing zero bins and assert every polyline y-coordinate is strictly less than the baseline
y, and that `0.001%` appears (five decades) while no second panel is emitted.

## RPT-024 — Thermalling Turn Radius — PASS

Evidence: `#ov-fig-turn-radius` renders two unfilled density lines (green Bill, blue Round winner)
over 0–100 m in 5 m bins, with dashed vertical median markers labelled `median 38 m` and
`median 29.2 m` (`charts.py:1544-1663`), a legend, and a captioned figure with an rcmodelspot source
link. Lead text: "Bill circles about 30% wider than the winner (median 38.0 vs 29.2 m)" — recomputing
`data.pooled_turn_radius()` gives Bill 38.00 m (n=4,464 circling samples), winner 29.20 m (n=5,810),
ratio **1.3014**, so both the medians and the "~30 %" are exact. Ties to the climb lever in the last
sentence, as required.

**Nit (cosmetic):** the in-chart marker prints `median 38 m` (`%g`) while the prose and the other
marker print one decimal (`38.0`, `29.2`). *Fix:* format the marker labels with `:.1f` in
`charts.py` for consistency.

Test coverage: same presence-only assertion as RPT-023. **Gap:** the median markers the spec calls for
are untested. *Fix:* assert `"median" in svg` twice and that two dashed verticals are emitted.

## RPT-025 — Airframe / equipment note — FAIL

The note is present in Start Energy as "The Airframe Question" and gets the central framing right:
event winner Florian Griese flies the Pike Paradigm (Samba Model), the same airframe as Bill, so the
~2,900-point gap (15,449 − 12,562 = 2,887 ✓) is technique not kit; the 5 m / 7 kg / 75 g/dm² class
caps are stated and linked to gps-triangle.net; the aerodynamic trade-offs are explicitly flagged as
"general aerodynamics rather than a measured difference"; and the "published glide-ratio figures for
these specific models were not found" caveat is carried over.

**Gap (material):** the spec requires the note to state that "the top field is a mix (Pike Paradigm,
Phantom, SkyTouch, Apollo)". The report asserts "an airframe mix, not a monoculture" but names none of
them — across the whole 2.8 MB file, `Phantom` = 0 hits, `SkyTouch` = 0 hits, `Apollo` = 0 hits,
`Pike Paradigm` = 1 hit. So the mix claim is unsupported on the page, and the spec's own acceptance
wording ("Start Energy names the airframes", plural) is not met. `analysis/pilot_equipment.csv`
supports the claim directly (top 12: Paradigm ×6, Phantom ×3, SkyTouch ×1, Apollo ×1) and
`analysis/airframe_note.md` already drafts the naming sentence.

**Gap (secondary):** `analysis/airframe_note.md` did find citable specifics (Pike Paradigm 4,726 mm
span / ~2.3 kg ballast — f3j.com / Leomotion; SkyTouch GPS best glide 10.6 m/s, comp range
55–90 km/h — solarwings.cz; Apollo 46 4.6 m / 93.33 dm² — f3xvault) and the spec says to cite real
grounding where found. None of it reaches the report.

*Fix (small, one sentence plus optional citations) in `scripts/build/pages/overview.py`, the airframe
paragraph:* after "an airframe mix, not a monoculture", insert the named mix and (optionally) one
cited specific, e.g. "— the top ten spans the Pike Paradigm (Samba), the ChocoFly Phantom, the
SolarWings SkyTouch and the ChocoFly Apollo — and event winner Florian Griese flies the Pike Paradigm,
the same airframe Bill flies". Ideally drive the four family names from
`analysis/pilot_equipment.csv` (`airframe_family` of the top N) rather than hard-coding, and add a
figure or link grounding the mix (a count-by-family strip, or a link to the event ranking).

Test coverage: **none**. No test in `tests/` mentions RPT-025, airframe, Pike or Paradigm, which is
why the missing airframe names never surfaced.

*Fix:* add to `tests/test_content_present.py`:

```python
def test_start_energy_airframe_note(soup):
    txt = soup.select_one("#ov-start-energy").get_text(" ", strip=True)
    for model in ("Pike Paradigm", "Phantom", "SkyTouch", "Apollo"):
        assert model in txt
    assert "technique" in txt and "not an equipment" in txt
```

and flip RPT-025's `passes` to `false` until it is green.
