# GPS Triangle — Bill Maisey performance analysis & coaching report

Product requirements and plan. Captures intent ahead of the build so the deliverable and its scope are agreed before construction.

*Status: the four-page v2 report is **built and refined** — `report/gps-triangle-world-masters-oschatz-2026.html` (Home / Analysis / Recommendations / Innovations). Data, analysis, per-round views, and the restructured four-section Overview are all rendering. Remaining: the build-review workflow, then the Methodology page (RPT-010) + its review, then the repo README (DOC-001). Last updated 2026-09-28.*

> **Next step:** run the build-review workflow (see AGENTS.md) — output-quality + Playwright visual/UI + batched spec reviewers → consolidate → propose fixes → user accepts. Only then build the Methodology page, review it, and finally write the README.*

## 1. Vision

Turn the public timing/telemetry data from an RC GPS Triangle competition into a clear, evidence-led **coaching report** for pilot **Bill Maisey (William Maisey)** — showing where he is strong, where he loses ground to the best pilots, and what to train to improve. The report must stand alone as a single file that can be emailed and opened by anyone.

## 2. Subject & data source

- **Pilot:** Bill Maisey, club Anglesey MAC (GB). `userGuid 2e6eb0fb-d61f-410c-a08e-313b1dd87977`.
- **Anchor event:** *World Masters, Sport class, Oschatz (Germany), 3–8 Aug 2026.* 38 competitors, 17 rounds. Bill finished **22nd/38** (12,562 pts); winner Florian Griese (15,449).
- **Data platform:** `rcmodelspot.com` — an open, anonymous JSON REST API (`/api`). Exposes per-flight scores, the heat/group tree, competitor identities, and **full ~1 Hz GPS tracks for every pilot** (lat/lon/alt/vario/groundspeed/bearing), plus per-flight lap/triangle events. This makes trajectory-level analysis possible, not just standings.
- **Weather:** Open-Meteo ERA5 archive (free, no key) at the Oschatz task coordinates, hourly, mapped to each flight's start time.

## 3. Sport model (grounds the analysis)

Sport class: a ~30-minute task. The motor is used **only** to climb to a capped start altitude (max entry altitude 400 m, max entry speed 120 km/h); after crossing the start line the motor is off and the flight is a pure glide. Pilots convert an altitude/energy budget into as many 350 m-leg triangle laps as possible, using thermals to stay aloft. **Laps completed drive the score; average speed is the tie-break; a clean landing scores landing points.** Three of the 17 rounds (heats 4, 10, 16) are a separate **one-lap speed sprint**, scored differently, and are analysed separately.

**Fairness principle:** scores are normalised to 1000 *within each heat-group* (~9–10 pilots flying the same time slot / same air). The like-for-like comparison is therefore **Bill vs the top scorer in his own group each round**, not vs the overall winner across different air. The report uses the same-air leader as the benchmark and states this.

## 4. Goals

1. Give Bill a prioritised, actionable view of what to train, backed by evidence from his own flights.
2. Separate genuine skill from conditions and luck (within-group normalised score vs raw laps).
3. Show progression across the six days (practice effect) distinct from conditions.
4. Explore the "art of the possible" for future coaching technology, grounded in the competition rules.

**Non-goals:** live/in-flight tooling; a general-purpose analytics product; ranking prediction; comparison against pilots in different air as if equivalent.

## 5. Users & audience

Primary: Bill (pilot) and whoever coaches/spots for him. Secondary: club/family. Tone is analytical and respectful; the report should be readable by a non-analyst.

## 6. Scope

**In scope:** the Oschatz 2026 event — full depth. Standings, per-round scores, per-round GPS trajectories (Bill vs same-air leader), flight-phase decomposition (start / straight / turn / climb), weather correlation, week-long progression, and a forward-looking coaching-technology section.

**Out of scope (with reason):**
- **Multi-event / season trend.** Intended, but **not feasible**: the rcmodelspot API has no search/list endpoint, the season league feeds do not contain Bill (championships are not league rounds), and UK Free Glide League events are not discoverable through it. Only the Oschatz event is retrievable. *Re-openable if Bill supplies URLs/GUIDs of his other events — the same pipeline would ingest them.*
- Speed-sprint deep trajectory analysis beyond noting the top-end gap.

