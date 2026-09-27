"""Assemble the single-file HTML report.

Composes the top nav, the four client-side pages, the Analysis view dropdown
(Overview + 17 rounds), a small vanilla-JS app (page routing, mobile burger,
collapsible toggles, expand/collapse-all, anchor + back-to-top) and the
embedded per-round track dataset into ONE self-contained HTML string, then
writes it to ``report/bill_oschatz_2026.html``.

The only remote resource is the Google Fonts ``<link>`` (ADR-001): there are no
remote ``<script src>`` or ``<img src>`` references.

Build command:
    uv run python -m scripts.build.assemble
"""

from __future__ import annotations

from pathlib import Path

from . import components as C
from .data import REPO_ROOT, build_context, embed_round_data_json
from .pages import home, innovations, overview, recommendations, rounds

OUTPUT_PATH = REPO_ROOT / "report" / "bill_oschatz_2026.html"


def _analysis_page(ctx: dict) -> str:
    """Build the Analysis page: the Overview/Rounds dropdown plus all views.

    The dropdown carries 18 options: Overview (default) then Round 1..17 with
    date-time labels. Selecting an option swaps the visible ``.view``.
    """
    labels = ctx["round_labels"]
    options = ['<option value="overview">Overview</option>']
    for entry in ctx["index"]:
        n = entry["round"]
        tag = " (speed)" if entry["task_type"] == "speedrun" else ""
        options.append(
            f'<option value="round-{n}">Round {n} - '
            f'{C.esc(labels.get(n, ""))}{tag}</option>'
        )
    picker = (
        '<div class="view-picker">'
        '<label for="view-select" class="label">View: </label>'
        '<select id="view-select" onchange="showView(this.value)">'
        + "".join(options)
        + "</select></div>"
    )
    views = overview.render(ctx) + rounds.render(ctx)
    return "<h1>Performance Analysis</h1>" + picker + views


def build_html() -> str:
    """Build and return the complete single-file HTML document string.

    Returns:
        str: the full ``<!doctype html>`` document.
    """
    ctx = build_context()
    pages = {
        "home": home.render(ctx),
        "analysis": _analysis_page(ctx),
        "recommendations": recommendations.render(ctx),
        "innovations": innovations.render(ctx),
    }
    body_pages = "".join(C.page_wrap(pid, html) for pid, html in pages.items())
    data_blob = embed_round_data_json()
    doc = (
        "<!doctype html><html lang=\"en\">"
        + C.head()
        + "<body>"
        + C.topnav()
        + f'<main class="page-wrap">{body_pages}</main>'
        + '<script type="application/json" id="round-data">'
        + data_blob
        + "</script>"
        + f"<script>{_app_js()}</script>"
        + "</body></html>"
    )
    return doc


def _app_js() -> str:
    """Return the inlined vanilla-JS app (routing + interactions)."""
    return r"""
(function () {
  'use strict';
  function qa(sel, root) { return Array.prototype.slice.call((root||document).querySelectorAll(sel)); }

  window.showPage = function (id) {
    qa('.page').forEach(function (p) { p.classList.toggle('active', p.id === 'page-' + id); });
    qa('.topnav-links a').forEach(function (a) {
      a.classList.toggle('active', a.getAttribute('data-nav') === id);
    });
    var links = document.getElementById('topnav-links');
    if (links) links.classList.remove('open');
    window.scrollTo(0, 0);
  };

  window.showView = function (v) {
    qa('.view').forEach(function (el) {
      el.classList.toggle('active', el.id === 'view-' + v);
    });
    var sel = document.getElementById('view-select');
    if (sel && sel.value !== v) sel.value = v;
    window.scrollTo(0, 0);
  };

  window.toggleBurger = function () {
    var links = document.getElementById('topnav-links');
    if (links) links.classList.toggle('open');
  };

  window.toggleSection = function (headEl) {
    var sec = headEl.closest('.section');
    if (sec) sec.classList.toggle('collapsed');
  };

  window.expandSection = function (id) {
    var sec = document.getElementById(id);
    if (sec && sec.classList.contains('section')) sec.classList.remove('collapsed');
  };

  function currentScope() {
    var view = qa('.page.active .view.active')[0];
    return view || qa('.page.active')[0] || document;
  }
  window.expandAll = function () {
    qa('.section', currentScope()).forEach(function (s) { s.classList.remove('collapsed'); });
  };
  window.collapseAll = function () {
    qa('.section', currentScope()).forEach(function (s) { s.classList.add('collapsed'); });
  };

  // Reveal an anchor target: expand its enclosing collapsible (and itself if
  // it is one), then bring it into view. Reuses expandSection for the section
  // case so the collapse/expand logic lives in one place.
  function scrollToAnchor(id) {
    var el = document.getElementById(id);
    if (!el) return;
    var sec = el.closest ? el.closest('.section') : null;
    if (sec) sec.classList.remove('collapsed');
    expandSection(id);
    try { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    catch (e) { el.scrollIntoView(); }
  }
  window.scrollToAnchor = scrollToAnchor;

  // One delegated handler for cross-page (.xref) links and in-page hash links.
  // An xref switches page (and, on Analysis, the owning view) before scrolling;
  // an in-page link just reveals and scrolls to its target. Back-to-top links
  // call event.stopPropagation() in markup, so they keep their native jump.
  document.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('a.xref, a[href^="#"]') : null;
    if (!a) return;
    var isXref = a.classList.contains('xref');
    var anchor = isXref
      ? a.getAttribute('data-anchor')
      : (a.getAttribute('href') || '').slice(1);
    if (!anchor) return;
    e.preventDefault();
    if (isXref) {
      var page = a.getAttribute('data-page');
      if (page) showPage(page);
    }
    var target = document.getElementById(anchor);
    if (target && target.closest) {
      var view = target.closest('.view');
      if (view && view.id) showView(view.id.replace('view-', ''));
    }
    requestAnimationFrame(function () { scrollToAnchor(anchor); });
  });

  // Parse embedded round data once, expose for Stage 2 chart hydration if needed.
  try {
    var raw = document.getElementById('round-data');
    window.ROUND_DATA = raw ? JSON.parse(raw.textContent) : [];
  } catch (e) { window.ROUND_DATA = []; }

  // Default page: Home.
  showPage('home');
  showView('overview');
})();
"""


def main() -> Path:
    """Build the report and write it to :data:`OUTPUT_PATH`.

    Returns:
        Path: the written file path.
    """
    html = build_html()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({len(html):,} bytes)")
    return OUTPUT_PATH


if __name__ == "__main__":
    main()
