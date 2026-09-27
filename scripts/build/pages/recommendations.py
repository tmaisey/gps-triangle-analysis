"""Recommendations page (STUB skeleton).

Consolidates the one canonical recommendation set, organised into implementation
themes (RPT-005). Each theme anchor is shared with the inline recommendations in
Analysis so both surfaces link to the same id; Stage 2 fills the drills,
further-analysis suggestions, resources and back-links to Analysis evidence.

Anchor / id scheme (theme section ids, shared with Analysis inline recos):
    rec-top       summary / back-to-top target
    rec-cruise    cruise-speed drills + analysis
    rec-climb     climb-quality (height banked) drills + analysis
    rec-entry     entry-speed (use the cap) drills
    rec-turns     turn / line refinement
    rec-signals   rules-legal live signals (audio vario, speech telemetry)
"""

from __future__ import annotations

from .. import components as C

_SECTIONS = [
    ("rec-cruise", "Cruise speed between thermals"),
    ("rec-climb", "Climb quality - height banked per thermal"),
    ("rec-entry", "Entry speed - use the 120 km/h cap"),
    ("rec-turns", "Turnpoint lines"),
    ("rec-signals", "Rules-legal live signals"),
]

_SUMMARY_BULLETS = [
    ("rec-cruise", "Train faster inter-thermal cruise (top lever)"),
    ("rec-climb", "Bank more height per climb on weak days"),
    ("rec-entry", "Use more of the entry-speed cap"),
    ("rec-turns", "Tighten turnpoint lines"),
    ("rec-signals", "Audio vario and speech telemetry callouts"),
]


def render(ctx: dict) -> str:
    """Render the Recommendations page fragment.

    Args:
        ctx: shared build context.

    Returns:
        str: the Recommendations page inner HTML.
    """
    summary = C.summary(
        "[STUB] The recommendations, grouped by implementation theme. Stage 2 "
        "writes the drills, further-analysis items and resource links, each "
        "back-linking to its Analysis evidence and relevant Innovations.",
        _SUMMARY_BULLETS,
        top_id="rec-top",
    )
    sections = [
        C.collapsible(sid, heading,
                      f"<p>[STUB] {C.esc(heading)} - drills and analysis.</p>",
                      top_id="rec-top")
        for sid, heading in _SECTIONS
    ]
    return (
        "<h1>Recommendations</h1>"
        + summary + C.expand_collapse_controls() + "".join(sections)
    )
