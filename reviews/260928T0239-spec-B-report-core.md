# Spec review B — report core (RPT-001/002/009/003/004/005/006/007)

Reviewer: spec-reviewer B (read-only). Date: 2026-09-28.
Artefacts inspected: `docs/SPEC.json`, `docs/PRD.md` §8, `tests/test_html_structure.py`,
`tests/test_content_present.py`, `tests/test_shared_foundation.py`, `scripts/build/*`,
`scripts/build/pages/*`, and the built
`report/gps-triangle-world-masters-oschatz-2026.html` (2,839,573 bytes, parsed with
BeautifulSoup).

Suite status: `uv run pytest -q` → **82 passed** (exit 0).
Build freshness: `assemble.build_html()` output is **byte-identical** to the committed
report file, so assertions made against the build code hold for the artefact on disk.

## Verdicts

| Spec | Verdict | One-line reason |
|---|---|---|
| RPT-001 | PASS | Zero remote script/style/img/font deps; fonts inlined (8 × woff2 data URI); 190 inline SVGs; 17 rounds of data embedded as JSON. |
| RPT-002 | PASS | Four right-aligned nav links, plain-text title, burger at ≤720 px, `showPage('home')` on load, 18-option Analysis dropdown with `overview` first. |
| RPT-009 | PASS-WITH-GAPS | Home output is exactly right, but **no test covers the spec's own test step**; the three "linked headings" are styled `<a>`, not heading elements. |
| RPT-003 | PASS-WITH-GAPS | All 24 Overview insights have a bold title + text before the plot; but the test is far weaker than the spec step (no per-insight evidence/recommendation assertion). |
| RPT-004 | PASS-WITH-GAPS | All 17 rounds render dashboard + energy + track + laps with the mandated titles and insight-first openings; no test asserts the Title→Insight→Visual ordering or the three literal titles. |
| RPT-005 | PASS-WITH-GAPS | `rec-entry` and `rec-turns` carry **no "Further Analysis"** block; `rec-signals` has **no back-link to Analysis evidence**; no dedicated test. |
| RPT-006 | PASS-WITH-GAPS | Innovations is standalone, anchored and rules-cited, but there are **zero Analysis→Innovations xrefs** (Recommendations→Innovations = 6), so half the mandated cross-link direction is unbuilt. |
| RPT-007 | PASS-WITH-GAPS | Every per-round summary bullet is just the section **title**, not a "key point/recommendation"; and no test checks bullets, back-to-top or the toggle behaviour. |

---

## RPT-001 — Single self-contained HTML file — **PASS**

Evidence (parsed from the built file):

- `<script>` tags: 2, **none with `src`**. `<link>` tags: **0**. `<img>`: 0. `<iframe>`/`<object>`: 0.
- No `url(http…)` in CSS; no `<image href>` inside any SVG.
- `data:font/woff2;base64,` × 8, `@font-face` × 8 (`scripts/build/design.py:57` retires
  `GOOGLE_FONTS_LINK` to `""`), so `components.head()` emits no font link.
- Charts: `<svg` × 190, ≈1,956 KB of inline SVG.
- Per-round data embedded at `scripts/build/assemble.py:75` as
  `<script type="application/json" id="round-data">` — 17 round objects, ≈397 KB.
- The only `http(s)` references are `<a href>` citations (rcmodelspot, gps-triangle.net,
  open-meteo, sm-modellbau, onlinecontest, bmfa, xreal, rokid) plus the SVG XML namespace —
  none of which are required to render.

Test coverage: `tests/test_html_structure.py:102-116` asserts all of the above
(no `script src`, data-URI `img`, no stylesheet `link`, no googleapis/gstatic, fonts inlined).

Gap (minor, test-only): the spec step says "**size reasonable**"; nothing asserts it.
The file is 2.84 MB (SVG 1.96 MB, data 0.4 MB, fonts 227 KB). Emailable, but unguarded
against future growth.

**Recommended fix:** add `test_output_size_within_budget` asserting
`len(assemble.build_html().encode()) < 4_000_000` so a regression in chart precision or
data embedding cannot silently push the file past a mail-gateway limit.

## RPT-002 — Four-page app + top nav — **PASS**

Evidence:

