# Spec review C — grounding, design system, ground-track/wind/time-axis, labels, regs links

**Date:** 2026-09-28T02:39
**Reviewer:** spec reviewer C (read-only)
**Artefact under review:** `report/gps-triangle-world-masters-oschatz-2026.html` (2,839,459 bytes)
**Build parity:** verified — `assemble.build_html()` is byte-identical (md5 match) to the committed report, so the built file is not stale.
**Test suite:** `uv run pytest -q` → **82 passed** (green).

## Verdicts

| Spec | Verdict | One-line reason |
|---|---|---|
| RPT-008 | **FAIL** | Both `gps-triangle.net` regs URLs (8 anchors) return HTTP 404 — the spec's own test step requires "every external link resolves". |
| DSN-001 | **PASS** | White bg, Deloitte-free palette, serif/sans pair, zero emoji, zero CSS gradients, zero accent bars, 71/71 figures captioned, all section titles Title Case, no lexical tics. |
| RPT-011 | **PASS-WITH-GAPS** | Geometry, draw order, traces and orientation aids are all correct in the output, but 17 captions mis-describe the 350 m **radius** as the "leg" (contradicts ADR-008) and claim the wind sits "in the right margin" when for 9 rounds it does not. |
| RPT-012 | **PASS** | All 18 ground-track plots place the wind glyph on the correct clockface side (dot product +1.000 vs the source bearing), inward-pointing, inside the frame, with compass + degrees + knots. |
| RPT-013 | **PASS-WITH-GAPS** | Altitude/speed panels are correctly run-relative, but the three speed-round cumulative-laps charts still plot the two pilots on a shared absolute clock (leader ~15–52 min after Bill) — the exact bug class RPT-013 was written to kill. |
| RPT-014 | **PASS** | 115/115 sections carry a `.section-toggle` reading "Collapse" at load; `syncLabel()` flips it on every state-change path; no `>toggle<` remains. |
| RPT-015 | **PASS** | 4× "Legality Consideration" as `<strong class="legality-label">` inside a `<p class="legality">` at `font-size: 1rem`; no "Legality gate"/"Legality Gate" anywhere. |
| RPT-016 | **PASS-WITH-GAPS** | Section-specific → PDF, general → index is correctly implemented, but both target URLs 404 and one general "Sport-class rules" mention on Home is unlinked. |

---

## RPT-008 — Grounding (FAIL)

### What was checked
Sampled well over 15 claims across the Overview (all four thematic sections, ~30 prose blocks), Rounds 1/4/7/10/12/16/17, the whole Recommendations page and the whole Innovations page, by walking each view in document order and recording, per prose block, whether a `<figure>` follows, whether the block carries an `http` source link, and whether it carries an `a.xref` into a figure-bearing block. Then ran a repo-wide sweep for quantitative prose with none of the three.

