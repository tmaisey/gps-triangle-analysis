"""Analysis - Overview view (Stage 2 content).

The Overview is the default view of the Analysis page. It opens with a short
verdict summary, anchor-linked bullets and a one-paragraph Overall Read, then
walks the coaching argument through four thematic, collapsible sections. Each
insight follows one pattern - a Title-Case title, the reading in plain prose,
then its visual (captioned, with grounding/source links) and, where it earns
one, a cross-link to the matching recommendation. Insights run top-down within
each section, general to specific. Every explanatory line sits BEFORE the plot
it describes, never after it.

Anchor / id scheme (section ids; summary bullets link to these):
    ov-top          summary block / back-to-top target
    ov-headline     headline result: rank, gap, phase levers, consistency,
                    progression, landings
    ov-scoring      scoring, laps & speed (grouped bars + field scatter +
                    speed gaps)
    ov-start-energy start-gate entry speed / altitude + airframe note
    ov-conditions   conditions dependence, trajectory, weather, climbing, and a
                    Round 12 worked example
"""

from __future__ import annotations

import statistics

from .. import charts, components as C
from ..data import (
    BILL_GUID,
    load_round,
    load_standings,
    pooled_distance_from_course,
    pooled_turn_radius,
    spearman_rho,
    top_airframe_families,
)
from ..links import EVENT_URL, RULES_INDEX_URL, WEATHER_URL

# --- Source links (link bank; verified constants live in build.links) -------
_EVENT_URL = EVENT_URL
_RULES_URL = RULES_INDEX_URL
_WEATHER_URL = WEATHER_URL

# Speed-sprint rounds (1-indexed) score no landing and are analysed apart.
_SPEED_ROUNDS = {4, 10, 16}

_SECTIONS = [
    ("ov-headline", "Headline Result"),
    ("ov-scoring", "Scoring, Laps & Speed"),
    ("ov-start-energy", "Start Energy"),
    ("ov-conditions", "Conditions, Trajectory & Climbing"),
]

_SUMMARY_BULLETS = [
    ("ov-headline", "22nd of 38 (12,562 pts); the gap is almost all distance-task"),
    ("ov-scoring", "Cruise speed between thermals is the dominant lever"),
    ("ov-start-energy", "Start is already competitive; the winner flies Bill's airframe"),
    ("ov-conditions", "Stronger in strong lift; wider circles and more time off the course line"),
]


# --- Small HTML helpers -----------------------------------------------------
def _link(url: str, text: str) -> str:
    """Return an external source link opening in a new tab."""
    return (
        f'<a href="{C.esc(url)}" target="_blank" rel="noopener">'
        f"{C.esc(text)}</a>"
    )


def _xref(page: str, anchor: str, text: str) -> str:
    """Return a cross-page reference link (handler wired by the consolidator)."""
    return (
        f'<a class="xref" data-page="{C.esc(page)}" '
        f'data-anchor="{C.esc(anchor)}">{C.esc(text)}</a>'
    )


def _explain(text: str) -> str:
    """Render the recommendation cue that follows an insight's visual.

    The bold ``What to do.`` label is an action cue (not a Point-Evidence-Explain
    structural label); it carries the cross-links to the matching recommendation.
    """
    return f'<p class="pee-explain"><strong>What to do.</strong> {text}</p>'


def _lead(title: str, text: str) -> str:
    """Render an insight lead-in: a short Title-Case title, then the reading.

    The title and its explanatory sentence(s) sit ABOVE the figure they
    introduce, so the reader meets the reading before the plot rather than after
    it. ``text`` may contain trusted inline HTML (cross-page ``xref`` links and
    external source links).

    Args:
        title: a short Title-Case label; a trailing full stop is added.
        text: the explanatory sentence(s); inline HTML allowed.

    Returns:
        str: a ``<p class="pee-point">`` lead-in fragment.
    """
    return f'<p class="pee-point"><strong>{C.esc(title)}.</strong> {text}</p>'


_ROUNDS = list(range(1, 18))


def _event_winner_results() -> list[dict]:
    """Return event winner Florian Griese's per-round result rows, round-aligned.

    The event winner is the standings entry with the highest total score
    (15,449 - Florian Griese, matching the headline). ``results.json`` lists
    each pilot's rounds in round order, so index ``r-1`` is round ``r``. Rounds
    the winner scored zero (a bombout) carry no ``laps``/``speed`` keys.

    Returns:
        list[dict]: 17 result dicts (one per round), padded if any are missing.
    """
    winner = max(load_standings(), key=lambda s: s.get("totalScore", 0))
    res = list(winner.get("results", []))
    return res + [{}] * (len(_ROUNDS) - len(res))


def _metric_by_round(ctx: dict) -> dict:
    """Index the per-round metrics by ``(round, role)`` for round-aligned lookup.

    Args:
        ctx: shared build context; ``ctx['metrics']`` is one row per pilot per
            round with ``role`` in {'BILL', 'leader'}.

    Returns:
        dict: ``{(round:int, role:str): row}``.
    """
    return {(int(m["round"]), m["role"]): m for m in ctx["metrics"]}


