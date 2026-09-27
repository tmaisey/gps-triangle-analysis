"""Bespoke inline-SVG chart generators for the report.

Every function returns a self-contained ``<svg>`` string themed from
:data:`design.PALETTE` (no external chart library — ADR-005). Charts carry an
accessible ``<title>`` (and ``role="img"`` + ``aria-label``) and degrade
gracefully on empty or degenerate input, returning a small placeholder SVG
rather than raising.

Coordinate convention: SVG y grows downward, so all y-scales invert. Helpers
map data space -> pixel space; series colours follow the chart convention
(Bill = green, same-air leader = teal-blue, field = neutral, loss = amber).

Track rows (from ``data.load_round``) are ``[t_s, lat, lon, alt_m, vario_ms,
gs_kmh]``; column indices are in :mod:`data` (TRACK_T, TRACK_ALT, ...).
"""

from __future__ import annotations

import html
import math
from typing import Sequence

from .design import PALETTE, SERIES

# Default drawing box. Charts scale to 100% width via CSS; the viewBox keeps
# the aspect ratio. Callers may override width/height.
_W, _H = 720, 380
_PAD = {"l": 56, "r": 24, "t": 34, "b": 46}


# --- Primitives -------------------------------------------------------------
def _esc(text: str) -> str:
    """Escape text for safe inclusion in SVG markup."""
    return html.escape(str(text), quote=True)


def _svg_open(w: int, h: int, title: str, desc: str = "") -> str:
    """Open an accessible SVG element with a title (and optional description)."""
    t = _esc(title)
    d = f"<desc>{_esc(desc)}</desc>" if desc else ""
    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="{t}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="inherit">'
        f"<title>{t}</title>{d}"
    )


def _placeholder(title: str, msg: str = "No data available") -> str:
    """Return a small, neutral placeholder SVG for empty/degenerate input."""
    w, h = 480, 140
    return (
        _svg_open(w, h, title, msg)
        + f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>'
        + f'<text x="{w/2}" y="{h/2}" text-anchor="middle" '
        f'dominant-baseline="middle" fill="{PALETTE["muted"]}" '
        f'font-size="14">{_esc(msg)}</text></svg>'
    )


def _scaler(dmin: float, dmax: float, pmin: float, pmax: float):
    """Return a function mapping a data value to a pixel coordinate.

    Falls back to the midpoint when the data range is degenerate (dmin==dmax).
    """
    span = dmax - dmin
    if span == 0:
        mid = (pmin + pmax) / 2
        return lambda v: mid
    return lambda v: pmin + (v - dmin) / span * (pmax - pmin)


def _nice_ticks(dmin: float, dmax: float, n: int = 5) -> list[float]:
    """Return ~n readable tick values spanning [dmin, dmax]."""
    if dmin == dmax:
        return [dmin]
    raw = (dmax - dmin) / n
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for mult in (1, 2, 2.5, 5, 10):
        step = mult * mag
        if raw <= step:
            break
    start = math.floor(dmin / step) * step
    ticks = []
    v = start
    while v <= dmax + step * 0.5:
        if v >= dmin - step * 0.5:
            ticks.append(round(v, 6))
        v += step
    return ticks


def _axes(w, h, xlabel, ylabel, xticks, yticks, xs, ys) -> str:
    """Render x/y axis lines, gridlines, tick labels and axis titles."""
    pl, pr, pt, pb = _PAD["l"], _PAD["r"], _PAD["t"], _PAD["b"]
    parts = []
    # y gridlines + labels
    for tv in yticks:
        y = ys(tv)
        parts.append(
            f'<line x1="{pl}" y1="{y:.1f}" x2="{w-pr}" y2="{y:.1f}" '
            f'stroke="{PALETTE["hairline"]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pl-8}" y="{y+4:.1f}" text-anchor="end" '
            f'fill="{PALETTE["muted"]}" font-size="11" '
            f'font-variant-numeric="tabular-nums">{_fmt(tv)}</text>'
        )
    # x labels
    for tv in xticks:
        x = xs(tv)
        parts.append(
            f'<text x="{x:.1f}" y="{h-pb+18}" text-anchor="middle" '
            f'fill="{PALETTE["muted"]}" font-size="11" '
            f'font-variant-numeric="tabular-nums">{_fmt(tv)}</text>'
        )
    # axis titles
    if xlabel:
        parts.append(
            f'<text x="{(pl+w-pr)/2:.1f}" y="{h-4}" text-anchor="middle" '
            f'fill="{PALETTE["text_secondary"]}" font-size="12">{_esc(xlabel)}</text>'
        )
    if ylabel:
        cy = (pt + h - pb) / 2
        parts.append(
            f'<text x="14" y="{cy:.1f}" text-anchor="middle" '
            f'fill="{PALETTE["text_secondary"]}" font-size="12" '
            f'transform="rotate(-90 14 {cy:.1f})">{_esc(ylabel)}</text>'
        )
    return "".join(parts)


