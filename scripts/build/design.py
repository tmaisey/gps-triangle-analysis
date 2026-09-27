"""Design tokens and CSS for the single-file GPS Triangle report.

This module is the single source of truth for the palette, typography and the
inlined stylesheet. The palette follows the restrained, elegant look agreed in
the PRD (DSN-001): white background, green primary for Bill, a cool teal-blue
for the same-air benchmark, warm amber for attention/loss, neutral greys for
field/other. There are deliberately NO coloured accent bars/stripes and NO
gradient hero blocks (ADR/DSN no-AI-tell rules), and no brand names anywhere.

Stage 2 composes pages using these tokens; charts.py themes every figure from
``PALETTE`` so the whole report reads as one system.
"""

from __future__ import annotations

# --- Palette tokens (exact values mandated by the brief / PRD §8) -----------
PALETTE: dict[str, str] = {
    # surfaces / text
    "background": "#FFFFFF",   # page background (white, hard rule)
    "ink": "#101820",          # primary text
    "text_secondary": "#53565A",
    "muted": "#75787B",
    "hairline": "#E4E4DF",     # borders / thin rules
    # series / semantic
    "primary": "#86BC25",      # Bill (green)
    "primary_dark": "#046A38", # dark green accent for emphasis
    "leader": "#00A3E0",       # same-air leader / benchmark (teal-blue)
    "leader_light": "#62B5E5",
    "attention": "#ED8B00",    # loss / attention (amber)
    "field": "#D0D0CE",        # field / other pilots (neutral)
}

# Convenience aliases used across charts (chart series convention).
SERIES = {
    "bill": PALETTE["primary"],
    "leader": PALETTE["leader"],
    "field": PALETTE["field"],
    "loss": PALETTE["attention"],
}

# --- Typography -------------------------------------------------------------
# Headings: serif display "Spectral" (Georgia fallback).
# Body/UI: "Source Sans 3" (system-ui fallback). Numbers use tabular-nums.
FONT_HEADING = '"Spectral", Georgia, "Times New Roman", serif'
FONT_BODY = (
    '"Source Sans 3", system-ui, -apple-system, "Segoe UI", '
    "Roboto, Helvetica, Arial, sans-serif"
)

# The single allowed remote resource: Google Fonts stylesheet.
GOOGLE_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" '
    'href="https://fonts.googleapis.com/css2?'
    "family=Spectral:ital,wght@0,400;0,500;0,600;1,400&"
    'family=Source+Sans+3:wght@400;500;600;700&display=swap">'
)

# Layout constants.
MAX_WIDTH_PX = 1040
SIDE_GUTTER_PX = 16
MOBILE_BREAKPOINT_PX = 720