### Grounding itself is strong
- 71 figures, **71 non-empty `<figcaption>`s**, 0 exceptions.
- Overview: every claim block is either immediately followed by its figure or carries an inline source link (usually the rcmodelspot ranking). The "What to do." blocks all carry both a link and xrefs to Recommendations anchors.
- Recommendations has no figures of its own but every quantitative lead paragraph xrefs a figure-bearing Overview block (`#ov-levers` → `ov-fig-deficit`, `#ov-consistency` → `ov-fig-consistency`); `test_xref_anchors_all_resolve` already guarantees those anchors resolve.
- "No forced links" is respected — drills carry no links; only the three genuinely useful resources (SM-Modellbau, OLC-RC, BMFA Silent Flight) and the two AR vendors are linked.
- The sweep flagged 16 quantitative blocks with no figure/link/xref; on inspection all 16 are false positives (14 "Single biggest-loss window:" lines whose immediately following sibling paragraph carries `Source: event results`; 2 drill bullets restating numbers established in the same section's linked lead paragraph).

### Gap 1 (severity: HIGH) — two external links are dead
Spec step 2 requires "every external link resolves". Of 9 unique external URLs (123 anchors), **2 URLs / 8 anchors are HTTP 404**:

| URL | Status | Anchors |
|---|---|---|
| `https://gps-triangle.net/gps-triangle/regulations-documents/` | **404** | 6 |
| `https://gps-triangle.net/wp-content/uploads/2022/03/regulations_sport_en_V1.6_Release01.pdf` | **404** | 2 |
| `https://www.rcmodelspot.com/Ranking/f772fc7c-…` | 200 | 106 |
| `https://open-meteo.com/` | 200 | 3 |
| `https://www.onlinecontest.org` | 200 | 2 |
| `https://www.sm-modellbau.de/GPS-Logger-3` | 200 | 1 |
| `https://silent-flight-tech.bmfa.org/specialisms/gps` | 200 | 1 |
| `https://www.xreal.com` / `https://www.rokid.com` | 200 | 1 each |

`gps-triangle.net` is up (200 on `/`) but is a static Mobirise site with `pageN.html` routing and `assets/files/*.pdf` — the WordPress-style paths in the report never existed there.

**Verified working replacements** (both fetched and confirmed; the PDF extracts to 22 pages and its ToC does list *"2.7 Gyros, Auto Pilots & Telemetry"*, so the citation remains topically correct):
- Regulations index → `https://gps-triangle.net/page1.html` (`<title>Regulations</title>`)
- Sport-class regs PDF → `https://gps-triangle.net/assets/files/regulations_sport_en_V1.9_release01.pdf` (current release; the v1.6 filename also resolves under `assets/files/` and serves a byte-identical file, but v1.9 is the one the site links)

**Recommended fix:** the URL is duplicated as three separate `_RULES_URL` constants —
`scripts/build/pages/innovations.py:42` (+ the PDF at `:44`), `scripts/build/pages/recommendations.py:40`, `scripts/build/pages/overview.py:38`.
Hoist a single `REGS_INDEX_URL` / `REGS_SPORT_PDF_URL` pair into `scripts/build/components.py` (next to `EVENT_URL`), point them at the two verified URLs, and import from all three page modules. Also consider bumping the link text from an implied v1.6 to v1.9 where version is implied.

### Gap 2 (severity: LOW) — one factual claim with neither plot nor source
`scripts/build/pages/overview.py` "The Airframe Question" paragraph asserts *"event winner Florian Griese flies the Pike Paradigm (Samba Model) — the same airframe Bill flies"* and *"the top of the Sport-class field is an airframe mix, not a monoculture"*. The only link in that paragraph is the regs link, which supports the *class-limits* clause, not the equipment claim. The equipment data does exist and is sourced (`analysis/pilot_equipment.csv`, columns `aircraft` / `airframe_family`, derived from the rcmodelspot event page; `analysis/airframe_note.md` carries the citations).
**Fix:** add the existing `EVENT_URL` as a source link on the airframe clause (e.g. "…the same airframe Bill flies ([event results](…))"), exactly as the other Overview blocks already do.

### Gap 3 (severity: INFO) — nits, not defects
- "Landings: A Clean Sweep." carries no inline link, but is grounded on-page by the `600 / Landing points / clean on all 14 distance rounds` stat tile and the zero-height "Landings / penalties" bar in `ov-fig-gap` in the same section. Adding `Source: event results` would make it consistent with its neighbours.
- Innovations: *"today's Ray-Ban Meta glasses are audio and camera only with no display"* is an unsourced external factual claim (the Xreal/Rokid links cover the alternatives, not this).

### Test strength
`tests/test_html_structure.py:198` (`test_captions_render_source_links_not_escaped`) is the only RPT-008 test. It asserts figcaption anchors are not HTML-escaped and that *at least one* figcaption carries a link. That is far weaker than the spec: it checks neither per-claim grounding nor link resolution — which is precisely why 8 dead anchors reached the deliverable.
**Recommended test:** add a test that collects every external `href` in the build and asserts each is in a curated `VERIFIED_LINKS` allowlist (kept in the build module), so a new or edited URL cannot ship without a human having resolved it. Optionally add an opt-in network-marked test that HEADs each allowlisted URL.

---

## DSN-001 — Design system (PASS)

All spec steps verified directly against the built file:

| Requirement | Evidence |
|---|---|
| White background | `:root { --bg: #FFFFFF; … }`, `background: var(--bg)` on body |
| Deloitte-inspired, no branding | `--primary: #86BC25`, `--primary-dark: #046A38`, `--leader: #00A3E0`, `--attention: #ED8B00`, cool greys `#53565A`/`#75787B`/`#D0D0CE`; `"deloitte"` occurs **0** times (case-insensitive) |
| Elegant typeface | `--font-heading: "Spectral", Georgia, …serif`; `--font-body: "Source Sans 3", system-ui, …` — both inlined as base64 woff2, no remote font link |
| No accent bars/stripes | In 241 KB of CSS: `border-left` **0**, `border-inline-start` **0**, `box-shadow` **0**, `::before` **0**, `::after` **0**. The only 3 `border-top` rules are 1 px `var(--hairline)` dividers on `.section`, `.home-links li` and `.dash-divider` — hairline rules, not accent bars |
| No gradients | `linear-gradient`/`radial-gradient` **0**. The single "gradient" string in the file is the prose phrase "shape the tone gradient tightly around the core" (audio-vario drill) — not styling |
| No emojis | 0 matches for the broad emoji ranges; a wider sweep for **any** codepoint above U+2000 also returns 0 |
| Every figure captioned | 71 `<figure>`, 71 non-empty `<figcaption>` |
| Title Case section titles | All 42 distinct `h1`/`h2` titles pass a Title-Case check with small-word and acronym/unit exemptions: acronyms preserved (GPS, AI, AR, HUD), units preserved (`km/h` in "Entry Speed - Use the 120 km/h Cap"), small words correctly lowercase mid-title ("Where the Time Went", "What to Train from This Round") |
| Lexical tics | The suite's 5 banned patterns pass; an extended sweep of 29 AI-tell patterns (delve, tapestry, crucial, leverage, underscores, testament, seamless, robust, "not just X but Y", moreover/furthermore, in conclusion, game-changing, cutting-edge, meticulous, …) returns **0** hits across all page prose |

### Test strength
`test_background_is_white`, `test_no_brand_string`, `test_no_emoji_anywhere`, `test_no_css_gradients`, `test_all_figures_have_captions`, `test_every_figure_has_a_nonempty_caption` and `test_no_banned_lexical_tics` cover most of it. **Two spec clauses are untested:** the "no left/top accent-bar pattern" step, and the Title-Case-on-every-section-title clause.
**Recommended test:** add (a) a CSS assertion that no rule sets a `border-left`/`border-top` wider than 1 px or in a non-hairline colour, and (b) a Title-Case assertion over `soup.select("h1,h2")` with an explicit acronym/unit/small-word exemption list. Both hold today, so they land green and lock the behaviour in.

---

## RPT-011 — Ground track & course geometry (PASS-WITH-GAPS)

### Verified correct in the output
- **Geometry matches ADR-008 exactly.** `data.course_geometry` for all 17 rounds: `radius = 350.0 m`, `leg = 495.0 m` (= r·√2), `hypotenuse = 700.0 m`, `perimeter = 1689.9 m`, `axis = 74.8°`, apex bearing `344.8°` (= axis − 90). Right angle at the apex and start at the hypotenuse midpoint are asserted by `tests/test_shared_foundation.py:26`.
- **The drawn polygon matches those metres.** Measuring the rendered `<polygon>` against each plot's own 100 m scale bar: `r1` = 495/495/700 m (perimeter 1689), `r12`/`r17`/`ov-fig-r12-track` = 495/495/700 m (perimeter 1690). One shared projection for course and traces, as required.
- **Drawn last, on top.** In all 18 ground-track SVGs the `<polygon>` byte offset is greater than the offset of the last `<polyline>` (e.g. r1: polygon @45581 vs last polyline @23684).
- **Full-resolution traces.** Distance rounds carry 1,700–1,801 points per pilot (≈1 Hz over the 30-min window), drawn at `stroke-opacity="0.38"`.
- **Orientation aids present in all 18:** North arrow (`>N</text>`), `100 m` scale bar, dashed start/finish perpendicular (`stroke-dasharray="7 5"`), 3-item legend (Bill / Leader / Course) with computed per-item widths (no swatch/label overlap), all inside the data box; the wind glyph lives in the frame margin outside the data box, so legend/scale/North cannot collide with it. Spot-checked the worst case (r15, N 003°, wind glyph at top-centre `x≈586`, `y 68–148`) against the North marker at `(958, 226)` — well clear, and all label blocks sit inside the frame `(40, 52, 1052×888)`.

### Gap 1 (severity: MEDIUM) — 17 captions call the radius a "leg", contradicting ADR-008
`scripts/build/pages/rounds.py:523` reads `leg = task.get("leg_length_m", "")`, but that dataset field is the `.rct` `length` = the **turnpoint radius** (350 m), which is exactly the mis-reading ADR-008 was written to correct (*"`length` is the radius / half-base, not the leg"*). It is then rendered into both caption variants at `rounds.py:543` and `rounds.py:559`, producing **17 occurrences of "350 m-leg"** in the deliverable:

> "the bold ink triangle is the factual **350 m-leg** course reconstructed from the .rct…"

The drawing is right; the caption tells the reader the wrong number for the wrong dimension.
**Fix:** use `data.course_geometry(task)` in `_track_section` and caption from it, e.g. *"the factual right-isosceles course from the .rct — 350 m turnpoint radius, ~495 m legs, 700 m base, ~1690 m lap"*, or at minimum rename the variable and write `{radius} m-radius`.

### Gap 2 (severity: MEDIUM) — captions hard-code "wind vector in the right margin"
`rounds.py:546` and `rounds.py:562-563` both end with *"North arrow top-right, 100 m scale bottom-left, wind vector in the right margin."* for every round. Per the verified RPT-012 placement the glyph is actually LEFT for rounds 7, 8, 10, 11, 12, 13, TOP-LEFT for 14, TOP for 15 and BOTTOM for 9 — so **9 of 17 captions point the reader at the wrong side of the plot.**
**Fix:** either drop the positional clause for the wind ("…and the wind vector on the side the wind blows from"), or derive it from `wind_for_round(n)["dir_deg"]` with the same clockface rule the chart uses.

### Note (severity: INFO) — spec text is internally stale
RPT-011's own description still says *"wind vector in the right margin"*, which RPT-012 explicitly supersedes ("A fixed right-band placement is wrong for non-easterly winds"). Worth reconciling the RPT-011 wording in `docs/SPEC.json` so the two specs do not contradict each other.

### Test strength
`test_course_geometry_is_right_isosceles` and `test_projection_matches_haversine` are strong but cover **round 17 only**; `test_ground_track_has_course_wind_and_orientation_marks` is presence-only. The spec's own step-2 list (turn-arc radius, flown-leg bearings, fitted arc centres, start-crossing centroid, both pilots, "triangle drawn last") is **not** covered by the committed suite — presumably validated during the Stage-1 prototype and not carried across.
**Recommended test:** add a cheap, deterministic assertion that the `<polygon>` offset exceeds the last `<polyline>` offset (draw order) and that the polygon's side lengths, scaled by the rendered 100 m bar, are 495/495/700 m ±2% — for all 17 rounds. That is the assertion that would also have caught the "350 m-leg" caption if the caption were derived from the same source.

---

## RPT-012 — Per-plot wind annotation (PASS)

Verified on **all 18** ground-track plots (17 rounds + the Overview R12 worked example) by extracting the grey `stroke-width="3"` shaft, computing its outward unit vector `(tail − head)` and comparing it to `(sin θ, −cos θ)` for the labelled source bearing:

| Round | Label | Expected side | Rendered side | dot |
|---|---|---|---|---|
| 1 / 16 / 17 | ENE 072/075/072 | right | right | +1.000 |
| 2 / 3 / 5 | ENE 057 / NE 045 / NNE 033 | top-right | top-right | +1.000 |
| 4 | ESE 115 | bottom-right | bottom-right | +1.000 |
| 6 | E 099 | right | right | +1.000 |
| 7 / 8 / 10 / 11 / 12 / 13 | W 260 / WSW 257 / W 281 / W 272 / W 262 / WNW 285 | left | left | +1.000 |
| 9 | S 171 | bottom | bottom | +1.000 |
| 14 | NW 306 | top-left | top-left | +1.000 |
| 15 | N 003 | top | top | +1.000 |
| ov-fig-r12 | W 262 | left | left | +1.000 |

The v2 bug named in the spec (fixed right band; "W/272 → LEFT") is genuinely fixed. Every glyph also: carries a three-line grey label `WIND` / `<compass> <ddd>°` / `<km/h> · <kn>` with knots present on all 18 (2.3–9.8 kn); points **inward** (arrowhead polygon built from `inx,iny = -ux,-uy`, `charts.py:578-585`); and sits entirely within the outer frame rect on all 18. The northerly case (r15) does not collide with the North marker — see RPT-011 above.

### Test strength
`test_ground_track_has_course_wind_and_orientation_marks` asserts only that the strings `WIND` and `kn` appear, on round 17 — a round whose wind is ENE, i.e. the one orientation the *old buggy* fixed-right-band code would also have passed. The spec's step 2 ("correct clockface position"; "northerly does not collide with the North marker") is untested.
**Recommended test:** port the dot-product check above into the suite, parametrised over all 17 rounds, plus a bounding-box non-overlap assertion between the wind label block and the North marker for round 15.

---

## RPT-013 — Run-relative time axes (PASS-WITH-GAPS)

### Verified fixed
Every Energy Management chart (all 17 rounds) labels its x-axis **"Relative flight time (minutes since scored start-line crossing)"** and both series begin at 0:
- distance rounds (e.g. r1, r17): ticks `0, 5, 10, 15, 20, 25, 30` — the 30-min window, no offset;
- speed rounds (r4, r10, r16): ticks `0, 0.2, 0.4, 0.6, 0.8` — both pilots overlaid from their own gate crossing.

The original bug (speed-run altitude on absolute clock, pilots ~25 min apart) is gone. `data.full_tracks_for_round` isolates a single run-relative window per pilot, asserted by `test_scored_start_isolates_longest_run_window`.

### Gap (severity: MEDIUM-HIGH) — the audit missed the cumulative-laps chart on speed rounds
The spec explicitly says *"audit all time-based charts for the same issue"* and its test step says *"no chart shows large empty offsets from absolute wall-clock"*. `charts.cumulative_laps` (`charts.py:622`) plots `lap_offsets_s` directly, and those offsets are **not** normalised per pilot on the three speed rounds, where the two pilots fly sequential slots:

| Round | Bill's lap offset | Leader's lap offset | Rendered step x (axis 56→~700) |
|---|---|---|---|
| 4 | 139 s (2.3 min) | **3095 s (51.6 min)** | Bill @85, leader @696 — axis forced to 0–60 min |
| 10 | 166 s (2.8 min) | **1744 s (29.1 min)** | Bill @115, leader @676 |
| 16 | 159 s (2.6 min) | **917 s (15.3 min)** | Bill @112, leader @382 |

So `#r4-fig-laps`, `#r10-fig-laps` and `#r16-fig-laps` render two single steps at opposite ends of a mostly-empty axis — the precise failure mode RPT-013 exists to prevent — and R4's axis stretches to 60 minutes for a ~2-minute sprint (`tmax = max(working_time_s, max(offsets))` at `charts.py:638`). The caption at `rounds.py:610-613` even says *"both pilots step to a single crossing"*, which is not what the reader sees. The 14 distance rounds are fine (both pilots' offsets sit inside the 0–30 min window).

