"""Home page (STUB — Stage 2 fills prose).

Very concise landing view: a short project summary paragraph and the three
sections listed as linked headings that route to the other pages (RPT-009).
No deep content, no collapsible sections.

Anchor / id scheme:
    page-home                     the routing container (set by assemble)
    home-link-analysis            link -> Analysis page
    home-link-recommendations     link -> Recommendations page
    home-link-innovations         link -> Innovations page
"""

from __future__ import annotations

from .. import components as C

# (target page id, heading label) for the three linked section headings.
_SECTIONS = [
    ("analysis", "Performance Analysis"),
    ("recommendations", "Recommendations"),
    ("innovations", "Innovations"),
]


def render(ctx: dict) -> str:
    """Render the Home page fragment.

    Args:
        ctx: shared build context (see :func:`data.build_context`).

    Returns:
        str: the Home page inner HTML (routing wrapper added by assemble).
    """
    intro = (
        "<p>[STUB] A single-file analysis of Bill Maisey's 17 rounds at the "
        "2026 World Masters Sport-class GPS Triangle competition in Oschatz, "
        "benchmarked against the same-air leader in each heat. Stage 2 replaces "
        "this with the finished summary.</p>"
    )
    links = "".join(
        f'<li><a id="home-link-{pid}" data-nav="{pid}" '
        f'onclick="showPage(\'{pid}\')">{C.esc(label)}</a></li>'
        for pid, label in _SECTIONS
    )
    return (
        "<h1>Bill's GPS Triangle Analysis 2026</h1>"
        f"{intro}"
        f'<ul class="home-links">{links}</ul>'
    )
