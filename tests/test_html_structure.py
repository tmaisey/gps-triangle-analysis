"""Structural tests for the generated HTML shell (RPT-001/002, DSN-001).

Build the report, parse it with BeautifulSoup, and assert the load-bearing
shell contract: the four nav links, the title, Home as the default page, the
Analysis 18-option dropdown, the expand/collapse controls, a white background,
no emoji, no brand string, and no remote script/image (Google-Fonts link only).

These should PASS once the shell exists (they test structure, not content).
"""

from __future__ import annotations

import re

import pytest
from bs4 import BeautifulSoup

from scripts.build import assemble

# Broad emoji ranges (pictographs, symbols, dingbats, flags, misc).
EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F"
    "\U00002300-\U000023FF"
    "]"
)

NAV_LABELS = ["Home", "Analysis", "Recommendations", "Innovations"]


@pytest.fixture(scope="module")
def html():
    """The full generated HTML document string."""
    return assemble.build_html()


@pytest.fixture(scope="module")
def soup(html):
    """Parsed document."""
    return BeautifulSoup(html, "html.parser")


def test_exactly_four_topnav_links(soup):
    """The top nav carries exactly the four expected page links."""
    links = soup.select(".topnav-links a")
    assert [a.get_text(strip=True) for a in links] == NAV_LABELS


def test_title_text_present(soup):
    """The report title text appears in the nav bar."""
    assert "Bill's GPS Triangle Analysis 2026" in soup.select_one(
        ".topnav-title").get_text()


def test_home_is_default_page(soup):
    """Home is the page marked active-by-default in the markup, and the app
    JS calls showPage('home') on load."""
    # Structural default: the routing JS defaults to Home.
    assert "showPage('home')" in soup.find_all("script")[-1].get_text()
    # The Home page container exists.
    assert soup.select_one("#page-home") is not None


def test_analysis_dropdown_has_18_options(soup):
    """The Analysis view select offers Overview + 17 rounds = 18 options."""
    select = soup.select_one("#view-select")
    assert select is not None
    options = select.find_all("option")
    assert len(options) == 18
    assert options[0]["value"] == "overview"


def test_expand_and_collapse_controls_exist(soup):
    """Both an Expand all and a Collapse all control are present."""
    text = soup.get_text()
    assert "Expand all" in text
    assert "Collapse all" in text


def test_no_emoji_anywhere(html):
    """No emoji characters appear anywhere in the rendered document."""
    found = EMOJI_RE.findall(html)
    assert not found, f"emoji found: {found[:10]}"


def test_no_brand_string(html):
    """The word 'deloitte' never appears (case-insensitive)."""
    assert "deloitte" not in html.lower()


def test_background_is_white(html):
    """The CSS sets a white page background."""
    assert "--bg: #FFFFFF" in html
    assert "background: var(--bg)" in html


def test_no_remote_script_or_image(soup):
    """No remote <script src> or remote <img src>; only a Google-Fonts link."""
    for s in soup.find_all("script"):
        assert not s.get("src"), "unexpected remote <script src>"
    for img in soup.find_all("img"):
        src = img.get("src", "")
        assert src.startswith("data:"), f"remote <img src>: {src}"
    # The only remote stylesheet link allowed is Google Fonts.
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        assert "fonts.googleapis.com" in href, f"non-fonts remote link: {href}"


def test_all_figures_have_captions(soup):
    """Every <figure> present in the shell already has a <figcaption>."""
    figures = soup.find_all("figure")
    for fig in figures:
        cap = fig.find("figcaption")
        assert cap is not None and cap.get_text(strip=True), "empty figcaption"