def _fmt(v: float) -> str:
    """Format a numeric tick compactly."""
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"


def _polyline(points: Sequence[tuple[float, float]], color: str, width=2.0,
              dash: str | None = None) -> str:
    """Render a polyline through pixel-space points."""
    if not points:
        return ""
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<polyline points="{pts}" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linejoin="round" '
        f'stroke-linecap="round"{d}/>'
    )


def _legend(entries: Sequence[tuple[str, str]], w: int, y: int = 16) -> str:
    """Render a right-aligned inline legend of (label, colour) pairs."""
    parts = []
    x = w - _PAD["r"]
    for label, color in reversed(entries):
        label_w = len(label) * 6.6 + 22
        x -= label_w
        parts.append(
            f'<rect x="{x:.1f}" y="{y-8}" width="12" height="4" rx="2" fill="{color}"/>'
            f'<text x="{x+18:.1f}" y="{y-1}" fill="{PALETTE["text_secondary"]}" '
            f'font-size="11.5">{_esc(label)}</text>'
        )
    return "".join(parts)


# --- (a) Altitude / energy vs time ------------------------------------------
def altitude_trace(bill_track, leader_track, *, bill_laps_s=None,
                   leader_laps_s=None, title="Altitude vs time",
                   w=_W, h=_H) -> str:
    """Two-series altitude-vs-time line with lap-crossing markers.

    Args:
        bill_track: list of track rows for Bill ([t, lat, lon, alt, vario, gs]).
        leader_track: list of track rows for the same-air leader.
        bill_laps_s: optional list of Bill's lap-crossing time offsets (s).
        leader_laps_s: optional list of the leader's lap-crossing offsets (s).
        title: accessible chart title.

    Returns:
        str: an inline SVG. Placeholder if both tracks are empty.
    """
    from .data import TRACK_T, TRACK_ALT
    if not bill_track and not leader_track:
        return _placeholder(title)
    pl, pr, pt, pb = _PAD["l"], _PAD["r"], _PAD["t"], _PAD["b"]
    allrows = (bill_track or []) + (leader_track or [])
    tmax = max(r[TRACK_T] for r in allrows)
    amin = min(r[TRACK_ALT] for r in allrows)
    amax = max(r[TRACK_ALT] for r in allrows)
    xs = _scaler(0, tmax, pl, w - pr)
    ys = _scaler(amin, amax, h - pb, pt)
    xt = _nice_ticks(0, tmax / 60.0)  # minutes on axis
    xs_min = _scaler(0, tmax / 60.0, pl, w - pr)
    yt = _nice_ticks(amin, amax)

    def line(track, color):
        return _polyline([(xs(r[TRACK_T]), ys(r[TRACK_ALT])) for r in track], color)

    def markers(laps, track, color):
        if not laps or not track:
            return ""
        out = []
        for ls in laps:
            # nearest alt at that time
            nearest = min(track, key=lambda r: abs(r[TRACK_T] - ls))
            out.append(
                f'<circle cx="{xs(ls):.1f}" cy="{ys(nearest[TRACK_ALT]):.1f}" '
                f'r="2.6" fill="{color}"/>'
            )
        return "".join(out)

    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
        _axes(w, h, "Time (min)", "Altitude (m)", xt, yt, xs_min, ys),
        line(leader_track or [], SERIES["leader"]),
        line(bill_track or [], SERIES["bill"]),
        markers(leader_laps_s, leader_track, SERIES["leader"]),
        markers(bill_laps_s, bill_track, SERIES["bill"]),
        _legend([("Bill", SERIES["bill"]), ("Leader", SERIES["leader"])], w),
        "</svg>",
    ]
    return "".join(body)