**Fix (either is acceptable):**
1. In `_laps_section` (`rounds.py:598`), when `is_speed`, normalise each pilot's single offset to its own run start (both step at t≈0 on a seconds axis sized to the longer run), **or**
2. suppress the cumulative-laps figure entirely on the three speed rounds — the caption already concedes *"the distance framing does not apply; the dashboard's single-lap speed panel carries the comparison"*, so the figure earns nothing.

Option 2 is the smaller, lower-risk change and removes three misleading figures.

### Nit (severity: LOW)
Speed-round Energy Management axes are labelled in minutes with `0.2 / 0.4 / 0.6 / 0.8` ticks for a ~50 s run. Correct, but seconds would read better. Not required by the spec.

### Test strength
No test targets the spec's "audit all time-based charts" clause; `test_scored_start_isolates_longest_run_window` checks the *track* rows, not the *laps* chart, which is exactly the hole the speed-round bug fell through.
**Recommended test:** assert that for every round, every series in `#r{n}-fig-laps` starts within the first ~10% of the x-range, and that the axis maximum does not exceed `working_time_min` — parametrised 1–17.

---

## RPT-014 — Dynamic Expand/Collapse label (PASS)

- Markup: `components.py:144-153` sets `toggle_label = "Collapse"` and emits `<span class="section-toggle">Collapse</span>` inside a `.section-head` with `onclick="toggleSection(this)"`.
- JS: `assemble.py:117-121` defines `syncLabel(sec)` → `t.textContent = sec.classList.contains('collapsed') ? 'Expand' : 'Collapse'`, and it is called from **every** state-change path: `toggleSection` (`:125`), `expandSection` (`:131`), `expandAll` (`:141`), `collapseAll` (`:146`) and `scrollToAnchor`'s reveal (`:157`). No path mutates `.collapsed` without re-syncing.
- Built output: **115 `.section` elements, 115 `.section-toggle` spans, all reading "Collapse"** at load (sections start expanded); `0` sections without a toggle; the string `>toggle<` does not appear; no `class="section collapsed"` in the initial markup, so the initial label is always correct.
- Both `Expand all` and `Collapse all` controls present (`components.py:172-173`) and scoped to the active view (`currentScope()`, `assemble.py:135`).