def _series_fns(ctx: dict):
    """Return round-aligned series accessors for Bill / leader / event winner.

    Args:
        ctx: shared build context.

    Returns:
        tuple: ``(bill, leader, winner, drop_speed, m)`` where ``bill``/
        ``leader``/``winner`` map a metric field name to a 17-long round-aligned
        list, ``drop_speed`` blanks the three speed-sprint rounds, and ``m`` is
        the ``(round, role)`` metric index.
    """
    m = _metric_by_round(ctx)
    win = _event_winner_results()

    def bill(field):
        return [m.get((r, "BILL"), {}).get(field) for r in _ROUNDS]

    def leader(field):
        return [m.get((r, "leader"), {}).get(field) for r in _ROUNDS]

    def winner(field, scale=1.0):
        out = []
        for r in _ROUNDS:
            v = win[r - 1].get(field)
            out.append(v * scale if isinstance(v, (int, float)) else None)
        return out

    def drop_speed(vals):
        return [None if r in _SPEED_ROUNDS else v for r, v in zip(_ROUNDS, vals)]

    return bill, leader, winner, drop_speed, m


def _field_scatter() -> tuple[str, int]:
    """Build the grinder-vs-sprinter field scatter from the standings.

    Returns:
        tuple[str, int]: the SVG string and Bill's index within the point list.
    """
    points: list[tuple[float, float]] = []
    labels: list[str] = []
    bill_idx: int | None = None
    for s in load_standings():
        res = s.get("results", [])
        laps = [r.get("laps") for i, r in enumerate(res, 1)
                if i not in _SPEED_ROUNDS and r.get("laps") is not None]
        spd = [r.get("speed") * 3.6 for i, r in enumerate(res, 1)
               if i not in _SPEED_ROUNDS and r.get("speed") is not None]
        if not laps or not spd:
            continue
        if s["userGuid"] == BILL_GUID:
            bill_idx = len(points)
        points.append((sum(spd) / len(spd), sum(laps) / len(laps)))
        labels.append("Bill" if s["userGuid"] == BILL_GUID else "")
    svg = charts.scatter_highlight(
        points,
        highlight_index=bill_idx,
        xlabel="Average task speed (km/h)",
        ylabel="Average laps",
        title="Grinder vs sprinter - the distance-round field",
        labels=labels,
    )
    return svg, (bill_idx if bill_idx is not None else -1)