- `scripts/build/components.py:56-77` — `<nav class="topnav">` with
  `<span class="topnav-title">GPS Triangle World Masters, Oschatz 2026</span>` (plain text,
  no emoji/logo), a `<button class="burger">Menu</button>`, and
  `<div class="topnav-links">` of four `<a data-nav=… onclick="showPage('…')">`.
  Built output nav labels: `['Home','Analysis','Recommendations','Innovations']`.
- Right alignment: `design.py:183-191` `.topnav-inner { display:flex; justify-content:space-between }`
  with the title first and the links last (burger is `display:none` on desktop), so the link
  cluster sits hard right.
- Burger: `design.py:395-412`, `@media (max-width: 720px) { .burger { display:inline-block } .topnav-links { display:none } .topnav-links.open { display:flex } }`;
  `toggleBurger()` at `assemble.py:110-113`.
- Routing: `assemble.py:91-99` `showPage` toggles `.page.active`; `design.py:229-230`
  `.page{display:none} .page.active{display:block}` — exactly one page visible at a time.
  `assemble.py:196` calls `showPage('home')` on load.
- Analysis dropdown: `assemble.py:35-49`; built output has **18** `<option>`s,
  `options[0].value == "overview"`, labels `Overview`, `Round 1 - 3 Aug 12:55` …
  `Round 17 - 8 Aug 13:25`, with `(speed)` appended on rounds 4/10/16.
- `showView` (`assemble.py:101-108`) toggles `.view.active`; `design.py:337-338` hides the rest.

Test coverage: `test_html_structure.py:48-51, 54-57, 60-66, 69-75` covers the four links,
title, Home default and the 18 options. Right-alignment and the burger media query are not
asserted but are verified visually by the QA-001 Playwright pass, so no fix proposed.

## RPT-009 — Home page — **PASS-WITH-GAPS**

Evidence (`scripts/build/pages/home.py`, built `#page-home`):

- `<h1>GPS Triangle World Masters, Oschatz 2026</h1>`, one summary paragraph naming
  **Bill Maisey** (Anglesey MAC), 38 pilots, 17 rounds, 22nd, with the rcmodelspot event page
  linked. Total Home text = 1,009 chars; **0** `.section`, **0** `.summary` (correctly minimal,
  per PRD §8 "Home stays minimal (no collapsing)").
- Exactly **three** `a.xref`, all resolving:
  `home-link-analysis → analysis#ov-top`, `home-link-recommendations → recommendations#rec-top`,
  `home-link-innovations → innovations#inn-top` (`home.py:29-42, 66-73`).
  Total anchors on Home = 4 (the three + the event link).

**Gap 1 (test):** the spec step "Home holds a summary paragraph and exactly three section links
that navigate to Analysis/Recommendations/Innovations" is **not tested anywhere**. The only
Home coverage is `test_content_present.py:27-33` (`len(text) > 400`, no `[STUB]`), which would
still pass if a link were dropped or a fourth added. Grep confirms no test references `RPT-009`
beyond the module docstring.

**Recommended fix:** add to `tests/test_content_present.py`:

```python
def test_home_summary_and_exactly_three_section_links(soup):
    home = soup.select_one("#page-home")
    assert home.find("p") and "Bill Maisey" in home.get_text()
    xrefs = home.select("a.xref")
    assert [(a["data-page"], a.get_text(strip=True)) for a in xrefs] == [
        ("analysis", "Performance Analysis"),
        ("recommendations", "Recommendations"),
        ("innovations", "Innovations"),
    ]
    assert not home.select(".section")  # Home stays minimal
```

**Gap 2 (cosmetic/semantic):** the spec wording is "the three sections listed as linked
**headings**". They render heading-like (`design.py:344-350`: heading font, 1.35 rem, block,
rules above/below) but are bare `<a>` inside `<li>`, with no `h2`. Screen-reader users get no
document outline for the three sections.

**Recommended fix:** in `home.py:67-72` wrap the link in a heading —
`<li><h2 class="home-link"><a class="xref" …>…</a></h2><p class="home-link-desc">…</p></li>` —
and retarget `.home-links a` → `.home-links h2 a` in `design.py:344`. Purely additive; no test
depends on the current shape.

## RPT-003 — Overview content — **PASS-WITH-GAPS**

Evidence (built `#view-overview`):

