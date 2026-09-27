"""Reusable HTML fragment builders for the report.

These compose the page shell (head, sticky top nav, page wrapper) and the
repeated content primitives (per-view summary block, collapsible sections with
back-to-top, expand/collapse-all controls, captioned figures, stat tiles / KPI
rows). None of them emit coloured accent bars or gradients, and no fragment
contains emoji or brand names (DSN-001 hard rules).

Stage 2 builds page content by calling these helpers; the routing/behaviour JS
lives in :mod:`assemble`.
"""

from __future__ import annotations

import html

from .design import GOOGLE_FONTS_LINK, css

# The four top-level pages (id, label). Order is fixed and load-bearing:
# tests assert exactly these four nav links.
NAV_PAGES = [
    ("home", "Home"),
    ("analysis", "Analysis"),
    ("recommendations", "Recommendations"),
    ("innovations", "Innovations"),
]

TITLE_TEXT = "GPS Triangle World Masters, Oschatz 2026"


def esc(text: str) -> str:
    """HTML-escape ``text`` for safe inclusion in markup."""
    return html.escape(str(text), quote=True)


def head(title: str = TITLE_TEXT) -> str:
    """Return the ``<head>`` block with fonts link and inlined CSS.

    Args:
        title: the document ``<title>`` (defaults to the report title).

    Returns:
        str: a complete ``<head>...</head>`` fragment.
    """
    return (
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title>"
        f"{GOOGLE_FONTS_LINK}"
        f"<style>{css()}</style>"
        "</head>"
    )


def topnav() -> str:
    """Return the sticky top navigation bar.

    Left: the plain-text report title (no logo/emoji). Right: always-visible
    links for the four pages, plus a burger toggle shown at <=720px. The
    links carry ``data-nav`` attributes the routing JS binds to.

    Returns:
        str: the ``<nav>`` fragment.
    """
    links = "".join(
        f'<a data-nav="{pid}" onclick="showPage(\'{pid}\')">{esc(label)}</a>'
        for pid, label in NAV_PAGES
    )
    return (
        '<nav class="topnav"><div class="topnav-inner">'
        f'<span class="topnav-title">{esc(TITLE_TEXT)}</span>'
        '<button class="burger" aria-label="Menu" '
        'onclick="toggleBurger()">Menu</button>'
        f'<div class="topnav-links" id="topnav-links">{links}</div>'
        "</div></nav>"
    )


def page_wrap(page_id: str, inner: str) -> str:
    """Wrap a page's content in its routing container.

    Args:
        page_id: one of the NAV_PAGES ids (``home``/``analysis``/...).
        inner: the page's inner HTML.

    Returns:
        str: a ``<section class="page" id="page-...">`` wrapper.
    """
    return f'<section class="page" id="page-{esc(page_id)}">{inner}</section>'


def summary(intro: str, bullets: list[tuple[str, str]], *,
            top_id: str = "top") -> str:
    """Return a per-view summary block: intro sentences + anchor-linked bullets.

    Args:
        intro: one or more sentences of lead-in prose (HTML allowed).
        bullets: list of ``(anchor_id, text)`` pairs; each bullet links to the
            on-page section with ``id=anchor_id``.
        top_id: the anchor id assigned to this summary (back-to-top target).

    Returns:
        str: a ``<div class="summary">`` fragment.
    """
    items = "".join(
        f'<li><a href="#{esc(aid)}" onclick="expandSection(\'{esc(aid)}\')">'
        f"{esc(text)}</a></li>"
        for aid, text in bullets
    )
    return (
        f'<div class="summary" id="{esc(top_id)}">'
        f"<p>{intro}</p>"
        f"<ul>{items}</ul>"
        "</div>"
    )


