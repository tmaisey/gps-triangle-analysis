# Architecture Decision Records

Standing decisions that constrain how the report is built. Kept lightweight (simple build). Status: `accepted` unless noted.

---

## ADR-001 — Single self-contained HTML file (inline SVG, embedded data)
**Status:** accepted
**Decision:** The deliverable is one `.html` file with charts as **inline SVG**, the per-round dataset embedded as JSON, and CSS/JS inlined. It renders standalone by opening the file. Web fonts load from Google Fonts via `<link>` with system fallbacks (graceful offline degradation); nothing else is remote.
**Rationale:** The user needs to email it and have anyone open it, offline. A file — not a hosted page.
**Rejected:** hosted dashboard/claude.ai artifact (not a sendable file); CDN chart libraries (offline fragility, generic look); rendered PNG charts (not crisp, larger, no text scaling).
**Refs:** SPEC RPT-001, DSN-001.

## ADR-002 — Deterministic Python build harness generates the HTML
**Status:** accepted
**Decision:** A Python harness reads `analysis/` outputs and emits the HTML; the HTML is generated, not hand-maintained. Modular: shared library (design tokens, chart functions, layout components, data loaders) + one module per page, composed by an assembler.
**Rationale:** Repeatable and testable — figures reconcile to source data, and the report regenerates when data changes. Modules let build subagents work in parallel without clobbering one file.
**Rejected:** hand-authored HTML (drifts from data, not reconcilable, not parallelisable).
**Refs:** SPEC RPT-001; PRD §11.

## ADR-003 — Same-air (within-group) leader is the per-round benchmark
**Status:** accepted
**Decision:** Each round compares Bill to the top scorer in **his own heat-group** (same time slot, same air). The overall event winner is referenced only where co-grouped with Bill.
**Rationale:** Scores are normalised within a group; different groups fly different thermals, so cross-group comparison confounds skill with conditions.
**Rejected:** benchmarking every round against the event winner (unfair; conflates conditions and skill).
**Refs:** PRD §9; SPEC ANL-001, ANL-004.

## ADR-004 — Multi-page client-side app in one file
**Status:** accepted
**Decision:** JS-toggled pages within the single file: Home / Analysis / Recommendations / Innovations for the initial product, plus a **Methodology** page added in a later phase (five total). Recommendations are one canonical set, surfaced **inline in Analysis** and **consolidated by theme** on the Recommendations page via shared anchor ids; Analysis and Recommendations cross-link to Innovations points. The Analysis **Overview** is organised into four Title-Case thematic sections — **Headline Result**, **Scoring, Laps & Speed**, **Start Energy**, **Conditions, Trajectory & Climbing** — under an "Overall Read" lead paragraph (RPT-022; replaces the old single Performance-Summary umbrella).
**Rationale:** Organises dense content and keeps evidence, action, and future ideas navigable and in context — while staying one file.
**Rejected:** multiple files (breaks single-send); one long scroll page (poor navigability).
**Refs:** SPEC RPT-002, RPT-005, RPT-006, RPT-009.

## ADR-005 — Bespoke inline-SVG charts, not a charting library
**Status:** accepted
**Decision:** Chart types (altitude/energy trace, ground-track overlay, cumulative laps, phase bars, scatter, waterfall, progression, climb distributions, metric strips) are authored as bespoke SVG generators in the harness.
**Rationale:** Self-containment (ADR-001), full control of the palette and the no-AI-tell / no-emoji design rules, and consistent theming across every figure.
**Rejected:** Chart.js/Plotly/D3 (remote or heavy bundle, generic styling that fights the design constraints).
**Refs:** SPEC DSN-001, RPT-003, RPT-004.

## ADR-006 — Methodology page durations from harness metadata + captured verbatim prompts
**Status:** accepted
**Decision:** The Methodology narrative sources agent working-durations and token/tool counts from the harness's subagent metadata (exact) and the user's verbatim prompts from a running capture in `docs/METHODOLOGY_LOG.md`. Inter-message human think-time is not instrumented, so it is not fabricated — human interjections are marked positionally, not timed.
**Rationale:** Durations must be truthful; the only precise timings available are agent run-times. Capturing verbatim prompts as the work happens protects them from later context summarisation.
**Rejected:** a full OTEL/event trace (overkill, not the intent); estimating human gap-times (would be invented).
**Refs:** SPEC RPT-010; docs/METHODOLOGY_LOG.md.

## ADR-007 — Visual/UI review via Playwright in the review stage
**Status:** accepted
**Decision:** The build-review workflow includes a subagent driving Playwright (CLI) to render the file and screenshot every page at desktop and mobile widths, checking layout/charts/nav/collapsibles/overflow before the user reviews. It is a review-stage QA activity, not a committed unit test in the suite.
**Rationale:** SVG/CSS layout correctness is not reliably caught by DOM-structure tests; a rendered visual pass catches overflow, clipping, and broken charts a human would otherwise have to find.
**Rejected:** relying only on BeautifulSoup structure tests (no rendering); manual-only visual QA (slower, later).
**Refs:** SPEC QA-001; AGENTS.md build-review workflow.

## ADR-008 — Course geometry from the .rct header (right-isosceles)
**Status:** accepted
**Decision:** Per heat, parse the `.rct` `T:` header (start, axis, `length`) and build the three turnpoints as `start + radius` at bearings `{axis, axis+180, axis-90}`, with the apex at `axis-90` (a fixed venue side, pointing away from the ground/safety zones) and `radius = length = 350 m`. The course is a **right-isosceles** triangle: the 700 m hypotenuse (base) runs along the axis with the start at its midpoint, the two legs are `radius·√2` (~495 m), and the perimeter is ~1690 m — the regs lap. Course and GPS tracks share **one** equirectangular projection (cos(lat) longitude, identical for both), validated against the flown corners (pilots round just outside the turnpoints).
**Rationale:** The `.rct` `RectZones` are ground/safety zones, not turnpoints; only the header defines the course, and `length` is the **radius / half-base**, not the leg. Confirmed by the frame/geometry tests and the 1690 m perimeter matching the Sport-class regs lap.
**Rejected:** equilateral 350 m legs (2× too small and the wrong shape); fitting the triangle to the flown tracks (circular — the course is the reference the tracks are judged against, not derived from them).
**Refs:** SPEC RPT-011; `scripts/build/data.py` `course_geometry`.
