"""Analysis - Overview view (Stage 2 content).

The Overview is the default view of the Analysis page. It opens with a short
verdict summary and anchor-linked bullets, then walks the coaching argument in
five collapsible Point-Evidence-Explain sections, each figure drawn from live
``ctx`` data and captioned, each claim backed by an on-page chart and/or a
source link, and each lever cross-linked to its recommendation.

Anchor / id scheme (section ids; summary bullets link to these):
    ov-top          summary block / back-to-top target
    ov-headline     headline result + gap decomposition
    ov-levers       phase levers ranked (cruise/climb/entry/turns)
    ov-conditions   conditions dependence
    ov-progression  week-long progression (skill vs conditions)
    ov-consistency  floor vs ceiling / consistency
"""

from __future__ import annotations

import statistics

from .. import charts, components as C
from ..data import BILL_GUID, load_round, load_standings

# --- Source links (link bank) ----------------------------------------------
_EVENT_URL = "https://www.rcmodelspot.com/Ranking/f772fc7c-c4c5-406d-9c21-f4e76044ddb7"
_RULES_URL = "https://gps-triangle.net/gps-triangle/regulations-documents/"
_WEATHER_URL = "https://open-meteo.com/"

# Speed-sprint rounds (1-indexed) score no landing and are analysed apart.
_SPEED_ROUNDS = {4, 10, 16}

_SECTIONS = [
    ("ov-headline", "Headline result"),
    ("ov-levers", "Where the ground is lost - phase levers"),
    ("ov-conditions", "Conditions dependence"),
    ("ov-progression", "Progression across the week"),
    ("ov-consistency", "Consistency - floor vs ceiling"),
]

