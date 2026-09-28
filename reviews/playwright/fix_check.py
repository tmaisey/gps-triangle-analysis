"""Playwright verification for the build-review chart/accessibility fixes.

Re-checks, at 1440 and 390 px, the items the visual review raised for the
chart/design layer: mobile chart legibility and the scroll container being
inert on desktop (item 10), tick clipping (11), the progression legend (12),
section-control overlap (13), the ground-track legend (14), one chart width
(15), and keyboard operation of the nav and the collapsibles (9). Also
re-confirms zero horizontal overflow and zero console errors.

Read-only with respect to the report. Screenshots go to
``reviews/playwright/screenshots/fixcheck/``; measurements are printed and
written to ``reviews/playwright/fix_check.json``.

Run with:
    uv run python reviews/playwright/fix_check.py
"""

from __future__ import annotations

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT = ROOT / "report" / "gps-triangle-world-masters-oschatz-2026.html"
SHOTS = pathlib.Path(__file__).resolve().parent / "screenshots" / "fixcheck"
RESULTS = pathlib.Path(__file__).resolve().parent / "fix_check.json"

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}

# The smallest label size a chart may render at, in CSS px.
MIN_EFFECTIVE_FONT_PX = 7.0


def measure_charts(page) -> dict:
    """Return per-chart geometry: rendered width, scale and effective font px.

    Args:
        page: the Playwright page, already on the view being measured.

    Returns:
        dict: summary statistics over every visible chart on the active view.
    """
    return page.evaluate(
        """() => {
          const out = [];
          document.querySelectorAll('.view.active .fig-scroll > svg,'
            + ' .page.active .fig-scroll > svg').forEach(svg => {
            const box = svg.getBoundingClientRect();
            if (!box.width) return;
            const vb = svg.viewBox.baseVal.width || box.width;
            const scale = box.width / vb;
            let minFont = Infinity;
            svg.querySelectorAll('[font-size]').forEach(t => {
              const v = parseFloat(t.getAttribute('font-size'));
              if (!isNaN(v)) minFont = Math.min(minFont, v);
            });
            const holder = svg.parentElement;
            out.push({
              label: svg.getAttribute('aria-label'),
              renderedW: Math.round(box.width),
              viewBoxW: vb,
              scale: +scale.toFixed(3),
              minFontPx: isFinite(minFont) ? +(minFont * scale).toFixed(2) : null,
              holderScrolls: holder.scrollWidth > holder.clientWidth + 1,
              holderOverflowX: getComputedStyle(holder).overflowX,
            });
          });
          return out;
        }"""
    )


def section_head_overlap(page) -> list:
    """Return section headers whose heading and controls share screen space."""
    return page.evaluate(
        """() => {
          const bad = [];
          document.querySelectorAll('.page.active .view.active .section-head,'
            + ' .page.active > .section .section-head').forEach(h => {
            const head = h.querySelector('h2, h3');
            const ctrl = h.querySelector('span');
            if (!head || !ctrl) return;
            const a = head.getBoundingClientRect();
            const b = ctrl.getBoundingClientRect();
            const overlap = !(b.left > a.right || b.right < a.left
              || b.top >= a.bottom || b.bottom <= a.top);
            if (overlap) bad.push({heading: head.textContent.trim().slice(0, 40),
                                   headBox: [a.left, a.right, a.top, a.bottom],
                                   ctrlBox: [b.left, b.right, b.top, b.bottom]});
          });
          return bad;
        }"""
    )


def overflow(page) -> dict:
    """Return the document's horizontal overflow measurement."""
    return page.evaluate(
        """() => ({scrollWidth: document.documentElement.scrollWidth,
                   clientWidth: document.documentElement.clientWidth})"""
    )


