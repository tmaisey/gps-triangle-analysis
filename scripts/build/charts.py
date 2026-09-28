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
def _ground_track_legacy(bill_track, leader_track, task=None, *,
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


_COMPASS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
               "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _compass_point(deg: float) -> str:
    """Return the 16-point compass label nearest to a bearing in degrees."""
    return _COMPASS_16[round((deg % 360) / 22.5) % 16]


def ground_track(round_or_bill=None, leader_track=None, task=None, *,
                 wind: dict | None = None, title: str | None = None,
                 w: int = 1120, h: int = 980) -> str:
    """Render the factual course + full-resolution GPS tracks for a round.

    Two call styles are supported:

    * **New (RPT-011):** ``ground_track(round_dict, wind=..., title=...)`` where
      ``round_dict`` is a full per-round dataset (carries ``task``, ``round``,
      ``bill``/``leader``). This is the current API for the report.
    * **Legacy:** ``ground_track(bill_track, leader_track, task, ...)`` — the
      earlier track-list overlay, kept for backwards compatibility.

    The new renderer draws the right-isosceles course (bold ink, on top, with
    turnpoint dots), full-resolution Bill + leader traces at low opacity in one
    shared equirectangular grid, a dashed perpendicular start/finish line, a
    North arrow (top-right of the plot), a 100 m scale bar (bottom-left), an
    inline bottom-right legend (Bill / Leader / Course), and a wind vector
    inside a reserved right band of the framed grid — pointing inward (the way
    the wind blows) with a compass + degrees + knots label. Marks are laid out
    so they do not overlap.

    Args:
        round_or_bill: a round dataset dict (new API), or Bill's track list
            (legacy API).
        leader_track: leader track list (legacy API only).
        task: task dict (legacy API only).
        wind: optional wind dict (``dir_deg``/``speed_kmh``/``speed_kn``); if
            omitted in the new API it is loaded from the round's weather row.
        title: accessible chart title.
        w: SVG width.
        h: SVG height.

    Returns:
        str: inline SVG; a placeholder if there is nothing to draw.
    """
    if not isinstance(round_or_bill, dict) or leader_track is not None or task is not None:
        return _ground_track_legacy(
            round_or_bill, leader_track, task,
            title=title or "Ground track", w=w if w != 1120 else 560,
            h=h if h != 980 else 520,
        )
    return _ground_track_course(round_or_bill, wind=wind, title=title, w=w, h=h)


def _ground_track_course(round_data: dict, *, wind: dict | None = None,
                         title: str | None = None, w: int = 1120,
                         h: int = 980) -> str:
    """Render the RPT-011 course + full-resolution track overlay for one round.

    See :func:`ground_track` for the visual contract. Ports the approved
    ``groundtrack_r17_v5`` prototype into inline SVG.
    """
    from . import data as D
    from .data import TRACK_LAT, TRACK_LON

    n = round_data["round"]
    task = round_data["task"]
    title = title or f"Round {n} ground track and course"
    geom = D.course_geometry(task)
    to_xy = D.projector(task["start_lat"], task["start_lon"])
    if wind is None:
        wind = D.wind_for_round(n)

    # Full-resolution tracks (fall back to the embedded compact tracks offline).
    try:
        bill_raw, lead_raw = D.full_tracks_for_round(n)
    except Exception:
        bill_raw, lead_raw = [], []
    if not bill_raw:
        bill_raw = round_data.get("bill", {}).get("track", [])
    if not lead_raw:
        lead_raw = round_data.get("leader", {}).get("track", [])
    bill_pts = [to_xy(r[TRACK_LAT], r[TRACK_LON]) for r in bill_raw]
    lead_pts = [to_xy(r[TRACK_LAT], r[TRACK_LON]) for r in lead_raw]

    course_pts = geom["turnpoints"]
    ink = PALETTE["ink"]
    grey = PALETTE["text_secondary"]
    grid = "#EEF0F1"

    # --- layout: the frame encloses the data area with a uniform margin band on
    # all four sides, wide enough to hold the wind glyph + label wherever the
    # wind's source bearing places it on the clockface (RPT-012). The glyph sits
    # in that margin — outside the trace box, inside the frame — on whichever
    # side the source points, so it is never pinned to one edge.
    frame = {"x": 40, "y": 52, "w": w - 40 - 28, "h": h - 52 - 40}
    wind_margin = 104
    data_box = {
        "x": frame["x"] + wind_margin, "y": frame["y"] + wind_margin,
        "w": frame["w"] - 2 * wind_margin, "h": frame["h"] - 2 * wind_margin,
    }

    allx = [p[0] for p in bill_pts + lead_pts + course_pts]
    ally = [p[1] for p in bill_pts + lead_pts + course_pts]
    if not allx:
        return _placeholder(title)
    pad = 40
    xmin, xmax = min(allx) - pad, max(allx) + pad
    ymin, ymax = min(ally) - pad, max(ally) + pad
    scale = min(data_box["w"] / (xmax - xmin), data_box["h"] / (ymax - ymin))
    offx = data_box["x"] + (data_box["w"] - (xmax - xmin) * scale) / 2
    offy = data_box["y"] + (data_box["h"] - (ymax - ymin) * scale) / 2

    def X(x):
        return offx + (x - xmin) * scale

    def Y(y):
        return offy + (ymax - y) * scale  # flip: north up

    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
    ]
    # faint 100 m grid inside the data area
    gx = math.ceil(xmin / 100) * 100
    while gx < xmax:
        body.append(f'<line x1="{X(gx):.1f}" y1="{data_box["y"]:.1f}" '
                    f'x2="{X(gx):.1f}" y2="{data_box["y"]+data_box["h"]:.1f}" '
                    f'stroke="{grid}" stroke-width="1"/>')
        gx += 100
    gy = math.ceil(ymin / 100) * 100
    while gy < ymax:
        body.append(f'<line x1="{data_box["x"]:.1f}" y1="{Y(gy):.1f}" '
                    f'x2="{data_box["x"]+data_box["w"]:.1f}" y2="{Y(gy):.1f}" '
                    f'stroke="{grid}" stroke-width="1"/>')
        gy += 100
    # outer frame (encloses the data area and the wind margin band)
    body.append(f'<rect x="{frame["x"]:.1f}" y="{frame["y"]:.1f}" width="{frame["w"]:.1f}" '
                f'height="{frame["h"]:.1f}" fill="none" stroke="{PALETTE["hairline"]}" '
                f'stroke-width="1.2"/>')

    # traces (full-res, low opacity)
    def trace(pts, color):
        if not pts:
            return ""
        s = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pts)
        return (f'<polyline points="{s}" fill="none" stroke="{color}" '
                f'stroke-width="1.1" stroke-opacity="0.38" '
                f'stroke-linejoin="round" stroke-linecap="round"/>')
    body.append(trace(bill_pts, SERIES["bill"]))
    body.append(trace(lead_pts, SERIES["leader"]))

    # start/finish: dashed perpendicular line through start
    (sfa, sfb) = geom["start_finish"]
    body.append(f'<line x1="{X(sfa[0]):.1f}" y1="{Y(sfa[1]):.1f}" '
                f'x2="{X(sfb[0]):.1f}" y2="{Y(sfb[1]):.1f}" stroke="{ink}" '
                f'stroke-width="1.6" stroke-dasharray="7 5" stroke-opacity="0.75"/>')

    # course triangle (bold ink, drawn last / on top) + turnpoint dots
    tri = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in course_pts)
    body.append(f'<polygon points="{tri}" fill="{ink}" fill-opacity="0.04" '
                f'stroke="{ink}" stroke-width="3.4" stroke-linejoin="round"/>')
    for (x, y) in course_pts:
        body.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="4.5" fill="{ink}"/>'
                    f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="4.5" fill="none" '
                    f'stroke="#fff" stroke-width="1.4"/>')
    body.append(f'<circle cx="{X(0):.1f}" cy="{Y(0):.1f}" r="5.5" fill="#fff" '
                f'stroke="{ink}" stroke-width="2"/>'
                f'<circle cx="{X(0):.1f}" cy="{Y(0):.1f}" r="1.6" fill="{ink}"/>')
    body.append(f'<text x="{X(0)+9:.1f}" y="{Y(0)+14:.1f}" font-size="11.5" '
                f'fill="{ink}" font-weight="600">START / FINISH</text>')

    # North arrow (top-right of data area)
    nx, ny = data_box["x"] + data_box["w"] - 30, data_box["y"] + 20
    body.append(f'<line x1="{nx:.1f}" y1="{ny+34:.1f}" x2="{nx:.1f}" y2="{ny:.1f}" '
                f'stroke="{ink}" stroke-width="2"/>'
                f'<polygon points="{nx:.1f},{ny-2:.1f} {nx-5:.1f},{ny+9:.1f} '
                f'{nx+5:.1f},{ny+9:.1f}" fill="{ink}"/>'
                f'<text x="{nx:.1f}" y="{ny+50:.1f}" font-size="13" font-weight="700" '
                f'fill="{ink}" text-anchor="middle">N</text>')

    # 100 m scale bar (bottom-left of data area)
    barm = 100 * scale
    bx, by = data_box["x"] + 18, data_box["y"] + data_box["h"] - 20
    body.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{bx+barm:.1f}" y2="{by:.1f}" '
                f'stroke="{ink}" stroke-width="2.4"/>'
                f'<line x1="{bx:.1f}" y1="{by-5:.1f}" x2="{bx:.1f}" y2="{by+5:.1f}" '
                f'stroke="{ink}" stroke-width="2.4"/>'
                f'<line x1="{bx+barm:.1f}" y1="{by-5:.1f}" x2="{bx+barm:.1f}" '
                f'y2="{by+5:.1f}" stroke="{ink}" stroke-width="2.4"/>'
                f'<text x="{bx:.1f}" y="{by-9:.1f}" font-size="12" fill="{ink}" '
                f'font-weight="600">100 m</text>')

    # legend (bottom-right of data area, evenly spaced)
    items = [("Bill", SERIES["bill"]), ("Leader", SERIES["leader"]), ("Course", ink)]
    char_w, swatch, sw_gap, item_gap = 7.3, 18, 8, 28
    widths = [swatch + sw_gap + len(lab) * char_w for lab, _ in items]
    total = sum(widths) + item_gap * (len(items) - 1)
    lx = (data_box["x"] + data_box["w"] - 16) - total
    ly = data_box["y"] + data_box["h"] - 20
    for i, (lab, col) in enumerate(items):
        body.append(f'<line x1="{lx:.1f}" y1="{ly-6:.1f}" x2="{lx+swatch:.1f}" '
                    f'y2="{ly-6:.1f}" stroke="{col}" stroke-width="3.2"/>'
                    f'<text x="{lx+swatch+sw_gap:.1f}" y="{ly-2:.1f}" font-size="12" '
                    f'fill="{ink}" font-weight="600">{_esc(lab)}</text>')
        lx += widths[i] + item_gap

    # wind glyph placed at the clockface angle of the source bearing, pointing
    # inward (the way the wind blows), with a knots label
    if wind and wind.get("dir_deg") is not None:
        body.append(_wind_vector_clockface(wind, data_box, frame, grey))

    body.append("</svg>")
    return "".join(body)