- Four Title-Case sections in DOM order: `ov-headline` "Headline Result", `ov-scoring`
  "Scoring, Laps & Speed", `ov-start-energy` "Start Energy", `ov-conditions`
  "Conditions, Trajectory & Climbing".
- **24** `p.pee-point` insights; **every one** opens with a `<strong>` short title
  (`pee-points without <strong> title: []`) and **every one of the 20 figures has an insight
  paragraph before it in DOM order** (`figures with NO preceding insight text: []`) — the
  "text BEFORE the plot" rule holds without exception.
- Spec-required coverage all present: result (`The Result.` — 22nd/38, 12,562 pts, 2,887 behind),
  strengths/weaknesses (`Landings: A Clean Sweep.`, `Where The Ground Is Lost.`), phase levers
  ranked (`#ov-levers`), conditions (`Conditions Dependence.`), progression
  (`Progression Across The Week.`), consistency (`Consistency: Floor Vs Ceiling.`),
  prioritised recommendations (6 × "What to do.", at least one per section, each xref'd to the
  canonical `rec-*` anchors).
- Lexical tics: `test_html_structure.py:178-195` enforces the ban (incl. standalone "real").

**Gap (test strength):** the spec step is "*each* Overview insight has an evidence
figure/number and an explain/recommendation". The actual test
(`test_content_present.py:98-109`) only asserts the *absence* of `Point.`/`Evidence.`/`Explain.`
labels and the *presence of the string* `"What to do."` once anywhere in the Overview. It would
pass with 23 of 24 insights stripped of evidence. Four insights currently carry no figure
(`The Overall Read.`, `The Result.`, `Landings: A Clean Sweep.`, `The Airframe Question.`) —
all four do carry numbers, so the spec is met, but nothing holds that in place.

**Recommended fix:** add a per-insight assertion, e.g. for each `p.pee-point` in
`#view-overview` require either a following `<figure>` before the next `pee-point` **or** a
digit in its own text, and assert `>= 1` "What to do." paragraph per `.section`:

```python
for sec in soup.select("#view-overview .section"):
    assert "What to do." in sec.get_text(), sec.get("id")
```

## RPT-004 — Per-round views — **PASS-WITH-GAPS**

Evidence (all 17 views sampled programmatically; rounds 1/4/12/17 inspected in full):

- Every round has 6 collapsible sections. Distance rounds:
  `Visual Overview of Performance`, **`Energy Management`**, **`Ground Track & Course`**,
  **`Cumulative Laps vs Leader`**, `Biggest-Loss Segment`, `What to Train from This Round`
  — the three mandated titles match the spec strings exactly.
  Speed rounds (4/10/16) substitute `Single-Lap Speed Task` + `Where the Time Went`, and the
  dropdown labels them `(speed)` — "speedruns labelled distinctly" satisfied.
- Each round carries `r{n}-fig-energy`, `r{n}-fig-track`, `r{n}-fig-laps`, all `<figure>`s with
  non-empty `<figcaption>`, plus 8 `.dash-cell`s and a `.dash-key` (metrics strip incl. wind and
  solar weather cells).
- **Ordering:** for every section that has a visual, the section renders
  h2 title → insight paragraph(s) → figure. Measured text-before-first-figure lengths are
  268–403 chars per section across rounds 1/4/12/17; zero sections put the plot first.
- **Insight-first openings** (all 17 checked): e.g. R1 Energy "*Bill flew lower than Ralph
  Losemann for essentially the whole flight, averaging…*"; R12 Ground Track "*Bill flew a
  markedly longer line than Jens Geider — about 2.54× the ground distance…*"; R17 Cumulative
  Laps "*Bill matched Jens Geider lap-for-lap the whole way…*". None opens by describing the
  plot type. The dashboard lead-in is 1 paragraph of 3–5 round-specific insight sentences
  before the SVG in every round sampled.

Test coverage: `test_content_present.py:43-48` (an SVG per round), `:51-62` (8 dash-cells,
`.dash-key`, energy + track figure ids per round), `:98-109` (no PEE labels, `km/h` present,
prose > 400 chars per round). That is reasonable coverage.

**Gap (test strength):** nothing asserts (a) the three literal section titles, (b) the
Title→Insight→Visual ordering, or (c) that the opening sentence is an insight rather than a
plot description. A refactor could reorder the figure above the prose and the suite would stay
green.

**Recommended fix:** add to `tests/test_content_present.py`:

