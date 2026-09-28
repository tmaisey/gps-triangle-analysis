"""Accessibility, chart-geometry and asset-budget tests for the built report.

Covers the build-review fix items owned by the charts/design/components layer:

* item 9  - keyboard reachability (nav/xref hrefs, collapsible role + keys,
            burger button semantics, focus-visible ring, ``.xref`` cursor)
* item 10 - mobile figure scroll container, active only below the breakpoint
* item 11 - axis ticks never clipped by the outer ``<svg>`` viewBox
* item 12 - progression legend clear of the right-hand axis labels
* item 13 - section controls stack under the heading on mobile
* item 14 - ground-track legend outside the plot frame
* item 15 - one chart width across the content column
* item 17 - descriptive dashboard aria-labels + one captioned dashboard figure
* item 18 - round subsections are ``<h3>`` under the round's ``<h2>``
* item 27 - one Source Sans face, no italic, report size budget
* item 31 - ``scroll-margin-top`` covers every anchor target
* item 32 - Home active in static markup + a ``<noscript>`` notice

Assertions are made against the *built output* (structure/CSS/JS contract) and
against the chart generators' own SVG geometry, not implementation detail.
"""

from __future__ import annotations

import base64
import re

import pytest
from bs4 import BeautifulSoup

from scripts.build import assemble, charts, dashboard, data, design

# Report size budget (spec review B, item 7): the single file stays well under
# the 3 MB an email/preview pipeline can be expected to carry.
SIZE_BUDGET_BYTES = 3 * 1024 * 1024


@pytest.fixture(scope="module")
def html():
    """The full generated HTML document string."""
    return assemble.build_html()


@pytest.fixture(scope="module")
def soup(html):
    """Parsed document."""
    return BeautifulSoup(html, "html.parser")


@pytest.fixture(scope="module")
def css_text():
    """The inlined stylesheet (without the embedded font data URIs)."""
    return re.sub(r"@font-face\{.*?\}", "", design.css(), flags=re.S)


# --- item 9: keyboard accessibility ----------------------------------------
def test_nav_links_are_keyboard_reachable(soup):
    """Every top-nav link carries a real in-page ``href`` (tab order)."""
    links = soup.select(".topnav-links a")
    assert links
    for a in links:
        href = a.get("href", "")
        assert href.startswith("#"), f"nav link without href: {a}"
        assert href[1:] == f"page-{a.get('data-nav')}"


def test_xref_links_have_matching_href(soup):
    """Every cross-page ``a.xref`` has ``href="#<data-anchor>"``."""
    xrefs = soup.select("a.xref")
    assert xrefs
    for a in xrefs:
        assert a.get("href") == "#" + a.get("data-anchor", ""), f"xref: {a}"


def test_nav_and_xref_clicks_stay_on_page(html):
    """The delegated handler intercepts nav links and hash links (no reload)."""
    assert "a[data-nav]" in html or "[data-nav]" in html
    assert "preventDefault" in html
    assert 'a.xref, a[href^="#"]' in html


def test_section_heads_are_keyboard_operable(soup, html):
    """Collapsible heads expose button semantics and an Enter/Space handler."""
    heads = soup.select(".section-head")
    assert heads
    for head in heads:
        assert head.get("role") == "button"
        assert head.get("tabindex") == "0"
        assert head.get("aria-expanded") == "true"
    assert "addEventListener('keydown'" in html
    assert "aria-expanded" in html


def test_burger_is_a_typed_button_with_aria_expanded(soup, html):
    """The mobile burger is ``type="button"`` and reports its expanded state."""
    burger = soup.select_one("button.burger")
    assert burger is not None
    assert burger.get("type") == "button"
    assert burger.get("aria-expanded") == "false"
    assert "aria-expanded" in html


def test_focus_ring_and_xref_cursor_styled(css_text):
    """A deliberate focus ring exists and ``.xref`` gets link affordances."""
    assert ":focus-visible" in css_text
    assert re.search(r"\.xref\s*\{[^}]*cursor:\s*pointer", css_text)


# --- item 10 / 13: mobile layout -------------------------------------------
def test_figures_have_a_mobile_only_scroll_container(soup, css_text):
    """Chart figures wrap the SVG in ``.fig-scroll``; the scroll behaviour and
    the minimum chart width exist only below the mobile breakpoint."""
    figs = [f for f in soup.find_all("figure") if f.find("svg")]
    assert figs
    for fig in figs:
        holder = fig.find("div", class_="fig-scroll")
        if holder is None:            # the dashboard figure opts out
            continue
        assert holder.find("svg") is not None
    head, _, mobile = css_text.partition(
        f"@media (max-width: {design.MOBILE_BREAKPOINT_PX}px)")
    assert "overflow-x: auto" not in head, "scroll container active on desktop"
    assert "min-width: 600px" not in head, "min chart width active on desktop"
    assert "overflow-x: auto" in mobile
    assert "min-width: 600px" in mobile