# --- (b) Ground-track overlay ----------------------------------------------
def ground_track(bill_track, leader_track, task=None, *,
                 title="Ground track", w=560, h=520) -> str:
    """Lat/lon ground-track overlay for two pilots plus the triangle geometry.

    Projects lat/lon to a local equirectangular metre grid centred on the
    task start, so the triangle and both flown lines share one scale.

    Args:
        bill_track: Bill's track rows.
        leader_track: leader's track rows.
        task: optional task dict (start_lat, start_lon, direction_deg,
            leg_length_m) used to draw the equilateral triangle course.
        title: accessible chart title.

    Returns:
        str: inline SVG; placeholder if no tracks.
    """
    from .data import TRACK_LAT, TRACK_LON
    if not bill_track and not leader_track:
        return _placeholder(title)
    rows = (bill_track or []) + (leader_track or [])
    lat0 = task["start_lat"] if task else sum(r[TRACK_LAT] for r in rows) / len(rows)
    lon0 = task["start_lon"] if task else sum(r[TRACK_LON] for r in rows) / len(rows)
    mlat = 111_320.0
    mlon = 111_320.0 * math.cos(math.radians(lat0))

    def to_xy(lat, lon):
        return (lon - lon0) * mlon, (lat - lat0) * mlat

    pts_bill = [to_xy(r[TRACK_LAT], r[TRACK_LON]) for r in (bill_track or [])]
    pts_lead = [to_xy(r[TRACK_LAT], r[TRACK_LON]) for r in (leader_track or [])]

    tri = _triangle_points(task, to_xy) if task else []
    allpts = pts_bill + pts_lead + tri
    xsv = [p[0] for p in allpts]
    ysv = [p[1] for p in allpts]
    xmin, xmax = min(xsv), max(xsv)
    ymin, ymax = min(ysv), max(ysv)
    # keep square aspect
    pad = 30
    span = max(xmax - xmin, ymax - ymin) or 1
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    xmin, xmax = cx - span / 2, cx + span / 2
    ymin, ymax = cy - span / 2, cy + span / 2
    sx = _scaler(xmin, xmax, pad, w - pad)
    sy = _scaler(ymin, ymax, h - pad, pad)  # invert (north up)

    def path(pts, color, width, dash=None):
        return _polyline([(sx(x), sy(y)) for x, y in pts], color, width, dash)

    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
    ]
    if tri:
        tri_px = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in tri)
        body.append(
            f'<polygon points="{tri_px}" fill="none" '
            f'stroke="{PALETTE["muted"]}" stroke-width="1.4" '
            f'stroke-dasharray="5 4"/>'
        )
    body.append(path(pts_lead, SERIES["leader"], 1.6))
    body.append(path(pts_bill, SERIES["bill"], 1.6))
    # start marker
    body.append(
        f'<circle cx="{sx(0):.1f}" cy="{sy(0):.1f}" r="4" '
        f'fill="{PALETTE["ink"]}"/>'
    )
    body.append(_legend([("Bill", SERIES["bill"]), ("Leader", SERIES["leader"]),
                         ("Course", PALETTE["muted"])], w))
    body.append("</svg>")
    return "".join(body)


def _triangle_points(task, to_xy):
    """Build the three corner points (as local x/y) of the triangle course.

    The API exposes start point + direction + leg length (not turnpoint
    coordinates); the equilateral triangle is reconstructed from that geometry.
    """
    lat0, lon0 = task["start_lat"], task["start_lon"]
    leg = task["leg_length_m"]
    brg = math.radians(task.get("direction_deg", 0.0))
    # start at origin; first leg along direction; internal angle 60 deg
    p0 = (0.0, 0.0)
    p1 = (leg * math.sin(brg), leg * math.cos(brg))
    brg2 = brg + math.radians(120)
    p2 = (p1[0] + leg * math.sin(brg2), p1[1] + leg * math.cos(brg2))
    return [p0, p1, p2]


