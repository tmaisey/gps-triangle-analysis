"""DOC-001: the repo README is a taster of the project, not an exhaustive dump.

Checks presence, the agreed sections, embedded visuals that exist on disk, a
link to the deliverable, and the same language constraints the report obeys
(no emojis, no flagged lexical tics).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

REQUIRED_HEADINGS = [
    "The Premise",
    "Key Insights",
    "What Was Built",
    "Design",
    "Recommendations",
    "How It Was Made",
    "Project Structure",
]

LEXICAL_TICS = [
    r"\bgenuinely\b", r"\bhonest(ly)?\b", r"\bsit with\b", r"\bdelve\b",
    r"\bcrucial\b", r"it's worth noting", r"\bin essence\b",
    r"that's not \w+, it's", r"\bgame-changer\b", r"\bseamless(ly)?\b",
]

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF]")


@pytest.fixture(scope="module")
def text() -> str:
    """Return the README text; the file must exist (DOC-001)."""
    assert README.exists(), "README.md is missing"
    return README.read_text(encoding="utf-8")


def test_readme_has_the_agreed_sections(text: str) -> None:
    """DOC-001: objective, visual story, what was built, insights, design, recommendations."""
    headings = re.findall(r"^##+ (.+)$", text, flags=re.M)
    missing = [h for h in REQUIRED_HEADINGS
               if not any(h.lower() in x.lower() for x in headings)]
    assert not missing, f"missing sections: {missing}"


def test_readme_embeds_visuals_that_exist(text: str) -> None:
    """DOC-001: representative visuals are embedded and the files are committed."""
    srcs = re.findall(r'<img[^>]+src="([^"]+)"', text) + \
        re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    assert len(srcs) >= 6, f"expected at least 6 embedded visuals, found {len(srcs)}"
    missing = [s for s in srcs if not (ROOT / s).exists()]
    assert not missing, f"embedded images missing on disk: {missing}"


def test_readme_links_to_the_deliverable_and_the_source(text: str) -> None:
    """The reader can reach the report file and the rcmodelspot source data."""
    assert "report/gps-triangle-world-masters-oschatz-2026.html" in text
    assert "rcmodelspot.com" in text
    assert "htmlpreview.github.io" in text, "a click-to-view link for the report"


def test_readme_is_a_taster_not_a_dump(text: str) -> None:
    """Fairly thorough but bounded: a few hundred lines, not the PRD reprinted."""
    lines = text.count("\n")
    assert 120 <= lines <= 420, f"README is {lines} lines"
    assert "## 7. Findings" not in text


def test_readme_language_constraints(text: str) -> None:
    """Same rules as the report: no emojis, no flagged lexical tics."""
    assert not EMOJI.search(text), "emoji found in README"
    hits = [p for p in LEXICAL_TICS if re.search(p, text, flags=re.I)]
    assert not hits, f"lexical tics present: {hits}"


def test_readme_does_not_promise_the_descoped_methodology_page(text: str) -> None:
    """RPT-010 was descoped; the README must not advertise a Methodology page."""
    assert not re.search(r"Methodology page", text, flags=re.I)
