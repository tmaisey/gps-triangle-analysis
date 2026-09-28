"""Assemble the single-file HTML report.

Composes the top nav, the four client-side pages, the Analysis view dropdown
(Overview + 17 rounds), a small vanilla-JS app (page routing, mobile burger,
collapsible toggles, expand/collapse-all, anchor + back-to-top) and the
embedded per-round track dataset into ONE self-contained HTML string, then
writes it to ``report/gps-triangle-world-masters-oschatz-2026.html`` (RPT-017).

The file is fully self-contained (RPT-019): fonts are inlined as base64 woff2
@font-face and there are no remote ``<link>``, ``<script src>`` or ``<img src>``
references.

Build command:
    uv run python -m scripts.build.assemble
"""

from __future__ import annotations

import re
from pathlib import Path

from . import components as C
from .data import REPO_ROOT, build_context, embed_round_data_json
from .pages import home, innovations, overview, recommendations, rounds

OUTPUT_PATH = REPO_ROOT / "report" / "gps-triangle-world-masters-oschatz-2026.html"

# Cross-page links are emitted by the page modules as
# ``<a class="xref" ... data-anchor="x">``. They are given a real ``href`` here,
# in one place, so every one of them is in the tab order and degrades to a plain
# in-page link; the delegated click handler still intercepts them.
_XREF_TAG_RE = re.compile(r'<a class="xref"(?P<attrs>[^>]*)>')
_ANCHOR_ATTR_RE = re.compile(r'data-anchor="(?P<anchor>[^"]*)"')

# The no-JS fallback notice. Home is already ``.page active`` in the markup.
NOSCRIPT_NOTE = (
    '<noscript><p class="noscript-note">This report is interactive and needs '
    "JavaScript to switch between the Home, Analysis, Recommendations and "
    "Innovations pages and to open and close sections. The Home page is shown "
    "below; open the file in a browser with JavaScript enabled for the rest."
    "</p></noscript>"
)


def _add_xref_hrefs(doc: str) -> str:
    """Give every ``a.xref`` a real ``href`` matching its ``data-anchor``.

    Keeps the cross-page link markup in one place: the page modules declare the
    destination as ``data-page``/``data-anchor`` and this pass derives the
    keyboard-reachable ``href="#<anchor>"`` from it. Links that already carry an
    ``href``, or that have no ``data-anchor``, are left untouched, so the pass
    is idempotent.

    Args:
        doc: the assembled HTML document.

    Returns:
        str: the document with hrefs added to cross-page links.
    """
    def repl(match: re.Match) -> str:
        attrs = match.group("attrs")
        if "href=" in attrs:
            return match.group(0)
        anchor = _ANCHOR_ATTR_RE.search(attrs)
        if not anchor:
            return match.group(0)
        return f'<a class="xref" href="#{anchor.group("anchor")}"{attrs}>'

    return _XREF_TAG_RE.sub(repl, doc)


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
    # Overview sections sit directly under the page <h1>, so they stay <h2>.
    # Each round view emits its own <h2> round title, so the sections inside it
    # are one level deeper.
    views = overview.render(ctx)
    with C.heading_level(3):
        views += rounds.render(ctx)
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
    body_pages = "".join(
        C.page_wrap(pid, html, active=(pid == "home"))
        for pid, html in pages.items()
    )
    data_blob = embed_round_data_json()
    doc = (
        "<!doctype html><html lang=\"en\">"
        + C.head()
        + "<body>"
        + C.topnav()
        + NOSCRIPT_NOTE
        + f'<main class="page-wrap">{body_pages}</main>'
        + '<script type="application/json" id="round-data">'
        + data_blob
        + "</script>"
        + f"<script>{_app_js()}</script>"
        + "</body></html>"
    )
    return _add_xref_hrefs(doc)


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

  window.toggleBurger = function (btn) {
    var links = document.getElementById('topnav-links');
    if (!links) return;
    var open = links.classList.toggle('open');
    var b = btn || document.querySelector('.burger');
    if (b) b.setAttribute('aria-expanded', open ? 'true' : 'false');
  };

  // Keep a section's control label and ARIA state in sync (RPT-014):
  // 'Expand' when collapsed, 'Collapse' when expanded.
  function syncLabel(sec) {
    if (!sec) return;
    var collapsed = sec.classList.contains('collapsed');
    var t = sec.querySelector('.section-toggle');
    if (t) t.textContent = collapsed ? 'Expand' : 'Collapse';
    var head = sec.querySelector('.section-head');
    if (head) head.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  }

  window.toggleSection = function (headEl) {
    var sec = headEl.closest('.section');
    if (sec) { sec.classList.toggle('collapsed'); syncLabel(sec); }
  };

  // Collapsible heads are role="button" with tabindex=0: Enter and Space
  // activate them. Only when the head itself has focus, so the back-to-top
  // link inside it keeps its native behaviour.
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ' && e.key !== 'Spacebar') return;
    var head = e.target && e.target.classList
      && e.target.classList.contains('section-head') ? e.target : null;
    if (!head) return;
    e.preventDefault();
    toggleSection(head);
  });

  window.expandSection = function (id) {
    var sec = document.getElementById(id);
    if (sec && sec.classList.contains('section')) {
      sec.classList.remove('collapsed'); syncLabel(sec);
    }
  };

  function currentScope() {
    var view = qa('.page.active .view.active')[0];
    return view || qa('.page.active')[0] || document;
  }
  window.expandAll = function () {
    qa('.section', currentScope()).forEach(function (s) {
      s.classList.remove('collapsed'); syncLabel(s);
    });
  };
  window.collapseAll = function () {
    qa('.section', currentScope()).forEach(function (s) {
      s.classList.add('collapsed'); syncLabel(s);
    });
  };

  // Reveal an anchor target: expand its enclosing collapsible (and itself if
  // it is one), then bring it into view. Reuses expandSection for the section
  // case so the collapse/expand logic lives in one place.
  function scrollToAnchor(id) {
    var el = document.getElementById(id);
    if (!el) return;
    var sec = el.closest ? el.closest('.section') : null;
    if (sec) { sec.classList.remove('collapsed'); syncLabel(sec); }
    expandSection(id);
    try { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    catch (e) { el.scrollIntoView(); }
  }
  window.scrollToAnchor = scrollToAnchor;

  // One delegated handler for top-nav links, cross-page (.xref) links and
  // in-page hash links. Nav links carry href="#page-x" for the tab order, so
  // they are routed (not scrolled) and the default jump is suppressed. An xref
  // switches page (and, on Analysis, the owning view) before scrolling; an
  // in-page link just reveals and scrolls to its target. Back-to-top links
  // call event.stopPropagation() in markup, so they keep their native jump.
  document.addEventListener('click', function (e) {
    var nav = e.target.closest ? e.target.closest('.topnav-links a[data-nav]') : null;
    if (nav) {
      e.preventDefault();
      showPage(nav.getAttribute('data-nav'));
      return;
    }
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