# --- Section builders -------------------------------------------------------
def _headline(ctx: dict) -> str:
    """Headline Result: result, rank, gap, phase levers, consistency, progression.

    The most general read first (the placing and where the points went), then
    the phase-lever ranking that names the dominant training target, then
    consistency and week-long progression, closing on the clean-landings
    strength.
    """
    _, _, _, _, m = _series_fns(ctx)
    official = ctx["official"]
    rank = official["rank"]
    total = official["total_score"]
    gap = 15449 - total  # winner Florian Griese 15,449
    dec = ctx["phase"]["per_lap_time_deficit_decomposition"]

    # (1) The result - number cards.
    result_lead = _lead(
        "The Result",
        "Bill finished <strong>22nd of 38</strong> on 12,562 points, 2,887 "
        "behind winner Florian Griese. Almost the entire gap is the distance "
        "task; his landings and rule compliance were faultless all week, so the "
        "training target is lap count in the distance rounds.")
    tiles = C.kpi_row([
        C.stat_tile(f"{rank} / 38", "Final placing", "World Masters, Sport class"),
        C.stat_tile(f"{total:,}", "Total points", "best 16 of 17 rounds"),
        C.stat_tile(f"{gap:,}", "Points behind winner", "Florian Griese, 15,449"),
        C.stat_tile("600", "Landing points", "clean on all 14 distance rounds"),
    ])

    # (2) Within-group rank strip.
    ranks = charts.rank_strip(
        [m.get((r, "BILL"), {}).get("rank") for r in _ROUNDS],
        group_sizes=[m.get((r, "BILL"), {}).get("group_size") for r in _ROUNDS],
        labels=_ROUNDS,
        title="Bill's within-group finishing rank by round",
    )
    ranks_cap = (
        "Bill's finishing position within his own group each round (1 = group "
        "winner; darker green = higher)."
    )
    ranks_fig = _lead(
        "Within-Group Rank",
        "Judged fairly against his own same-air group each round, Bill lands "
        "mid-pack; his best relative rounds line up with the strongest lift."
    ) + C.figure(ranks, ranks_cap, fig_id="ov-fig-sum-rank",
                 source=(_EVENT_URL, "event results (rcmodelspot)"))

    # (3) Gap decomposition by task type, worst round dropped per pilot
    # (reconciles to 2,887). Landings/penalties contribute nothing.
    waterfall = charts.waterfall(
        [("Distance task", 2197.0),
         ("One-lap speed", 690.0),
         ("Landings / penalties", 0.0)],
        title="Gap to the winner, by task type",
        xlabel="Points behind the winner",
    )
    gap_cap = (
        "Gap to the winner by task type (points behind), each pilot's worst "
        "round dropped."
    )
    gap_fig = _lead(
        "Gap Breakdown",
        "Where the 2,887-point gap comes from, each pilot's worst round dropped: "
        "about 76% is the distance task and 24% the one-lap speed sprint, while "
        "landings and penalties add nothing."
    ) + C.figure(waterfall, gap_cap, fig_id="ov-fig-gap")

    # (4) Where the ground is lost - the clean-lap time deficit.
    deficit_wf = charts.waterfall(
        [("Cruise (straight glide)", dec["straight_deficit_s"]),
         ("Turns & lines", dec["turn_deficit_s"])],
        title="Clean-lap time deficit vs the same-air leader",
        xlabel="Seconds slower per clean lap",
    )
    deficit_cap = (
        "Clean-lap time deficit vs the same-air leader, split into straight glide "
        "and turns/lines (seconds slower per lap)."
    )
    # Anchor id ``ov-levers`` is preserved (cross-linked from the
    # Recommendations page) now that the phase-lever ranking lives here.
    ground_fig = '<div id="ov-levers">' + _lead(
        "Where the Ground Is Lost",
        f"Bill's clean lap is about {dec['mean_lap_deficit_s']:.0f} s slower than "
        f"his same-air leader's. {dec['straight_share_pct']:.0f}% of that is the "
        f"straight glide between thermals; only {dec['turn_share_pct']:.0f}% is "
        "turns and lines. In cost order the levers are cruise speed, then climb "
        "quality, then entry speed, then turns - cruise pace dominates."
    ) + C.figure(deficit_wf, deficit_cap, fig_id="ov-fig-deficit") + "</div>"
    ground_rec = _explain(
        "Train fastest-first: "
        f"{_xref('recommendations', 'rec-cruise', 'cruise pace between thermals')} "
        "(the ~2.7-lap pace effect), then "
        f"{_xref('recommendations', 'rec-climb', 'climb quality')} for weak-lift "
        "days, then a cheap win by "
        f"{_xref('recommendations', 'rec-entry', 'using the entry-speed cap')}; "
        f"{_xref('recommendations', 'rec-turns', 'turns and lines')} are the "
        "smallest lever. He matched the leader lap-for-lap in Rounds 7 and 17, "
        "so the ceiling is there. The 120 km/h entry cap and scoring are set in "
        f"the {_link(_RULES_URL, 'Sport-class regulations')}; field data from "
        f"the {_link(_EVENT_URL, 'event results')}."
    )

    # (5) Consistency: floor vs ceiling.
    dist = [r for r in ctx["rounds_csv"] if r.get("task_type") == "distance"]
    scores = [r.get("score") for r in dist]
    laps = [r.get("laps") for r in dist]
    laps_mean = statistics.mean(laps)
    laps_med = statistics.median(laps)
    laps_sd = statistics.pstdev(laps)
    score_mean = statistics.mean(scores)
    score_med = statistics.median(scores)
    score_sd = statistics.pstdev(scores)

    cons_tiles = C.kpi_row([
        C.stat_tile(f"{laps_mean:.1f}", "Laps per distance round",
                    f"median {laps_med:.0f}, sd {laps_sd:.1f}"),
        C.stat_tile(f"{score_mean:.0f}", "Mean distance-round score",
                    f"median {score_med:.0f}, sd {score_sd:.0f}"),
        C.stat_tile("2", "Bombout rounds", "R9 = 3 laps, R12 = 2 laps"),
        C.stat_tile("0", "Illegal flights / zone penalties", "clean all week"),
    ])
    strip = charts.strip_plot(
        [("All 14 rounds", scores),
         ("Bombout rounds", [581, 418])],
        title="Distance-round scores, with the two low rounds marked",
        xlabel="Round score (normalised to 1000)",
    )
    strip_cap = (
        "Distance-round scores (normalised to 1000), with the two low rounds "
        "marked on a lower row."
    )
    # Anchor id ``ov-consistency`` is preserved (cross-linked from the
    # Recommendations page).
    cons_fig = '<div id="ov-consistency">' + _lead(
        "Consistency: Floor vs Ceiling",
        "The score is dragged down by a few weak-lift rounds, not by the good "
        "ones falling short. The two bombouts (R12 = 418, dropped; R9 = 581) sit "
        f"far below the median of {score_med:.0f}."
    ) + cons_tiles + C.figure(strip, strip_cap, fig_id="ov-fig-consistency",
                              source=(_EVENT_URL, "event results (rcmodelspot)")) + "</div>"

    r17 = load_round(17)
    ceiling = charts.cumulative_laps(
        r17["bill"]["lap_offsets_s"],
        r17["leader"]["lap_offsets_s"],
        working_time_s=r17["task"]["working_time_min"] * 60,
        title="Round 17 cumulative laps - Bill vs the same-air leader",
    )
    ceiling_cap = "Round 17 cumulative laps, Bill vs the same-air leader."
    ceiling_fig = _lead(
        "The Ceiling Holds",
        f"Round 17: Bill (green) tracks the same-air leader "
        f"{C.esc(r17['leader']['name'])} (teal) lap-for-lap to a near-perfect "
        "999. When lift is good the top-end pace is already there."
    ) + C.figure(ceiling, ceiling_cap, fig_id="ov-fig-ceiling")
    cons_rec = _explain(
        "A bombout costs more than a strong round gains, so the fastest ranking "
        "win is <strong>raising the floor</strong> - staying aloft through weak, "
        "scratchy lift - rather than chasing the ceiling. This is the "
        f"{_xref('recommendations', 'rec-climb', 'weak-lift climb work')} again, "
        "seen from the results side. Round scores: "
        f"{_link(_EVENT_URL, 'event results (rcmodelspot)')}."
    )

    # (6) Progression across the week.
    wdist = [r for r in ctx["weather"] if r.get("task_type") == "distance"]
    wdist.sort(key=lambda r: str(r.get("start_datetime_local")))
    prog = charts.progression(
        [str(r.get("round")) for r in wdist],
        [r.get("normalised_score") for r in wdist],
        [r.get("laps") for r in wdist],
        title="Across the week: normalised score vs raw laps",
    )
    prog_cap = (
        "Distance rounds in time order: within-group normalised score (solid) "
        "vs raw laps (dashed)."
    )
    prog_fig = _lead(
        "Progression Across the Week",
        "Splitting conditions from skill, there is no clear week-long practice "
        "trend. Both series swing round to round with the air; his two strongest "
        "normalised results (Round 7 on 5 August and Round 17 on 8 August) are a "
        "mid-week and a last-day flight, not the ends of a rising line."
    ) + C.figure(prog, prog_cap, fig_id="ov-fig-progression",
                 source=(_EVENT_URL, "event results (rcmodelspot)"))
    prog_rec = _explain(
        "Round-to-round conditions dominate the record far more than any drift in "
        "form, so read single rounds cautiously and judge progress on the "
        "conditions-controlled score, not on laps. With n &asymp; 14 the trend "
        "signal is weak either way. Per-round scores: "
        f"{_link(_EVENT_URL, 'event results (rcmodelspot)')}."
    )

    # (7) Landings strength - text-only callout, grounded on the event results
    # (it is the one insight here with no figure of its own).
    landings = _lead(
        "Landings: A Clean Sweep",
        "Bill scored the full 600 landing points on every one of the 14 distance "
        "rounds and drew no zone or airspace penalties all week - the "
        "clean-execution baseline the lap-count work builds on. Per-round "
        f"landing scores and penalty flags: {_link(_EVENT_URL, 'event results')}."
    )

    return (
        result_lead + tiles
        + ranks_fig
        + gap_fig
        + ground_fig + ground_rec
        + cons_fig + ceiling_fig + cons_rec
        + prog_fig + prog_rec
        + landings
    )