```python
@pytest.mark.parametrize("n", [n for n in range(1, 18) if n not in (4, 10, 16)])
def test_round_sections_are_title_text_then_visual(soup, n):
    titles = [s.select_one("h2").get_text(strip=True)
              for s in soup.select(f"#view-round-{n} .section")]
    for t in ("Energy Management", "Ground Track & Course", "Cumulative Laps vs Leader"):
        assert t in titles
    for s in soup.select(f"#view-round-{n} .section"):
        body = s.select_one(".section-body")
        fig = body.find("figure")
        if fig is None:
            continue
        els = body.find_all(True)
        prose = " ".join(e.get_text(" ", strip=True)
                         for e in els[:els.index(fig)] if e.name == "p")
        assert len(prose) > 150, (n, s.get("id"))
```

## RPT-005 — Recommendations inline + consolidated — **PASS-WITH-GAPS**

Evidence (built `#page-recommendations`, `scripts/build/pages/recommendations.py`):

- Five themed sections with stable anchors: `rec-cruise` (Cruise Speed Between Thermals),
  `rec-climb` (Climb Quality — Height Banked Per Thermal), `rec-entry`
  (Entry Speed — Use the 120 km/h Cap), `rec-turns` (Turnpoint Lines), `rec-signals`
  (Rules-Legal Live Signals).
- Sub-headings render as **bold Title-Case `<strong>` labels at body size**, not headings
  (`h3`/`h4` counts on the page are both 0): `Drills` × 4, `Further Analysis` × 2,
  `Where Technology Could Help` × 1 — the RPT-005 styling clause is met.
- Shared-anchor round trip works both ways and all links resolve
  (`test_html_structure.py:127-138` proves no dangling `data-anchor`):
  Analysis → Recommendations = **34** xrefs onto `rec-cruise`/`rec-climb`/`rec-entry`/`rec-turns`
  (6 from the Overview "What to do." paragraphs, the rest from the 17 per-round
  `#r{n}-reco` sections); Recommendations → Analysis = 5; Recommendations → Innovations = 6.

**Gap 1 (content):** the spec's test step requires *"every top-level weakness has at least one
drill **and** one further-analysis suggestion"*. Per-section `<strong>` labels:

| Section | Drills | Further Analysis | Innovations link | Analysis back-link |
|---|---|---|---|---|
| `rec-cruise` | yes | yes | — | `ov-levers` |
| `rec-climb` | yes | yes | `inn-navigator`, `inn-live` | `ov-levers`, `ov-consistency` |
| `rec-entry` | yes | **missing** | — | `ov-levers` |
| `rec-turns` | yes | **missing** | — | `ov-levers` |
| `rec-signals` | (`Set up now`) | (`Resources`) | 4 links | **none** |

`rec-entry` and `rec-turns` are top-level weakness themes and carry no Further Analysis block.