def _wind_vector_clockface(wind: dict, data_box: dict, frame: dict,
                           grey: str) -> str:
    """Draw the wind glyph in the margin at the clockface angle of the source.

    The glyph sits on the ray leaving the data-area centre toward the wind
    *source* bearing, measured clockwise from screen-up (N = top, E = right,
    S = bottom, W = left): ``x = cx + R·sin θ``, ``y = cy − R·cos θ``. So a
    westerly wind (source ~270°) lands to the LEFT of the traces, an easterly
    (~90°) to the RIGHT, a northerly (~0/360°) at the TOP, a southerly (~180°)
    at the BOTTOM. The glyph lives in the framed margin — OUTSIDE the trace box
    but INSIDE the outer frame — and the arrow points INWARD (toward the centre),
    i.e. the direction the wind blows. A grey compass/degrees/speed label sits
    beside it, offset off the shaft and clamped to stay within the frame, so it
    never clips the frame nor collides with the (in-box) North marker, scale bar
    or legend.

    Args:
        wind: wind dict (``dir_deg`` source bearing, ``speed_kmh``, ``speed_kn``).
        data_box: the trace box rect (``x``/``y``/``w``/``h``).
        frame: the outer frame rect the glyph+label must stay inside.
        grey: stroke/fill colour for the glyph and label.

    Returns:
        str: SVG fragment for the arrow and its label.
    """
    deg = float(wind["dir_deg"])
    th = math.radians(deg)
    # placement unit vector: centre -> glyph, clockwise from screen-up (N).
    ux, uy = math.sin(th), -math.cos(th)
    cx = data_box["x"] + data_box["w"] / 2
    cy = data_box["y"] + data_box["h"] / 2
    hw, hh = data_box["w"] / 2, data_box["h"] / 2
    # ray/box intersection: distance from the centre to the trace-box edge.
    tx_e = hw / abs(ux) if abs(ux) > 1e-6 else float("inf")
    ty_e = hh / abs(uy) if abs(uy) > 1e-6 else float("inf")
    t_edge = min(tx_e, ty_e)
    ex, ey = cx + ux * t_edge, cy + uy * t_edge  # exit point on the box edge
    gap_in, shaft = 8.0, 40.0
    hx, hy = ex + ux * gap_in, ey + uy * gap_in       # arrow head (inner tip)
    tx2, ty2 = hx + ux * shaft, hy + uy * shaft       # arrow tail (outer end)
    inx, iny = -ux, -uy                               # inward = the way wind blows
    perpx, perpy = -iny, inx
    parts = [
        f'<line x1="{tx2:.1f}" y1="{ty2:.1f}" x2="{hx:.1f}" y2="{hy:.1f}" '
        f'stroke="{grey}" stroke-width="3"/>',
        f'<polygon points="{hx+inx*12:.1f},{hy+iny*12:.1f} '
        f'{hx+perpx*6:.1f},{hy+perpy*6:.1f} '
        f'{hx-perpx*6:.1f},{hy-perpy*6:.1f}" fill="{grey}"/>',
    ]
    # label: three short grey lines, offset off the shaft so text never sits on
    # the arrow, then clamped so the whole block stays inside the frame.
    kmh = wind.get("speed_kmh")
    kn = wind.get("speed_kn")
    lines = ["WIND", f"{_compass_point(deg)} {int(round(deg)):03d}°"]
    if isinstance(kmh, (int, float)):
        spd = f"{kmh:.1f} km/h"
        if isinstance(kn, (int, float)):
            spd += f" · {kn:.1f} kn"
        lines.append(spd)
    line_h = 15.0
    block_h = line_h * len(lines)
    if abs(ux) >= abs(uy):
        # horizontal-ish arrow (glyph left/right): stack the label above the tail
        lcx, lcy = tx2, ty2 - block_h - 8
    else:
        # vertical-ish arrow (glyph top/bottom): label beyond the tail
        lcx = tx2
        lcy = ty2 + 8 if uy > 0 else ty2 - block_h - 8
    half_w = max(len(s) for s in lines) * 3.4 + 6
    lcx = min(max(lcx, frame["x"] + half_w + 6),
              frame["x"] + frame["w"] - half_w - 6)
    lcy = min(max(lcy, frame["y"] + 4),
              frame["y"] + frame["h"] - block_h - 4)
    weights = ("700", "400", "400")
    for i, s in enumerate(lines):
        parts.append(
            f'<text x="{lcx:.1f}" y="{lcy + 12 + i * line_h:.1f}" font-size="12" '
            f'fill="{grey}" text-anchor="middle" '
            f'font-weight="{weights[i] if i < len(weights) else "400"}">'
            f'{_esc(s)}</text>')
    return "".join(parts)


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