def _scoring(ctx: dict) -> str:
    """Scoring, Laps & Speed: the outcome, its drivers, and the pace gap.

    Score first (the outcome), then the laps and cruise pace that decide it, the
    field context, and the head-to-head speed numbers.
    """
    bill, leader, winner, drop_speed, _ = _series_fns(ctx)
    straight = ctx["phase"]["aggregate_phase_metrics"]["straight"]
    start = ctx["phase"]["aggregate_phase_metrics"]["start"]

    score = charts.grouped_bar_rounds(
        _ROUNDS,
        [("Round winner", leader("score"), "leader"),
         ("Event winner", winner("score"), "field"),
         ("Bill", bill("score"), "bill")],
        title="Round score by round (normalised to 1000)",
        ylabel="Score",
    )
    score_cap = (
        "Normalised round score across all 17 rounds; 1000 = the round winner "
        "within each group."
    )
    laps = charts.grouped_bar_rounds(
        _ROUNDS,
        [("Round winner", drop_speed(leader("laps")), "leader"),
         ("Event winner", drop_speed(winner("laps")), "field"),
         ("Bill", drop_speed(bill("laps")), "bill")],
        title="Laps completed by distance round",
        ylabel="Laps",
    )
    laps_cap = (
        "Laps in the 14 distance rounds; the three speed sprints (one lap each) "
        "are omitted."
    )
    speed = charts.grouped_bar_rounds(
        _ROUNDS,
        [("Round winner", drop_speed(leader("avg_speed_kmh")), "leader"),
         ("Event winner", drop_speed(winner("speed", 3.6)), "field"),
         ("Bill", drop_speed(bill("avg_speed_kmh")), "bill")],
        title="Average task speed by distance round",
        ylabel="km/h",
    )
    speed_cap = (
        "Average task speed over the 14 distance rounds (km/h); speed sprints "
        "omitted."
    )

    scatter_svg, _ = _field_scatter()
    scatter_cap = (
        "Average task speed vs average laps over the 14 distance rounds; Bill "
        "highlighted."
    )

    speeds = charts.paired_bars(
        ["Clean-lap cruise", "Start-gate entry"],
        [straight["bill_cruise_kmh"], start["bill_entry_speed_kmh"]],
        [straight["leader_cruise_kmh"], start["leader_entry_speed_kmh"]],
        title="Speeds: Bill vs same-air leader",
        ylabel="km/h",
    )
    speeds_cap = (
        "Clean-lap cruise and start-gate entry speed, Bill vs the same-air "
        "leader (km/h)."
    )

    scoring_rec = _explain(
        "Laps decide the score and pace drives laps, so the dominant training "
        "lever is "
        f"{_xref('recommendations', 'rec-cruise', 'cruise pace between thermals')}, "
        "with "
        f"{_xref('recommendations', 'rec-climb', 'climb quality')} closing the "
        "weak-lift days. Round winner is Bill's same-air group leader (fair, "
        "same-conditions); the event winner flew a different group, so his "
        "absolute laps and speed reflect his own air. Per-round scores and laps: "
        f"{_link(_EVENT_URL, 'event results (rcmodelspot)')}."
    )

    return (
        _lead(
            "Score per Round",
            "Every round's normalised score - his same-air round winner (blue), "
            "event winner Florian Griese (grey) and Bill (green). Bill trails the "
            "round-winning pace in most distance rounds, and Griese is not always "
            "top of his own group either.")
        + C.figure(score, score_cap, fig_id="ov-fig-sum-score",
                   source=(_EVENT_URL, "event results (rcmodelspot)"))
        + _lead(
            "Laps per Round",
            "Laps decide the distance score, and Bill's bars sit below the round "
            "winner almost everywhere - the gap widening on weak-lift days. The "
            "winner's blank at Round 9 is his own bombout.")
        + C.figure(laps, laps_cap, fig_id="ov-fig-sum-laps",
                   source=(_EVENT_URL, "event results (rcmodelspot)"))
        + _lead(
            "Cruise Speed",
            "Pace drives laps, and Bill's average task speed runs consistently "
            "below the round winner's - the dominant lever behind the laps gap.")
        + C.figure(speed, speed_cap, fig_id="ov-fig-sum-speed",
                   source=(_EVENT_URL, "event results (rcmodelspot)"))
        + _lead(
            "Field Position & Laps/Speed Scatter",
            "Every pilot's average task speed against average laps over the 14 "
            "distance rounds; Bill (green) sits low-left - fewer laps because the "
            "average pace is slower. Laps decide the score, and pace drives laps.")
        + C.figure(scatter_svg, scatter_cap, fig_id="ov-fig-field",
                   source=(_EVENT_URL, "event results (rcmodelspot)"))
        + _lead(
            "Speed Gaps",
            f"Clean-lap cruise {straight['bill_cruise_kmh']:.1f} vs "
            f"{straight['leader_cruise_kmh']:.1f} km/h "
            f"(~{straight['cruise_gap_pct']:.0f}% slower). At the start gate Bill "
            f"crosses at {start['bill_entry_speed_kmh']:.0f} vs "
            f"{start['leader_entry_speed_kmh']:.0f} km/h, leaving "
            f"~{start['bill_margin_to_cap_kmh']:.0f} km/h of the 120 km/h cap "
            "unused - free opening-lap energy.")
        + C.figure(speeds, speeds_cap, fig_id="ov-fig-speeds")
        + scoring_rec
    )


