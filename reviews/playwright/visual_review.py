"""Playwright visual/UI review driver for the GPS Triangle single-file report.

Renders report/gps-triangle-world-masters-oschatz-2026.html at desktop and
mobile widths, screenshots every page and every Analysis view, and asserts a
set of visual/structural checks (charts visible, no horizontal overflow, nav
and burger behaviour, collapsibles, cross-page links, self-containment).

Read-only with respect to the report: it never modifies the HTML. Outputs
screenshots to reviews/playwright/screenshots/ and a JSON result blob to
reviews/playwright/results.json.

Run with:
    uv run python reviews/playwright/visual_review.py
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT = ROOT / "report" / "gps-triangle-world-masters-oschatz-2026.html"
SHOTS = pathlib.Path(__file__).resolve().parent / "screenshots"
RESULTS = pathlib.Path(__file__).resolve().parent / "results.json"

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}

PAGES = ["home", "analysis", "recommendations", "innovations"]
VIEWS = ["overview"] + [f"round-{i}" for i in range(1, 18)]
MOBILE_ROUND_SAMPLE = ["round-1", "round-4", "round-9", "round-12"]

# Collected diagnostics shared across the run.
console_errors: list[str] = []
page_errors: list[str] = []
external_requests: list[str] = []


def shot(page, name: str) -> str:
    """Take a full-page screenshot and return its repo-relative path.

    Args:
        page: The Playwright page to capture.
        name: Screenshot base name (no extension).

    Returns:
        Path of the written PNG, relative to the repo root.
    """
    out = SHOTS / f"{name}.png"
    page.screenshot(path=str(out), full_page=True)
    return str(out.relative_to(ROOT))


def overflow_report(page) -> dict[str, Any]:
    """Measure horizontal overflow and list offending elements.

    Args:
        page: The Playwright page to measure.

    Returns:
        Dict with scrollWidth, clientWidth and up to 10 offender descriptors.
    """
    return page.evaluate(
        """() => {
      const de = document.documentElement;
      const vw = de.clientWidth;
      const offenders = [];
      if (de.scrollWidth > vw + 1) {
        document.querySelectorAll('.page.active *').forEach(el => {
          const r = el.getBoundingClientRect();
          if (r.width === 0 && r.height === 0) return;
          if (r.right > vw + 1 || r.left < -1) {
            offenders.push({
              tag: el.tagName.toLowerCase(),
              cls: (el.className && el.className.baseVal !== undefined
                     ? el.className.baseVal : el.className || '').toString().slice(0, 80),
              id: el.id || '',
              left: Math.round(r.left), right: Math.round(r.right),
              w: Math.round(r.width)
            });
          }
        });
      }
      return {scrollWidth: de.scrollWidth, clientWidth: vw,
              offenders: offenders.slice(0, 10), offenderCount: offenders.length};
    }"""
    )


def svg_report(page) -> dict[str, Any]:
    """Audit SVGs in the active page/view: visibility, size, overflow, text collisions.

    Args:
        page: The Playwright page to audit.

    Returns:
        Dict with counts and lists of problem SVGs.
    """
    return page.evaluate(
        """() => {
      const scope = document.querySelector('.page.active .view.active')
                 || document.querySelector('.page.active');
      if (!scope) return {count: 0, zeroBox: [], hidden: [], overflow: [], textCollisions: []};
      const svgs = Array.from(scope.querySelectorAll('svg'));
      const zeroBox = [], hidden = [], overflow = [], textCollisions = [];
      svgs.forEach((svg, i) => {
        const r = svg.getBoundingClientRect();
        const cs = getComputedStyle(svg);
        const label = (svg.id || svg.getAttribute('aria-label') || ('svg#' + i));
        if (r.width < 1 || r.height < 1) zeroBox.push({label, w: r.width, h: r.height});
        if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0')
          hidden.push({label});
        const parent = svg.parentElement;
        if (parent) {
          const pr = parent.getBoundingClientRect();
          if (r.right > pr.right + 2 || r.left < pr.left - 2)
            overflow.push({label, svgRight: Math.round(r.right), parentRight: Math.round(pr.right),
                           parentCls: (parent.className||'').toString().slice(0,60)});
        }
        // Text collision heuristic: pairwise bbox intersection of <text> nodes.
        const texts = Array.from(svg.querySelectorAll('text')).filter(t => (t.textContent||'').trim());
        const boxes = texts.map(t => {
          const b = t.getBoundingClientRect();
          return {t: (t.textContent||'').trim().slice(0, 24), x: b.left, y: b.top,
                  r: b.right, b: b.bottom, w: b.width, h: b.height};
        }).filter(b => b.w > 0 && b.h > 0);
        for (let a = 0; a < boxes.length; a++) {
          for (let c = a + 1; c < boxes.length; c++) {
            const A = boxes[a], B = boxes[c];
            const ox = Math.min(A.r, B.r) - Math.max(A.x, B.x);
            const oy = Math.min(A.b, B.b) - Math.max(A.y, B.y);
            if (ox > 1.5 && oy > 1.5) {
              const area = ox * oy;
              const minArea = Math.min(A.w * A.h, B.w * B.h);
              if (area / minArea > 0.18) {
                textCollisions.push({label, a: A.t, b: B.t,
                                     overlapPct: Math.round(100 * area / minArea)});
              }
            }
          }
        }
      });
      return {count: svgs.length, zeroBox, hidden, overflow,
              textCollisions: textCollisions.slice(0, 12),
              textCollisionCount: textCollisions.length};
    }"""
    )


def section_report(page) -> dict[str, Any]:
    """Report collapsible-section state and toggle labels in the active scope."""
    return page.evaluate(
        """() => {
      const scope = document.querySelector('.page.active .view.active')
                 || document.querySelector('.page.active');
      if (!scope) return {total: 0};
      const secs = Array.from(scope.querySelectorAll('.section'));
      return {
        total: secs.length,
        collapsed: secs.filter(s => s.classList.contains('collapsed')).length,
        labels: Array.from(new Set(secs.map(s => {
          const t = s.querySelector('.section-toggle');
          return t ? t.textContent.trim() : '(none)';
        }))),
        hasExpandAll: !!scope.querySelector('[onclick*="expandAll"]'),
        hasCollapseAll: !!scope.querySelector('[onclick*="collapseAll"]'),
        summaryPresent: !!scope.querySelector('.summary, .view-summary, .page-summary'),
        anchorBullets: scope.querySelectorAll('a[href^="#"]').length
      };
    }"""
    )


def setup(context) -> None:
    """Wire console/error/network listeners onto a browser context."""

    def on_route(route, request):
        url = request.url
        if url.startswith("file://") or url.startswith("data:") or url.startswith("about:"):
            route.continue_()
        else:
            external_requests.append(url)
            route.abort()

    context.route("**/*", on_route)


def run_width(pw, label: str, viewport: dict, results: dict) -> None:
    """Run the full check sweep at one viewport width."""
    browser = pw.chromium.launch()
    context = browser.new_context(viewport=viewport, device_scale_factor=1)
    setup(context)
    page = context.new_page()
    page.on("console", lambda m: console_errors.append(f"[{label}] {m.type}: {m.text}")
            if m.type == "error" else None)
    page.on("pageerror", lambda e: page_errors.append(f"[{label}] {e}"))
    page.goto(REPORT.as_uri())
    page.wait_for_timeout(600)

    w = viewport["width"]
    res: dict[str, Any] = {}

    # --- Top-level pages -------------------------------------------------
    for pid in PAGES:
        if label == "mobile":
            # Links live behind the burger: open it, verify, then click through.
            page.evaluate("() => document.getElementById('topnav-links').classList.remove('open')")
            burger_vis = page.evaluate(
                """() => {
                  const b = document.querySelector('.burger');
                  const links = document.getElementById('topnav-links');
                  const br = b.getBoundingClientRect();
                  const lr = links.getBoundingClientRect();
                  return {burgerVisible: br.width > 0 && br.height > 0,
                          linksVisibleClosed: lr.height > 0 && getComputedStyle(links).display !== 'none'};
                }"""
            )
            res.setdefault("burger", burger_vis)
            page.click(".burger")
            page.wait_for_timeout(200)
            if pid == PAGES[0]:
                res["burger_open_shot"] = shot(page, f"nav-burger-open-{w}")
                res["burger_open_state"] = page.evaluate(
                    """() => {
                      const links = document.getElementById('topnav-links');
                      const r = links.getBoundingClientRect();
                      return {open: links.classList.contains('open'), h: Math.round(r.height),
                              linkCount: links.querySelectorAll('a').length};
                    }"""
                )
        page.click(f".topnav-links a[data-nav='{pid}']")
        page.wait_for_timeout(350)
        active = page.evaluate("() => (document.querySelector('.page.active')||{}).id")
        entry = {
            "activePage": active,
            "shot": shot(page, f"{pid}-page-{w}"),
            "overflow": overflow_report(page),
            "svg": svg_report(page),
            "sections": section_report(page),
        }
        res[f"page:{pid}"] = entry

    # --- Methodology presence -------------------------------------------
    res["methodology"] = page.evaluate(
        """() => {
      const navLink = document.querySelector('.topnav-links a[data-nav="methodology"]');
      const pageEl = document.getElementById('page-methodology');
      const anyText = document.body.innerText.toLowerCase().includes('methodology');
      return {navLink: !!navLink, pageEl: !!pageEl, mentionedInText: anyText};
    }"""
    )

    # --- Analysis views --------------------------------------------------
    page.evaluate("() => showPage('analysis')")
    page.wait_for_timeout(200)
    views = VIEWS if label == "desktop" else ["overview"] + MOBILE_ROUND_SAMPLE
    view_res: dict[str, Any] = {}
    for v in views:
        page.select_option("#view-select", v)
        page.wait_for_timeout(350)
        active_view = page.evaluate("() => (document.querySelector('.page.active .view.active')||{}).id")
        entry = {
            "activeView": active_view,
            "swapOk": active_view == f"view-{v}",
            "shot": shot(page, f"analysis-{v}-{w}"),
            "overflow": overflow_report(page),
            "svg": svg_report(page),
            "sections": section_report(page),
        }
        view_res[v] = entry
    res["views"] = view_res

    # --- Anchor bullet jump + back-to-top (desktop only, overview) -------
    if label == "desktop":
        page.select_option("#view-select", "overview")
        page.wait_for_timeout(300)
        res["anchor_test"] = page.evaluate(
            """() => {
          const scope = document.querySelector('.page.active .view.active');
          const links = Array.from(scope.querySelectorAll('a[href^="#"]'))
            .filter(a => !/top/i.test(a.textContent||''));
          const probe = links.slice(0, 5).map(a => {
            const id = a.getAttribute('href').slice(1);
            return {text: (a.textContent||'').trim().slice(0,40), id, targetExists: !!document.getElementById(id)};
          });
          const backToTop = Array.from(scope.querySelectorAll('a')).filter(a =>
            /top/i.test((a.textContent||'')) || /top/i.test(a.getAttribute('href')||''));
          return {bulletLinks: links.length, probe, backToTopCount: backToTop.length};
        }"""
        )
        # Actually click one anchor bullet and confirm it scrolls + reveals.
        clicked = page.evaluate(
            """() => {
          const scope = document.querySelector('.page.active .view.active');
          const a = Array.from(scope.querySelectorAll('a[href^="#"]'))
            .filter(x => !/top/i.test(x.textContent||''))[0];
          if (!a) return null;
          const id = a.getAttribute('href').slice(1);
          a.click();
          return id;
        }"""
        )
        page.wait_for_timeout(900)
        if clicked:
            res["anchor_click"] = page.evaluate(
                f"""() => {{
              const el = document.getElementById({json.dumps(clicked)});
              if (!el) return {{ok: false}};
              const r = el.getBoundingClientRect();
              return {{ok: true, id: {json.dumps(clicked)}, top: Math.round(r.top),
                       inViewport: r.top > -80 && r.top < innerHeight,
                       scrollY: Math.round(window.scrollY)}};
            }}"""
            )
            res["anchor_click_shot"] = shot(page, f"analysis-anchor-jump-{w}")

        # Back-to-top link behaviour.
        res["back_to_top"] = page.evaluate(
            """() => {
          const scope = document.querySelector('.page.active .view.active');
          const a = Array.from(scope.querySelectorAll('a')).find(x =>
            /top/i.test((x.textContent||'')));
          if (!a) return {found: false};
          const href = a.getAttribute('href') || '';
          const id = href.replace('#','');
          return {found: true, text: (a.textContent||'').trim(), href,
                  targetExists: !!document.getElementById(id)};
        }"""
        )

    # --- Collapsibles ----------------------------------------------------
    page.evaluate("() => { showPage('analysis'); showView('overview'); }")
    page.wait_for_timeout(250)
    before = section_report(page)
    page.evaluate("() => collapseAll()")
    page.wait_for_timeout(300)
    collapsed = section_report(page)
    res["collapse_all_shot"] = shot(page, f"analysis-collapsed-{w}")
    page.evaluate("() => expandAll()")
    page.wait_for_timeout(300)
    expanded = section_report(page)
    # Individual toggle round trip.
    toggle = page.evaluate(
        """() => {
      const scope = document.querySelector('.page.active .view.active');
      const head = scope.querySelector('.section .section-head, .section h2, .section header');
      const sec = scope.querySelector('.section');
      if (!sec) return {ok: false};
      const t = sec.querySelector('.section-toggle');
      const start = {collapsed: sec.classList.contains('collapsed'), label: t ? t.textContent.trim() : null};
      toggleSection(t || head || sec.firstElementChild);
      const mid = {collapsed: sec.classList.contains('collapsed'), label: t ? t.textContent.trim() : null};
      toggleSection(t || head || sec.firstElementChild);
      const end = {collapsed: sec.classList.contains('collapsed'), label: t ? t.textContent.trim() : null};
      return {ok: true, start, mid, end};
    }"""
    )
    res["collapsibles"] = {"defaultState": before, "afterCollapseAll": collapsed,
                           "afterExpandAll": expanded, "individualToggle": toggle}

    # --- Cross-page links ------------------------------------------------
    xrefs = page.evaluate(
        """() => Array.from(document.querySelectorAll('a.xref')).map((a, i) => ({
             i, page: a.getAttribute('data-page'), anchor: a.getAttribute('data-anchor'),
             text: (a.textContent||'').trim().slice(0, 50),
             ownerPage: (a.closest('.page')||{}).id,
             ownerView: (a.closest('.view')||{}).id,
             targetExists: !!document.getElementById(a.getAttribute('data-anchor'))
           }))"""
    )
    res["xrefs_total"] = len(xrefs)
    res["xrefs_missing_target"] = [x for x in xrefs if not x["targetExists"]]

    # Click a sample: analysis->recommendations, recommendations->innovations.
    sample = []
    for want_owner, want_page in (("page-analysis", "recommendations"),
                                  ("page-recommendations", "innovations"),
                                  ("page-home", "analysis")):
        cand = next((x for x in xrefs if x["ownerPage"] == want_owner and x["page"] == want_page), None)
        if cand:
            sample.append(cand)
    click_res = []
    for c in sample:
        owner = c["ownerPage"].replace("page-", "")
        page.evaluate(f"() => showPage({json.dumps(owner)})")
        if c["ownerView"]:
            page.evaluate(f"() => showView({json.dumps(c['ownerView'].replace('view-', ''))})")
        page.wait_for_timeout(250)
        page.evaluate(
            """(idx) => {
              const a = document.querySelectorAll('a.xref')[idx];
              a.scrollIntoView({block:'center'});
              a.click();
            }""",
            c["i"],
        )
        page.wait_for_timeout(1000)
        out = page.evaluate(
            f"""() => {{
          const el = document.getElementById({json.dumps(c['anchor'])});
          const r = el ? el.getBoundingClientRect() : null;
          const cs = el ? getComputedStyle(el) : null;
          return {{activePage: (document.querySelector('.page.active')||{{}}).id,
                   targetExists: !!el,
                   visible: !!r && r.height > 0 && cs.display !== 'none',
                   top: r ? Math.round(r.top) : null,
                   inViewport: !!r && r.top > -120 && r.top < innerHeight}};
        }}"""
        )
        out.update({"from": c["ownerPage"], "toPage": c["page"], "anchor": c["anchor"],
                    "linkText": c["text"],
                    "pageOk": out["activePage"] == "page-" + c["page"]})
        click_res.append(out)
        if c == sample[0]:
            res["xref_landing_shot"] = shot(page, f"xref-analysis-to-recs-{w}")
    res["xref_clicks"] = click_res

    # --- Design spot-check numbers ---------------------------------------
    page.evaluate("() => showPage('home')")
    page.wait_for_timeout(200)
    res["design"] = page.evaluate(
        """() => {
      const cs = getComputedStyle(document.body);
      const fonts = {body: cs.fontFamily};
      const h = document.querySelector('h1, h2');
      const hs = h ? getComputedStyle(h) : null;
      const loaded = document.fonts ? Array.from(document.fonts).map(f => f.family + ' ' + f.weight + ' ' + f.status) : [];
      return {bodyBg: cs.backgroundColor, bodyColor: cs.color, fonts,
              headingFont: hs ? hs.fontFamily : null,
              fontFaces: Array.from(new Set(loaded)).slice(0, 12),
              fontsReady: document.fonts ? document.fonts.status : 'n/a'};
    }"""
    )

    results[label] = res
    context.close()
    browser.close()


def main() -> int:
    """Execute the review sweep at both widths and dump results JSON."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    if not REPORT.exists():
        print(f"Report not found: {REPORT}", file=sys.stderr)
        return 1
    results: dict[str, Any] = {}
    with sync_playwright() as pw:
        run_width(pw, "desktop", DESKTOP, results)
        run_width(pw, "mobile", MOBILE, results)
    results["console_errors"] = console_errors
    results["page_errors"] = page_errors
    results["external_requests"] = sorted(set(external_requests))
    RESULTS.write_text(json.dumps(results, indent=2))
    print(f"console errors: {len(console_errors)}, page errors: {len(page_errors)}, "
          f"external requests: {len(set(external_requests))}")
    print(f"results -> {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
