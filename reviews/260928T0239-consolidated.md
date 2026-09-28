# Build review — consolidated findings and proposed fixes

Date: 2026-09-28. Orchestrator consolidation of six parallel reviews (all reviewers on Opus):
`260928T0239-output-quality.md`, `260928T0239-visual-ui.md`, `260928T0239-spec-A-data-analysis.md`,
`260928T0239-spec-B-report-core.md`, `260928T0239-spec-C-grounding-design.md`, `260928T0239-spec-D-v2-overview.md`.

Status: **proposal awaiting user approval. No fixes applied.**

## Verdict

The build is structurally sound: 82 tests green, output byte-identical to a fresh build, fully
self-contained (zero external requests under Playwright with the network blocked), zero console
errors, zero horizontal overflow at 360–1920 px, zero dangling anchors, zero duplicate ids, no
emoji, no accent bars or gradients, all 71 figures captioned, every headline number reconciles to
the cached API data. Navigation, dropdown, burger, collapsibles and 50/50 cross-page links work.

Spec verdicts: 31 reviewed, **2 FAIL** (RPT-008 dead rules links; RPT-025 airframe note), 19
PASS-WITH-GAPS, 10 PASS. The gaps are content-accuracy errors, mobile/accessibility shortfalls,
and tests that are much weaker than the specs they claim to cover.

## Tier 1 — content accuracy (must fix before acceptance)

| # | Finding | Source | Fix |
|---|---|---|---|
| 1 | **Round 12 worked example says the opposite of the data.** Overview claims the leader ranges off course and circles tighter while Bill holds a neater line. Round 12 metrics: Bill's fastest clean lap 4,622 m vs leader 1,819 m (ratio 2.54), turn radii 42.0 vs 40.9 m. | OQ-B1 | Rewrite point + caption in `pages/overview.py:735-752` as a weak-lift worked example (Bill's off-course loops on a 2-lap day, comparable turn radii). |
| 2 | **Conditions Dependence uses all 17 rounds** incl. the 3 speed sprints; quoted rho +0.6 is n=17 (0.608) while the text says n≈14. Distance-only rho = 0.543. | A1 | Filter `ctx["weather"]` to distance rounds in `overview.py:608`; reword to "~ +0.5"; add distance-only row to `analyse_weather.py` / `weather_correlations.csv`; update PRD §7.8. |
| 3 | **"350 m-leg course" in all 17 ground-track captions** (+2 others) contradicts ADR-008 (350 m is the radius; legs ≈495 m, base 700 m, lap ≈1,690 m). Also `PERIMETER_M = 1050` in `compute_metrics.py:32` / `trajectory_poc.py:35` (contained: affected columns never reach the report). | OQ-B2, C3, A2 | Derive caption text from `course_geometry()`; fix `PERIMETER_M` to 350·(2+2√2) and stale comment in `analyse_weather.py:87`; regenerate metrics. |
| 4 | **Both gps-triangle.net rules links are dead (404), 8 anchors.** Verified replacements: `https://gps-triangle.net/page1.html` and `https://gps-triangle.net/assets/files/regulations_sport_en_V1.9_release01.pdf` (§2.7 confirmed). | C1 | Hoist one shared URL constant into `components.py`, replacing 3 duplicated `_RULES_URL` defs. |
| 5 | **RPT-025 FAIL.** Airframe note names only Pike Paradigm; Phantom / SkyTouch / Apollo appear nowhere. No test exists. | D1 | One sentence naming the four families from `analysis/pilot_equipment.csv`; add test; flip spec red→green. |
| 6 | **Speed rounds 4/10/16 cumulative-laps chart on absolute clock** (Bill at ~150 s, leader at up to 3,095 s; R4 axis spans 60 min for a 2-min sprint). | C2 | Drop the figure on speed rounds (caption already says the framing does not apply). |
| 7 | Round 7 called "a first-day flight"; it is 2026-08-05, day 3. | A6 | Reword `overview.py:382-384`. |
| 8 | RPT-023 lead calls the winner's distance-from-course "bimodal"; plot shows one mode + a shoulder. Evidenced claim is the tail: 5.9% vs 1.9% of time beyond 300 m. | D2 | Reword from the density dict. |

