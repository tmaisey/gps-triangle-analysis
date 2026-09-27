"""Analysis - Overview view (STUB + one real chart to prove the pipeline).

The Overview is the default view of the Analysis page. Stage 2 fills each
section with Point-Evidence-Explain content and the ranked phase levers; the
foundation lays out the summary, the section skeleton with correct anchors, the
expand/collapse controls, and renders ONE real figure (cumulative laps vs the
same-air leader, Round 1) from live data to prove data -> charts -> figure.

Anchor / id scheme (section ids; summary bullets link to these):
    ov-top          summary block / back-to-top target
    ov-headline     headline result + KPIs
    ov-levers       phase levers ranked (cruise/climb/entry/turns)
    ov-conditions   conditions dependence
    ov-progression  week-long progression (skill vs conditions)
    ov-consistency  floor vs ceiling / consistency
"""

from __future__ import annotations

from .. import charts, components as C
from ..data import load_round

_SECTIONS = [
    ("ov-headline", "Headline result"),
    ("ov-levers", "Where the ground is lost - phase levers"),
    ("ov-conditions", "Conditions dependence"),
    ("ov-progression", "Progression across the week"),
    ("ov-consistency", "Consistency - floor vs ceiling"),
]

_SUMMARY_BULLETS = [
    ("ov-headline", "Headline: 22nd of 38, 12,562 points"),
    ("ov-levers", "Biggest lever: cruise speed between thermals"),
    ("ov-conditions", "Relatively stronger when lift is strong"),
    ("ov-progression", "Progression separates skill from conditions"),
    ("ov-consistency", "High ceiling (matched the leader twice)"),
]


def _pipeline_figure(ctx: dict) -> str:
    """Render one real chart from live data (Round 1 cumulative laps)."""
    r1 = load_round(1)
    svg = charts.cumulative_laps(
        r1["bill"]["lap_offsets_s"],
        r1["leader"]["lap_offsets_s"],
        working_time_s=r1["task"]["working_time_min"] * 60,
        title="Round 1 cumulative laps - Bill vs same-air leader",
    )
    cap = (
        f"Round 1 ({C.esc(r1['heat'])}): laps completed over the 30-minute "
        f"task, Bill (green) against the same-air leader "
        f"{C.esc(r1['leader']['name'])} (teal). Real data rendered by the "
        "build pipeline."
    )
    return C.figure(svg, cap, fig_id="ov-fig-r1laps")


def render(ctx: dict) -> str:
    """Render the Overview view fragment (wrapped as an Analysis view).

    Args:
        ctx: shared build context.

    Returns:
        str: a ``<div class="view active" id="view-overview">`` fragment.
    """
    summary = C.summary(
        "[STUB] Overview summary - Stage 2 writes the verdict prose here.",
        _SUMMARY_BULLETS,
        top_id="ov-top",
    )
    sections = []
    for i, (sid, heading) in enumerate(_SECTIONS):
        if sid == "ov-headline":
            body = _pipeline_figure(ctx) + "<p>[STUB] Headline content.</p>"
        else:
            body = f"<p>[STUB] {C.esc(heading)} - Stage 2 content.</p>"
        sections.append(C.collapsible(sid, heading, body, top_id="ov-top"))
    inner = summary + C.expand_collapse_controls() + "".join(sections)
    return f'<div class="view active" id="view-overview">{inner}</div>'
