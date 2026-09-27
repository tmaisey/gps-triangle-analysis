# gps-triangle — project operating manual

Analysis and coaching-report project for RC "GPS Triangle" racing, focused on pilot **Bill Maisey**. This file governs how work is done in this repo.

> An earlier, unrelated "mad-skillz" manual previously occupied this file. It does **not** apply to this project and is archived at `AGENTS.mad-skillz.bak.md`. Ignore it.

**Resume here:** read `docs/PRD.md` (intent + deliverable spec) and `docs/SPEC.json` (feature + test backlog — scan `passes`). Those two are the live state.

## Workflow (intent-first, test-driven)
1. **Intent capture** — requirements live in `docs/PRD.md`. When intent changes, refine the PRD **first**, then the spec, then code.
2. **Spec** — decompose intent into `docs/SPEC.json` features, each with a test and `passes: false`.
3. **Red** — write the failing test first. For data/analysis, a *reconciliation* test (computed values match the authoritative rcmodelspot results and the API's own distance fields). For the report, HTML structure / self-containment / navigation / design tests. Prove it fails.
4. **Green** — implement until the test passes; run the suite.
5. **Flip & commit** — set `passes: true`; stage test + implementation + spec together. (Initialise git before the first commit.)

TDD exception (PRD §11): data/analysis is validated by reconciliation rather than classic unit tests; the build script is deterministic and re-runnable.

## Build methodology (final report)
The deliverable is **one self-contained HTML file** produced by a deterministic Python build harness that reads `analysis/` outputs and emits inline-SVG charts with the per-round data embedded. Build with subagents, parallel where the dependency graph allows:
- **Stage 1 — Foundation (single agent, runs first):** build harness + module interfaces, design system (palette/typography), HTML shell, dropdown navigation, and the shared inline-SVG chart library; plus the failing test suite (red). Renders a skeleton on real data so downstream agents have stable interfaces.
- **Stage 2 — Content (parallel agents):** Overview; per-round views (all 17); recommendations layer + the "art of the possible" tech section. Each builds against the foundation's interfaces.
- **Stage 3 — Consolidation (single agent):** integrate the modules, run the generator, drive the test suite to green, and align consistency across the whole file (typography, spacing, captions, Point-Evidence-Explain structure, lexical-tic sweep, self-containment).

## Build-review workflow (mandatory — at the end of the build phase)
Once the build reaches green, and **before it is considered done**, subagents review it in parallel:
- **One output-quality reviewer** — reviews the built output for **syntax and output quality** (HTML/CSS/JS correctness, rendering, accessibility, self-containment, adherence to the design constraints) and recommends fixes.
- **Spec reviewers** — review **every** `SPEC.json` item. Not one agent per item: **batch** the items across a sensible number of agents (e.g. 12 specs → 4 agents × 3 specs each). Each verifies its assigned specs against the build and their tests.
- **Each reviewer writes a report** in `reviews/` named **`yymmddThhmm-<review-domain>.md`**, and returns a **concise** summary of recommended fixes to the orchestrator.
- **The orchestrator consolidates** the recommendations and **proposes the improvements to the user for approval BEFORE** any fixing begins.
- **On approval**, a separate fix subagent applies the agreed changes. Re-review if the changes are substantial.

## Doc index / repo map
| Path | What it holds | When to use / update |
|---|---|---|
| `docs/PRD.md` | Intent, scope, deliverable spec, findings, limitations | Read first; update when intent or scope changes |
| `docs/SPEC.json` | Feature + test backlog with `passes` state | Check before building; flip status through red → green |
| `docs/ADR.md` | Architecture decision records (standing build constraints) | Read before an architectural choice; add an ADR when one is made |
| `reviews/` | Build-review reports (`yymmddThhmm-<domain>.md`) | Written at end of build phase; read before proposing fixes |
| `scripts/` | Fetch + analysis scripts (and, to come, the build harness) | — |
| `data/scores/`, `data/tracks/` | Cached raw rcmodelspot API JSON (re-fetchable) | — |
| `analysis/`, `analysis/round_data/` | Computed metrics + the compact embeddable per-round dataset | Inputs to the report build |
| `report/` | The single-file HTML deliverable | Build output |
| `AGENTS.mad-skillz.bak.md` | Archived unrelated manual — does not apply | Ignore |

*Note: `CLAUDE.md` still imports the archived manual via `@AGENTS.md`; since `AGENTS.md` is now this project's manual, it loads the right content. Say the word to simplify `CLAUDE.md` if desired.*