Test `test_collapsible_starts_expanded_with_dynamic_label` (`test_shared_foundation.py:146`) covers the markup contract well. **Minor:** it does not assert the JS wiring; a one-line `assert "syncLabel" in assemble.build_html()` would close that (cosmetic — the behaviour is correct).

---

## RPT-015 — "Legality Consideration" (PASS)

- Strings `Legality gate` and `Legality Gate` appear **0** times in the deliverable (also asserted by `test_no_old_title_and_legality_wording`).
- 4 occurrences of "Legality Consideration", all in Innovations (post-flight coach, navigator AR HUD, live AI cueing, data flywheel), all rendered as:
  `<p class="legality"><strong class="legality-label">Legality Consideration.</strong> …`
- Styling is body-size inline emphasis, not a heading: `.legality { font-size: 1rem; }` and `.legality-label { font-weight: 700; color: var(--ink); }`. No `<h*>` element is involved.
- `test_legality_consideration_is_inline_bold_not_heading` verifies wording, `<strong>`, and absence of `<h`. Test matches the spec; no gap.

---

## RPT-016 — Regs references hyperlinked (PASS-WITH-GAPS)

### Verified correct
- **Section-specific → PDF.** Both `section 2.7` mentions (Innovations intro, and the live-cueing Legality Consideration as "regs section 2.7") are wrapped in anchors to `…/regulations_sport_en_V1.6_Release01.pdf`. The citation is topically right: the fetched Sport-class PDF's ToC lists *"2.7 Gyros, Auto Pilots & Telemetry"*, and the report's claims (passive telemetry/relay permitted; nothing may feed model control) match that section's subject.
- **General → index.** 6 anchors to the regulations index, covering: the Overview "What to do" (entry cap / scoring), the Overview airframe class-limits clause, the Start Energy "What to do", the Recommendations "Rules-Legal Live Signals" lead ("Sport-class rules"), the Innovations intro ("regulations") and the AR HUD Legality Consideration ("Sport-class regulations").
- A full text sweep found 28 regs/rules-ish fragments; 15 are linked or sit in a linked block. Of the 13 unlinked, 11 are not regs references at all (adjectival "rules-legal", "rule compliance", the event subtitle "Sport class", the `Rules-Legal Live Signals` heading) or are in-SVG dashboard labels.

