# Methodology log (source data for the Methodology page)

State capture of how this project was built between the user (Tom) and Claude (Claude Code, model Opus 4.8) with delegated subagents. This is the raw material for the Methodology page (SPEC RPT-010), captured as the work happened to preserve verbatim prompts and exact durations before any context summarisation.

**Duration provenance (ADR-006):** agent working-times, token and tool counts are exact, from the harness's subagent metadata. Inter-message human think-time was not instrumented and is **not** invented — the user's interjections are marked positionally in the flow, not timed.

## Setup (for the page's collapsed setup panel)
- **Claude Code** (CLI agent) running on the user's laptop (macOS), Python available (managed with `uv`).
- A project **CLAUDE.md/AGENTS.md** carrying intent-capture heuristics: capture intent in a PRD before building, decompose into a spec, TDD for the build, a doc index, and a build + build-review workflow.
- Public GitHub repo `tmaisey/gps-triangle-analysis`; work committed and pushed per stage.
- Data source: the public rcmodelspot JSON API (anonymous); weather from the Open-Meteo ERA5 archive.
- High-autonomy pattern: the user gives intent and refinements; the orchestrator agent plans, delegates heavy work to subagents (research, analysis, build, review) to manage context, and reports back at decision points.

## Subagent working-time table (exact, from harness metadata)
| Step group | Subagent | Duration | Tokens | Tools |
|---|---|---|---|---|
| Research | Sport & rules briefing | 3m49s | 59.4k | 22 |
| Research | rcmodelspot data scoping | 9m00s | 74.8k | 31 |
| Analysis | Trajectory proof-of-concept | 10m44s | 91.1k | 33 |
| Analysis | Scores + event discovery | 17m01s | 98.7k | 38 |
| Analysis | Weather enrichment | 26m55s | 77.1k | 21 |
| Analysis | Per-round track extraction | 17m41s | 107.6k | 31 |
| Research | Rules: pilot/helper aids | 2m41s | 57.8k | 16 |
| Analysis | Phase decomposition | 16m56s | 127.4k | 32 |
| Build | Foundation harness + tests | 17m55s | 120.2k | 37 |
| Build | Home/Recommendations/Innovations | 19m28s | 84.6k | 21 |
| Build | Per-round views (17) | 22m34s | 108.1k | 20 |
| Build | Analysis Overview | 30m05s | 119.1k | 38 |

Cumulative subagent working-time ≈ 3h15m across 12 subagents; wall-clock was much shorter because research/analysis and the content builds ran in parallel batches.

---

## Step 1 — Specify & clarify
**User (verbatim, opening request):**
> My dad flies 'gps triangle', where you fly as many triangles in 30mins or so against competitors through a competition. It's a speed-endurance RC thing taking skill and ability to read conditions to maximise average speed/minimise distance per lap while staying aloft. He did this competition where they have the results. His name is Bill Maisey (William Maisey). I want you to research the event, the rules associated, look into Bill's performance across the event and derive some insights into his performance vs competitors. Use sub-agents to do this research first (the sport and the results) and propose some valuable thigns you could do with the insights. [link to rcmodelspot ranking] Clarify some basics first, but I'm busy so once the first steps are clear I want you to work away autonomously to do this, using subagents to manage your context as the orchestrator. I'm thinking looking for the times he did better or worse, if you can get trajectories vs the winners per flight there could be some things to do there. Research into art of poss.

**Agent:** launched two research subagents in parallel (sport & rules; rcmodelspot data scoping) and asked three bounded clarifying questions.
**User (clarifications, via picker):** purpose = coaching/improvement; deliverable = initial insights (inline TLDR + summary md) with options + pros/cons, then decide; scope = all of Bill's events.