#: Maker names for the airframe families, so the note reads as prose rather
#: than as raw CSV values. Keys are the ``airframe_family`` column.
_AIRFRAME_MAKERS = {
    "Pike Paradigm (Samba)": "the Pike Paradigm (Samba Model)",
    "Phantom": "the ChocoFly Phantom",
    "SkyTouch": "the SolarWings SkyTouch",
    "Apollo": "the ChocoFly Apollo",
}


def _airframe_mix_sentence(top_n: int = 12) -> str:
    """Return a sentence naming the airframe families the leading pilots fly.

    Driven from ``analysis/pilot_equipment.csv`` (via
    :func:`data.top_airframe_families`) so the named mix and its counts stay
    tied to the data. Model names are self-entered by pilots, so the family
    grouping is what is quoted, not the exact model strings.

    Args:
        top_n: how many finishers, by final standing, the mix is counted over.

    Returns:
        str: one sentence, ending in a full stop.
    """
    fams = top_airframe_families(top_n)
    parts = [
        f"{count} fly {_AIRFRAME_MAKERS.get(fam, fam)}" if i == 0
        else f"{count} {_AIRFRAME_MAKERS.get(fam, fam)}"
        for i, (fam, count) in enumerate(fams)
    ]
    if len(parts) > 1:
        listed = ", ".join(parts[:-1]) + " and " + parts[-1]
    else:
        listed = parts[0] if parts else ""
    return (f"of the top {top_n} finishers, {listed}, counted from the pilots' "
            "own model entries.")


