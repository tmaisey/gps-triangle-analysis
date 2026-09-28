# Output-quality review — `report/gps-triangle-world-masters-oschatz-2026.html`

**Reviewer:** output-quality (read-only)
**Date:** 2026-09-28T02:39
**Subject:** built deliverable, 2,839,573 bytes, 409 lines, 6,323 tags
**Method:** BeautifulSoup (`html.parser`, `html5lib`, `lxml` cross-check), `node --check` on the inline JS, `json.loads` on the embedded dataset, regex sweeps for external refs / emoji / lexical tics / typography, WCAG relative-luminance contrast computation, reconciliation of prose figures against `analysis/*.csv` and `analysis/phase_summary.md`. `uv run pytest -q` → **82 passed**.

---

## Verdict

**Structurally and typographically excellent; two content-accuracy defects and one accessibility defect should be fixed before the user reviews.**

The markup is clean — three independent parsers produce byte-identical tag counts (no implicit fix-ups), 236 ids with zero duplicates, zero dangling anchors, valid JS and JSON. Self-containment is perfect: no `<img>`, `<link>`, `<script src>`, `@import` or non-`data:` `url()` anywhere; fonts are inlined base64; the nine external URLs are all `<a href>` grounding links. No emoji (only `°`, `·`, `ä`, `ö` outside ASCII). No gradients, no coloured accent stripes, white background. All 71 `<figure>`s captioned. Lexical-tic sweep across 55 patterns returned one marginal hit. All headline numbers reconcile to source.

What lets it down: the Overview's Round 12 worked example asserts the opposite of what Round 12's own page and the pooled data say; every ground-track caption describes the course geometry in the exact terms ADR-008 rejects; and nothing in the navigation is reachable by keyboard.

---

## Blocker

### B1 — Overview Round 12 worked example contradicts the Round 12 page and the pooled data

`scripts/build/pages/overview.py:735-752` emits:

> "the leader breaks well off the course line to work better lift and **circles tighter**, while **Bill holds a neater but slower line**"
> caption: "…a concrete case of **the leader's off-course thermalling excursions and tighter turns against Bill's tidier but slower line**."

The Round 12 view (same figure, same flight) says the reverse:

> "**Bill flew a markedly longer line** than Jens Geider - about **2.54x the ground distance** over the same course - the extra length is **off-course loops** spent searching for and working lift. **Turn radii were comparable (42 m to 41 m).**"

The pooled Overview charts agree with the Round 12 page, not with the caption: distance-from-course median **Bill 46.8 m vs winner 37.0 m**, thermalling turn radius **Bill 38.0 m vs winner 29.2 m**. `line_eff_ratio_bill_vs_leader = 2.54` is Bill-over-leader by its own field name.

**Fix:** rewrite the worked-example point and caption to match the data — Bill ranges further off the course line and circles no tighter, which is the concrete instance of the pooled pattern. Check whether the intended story was inverted at authoring time or whether the sign of `line_eff_ratio_bill_vs_leader` was misread.

### B2 — All 17 ground-track captions state a course geometry ADR-008 explicitly rejects

`scripts/build/pages/rounds.py:523` → `leg = task.get("leg_length_m", "")` (value 350), interpolated at `:543-545` and `:557-559`:

> "the bold ink triangle is the factual **350 m-leg course** reconstructed from the .rct"

ADR-008: *"`length` is the **radius / half-base**, not the leg… the two legs are `radius·√2` (~495 m)… **Rejected:** equilateral 350 m legs (2× too small and the wrong shape)."* `scripts/build/data.py:404-414` builds it correctly (`leg = radius*sqrt(2)`, `hypotenuse_m = 2*radius`, `perimeter_m ≈ 1690`) — only the caption is wrong. 17 occurrences (14 distance + 3 speed variants).

**Fix:** use the values `course_geometry()` already returns, e.g. *"the factual course from the .rct — 350 m turnpoint radius, 700 m base, ~495 m legs (~1690 m lap)"*.

### B3 — Navigation and all cross-page links are keyboard-inaccessible

- 4 top-nav links have **no `href`**, so they are not in the tab order:
  `<a data-nav="home" onclick="showPage('home')">Home</a>` (× Home/Analysis/Recommendations/Innovations)
- **50 `a.xref`** cross-page links likewise have no `href` (`0 of 50`):
  `<a class="xref" id="home-link-analysis" data-page="analysis" data-anchor="ov-top">Performance Analysis</a>`
  These are the Home page's *only* navigation and every Analysis↔Recommendations↔Innovations cross-reference.