def css() -> str:
    """Return the full inlined stylesheet as a string.

    The CSS is token-driven (see :data:`PALETTE`) and enforces the hard design
    rules: white background, no accent bars, no gradients, responsive layout
    capped at ~1040px with 16px side gutters and no horizontal scroll at phone
    width.

    Returns:
        str: A complete CSS stylesheet (no surrounding ``<style>`` tags).
    """
    p = PALETTE
    return f"""
:root {{
  --bg: {p['background']};
  --ink: {p['ink']};
  --text-2: {p['text_secondary']};
  --muted: {p['muted']};
  --hairline: {p['hairline']};
  --primary: {p['primary']};
  --primary-dark: {p['primary_dark']};
  --leader: {p['leader']};
  --leader-light: {p['leader_light']};
  --attention: {p['attention']};
  --field: {p['field']};
  --font-heading: {FONT_HEADING};
  --font-body: {FONT_BODY};
  --maxw: {MAX_WIDTH_PX}px;
  --gutter: {SIDE_GUTTER_PX}px;
}}

* {{ box-sizing: border-box; }}

html, body {{
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-body);
  font-size: 17px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}}

body {{ background: var(--bg); }}

h1, h2, h3, h4 {{
  font-family: var(--font-heading);
  font-weight: 600;
  color: var(--ink);
  line-height: 1.2;
  margin: 0 0 0.5em;
}}
h1 {{ font-size: 2.1rem; }}
h2 {{ font-size: 1.55rem; margin-top: 1.6em; }}
h3 {{ font-size: 1.2rem; margin-top: 1.3em; }}

p {{ margin: 0 0 1em; color: var(--ink); }}
a {{ color: var(--primary-dark); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.num {{ font-variant-numeric: tabular-nums; }}

/* ---- Top navigation bar ------------------------------------------------ */
.topnav {{
  position: sticky;
  top: 0;
  z-index: 50;
  background: var(--bg);
  border-bottom: 1px solid var(--hairline);
}}
.topnav-inner {{
  max-width: var(--maxw);
  margin: 0 auto;
  padding: 0 var(--gutter);
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.topnav-title {{
  font-family: var(--font-heading);
  font-weight: 600;
  font-size: 1.15rem;
  color: var(--ink);
  white-space: nowrap;
}}
.topnav-links {{
  display: flex;
  gap: 1.5rem;
  align-items: center;
}}
.topnav-links a {{
  color: var(--text-2);
  font-weight: 500;
  font-size: 0.98rem;
  cursor: pointer;
}}
.topnav-links a.active {{ color: var(--ink); }}
.burger {{
  display: none;
  background: none;
  border: 1px solid var(--hairline);
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 1.1rem;
  line-height: 1;
  color: var(--ink);
}}

/* ---- Page wrapper ------------------------------------------------------ */
.page-wrap {{
  max-width: var(--maxw);
  margin: 0 auto;
  padding: 2rem var(--gutter) 5rem;
}}
.page {{ display: none; }}
.page.active {{ display: block; }}

/* ---- Summary block ----------------------------------------------------- */
.summary {{
  border: 1px solid var(--hairline);
  border-radius: 8px;
  padding: 1.25rem 1.4rem;
  margin: 1.5rem 0 2rem;
  background: var(--bg);
}}
.summary ul {{ margin: 0.6rem 0 0; padding-left: 1.2rem; }}
.summary li {{ margin: 0.3rem 0; }}

/* ---- Collapsible sections --------------------------------------------- */
.section {{
  border-top: 1px solid var(--hairline);
  padding: 0.4rem 0 0.6rem;
}}
.section-head {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  cursor: pointer;
  gap: 1rem;
}}
.section-head h2, .section-head h3 {{ margin: 0.7em 0; }}
.section-toggle {{
  color: var(--muted);
  font-size: 0.85rem;
  font-weight: 500;
  white-space: nowrap;
}}
.back-to-top {{
  font-size: 0.8rem;
  color: var(--muted);
  margin-left: 0.75rem;
}}
.section-body {{ overflow: hidden; }}
.section.collapsed .section-body {{ display: none; }}

.controls {{
  display: flex;
  gap: 1rem;
  margin: 1rem 0;
  font-size: 0.9rem;
}}
.controls button {{
  background: none;
  border: 1px solid var(--hairline);
  border-radius: 6px;
  padding: 5px 12px;
  cursor: pointer;
  color: var(--text-2);
  font-family: var(--font-body);
  font-size: 0.9rem;
}}
.controls button:hover {{ border-color: var(--muted); }}

/* ---- Figures ----------------------------------------------------------- */
figure {{ margin: 1.4rem 0; }}
figure svg {{ max-width: 100%; height: auto; display: block; }}
figcaption {{
  color: var(--text-2);
  font-size: 0.88rem;
  margin-top: 0.5rem;
  line-height: 1.45;
}}

/* ---- Stat tiles / KPI row (NO accent bars) ---------------------------- */
.kpi-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin: 1.5rem 0;
}}
.stat-tile {{
  flex: 1 1 140px;
  border: 1px solid var(--hairline);
  border-radius: 8px;
  padding: 1rem 1.1rem;
}}
.stat-tile .value {{
  font-family: var(--font-heading);
  font-size: 1.7rem;
  font-weight: 600;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}}
.stat-tile .label {{
  font-size: 0.82rem;
  color: var(--muted);
  margin-top: 0.25rem;
}}
.stat-tile .sub {{ font-size: 0.85rem; color: var(--text-2); margin-top: 0.35rem; }}

/* ---- Analysis dropdown ------------------------------------------------- */
.view-picker {{ margin: 1rem 0 1.5rem; }}
.view-picker select {{
  font-family: var(--font-body);
  font-size: 1rem;
  padding: 8px 12px;
  border: 1px solid var(--hairline);
  border-radius: 6px;
  background: var(--bg);
  color: var(--ink);
  max-width: 100%;
}}
.view {{ display: none; }}
.view.active {{ display: block; }}

/* ---- Home section links ------------------------------------------------ */
.home-links {{ list-style: none; padding: 0; margin: 2rem 0; }}
.home-links li {{ border-top: 1px solid var(--hairline); }}
.home-links li:last-child {{ border-bottom: 1px solid var(--hairline); }}
.home-links a {{
  display: block;
  padding: 1.1rem 0;
  font-family: var(--font-heading);
  font-size: 1.35rem;
  color: var(--ink);
}}

/* ---- Responsive -------------------------------------------------------- */
@media (max-width: {MOBILE_BREAKPOINT_PX}px) {{
  body {{ font-size: 16px; }}
  h1 {{ font-size: 1.7rem; }}
  .burger {{ display: inline-block; }}
  .topnav-links {{
    display: none;
    position: absolute;
    top: 60px;
    right: 0;
    left: 0;
    flex-direction: column;
    gap: 0;
    background: var(--bg);
    border-bottom: 1px solid var(--hairline);
    padding: 0.5rem var(--gutter);
  }}
  .topnav-links.open {{ display: flex; }}
  .topnav-links a {{ padding: 0.7rem 0; }}
  .topnav-title {{ font-size: 1rem; white-space: normal; }}
}}
"""