# --- (j) Energy Management dual-panel (RPT-018) -----------------------------
def _rolling_mean(vals: Sequence[float], window: int) -> list[float]:
    """Return a centred simple rolling mean with an odd, edge-shrinking window."""
    if window <= 1 or len(vals) < 3:
        return list(vals)
    half = window // 2
    out = []
    n = len(vals)
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        out.append(sum(vals[lo:hi]) / (hi - lo))
    return out


def energy_management(round_data: dict, *, title: str = "Energy Management",
                      speed_smooth: int = 5, w: int = 980, h: int = 600) -> str:
    """Stacked dual-panel altitude + ground-speed chart for one round (RPT-018).

    Ports the approved ``energy_management_v3`` prototype. A single shared x-axis
    (run-relative flight time, T0 = the scored start-line crossing) spans the
    full 0-30 min working window. Altitude occupies the top ~80% at full GPS
    resolution; ground speed the bottom ~20%, lightly smoothed. Both pilots
    appear on both panels as solid lines (Bill green, leader blue); one figure
    title, no per-panel titles, one legend. Each trace is clipped at that pilot's
    last turn-point crossing (the descent/rollout is dropped).

    Args:
        round_data: a full per-round dataset dict (carries ``round``, ``bill``,
            ``leader``).
        title: figure title (kept as 'Energy Management').
        speed_smooth: rolling-mean window (samples ~= seconds at 1 Hz) applied to
            the ground-speed panel only.
        w: SVG width.
        h: SVG height.

    Returns:
        str: inline SVG; a placeholder if no track data is available.
    """
    from . import data as D
    from .data import TRACK_T, TRACK_ALT, TRACK_GS

    n = round_data["round"]
    try:
        bill_rows, lead_rows = D.full_tracks_for_round(n, clip_to_last_tpc=True)
    except Exception:
        bill_rows, lead_rows = [], []
    if not bill_rows:
        bill_rows = round_data.get("bill", {}).get("track", [])
    if not lead_rows:
        lead_rows = round_data.get("leader", {}).get("track", [])
    if not bill_rows and not lead_rows:
        return _placeholder(title)

    bill = _series_from_rows(bill_rows, TRACK_T, TRACK_ALT, TRACK_GS, speed_smooth)
    lead = _series_from_rows(lead_rows, TRACK_T, TRACK_ALT, TRACK_GS, speed_smooth)

    # Distance rounds keep the fixed 0-30 min shared window; speed runs are
    # ~1-min flights, so fit the x-axis to the actual flight duration and use the
    # full plot width instead of squashing them into the far left (RPT-018).
    is_speed = round_data.get("task_type") == "speedrun"
    if is_speed:
        all_mins = bill["mins"] + lead["mins"]
        x_max = max(all_mins) if all_mins else 1.0
    else:
        x_max = 30.0  # full working window in minutes
    all_alt = bill["alt"] + lead["alt"]
    all_spd = bill["spd"] + lead["spd"]
    if not all_alt:
        return _placeholder(title)
    alt_lo, alt_hi = min(all_alt), max(all_alt)
    pad = (alt_hi - alt_lo) * 0.06 or 1.0
    alt_lo, alt_hi = alt_lo - pad, alt_hi + pad
    spd_hi = (max(all_spd) * 1.10) if all_spd else 1.0

    ink, grey, hair, bg = (PALETTE["ink"], PALETTE["muted"], PALETTE["hairline"],
                           PALETTE["background"])
    ml, mr, mt, mb = 64, 24, 44, 54
    gap = 30
    px0, px1 = ml, w - mr
    py0, py1 = mt, h - mb
    total_h = py1 - py0 - gap
    alt_h = total_h * 0.80
    alt_y0, alt_y1 = py0, py0 + alt_h
    spd_y0, spd_y1 = alt_y1 + gap, py1

    def sx(m):
        return px0 + (m / x_max) * (px1 - px0)

    def sy_alt(v):
        return alt_y1 - (v - alt_lo) / (alt_hi - alt_lo) * (alt_y1 - alt_y0)

    def sy_spd(v):
        return spd_y1 - (v / spd_hi) * (spd_y1 - spd_y0)

    def pts(mins, vals, yf):
        return " ".join(f"{sx(m):.1f},{yf(v):.1f}" for m, v in zip(mins, vals))

    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{bg}"/>',
        f'<text x="{px0}" y="26" font-size="19" font-weight="600" fill="{ink}">'
        f'{_esc(title)}</text>',
    ]
    # shared x gridlines across both panels (5-min ticks over the 30-min window;
    # readable sub-minute ticks fitted to a speed run's short flight)
    xticks = [t for t in _nice_ticks(0, x_max, 6) if 0 <= t <= x_max + 1e-6]
    for xt in xticks:
        x = sx(xt)
        body.append(f'<line x1="{x:.1f}" y1="{alt_y0:.1f}" x2="{x:.1f}" y2="{alt_y1:.1f}" '
                    f'stroke="{hair}" stroke-width="1"/>')
        body.append(f'<line x1="{x:.1f}" y1="{spd_y0:.1f}" x2="{x:.1f}" y2="{spd_y1:.1f}" '
                    f'stroke="{hair}" stroke-width="1"/>')
    # altitude horizontal gridlines + labels
    for a in _nice_ticks(alt_lo, alt_hi, 5):
        if a < alt_lo or a > alt_hi:
            continue
        y = sy_alt(a)
        body.append(f'<line x1="{px0}" y1="{y:.1f}" x2="{px1}" y2="{y:.1f}" '
                    f'stroke="{hair}" stroke-width="1"/>'
                    f'<text x="{px0-8}" y="{y+3.5:.1f}" text-anchor="end" font-size="11" '
                    f'fill="{grey}">{_fmt(a)}</text>')
    # speed horizontal gridlines + labels
    for sv in _nice_ticks(0, spd_hi, 3):
        if sv < 0 or sv > spd_hi:
            continue
        y = sy_spd(sv)
        body.append(f'<line x1="{px0}" y1="{y:.1f}" x2="{px1}" y2="{y:.1f}" '
                    f'stroke="{hair}" stroke-width="1"/>'
                    f'<text x="{px0-8}" y="{y+3.5:.1f}" text-anchor="end" font-size="11" '
                    f'fill="{grey}">{_fmt(sv)}</text>')
    # panel left axes + shared baseline
    for y0, y1 in ((alt_y0, alt_y1), (spd_y0, spd_y1)):
        body.append(f'<line x1="{px0}" y1="{y0:.1f}" x2="{px0}" y2="{y1:.1f}" '
                    f'stroke="{grey}" stroke-width="1"/>')
    body.append(f'<line x1="{px0}" y1="{spd_y1:.1f}" x2="{px1}" y2="{spd_y1:.1f}" '
                f'stroke="{grey}" stroke-width="1"/>')
    # x tick labels once, under bottom panel + axis title
    for xt in xticks:
        body.append(f'<text x="{sx(xt):.1f}" y="{spd_y1+16:.1f}" text-anchor="middle" '
                    f'font-size="11" fill="{grey}">{xt:g}</text>')
    body.append(f'<text x="{(px0+px1)/2:.1f}" y="{h-8}" text-anchor="middle" '
                f'font-size="12.5" fill="{ink}">Relative flight time (minutes since '
                f'scored start-line crossing)</text>')
    # rotated y-axis labels naming each panel
    acy = (alt_y0 + alt_y1) / 2
    scy = (spd_y0 + spd_y1) / 2
    body.append(f'<text x="16" y="{acy:.1f}" text-anchor="middle" font-size="12.5" '
                f'fill="{ink}" transform="rotate(-90 16 {acy:.1f})">Altitude (m)</text>')
    body.append(f'<text x="16" y="{scy:.1f}" text-anchor="middle" font-size="12.5" '
                f'fill="{ink}" transform="rotate(-90 16 {scy:.1f})">Ground speed (km/h)</text>')
    # data lines (leader under Bill)
    for sdat, color in ((lead, SERIES["leader"]), (bill, SERIES["bill"])):
        if sdat["mins"]:
            body.append(f'<polyline points="{pts(sdat["mins"], sdat["alt"], sy_alt)}" '
                        f'fill="none" stroke="{color}" stroke-width="2" '
                        f'stroke-linejoin="round" stroke-linecap="round"/>')
            body.append(f'<polyline points="{pts(sdat["mins"], sdat["spd"], sy_spd)}" '
                        f'fill="none" stroke="{color}" stroke-width="1.8" '
                        f'stroke-linejoin="round" stroke-linecap="round"/>')
    # single legend, top-right of altitude panel
    bname = round_data.get("bill", {}).get("name", "Bill Maisey")
    lname = round_data.get("leader", {}).get("name", "Leader")
    entries = [(bname, SERIES["bill"]), (f"{lname} (leader)", SERIES["leader"])]
    box_w, row_h = 200, 18
    lgx0 = px1 - box_w - 8
    lgy0 = alt_y0 + 10
    body.append(f'<rect x="{lgx0:.1f}" y="{lgy0:.1f}" width="{box_w}" '
                f'height="{row_h*len(entries)+8}" rx="4" fill="{bg}" fill-opacity="0.85" '
                f'stroke="{hair}" stroke-width="1"/>')
    for i, (label, color) in enumerate(entries):
        yy = lgy0 + 14 + i * row_h
        body.append(f'<line x1="{lgx0+10:.1f}" y1="{yy:.1f}" x2="{lgx0+30:.1f}" '
                    f'y2="{yy:.1f}" stroke="{color}" stroke-width="3"/>'
                    f'<text x="{lgx0+38:.1f}" y="{yy+4:.1f}" font-size="12" '
                    f'fill="{ink}">{_esc(label)}</text>')
    body.append("</svg>")
    return "".join(body)