_SUMMARY_BULLETS = [
    ("ov-headline", "22nd of 38 (12,562 pts); the gap is almost all distance-task"),
    ("ov-levers", "Biggest lever: cruise speed between thermals"),
    ("ov-conditions", "Relatively stronger when thermals are strong"),
    ("ov-progression", "Progression separates skill from conditions"),
    ("ov-consistency", "High ceiling; the fastest gain is raising the floor"),
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


def _point(text: str) -> str:
    """Render the Point line of a Point-Evidence-Explain block."""
    return f'<p class="pee-point"><strong>Point.</strong> {text}</p>'


def _explain(text: str) -> str:
    """Render the Explain line of a Point-Evidence-Explain block."""
    return f'<p class="pee-explain"><strong>What to do.</strong> {text}</p>'


# --- Section builders -------------------------------------------------------
def _headline(ctx: dict) -> str:
    """Headline result: rank, total, and the gap-to-winner decomposition."""
    official = ctx["official"]
    rank = official["rank"]
    total = official["total_score"]
    gap = 15449 - total  # winner Florian Griese 15,449

    tiles = C.kpi_row([
        C.stat_tile(f"{rank} / 38", "Final placing", "World Masters, Sport class"),
        C.stat_tile(f"{total:,}", "Total points", "best 16 of 17 rounds"),
        C.stat_tile(f"{gap:,}", "Points behind winner", "Florian Griese, 15,449"),
        C.stat_tile("600", "Landing points", "clean on all 14 distance rounds"),
    ])

    # Gap decomposition by task type, worst round dropped per pilot (reconciles
    # to the 2,887 total). Landings/penalties contribute nothing - Bill is level
    # or ahead there.
    waterfall = charts.waterfall(
        [("Distance task", 2197.0),
         ("One-lap speed", 690.0),
         ("Landings / penalties", 0.0)],
        title="Gap to the winner, by task type",
        xlabel="Points behind the winner",
    )
    cap = (
        "Where the 2,887-point gap to the winner comes from, with each pilot's "
        "worst round dropped: about 76% is the distance task and 24% the one-lap "
        "speed sprint; landings and penalties add nothing."
    )
    fig = C.figure(waterfall, cap, fig_id="ov-fig-gap")

    point = _point(
        "Bill finished <strong>22nd of 38</strong> on 12,562 points, 2,887 "
        "behind winner Florian Griese. Almost the entire gap is the distance "
        "task; his landings and rule compliance were faultless all week."
    )
    explain = _explain(
        "The training focus is lap count in the distance task, not tidying up "
        "landings or avoiding penalties - those are already maxed. The next "
        "section ranks the phases that cost the laps, feeding the "
        f"{_xref('recommendations', 'rec-cruise', 'recommendations')}. Full "
        f"standings: {_link(_EVENT_URL, 'event results (rcmodelspot)')}."
    )
    return point + tiles + fig + explain


def _levers(ctx: dict) -> str:
    """Phase levers ranked: cruise > climb > entry > turns."""
    phase = ctx["phase"]
    straight = phase["aggregate_phase_metrics"]["straight"]
    start = phase["aggregate_phase_metrics"]["start"]
    climbs = phase["aggregate_phase_metrics"]["climbs"]
    dec = phase["per_lap_time_deficit_decomposition"]

    # (1) The clean-lap time deficit, split into where it is spent.
    deficit_wf = charts.waterfall(
        [("Cruise (straight glide)", dec["straight_deficit_s"]),
         ("Turns & lines", dec["turn_deficit_s"])],
        title="Clean-lap time deficit vs the same-air leader",
        xlabel="Seconds slower per clean lap",
    )
    deficit_cap = (
        f"Bill's clean lap is about {dec['mean_lap_deficit_s']:.0f} s slower than "
        f"his same-air leader's. {dec['straight_share_pct']:.0f}% of that is the "
        f"straight glide between thermals; only {dec['turn_share_pct']:.0f}% is "
        "turns and lines. Cruise pace is the dominant lever."
    )

    # (2) Field context: grinder vs sprinter.
    scatter_svg, bill_idx = _field_scatter()
    scatter_cap = (
        "Every pilot's average task speed against average laps over the 14 "
        "distance rounds; Bill (green) sits low-left - fewer laps because the "
        "average pace is slower. Laps decide the score, and pace drives laps."
    )

    # (3) Speeds: cruise + start-gate entry (both km/h).
    speeds = charts.paired_bars(
        ["Clean-lap cruise", "Start-gate entry"],
        [straight["bill_cruise_kmh"], start["bill_entry_speed_kmh"]],
        [straight["leader_cruise_kmh"], start["leader_entry_speed_kmh"]],
        title="Speeds: Bill vs same-air leader",
        ylabel="km/h",
    )
    speeds_cap = (
        f"Clean-lap cruise {straight['bill_cruise_kmh']:.1f} vs "
        f"{straight['leader_cruise_kmh']:.1f} km/h "
        f"(~{straight['cruise_gap_pct']:.0f}% slower). At the start gate Bill "
        f"crosses at {start['bill_entry_speed_kmh']:.0f} vs "
        f"{start['leader_entry_speed_kmh']:.0f} km/h, leaving "
        f"~{start['bill_margin_to_cap_kmh']:.0f} km/h of the 120 km/h cap unused "
        "- free opening-lap energy."
    )

    # (4) Climb geometry (metres) and (5) climb rate (m/s).
    climb_geom = charts.paired_bars(
        ["Height per thermal", "Circle radius"],
        [climbs["bill_gain_m_per_climb"], climbs["bill_median_radius_m"]],
        [climbs["leader_gain_m_per_climb"], climbs["leader_median_radius_m"]],
        title="Climb geometry: Bill vs leader",
        ylabel="metres",
    )
    climb_rate = charts.paired_bars(
        ["Mean climb", "Best climb"],
        [climbs["bill_mean_rate_ms"], climbs["bill_best_rate_ms"]],
        [climbs["leader_mean_rate_ms"], climbs["leader_best_rate_ms"]],
        title="Climb rate: Bill vs leader",
        ylabel="m/s",
    )
    climb_cap = (
        f"Bill banks {climbs['bill_gain_m_per_climb']:.0f} m per thermal against "
        f"the leader's {climbs['leader_gain_m_per_climb']:.0f} m (~35% less), in "
        f"wider circles ({climbs['bill_median_radius_m']:.0f} vs "
        f"{climbs['leader_median_radius_m']:.0f} m radius) and at a lower rate "
        f"({climbs['bill_mean_rate_ms']:.2f}/{climbs['bill_best_rate_ms']:.2f} vs "
        f"{climbs['leader_mean_rate_ms']:.2f}/{climbs['leader_best_rate_ms']:.2f} "
        "m/s mean/best). Yet he spends less total time circling "
        f"({climbs['bill_total_climb_time_s']:.0f} vs "
        f"{climbs['leader_total_climb_time_s']:.0f} s) - he is not "
        "over-thermalling; weak climbs make him land early on poor-lift days."
    )

    point = _point(
        "In cost order the levers are <strong>cruise speed &rarr; climb quality "
        "&rarr; entry speed &rarr; turns</strong>. Cruise pace dominates; turns "
        "are already close to a strength."
    )
    explain = _explain(
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
    return (
        point
        + C.figure(deficit_wf, deficit_cap, fig_id="ov-fig-deficit")
        + C.figure(scatter_svg, scatter_cap, fig_id="ov-fig-field",
                   source=(_EVENT_URL, "event results (rcmodelspot)"))
        + C.figure(speeds, speeds_cap, fig_id="ov-fig-speeds")
        + C.figure(climb_geom, climb_cap, fig_id="ov-fig-climb-geom")
        + C.figure(climb_rate, "Climb rate, mean and best, Bill vs the same-air "
                   "leader (m/s) - the same climb-quality gap in vertical speed.",
                   fig_id="ov-fig-climb-rate")
        + explain
    )


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


def _conditions(ctx: dict) -> str:
    """Conditions dependence: thermal strength tracks his standing, wind does not."""
    wx = ctx["weather"]
    points = [(r.get("shortwave_radiation"), r.get("normalised_score"))
              for r in wx]
    svg = charts.scatter_highlight(
        points,
        highlight_index=None,
        xlabel="Solar radiation (W/m^2, thermal-strength proxy)",
        ylabel="Within-group normalised score",
        title="Relative standing vs thermal strength",
    )
    cap = (
        "Each round's within-group normalised score against solar radiation, the "
        "usable thermal-strength proxy (CAPE was unavailable). Score rises with "
        "radiation."
    )
    point = _point(
        "Wind shows <strong>no association</strong> with Bill's relative "
        "standing, but <strong>thermal strength does</strong>: his normalised "
        "score tracks solar radiation (Spearman &rho; &asymp; +0.61) and his lap "
        "count tracks it too (&rho; &asymp; +0.52). His weakest relative rounds "
        "cluster in weak, late-day lift."
    )
    explain = _explain(
        "He is competitive when lift is strong and slips when it is scarce, which "
        "points the same way as climb quality: "
        f"{_xref('recommendations', 'rec-climb', 'weak-lift persistence')} is the "
        "condition-specific fix. Read this as suggestive only - n &asymp; 14 "
        "distance rounds, not a significance claim. Weather from "
        f"{_link(_WEATHER_URL, 'Open-Meteo ERA5')}, flights from the "
        f"{_link(_EVENT_URL, 'event results')}."
    )
    return point + C.figure(
        svg, cap, fig_id="ov-fig-conditions",
        source=(_WEATHER_URL, "Open-Meteo ERA5 (weather)"),
    ) + explain


def _progression(ctx: dict) -> str:
    """Week-long progression: normalised score (skill) vs raw laps (skill+air)."""
    dist = [r for r in ctx["weather"] if r.get("task_type") == "distance"]
    dist.sort(key=lambda r: str(r.get("start_datetime_local")))
    rounds = [str(r.get("round")) for r in dist]
    score_series = [r.get("normalised_score") for r in dist]
    laps_series = [r.get("laps") for r in dist]
    svg = charts.progression(
        rounds, score_series, laps_series,
        title="Across the week: normalised score vs raw laps",
    )
    cap = (
        "The 14 distance rounds in time order. The solid line is the within-group "
        "normalised score (conditions controlled, a skill proxy); the dashed line "
        "is raw laps (conditions and skill together)."
    )
    point = _point(
        "Splitting conditions from skill, there is <strong>no clear week-long "
        "practice trend</strong>. Both series swing round to round with the air; "
        "his two strongest normalised results (Rounds 7 and 17) are a first-day "
        "and a last-day flight, not the ends of a rising line."
    )
    explain = _explain(
        "Round-to-round conditions dominate the record far more than any drift in "
        "form, so read single rounds cautiously and judge progress on the "
        "conditions-controlled score, not on laps. With n &asymp; 14 the trend "
        "signal is weak either way. Per-round scores: "
        f"{_link(_EVENT_URL, 'event results (rcmodelspot)')}."
    )
    return point + C.figure(
        svg, cap, fig_id="ov-fig-progression",
        source=(_EVENT_URL, "event results (rcmodelspot)"),
    ) + explain


def _consistency(ctx: dict) -> str:
    """Consistency: the downside rounds cost more than the best rounds gain."""
    dist = [r for r in ctx["rounds_csv"] if r.get("task_type") == "distance"]
    scores = [r.get("score") for r in dist]
    laps = [r.get("laps") for r in dist]

    laps_mean = statistics.mean(laps)
    laps_med = statistics.median(laps)
    laps_sd = statistics.pstdev(laps)
    score_mean = statistics.mean(scores)
    score_med = statistics.median(scores)
    score_sd = statistics.pstdev(scores)

    tiles = C.kpi_row([
        C.stat_tile(f"{laps_mean:.1f}", "Laps per distance round",
                    f"median {laps_med:.0f}, sd {laps_sd:.1f}"),
        C.stat_tile(f"{score_mean:.0f}", "Mean round score",
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
        "The 14 distance-round scores on one scale; the lower row isolates the two "
        "bombouts (R12 = 418, dropped; R9 = 581). These sit far below the median "
        f"of {score_med:.0f}."
    )

    r17 = load_round(17)
    ceiling = charts.cumulative_laps(
        r17["bill"]["lap_offsets_s"],
        r17["leader"]["lap_offsets_s"],
        working_time_s=r17["task"]["working_time_min"] * 60,
        title="Round 17 cumulative laps - Bill vs the same-air leader",
    )
    ceiling_cap = (
        f"Round 17: Bill (green) tracks the same-air leader "
        f"{C.esc(r17['leader']['name'])} (teal) lap-for-lap to a near-perfect 999. "
        "When lift is good the top-end pace is already there."
    )

    point = _point(
        "The score is dragged down by a few weak-lift rounds, not by the good "
        "ones falling short. The two bombouts sit far below the median; his best "
        "rounds nearly match the leader."
    )
    explain = _explain(
        "A bombout costs more than a strong round gains, so the fastest ranking "
        "win is <strong>raising the floor</strong> - staying aloft through weak, "
        "scratchy lift - rather than chasing the ceiling. This is the "
        f"{_xref('recommendations', 'rec-climb', 'weak-lift climb work')} again, "
        "seen from the results side. Round scores: "
        f"{_link(_EVENT_URL, 'event results (rcmodelspot)')}."
    )
    return (
        point
        + tiles
        + C.figure(strip, strip_cap, fig_id="ov-fig-consistency",
                   source=(_EVENT_URL, "event results (rcmodelspot)"))
        + C.figure(ceiling, ceiling_cap, fig_id="ov-fig-ceiling")
        + explain
    )


_BUILDERS = {
    "ov-headline": _headline,
    "ov-levers": _levers,
    "ov-conditions": _conditions,
    "ov-progression": _progression,
    "ov-consistency": _consistency,
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
        "overview sets out the headline, ranks the phases where laps are lost, "
        "then separates conditions and week-long form from underlying skill. Every "
        "figure is drawn from his own flights against the "
        f"{_link(_EVENT_URL, 'same-air leader each round')}."
    )
    summary = C.summary(intro, _SUMMARY_BULLETS, top_id="ov-top")

    sections = []
    for sid, heading in _SECTIONS:
        body = _BUILDERS[sid](ctx)
        sections.append(C.collapsible(sid, heading, body, top_id="ov-top"))

    inner = summary + C.expand_collapse_controls() + "".join(sections)
    return f'<div class="view active" id="view-overview">{inner}</div>'
