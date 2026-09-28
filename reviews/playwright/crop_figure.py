"""Screenshot one figure of the built report by its figure id, at a given width.

Usage:
    uv run python reviews/playwright/crop_figure.py <fig_id> <width> <out.png> [view]

``view`` is an Analysis dropdown value such as ``round-12`` (default: overview).
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "report" / "gps-triangle-world-masters-oschatz-2026.html"


def main() -> None:
    """Render the report, switch to the requested view, and crop the figure."""
    fig_id, width, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    view = sys.argv[4] if len(sys.argv) > 4 else None
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": width, "height": 900})
        page.goto(REPORT.as_uri())
        page.evaluate("document.querySelector('[data-page=\"analysis\"]')?.click()")
        if view:
            page.select_option("select", view)
        page.wait_for_timeout(300)
        el = page.locator(f"#{fig_id}")
        el.scroll_into_view_if_needed()
        el.screenshot(path=out)
        b.close()
    print(out)


if __name__ == "__main__":
    main()