### Gap 1 (severity: HIGH — shared with RPT-008)
Both target URLs 404. See RPT-008 Gap 1 for the verified replacements and the single-constant fix. The *linking* is implemented to spec; the destinations are wrong.

### Gap 2 (severity: LOW) — one unlinked general regs mention
Home page, Innovations teaser (`scripts/build/pages/home.py`): *"…each weighed against the **Sport-class rules**."* — unlinked, while the identical phrase on the Recommendations page **is** linked to the index.
**Fix:** wrap it in the same shared `REGS_INDEX_URL` anchor.

### Gap 3 (severity: INFO) — in-SVG dashboard labels
`Regs limit / Other pilots` (colour key), `Track top = 120 regs cap`, `Track top = 400 regs cap`, `No regs cap` are regs references inside inline-SVG chart furniture. Not "section N" mentions, so out of the spec's literal scope, and linking inside a legend would be visually noisy — recording as a deliberate non-issue, not a fix.

### Test strength
`test_regs_section_references_are_linked` (`test_html_structure.py:159`) only checks the literal `section 2.7`. It does not cover the general mentions the spec also requires, and (like every other test) does not check resolution.
**Recommended test:** broaden the regex to `(regs?|regulations?|Sport-class rules)` over visible prose (excluding SVG and adjectival compounds via an explicit exemption list) and assert each match sits in a block carrying a `gps-triangle.net` anchor; plus the allowlist test proposed under RPT-008.