def _start_energy(ctx: dict) -> str:
    """Start Energy: entry speed, entry altitude, and the airframe question."""
    bill, leader, _, _, _ = _series_fns(ctx)

    entry_spd = charts.grouped_bar_rounds(
        _ROUNDS,
        [("Round winner", leader("entry_speed_kmh"), "leader"),
         ("Bill", bill("entry_speed_kmh"), "bill")],
        title="Start-gate entry speed by round",
        ylabel="km/h",
    )
    entry_spd_cap = "Speed crossing the start gate each round (120 km/h cap)."
    entry_alt = charts.grouped_bar_rounds(
        _ROUNDS,
        [("Round winner", leader("entry_alt_m"), "leader"),
         ("Bill", bill("entry_alt_m"), "bill")],
        title="Start-gate entry altitude by round",
        ylabel="metres",
    )
    entry_alt_cap = "Height at the start gate each round (400 m cap)."

    entry_rec = _explain(
        "Entry height is already maxed, so the free win at the gate is "
        f"{_xref('recommendations', 'rec-entry', 'crossing nearer the 120 km/h speed cap')}. "
        "The 120 km/h entry cap and the wing-loading limits below are set in the "
        f"{_link(_RULES_URL, 'Sport-class regulations')}."
    )

    # Airframe note - trimmed from analysis/airframe_note.md, kept caveated.
    # The family mix is driven from analysis/pilot_equipment.csv so the named
    # airframes cannot drift from the data (RPT-025).
    airframe = _lead(
        "The Airframe Question",
        "The top of the Sport-class field is an airframe mix, not a "
        f"monoculture: {_airframe_mix_sentence()} Event winner Florian Griese "
        "flies the Pike Paradigm (Samba Model) - the same airframe Bill flies - "
        "so the ~2,900-point gap between them is a technique and task-execution "
        "gap, not an equipment one "
        f"({_link(_EVENT_URL, 'event results')}, pilot-entered model names). "
        "The class rules reinforce this: every Sport-class glider "
        "is capped at 5 m span, 7 kg all-up weight and 75 g/dm&sup2; wing "
        "loading, compressing the envelope so no legal airframe holds a decisive "
        f"edge ({_link(_RULES_URL, 'Sport-class regulations')}). As general "
        "aerodynamics rather than a measured difference in this field, a cleaner "
        "or more heavily ballasted airframe can carry more speed and hold a "
        "flatter glide (higher L/D) while lighter wing loading tightens the turn "
        "for weak lift - trade-offs a pilot dials in with ballast and flap "
        "presets, not gains fixed in the kit. Published glide-ratio figures for "
        "these specific models were not found, so treat the aerodynamic points as "
        "directional, not measured."
    )

    return (
        _lead(
            "Entry Speed",
            "Bill routinely crosses the start gate slower than the round winner, "
            "leaving free opening-lap energy on the table. Only Bill and each "
            "round's same-air winner were track-analysed, so the event winner - "
            "who flew other groups - carries no entry telemetry here and is "
            "absent from these two charts.")
        + C.figure(entry_spd, entry_spd_cap, fig_id="ov-fig-sum-entryspd")
        + _lead(
            "Entry Altitude",
            "Bill and the round winner both start near the ceiling, so entry "
            "altitude is not a lever. Event winner omitted for the same telemetry "
            "reason as entry speed.")
        + C.figure(entry_alt, entry_alt_cap, fig_id="ov-fig-sum-entryalt")
        + entry_rec
        + airframe
    )