def collapsible(section_id: str, heading: str, body: str, *,
                level: int = 2, top_id: str = "top",
                collapsed: bool = False) -> str:
    """Return a collapsible section with a back-to-top control.

    The header is clickable to toggle the body; a small back-to-top link jumps
    to the page's summary. Sections carry ``data-section`` so the
    expand/collapse-all controls can target them.

    Args:
        section_id: stable anchor id for the section (summary bullets link here).
        heading: section heading text.
        body: the section's inner HTML.
        level: heading level (2 or 3).
        top_id: anchor id to scroll back to (the page summary).
        collapsed: whether the section starts collapsed.

    Returns:
        str: a ``<div class="section">`` fragment.
    """
    tag = f"h{level}"
    cls = "section collapsed" if collapsed else "section"
    # Dynamic control label (RPT-014): 'Expand' when collapsed, 'Collapse' when
    # expanded. The initial text matches the initial state; the app JS keeps it
    # in sync on every state change.
    toggle_label = "Expand" if collapsed else "Collapse"
    return (
        f'<div class="{cls}" data-section id="{esc(section_id)}">'
        '<div class="section-head" onclick="toggleSection(this)">'
        f"<{tag}>{esc(heading)}</{tag}>"
        "<span>"
        f'<span class="section-toggle">{toggle_label}</span>'
        f'<a class="back-to-top" href="#{esc(top_id)}" '
        'onclick="event.stopPropagation()">back to top</a>'
        "</span>"
        "</div>"
        f'<div class="section-body">{body}</div>'
        "</div>"
    )


def expand_collapse_controls() -> str:
    """Return the Expand all / Collapse all button pair.

    Returns:
        str: a ``<div class="controls">`` fragment. The buttons call
        ``expandAll()`` / ``collapseAll()`` in the page JS.
    """
    return (
        '<div class="controls">'
        '<button type="button" onclick="expandAll(this)">Expand all</button>'
        '<button type="button" onclick="collapseAll(this)">Collapse all</button>'
        "</div>"
    )


def figure(svg: str, caption: str, *, fig_id: str | None = None,
           source: tuple[str, str] | list[tuple[str, str]] | None = None) -> str:
    """Wrap an inline-SVG chart in a captioned ``<figure>``.

    Every figure in the report is captioned (DSN-001), so ``caption`` must be
    non-empty; a blank caption is replaced with a minimal placeholder to keep
    the ``<figcaption>`` present.

    The caption text is always HTML-escaped. To ground a figure with a
    resolvable source link (RPT-008) the caller passes ``source`` rather than
    embedding raw ``<a>`` markup in ``caption`` (which would be escaped and
    render as literal text). This dedicated path is the only way trusted HTML
    enters a caption: each source is rendered as a single ``<a>`` whose href and
    text are both escaped, so no untrusted markup can leak through.

    Args:
        svg: the inline SVG string.
        caption: figure caption text (required, non-empty).
        fig_id: optional element id for anchoring.
        source: an optional ``(url, text)`` pair, or a list of them, appended to
            the caption as ``Source: <a>...</a>`` external links.

    Returns:
        str: a ``<figure>`` with a non-empty ``<figcaption>``.
    """
    cap = esc(caption) if caption else "Figure"
    if source:
        pairs = [source] if isinstance(source, tuple) else list(source)
        links = "; ".join(
            f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(text)}</a>'
            for url, text in pairs
        )
        if links:
            cap = f"{cap} Source: {links}."
    idattr = f' id="{esc(fig_id)}"' if fig_id else ""
    return f"<figure{idattr}>{svg}<figcaption>{cap}</figcaption></figure>"


def stat_tile(value: str, label: str, sub: str = "") -> str:
    """Return a single KPI stat tile (no accent bar).

    Args:
        value: the headline number/text.
        label: the metric label beneath the value.
        sub: optional supporting line (e.g. a comparison).

    Returns:
        str: a ``<div class="stat-tile">`` fragment.
    """
    sub_html = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    return (
        '<div class="stat-tile">'
        f'<div class="value num">{esc(value)}</div>'
        f'<div class="label">{esc(label)}</div>'
        f"{sub_html}</div>"
    )


def legality_consideration(text: str) -> str:
    """Return a 'Legality Consideration' inline-bold lead-in at body size.

    Renders the label as bold inline emphasis at body-text size (a highlighted
    lead-in, NOT a heading element) followed by the consideration text (RPT-015).
    Replaces the former 'Legality gate' label; use this for every legality note
    in Innovations and elsewhere.

    Args:
        text: the consideration prose that follows the bold label (HTML allowed).

    Returns:
        str: a ``<p>`` fragment with a bold ``Legality Consideration`` lead-in.
    """
    return (
        '<p class="legality"><strong class="legality-label">'
        "Legality Consideration.</strong> "
        f"{text}</p>"
    )


def kpi_row(tiles: list[str]) -> str:
    """Return a flex row of stat tiles.

    Args:
        tiles: list of ``stat_tile`` fragment strings.

    Returns:
        str: a ``<div class="kpi-row">`` fragment.
    """
    return f'<div class="kpi-row">{"".join(tiles)}</div>'