def run() -> dict:
    """Drive the report at both widths and collect the fix-check measurements."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    results: dict = {"console_errors": [], "page_errors": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, size in (("desktop", DESKTOP), ("mobile", MOBILE)):
            ctx = browser.new_context(viewport=size)
            page = ctx.new_page()
            page.on("console", lambda m: m.type == "error"
                    and results["console_errors"].append(m.text))
            page.on("pageerror", lambda e: results["page_errors"].append(str(e)))
            page.goto(REPORT.as_uri())
            page.wait_for_timeout(400)

            entry: dict = {}
            if name == "mobile":          # links live behind the burger
                page.click("button.burger")
                page.wait_for_timeout(150)
                entry["burger_aria"] = page.get_attribute("button.burger",
                                                          "aria-expanded")
            page.click('.topnav-links a[data-nav="analysis"]')
            page.wait_for_timeout(250)
            entry["hash_after_nav"] = page.evaluate("() => location.hash")
            entry["overview_charts"] = measure_charts(page)
            entry["overview_overflow"] = overflow(page)
            page.screenshot(path=str(SHOTS / f"overview-{name}.png"),
                            full_page=True)
            # Close-ups of the figures the review flagged for clipping and
            # collisions, so the fixes can be eyeballed directly.
            for fid in ("ov-fig-progression", "ov-fig-field", "ov-fig-gap",
                        "ov-fig-ceiling", "ov-fig-deficit"):
                el = page.query_selector(f"#{fid}")
                if el:
                    el.scroll_into_view_if_needed()
                    el.screenshot(path=str(SHOTS / f"{fid}-{name}.png"))

            page.select_option("#view-select", "round-12")
            page.wait_for_timeout(250)
            entry["round12_charts"] = measure_charts(page)
            entry["round12_overflow"] = overflow(page)
            entry["round12_head_overlap"] = section_head_overlap(page)
            page.screenshot(path=str(SHOTS / f"round12-{name}.png"),
                            full_page=True)

            # Keyboard: focus the first section head and toggle it with Enter.
            entry["keyboard"] = page.evaluate(
                """() => {
                  const head = document.querySelector(
                    '.page.active .view.active .section-head');
                  head.focus();
                  const focused = document.activeElement === head;
                  head.dispatchEvent(new KeyboardEvent('keydown',
                    {key: 'Enter', bubbles: true}));
                  const sec = head.closest('.section');
                  const collapsed = sec.classList.contains('collapsed');
                  const aria = head.getAttribute('aria-expanded');
                  head.dispatchEvent(new KeyboardEvent('keydown',
                    {key: 'Enter', bubbles: true}));
                  return {focusable: focused, collapsedAfterEnter: collapsed,
                          ariaAfterEnter: aria,
                          restored: !sec.classList.contains('collapsed'),
                          ariaRestored: head.getAttribute('aria-expanded')};
                }"""
            )
            entry["nav_hrefs"] = page.eval_on_selector_all(
                ".topnav-links a", "els => els.map(e => e.getAttribute('href'))")

            # A cross-page link still routes (and does not jump via its href).
            page.select_option("#view-select", "overview")
            page.wait_for_timeout(200)
            page.click('.view.active a.xref[data-page="recommendations"]')
            page.wait_for_timeout(350)
            entry["xref"] = page.evaluate(
                """() => ({activePage: document.querySelector('.page.active').id,
                           hash: location.hash,
                           targetVisible: !!document.querySelector(
                             '.page.active #rec-cruise')})"""
            )
            results[name] = entry
            ctx.close()
        browser.close()
    return results


def summarise(results: dict) -> int:
    """Print a pass/fail summary and return a process exit code."""
    failures = []
    for width in ("desktop", "mobile"):
        entry = results[width]
        charts = entry["overview_charts"] + entry["round12_charts"]
        widths = {c["viewBoxW"] for c in charts}
        fonts = [c["minFontPx"] for c in charts if c["minFontPx"]]
        scrolls = {c["holderOverflowX"] for c in charts}
        print(f"\n== {width} ==")
        print(f"  charts measured      : {len(charts)}")
        print(f"  distinct viewBox w   : {sorted(widths)}")
        print(f"  rendered widths      : {sorted({c['renderedW'] for c in charts})}")
        print(f"  min effective font px: {min(fonts):.2f}" if fonts else "  no fonts")
        print(f"  holder overflow-x    : {sorted(scrolls)}")
        print(f"  head overlaps (R12)  : {len(entry['round12_head_overlap'])}")
        print(f"  keyboard             : {entry['keyboard']}")
        for key in ("overview_overflow", "round12_overflow"):
            box = entry[key]
            if box["scrollWidth"] > box["clientWidth"]:
                failures.append(f"{width}: horizontal overflow on {key}")
        if len(widths) != 1:
            failures.append(f"{width}: charts not one width: {sorted(widths)}")
        if entry["round12_head_overlap"]:
            failures.append(f"{width}: section head controls overlap heading")
        if fonts and min(fonts) < MIN_EFFECTIVE_FONT_PX:
            failures.append(f"{width}: chart label at {min(fonts)} px")
        kb = entry["keyboard"]
        if not (kb["focusable"] and kb["collapsedAfterEnter"] and kb["restored"]
                and kb["ariaAfterEnter"] == "false"
                and kb["ariaRestored"] == "true"):
            failures.append(f"{width}: keyboard toggle broken")
        if any(h is None or not h.startswith("#") for h in entry["nav_hrefs"]):
            failures.append(f"{width}: nav links missing href")
        xref = entry["xref"]
        print(f"  xref routing         : {xref}")
        if (xref["activePage"] != "page-recommendations" or xref["hash"]
                or not xref["targetVisible"]):
            failures.append(f"{width}: xref routing changed: {xref}")
    if results["console_errors"]:
        failures.append(f"console errors: {results['console_errors'][:3]}")
    if results["page_errors"]:
        failures.append(f"page errors: {results['page_errors'][:3]}")
    desktop_scroll = {c["holderOverflowX"]
                      for c in results["desktop"]["overview_charts"]}
    if desktop_scroll - {"visible"}:
        failures.append(f"scroll container active on desktop: {desktop_scroll}")
    print("\nconsole errors:", len(results["console_errors"]),
          "| page errors:", len(results["page_errors"]))
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  -", f)
        return 1
    print("\nAll fix checks passed.")
    return 0


if __name__ == "__main__":
    data = run()
    RESULTS.write_text(json.dumps(data, indent=2))
    sys.exit(summarise(data))
