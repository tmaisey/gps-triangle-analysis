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

from scripts.build import assemble, links

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
    """The report title reads the same in the nav bar, <title> and the Home h1.

    RPT-017 names all three surfaces explicitly, so all three are asserted.
    """
    assert "GPS Triangle World Masters, Oschatz 2026" in soup.select_one(
        ".topnav-title").get_text()
    assert soup.select_one("title").get_text(strip=True) == \
        "GPS Triangle World Masters, Oschatz 2026"
    h1 = soup.select_one("#page-home h1")
    assert h1 is not None and h1.get_text(strip=True) == \
        "GPS Triangle World Masters, Oschatz 2026"


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


def test_fully_self_contained_no_remote_resources(soup, html):
    """No remote <script src>, remote <img src> or remote stylesheet/font link:
    the report is a single self-contained file (RPT-019). Fonts are inlined as
    base64 woff2 @font-face, so the Google-Fonts network dependency is gone."""
    for s in soup.find_all("script"):
        assert not s.get("src"), "unexpected remote <script src>"
    for img in soup.find_all("img"):
        src = img.get("src", "")
        assert src.startswith("data:"), f"remote <img src>: {src}"
    # No remote stylesheet links at all (fonts are inlined, not linked).
    for link in soup.find_all("link", rel="stylesheet"):
        assert False, f"unexpected remote stylesheet link: {link.get('href')}"
    assert "fonts.googleapis.com" not in html, "remote Google-Fonts link remains"
    assert "fonts.gstatic.com" not in html, "remote gstatic font remains"
    assert "data:font/woff2;base64," in html, "fonts not inlined as data URIs"


def test_all_figures_have_captions(soup):
    """Every <figure> present in the shell already has a <figcaption>."""
    figures = soup.find_all("figure")
    for fig in figures:
        cap = fig.find("figcaption")
        assert cap is not None and cap.get_text(strip=True), "empty figcaption"


def test_xref_anchors_all_resolve(soup):
    """Every cross-page ``.xref`` link points at a real page and a real
    on-page element id (no dangling data-page/data-anchor)."""
    page_ids = {"home", "analysis", "recommendations", "innovations"}
    ids = {el["id"] for el in soup.select("[id]")}
    xrefs = soup.select("a.xref")
    assert xrefs, "no xref links found at all"
    for a in xrefs:
        page = a.get("data-page")
        anchor = a.get("data-anchor")
        assert page in page_ids, f"xref to unknown page: {page}"
        assert anchor in ids, f"dangling xref anchor: {anchor}"


def test_xref_and_anchor_handler_wired(html):
    """The app JS wires a global click handler for ``.xref`` links and an
    anchor-scroller that expands collapsed targets (RPT-005/006/007)."""
    assert "scrollToAnchor" in html
    assert "addEventListener('click'" in html
    assert ".xref" in html


def test_no_old_title_and_legality_wording(html):
    """The retitle (RPT-017) and label rename (RPT-015) hold across the whole
    document: the old title and 'Legality gate' are gone; the nav title and the
    'Legality Consideration' wording are present."""
    assert "Bill's GPS Triangle Analysis 2026" not in html
    assert "Legality gate" not in html and "Legality Gate" not in html
    assert "GPS Triangle World Masters, Oschatz 2026" in html
    assert "Legality Consideration" in html


#: Prose phrases that are regulations references and must therefore be
#: hyperlinked to gps-triangle.net (RPT-016). Adjectival compounds
#: ("rules-legal"), the class name in the event subtitle ("Sport class") and
#: in-SVG chart furniture ("Regs limit / Other pilots") are deliberately out of
#: scope - they are not citations.
REGS_PHRASES = [
    r"section 2\.7",
    r"Sport-class regulations",
    r"Sport-class rules",
]


@pytest.mark.parametrize("phrase", REGS_PHRASES)
def test_regs_references_are_linked(html, phrase):
    """Every regs reference in prose sits inside a gps-triangle.net link.

    RPT-016 requires section-specific mentions to point at the Sport-class regs
    PDF and general mentions at the regulations index; both live on
    gps-triangle.net. A bare, unlinked regs reference fails here.
    """
    found = list(re.finditer(phrase, html))
    assert found, f"regs phrase never appears: {phrase}"
    # Assertions compare short extracts, never the whole 2.8 MB document: a
    # failing membership test on a megabyte string makes pytest's assertion
    # explainer crawl.
    unlinked = []
    for m in found:
        start = html.rfind("<a ", 0, m.start())
        end = html.find("</a>", m.start())
        if start == -1 or end == -1:
            unlinked.append(html[max(0, m.start() - 60):m.end() + 20])
            continue
        href = re.search(r'href="([^"]+)"', html[start:end])
        if not href or "gps-triangle.net" not in href.group(1):
            unlinked.append(html[start:start + 100])
    assert not unlinked, f"{phrase} not linked to gps-triangle.net: {unlinked}"


