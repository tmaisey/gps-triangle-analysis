"""Analysis - per-round views (STUB skeleton).

Emits one view per round (1-17), each selectable from the Analysis dropdown.
The foundation lays out the per-round section skeleton with correct anchors and
a summary; Stage 2 renders the real figures (energy/altitude trace, ground-track
overlay, cumulative laps, biggest-loss segment, metrics strip incl. weather) and
the round's inline recommendation.

Anchor / id scheme, per round N:
    view-round-N        the view container (Analysis dropdown selects this)
    rN-top              summary / back-to-top target
    rN-energy           altitude/energy trace
    rN-track            ground-track overlay
    rN-laps             cumulative laps vs leader
    rN-loss             biggest-loss segment
    rN-metrics          per-round metrics strip (incl. weather)
    rN-reco             round's inline recommendation
"""

from __future__ import annotations

from .. import components as C

# (suffix, heading) for the per-round sections.
_SECTIONS = [
    ("energy", "Energy / altitude trace"),
    ("track", "Ground-track overlay"),
    ("laps", "Cumulative laps vs leader"),
    ("loss", "Biggest-loss segment"),
    ("metrics", "Round metrics and weather"),
    ("reco", "What to train from this round"),
]


def _round_view(entry: dict, ctx: dict) -> str:
    """Render one round's view skeleton from its index entry."""
    n = entry["round"]
    top = f"r{n}-top"
    kind = "Speed sprint" if entry["task_type"] == "speedrun" else "Distance task"
    label = ctx["round_labels"].get(n, f"Round {n}")
    bullets = [(f"r{n}-{suf}", heading) for suf, heading in _SECTIONS]
    summary = C.summary(
        f"[STUB] Round {n} - {C.esc(entry['heat'])} ({C.esc(kind)}, "
        f"{C.esc(label)}). Same-air leader: {C.esc(entry['leader_name'])}. "
        "Stage 2 writes the round narrative and figures.",
        bullets,
        top_id=top,
    )
    sections = [
        C.collapsible(f"r{n}-{suf}", heading,
                      f"<p>[STUB] Round {n} {C.esc(heading)}.</p>", top_id=top)
        for suf, heading in _SECTIONS
    ]
    inner = (
        f"<h2>Round {n} - {C.esc(label)}</h2>"
        + summary + C.expand_collapse_controls() + "".join(sections)
    )
    return f'<div class="view" id="view-round-{n}">{inner}</div>'


def render(ctx: dict) -> str:
    """Render all 17 per-round view fragments, concatenated.

    Args:
        ctx: shared build context (uses ``index`` and ``round_labels``).

    Returns:
        str: 17 ``<div class="view" id="view-round-N">`` fragments.
    """
    return "".join(_round_view(entry, ctx) for entry in ctx["index"])