- **115 `div.section-head[onclick="toggleSection(this)"]`** — no `role="button"`, no `tabindex`, no `aria-expanded`, no key handler. Every collapsible is mouse-only.
- There is **no `.xref` rule in the CSS** (0 matches in the 7,632-char stylesheet), so xrefs also get no `cursor:pointer` — they look like links but the cursor stays an I-beam.

**Fix:** give the nav and xref anchors a real `href` (`href="#ov-top"` etc.; the delegated handler at `script:83-102` already intercepts `a.xref, a[href^="#"]` and calls `preventDefault`, so behaviour is unchanged). Add `role="button" tabindex="0" aria-expanded="true"` to `.section-head` plus an Enter/Space key handler, and toggle `aria-expanded` in `syncLabel()`. Add a `.xref{cursor:pointer}` rule.

---

## Should-fix

### S1 — Text colour contrast below WCAG AA

Computed against `#FFFFFF`:

| Token / value | Ratio | Used as text where | Verdict |
|---|---|---|---|
| `#75787B` (`--muted`) | **4.44:1** | 640 SVG `<text>` at 10–11 px; `.stat-tile .label` (0.82rem), `.section-toggle` (0.85rem), `.back-to-top` (0.8rem) | fails AA (4.5) |
| `#00A3E0` (`--leader`) | **2.87:1** | 69 SVG `<text>` at 9.5–10 px | fails badly |
| `#5C8F10` | **3.89:1** | 68 SVG `<text>` at 10–13 px | fails AA |
| `#86BC25` (`--primary`) | **2.27:1** | 1 SVG `<text>`: `<text … fill="#86BC25">median 38 m</text>` | fails |

**Fix:** darken `--muted` a touch (≈`#6E7174` clears 4.5:1) and introduce a text-only leader ink (≈`#0A6E96`) and green ink (≈`#4E7A0D`) for SVG labels; keep the bright values for fills. `--ink` (17.9:1), `--text-2` (7.4:1) and `--primary-dark` (6.7:1) are fine.

### S2 — 119 of 190 SVGs have non-descriptive accessible names

`aria-label` values: `"bullet"` ×51, `"violin"` ×17, `"laps"` ×17, `"wind"` ×17, `"solar"` ×17. A screen reader announces "image, bullet". (The 24 Overview charts are well labelled — e.g. `"Clean-lap time deficit vs the same-air leader"` — so this is a dashboard-generator gap only.)

**Fix:** build the label from the values already in hand, e.g. `aria-label="Entry speed: Bill 71 km/h, leader 95 km/h, 120 km/h cap"`.

### S3 — 51 dashboard SVGs have no caption; the dashboard is not a captioned figure

136 `.dash-cell`s; 119 contain an SVG; **51 of those have no `.dash-cap`** — `Laps` ×17, `Wind` ×17, `Solar radiation` ×17 (each has a `.dash-title` and `.dash-sub` only). None of the 17 `.dash-wrap` dashboards sits inside a `<figure>` and none has a `<figcaption>`. PRD §8: *"Every figure captioned."*

**Fix:** either add a `.dash-cap` to those three cell types, or wrap `.dash-wrap` in `<figure>` with one `<figcaption>` covering the dashboard.

### S4 — Flat heading hierarchy: 4 `h1`, 132 `h2`, no `h3`

Inside `view-round-1` the round title `<h2>Round 1 - 3 Aug 12:55</h2>` and its six subsections (`Visual Overview of Performance`, `Energy Management`, …) are all `h2` — siblings, not children. The CSS already ships `h3{font-size:1.2rem}` and `.section-head h3` rules that nothing uses.

**Fix:** demote `.section-head` headings inside round/overview views to `h3`.

### S5 — Template placeholder `lap(s)` leaks into prose, 42 times

> "Leader gained **1 lap(s)** here while Bill held station"

Appears in both the round summary and the Biggest-Loss Segment body of every round. **Fix:** pluralise (`1 lap` / `2 laps`).

### S6 — Elapsed-time windows read as clock times

> "Single biggest-loss window: **22:25-23:25** (60 s)" — in a round flown at 17:05.

Values are mm:ss from the start gate but parse as 10:25 pm. Also `9:31-10:31`, `18:05-19:05`, `10:58-11:58`, `7:03-8:03`, `10:45-11:45`.

