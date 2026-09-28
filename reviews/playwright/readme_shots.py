"""Capture the README's screenshots from the built report into docs/images/.

Deterministic set of page-level and figure-level crops at desktop and mobile
widths. Re-run after a rebuild so the README visuals never drift from the
deliverable.

Usage:
    uv run python reviews/playwright/readme_shots.py
"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "report" / "gps-triangle-world-masters-oschatz-2026.html"
OUT = ROOT / "docs" / "images"

#: (output name, analysis view or None, figure id or None, viewport width)
SHOTS = [
    ("home-desktop", None, None, 1280),
    ("overview-top-desktop", "overview", None, 1280),
    ("analysis-mobile", "overview", None, 390),
    ("gap-breakdown", "overview", "ov-fig-gap", 1280),
    ("clean-lap-deficit", "overview", "ov-fig-deficit", 1280),
    ("progression", "overview", "ov-fig-progression", 1280),
    ("conditions", "overview", "ov-fig-conditions", 1280),
    ("trajectory-density", "overview", "ov-fig-trajectory", 1280),
    ("turn-radius", "overview", "ov-fig-turn-radius", 1280),
    ("round12-dashboard", "round-12", "r12-fig-dashboard", 1280),
    ("round12-energy", "round-12", "r12-fig-energy", 1280),
    ("round12-track", "round-12", "r12-fig-track", 1280),
    ("recommendations-desktop", "page:recommendations", None, 1280),
    ("innovations-desktop", "page:innovations", None, 1280),
]


def _open(page: Page, view: str | None) -> None:
    """Navigate the single-file app to the requested page/view."""
    page.goto(REPORT.as_uri())
    if view is None:
        return
    if view.startswith("page:"):
        page.evaluate(
            f"document.querySelector('[data-page=\"{view[5:]}\"]')?.click()")
    else:
        page.evaluate("document.querySelector('[data-page=\"analysis\"]')?.click()")
        page.select_option("select", view)
    page.wait_for_timeout(300)


def main() -> None:
    """Render every shot in SHOTS into docs/images/<name>.png."""
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, view, fig, width in SHOTS:
            page = browser.new_page(viewport={"width": width, "height": 900},
                                    device_scale_factor=2)
            _open(page, view)
            out = OUT / f"{name}.png"
            if fig:
                el = page.locator(f"#{fig}")
                el.scroll_into_view_if_needed()
                el.screenshot(path=str(out))
            else:
                page.screenshot(path=str(out), full_page=False)
            page.close()
            print(out.relative_to(ROOT))
        browser.close()


if __name__ == "__main__":
    main()