def _series_from_rows(rows, ti, ai, gi, smooth):
    """Build a run-relative {mins, alt, spd} series from track rows for a panel."""
    mins = [r[ti] / 60.0 for r in rows]
    alt = [r[ai] for r in rows]
    spd_raw = [r[gi] for r in rows]
    return {"mins": mins, "alt": alt, "spd": _rolling_mean(spd_raw, smooth)}


# --- (k) All-rounds grouped bars + condition/rank strips (RPT-022) ----------
def grouped_bar_rounds(rounds, series, *, title="", ylabel="", unit="",
                       w=_W, h=300) -> str:
    """All-rounds grouped bar chart: several series, one group of bars per round.

    Built for the Overview Performance summary (RPT-022): three bars per round —
    round winner (blue), overall event winner (grey), Bill (green). Generic over
    the metric, so the same component renders score, laps, avg speed, entry speed
    and entry altitude.

    Args:
        rounds: x-axis round labels/numbers (e.g. ``list(range(1, 18))``).
        series: list of ``(label, values, color_key)`` tuples, where ``values``
            aligns with ``rounds`` (``None`` entries are skipped, e.g. a speed
            round with no distance metric) and ``color_key`` is one of
            ``'leader'`` (round winner), ``'field'`` (event winner), ``'bill'``.
        title: accessible chart title.
        ylabel: y-axis title.
        unit: optional unit suffix (unused on axis, kept for callers).

    Returns:
        str: inline SVG; placeholder if no rounds/series.
    """
    if not rounds or not series:
        return _placeholder(title or "Rounds")
    pl, pr, pt, pb = _PAD["l"], _PAD["r"], _PAD["t"], _PAD["b"]
    allv = [v for _, vals, _ in series for v in vals if v is not None]
    if not allv:
        return _placeholder(title or "Rounds")
    vmax = max(allv + [0])
    vmin = min(allv + [0])
    ys = _scaler(vmin, vmax, h - pb, pt)
    n = len(rounds)
    band = (w - pl - pr) / n
    k = len(series)
    bw = band * 0.8 / k
    zero = ys(0 if vmin <= 0 <= vmax else vmin)
    body = [
        _svg_open(w, h, title or "Rounds"),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
    ]
    for tv in _nice_ticks(vmin, vmax):
        y = ys(tv)
        body.append(f'<line x1="{pl}" y1="{y:.1f}" x2="{w-pr}" y2="{y:.1f}" '
                    f'stroke="{PALETTE["hairline"]}"/>'
                    f'<text x="{pl-8}" y="{y+4:.1f}" text-anchor="end" '
                    f'fill="{PALETTE["muted"]}" font-size="11">{_fmt(tv)}</text>')
    for i, rnd in enumerate(rounds):
        gx = pl + band * i + band * 0.1
        for j, (_, vals, ckey) in enumerate(series):
            v = vals[i] if i < len(vals) else None
            if v is None:
                continue
            y = ys(v)
            top, ht = min(y, zero), abs(y - zero)
            body.append(f'<rect x="{gx+j*bw:.1f}" y="{top:.1f}" width="{bw*0.92:.1f}" '
                        f'height="{ht:.1f}" fill="{SERIES.get(ckey, PALETTE["field"])}" '
                        f'rx="1"/>')
        body.append(f'<text x="{pl+band*(i+0.5):.1f}" y="{h-pb+15}" text-anchor="middle" '
                    f'fill="{PALETTE["muted"]}" font-size="10">{_esc(rnd)}</text>')
    if ylabel:
        cy = (pt + h - pb) / 2
        body.append(f'<text x="14" y="{cy:.1f}" text-anchor="middle" '
                    f'fill="{PALETTE["text_secondary"]}" font-size="12" '
                    f'transform="rotate(-90 14 {cy:.1f})">{_esc(ylabel)}</text>')
    labels = [(lab, SERIES.get(ck, PALETTE["field"])) for lab, _, ck in series]
    body.append(_legend(labels, w))
    body.append("</svg>")
    return "".join(body)