def _conditions_climbing(ctx: dict) -> str:
    """Conditions, Trajectory & Climbing: from broad dependence to a worked round.

    Conditions dependence first (the broad signal), then where flight time is
    spent, the weather driver, climb geometry and rate, the turn radius, and a
    single-round worked example that shows the pooled patterns in one flight.
    """
    # The three speed sprints score on a different task, so the conditions
    # association is computed and plotted over the 14 distance rounds only -
    # the same n the prose quotes.
    wx = [r for r in ctx["weather"] if r.get("task_type") == "distance"]
    climbs = ctx["phase"]["aggregate_phase_metrics"]["climbs"]

    # (1) Conditions dependence - relative standing vs thermal strength.
    rad = [r.get("shortwave_radiation") for r in wx]
    rho_score = spearman_rho(rad, [r.get("normalised_score") for r in wx])
    rho_laps = spearman_rho(rad, [r.get("laps") for r in wx])
    cond_scatter = charts.scatter_highlight(
        [(r.get("shortwave_radiation"), r.get("normalised_score")) for r in wx],
        highlight_index=None,
        xlabel="Solar radiation (W/m^2, thermal-strength proxy)",
        ylabel="Within-group normalised score",
        title="Relative standing vs thermal strength",
    )
    cond_cap = (
        "Within-group normalised score vs solar radiation (thermal-strength "
        f"proxy) over the {len(wx)} distance rounds; the three speed sprints "
        "score on a different task and are excluded."
    )
    cond_fig = _lead(
        "Conditions Dependence",
        "Wind shows no association with Bill's relative standing, but thermal "
        "strength does: his within-group score tends to rise with stronger lift "
        f"- a moderate positive correlation (Spearman &rho; &asymp; "
        f"{rho_score:+.1f} over the {len(wx)} distance rounds), and his raw lap "
        f"count follows the same way at about the same strength "
        f"({rho_laps:+.1f}). His weakest relative rounds cluster in weak, "
        "late-day lift."
    ) + C.figure(cond_scatter, cond_cap, fig_id="ov-fig-conditions",
                 source=(_WEATHER_URL, "Open-Meteo ERA5 (weather)"))
    cond_rec = _explain(
        "He is competitive when lift is strong and slips when it is scarce, which "
        "points the same way as climb quality: "
        f"{_xref('recommendations', 'rec-climb', 'weak-lift persistence')} is the "
        f"condition-specific fix. Read this as suggestive only - n = {len(wx)} "
        "distance rounds, not a significance claim. Weather from "
        f"{_link(_WEATHER_URL, 'Open-Meteo ERA5')}, flights from the "
        f"{_link(_EVENT_URL, 'event results')}."
    )

    # (2) Trajectory trends - distance-from-course density (log frequency).
    traj = pooled_distance_from_course()

    def _pct(record: dict, lo: float, hi: float | None = None) -> str:
        """Return a pilot's share of flight time in a distance band, formatted.

        Read from the same density dict the figure plots, so the prose and the
        chart cannot drift apart.

        Args:
            record: the ``bill``/``leader`` density record (``frac`` per bin).
            lo: inclusive lower bin edge, in metres.
            hi: exclusive upper bin edge, in metres; open-ended when omitted.

        Returns:
            str: the share as a one-decimal percentage, e.g. ``"5.9%"``.
        """
        share = sum(
            f for edge, f in zip(traj["edges"][:-1], record["frac"])
            if edge >= lo and (hi is None or edge < hi)
        )
        return f"{100 * share:.1f}%"

    traj_svg = charts.distance_from_course_density(traj, caption="")
    traj_cap = (
        "Pooled ~1 Hz track points over the 14 distance rounds; distance to the "
        "nearest triangle leg, log frequency over 20 m bins. Winner = Bill's "
        "same-air group winner."
    )
    traj_fig = _lead(
        "Trajectory Trends",
        "Most flight time is spent lapping right on the course line, so the "
        "frequency axis is logarithmic to expose the rare far excursions. The "
        "winner's distribution is a tight peak against the course with a long, "
        f"flat tail: he holds {_pct(traj['leader'], 0, 40)} of his flight time "
        f"within 40 m of a leg, yet spends {_pct(traj['leader'], 300)} of it "
        f"beyond 300 m against Bill's {_pct(traj['bill'], 300)} - a willingness "
        "to stray much further off the course line when the lift is worth it. "
        f"Bill sits in a moderate mid-band (median {traj['bill']['median']:.1f} "
        f"vs the winner's {traj['leader']['median']:.1f} m): neither as tight to "
        "the line by default nor as committed to the excursion."
    ) + C.figure(traj_svg, traj_cap, fig_id="ov-fig-trajectory",
                 source=(_EVENT_URL, "event results (rcmodelspot)"))

    # (3) Thermal strength / weather - solar strip (all 17 rounds: the strip is
    # read against the per-round views, which include the sprints).
    solar = charts.conditions_strip(
        [w.get("shortwave_radiation") for w in ctx["weather"]],
        labels=_ROUNDS,
        title="Solar radiation by round (thermal-strength proxy)",
    )
    solar_cap = (
        "Solar radiation per round, normalised across the week (pastel yellow = "
        "weakest lift, deep red = strongest)."
    )
    solar_fig = _lead(
        "Thermal Strength & Weather",
        "The usable thermal-strength proxy. Read the laps against this strip: "
        "Bill's gap to the round winner grows as the lift pales."
    ) + C.figure(solar, solar_cap, fig_id="ov-fig-sum-solar",
                 source=(_WEATHER_URL, "Open-Meteo ERA5 (weather)"))

    # (4) Climb geometry and (5) climb rate.
    climb_geom = charts.paired_bars(
        ["Height per thermal", "Circle radius"],
        [climbs["bill_gain_m_per_climb"], climbs["bill_median_radius_m"]],
        [climbs["leader_gain_m_per_climb"], climbs["leader_median_radius_m"]],
        title="Climb geometry: Bill vs leader",
        ylabel="metres",
    )
    climb_geom_cap = (
        "Height gained per thermal and circle radius, Bill vs the leader "
        "(metres). Radius here is the per-round average of each round's median "
        "climb radius; the pooled per-point median is plotted separately under "
        "Thermalling Turn Radius below."
    )
    climb_geom_fig = _lead(
        "Climb Geometry",
        f"Bill banks {climbs['bill_gain_m_per_climb']:.0f} m per thermal against "
        f"the leader's {climbs['leader_gain_m_per_climb']:.0f} m (~35% less), in "
        f"wider circles - {climbs['bill_median_radius_m']:.1f} vs "
        f"{climbs['leader_median_radius_m']:.1f} m, averaging each round's "
        "median climb radius. Yet he spends less total time circling "
        f"({climbs['bill_total_climb_time_s']:.0f} vs "
        f"{climbs['leader_total_climb_time_s']:.0f} s) - he is not "
        "over-thermalling; weak climbs make him land early on poor-lift days."
    ) + C.figure(climb_geom, climb_geom_cap, fig_id="ov-fig-climb-geom")

    climb_rate = charts.paired_bars(
        ["Mean climb", "Best climb"],
        [climbs["bill_mean_rate_ms"], climbs["bill_best_rate_ms"]],
        [climbs["leader_mean_rate_ms"], climbs["leader_best_rate_ms"]],
        title="Climb rate: Bill vs leader",
        ylabel="m/s",
    )
    climb_rate_cap = "Mean and best climb rate, Bill vs the same-air leader (m/s)."
    climb_rate_fig = _lead(
        "Climb Rate",
        f"The same climb-quality gap in vertical speed: Bill climbs at "
        f"{climbs['bill_mean_rate_ms']:.2f}/{climbs['bill_best_rate_ms']:.2f} vs "
        f"the leader's "
        f"{climbs['leader_mean_rate_ms']:.2f}/{climbs['leader_best_rate_ms']:.2f} "
        "m/s (mean/best)."
    ) + C.figure(climb_rate, climb_rate_cap, fig_id="ov-fig-climb-rate")

    # (6) Thermalling turn radius density.
    tr = pooled_turn_radius()
    tr_svg = charts.turn_radius_density(tr, caption="")
    tr_cap = (
        "Per-point turn radius in detected sustained climbs, pooled over the 14 "
        "distance rounds; dashed lines mark each pilot's median. This is the "
        "pooled per-point median, so it differs from the per-climb mean quoted "
        "under Climb Geometry. Winner = Bill's same-air group winner."
    )
    tr_fig = _lead(
        "Thermalling Turn Radius",
        f"Inside sustained climbs Bill circles about 30% wider than the winner - "
        f"a pooled per-point median of {tr['bill']['median']:.1f} vs "
        f"{tr['leader']['median']:.1f} m across every circling sample, against "
        f"the {climbs['bill_median_radius_m']:.1f} / "
        f"{climbs['leader_median_radius_m']:.1f} m per-round averages above. "
        "Wider "
        "circles sink more of each turn into repositioning than climbing - the "
        "same climb-quality lever, seen in the turn itself."
    ) + C.figure(tr_svg, tr_cap, fig_id="ov-fig-turn-radius",
                 source=(_EVENT_URL, "event results (rcmodelspot)"))
    climb_rec = _explain(
        "Both readings point at the same drill: "
        f"{_xref('recommendations', 'rec-climb', 'tighter, better-centred circles')} "
        "to bank more height per thermal, which is also the one in-flight signal "
        "a coach could feed him legally today - the "
        f"{_xref('innovations', 'inn-live', 'live climb-rate cueing tier')} "
        "builds on exactly this measurement. Circling geometry is measured from "
        f"the ~1 Hz tracks on the {_link(_EVENT_URL, 'event results')}."
    )

    # (7) Round 12 worked example - ground track. Round 12 is the weak-lift
    # bombout: Bill's fastest clean lap covered 4,622 m of ground against the
    # leader's 1,819 m (line ratio 2.54) while turn radii were comparable
    # (42.0 vs 40.9 m) - see analysis/per_round_metrics.csv, round 12.
    r12 = load_round(12)
    r12_track = charts.ground_track(
        r12,
        title="Round 12 ground track - Bill vs the same-air leader",
    )
    r12_cap = (
        "Round 12 ground track: the course triangle with full-resolution GPS "
        "traces, Bill vs the same-air leader Jens Geider. Bill's loops off the "
        "course line are the searching that cost him the round; the corner arcs "
        "of the two pilots are much the same size."
    )
    r12_fig = _lead(
        "Round 12: A Worked Example",
        "One round makes the pooled patterns concrete, and it is the weak-lift "
        "case rather than the tidy one. Bill managed 2 laps to the leader's 8: "
        "his fastest clean lap covered 4,622 m of ground against the leader's "
        "1,819 m - 2.54&times; the distance for the same lap - almost all of it "
        "off-course loops hunting for lift that would not connect. The corners "
        "were not the problem: turn radii were comparable at 42.0 m to 40.9 m. "
        "It is the mirror image of the pooled picture, where the winner is the "
        "one who ranges far when it pays and Bill's excursions bought less "
        "height."
    ) + C.figure(r12_track, r12_cap, fig_id="ov-fig-r12-track",
                 source=(_EVENT_URL, "event results (rcmodelspot)"))
    r12_rec = _explain(
        "A day like this is won by connecting sooner, not by flying tidier: the "
        f"drill is {_xref('recommendations', 'rec-climb', 'decisive re-centring in weak lift')}, "
        "and it is the decision an on-the-ground "
        f"{_xref('innovations', 'inn-navigator', 'navigator reading live telemetry')} "
        "is best placed to support. Round 12 laps and score: "
        f"{_link(_EVENT_URL, 'event results')}."
    )

    return (
        cond_fig + cond_rec
        + traj_fig
        + solar_fig
        + climb_geom_fig
        + climb_rate_fig
        + tr_fig + climb_rec
        + r12_fig + r12_rec
    )