def test_external_links_are_allowlisted(soup):
    """Every external href is a URL from the verified allowlist (RPT-008).

    The spec's own test step is "every external link resolves". Resolution is
    checked by hand when a constant is added to :mod:`scripts.build.links`; this
    test holds the build to that allowlist so no unverified URL can ship. It
    performs no network access.
    """
    external = {a["href"] for a in soup.select("a[href]")
                if a["href"].startswith("http")}
    assert external, "no external grounding links at all"
    unknown = external - links.ALLOWED_EXTERNAL_URLS
    assert not unknown, f"external links outside the verified allowlist: {unknown}"


def test_no_dead_legacy_regs_urls(html):
    """The two 404 WordPress-style gps-triangle.net paths never reappear."""
    dead = [p for p in ("gps-triangle/regulations-documents", "wp-content/uploads")
            if p in html]
    assert not dead, f"dead regs URL fragments still emitted: {dead}"


#: Short words that stay lower-case mid-title under the report's heading
#: convention (the one the h2s already follow, e.g. "Cumulative Laps vs
#: Leader", "What to Train from This Round").
SMALL_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
    "nor", "of", "on", "or", "per", "the", "to", "up", "via", "vs", "with",
}


def _title_case_offenders(title: str) -> list[str]:
    """Return the words in ``title`` that break the heading-case convention.

    A small word is allowed a capital only when it opens the title or follows a
    colon (the start of a subtitle).

    Args:
        title: the heading or lead-in title text, without its trailing stop.

    Returns:
        list[str]: offending words, empty when the title is conventional.
    """
    words = title.split()
    bad = []
    for i, word in enumerate(words):
        if i == 0 or words[i - 1].endswith(":"):
            continue
        if word.lower() in SMALL_WORDS and word != word.lower():
            bad.append(word)
    return bad


def test_headings_and_lead_ins_share_one_title_case_convention(soup):
    """Headings and insight lead-in titles follow the same Title-Case rule.

    The ``<h1>``/``<h2>`` titles already lower-case articles, short
    prepositions and "vs" mid-title; the insight lead-ins must match, so the
    document does not carry two competing conventions (DSN-001 tone).
    """
    titles = [h.get_text(" ", strip=True) for h in soup.select("h1, h2")]
    titles += [s.get_text(" ", strip=True).rstrip(".")
               for s in soup.select("p.pee-point > strong")]
    assert titles, "no titles found"
    offenders = {t: _title_case_offenders(t) for t in titles
                 if _title_case_offenders(t)}
    assert not offenders, f"title-case offenders: {offenders}"


def test_no_css_gradients(html):
    """No gradient hero / gradient fills anywhere (DSN-001 no-AI-tell)."""
    assert "linear-gradient" not in html
    assert "radial-gradient" not in html


def test_no_banned_lexical_tics(html):
    """None of the flagged lexical tics appear (RPT-003 tone rule); 'real-time'
    is explicitly allowed, but a standalone 'real' as a filler is not."""
    banned = [
        r"\bhonest(ly)?\b",
        r"\bgenuine(ly)?\b",
        r"sit with",
        r"that'?s not\b.{1,40}?\bit'?s\b",
        r"that is not\b.{1,40}?\bit is\b",
    ]
    for pat in banned:
        hits = re.findall(pat, html, re.I)
        assert not hits, f"banned tic {pat!r}: {hits[:5]}"
    # 'real' is only permitted inside 'real-time'.
    real_words = re.findall(r"\breal\b", html, re.I)
    realtime = re.findall(r"real-time", html, re.I)
    assert len(real_words) == len(realtime), \
        "standalone 'real' filler present (only 'real-time' allowed)"


def test_captions_render_source_links_not_escaped(html):
    """Figure source links render as real anchors, never as escaped literal
    ``<a>`` markup inside a <figcaption> (RPT-008 grounding)."""
    caps = re.findall(r"<figcaption>(.*?)</figcaption>", html, re.S)
    assert caps, "no figcaptions rendered"
    escaped = [c for c in caps if "&lt;a" in c]
    assert not escaped, f"{len(escaped)} figcaptions contain escaped <a> markup"
    assert any("<a href=" in c for c in caps), "no figcaption carries a source link"