def _lerp(a, b, t):
    return round(a + (b - a) * t)


def conditions_strip(values, *, labels=None, title="Conditions",
                     low_rgb=(250, 224, 139), high_rgb=(176, 32, 32),
                     unit="", w=_W, h=70) -> str:
    """Horizontal per-round colour strip normalised across all rounds (RPT-022).

    Each round is a cell whose colour interpolates from ``low_rgb`` (pastel
    yellow, the minimum across all rounds) to ``high_rgb`` (deep red, the
    maximum) by the round's normalised value. Built for the solar-radiation /
    lift-proxy strip aligned beneath the grouped bars so performance reads
    against conditions.

    Args:
        values: per-round numeric values (``None`` allowed; renders a hairline
            cell). Aligns with ``labels``.
        labels: per-round labels for the cells; defaults to ``1..len(values)``.
        title: accessible chart title.
        unit: optional unit label appended to the caption context (unused here).

    Returns:
        str: inline SVG; placeholder if no values.
    """
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return _placeholder(title)
    labels = labels or list(range(1, len(values) + 1))
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    n = len(values)
    pl, pr = _PAD["l"], _PAD["r"]
    cellw = (w - pl - pr) / n
    top, ch = 14, h - 34
    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
    ]
    for i, v in enumerate(values):
        x = pl + i * cellw
        if isinstance(v, (int, float)):
            t = (v - lo) / span
            col = (f'rgb({_lerp(low_rgb[0], high_rgb[0], t)},'
                   f'{_lerp(low_rgb[1], high_rgb[1], t)},'
                   f'{_lerp(low_rgb[2], high_rgb[2], t)})')
            body.append(f'<rect x="{x+1:.1f}" y="{top}" width="{cellw-2:.1f}" '
                        f'height="{ch:.1f}" rx="2" fill="{col}"/>')
        else:
            body.append(f'<rect x="{x+1:.1f}" y="{top}" width="{cellw-2:.1f}" '
                        f'height="{ch:.1f}" rx="2" fill="none" '
                        f'stroke="{PALETTE["hairline"]}"/>')
        body.append(f'<text x="{x+cellw/2:.1f}" y="{h-8}" text-anchor="middle" '
                    f'fill="{PALETTE["muted"]}" font-size="10">{_esc(labels[i])}</text>')
    body.append("</svg>")
    return "".join(body)


