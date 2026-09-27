"""Home page.

Very concise landing view: a short project summary paragraph and the three
sections listed as linked headings that route to the other pages (RPT-009).
No deep content, no collapsible sections.

Anchor / id scheme:
    page-home                     the routing container (set by assemble)
    home-link-analysis            link -> Analysis page
    home-link-recommendations     link -> Recommendations page
    home-link-innovations         link -> Innovations page

Cross-page routing uses the shared xref convention
(``<a class="xref" data-page="..." data-anchor="...">``); the handler that
switches page and scrolls to the anchor is wired centrally, not here.
"""

from __future__ import annotations

from .. import components as C

# Public event page on rcmodelspot (the standings + telemetry source).
_EVENT_URL = (
    "https://www.rcmodelspot.com/Ranking/"
    "f772fc7c-c4c5-406d-9c21-f4e76044ddb7"
)

# (target page id, target anchor, heading label, one-line description).
_SECTIONS = [
    ("analysis", "ov-top", "Performance Analysis",
     "Round by round against the same-air leader in each heat, decomposed by "
     "flight phase - cruise, climb, start and turns - and read against the "
     "day's conditions."),
    ("recommendations", "rec-top", "Recommendations",
     "The training actions that follow from the evidence, in priority order, "
     "with drills, further analysis, resources and rules-legal live-signal "
     "options."),
    ("innovations", "inn-top", "Innovations",
     "The art of the possible for coaching technology, from a post-flight AI "
     "coach to a navigator heads-up display, each weighed against the "
     "Sport-class rules."),
]


def render(ctx: dict) -> str:
    """Render the Home page fragment.

    Args:
        ctx: shared build context (see :func:`data.build_context`).

    Returns:
        str: the Home page inner HTML (routing wrapper added by assemble).
    """
    intro = (
        "<p>This is a coaching analysis of Bill Maisey's (Anglesey MAC) "
        "performance at the "
        f'<a href="{C.esc(_EVENT_URL)}" target="_blank" rel="noopener">World '
        "Masters, Sport class, Oschatz 2026</a> - 38 pilots over 17 rounds, "
        "where Bill finished 22nd. It is built entirely from the public "
        "rcmodelspot GPS telemetry: every pilot's roughly 1 Hz track is "
        "recorded, so each round is compared like for like against the pilot "
        "who led Bill's own heat group and flew the same air, rather than "
        "against the overall winner in different conditions.</p>"
    )
    items = []
    for pid, anchor, label, desc in _SECTIONS:
        items.append(
            "<li>"
            f'<a class="xref" id="home-link-{pid}" data-page="{pid}" '
            f'data-anchor="{anchor}">{C.esc(label)}</a>'
            f'<p class="home-link-desc">{C.esc(desc)}</p>'
            "</li>"
        )
    return (
        "<h1>GPS Triangle World Masters, Oschatz 2026</h1>"
        f"{intro}"
        f'<ul class="home-links">{"".join(items)}</ul>'
    )