## Tier 2 — UX and accessibility (should fix)

| # | Finding | Source | Fix |
|---|---|---|---|
| 9 | **Nothing in the navigation is keyboard-reachable.** 4 nav `<a>` and all 50 `a.xref` have no `href`/`tabindex`; 115 collapsible heads have no role/aria-expanded/key handler; no `.xref` CSS (no pointer cursor). | OQ-B3 | Real `href="#..."` on nav/xref (delegated handler already intercepts); `role="button" tabindex="0" aria-expanded` + Enter/Space handler on `.section-head`; `.xref{cursor:pointer}`. |
| 10 | **Chart text 5–6 px effective on mobile** (720–1120 unit viewBoxes scaled ~0.3–0.5 into a 358 px column). Every axis/legend unreadable at 390 px. | V-S1, OQ-S11 | Recommended: wrap figures in a horizontally scrollable container with a `min-width` (~600 px) below 720 px, and raise base SVG label size to 12 px. Alternative (heavier): emit a second narrow-layout SVG per chart, roughly doubling SVG payload. |
| 11 | **Axis ticks clipped** by the outer `<svg>` overflow: cumulative-laps final x-tick lost on R1/3/4/5; Overview scatter "30" renders as ")"; top y-tick as "--" on R9/15/17. | V-S2 | Pad viewBox by tick metrics + `overflow:visible` in `charts.py`. |
| 12 | Progression chart: right-axis "20" tick collides with "Laps" legend. | V-S3 | Shift legend. |
| 13 | Mobile: section "Collapse" toggle and "back to top" overlap the heading. | V-S5 | Stack controls under heading below 720 px. |
| 14 | Ground-track legend sits over the leader's trace; empty band available below. | V-S6 | Move legend. |
| 15 | Inconsistent chart widths in one column (1008 / 980 / 720) leave a ragged edge. | V-S4 | Standardise to one width. |
| 16 | Text contrast on white: `#75787B` 4.44:1 on 640 small labels; `#00A3E0` 2.87:1 (69); `#5C8F10` 3.89:1 (68). | OQ-S1 | Darken those tokens in `design.py` (e.g. grey to #63666A, blue to #0076A8). |
| 17 | 51 dashboard SVGs have generic aria-labels and no `<figure>`/caption. | OQ-S2/S3 | Descriptive aria-labels; wrap dashboard in one captioned `<figure>`. |
| 18 | Flat heading hierarchy: 132 `<h2>`, no `<h3>`; round subsections are siblings of the round title. | OQ-S4 | Demote subsections to `<h3>` (CSS rules already exist). |

## Tier 3 — content polish

| # | Finding | Source |
|---|---|---|
| 19 | "Leader gained 1 lap(s) here" template leak, 42 occurrences (`compute_metrics.py:384`). | OQ-S5, D6 |
| 20 | Elapsed windows print as "22:25-23:25" in a 17:05 round, reads as clock time. | OQ-S6 |
| 21 | Speed rounds show "Within-group rank 29/38" though prose says field-scored. | OQ-S7 |
| 22 | Two different circle-radius pairs for one idea in one section (39/33 m then 38.0/29.2 m) with no distinction. | OQ-S8 |
| 23 | All 17 round summaries: bullets are section titles, not key points/recommendations (RPT-007). | B1 |
| 24 | Recommendations: `rec-entry` and `rec-turns` lack "Further Analysis"; `rec-signals` lacks a back-link to evidence (RPT-005). | B2 |
| 25 | Analysis → Innovations cross-links: zero (spec and PRD require them). Add 2–3 (Climb Geometry / Turn Radius → `inn-live`; Round 12 → `inn-navigator`). | B3 |
| 26 | Entry speed / entry altitude summary charts render 2 of the 3 specified series (no event-winner). | D3 |
| 27 | Fonts: Source Sans 400/500/600/700 are four byte-identical copies of one variable font, plus an unused Spectral italic; ~100 KB dead weight. | D4 |
| 28 | Ungrounded claims: Landings callout, Airframe Question, Ray-Ban Meta hardware; Home "Sport-class rules" unlinked. | D5, C5, C6 |
| 29 | Wind-vector captions hard-code "right margin" though it is left/top/bottom for 9 of 17 rounds. | C4 |
| 30 | Title Case over-applied to lead-ins ("Floor Vs Ceiling", "Where The Ground Is Lost") vs h2 convention ("vs"). | OQ-S12 |
| 31 | `scroll-margin-top` selector misses `#ov-consistency` / `#ov-levers`. | OQ-S13 |
| 32 | No `<noscript>` and no default `.page.active` in markup: blank page if JS is stripped. | OQ-S9 |
| 33 | Home's three linked headings are bare `<a>` in `<li>`; wrap in `<h2>`. | B6 |

## Tier 4 — tests and spec hygiene

| # | Finding | Source |
|---|---|---|
| 34 | **No dedicated tests** for DATA-002, DATA-003, ANL-002, ANL-003, ANL-004, RPT-005, RPT-006, RPT-007, RPT-009, RPT-025. Existing laps/speed reconciliation is near-tautological (both sides copied from the API). Highest-value independent assertions: scored_start vs the API's scored stats entry; aloft_time_s vs timeElapsedSeconds; API-implied lap distance 1,689.9 m on all 17 rounds. | A4, B4 |
| 35 | **Weak tests** for RPT-003/004 (no per-insight structure), RPT-008 (no link resolution, hence 8 dead links shipped), RPT-011 (round 17 only), RPT-012 (string presence only), RPT-013 (tracks not laps chart), RPT-016 (literal "section 2.7"), RPT-019 (no size/weights budget), RPT-021/022/023/024 (presence-only). Each reviewer report carries paste-ready tests. Add a size-budget assertion for RPT-001. | all |
| 36 | Spec text corrections: ANL-001 step 2 ("within 3% of API distance fields") is unsupportable, replace with the 1,689.9 m check; DATA-003 `cape` is null in all 144 ERA5 hours, drop the step and column; RPT-011 text still says "right margin", reconcile with RPT-012. | A3, A5, C7 |
| 37 | Robustness: same-air leader matched by lowercased name with silent empty fallback (`data.py:582`), match on userGuid or raise; `fetch_data.py:13` hard-codes an absolute path. | A7 |

## Nice-to-have (deferred unless wanted)

Spaced hyphens instead of en-dashes (296); `2.54x` → `×`, `g/dm2` → `g/dm²`; `:focus-visible` styling; meta description / skip link; hash deep-linking; burger `type`/`aria-expanded`; non-text chart marks `#ED8B00` 2.53:1 and `#D0D0CE` 1.54:1; Bill plotted grey in 2 Overview charts where grey means "others"; solar-radiation tile is an unlabelled colour block; scatter points below y-axis min; "Mean round score 774" unlabelled as distance-only; `pee-explain` class on 6 of 24 blocks.

## Questions for the user

1. **Orange accent `#ED8B00`.** Used for the dashboard "attention" state. PRD §8 names only green, greys, and teal/blue. Keep or replace?
2. **Mobile charts (item 10).** Scrollable container (cheap, keeps one SVG) or dual-layout SVGs (heavier, better UX)?
3. **Scope.** Fix all four tiers, or Tiers 1–2 + 4 now and Tier 3 selectively?

## Proposed execution

Three parallel Opus fix agents, each red→green per item with the spec flipped where a spec is touched:
(A) analysis + data + tests + spec text (items 2, 3, 34–37); (B) charts + design + accessibility
(items 9–18, 27); (C) page content (items 1, 4–8, 19–26, 28–33). Then a re-run of the Playwright
driver and a short re-review of Tier 1 items before the product is put to the user for acceptance.