def rank_strip(ranks, *, group_sizes=None, labels=None,
               title="Within-group rank", w=_W, h=70) -> str:
    """Per-round within-group rank strip (Bill), 1 = best (RPT-022).

    Each round is a cell shaded by Bill's finishing position in his group (dark
    green = near the top of the group, pale = near the bottom), with the rank
    printed. Aligns column-for-column with :func:`grouped_bar_rounds`.

    Args:
        ranks: Bill's within-group rank per round (``None`` allowed).
        group_sizes: per-round group sizes used to normalise the shade; defaults
            to the max rank seen.
        labels: per-round labels; defaults to ``1..len(ranks)``.
        title: accessible chart title.

    Returns:
        str: inline SVG; placeholder if no ranks.
    """
    rk = [r for r in ranks if isinstance(r, (int, float))]
    if not rk:
        return _placeholder(title)
    labels = labels or list(range(1, len(ranks) + 1))
    n = len(ranks)
    pl, pr = _PAD["l"], _PAD["r"]
    cellw = (w - pl - pr) / n
    top, ch = 14, h - 34
    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
    ]
    for i, r in enumerate(ranks):
        x = pl + i * cellw
        if isinstance(r, (int, float)):
            gs = (group_sizes[i] if group_sizes and i < len(group_sizes)
                  and group_sizes[i] else max(rk))
            t = 1 - (r - 1) / max(gs - 1, 1)  # 1 (best) -> 1.0
            col = (f'rgb({_lerp(230, 4, t)},{_lerp(233, 106, t)},{_lerp(219, 56, t)})')
            body.append(f'<rect x="{x+1:.1f}" y="{top}" width="{cellw-2:.1f}" '
                        f'height="{ch:.1f}" rx="2" fill="{col}"/>')
            body.append(f'<text x="{x+cellw/2:.1f}" y="{top+ch/2+4:.1f}" '
                        f'text-anchor="middle" fill="{PALETTE["ink"]}" font-size="10" '
                        f'font-weight="600">{int(r)}</text>')
        else:
            body.append(f'<rect x="{x+1:.1f}" y="{top}" width="{cellw-2:.1f}" '
                        f'height="{ch:.1f}" rx="2" fill="none" '
                        f'stroke="{PALETTE["hairline"]}"/>')
        body.append(f'<text x="{x+cellw/2:.1f}" y="{h-8}" text-anchor="middle" '
                    f'fill="{PALETTE["muted"]}" font-size="10">{_esc(labels[i])}</text>')
    body.append("</svg>")
    return "".join(body)


