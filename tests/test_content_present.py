"""Content-presence tests (RPT-003/004/009 + DSN-001 figure captioning).

These assert that the four pages carry real content and that the Analysis
Overview and each of the 17 rounds render at least one chart. Against the
Stage 1 STUBS these will LARGELY FAIL by design (the intended red) - Stage 2
and Stage 3 turn them green as page content and per-round figures land.

The figure-caption invariant is expected to hold at every stage.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from scripts.build import assemble


@pytest.fixture(scope="module")
def soup():
    """Parsed generated document."""
    return BeautifulSoup(assemble.build_html(), "html.parser")


@pytest.mark.parametrize("page_id", ["home", "analysis", "recommendations",
                                     "innovations"])
def test_page_has_real_content_no_stubs(soup, page_id):
    """Each page has substantive content and no remaining [STUB] markers."""
    page = soup.select_one(f"#page-{page_id}")
    assert page is not None
    text = page.get_text(" ", strip=True)
    assert "[STUB]" not in text, f"{page_id} still contains stubs"
    assert len(text) > 400, f"{page_id} content too thin"


def test_overview_renders_a_chart(soup):
    """The Analysis Overview view renders at least one inline-SVG chart."""
    view = soup.select_one("#view-overview")
    assert view is not None
    assert view.find("svg") is not None


@pytest.mark.parametrize("n", list(range(1, 18)))
def test_each_round_renders_a_chart(soup, n):
    """Each of the 17 per-round views renders at least one inline-SVG chart."""
    view = soup.select_one(f"#view-round-{n}")
    assert view is not None, f"round {n} view missing"
    assert view.find("svg") is not None, f"round {n} has no chart"


@pytest.mark.parametrize("n", list(range(1, 18)))
def test_each_round_has_dashboard_energy_and_track(soup, n):
    """Each round view opens with the RPT-021 dashboard (2x4 grid + colour key)
    and carries an Energy Management figure and a ground-track figure."""
    view = soup.select_one(f"#view-round-{n}")
    assert view is not None, f"round {n} view missing"
    # Dashboard: the 8-cell grid plus its colour key legend (RPT-021).
    assert len(view.select(".dash-cell")) == 8, f"round {n} dashboard not 2x4"
    assert view.select_one(".dash-key") is not None, f"round {n} has no colour key"
    # Energy Management dual-panel figure and ground-track figure (RPT-018/011).
    assert view.select_one(f"#r{n}-fig-energy") is not None, f"round {n} no energy fig"
    assert view.select_one(f"#r{n}-fig-track") is not None, f"round {n} no track fig"


def test_overview_four_thematic_sections_with_trajectory_figures(soup):
    """The Overview is organised into the four Title-Case thematic sections in
    order (Headline Result / Scoring, Laps & Speed / Start Energy / Conditions,
    Trajectory & Climbing), led by an 'Overall Read' paragraph above the first
    section, and carries the three new trajectory figures with captions
    (RPT-022/023/024)."""
    view = soup.select_one("#view-overview")
    assert view is not None
    # The four thematic sections exist and appear in this exact DOM order.
    section_ids = [s.get("id") for s in view.select(".section")]
    assert section_ids == ["ov-headline", "ov-scoring",
                           "ov-start-energy", "ov-conditions"], section_ids
    # The 'Overall Read' lead paragraph precedes the first section (ov-headline).
    lead = view.find(lambda t: t.name == "p"
                     and "pee-point" in (t.get("class") or [])
                     and "Overall Read" in t.get_text())
    assert lead is not None, "no 'Overall Read' lead paragraph"
    headline = view.select_one("#ov-headline")
    assert headline is not None
    ordered = view.find_all(True)
    assert ordered.index(lead) < ordered.index(headline), \
        "'Overall Read' must appear before the first section"
    # The three new Overview trajectory figures are present, are <figure>s, and
    # each carries a non-empty caption.
    for fid in ("ov-fig-trajectory", "ov-fig-turn-radius", "ov-fig-r12-track"):
        fig = view.select_one(f"#{fid}")
        assert fig is not None, f"missing {fid}"
        assert fig.name == "figure", f"{fid} is not a <figure>"
        cap = fig.find("figcaption")
        assert cap is not None and cap.get_text(strip=True), \
            f"{fid} has no non-empty caption"


def test_analysis_is_insight_first_no_pee_labels(soup):
    """Analysis pages are insight-first (RPT-003/004, updated): no literal
    'Point.'/'Evidence.'/'Explain.' bold labels; the Overview keeps a
    'What to do.' recommendation cue, and every per-round view carries
    substantive, quantitative prose."""
    ov = soup.select_one("#view-overview").get_text(" ", strip=True)
    assert "Point." not in ov and "Evidence." not in ov and "Explain." not in ov
    assert "What to do." in ov  # recommendation cue kept
    for n in range(1, 18):
        txt = soup.select_one(f"#view-round-{n}").get_text(" ", strip=True)
        assert "Point." not in txt and "Evidence." not in txt, f"round {n} has a PEE label"
        assert "km/h" in txt and len(txt) > 400, f"round {n} prose thin/unquantified"


def test_every_figure_has_a_nonempty_caption(soup):
    """Every <figure> anywhere in the report has a non-empty <figcaption>."""
    figures = soup.find_all("figure")
    assert figures, "no figures rendered at all"
    for fig in figures:
        cap = fig.find("figcaption")
        assert cap is not None and cap.get_text(strip=True)
