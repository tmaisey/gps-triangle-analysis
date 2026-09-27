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


def test_every_figure_has_a_nonempty_caption(soup):
    """Every <figure> anywhere in the report has a non-empty <figcaption>."""
    figures = soup.find_all("figure")
    assert figures, "no figures rendered at all"
    for fig in figures:
        cap = fig.find("figcaption")
        assert cap is not None and cap.get_text(strip=True)