def test_section_controls_stack_under_the_heading_on_mobile(css_text):
    """Below the breakpoint the section head becomes a column so the toggle and
    back-to-top link sit under the heading instead of over it."""
    _, _, mobile = css_text.partition(
        f"@media (max-width: {design.MOBILE_BREAKPOINT_PX}px)")
    assert re.search(r"\.section-head\s*\{[^}]*flex-direction:\s*column", mobile)


def test_chart_label_font_sizes_are_legible(soup):
    """No chart label is emitted below 12 SVG units (mobile legibility)."""
    small = []
    for fig in soup.select("figure .fig-scroll svg"):
        for el in fig.find_all(attrs={"font-size": True}):
            try:
                size = float(el["font-size"])
            except (TypeError, ValueError):
                continue
            if size < 12:
                small.append((el.name, el["font-size"]))
    assert not small, f"labels below 12 units: {small[:8]}"


# --- item 11: tick clipping -------------------------------------------------
def _text_box(el, font_size):
    """Return an approximate ``(x0, x1, y0, y1)`` box for an SVG text element."""
    x = float(el.get("x", 0))
    y = float(el.get("y", 0))
    width = len(el.get_text()) * font_size * 0.62
    anchor = el.get("text-anchor", "start")
    if anchor == "middle":
        x0, x1 = x - width / 2, x + width / 2
    elif anchor == "end":
        x0, x1 = x - width, x
    else:
        x0, x1 = x, x + width
    return x0, x1, y - font_size * 0.78, y + font_size * 0.25


def _view_box(svg):
    """Return the ``viewBox`` of an SVG tag (the parser lowercases attributes)."""
    return svg.get("viewBox") or svg.get("viewbox")


def _overflowing_labels(svg_markup):
    """Return text elements whose estimated box falls outside the viewBox."""
    soup = BeautifulSoup(svg_markup, "html.parser")
    svg = soup.find("svg")
    _, _, vw, vh = (float(v) for v in _view_box(svg).split())
    bad = []
    for el in svg.find_all("text"):
        if el.get("transform"):          # rotated axis titles
            continue
        try:
            size = float(el.get("font-size", 11))
        except ValueError:
            continue
        x0, x1, y0, y1 = _text_box(el, size)
        if x0 < 0 or x1 > vw or y0 < 0 or y1 > vh:
            bad.append((el.get_text(), round(x0, 1), round(x1, 1),
                        round(y0, 1), round(y1, 1)))
    return bad


@pytest.mark.parametrize("n", [1, 3, 4, 5, 9, 15, 17])
def test_cumulative_laps_ticks_inside_viewbox(n):
    """Every cumulative-laps tick renders inside the SVG box (no lost ticks)."""
    r = data.load_round(n)
    svg = charts.cumulative_laps(
        r["bill"]["lap_offsets_s"], r["leader"]["lap_offsets_s"],
        working_time_s=r["task"]["working_time_min"] * 60)
    assert not _overflowing_labels(svg)


def test_overview_chart_ticks_inside_viewbox(soup):
    """No chart in the built report draws a label outside its own viewBox."""
    offenders = []
    for svg in soup.select("figure .fig-scroll svg"):
        bad = _overflowing_labels(str(svg))
        if bad:
            offenders.append((svg.get("aria-label"), bad[:3]))
    assert not offenders, offenders[:5]


# --- item 12: progression legend --------------------------------------------
def test_progression_legend_clear_of_right_axis():
    """The 'Laps' legend no longer sits under the right-hand axis ticks."""
    svg = charts.progression(list(range(1, 15)), [700 + i for i in range(14)],
                             [8 + (i % 4) for i in range(14)])
    doc = BeautifulSoup(svg, "html.parser")
    legend = [t for t in doc.find_all("text") if t.get_text() == "Laps"]
    assert legend, "no Laps legend entry"
    right_axis_x = min(
        float(t["x"]) for t in doc.find_all("text")
        if t.get("text-anchor") == "start" and t.get_text().isdigit())
    size = float(legend[0].get("font-size", 11))
    _, lx1, _, _ = _text_box(legend[0], size)
    assert lx1 <= right_axis_x, (lx1, right_axis_x)