# --- (c) Cumulative laps step chart ----------------------------------------
def cumulative_laps(bill_laps_s, leader_laps_s, *, working_time_s=1800,
                    title="Cumulative laps", w=_W, h=320) -> str:
    """Two-series cumulative-laps step chart over the working window.

    Args:
        bill_laps_s: list of Bill's lap-completion time offsets (s).
        leader_laps_s: list of the leader's lap-completion offsets (s).
        working_time_s: x-axis extent (default 30-min task = 1800 s).
        title: accessible chart title.

    Returns:
        str: inline SVG; placeholder if both lists are empty.
    """
    if not bill_laps_s and not leader_laps_s:
        return _placeholder(title)
    pl, pr, pt, pb = _PAD["l"], _PAD["r"], _PAD["t"], _PAD["b"]
    tmax = max([working_time_s] + (bill_laps_s or []) + (leader_laps_s or []))
    lapmax = max(len(bill_laps_s or []), len(leader_laps_s or []))
    xs = _scaler(0, tmax / 60.0, pl, w - pr)
    ys = _scaler(0, lapmax, h - pb, pt)

    def step(laps, color):
        if not laps:
            return ""
        pts = [(xs(0), ys(0))]
        for i, t in enumerate(sorted(laps), 1):
            pts.append((xs(t / 60.0), ys(i - 1)))
            pts.append((xs(t / 60.0), ys(i)))
        return _polyline(pts, color, 2.0)

    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
        _axes(w, h, "Time (min)", "Laps", _nice_ticks(0, tmax / 60.0),
              _nice_ticks(0, lapmax), xs, ys),
        step(leader_laps_s or [], SERIES["leader"]),
        step(bill_laps_s or [], SERIES["bill"]),
        _legend([("Bill", SERIES["bill"]), ("Leader", SERIES["leader"])], w),
        "</svg>",
    ]
    return "".join(body)


# --- (d) Grouped / paired bar ----------------------------------------------
def paired_bars(categories, bill_values, leader_values, *,
                title="Bill vs leader", ylabel="", w=_W, h=340,
                bill_label="Bill", leader_label="Leader") -> str:
    """Grouped (paired) bar chart: Bill vs leader across categories.

    Args:
        categories: list of category labels (x groups).
        bill_values: list of Bill's values (same length as categories).
        leader_values: list of the leader's values.
        title: accessible chart title.
        ylabel: y-axis title.

    Returns:
        str: inline SVG; placeholder if no categories.
    """
    if not categories:
        return _placeholder(title)
    pl, pr, pt, pb = _PAD["l"], _PAD["r"], _PAD["t"], _PAD["b"]
    vals = [v for v in (bill_values + leader_values) if v is not None]
    vmax = max(vals + [0])
    vmin = min(vals + [0])
    ys = _scaler(vmin, vmax, h - pb, pt)
    n = len(categories)
    band = (w - pl - pr) / n
    bw = band * 0.32
    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
    ]
    zero = ys(0 if vmin <= 0 <= vmax else vmin)
    for tv in _nice_ticks(vmin, vmax):
        y = ys(tv)
        body.append(
            f'<line x1="{pl}" y1="{y:.1f}" x2="{w-pr}" y2="{y:.1f}" '
            f'stroke="{PALETTE["hairline"]}"/>'
            f'<text x="{pl-8}" y="{y+4:.1f}" text-anchor="end" '
            f'fill="{PALETTE["muted"]}" font-size="11">{_fmt(tv)}</text>'
        )
    for i, cat in enumerate(categories):
        cx = pl + band * (i + 0.5)
        for val, color, off in ((leader_values[i], SERIES["leader"], -bw - 2),
                                 (bill_values[i], SERIES["bill"], 2)):
            if val is None:
                continue
            y = ys(val)
            top, ht = min(y, zero), abs(y - zero)
            body.append(
                f'<rect x="{cx+off:.1f}" y="{top:.1f}" width="{bw:.1f}" '
                f'height="{ht:.1f}" fill="{color}" rx="1.5"/>'
            )
        body.append(
            f'<text x="{cx:.1f}" y="{h-pb+16}" text-anchor="middle" '
            f'fill="{PALETTE["muted"]}" font-size="11">{_esc(cat)}</text>'
        )
    if ylabel:
        cy = (pt + h - pb) / 2
        body.append(
            f'<text x="14" y="{cy:.1f}" text-anchor="middle" '
            f'fill="{PALETTE["text_secondary"]}" font-size="12" '
            f'transform="rotate(-90 14 {cy:.1f})">{_esc(ylabel)}</text>'
        )
    body.append(_legend([(bill_label, SERIES["bill"]),
                         (leader_label, SERIES["leader"])], w))
    body.append("</svg>")
    return "".join(body)