## 7. Findings that inform the report (evidence basis)

Established from the data pulls (subject to the weather and phase passes finalising):

1. **Biggest lever — cruise speed between thermals.** Bill's clean-lap cruise is ~8% slower than his same-air leader (61.9 vs 67.4 km/h; glide ratio 9.3 vs 10.3). This is ~90% of his 22 s/lap clean-lap deficit *and* the dominant driver of his lower lap count (a pace counterfactual attributes ≈ +2.7 of the ~3-lap gap to speed). Laps decide the score; cruise pace is the underlying cause.
2. **Climb quality — second lever (qualitative, not time).** Bill spends *less* total time circling than the leader (287 vs 402 s), so he is not over-thermalling; but he banks ~35% less height per thermal (40.7 vs 63.1 m) with wider, slower circles (39.4 vs 33.2 m radius; 0.89/2.55 vs 1.03/3.64 m/s mean/best). Weak climbs make him land early on poor-lift days (e.g. R9 = 3 laps, R12 = 2) — the lap-count shortfall.
3. **Under-used entry speed — cheap third lever.** He crosses the start gate at 70.8 vs 94.5 km/h, leaving ~49 km/h of the 120 km/h cap unused (twice the leader's unused margin). Free opening-lap energy; entry altitude is already at the cap.
4. **Turns and lines — near a strength.** Turnpoint technique costs only ~2 s/lap (~10% of the deficit); lines are slightly wider (+15 m/lap) but this is the smallest lever.
5. **Landings are a strength** — clean 600 on all 14 distance rounds; no illegal flights, no zone penalties all week. He matched the leader lap-for-lap in R7 and R17 (scores 998/999) — the ceiling is there.
6. **Secondary, separable weakness:** the one-lap speed task (~110 vs ~150 km/h, ~24% slower).
7. Gap to the winner (2,887 pts) decomposes to ≈76% distance task (2,197), ≈24% one-lap speed sprint (690), ≈0% landings/penalties — reconciled to sum exactly to the total (the dropped worst round attributed in the split).
8. **Conditions:** wind shows no association with his relative standing; **thermal strength is the differentiator** — his within-group score and lap count rise with solar radiation (ρ≈+0.61 / +0.52), and his lowest relative results cluster on weak/late-day lift. Read: relatively worse when lift is scarce, competitive when it is strong. Suggestive only (n≈14). Reinforces the climb-quality lever (#2) for weak-lift days.
9. **Phase cost ranking (biggest lever first):** cruise speed → climb quality (height banked) → entry speed → turns. Confirms all four phase hypotheses.
10. **Progression across the week:** computed at build from per-round normalised score (skill, conditions-controlled) vs raw laps (skill + conditions), ordered by day.

## 8. Deliverable specification — single-file HTML report

**Format & portability**
- **One self-contained `.html` file** the user can email and open offline. All data and charts embedded (inline SVG generated from the embeddable per-round dataset, ~0.4 MB; no heavy CDN dependency required for display).

**Design**
- White background. **Deloitte-inspired palette** (green primary, cool greys, a teal/blue secondary) for an elegant, restrained look — **no Deloitte branding or logos**.
- Elegant typeface (serif display for headings, clean sans for body; graceful system fallback so it reads well offline).
- **No AI-tell styling:** no coloured accent bars/stripes on the top or left of boxes, no gradient hero blocks.
- **No emojis anywhere** — in the report, headings, nav, or any project output.
- **Every figure captioned.**
- Insights written **Point → Evidence → Explain**.
- **Grounding (mandatory):** every claim is backed by a plot/visualisation on the page **and/or** a link to the source data online (the rcmodelspot event/flight pages; and where relevant the weather source and the Sport-class regs). No unsupported assertions.
- **Useful links only:** recommended tech and drills link to a relevant online resource **where one genuinely helps** — do not force links onto items that lack a usefully relevant source.
- Avoid flagged lexical tics ("honest/genuinely/sit with/real", "that's not X it's Y", etc.).

**Navigation / UX**
- **Five top-level pages in one self-contained file:** **Home**, **Analysis** (Performance Analysis), **Recommendations**, **Innovations** (the art-of-the-possible / coaching-tech content), and **Methodology** (how the work was done). JavaScript toggles which page is visible; no reload. *Build order:* the first four pages are the initial product; **Methodology is added in a later phase** (§13), after the product is reviewed and accepted.
- **Top bar:** left shows the title text **"Bill's GPS Triangle Analysis 2026"** (plain text — no emoji, no logo). Right-aligned, always-visible links: **Home · Analysis · Recommendations · Innovations · Methodology**. On mobile the links collapse to a burger menu.
- **Home:** very concise — a short project summary and the three sections listed as linked headings (Performance Analysis, Recommendations, Innovations). No deep content.
- **Analysis page:** contains the **Overview / Rounds dropdown** — **Overview** (default) then **Round 1 · <date-time>** … **Round 17 · <date-time>**; selecting an item swaps the visible view. The dropdown behaves exactly as previously specified (per-view summary, anchor links, collapsible sections, expand/collapse-all) — just scoped to this page.
- **Per-view structure (Analysis Overview and each round; Recommendations/Innovations where dense):** opens with a short **summary** — a few sentences then ~5 bullets of key points/recommendations; each bullet is an **anchor link** to its section; each **section header links back to the top**.
- **Collapsible sections** on dense pages, with **"Expand all" / "Collapse all"** controls; the summary stays visible. Home stays minimal (no collapsing).

**Content by page**
- **Home:** one short project summary paragraph + the three linked section headings. Minimal.
- **Analysis — Overview (default view):** an **Overall Read** lead paragraph + a section index near the top, then **four Title-Case thematic sections** (insights top-down general→specific; each Title → Insight text → Visual + grounding → recommendation): **1. Headline Result** (number cards, Within-Group Rank, Gap Breakdown, Where The Ground Is Lost, Consistency: Floor vs Ceiling, Progression Across The Week, Landings callout); **2. Scoring, Laps & Speed** (Score → Laps → Cruise Speed → Field Position & Laps/Speed Scatter → Speed Gaps); **3. Start Energy** (Entry Speed → Entry Altitude → airframe/equipment note); **4. Conditions, Trajectory & Climbing** (Conditions Dependence with plain-English Spearman → Trajectory Trends (distance-from-course, log-y) → Thermal Strength → Climb Geometry → Climb Rate → Thermalling Turn Radius → the Round 12 ground-track as a worked example). Drops the standalone "Conditions Link". Details in SPEC RPT-022/023/024/025. Recommendations link inline to the Recommendations/Innovations pages.
- **Analysis — Per-round views:** open (under the summary) with a **Visual overview of performance** dashboard — vertical bullet plots (entry speed / entry altitude vs leader and the regs caps; avg speed vs leader), a score ladder (winner 1000 / Bill / field), a wind card, and number-cards (laps, rank, radiation). Then the **Energy Management** dual-panel, the **ground-track & course** overlay, cumulative-laps-vs-leader, the biggest-loss segment, and the round's **inline recommendation(s)**.
- **Recommendations page:** every recommendation gathered in one place, **organised into implementation themes** so they can be seen and planned together — drills, further analysis, resources, and rules-legal live signals (audio vario tuning, speech telemetry callouts, a navigator on the ground station). These are the **same** recommendations shown inline in Analysis (one canonical set, surfaced in both places via shared anchors); each **links back** to its supporting evidence on Analysis and out to relevant **Innovations**.
- **Innovations page:** the forward-looking coaching-tech roadmap — post-flight AI coach, navigator AR HUD, live AI cueing, data flywheel — with the rules-legality framing (navigator telemetry/AR plausibly legal at Contest-Director discretion; nothing may feed model control per §2.7; pilot-worn HUD safest as training-only; audio vario/speech telemetry explicitly permitted). Standalone, but **linkable from Analysis and Recommendations** so each point stays in context.
- **Methodology page (later phase):** a visual narrative of how this work was done between the user and the AI agents — for a general reader to "replay" the high-autonomy build. Opens with a short summary paragraph on the human+agent approach, and a collapsed-by-default **setup** panel (Claude Code; a CLAUDE.md/AGENTS.md carrying intent-capture heuristics; a laptop with Python). Work grouped into high-level **steps** (Specify, Research, Design, Build, Refinement, Review, Finish). Each step is **expandable**: a summary of what the user asked, expanding to the actual exchange — the user's **verbatim prompts** and a **summary of what the agent did** (research, data fetches, planning, and delegation to subagents). **Durations shown at each level**: agent working-time between instructions comes from harness metadata (exact); points where the user interjected to clarify are marked. Not a full OTEL trace — an accessible narrative. Source data captured in `docs/METHODOLOGY_LOG.md`.
- **Cross-linking:** Analysis ↔ Recommendations ↔ Innovations are cross-referenced via shared anchors, so the reader moves between evidence, action, and future ideas in context.

## 9. Methodology & fairness

- Same-air (within-group) leader as the per-round benchmark; overall winner referenced only where co-grouped.
- Skill vs conditions separated via within-group normalised score (conditions controlled) against raw laps (conditions + skill).
- Phase decomposition by bearing-rate + vario segmentation; turn vs thermal separated by duration/continuity.
- Weather associations reported as *suggestive* given n≈14 triangle rounds, never as significance claims.

## 10. Constraints & limitations

- Single event only (see §6); small n for weather/progression correlations.
- ERA5 weather is hourly; flights are sub-hourly — conditions are approximate.
- API exposes start point + direction + leg length, not explicit turnpoint coordinates; the triangle is drawn from the flown tracks or reconstructed from geometry.
- Turn-radius/line metrics are indicative (segmentation blends some thermalling with turns); low-lap rounds are noisy and down-weighted.
- Live/competition AR-HUD legality is organiser discretion (regs silent); framed as such.

## 11. Build approach

- **Workflow note (TDD exception):** this is a data-analysis + reporting deliverable, not application code, so classic red/green TDD does not fit. The agreed validation alternative is **data reconciliation** — computed laps/speeds/scores reconcile to the authoritative results, distances validate against the API's own distance fields, and weather maps to the correct flight windows. The build script is deterministic and re-runnable.
- **Orchestration:** research and heavy data work run in subagents to keep the build context clean; the orchestrator assembles the final HTML from the compact analysis outputs.
- **Pipeline:** fetch (scores/tracks/weather) → compute per-round metrics + phase decomposition + weather correlation → emit compact embeddable dataset → generate single-file HTML with inline SVG charts.
- **Build order (phased):** (1) build the four-page product (foundation → parallel content → consolidation); (2) build-review workflow; (3) user reviews and accepts the product; (4) build the **Methodology** page and review it; (5) once accepted, write the repo **README.md** (DOC-001) last.
- **Build-review includes a visual/UI pass:** alongside the output-quality and spec reviewers, a subagent drives **Playwright (CLI)** to render the file, screenshot the pages at desktop and mobile widths, and check visual correctness (layout, charts visible, nav/burger, collapsibles, no overflow) before the user needs to look. This visual-review step is itself part of the Methodology narrative.

## 12. Repo map

| Path | What it holds |
|---|---|
| `docs/PRD.md` | This document — intent, scope, deliverable spec |
| `docs/SPEC.json` | Feature + test backlog with `passes` state |
| `docs/ADR.md` | Architecture decision records (standing build constraints) |
| `docs/METHODOLOGY_LOG.md` | Source data for the Methodology page: verbatim prompts, agent actions, subagent durations/tokens (state capture) |
| `scripts/` | Fetch and analysis scripts (`fetch_data.py`, `fetch_replays.py`, `compute_metrics.py`, weather, phase decomposition) |
| `data/scores/` | Cached raw JSON: competition results tree, competitors |
| `data/tracks/` | Cached raw ~1 Hz GPS replay JSON per group (re-fetchable) |
| `analysis/` | Computed outputs: per-round metrics, field summary, weather, phase summary, trajectory PoC |
| `analysis/round_data/` | Compact downsampled per-round tracks for embedding (`round_NN.json` + `index.json`) |
| `analysis/charts/` | PoC chart PNGs |
| `reviews/` | Build-review reports (`yymmddThhmm-<domain>.md`), written at end of build phase |
| `report/gps-triangle-world-masters-oschatz-2026.html` | The single-file deliverable (RPT-017) |

## 13. Open questions / future

- If Bill provides links/GUIDs to his other rcmodelspot events, extend to multi-event trend analysis (same pipeline).
- Coaching-technology roadmap (post-flight AI coach → live cueing) is scoped as future work in the report's "art of the possible" section, not built here.