**Fix:** render as `T+22:25–23:25` or "22:25–23:25 into the task".

### S7 — "Within-group rank … 38 pilots in group" on the three speed rounds

`<div class="dash-title">Within-group rank</div><div class="dash-bignum">29/38</div><div class="dash-sub">38 pilots in group</div>` (Rounds 4, 10, 16). The speed sprint is scored across the whole field, and the prose correctly says *"a one-lap flat-out task scored across all 38 pilots"* — the tile contradicts it.

**Fix:** for `task_type == "speed"`, label the tile "Field rank" / "38 pilots in the field".

### S8 — Two different circle-radius pairs for the same concept in one Overview section

- *Climb Geometry*: "in wider circles (**39 vs 33 m** radius)" — per-round mean of medians (`phase_summary.md`: 39.4 / 33.2).
- *Thermalling Turn Radius*, three subsections later: "circles about **30% wider** … (median **38.0 vs 29.2 m**)" — pooled per-point distribution.

Both reconcile to their own sources, but the reader sees the same quantity twice with different numbers (18% wider vs 30% wider) and no explanation.

**Fix:** say which is which in the captions ("per-round mean of medians" vs "pooled per-point median across the 14 distance rounds"), or quote one pair in both places.

### S9 — No `<noscript>`; the page is blank with JS disabled

`.page{display:none}` and no `.page.active` in the markup (`class="section collapsed"` count = 0, `class="page active"` count = 0) — visibility comes solely from `showPage('home')` at `script:111`. A sandboxed email preview that strips JS shows an empty document.

**Fix:** ship `page-home` as `class="page active"` in the generated markup (JS is then idempotent) and add a one-line `<noscript>` explaining that the other pages need JavaScript.

### S10 — `.dash svg` lacks `max-width`, so the dashboard overflows on narrow phones

`figure svg{max-width:100%;height:auto}` is correct, but `.dash svg{height:auto}` sets no width bound. The bullet charts carry `width="138"`; at ≤340 px viewport the 2-column grid gives ~132 px columns, so they overflow (currently masked by `html,body{overflow-x:hidden}`).

**Fix:** `.dash svg{max-width:100%;height:auto}`.

### S11 — Chart text becomes illegible at mobile widths

18 SVGs are `1120×980` and 17 are `980×600`. Scaled to a 360 px viewport (328 px content) that is 0.29–0.33×, rendering the 9.5–11 px labels at roughly **3–4 px**.

**Fix:** raise the label font sizes in the large charts, or add a `@media (max-width:720px)` variant with fewer/larger labels. Flag for the visual/UI reviewer to confirm against screenshots.

### S12 — Title Case over-applied and inconsistent in the 24 Point lead-ins

`Where The Ground Is Lost.` · `Consistency: Floor Vs Ceiling.` · `Progression Across The Week.` · `Score Per Round.` · `Laps Per Round.` · `Field Position & The Laps/Speed Scatter.` · `Landings: A Clean Sweep.` · `Round 12: A Worked Example.`

The `<h2>`s use the opposite convention (`Cumulative Laps vs Leader`, `What to Train from This Round`), so the file mixes two rules. The `<h2>`s themselves are clean — the only flag was `Entry Speed - Use the 120 km/h Cap`, a false positive on the unit.

**Fix:** lowercase articles/short prepositions/`vs` mid-title in the lead-ins to match the `<h2>` convention.

### S13 — Two anchor targets sit outside the `scroll-margin-top` rule

`.section, .summary, figure, h2, h3 { scroll-margin-top: 76px; }` covers 135 of 137 targets. `#ov-consistency` and `#ov-levers` are bare `<div>`s, so the 60 px sticky nav covers their first line when jumped to.

**Fix:** widen the selector to `[id]` or add those two ids.

---

## Nice-to-have