---

## Consolidated fix list (ranked)

1. **[HIGH, RPT-008 / RPT-016]** Repoint both `gps-triangle.net` URLs — index → `https://gps-triangle.net/page1.html`, PDF → `https://gps-triangle.net/assets/files/regulations_sport_en_V1.9_release01.pdf`. Hoist to one shared constant pair in `components.py`, replacing the three duplicated `_RULES_URL` definitions (`overview.py:38`, `recommendations.py:40`, `innovations.py:42-44`). 8 anchors fixed.
2. **[MED-HIGH, RPT-013]** Speed rounds 4/10/16: drop the cumulative-laps figure (preferred) or normalise each pilot's lap offset to its own run start. Currently the leader steps 15–52 min after Bill on a shared clock.
3. **[MED, RPT-011]** Stop calling the 350 m radius a "leg" in 17 captions — derive the caption from `course_geometry` (350 m radius / ~495 m legs / 700 m base / ~1690 m lap) per ADR-008. `rounds.py:523,543,559`.
4. **[MED, RPT-011]** Make the caption's wind-position clause dynamic (or drop it) — "right margin" is wrong for 9 of 17 rounds. `rounds.py:546,562`.
5. **[LOW, RPT-016]** Link the Home page's "Sport-class rules" to the regulations index.
6. **[LOW, RPT-008]** Add an `EVENT_URL` source link to the Overview airframe claim (data exists in `analysis/pilot_equipment.csv`); optionally to the "Landings: A Clean Sweep" paragraph and the Ray-Ban Meta hardware claim.
7. **[INFO, docs]** Reconcile RPT-011's stale "wind vector in the right margin" wording in `docs/SPEC.json` against RPT-012.
8. **[Tests]** Add: external-link allowlist check (RPT-008); Title-Case + accent-bar assertions (DSN-001); polygon-drawn-last and 495/495/700 m scale check across all rounds (RPT-011); clockface dot-product across all rounds (RPT-012); laps-axis start/extent check across all rounds (RPT-013). All of these pass on the current build except the ones covering findings 2–4, which is the point.