_BUILDERS = {
    "ov-headline": _headline,
    "ov-scoring": _scoring,
    "ov-start-energy": _start_energy,
    "ov-conditions": _conditions_climbing,
}


def render(ctx: dict) -> str:
    """Render the Overview view fragment (wrapped as an Analysis view).

    Args:
        ctx: shared build context from :func:`data.build_context`.

    Returns:
        str: a ``<div class="view active" id="view-overview">`` fragment.
    """
    intro = (
        "Bill flew a clean, consistent World Masters and finished mid-field. The "
        "data points to one dominant lever and a clear order behind it: this "
        "overview sets out the headline, then scoring and pace, start energy, and "
        "the conditions, trajectory and climbing that separate skill from air. "
        "Every figure is drawn from his own flights against the "
        f"{_link(_EVENT_URL, 'same-air leader each round')}."
    )
    summary = C.summary(intro, _SUMMARY_BULLETS, top_id="ov-top")

    overall_read = _lead(
        "The Overall Read",
        "Across all 17 rounds Bill (green) sits below his same-air "
        "<strong>round winner</strong> (blue) on score, laps and cruise speed, "
        "while matching everyone at the start gate. The gap tracks the day's "
        "lift, and event winner <strong>Florian Griese</strong> (grey) marks the "
        "benchmark - though from his own group, not Bill's air."
    )

    sections = []
    for sid, heading in _SECTIONS:
        body = _BUILDERS[sid](ctx)
        sections.append(C.collapsible(sid, heading, body, top_id="ov-top"))

    inner = (
        summary + overall_read
        + C.expand_collapse_controls()
        + "".join(sections)
    )
    return f'<div class="view active" id="view-overview">{inner}</div>'