- **N1 — Typography.** 0 em dashes and 0 en dashes; **296** spaced hyphens (` - `) stand in for both appositives and numeric ranges (`61.9 vs 67.4`, `22:25-23:25`, `Round 1 - 3 Aug 12:55`). Also `2.54x` / `1.36x` → `×`, and `75 g/dm2` → `g/dm²`. At minimum use en dashes for numeric ranges.
- **N2 — Burger button.** `<button aria-label="Menu" class="burger" onclick="toggleBurger()">Menu</button>` — the only `<button>` of 41 with no `type`, and it never toggles `aria-expanded`.
- **N3 — No `:focus` / `:focus-visible` styling** (0 matches). Browser defaults survive (nothing sets `outline:none`), but a deliberate ring would help once B3 makes things focusable.
- **N4 — Landmarks/meta.** No `<meta name="description">`, no `<header>`/`<footer>`, no skip link. `<html lang="en">`, `<nav>` and `<main>` are present and correct.
- **N5 — No deep linking.** The delegated handler `preventDefault`s every `a[href^="#"]`, so `location.hash` never updates and the back button does not retrace page/view changes. `.back-to-top` links bypass this via `event.stopPropagation()`, so the hash updates only on those — slightly inconsistent.
- **N6 — Non-text contrast.** As chart marks on white: `--attention #ED8B00` 2.53:1, `--field #D0D0CE` 1.54:1, `--primary #86BC25` 2.27:1 — all below WCAG 1.4.11's 3:1 for graphics that carry meaning, including the 11×11 px `.dash-key i` legend swatches.
- **N7 — Untokenised colour.** `#5C8F10` (68 SVG labels) is hardcoded in the chart generators and absent from the `:root` token block.
- **N8 — "Mean round score 774"** is the 14-distance-round mean; the all-17 mean is 763.5. The sub-label says "median 794, sd 146" (also distance-only) but the tile does not say "distance rounds".
- **N9 — 106 links** all point at the same ranking URL. Correct but repetitive; consider one grounding link per section.
- **N10 — `pee-explain`** is on only 6 of 24 PEE blocks, so the Point→Evidence→Explain structure is not uniformly marked up (it is present in the prose).

---

## Verified clean

| Check | Result |
|---|---|
| Well-formedness | `html.parser` / `html5lib` / `lxml` all return 6,323 tags with identical per-element counts — no implicit fix-ups |
| Duplicate ids | 0 (236 ids, 236 unique) |
| Dangling `#` anchors | 0; `href="#"` no-ops 0; all 50 `data-anchor` targets resolve |
| Inline JS | `node --check` clean (4,096 chars) |
| Embedded data | `type="application/json"` parses; list of 17 rounds |
| Self-containment | 0 `<img>`, 0 `<link>`, 0 `<script src>`, 0 `@import`, 0 non-`data:` `url()`, 0 iframe/object/embed/video/audio. Fonts inlined base64 (233 KB). 9 external URLs, all `<a href>` grounding links |
| Emoji | none — 4 distinct non-ASCII chars: `°` ×35, `·` ×35, `ä` ×29, `ö` ×11 |
| Lexical tics | 55 patterns swept; 1 marginal hit (*"audible, not just present or absent"*). `Pike Paradigm` and `a real-time engine` are false positives |
| PRD §8 design | white background; no gradients (0 matches); no coloured accent bars — the only `border-top`s are 1 px `--hairline` greys on `.section`, `.home-links li`, `.dash-divider` |
| Figures | all 71 `<figure>`s have a `<figcaption>`; all 190 SVGs have a `viewBox` and `role="img"` |
| Tables | none (no overflow risk) |
| Controls | 41 buttons, all labelled; `<select id="view-select">` has a `<label for>`; 18 options ↔ 18 views |
| Test suite | `uv run pytest -q` → **82 passed** |

### Numeric reconciliation (spot-checks, all correct)

22nd of 38 and 12,562 pts (`events_bill.csv`) · winner 15,449, gap 2,887 · best-16-of-17 total = 12,980 − 418 = 12,562 · distance-round median 793.5 → 794, mean 774.3 → 774 · laps/round 8.714 → 8.7, median 9, population sd 4.13 → 4.1 · bombouts R9 = 3 laps/581, R12 = 2 laps/418 · 600 landing points on all 14 distance rounds, 0 penalties · cruise 61.9 vs 67.4 km/h, 8.2% → "~8%" · entry 70.8/94.5 → "71 vs 95", 49 km/h unused of the 120 cap · 22 s/lap deficit split 90.2% / 9.6% · height banked 40.7 vs 63.1 m → "41 vs 63", 35% less · circling 287 vs 402 s · climb 0.89/2.55 vs 1.03/3.64 m/s · Spearman ρ 0.608 → "+0.6", laps 0.523 → "+0.5" · pace effect 2.67 → "~2.7 laps".

The 76% / 24% distance-vs-speed gap split cannot be verified from the cached CSVs (the winner's per-round scores are not in `analysis/`), but it is internally consistent with the totals.