# --- (m) Trajectory density charts (RPT-023 / RPT-024) ----------------------
def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Greedily wrap ``text`` to lines of at most ``max_chars`` characters."""
    words, lines, cur = text.split(), [], ""
    for word in words:
        if cur and len(cur) + 1 + len(word) > max_chars:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def _caption_block(caption: str, x: float, y: float, width: float) -> str:
    """Render a wrapped, top-ruled caption block at ``(x, y)`` (SVG text)."""
    if not caption:
        return ""
    lines = _wrap_text(caption, max_chars=int(width / 6.0))
    parts = [
        f'<line x1="{x:.1f}" y1="{y-10:.1f}" x2="{x+width:.1f}" y2="{y-10:.1f}" '
        f'stroke="{PALETTE["hairline"]}" stroke-width="1"/>'
    ]
    for i, line in enumerate(lines):
        parts.append(
            f'<text x="{x:.1f}" y="{y + i*14:.1f}" fill="{PALETTE["muted"]}" '
            f'font-size="11">{_esc(line)}</text>'
        )
    return "".join(parts)


def distance_from_course_density(density, *,
                                 title="Time spent away from the course",
                                 xlabel="Distance from the course triangle (m)",
                                 caption=None, w=_W, h=None) -> str:
    """Log-frequency density of distance from the course triangle (RPT-023).

    Renders a single **log-frequency** panel (no linear panel) of how each
    pilot's flight time is distributed by straight-line distance from the
    three-leg course outline, Bill vs the same-air round winner, pooled over the
    14 distance rounds. The log y-axis is floored across five decades
    (10 % / 1 % / 0.1 % / 0.01 % / 0.001 %) and every near-zero bin is floored to
    a value strictly above the axis baseline, so **both** density lines — and
    Bill's green line in particular — always sit above the x-axis and never
    touch or cross it. Lines are unfilled.

    Args:
        density: dict from :func:`data.pooled_distance_from_course` — keys
            ``edges`` (bin edges, m) and ``bill``/``leader`` records each with
            ``frac`` (share of flight time per bin), ``n`` and ``median`` (m).
        title: accessible chart title.
        xlabel: x-axis label.
        caption: caption text; a source/method caption is built from the data
            when omitted. Pass ``""`` to suppress.
        w, h: SVG viewBox size.

    Returns:
        str: inline SVG (placeholder if the density is empty).
    """
    if not density or not density.get("edges"):
        return _placeholder(title)
    edges = density["edges"]
    mids = [(edges[i] + edges[i + 1]) / 2 for i in range(len(edges) - 1)]
    bill, lead = density["bill"], density["leader"]

    pl, pr, pt = 64, 24, 44
    yb = pt + 252                      # plot baseline (x-axis)
    xmax = float(edges[-1])
    if caption is None:
        caption = (
            f"Pooled ~1 Hz track points across the 14 distance rounds "
            f"(Bill {bill['n']:,} pts, winner {lead['n']:,} pts); one point per "
            f"second, so the curve is time-weighted. Distance-from-course = "
            f"straight-line distance in the local metre grid to the nearest of "
            f"the three triangle legs. Log frequency; unfilled 20 m bins, with "
            f"near-zero bins floored so both lines stay above the axis. Winner = "
            f"Bill's same-air group winner. Median distance: Bill "
            f"{bill['median']:g} m, winner {lead['median']:g} m."
        )
    cap_lines = _wrap_text(caption, int((w - pr - pl) / 6.0)) if caption else []
    if h is None:
        h = int(yb + 62 + len(cap_lines) * 14 + 6)
    ymin, ymax = 1e-5, 0.35            # 0.001 % .. 35 %
    floor = 1.6e-5                     # keep every point above the axis baseline
    yticks = [0.1, 0.01, 1e-3, 1e-4, 1e-5]   # 10 % 1 % 0.1 % 0.01 % 0.001 %
    xticks = [t for t in (0, 100, 200, 300, 400, 500, 600) if t <= xmax]

    xs = _scaler(0.0, xmax, pl, w - pr)
    lymin, lymax = math.log10(ymin), math.log10(ymax)
    ys_log = _scaler(lymin, lymax, yb, pt)

    def ys(frac: float) -> float:
        return ys_log(math.log10(max(frac, floor)))

    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
        _legend([("Bill", SERIES["bill"]), ("Round winner", SERIES["leader"])], w, y=22),
    ]
    # y gridlines + percentage labels
    for tv in yticks:
        y = ys_log(math.log10(tv))
        body.append(
            f'<line x1="{pl}" y1="{y:.1f}" x2="{w-pr}" y2="{y:.1f}" '
            f'stroke="{PALETTE["hairline"]}" stroke-width="1"/>'
        )
        body.append(
            f'<text x="{pl-8}" y="{y+4:.1f}" text-anchor="end" '
            f'fill="{PALETTE["muted"]}" font-size="11" '
            f'font-variant-numeric="tabular-nums">{tv*100:g}%</text>'
        )
    # x ticks
    for tv in xticks:
        x = xs(tv)
        body.append(
            f'<line x1="{x:.1f}" y1="{yb}" x2="{x:.1f}" y2="{yb+5}" '
            f'stroke="{PALETTE["text_secondary"]}" stroke-width="1"/>'
        )
        body.append(
            f'<text x="{x:.1f}" y="{yb+19:.1f}" text-anchor="middle" '
            f'fill="{PALETTE["muted"]}" font-size="11" '
            f'font-variant-numeric="tabular-nums">{int(tv)}</text>'
        )
    # axis frame (left + baseline) in ink
    body.append(f'<line x1="{pl}" y1="{pt}" x2="{pl}" y2="{yb}" '
                f'stroke="{PALETTE["ink"]}" stroke-width="1.5"/>')
    body.append(f'<line x1="{pl}" y1="{yb}" x2="{w-pr}" y2="{yb}" '
                f'stroke="{PALETTE["ink"]}" stroke-width="1.5"/>')
    # y-axis title
    cy = (pt + yb) / 2
    body.append(
        f'<text x="18" y="{cy:.1f}" text-anchor="middle" '
        f'fill="{PALETTE["text_secondary"]}" font-size="12" '
        f'transform="rotate(-90 18 {cy:.1f})">Share of flight time (log)</text>'
    )
    # x-axis title
    body.append(
        f'<text x="{(pl+w-pr)/2:.1f}" y="{yb+40:.1f}" text-anchor="middle" '
        f'fill="{PALETTE["text_secondary"]}" font-size="12">{_esc(xlabel)}</text>'
    )
    # unfilled, floored density lines
    for rec, color in ((bill, SERIES["bill"]), (lead, SERIES["leader"])):
        pts = [(xs(m), ys(f)) for m, f in zip(mids, rec["frac"])]
        body.append(_polyline(pts, color, width=2.4))
    body.append(_caption_block(caption, pl, yb + 62, w - pr - pl))
    body.append("</svg>")
    return "".join(body)


def turn_radius_density(density, *,
                        title="Thermalling turn-radius distribution",
                        xlabel="Thermalling turn radius (m)",
                        caption=None, w=_W, h=None) -> str:
    """Turn-radius density in sustained climbs, Bill vs winner (RPT-024).

    Unfilled density lines of per-point turn radius ``r = v / omega`` inside
    detected sustained climbs (>= 12 s, >= 270 deg of turn, net height gain),
    pooled over the 14 distance rounds, with a dashed vertical marker at each
    pilot's median.

    Args:
        density: dict from :func:`data.pooled_turn_radius` — keys ``edges``
            (bin edges, m) and ``bill``/``leader`` records each with ``frac``
            (share of circling time per bin), ``n`` and ``median`` (m).
        title: accessible chart title.
        xlabel: x-axis label.
        caption: caption text; a source/method caption is built from the data
            when omitted. Pass ``""`` to suppress.
        w, h: SVG viewBox size.

    Returns:
        str: inline SVG (placeholder if the density is empty).
    """
    if not density or not density.get("edges"):
        return _placeholder(title)
    edges = density["edges"]
    mids = [(edges[i] + edges[i + 1]) / 2 for i in range(len(edges) - 1)]
    bill, lead = density["bill"], density["leader"]

    pl, pr, pt = 64, 24, 44
    yb = pt + 252
    xmax = float(edges[-1])
    if caption is None:
        caption = (
            f"Per-point turn radius r = v / omega (ground speed / bearing rate) "
            f"during detected sustained climbs (>= 12 s, >= 270 deg of turn, net "
            f"height gain), pooled over the 14 distance rounds "
            f"(Bill {bill['n']:,} vs winner {lead['n']:,} circling samples). "
            f"Unfilled densities over 5 m bins; dashed lines mark each pilot's "
            f"median. Display window 0-100 m. Winner = Bill's same-air group "
            f"winner. Median radius: Bill {bill['median']:g} m, winner "
            f"{lead['median']:g} m."
        )
    cap_lines = _wrap_text(caption, int((w - pr - pl) / 6.0)) if caption else []
    if h is None:
        h = int(yb + 62 + len(cap_lines) * 14 + 6)
    peak = max(max(bill["frac"], default=0), max(lead["frac"], default=0))
    ymax = max(peak * 1.15, 1e-6)
    xs = _scaler(0.0, xmax, pl, w - pr)
    ys = _scaler(0.0, ymax, yb, pt)

    body = [
        _svg_open(w, h, title),
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{PALETTE["background"]}"/>',
        _legend([("Bill", SERIES["bill"]), ("Round winner", SERIES["leader"])], w, y=22),
    ]
    # y gridlines + percentage labels
    for tv in _nice_ticks(0.0, ymax, 5):
        y = ys(tv)
        body.append(
            f'<line x1="{pl}" y1="{y:.1f}" x2="{w-pr}" y2="{y:.1f}" '
            f'stroke="{PALETTE["hairline"]}" stroke-width="1"/>'
        )
        body.append(
            f'<text x="{pl-8}" y="{y+4:.1f}" text-anchor="end" '
            f'fill="{PALETTE["muted"]}" font-size="11" '
            f'font-variant-numeric="tabular-nums">{tv*100:g}%</text>'
        )
    # x ticks
    for tv in (t for t in (0, 20, 40, 60, 80, 100) if t <= xmax):
        x = xs(tv)
        body.append(
            f'<line x1="{x:.1f}" y1="{yb}" x2="{x:.1f}" y2="{yb+5}" '
            f'stroke="{PALETTE["text_secondary"]}" stroke-width="1"/>'
        )
        body.append(
            f'<text x="{x:.1f}" y="{yb+19:.1f}" text-anchor="middle" '
            f'fill="{PALETTE["muted"]}" font-size="11" '
            f'font-variant-numeric="tabular-nums">{int(tv)}</text>'
        )
    # axis frame
    body.append(f'<line x1="{pl}" y1="{pt}" x2="{pl}" y2="{yb}" '
                f'stroke="{PALETTE["ink"]}" stroke-width="1.5"/>')
    body.append(f'<line x1="{pl}" y1="{yb}" x2="{w-pr}" y2="{yb}" '
                f'stroke="{PALETTE["ink"]}" stroke-width="1.5"/>')
    cy = (pt + yb) / 2
    body.append(
        f'<text x="18" y="{cy:.1f}" text-anchor="middle" '
        f'fill="{PALETTE["text_secondary"]}" font-size="12" '
        f'transform="rotate(-90 18 {cy:.1f})">Share of circling time</text>'
    )
    body.append(
        f'<text x="{(pl+w-pr)/2:.1f}" y="{yb+40:.1f}" text-anchor="middle" '
        f'fill="{PALETTE["text_secondary"]}" font-size="12">{_esc(xlabel)}</text>'
    )
    # unfilled density lines
    for rec, color in ((bill, SERIES["bill"]), (lead, SERIES["leader"])):
        pts = [(xs(m), ys(f)) for m, f in zip(mids, rec["frac"])]
        body.append(_polyline(pts, color, width=2.4))
    # dashed median markers
    markers = [
        (lead["median"], SERIES["leader"], "end", -4, pt + 14),
        (bill["median"], SERIES["bill"], "start", 4, pt + 30),
    ]
    for med, color, anchor, dx, ly in markers:
        if med is None or med > xmax:
            continue
        x = xs(med)
        body.append(
            f'<line x1="{x:.1f}" y1="{pt}" x2="{x:.1f}" y2="{yb}" stroke="{color}" '
            f'stroke-width="1.3" stroke-dasharray="4 3" opacity="0.85"/>'
        )
        body.append(
            f'<text x="{x+dx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="10.5" fill="{color}">median {med:g} m</text>'
        )
    body.append(_caption_block(caption, pl, yb + 62, w - pr - pl))
    body.append("</svg>")
    return "".join(body)