# --- (e) Scatter with highlighted point ------------------------------------
def scatter_highlight(points, *, highlight_index=None, xlabel="", ylabel="",
                      title="Scatter", labels=None, w=_W, h=420) -> str:
    """Scatter plot with one highlighted point (grinder-vs-sprinter).

    Args:
        points: list of (x, y) tuples.
        highlight_index: index of the point to emphasise (Bill), or None.
        xlabel: x-axis title (e.g. 'Avg speed (km/h)').
        ylabel: y-axis title (e.g. 'Laps').
        title: accessible chart title.
        labels: optional list of point labels (drawn near highlighted point).

    Returns:
        str: inline SVG; placeholder if no points.
    """
    pts = [p for p in (points or []) if p and p[0] is not None and p[1] is not None]
    if not pts:
        return _placeholder(title)
    pl, pr, pt, pb = _PAD["l"], _PAD["r"], _PAD["t"], _PAD["b"]
    xsv = [p[0] for p in pts]
    ysv = [p[1] for p in pts]
    xs = _scaler(min(xsv), max(xsv), pl, w - pr)
    ys = _scaler(min(ysv), max(ysv), h - pb, pt)
    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
        _axes(w, h, xlabel, ylabel, _nice_ticks(min(xsv), max(xsv)),
              _nice_ticks(min(ysv), max(ysv)), xs, ys),
    ]
    for i, (x, y) in enumerate(points or []):
        if x is None or y is None:
            continue
        if i == highlight_index:
            continue
        body.append(
            f'<circle cx="{xs(x):.1f}" cy="{ys(y):.1f}" r="4.5" '
            f'fill="{PALETTE["field"]}" stroke="{PALETTE["muted"]}" '
            f'stroke-width="0.6"/>'
        )
    if highlight_index is not None and 0 <= highlight_index < len(points):
        x, y = points[highlight_index]
        if x is not None and y is not None:
            body.append(
                f'<circle cx="{xs(x):.1f}" cy="{ys(y):.1f}" r="6.5" '
                f'fill="{SERIES["bill"]}" stroke="{PALETTE["background"]}" '
                f'stroke-width="1.5"/>'
            )
            lab = (labels[highlight_index] if labels
                   and highlight_index < len(labels) else "Bill")
            body.append(
                f'<text x="{xs(x)+10:.1f}" y="{ys(y)-8:.1f}" '
                f'fill="{PALETTE["primary_dark"]}" font-size="12" '
                f'font-weight="600">{_esc(lab)}</text>'
            )
    body.append("</svg>")
    return "".join(body)


# --- (f) Horizontal waterfall ----------------------------------------------
def waterfall(components, *, title="Gap decomposition", xlabel="",
              w=_W, h=None) -> str:
    """Horizontal waterfall: decompose a gap into contributing components.

    Args:
        components: list of (label, value) pairs; positive values add to the
            running total (each stacked bar starts where the previous ended).
        title: accessible chart title.
        xlabel: x-axis unit label.

    Returns:
        str: inline SVG; placeholder if no components.
    """
    comps = [(l, v) for l, v in (components or []) if v is not None]
    if not comps:
        return _placeholder(title)
    rows = len(comps)
    h = h or (70 + rows * 46)
    pl, pr, pt, pb = 150, 24, 30, 40
    total = sum(v for _, v in comps)
    hi = max(total, max(abs(v) for _, v in comps))
    xs = _scaler(0, hi, pl, w - pr)
    palette_cycle = [SERIES["loss"], SERIES["leader"], PALETTE["primary_dark"],
                     PALETTE["field"], SERIES["bill"]]
    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
    ]
    run = 0.0
    rowh = (h - pt - pb) / rows
    for i, (label, val) in enumerate(comps):
        y = pt + i * rowh + rowh * 0.2
        bh = rowh * 0.6
        x0, x1 = xs(run), xs(run + val)
        color = palette_cycle[i % len(palette_cycle)]
        body.append(
            f'<rect x="{min(x0,x1):.1f}" y="{y:.1f}" '
            f'width="{abs(x1-x0):.1f}" height="{bh:.1f}" fill="{color}" rx="2"/>'
        )
        body.append(
            f'<text x="{pl-10}" y="{y+bh/2+4:.1f}" text-anchor="end" '
            f'fill="{PALETTE["text_secondary"]}" font-size="12">{_esc(label)}</text>'
        )
        body.append(
            f'<text x="{max(x0,x1)+6:.1f}" y="{y+bh/2+4:.1f}" '
            f'fill="{PALETTE["muted"]}" font-size="11" '
            f'font-variant-numeric="tabular-nums">{_fmt(round(val,1))}</text>'
        )
        run += val
    if xlabel:
        body.append(
            f'<text x="{(pl+w-pr)/2:.1f}" y="{h-6}" text-anchor="middle" '
            f'fill="{PALETTE["text_secondary"]}" font-size="12">{_esc(xlabel)}</text>'
        )
    body.append("</svg>")
    return "".join(body)


