"""Per-round 'Visual overview of performance' dashboard components (RPT-021).

Ports the approved ``round_dashboard_v6`` prototype into server-side inline-SVG
generators (ADR-005), matching the rest of the harness. Each component returns a
self-contained ``<svg>`` string themed from :data:`design.PALETTE`; the
top-level :func:`dashboard` assembles them into a 2-row x 4-col HTML grid with a
top-right colour-key legend.

Colour convention (locked to the report palette): Bill = green, round leader =
teal-blue, regs limit / other pilots = neutral grey. There are no accent bars,
gradients or emoji (DSN-001).

The dashboard is self-sufficient from a single per-round dataset dict (as loaded
by :func:`data.load_round`): it pulls the group score distribution, per-round
wind and the solar-radiation normalisation from the shared data loaders itself,
so a page only needs to pass the round.
"""

from __future__ import annotations

import html
import math

from . import components as C
from .design import PALETTE

# The public results page for the whole event (the dashboard's data source).
_EVENT_URL = (
    "https://www.rcmodelspot.com/Ranking/f772fc7c-c4c5-406d-9c21-f4e76044ddb7"
)

# Component palette (mirrors the v6 prototype tokens).
BILL = PALETTE["primary"]
BILL_INK = "#5C8F10"
LEADER = PALETTE["leader"]
FIELD = PALETTE["field"]
INK = PALETTE["ink"]
SEC = PALETTE["text_secondary"]
HAIR = PALETTE["hairline"]
BG = PALETTE["background"]
TRACK = "#EFEFE9"


def _esc(text) -> str:
    """Escape text for safe inclusion in SVG/HTML markup."""
    return html.escape(str(text), quote=True)


def _fmt(v, dec=1) -> str:
    """Format a number to ``dec`` decimals."""
    return f"{float(v):.{dec}f}"


