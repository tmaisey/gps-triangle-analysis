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


def test_overview_performance_summary_first_with_figures(soup):
    """The Overview leads with the Performance summary (ov-summary) BEFORE the
    headline (ov-headline), carrying the grouped-bar, conditions and rank
    figures (RPT-022)."""
    view = soup.select_one("#view-overview")
    assert view is not None
    summary = view.select_one("#ov-summary")
    headline = view.select_one("#ov-headline")
    assert summary is not None and headline is not None
    # ov-summary appears before ov-headline in document order.
    section_ids = [s.get("id") for s in view.select(".section")]
    assert section_ids.index("ov-summary") < section_ids.index("ov-headline")
    # Grouped-bar charts (score/laps/speed/entry) + conditions strip + rank strip.
    for fid in ("ov-fig-sum-score", "ov-fig-sum-laps", "ov-fig-sum-speed",
                "ov-fig-sum-entryspd", "ov-fig-sum-entryalt",
                "ov-fig-sum-solar", "ov-fig-sum-rank"):
        assert summary.select_one(f"#{fid}") is not None, f"missing {fid}"


def test_point_evidence_explain_preserved(soup):
    """The Overview and the per-round views keep the Point-Evidence-Explain
    structure (RPT-003/004): a Point lead-in plus Evidence/what-to-do follow-up."""
    ov = soup.select_one("#view-overview").get_text(" ", strip=True)
    assert "Point." in ov and "What to do." in ov
    # Every round carries an explicit Point + Evidence PEE block.
    for n in range(1, 18):
        txt = soup.select_one(f"#view-round-{n}").get_text(" ", strip=True)
        assert "Point." in txt and "Evidence." in txt, f"round {n} missing PEE"


def test_every_figure_has_a_nonempty_caption(soup):
    """Every <figure> anywhere in the report has a non-empty <figcaption>."""
    figures = soup.find_all("figure")
    assert figures, "no figures rendered at all"
    for fig in figures:
        cap = fig.find("figcaption")
        assert cap is not None and cap.get_text(strip=True)