# --- (g) Progression line over rounds --------------------------------------
def progression(rounds, score_series, laps_series, *,
                title="Progression across rounds", w=_W, h=360) -> str:
    """Dual-y progression line over rounds: normalised score and raw laps.

    Args:
        rounds: list of round numbers/labels for the x-axis.
        score_series: normalised score per round (0-1000-ish, left axis).
        laps_series: raw laps per round (right axis).
        title: accessible chart title.

    Returns:
        str: inline SVG; placeholder if no rounds.
    """
    if not rounds:
        return _placeholder(title)
    pl, pr, pt, pb = _PAD["l"], _PAD["r"] + 32, _PAD["t"], _PAD["b"]
    n = len(rounds)
    xs = _scaler(0, max(n - 1, 1), pl, w - pr)
    sv = [s for s in score_series if s is not None]
    lv = [l for l in laps_series if l is not None]
    ys_score = _scaler(min(sv + [0]), max(sv + [1]), h - pb, pt)
    ys_laps = _scaler(0, max(lv + [1]), h - pb, pt)
    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
    ]
    # left axis ticks (score)
    for tv in _nice_ticks(min(sv + [0]), max(sv + [1])):
        y = ys_score(tv)
        body.append(
            f'<line x1="{pl}" y1="{y:.1f}" x2="{w-pr}" y2="{y:.1f}" '
            f'stroke="{PALETTE["hairline"]}"/>'
            f'<text x="{pl-8}" y="{y+4:.1f}" text-anchor="end" '
            f'fill="{PALETTE["muted"]}" font-size="11">{_fmt(tv)}</text>'
        )
    # right axis ticks (laps)
    for tv in _nice_ticks(0, max(lv + [1])):
        y = ys_laps(tv)
        body.append(
            f'<text x="{w-pr+8}" y="{y+4:.1f}" text-anchor="start" '
            f'fill="{PALETTE["muted"]}" font-size="11">{_fmt(tv)}</text>'
        )
    # x labels
    for i, r in enumerate(rounds):
        body.append(
            f'<text x="{xs(i):.1f}" y="{h-pb+16}" text-anchor="middle" '
            f'fill="{PALETTE["muted"]}" font-size="10">{_esc(r)}</text>'
        )
    laps_pts = [(xs(i), ys_laps(v)) for i, v in enumerate(laps_series) if v is not None]
    score_pts = [(xs(i), ys_score(v)) for i, v in enumerate(score_series) if v is not None]
    body.append(_polyline(laps_pts, SERIES["field"], 2.0, dash="4 3"))
    body.append(_polyline(score_pts, SERIES["bill"], 2.4))
    for x, y in score_pts:
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{SERIES["bill"]}"/>')
    body.append(_legend([("Norm. score", SERIES["bill"]),
                         ("Laps", SERIES["field"])], w))
    body.append("</svg>")
    return "".join(body)