# --- Individual components --------------------------------------------------
def bullet(bill, leader, domain_max, *, dec=1, w=138, th=196,
           label="Value", unit="", cap_note="cap") -> str:
    """Vertical bullet plot: Bill's value against the leader and a domain ceiling.

    The grey track's top edge is the domain maximum — the regs cap where one
    exists (entry speed 120 km/h, entry altitude 400 m), else a padded domain
    ceiling. Bill is a green fill from the baseline with the value printed to the
    RIGHT; the leader is a blue horizontal line with a small blue value on the
    left.

    Args:
        bill: Bill's value.
        leader: the leader's value.
        domain_max: the value mapped to the full track height (regs cap/ceiling).
        dec: decimal places for the value readouts.
        w: SVG width.
        th: track height in px.
        label: what the metric is, for the accessible name (e.g. 'Entry speed').
        unit: the unit both values are in (e.g. 'km/h').
        cap_note: how to describe ``domain_max`` in the accessible name
            (e.g. 'regs cap' or 'chart ceiling').

    Returns:
        str: inline SVG.
    """
    top = 24
    bottom = top + th
    track_x, track_w = 40, 30
    dm = domain_max or 1

    def y(v):
        return bottom - max(0.0, min(1.0, v / dm)) * th

    by = y(bill)
    ly = y(leader)
    unit_txt = f" {unit}" if unit else ""
    aria = (f"{label}: Bill {_fmt(bill, dec)}{unit_txt} versus leader "
            f"{_fmt(leader, dec)}{unit_txt}, {cap_note} {_fmt(dm, 0)}{unit_txt}")
    parts = [_open(w, bottom + 8, aria)]
    parts.append(f'<rect x="{track_x}" y="{top}" width="{track_w}" height="{th}" '
                 f'rx="4" fill="{TRACK}"/>')
    parts.append(f'<rect x="{track_x}" y="{by:.1f}" width="{track_w}" '
                 f'height="{bottom-by:.1f}" rx="4" fill="{BILL}"/>')
    parts.append(f'<line x1="{track_x-5}" y1="{ly:.1f}" x2="{track_x+track_w+5}" '
                 f'y2="{ly:.1f}" stroke="{LEADER}" stroke-width="3"/>')
    parts.append(f'<text x="{track_x-8}" y="{ly+3:.1f}" fill="{LEADER}" font-size="9.5" '
                 f'text-anchor="end">{_fmt(leader, dec)}</text>')
    parts.append(f'<text x="{track_x+track_w+8}" y="{by+4.5:.1f}" fill="{BILL_INK}" '
                 f'font-size="13" font-weight="700" text-anchor="start">'
                 f'{_fmt(bill, dec)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def violin(scores, bill_score, *, w=138, th=196) -> str:
    """Score-density violin: the group field with the winner and Bill marked.

    A symmetric grey kernel-density field of the group's normalised scores, a
    blue line at the winner's 1000, and a green line + label at Bill's score.

    Args:
        scores: the group's normalised scores (any order).
        bill_score: Bill's normalised score.
        w: SVG width.
        th: field height in px.

    Returns:
        str: inline SVG (placeholder note if no scores).
    """
    top = 24
    bottom = top + th
    cx = w / 2
    half_w = 30
    scores = [s for s in (scores or []) if s is not None]
    if not scores:
        return _open(w, bottom + 8, "Group score density: no group scores") + "</svg>"
    dmin, dmax = min(scores), 1000
    span = (dmax - dmin) or 1

    def y(v):
        return bottom - ((v - dmin) / span) * th

    n = 64
    bw = max(35.0, span * 0.06)
    ys, dens = [], []
    dmaxv = 0.0
    for i in range(n):
        v = dmin + span * i / (n - 1)
        d = sum(math.exp(-0.5 * ((v - s) / bw) ** 2) for s in scores)
        ys.append(y(v))
        dens.append(d)
        dmaxv = max(dmaxv, d)
    dmaxv = dmaxv or 1
    left = "".join(
        ("M" if i == 0 else "L") + f"{cx - dens[i]/dmaxv*half_w:.2f} {ys[i]:.2f} "
        for i in range(n)
    )
    right = "".join(
        f"L{cx + dens[i]/dmaxv*half_w:.2f} {ys[i]:.2f} " for i in range(n - 1, -1, -1)
    )
    aria = (f"Group score density: Bill {int(bill_score)} against a winning "
            f"1000, lowest in group {int(dmin)}, {len(scores)} pilots")
    parts = [_open(w, bottom + 8, aria)]
    parts.append(f'<path d="{left}{right}Z" fill="{FIELD}" opacity="0.9"/>')
    win_y = y(1000)
    by = y(bill_score)
    if by - win_y < 9:
        by = win_y + 9
    parts.append(f'<line x1="{cx-half_w-4}" y1="{win_y:.1f}" x2="{cx+half_w+4}" '
                 f'y2="{win_y:.1f}" stroke="{LEADER}" stroke-width="3.5"/>')
    parts.append(f'<text x="{cx-half_w-4}" y="{win_y-6:.1f}" fill="{LEADER}" '
                 f'font-size="10" font-weight="700">Winner 1000</text>')
    parts.append(f'<line x1="{cx-half_w-4}" y1="{by:.1f}" x2="{cx+half_w+4}" '
                 f'y2="{by:.1f}" stroke="{BILL}" stroke-width="3.5"/>')
    parts.append(f'<text x="{cx-half_w-4}" y="{by+13:.1f}" fill="{BILL_INK}" '
                 f'font-size="10" font-weight="700">Bill {int(bill_score)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def laps_bars(bill, leader, *, w=112, h=132) -> str:
    """Paired laps bars (Bill green, leader blue), value labels on top, no axis.

    Args:
        bill: Bill's lap count.
        leader: the leader's lap count.
        w: SVG width.
        h: SVG height.

    Returns:
        str: inline SVG.
    """
    base, top_pad, bw, gap = 104, 22, 30, 20
    mx = max(bill, leader, 1)
    bar_max = base - top_pad
    x0 = (w - (bw * 2 + gap)) / 2
    parts = [_open(w, h, f"Laps: Bill {int(bill)} versus leader {int(leader)}")]

    def draw(x, val, col):
        hh = (val / mx) * bar_max
        yv = base - hh
        return (f'<rect x="{x:.1f}" y="{yv:.1f}" width="{bw}" height="{hh:.1f}" '
                f'rx="3" fill="{col}"/>'
                f'<text x="{x+bw/2:.1f}" y="{yv-6:.1f}" fill="{INK}" font-size="14" '
                f'font-weight="700" text-anchor="middle">{int(val)}</text>')
    parts.append(draw(x0, bill, BILL))
    parts.append(draw(x0 + bw + gap, leader, LEADER))
    parts.append("</svg>")
    return "".join(parts)


_COMPASS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
               "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _compass_point(deg) -> str:
    """Return the 16-point compass label nearest to ``deg``."""
    return _COMPASS_16[round((deg % 360) / 22.5) % 16]


def wind_card(dir_deg, *, s=118, speed_kmh=None) -> str:
    """Compass card with an arrow pointing the way the wind blows (inward).

    Args:
        dir_deg: bearing the wind blows FROM (degrees).
        s: square SVG side length.
        speed_kmh: optional wind speed, included in the accessible name.

    Returns:
        str: inline SVG.
    """
    cx = cy = s / 2
    r = 40
    aria = f"Wind from {_compass_point(dir_deg)} {int(round(dir_deg)):03d} degrees"
    if isinstance(speed_kmh, (int, float)):
        aria += f" at {_fmt(speed_kmh, 1)} km/h"
    parts = [_open(s, s, aria)]
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
                 f'stroke="{HAIR}" stroke-width="1.4"/>')
    for i, lab in enumerate(["N", "E", "S", "W"]):
        a = i * 90 * math.pi / 180
        parts.append(f'<text x="{cx+math.sin(a)*(r+9):.1f}" '
                     f'y="{cy-math.cos(a)*(r+9)+3:.1f}" fill="{SEC}" font-size="8.5" '
                     f'text-anchor="middle">{lab}</text>')
    a = dir_deg * math.pi / 180
    tail_x, tail_y = cx + math.sin(a) * (r - 4), cy - math.cos(a) * (r - 4)
    head_x, head_y = cx + math.sin(a) * 8, cy - math.cos(a) * 8
    parts.append(f'<line x1="{tail_x:.1f}" y1="{tail_y:.1f}" x2="{head_x:.1f}" '
                 f'y2="{head_y:.1f}" stroke="{INK}" stroke-width="2.4" '
                 f'stroke-linecap="round"/>')
    dx, dy = head_x - tail_x, head_y - tail_y
    dl = math.hypot(dx, dy) or 1
    ux, uy = dx / dl, dy / dl
    px, py = -uy, ux
    ah = 6
    parts.append(f'<polygon points="{head_x:.1f},{head_y:.1f} '
                 f'{head_x-ux*ah+px*ah*0.6:.1f},{head_y-uy*ah+py*ah*0.6:.1f} '
                 f'{head_x-ux*ah-px*ah*0.6:.1f},{head_y-uy*ah-py*ah*0.6:.1f}" '
                 f'fill="{INK}"/>')
    parts.append("</svg>")
    return "".join(parts)


def solar_bar(rad, rad_min, rad_max, *, w=90, h=150) -> str:
    """Solar-radiation colour bar, height & colour normalised across all rounds.

    The bar height is proportional to the round's solar radiation normalised over
    all 17 rounds (a small bar still shows at the minimum); the solid fill
    interpolates deep red (at the event maximum) to pastel yellow (at the
    minimum). The value is printed beside the bar so the block is decodable on
    its own; the colour remains a relative lift proxy.

    Args:
        rad: this round's shortwave radiation.
        rad_min: minimum across all rounds.
        rad_max: maximum across all rounds.
        w: SVG width.
        h: SVG height.

    Returns:
        str: inline SVG.
    """
    span = (rad_max - rad_min) or 1
    norm = max(0.0, min(1.0, (rad - rad_min) / span))
    y_el = (250, 224, 139)   # pastel yellow (min)
    r_el = (176, 32, 32)     # deep red (max)

    def lerp(a, b):
        return round(a + (b - a) * norm)
    col = f"rgb({lerp(y_el[0], r_el[0])},{lerp(y_el[1], r_el[1])},{lerp(y_el[2], r_el[2])})"
    base, min_h, max_h, bw = 138, 16, 118, 44
    hh = min_h + norm * (max_h - min_h)
    aria = (f"Solar radiation {_fmt(rad, 0)} watts per square metre, "
            f"{norm*100:.0f}% of the event range "
            f"({_fmt(rad_min, 0)} to {_fmt(rad_max, 0)})")
    parts = [_open(w, h, aria)]
    parts.append(f'<rect x="4" y="{base-hh:.1f}" width="{bw}" '
                 f'height="{hh:.1f}" rx="4" fill="{col}"/>')
    parts.append(f'<text x="{4+bw+8}" y="{base-hh+13:.1f}" fill="{INK}" '
                 f'font-size="13" font-weight="700">{_fmt(rad, 0)}</text>')
    parts.append(f'<text x="{4+bw+8}" y="{base-hh+27:.1f}" fill="{SEC}" '
                 f'font-size="10">W/m²</text>')
    parts.append("</svg>")
    return "".join(parts)


def _open(w, h, label) -> str:
    """Open an accessible SVG element.

    Args:
        w: viewBox width.
        h: viewBox height.
        label: the accessible name. Each tile passes a sentence carrying its own
            values ("Entry speed: Bill 71 km/h versus leader 95 km/h, regs cap
            120 km/h"), so a screen reader announces the reading rather than the
            chart type.

    Returns:
        str: the opening ``<svg>`` tag.
    """
    return (f'<svg viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" '
            f'role="img" aria-label="{_esc(label)}" '
            f'xmlns="http://www.w3.org/2000/svg" font-family="inherit">')


# --- Number card (clean big number, no accent bar) -------------------------
def number_card(value, sub="") -> str:
    """Return a clean big-number block (no accent bar) with an optional sub-line.

    Args:
        value: the headline value (e.g. ``'2/10'``).
        sub: supporting line beneath (e.g. ``'10 pilots in group'``).

    Returns:
        str: an HTML fragment.
    """
    sub_html = f'<div class="dash-sub">{_esc(sub)}</div>' if sub else ""
    return f'<div class="dash-bignum">{_esc(value)}</div>{sub_html}'


# --- Cell + grid assembly ---------------------------------------------------
def _cell(title, body_html, *, cap="", sub="") -> str:
    """One dashboard grid cell: a small title, a body, and an optional caption."""
    cap_html = f'<div class="dash-cap">{_esc(cap)}</div>' if cap else ""
    sub_html = f'<div class="dash-sub">{_esc(sub)}</div>' if sub else ""
    return (f'<div class="dash-cell"><div class="dash-title">{_esc(title)}</div>'
            f'{body_html}{sub_html}{cap_html}</div>')


def _round_key(leader_name: str) -> str:
    """Return the top-right colour-key legend for a round dashboard."""
    return (
        '<div class="dash-key">'
        f'<span><i style="background:{BILL}"></i> Bill Maisey</span>'
        f'<span><i style="background:{LEADER}"></i> Round Leader '
        f'({_esc(leader_name)})</span>'
        f'<span><i style="background:{FIELD}"></i> Regs limit / Other pilots</span>'
        '</div>'
    )


def dashboard(round_data: dict) -> str:
    """Assemble the per-round visual-overview dashboard as an HTML fragment.

    Builds a 2-row x 4-col grid — row 1: group-score violin, entry-speed bullet,
    entry-altitude bullet, average (or single-lap) speed bullet; row 2: laps
    paired-bars, within-group rank number card, wind compass card, solar bar —
    with a top-right colour-key legend (green = Bill, blue = round leader, grey =
    regs limit / other pilots). Self-sufficient from a single round dataset: the
    group scores, wind and solar normalisation are pulled from the shared data
    loaders. Matches ``round_dashboard_v6``.

    Args:
        round_data: a full per-round dataset dict (as from
            :func:`data.load_round`).

    Returns:
        str: a captioned ``<figure>`` wrapping the ``<div class="dash-wrap">``
        grid, so the dashboard is one captioned figure like every other visual
        in the report. The styling classes are defined in :func:`design.css`.
    """
    from . import data as D

    n = round_data["round"]
    b = round_data["bill"]
    lead = round_data["leader"]
    is_speed = round_data.get("task_type") == "speedrun"
    leader_name = lead.get("name", "leader")

    scores = D.group_scores(round_data["group_id"])
    wind = D.wind_for_round(n) or {}
    weather = {row["round"]: row for row in D.load_weather_per_flight()}
    rads = [row["shortwave_radiation"] for row in weather.values()
            if isinstance(row.get("shortwave_radiation"), (int, float))]
    rad_min, rad_max = (min(rads), max(rads)) if rads else (0, 1)
    my_rad = weather.get(f"R{n:02d}", {}).get("shortwave_radiation", rad_min)

    avg_ceiling = math.ceil(max(b["speed_kmh"], lead["speed_kmh"]) * 1.1 / 10) * 10

    # --- row 1 ---
    row1 = [
        _cell("Group score", violin(scores, b["score"]),
              cap="Field score density. Winner 1000, Bill over the top."),
        _cell("Entry speed", bullet(b["entry_speed_kmh"], lead["entry_speed_kmh"],
                                    round_data["task"].get("max_entry_speed_kmh", 120),
                                    dec=1, label="Entry speed", unit="km/h",
                                    cap_note="regs cap"),
              cap="km/h at gate. Track top = 120 regs cap."),
        _cell("Entry altitude", bullet(b["entry_alt_m"], lead["entry_alt_m"],
                                       round_data["task"].get("max_entry_alt_m", 400),
                                       dec=0, label="Entry altitude", unit="m",
                                       cap_note="regs cap"),
              cap="m at gate. Track top = 400 regs cap."),
        _cell("Single-lap speed" if is_speed else "Average speed",
              bullet(b["speed_kmh"], lead["speed_kmh"], avg_ceiling, dec=1,
                     label="Single-lap speed" if is_speed else "Average speed",
                     unit="km/h", cap_note="chart ceiling"),
              cap=("km/h over the single run. No regs cap." if is_speed
                   else "km/h over task. No regs cap.")),
    ]
    # --- row 2 ---
    wind_body = (
        wind_card(wind.get("dir_deg", 0), speed_kmh=wind.get("speed_kmh"))
        + f'<div class="dash-sub"><span style="font-size:15px">'
          f'{_fmt(wind.get("speed_kmh", 0), 1)}</span> km/h</div>'
        + f'<div class="dash-sub">{_compass_point(wind.get("dir_deg", 0))} '
          f'{int(round(wind.get("dir_deg", 0))):03d}° from</div>'
    )
    row2 = [
        _cell("Laps", laps_bars(b["laps"], lead["laps"]), sub="Bill vs leader"),
        _cell("Within-group rank",
              number_card(f'{b["rank"]}/{round_data["group_size"]}',
                          sub=f'{round_data["group_size"]} pilots in group')),
        _cell("Wind", wind_body),
        _cell("Solar radiation", solar_bar(my_rad, rad_min, rad_max),
              sub="Relative to all 17 rounds · lift proxy"),
    ]
    grid = ("".join(row1) + '<div class="dash-divider"></div>' + "".join(row2))
    wrap = (
        '<div class="dash-wrap">'
        + _round_key(leader_name)
        + f'<div class="dash">{grid}</div>'
        + "</div>"
    )
    caption = (
        f"Round {n} at a glance: Bill (green) against his same-air round leader "
        f"{leader_name} (blue), with the regs limits and the rest of the group "
        f"in grey. Top row - group score density, entry speed and entry altitude "
        f"against their regulation caps, and "
        f"{'single-lap' if is_speed else 'average'} speed. Bottom row - laps, "
        f"{'field' if is_speed else 'within-group'} rank, the wind the round was "
        f"flown in, and solar radiation as a lift proxy relative to the other 16 "
        f"rounds. Each panel carries its own values."
    )
    return C.figure(wrap, caption, fig_id=f"r{n}-fig-dashboard",
                    source=(_EVENT_URL, "event results (rcmodelspot)"),
                    scroll=False)