# --- item 14: ground-track legend -------------------------------------------
def test_ground_track_legend_sits_below_the_plot_frame():
    """The Bill/Leader/Course legend is outside the framed plot, not over the
    traces."""
    svg = charts.ground_track(data.load_round(17))
    doc = BeautifulSoup(svg, "html.parser")
    frame = [r for r in doc.find_all("rect") if r.get("fill") == "none"]
    assert frame, "no plot frame"
    frame_bottom = float(frame[0]["y"]) + float(frame[0]["height"])
    labels = [t for t in doc.find_all("text")
              if t.get_text() in {"Bill", "Leader", "Course"}]
    assert len(labels) == 3
    for t in labels:
        assert float(t["y"]) > frame_bottom, f"legend inside frame: {t}"


# --- item 15: one chart width ----------------------------------------------
def test_all_report_charts_share_one_width(soup):
    """Every figure chart uses the single content-column chart width."""
    widths = set()
    for svg in soup.select("figure .fig-scroll svg"):
        widths.add(float(_view_box(svg).split()[2]))
    assert widths == {float(charts.CHART_W)}, widths


# --- item 17: dashboard accessibility ---------------------------------------
def test_dashboard_svgs_have_descriptive_aria_labels():
    """Dashboard tiles announce their values, not just their chart type."""
    frag = dashboard.dashboard(data.load_round(17))
    doc = BeautifulSoup(frag, "html.parser")
    labels = [s.get("aria-label", "") for s in doc.find_all("svg")]
    assert labels
    generic = {"bullet", "violin", "laps", "wind", "solar"}
    for label in labels:
        assert label.lower() not in generic, f"generic aria-label: {label!r}"
        assert re.search(r"\d", label), f"aria-label without values: {label!r}"


def test_dashboard_is_one_captioned_figure(soup):
    """Each round's dashboard is wrapped in a captioned ``<figure>``."""
    for n in (1, 12, 17):
        view = soup.select_one(f"#view-round-{n}")
        wrap = view.select_one(".dash-wrap")
        assert wrap is not None
        fig = wrap.find_parent("figure")
        assert fig is not None, f"round {n} dashboard not in a <figure>"
        cap = fig.find("figcaption")
        assert cap is not None and cap.get_text(strip=True)


# --- item 18: heading hierarchy ---------------------------------------------
@pytest.mark.parametrize("n", [1, 9, 17])
def test_round_subsections_are_h3(soup, n):
    """A round view has one ``<h2>`` (its title) and ``<h3>`` subsections."""
    view = soup.select_one(f"#view-round-{n}")
    assert len(view.find_all("h2")) == 1
    assert len(view.find_all("h3")) >= 4


def test_report_has_a_real_heading_hierarchy(soup):
    """The document is no longer flat: h3s exist alongside the h2s."""
    assert len(soup.find_all("h3")) >= 50


# --- item 27: font payload + size budget ------------------------------------
def test_one_source_sans_face_and_no_italic():
    """Source Sans ships once as a variable face; the unused italic is gone."""
    face = design.font_face_css()
    assert face.count("font-family:'Source Sans 3'") == 1
    assert "font-weight:400 700" in face.replace(" ", " ")
    assert "font-style:italic" not in face


def test_no_duplicate_embedded_font_payloads(html):
    """No base64 font payload is embedded twice."""
    payloads = re.findall(r"base64,([A-Za-z0-9+/=]+)\)", html)
    assert payloads
    assert len(payloads) == len(set(payloads)), "duplicate font payloads"
    for blob in payloads:
        base64.b64decode(blob)          # each payload is valid base64


def test_report_size_within_budget(html):
    """The single-file report stays inside the size budget."""
    size = len(html.encode("utf-8"))
    assert size <= SIZE_BUDGET_BYTES, f"{size:,} bytes"


# --- items 31 / 32: anchors and no-JS ---------------------------------------
def test_scroll_margin_covers_every_anchor_target(css_text):
    """``scroll-margin-top`` applies to any element with an id."""
    assert re.search(r"\[id\][^{]*\{[^}]*scroll-margin-top", css_text)


def test_home_is_active_in_static_markup_with_noscript(soup):
    """Without JS the Home page still renders and a notice explains the rest."""
    home = soup.select_one("#page-home")
    assert "active" in (home.get("class") or [])
    actives = soup.select(".page.active")
    assert [p.get("id") for p in actives] == ["page-home"]
    noscript = soup.find("noscript")
    assert noscript is not None and noscript.get_text(strip=True)
