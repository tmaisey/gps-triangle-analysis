"""Prototype builder (v2): "Energy Management" dual-panel chart for the GPS Triangle report.

Standalone design prototype (spec-free). Reads a cached replay, extracts Bill's and the
same-air leader's tracks, aligns time to run-relative T0 (the scored start-line crossing),
clips the window at each pilot's last turn-point crossing (so the final descent/rollout does
not clutter the right edge), lightly smooths the ground-speed panel only, and emits a
self-contained inline-SVG HTML page under design/prototypes/.

Refinements over energy_dualpanel_prototype.html (Round 6, group 5719):
  1. Single figure title "Energy Management"; no per-subplot captions (y-axis labels suffice).
  2. No line-end labels; one legend (Bill / Leader); solid lines.
  3. Light rolling-mean smoothing on the SPEED panel only (~5 s); altitude stays full-res.
  4. Window clipped at each pilot's last turn-point crossing (TPC), not the STO/landing.
  5. Shared single x-axis, labelled once at the bottom (relative flight time, minutes).

Not part of the main build. Does not touch scripts/build/* or docs/*.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

# --- Configuration ------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
GROUP_ID = 5719  # Round 6, triangle, Bill 10 laps @42 vs leader 16 @57 km/h
BILL_GUID = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"
LEADER_NAME = ("Oliver", "Ladach")  # same-air leader from analysis/round_data/index.json
OUT = ROOT / "design" / "prototypes" / "energy_management_v2.html"

SPEED_SMOOTH_WINDOW = 5  # samples (~5 s at 1 Hz); odd = centred

# Palette (brand-locked)
BILL = "#86BC25"
LEADER = "#00A3E0"
INK = "#101820"
MUTE = "#53565A"
HAIR = "#E4E4DF"
BG = "#FFFFFF"


def parse_t(s: str) -> datetime:
    """Parse an ISO-8601 timestamp with a trailing Z into an aware UTC datetime.

    Args:
        s: ISO timestamp, possibly with a 'Z' suffix and fractional seconds.

    Returns:
        Parsed datetime.
    """
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def scored_start(events: list[dict]) -> datetime:
    """Return the run-relative T0: the start-line crossing that began the scored run.

    Multistart replays contain several ARM/STA cycles; the scored run is the one whose
    lap-bearing flightStat carries the most laps. Its flightStart is the definitive T0.
    Falls back to the last STA event time.

    Args:
        events: pilot event list.

    Returns:
        Datetime of the scored start-line crossing.
    """
    best_laps = -1
    best_start: datetime | None = None
    for e in events:
        fs = e.get("flightStat")
        if fs and fs.get("laps", 0) >= best_laps and fs.get("flightStart"):
            best_laps = fs["laps"]
            best_start = parse_t(fs["flightStart"])
    if best_start is not None:
        return best_start
    stas = [parse_t(e["time"]) for e in events if e["type"] == "STA"]
    return stas[-1]


def last_turnpoint_end(events: list[dict], t0: datetime) -> float:
    """Return the racing-phase end in run-relative minutes: the last turn-point crossing.

    Clipping at the final TPC (rather than the STO/landing or the last tail sample) keeps
    the final descent and ground rollout out of the window, so the altitude floor is not
    dragged down and the right edge stays clean.

    Args:
        events: pilot event list.
        t0: run-relative zero (scored start-line crossing).

    Returns:
        Run-relative minutes of the last turn-point crossing after T0.
    """
    tpc = [parse_t(e["time"]) for e in events if e["type"] == "TPC"]
    tpc = [t for t in tpc if (t - t0).total_seconds() >= 0]
    end_dt = max(tpc) if tpc else parse_t(events[-1]["time"])
    return (end_dt - t0).total_seconds() / 60.0


def rolling_mean(vals: list[float], window: int) -> list[float]:
    """Return a centred simple rolling mean of `vals` with an odd `window` (edge-shrinking).

    Near the ends the window shrinks to the samples available, so the series keeps its
    length and endpoints stay anchored to real data.

    Args:
        vals: input series.
        window: number of samples in the (odd) smoothing window.

    Returns:
        Smoothed series, same length as `vals`.
    """
    if window <= 1 or len(vals) < 3:
        return list(vals)
    half = window // 2
    out = []
    n = len(vals)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        out.append(sum(vals[lo:hi]) / (hi - lo))
    return out


def series(pilot: dict) -> dict:
    """Build a run-relative series (minutes, gpsAlt, groundSpeed) clipped at the last TPC.

    Altitude is full resolution; ground speed is lightly smoothed (rolling mean) so the
    1 Hz spikes read cleanly.

    Args:
        pilot: a replay pilot dict.

    Returns:
        dict with name, minutes/alt/speed lists (speed smoothed), and the clip end.
    """
    t0 = scored_start(pilot["events"])
    t_end = last_turnpoint_end(pilot["events"], t0)
    mins, alt, spd = [], [], []
    for pt in pilot["tail"]:
        m = (parse_t(pt["time"]) - t0).total_seconds() / 60.0
        if m < 0 or m > t_end + 0.01:
            continue
        mins.append(m)
        alt.append(float(pt["gpsAlt"]))
        spd.append(float(pt["groundSpeed"]))
    return {
        "name": f"{pilot['pilot']['name']} {pilot['pilot']['surname']}",
        "first": pilot["pilot"]["name"],
        "mins": mins,
        "alt": alt,
        "spd_raw": spd,
        "spd": rolling_mean(spd, SPEED_SMOOTH_WINDOW),
        "t_end": t_end,
    }


def nice_step(span: float, target: int = 5) -> float:
    """Return a 1/2/5 x 10^k step giving roughly `target` ticks over `span`."""
    raw = span / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if m * mag >= raw:
            return m * mag
    return 10 * mag


def main() -> None:
    """Load the replay, build both series, render the dual-panel SVG, write the HTML."""
    replay = json.loads((ROOT / "data" / "tracks" / f"replay_{GROUP_ID}.json").read_text())

    bill = next(p for p in replay if p["pilot"]["userGuid"] == BILL_GUID)
    leader = next(
        p for p in replay
        if p["pilot"]["name"] == LEADER_NAME[0] and p["pilot"]["surname"] == LEADER_NAME[1]
    )
    s_bill = series(bill)
    s_lead = series(leader)

    # --- Shared scales --------------------------------------------------------
    x_max = max(s_bill["t_end"], s_lead["t_end"])
    all_alt = s_bill["alt"] + s_lead["alt"]
    all_spd = s_bill["spd"] + s_lead["spd"]
    alt_lo, alt_hi = min(all_alt), max(all_alt)
    pad = (alt_hi - alt_lo) * 0.06
    alt_lo, alt_hi = alt_lo - pad, alt_hi + pad
    spd_hi = max(all_spd) * 1.10

    # --- Geometry -------------------------------------------------------------
    W, H = 980, 600
    ml, mr, mt, mb = 64, 24, 44, 54
    inner_gap = 30
    plot_x0, plot_x1 = ml, W - mr
    plot_y0, plot_y1 = mt, H - mb
    total_h = plot_y1 - plot_y0 - inner_gap
    alt_h = total_h * 0.80
    spd_h = total_h * 0.20
    alt_y0, alt_y1 = plot_y0, plot_y0 + alt_h
    spd_y0, spd_y1 = alt_y1 + inner_gap, plot_y1

    def sx(m: float) -> float:
        return plot_x0 + (m / x_max) * (plot_x1 - plot_x0)

    def sy_alt(v: float) -> float:
        return alt_y1 - (v - alt_lo) / (alt_hi - alt_lo) * (alt_y1 - alt_y0)

    def sy_spd(v: float) -> float:
        return spd_y1 - (v / spd_hi) * (spd_y1 - spd_y0)

    def path_pts(mins, vals, yf) -> str:
        return " ".join(f"{sx(m):.1f},{yf(v):.1f}" for m, v in zip(mins, vals))

    svg = []
    svg.append(f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
               f'aria-label="Energy Management: altitude and ground speed versus relative flight time" '
               f'font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">')
    svg.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>')

    # --- Figure title ---------------------------------------------------------
    svg.append(f'<text x="{plot_x0}" y="26" font-size="19" font-weight="600" '
               f'fill="{INK}">Energy Management</text>')

    # --- Gridlines (shared x, drawn across both panels for alignment) ---------
    xstep = nice_step(x_max, 6)
    xt = 0.0
    xticks = []
    while xt <= x_max + 1e-6:
        xticks.append(xt)
        xt += xstep
    for xt in xticks:
        x = sx(xt)
        svg.append(f'<line x1="{x:.1f}" y1="{alt_y0}" x2="{x:.1f}" y2="{alt_y1}" '
                   f'stroke="{HAIR}" stroke-width="1"/>')
        svg.append(f'<line x1="{x:.1f}" y1="{spd_y0}" x2="{x:.1f}" y2="{spd_y1}" '
                   f'stroke="{HAIR}" stroke-width="1"/>')

    # altitude horizontal gridlines + labels
    astep = nice_step(alt_hi - alt_lo, 5)
    a = math.ceil(alt_lo / astep) * astep
    while a <= alt_hi:
        y = sy_alt(a)
        svg.append(f'<line x1="{plot_x0}" y1="{y:.1f}" x2="{plot_x1}" y2="{y:.1f}" '
                   f'stroke="{HAIR}" stroke-width="1"/>')
        svg.append(f'<text x="{plot_x0 - 8:.1f}" y="{y + 3.5:.1f}" text-anchor="end" '
                   f'font-size="11" fill="{MUTE}">{int(a)}</text>')
        a += astep

    # speed horizontal gridlines + labels (compressed panel: baseline + a couple)
    sstep = nice_step(spd_hi, 3)
    s = 0.0
    while s <= spd_hi:
        y = sy_spd(s)
        svg.append(f'<line x1="{plot_x0}" y1="{y:.1f}" x2="{plot_x1}" y2="{y:.1f}" '
                   f'stroke="{HAIR}" stroke-width="1"/>')
        svg.append(f'<text x="{plot_x0 - 8:.1f}" y="{y + 3.5:.1f}" text-anchor="end" '
                   f'font-size="11" fill="{MUTE}">{int(s)}</text>')
        s += sstep

    # --- Panel frames (left + baseline axis, recessive) -----------------------
    for y0, y1 in ((alt_y0, alt_y1), (spd_y0, spd_y1)):
        svg.append(f'<line x1="{plot_x0}" y1="{y0}" x2="{plot_x0}" y2="{y1}" '
                   f'stroke="{MUTE}" stroke-width="1"/>')
    # shared x baseline under speed panel
    svg.append(f'<line x1="{plot_x0}" y1="{spd_y1}" x2="{plot_x1}" y2="{spd_y1}" '
               f'stroke="{MUTE}" stroke-width="1"/>')

    # --- x tick labels (once, under bottom panel) -----------------------------
    for xt in xticks:
        x = sx(xt)
        svg.append(f'<text x="{x:.1f}" y="{spd_y1 + 16:.1f}" text-anchor="middle" '
                   f'font-size="11" fill="{MUTE}">{xt:g}</text>')
    svg.append(f'<text x="{(plot_x0 + plot_x1) / 2:.1f}" y="{H - 8}" text-anchor="middle" '
               f'font-size="12.5" fill="{INK}">Relative flight time (minutes since scored '
               f'start-line crossing)</text>')

    # --- y-axis labels (rotated, left) — these name each panel ----------------
    svg.append(f'<text x="16" y="{(alt_y0 + alt_y1) / 2:.1f}" text-anchor="middle" '
               f'font-size="12.5" fill="{INK}" transform="rotate(-90 16 {(alt_y0 + alt_y1) / 2:.1f})">'
               f'Altitude (m)</text>')
    svg.append(f'<text x="16" y="{(spd_y0 + spd_y1) / 2:.1f}" text-anchor="middle" '
               f'font-size="12.5" fill="{INK}" transform="rotate(-90 16 {(spd_y0 + spd_y1) / 2:.1f})">'
               f'Ground speed (km/h)</text>')

    # --- Data lines (solid) ---------------------------------------------------
    for sdat, color in ((s_lead, LEADER), (s_bill, BILL)):
        svg.append(f'<polyline points="{path_pts(sdat["mins"], sdat["alt"], sy_alt)}" '
                   f'fill="none" stroke="{color}" stroke-width="2" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
        svg.append(f'<polyline points="{path_pts(sdat["mins"], sdat["spd"], sy_spd)}" '
                   f'fill="none" stroke="{color}" stroke-width="1.8" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')

    # --- Single legend (top-right of altitude panel) --------------------------
    entries = [(f'Bill Maisey', BILL), (f'Oliver Ladach (leader)', LEADER)]
    box_w, row_h = 190, 18
    lgx0 = plot_x1 - box_w - 8
    lgy0 = alt_y0 + 10
    svg.append(f'<rect x="{lgx0}" y="{lgy0}" width="{box_w}" height="{row_h * len(entries) + 8}" '
               f'rx="4" fill="{BG}" fill-opacity="0.85" stroke="{HAIR}" stroke-width="1"/>')
    for i, (label, color) in enumerate(entries):
        yy = lgy0 + 14 + i * row_h
        svg.append(f'<line x1="{lgx0 + 10}" y1="{yy}" x2="{lgx0 + 30}" y2="{yy}" '
                   f'stroke="{color}" stroke-width="3"/>')
        svg.append(f'<text x="{lgx0 + 38}" y="{yy + 4}" font-size="12" fill="{INK}">'
                   f'{label}</text>')

    svg.append('</svg>')
    svg_str = "\n".join(svg)

    # --- Diagnostics ----------------------------------------------------------
    print(f"Round 6 (group {GROUP_ID}) — Bill Maisey vs Oliver Ladach (same-air leader)")
    print(f"  Bill:   {len(s_bill['mins'])} samples, clip {s_bill['t_end']:.1f} min, "
          f"alt {min(s_bill['alt']):.0f}-{max(s_bill['alt']):.0f} m, "
          f"spd(smoothed) 0-{max(s_bill['spd']):.0f} km/h")
    print(f"  Oliver: {len(s_lead['mins'])} samples, clip {s_lead['t_end']:.1f} min, "
          f"alt {min(s_lead['alt']):.0f}-{max(s_lead['alt']):.0f} m, "
          f"spd(smoothed) 0-{max(s_lead['spd']):.0f} km/h")
    print(f"  Shared x: 0-{x_max:.1f} min | alt y: {alt_lo:.0f}-{alt_hi:.0f} m | "
          f"spd y: 0-{spd_hi:.0f} km/h | speed smoothing window {SPEED_SMOOTH_WINDOW} samples")

    # --- HTML shell -----------------------------------------------------------
    caption = (
        f"Round 6 (Heat 6, group {GROUP_ID}), GPS Triangle. Time is aligned to each pilot's "
        f"scored start-line crossing (T0 = 0 min) and the window is clipped at each pilot's "
        f"last turn-point crossing, so the final descent and rollout are excluded. "
        f"Bill Maisey (10 laps, 42 km/h avg) versus same-air leader Oliver Ladach "
        f"(16 laps, 57 km/h avg). Altitude is shown at full GPS resolution; ground speed is "
        f"lightly smoothed (about a 5-second rolling mean) to settle the 1 Hz sampling noise."
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Energy Management</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; background: {BG}; color: {INK};
         font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
  .wrap {{ max-width: 1040px; margin: 0 auto; padding: 32px 16px 48px; }}
  figure {{ margin: 0; }}
  figcaption {{ color: {MUTE}; font-size: 12.5px; line-height: 1.5;
               margin-top: 14px; max-width: 900px; }}
  .note {{ background: #F7F7F4; border: 1px solid {HAIR}; border-radius: 8px;
          padding: 12px 16px; font-size: 12.5px; color: {MUTE};
          margin-top: 24px; line-height: 1.55; }}
  .note b {{ color: {INK}; }}
</style>
</head>
<body>
  <div class="wrap">
    <figure>
      {svg_str}
      <figcaption>{caption}</figcaption>
    </figure>
    <div class="note">
      <b>Prototype note.</b> Round 6 chosen for its clear speed contrast so the compressed
      speed panel earns its place. Leader is the same-air pilot from
      <code>analysis/round_data/index.json</code>. Design-approval prototype only; not the
      final build.
    </div>
  </div>
</body>
</html>
"""
    OUT.write_text(html)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