**Recommended fix:** in `scripts/build/pages/recommendations.py`, add a `Further Analysis`
bullet to `rec-entry` (e.g. "quantify the opening-lap time value of each 10 km/h of unused
entry-speed cap across the 14 distance rounds") and to `rec-turns` (e.g. "measure per-turnpoint
arc radius and exit-speed retention against the leader to confirm the ~2 s/lap estimate"), each
xref'd to its Analysis evidence.

**Gap 2 (content, minor):** `rec-signals` has no back-link to Analysis evidence, though the spec
says each recommendation links back to its supporting evidence. Add an xref to
`#ov-levers` or `#ov-conditions` from its lead sentence.

**Gap 3 (test):** RPT-005 has **no dedicated test**. Coverage is only the generic
`test_xref_anchors_all_resolve`, which proves links are not dangling but not that every weakness
has a drill + further-analysis, nor that every canonical rec is surfaced inline in Analysis.

**Recommended fix:**

```python
WEAKNESS_SECTIONS = ["rec-cruise", "rec-climb", "rec-entry", "rec-turns"]

@pytest.mark.parametrize("sid", WEAKNESS_SECTIONS)
def test_each_weakness_has_drill_and_further_analysis(soup, sid):
    body = soup.select_one(f"#{sid} .section-body")
    labels = {s.get_text(strip=True).rstrip(".") for s in body.find_all("strong")}
    assert "Drills" in labels and "Further Analysis" in labels, (sid, labels)
    assert body.select("a.xref[data-page=analysis]"), f"{sid} has no Analysis back-link"

def test_every_rec_anchor_is_referenced_inline_from_analysis(soup):
    rec_ids = {s["id"] for s in soup.select("#page-recommendations .section")}
    linked = {a["data-anchor"]
              for a in soup.select("#page-analysis a.xref[data-page=recommendations]")}
    assert rec_ids - {"rec-signals"} <= linked
```

## RPT-006 — Innovations page — **PASS-WITH-GAPS**

Evidence (built `#page-innovations`, `scripts/build/pages/innovations.py`):

- Own page (`#page-innovations`), `<h1>Innovations</h1>`, four anchored tiers:
  `inn-postflight` (Post-Flight AI Coach), `inn-navigator` (Navigator AR HUD), `inn-live`
  (Live AI Cueing), `inn-flywheel` (The Data Flywheel), plus `inn-top`.
- Four `p.legality` "Legality Consideration." paragraphs (bold inline, no heading element —
  `components.py:236-254`), three of which cite the rules basis by link:
  `inn-navigator` → gps-triangle.net regulations index; `inn-live` → the Sport-class regs PDF
  (`regs section 2.7`); `inn-postflight` → OLC-RC (its claim is "no competition constraint —
  offline"). `inn-flywheel` carries no link, but its claim is also "purely offline and
  historical", so no rules cite is needed.
- `test_html_structure.py:159-169` proves every `section 2.7` mention sits inside a
  gps-triangle.net anchor; `:149-156` proves no "Legality gate" wording remains.
- All inbound `a.xref[data-page=innovations]` resolve to a real `inn-*` id.

**Gap (content):** the spec is "*each point anchored so **Analysis** and Recommendations can
link to it in context*", with the test step "anchor links from **Analysis**/Recommendations
resolve to the right point"; PRD §8 states "Analysis ↔ Recommendations ↔ Innovations are
cross-referenced". Measured: `#page-recommendations a.xref[data-page=innovations]` = **6**;
`#page-analysis a.xref[data-page=innovations]` = **0**. The Analysis→Innovations direction is
never built, so that half of the test step passes only vacuously.

**Recommended fix:** add two or three Analysis→Innovations xrefs where the evidence directly
motivates a tier — from the Overview `Climb Geometry.` / `Thermalling Turn Radius.` "What to
do." paragraph to `inn-live` (live climb-rate cueing), and from `Conditions Dependence.` or the
Round 12 worked example to `inn-navigator`. Then strengthen the assertion:

```python
def test_analysis_links_out_to_innovations(soup):
    anchors = {a["data-anchor"]
               for a in soup.select("#page-analysis a.xref[data-page=innovations]")}
    assert anchors, "Analysis never links out to Innovations"
    assert anchors <= {s["id"] for s in soup.select("#page-innovations .section")}
```

**Gap (test):** RPT-006 otherwise has no dedicated test — nothing asserts the four tiers exist,
that each has a Legality Consideration, or that the page is standalone.

**Recommended fix:** add
`test_innovations_tiers_each_have_a_legality_consideration` asserting the four `inn-*` section
ids and that each `.section-body` contains a `p.legality`.

## RPT-007 — In-page summary + collapsible sections — **PASS-WITH-GAPS**

Evidence (all 18 Analysis views + both standalone pages measured):

| View | Summary | Bullets | Sections | Back-to-top | Expand/Collapse | Dangling bullets | Collapsed on load |
|---|---|---|---|---|---|---|---|
| `view-overview` | yes (`#ov-top`) | 4 | 4 | 4 | 2 | 0 | 0 |
| `view-round-1..17` | yes (`#r{n}-top`) | 6 | 6 | 6 | 2 | 0 | 0 |
| `page-recommendations` | yes (`#rec-top`) | 5 | 5 | 5 | 2 | 0 | 0 |
| `page-innovations` | yes (`#inn-top`) | 4 | 4 | 4 | 2 | 0 | 0 |

- Every bullet `href="#…"` resolves to an on-page id (0 dangling across all 20 views).
- Each section header carries `<a class="back-to-top" href="#{top_id}" onclick="event.stopPropagation()">`
  (`components.py:154-155`) — the stopPropagation correctly prevents the header's
  `toggleSection` firing and lets the native jump run.
- **All sections start expanded** on every page: `components.py:143` hard-codes
  `cls = "section"` (no `collapsed`), and the built file has **zero** `.section.collapsed` —
  the RPT-007 amendment is honoured. Initial toggle label is `Collapse` (`components.py:147`),
  kept in sync by `syncLabel` (`assemble.py:117-121`) — RPT-014's dynamic label.
- `expandAll`/`collapseAll` (`assemble.py:139-148`) scope to `currentScope()` =
  `.page.active .view.active` falling back to `.page.active`, so they toggle exactly the
  sections of the visible view, and the `.summary` block (not a `.section`) **stays visible**
  under Collapse all — the spec's "summary stays visible" clause holds by construction.

**Gap 1 (content):** the spec requires "~5 bullets of **key points/recommendations**".
The Overview bullets are genuine key points
("*22nd of 38 (12,562 pts); the gap is almost all distance-task*",
"*Cruise speed between thermals is the dominant lever*"), but in **all 17 round views** the
bullets are the literal section titles:
`['Visual Overview of Performance', 'Energy Management', 'Ground Track & Course',
'Cumulative Laps vs Leader', 'Biggest-Loss Segment', 'What to Train from This Round']`.
That is a table of contents, not key points — the reader gets no takeaway from the summary
list. (The round summary *prose* above it is substantive; only the bullets are the issue.)

**Recommended fix:** in `scripts/build/pages/rounds.py`, generate each bullet from the same
round facts already computed for the section prose, e.g.
`("r{n}-energy", f"Flew {alt_gap:.0f} m lower than {leader} for most of the flight")`,
`("r{n}-laps", f"{bill_laps} laps to {leader_laps}; the gap opened in the back half")`,
`("r{n}-reco", f"Lever this round: {lever}")`. Keep the anchor ids unchanged so nothing else
moves.

**Gap 2 (test):** RPT-007's test step is "each page has a summary with ~5 bullets that anchor to
on-page section ids; each section header links to top; Expand all/Collapse all toggle every
section; summary stays visible". The only test is
`test_html_structure.py:78-83`, which asserts the **strings** `"Expand all"` and
`"Collapse all"` appear in the document text. None of the four clauses is actually tested.

**Recommended fix:** add a structural test (no browser needed) and let the QA-001 Playwright
pass cover the runtime toggle:

```python
VIEWS = ["view-overview"] + [f"view-round-{n}" for n in range(1, 18)]

@pytest.mark.parametrize("vid", VIEWS)
def test_view_summary_bullets_and_back_to_top(soup, vid):
    view = soup.select_one(f"#{vid}")
    summ = view.select_one(".summary")
    assert summ is not None and summ.find("p").get_text(strip=True)
    ids = {e["id"] for e in view.select("[id]")}
    bullets = summ.select("li a")
    assert 3 <= len(bullets) <= 7
    titles = {s.select_one("h2").get_text(strip=True) for s in view.select(".section")}
    for a in bullets:
        assert a["href"][1:] in ids, a["href"]
        assert a.get_text(strip=True) not in titles, \
            f"{vid}: bullet is a section title, not a key point"
    assert len(view.select("a.back-to-top")) == len(view.select(".section"))
    assert not view.select(".section.collapsed")   # expanded by default
    assert len(view.select(".controls button")) == 2
```

Note the `bullet not in titles` assertion is the red test for Gap 1 — it fails today for all 17
round views and passes for the Overview.

---

## Summary of recommended fixes, by severity

1. **Content — RPT-007:** replace the 17 round-view summary bullets (currently section titles)
   with data-derived key points. Highest reader-facing impact.
2. **Content — RPT-005:** add a `Further Analysis` block to `rec-entry` and `rec-turns`; add an
   Analysis back-link to `rec-signals`.
3. **Content — RPT-006:** build the missing Analysis→Innovations cross-links (currently 0).
4. **Test — RPT-007/005/006/009:** add the structural tests above; these four specs are marked
   `passes: true` on essentially no dedicated coverage.
5. **Test — RPT-003/004:** tighten to per-insight evidence/recommendation and
   Title→Insight→Visual ordering assertions.
6. **Semantic — RPT-009 (cosmetic):** wrap the three Home section links in `<h2>`.
7. **Test — RPT-001 (cosmetic):** add an output-size budget assertion.