# --- (h) Distribution / strip plot ------------------------------------------
def strip_plot(series, *, title="Distribution", xlabel="", w=_W, h=None,
               highlight_values=None) -> str:
    """Horizontal strip/dot distribution, one row per named series.

    Args:
        series: list of (label, values) pairs; each ``values`` is a list of
            numbers plotted as dots on a shared x-scale.
        title: accessible chart title.
        xlabel: x-axis unit label.
        highlight_values: optional dict {label: value} drawing a marker (e.g.
            Bill's value vs the field row).

    Returns:
        str: inline SVG; placeholder if no data.
    """
    rows = [(l, [v for v in vs if v is not None]) for l, vs in (series or [])]
    rows = [(l, vs) for l, vs in rows if vs]
    if not rows:
        return _placeholder(title)
    all_vals = [v for _, vs in rows for v in vs]
    h = h or (60 + len(rows) * 54)
    pl, pr, pt, pb = 130, 24, 26, 38
    xs = _scaler(min(all_vals), max(all_vals), pl, w - pr)
    colors = [SERIES["field"], SERIES["leader"], SERIES["bill"]]
    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
    ]
    for tv in _nice_ticks(min(all_vals), max(all_vals)):
        x = xs(tv)
        body.append(
            f'<line x1="{x:.1f}" y1="{pt}" x2="{x:.1f}" y2="{h-pb}" '
            f'stroke="{PALETTE["hairline"]}"/>'
            f'<text x="{x:.1f}" y="{h-pb+16}" text-anchor="middle" '
            f'fill="{PALETTE["muted"]}" font-size="11">{_fmt(tv)}</text>'
        )
    rowh = (h - pt - pb) / len(rows)
    for i, (label, vs) in enumerate(rows):
        cy = pt + rowh * (i + 0.5)
        color = colors[i % len(colors)]
        body.append(
            f'<text x="{pl-10}" y="{cy+4:.1f}" text-anchor="end" '
            f'fill="{PALETTE["text_secondary"]}" font-size="12">{_esc(label)}</text>'
        )
        for v in vs:
            body.append(
                f'<circle cx="{xs(v):.1f}" cy="{cy:.1f}" r="4" '
                f'fill="{color}" fill-opacity="0.75"/>'
            )
        if highlight_values and label in highlight_values:
            hv = highlight_values[label]
            body.append(
                f'<line x1="{xs(hv):.1f}" y1="{cy-rowh*0.35:.1f}" '
                f'x2="{xs(hv):.1f}" y2="{cy+rowh*0.35:.1f}" '
                f'stroke="{SERIES["loss"]}" stroke-width="2"/>'
            )
    if xlabel:
        body.append(
            f'<text x="{(pl+w-pr)/2:.1f}" y="{h-4}" text-anchor="middle" '
            f'fill="{PALETTE["text_secondary"]}" font-size="12">{_esc(xlabel)}</text>'
        )
    body.append("</svg>")
    return "".join(body)


# --- (i) Small bullet / deficit bar ----------------------------------------
def bullet_bar(value, benchmark, *, vmax=None, title="Metric", label="",
               unit="", w=460, h=64) -> str:
    """Small bullet chart: a value bar against a benchmark marker.

    Args:
        value: Bill's value (green bar).
        benchmark: the leader/target value (drawn as a vertical marker).
        vmax: optional axis maximum (defaults to 1.15x the larger value).
        title: accessible chart title.
        label: row label drawn at the left.
        unit: unit suffix for the value readout.

    Returns:
        str: inline SVG; placeholder if value is None.
    """
    if value is None:
        return _placeholder(title, "n/a")
    hi = vmax or max(v for v in (value, benchmark) if v is not None) * 1.15 or 1
    pl, pr = 130, 70
    xs = _scaler(0, hi, pl, w - pr)
    cy = h / 2
    barh = 14
    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
        f'<text x="{pl-10}" y="{cy+4:.1f}" text-anchor="end" '
        f'fill="{PALETTE["text_secondary"]}" font-size="12">{_esc(label)}</text>',
        f'<rect x="{pl}" y="{cy-barh/2:.1f}" width="{xs(hi)-pl:.1f}" '
        f'height="{barh}" fill="{PALETTE["hairline"]}" rx="3"/>',
        f'<rect x="{pl}" y="{cy-barh/2:.1f}" width="{max(0,xs(value)-pl):.1f}" '
        f'height="{barh}" fill="{SERIES["bill"]}" rx="3"/>',
    ]
    if benchmark is not None:
        body.append(
            f'<line x1="{xs(benchmark):.1f}" y1="{cy-barh:.1f}" '
            f'x2="{xs(benchmark):.1f}" y2="{cy+barh:.1f}" '
            f'stroke="{SERIES["leader"]}" stroke-width="2.5"/>'
        )
    body.append(
        f'<text x="{w-pr+8}" y="{cy+4:.1f}" fill="{PALETTE["ink"]}" '
        f'font-size="12" font-variant-numeric="tabular-nums">'
        f'{_fmt(round(value,1))}{_esc(unit)}</text>'
    )
    body.append("</svg>")
    return "".join(body)