## Step 2 — Research & analysis (delegated)
**Agent:** ran a sequence of subagents to build the evidence base (see table). Findings: GPS-Triangle Sport class rules and scoring; the rcmodelspot open API exposing per-flight scores and full ~1 Hz GPS tracks for every pilot; a trajectory PoC; the full scores analysis + event-discovery (multi-event blocked — only the Oschatz event retrievable); weather enrichment (thermal strength, not wind, tracks his relative results); per-round track extraction (downsampled, embeddable); a rules check on pilot/helper aids; and a phase decomposition (cruise speed the #1 lever, then climb quality, then entry speed; turns/landings near strengths).

## Step 3 — Deliverable spec & iterative UX refinement
**User (verbatim):**
> OK, my initial thought is we could make a html report on his performance at the event. I want this to be a single file if possible so I can just send it. This should give a performance report TLDR up-front, where he was strong, where lost ground vs the top pilots. Then if feasible, it would be great to generate a view per round to show insights on his performance vs the best and how to train/improve. This wouldn't need to store the full 250mb, just Bill's flight and the winners' per round perhaps, likely you could sub-sample the data and still show the insights, perhaps just showing sections of the flight where the biggest gains/losses were made. Note his performance would have improved through the week from practice too, not just conditions and competitor effects. You don't have to just show the gps tracks for the insights, it could be other visualisations that show the insights and recommendations per flight. Perhaps thermalling performance vs others (side-on view of climb rates, turn radiuses, or non-geo vis if relevant). Brainstorm concepts of insights and how to show it. [plus: white background, Deloitte colour scheme without branding, no AI-looking accent bars, elegant typeface, caption images, Point-Evidence-Explain, avoid AI lexical tics] Can you get weather info per flight to see if he performed better in some conditions than others?

**User (verbatim):**
> UX for switching per round I suggest a drop-down with 'Overview', then Round 1 <data-time> listed, switching the whole page view. Home defaults to overview. Overview includes the most valuable insights, including cross-round and general insights. Are there particular points he's losing ground or particularly strong? Starts, straights, turns, climbs/thermals, other? Conditions. For the insights, recommend drills, further analysis, resources, perhaps even kit/live-signals (vario, audio/vis warnings. What about HUD etc?

**User (verbatim):**
> HUD could be Meta glasses or something if not forbidden though. They have a spotter pilot assisting them while flying, so perhaps HUD info could be helpful if allowed. If not in competition it could be in training. What about training data HUD, extended to AI coach etc

**Agent:** brainstormed insight concepts and a tiered coaching-tech space; confirmed weather feasibility (Open-Meteo); dispatched weather, per-round track, phase-decomposition, and rules-aids subagents; folded results into the emerging plan.

## Step 4 — Intent capture (docs) & scaffolding
**User (verbatim):** ok can you write the plan down in docs/PRD.md so intent is captured ahead of the build
**User (verbatim):** just scaffold what we have so far, we'll refine the final output before building
**User (verbatim):** yeah ignore the skillz project, but the other content on docs and workflow should apply re intent capture, tdd for build etc
**Agent:** wrote `docs/PRD.md` and `docs/SPEC.json` (TDD backlog); archived the unrelated inherited manual and repointed `AGENTS.md` at this project.

**User (verbatim):**
> Add a new instruction to the AGENTS.md for this project. At the end of build phase, I want subagents to then review the build. [one output-quality reviewer; spec reviewers batched across a sensible number of agents; each writes reviews/yymmddThhmm-<domain>.md and summarises fixes; orchestrator proposes improvements before another subagent fixes] Use sub-agent(s) to build the outputs for the final product. You decide how to do this against the spec-items breakdown, but they should build in parallel where possible.

**User (verbatim):** I expect there will be a decent amount of content per page in the output. Have a short summary at the start with the key points and recommendations (a few sentences then ~5 bullets). Those can have hyperlinks to the sections on each below, with the section-headers also linking back to the top. Have the sections themselves collapseable... Have expand all and collapse all buttons at the top of the sub-sections
**User (verbatim):** also ensure all claims are grounded in either a plot/visualisation and/or a reference to the source data online. Include links to the recommended tech or drills if possible online, but only where appropriate, don't force links to things that aren't usefully relevant
**User (verbatim):** For the recommendations and art of the possible features, have those as separate tabs. [Home lists 3 sections: Performance Analysis, Recommendations, Innovations; top nav bar, title left, links right, burger on mobile; no emojis anywhere; Home concise]
**User (verbatim):** is it clear that the overview/rounds dropdown still is as before though, just in the Analysis page only. And I want the Recommendations to also be inline with the Analysis, but then also shown together in a single page that organises them into themes... Innovations is just a separate page, but you could link to those points from Analysis and Recommendations too...
**Agent:** captured every refinement into PRD §8 and the spec (RPT-002/005/006/007/008/009, DSN-001); added ADRs.

## Step 5 — Git & remote
**User (verbatim):** I've thought of another page... [see Step 7] // and earlier: I want to start managing this with git too now. create public repo on my tmaisey gh called gps-triangle-analysis and use the workflow in the AGENTS.md on gitops. commits, push etc. [and: README styled after the bloaty-mcbloatface project, built last]
**Agent:** initialised git, wrote `.gitignore` (excluding the 64 MB raw replays and the archived manual), created and pushed the public repo, and captured the README as DOC-001.

## Step 6 — Build
**User (verbatim):** go: do the full build unless you hit any blockers that you need to check with me. Remember to capture the ADRs too as appropriate, though this is a simple build.
**Agent:** wrote `docs/ADR.md`; ran Stage 1 (foundation + test suite), Stage 2 (three parallel content agents: Overview; 17 per-round views; Home/Recommendations/Innovations), then Stage 3 consolidation. Committed and pushed per stage.

## Step 7 — Methodology page & review refinement (this step)
**User (verbatim):** [request to add a Methodology page replaying how the work was done between user and agents — grouped steps, expandable summary→verbatim exchange, durations at each level, collapsed setup panel, high-autonomy summary; built after the main product is accepted; plus a Playwright CLI UI-review subagent during review; the Methodology page gets its own review; then finally the README.]
**Agent:** captured into PRD/SPEC/ADR and this log; the Methodology page (RPT-010) is scheduled after the four-page product is accepted.

## Step 8 — Refinement (user review feedback)
The user reviewed the built product and gave targeted fixes, captured as spec items and applied via the same red/green workflow: dynamic Expand/Collapse labels (RPT-014); GPS ground-track fixes — correct reference-triangle geometry, bolder and drawn on top, full-resolution traces, a North arrow, and a per-plot wind vector with a knots label (RPT-011, RPT-012); run-relative time on the speed-run overlay (RPT-013); "Legality gate" to "Legality Consideration" (RPT-015); hyperlinked regs references (RPT-016); retitle to "GPS Triangle World Masters, Oschatz 2026" and repo/file rename (RPT-017).

A second refinement round reworked the Analysis Overview and deepened the trajectory story: the Overview was **restructured from the single Performance-Summary umbrella into four thematic sections** (Headline Result; Scoring, Laps & Speed; Start Energy; Conditions, Trajectory & Climbing) under an "Overall Read" lead paragraph (RPT-022); two new pooled trajectory charts were added — **distance-from-course** log-density (RPT-023) and **thermalling turn-radius** density (RPT-024) — plus the Round 12 ground track as a worked example; an **airframe/equipment note** framing the gap as technique-not-kit (RPT-025); the per-plot **wind clockface** placement fix; **Title Case** section titles throughout; and **expand-by-default** collapsibles. The course geometry was pinned as a decision (ADR-008: right-isosceles from the `.rct` header). The formal **Review** (output-quality + Playwright visual/UI + batched spec reviewers) is the next phase.

## Step 9 — Review, Methodology, Finish (pending)
Formal build-review (output-quality + Playwright visual/UI + batched spec reviewers) -> consolidate -> propose fixes to the user -> product accepted. Then build the Methodology page (this narrative) and review it. Finally write the repo README.md.

**Phase taxonomy for the page:** Specify -> Research -> Design -> Build -> Refinement -> Review -> Finish.
