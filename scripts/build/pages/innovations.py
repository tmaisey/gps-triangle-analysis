"""Innovations page (STUB skeleton).

The forward-looking coaching-technology roadmap (RPT-006), standalone and
rules-grounded. Each tier gets a stable anchor id so Analysis and
Recommendations can link to it in context. Stage 2 writes the tier prose and
the Sport-class legality framing.

Anchor / id scheme (tier section ids, link targets from other pages):
    inn-top          summary / back-to-top target
    inn-postflight   post-flight AI coach
    inn-navigator    navigator AR HUD (CD discretion)
    inn-live         live AI cueing (audio vario / speech telemetry)
    inn-flywheel     the data flywheel
"""

from __future__ import annotations

from .. import components as C

_SECTIONS = [
    ("inn-postflight", "Post-flight AI coach"),
    ("inn-navigator", "Navigator AR HUD"),
    ("inn-live", "Live AI cueing"),
    ("inn-flywheel", "The data flywheel"),
]

_SUMMARY_BULLETS = [
    ("inn-postflight", "Post-flight AI coach on this same data"),
    ("inn-navigator", "Navigator AR HUD (organiser discretion)"),
    ("inn-live", "Live cueing within the rules"),
    ("inn-flywheel", "A season-long data flywheel"),
]


def render(ctx: dict) -> str:
    """Render the Innovations page fragment.

    Args:
        ctx: shared build context.

    Returns:
        str: the Innovations page inner HTML.
    """
    summary = C.summary(
        "[STUB] The art of the possible for coaching technology, framed against "
        "the Sport-class rules. Stage 2 writes each tier and its legality basis.",
        _SUMMARY_BULLETS,
        top_id="inn-top",
    )
    sections = [
        C.collapsible(sid, heading,
                      f"<p>[STUB] {C.esc(heading)} - concept and legality.</p>",
                      top_id="inn-top")
        for sid, heading in _SECTIONS
    ]
    return (
        "<h1>Innovations</h1>"
        + summary + C.expand_collapse_controls() + "".join(sections)
    )
