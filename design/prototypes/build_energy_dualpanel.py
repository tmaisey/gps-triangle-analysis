"""Prototype builder: dual-panel "energy" chart (altitude + ground speed) for the GPS Triangle report.

Standalone design prototype (spec-free). Reads a cached replay, extracts Bill's and the
same-air leader's tracks, aligns time to run-relative T0 (the scored start-line crossing),
and emits a self-contained inline-SVG HTML page under design/prototypes/.

Not part of the main build. Does not touch scripts/build/* or docs/*.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# --- Configuration ------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
GROUP_ID = 5719  # Round 6, triangle, Bill 10 laps @42 vs leader 16 @57 km/h
BILL_GUID = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"
LEADER_NAME = ("Oliver", "Ladach")  # same-air leader from analysis/round_data/index.json
OUT = ROOT / "design" / "prototypes" / "energy_dualpanel_prototype.html"

# Palette (brand-locked)
BILL = "#86BC25"
LEADER = "#00A3E0"
INK = "#101820"
MUTE = "#53565A"
HAIR = "#E4E4DF"
BG = "#FFFFFF"


def parse_t(s: str) -> datetime:
    """Parse an ISO-8601 timestamp with a trailing Z into a naive UTC datetime.

    Args:
        s: ISO timestamp, possibly with a 'Z' suffix and fractional seconds.

    Returns:
        Parsed datetime.
    """
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


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


def race_end(events: list[dict], t0: datetime) -> float:
    """Return the racing-phase end in run-relative minutes (STO event, else last event)."""
    sto = [parse_t(e["time"]) for e in events if e["type"] == "STO"]
    end_dt = sto[-1] if sto else parse_t(events[-1]["time"])
    return (end_dt - t0).total_seconds() / 60.0


def series(pilot: dict) -> dict:
    """Build a run-relative series (minutes, gpsAlt, groundSpeed) for the racing phase.

    Full resolution: every tail sample from T0 to the racing-phase end, no downsampling.

    Args:
        pilot: a replay pilot dict.

    Returns:
        dict with name, minutes/alt/speed lists, and summary ranges.
    """
    t0 = scored_start(pilot["events"])
    t_end = race_end(pilot["events"], t0)
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
        "spd": spd,
        "t_end": t_end,
    }


def nice_step(span: float, target: int = 5) -> float:
    """Return a 1/2/5 x 10^k step giving roughly `target` ticks over `span`."""
    import math

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
    # pad altitude a touch
    pad = (alt_hi - alt_lo) * 0.06
    alt_lo, alt_hi = alt_lo - pad, alt_hi + pad
    spd_hi = max(all_spd) * 1.08

    # --- Geometry -------------------------------------------------------------
    W, H = 980, 580
    ml, mr, mt, mb = 62, 96, 18, 52
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
               f'aria-label="Dual-panel energy chart: altitude and ground speed vs run time" '
               f'font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">')
    svg.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>')

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
    import math
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
    svg.append(f'<text x="{(plot_x0 + plot_x1) / 2:.1f}" y="{H - 6}" text-anchor="middle" '
               f'font-size="12" fill="{INK}">Minutes since start-line crossing (T0)</text>')

    # --- Panel titles (rotated, left) -----------------------------------------
    svg.append(f'<text x="16" y="{(alt_y0 + alt_y1) / 2:.1f}" text-anchor="middle" '
               f'font-size="12" fill="{INK}" transform="rotate(-90 16 {(alt_y0 + alt_y1) / 2:.1f})">'
               f'Altitude (m)</text>')
    svg.append(f'<text x="16" y="{(spd_y0 + spd_y1) / 2:.1f}" text-anchor="middle" '
               f'font-size="12" fill="{INK}" transform="rotate(-90 16 {(spd_y0 + spd_y1) / 2:.1f})">'
               f'Speed (km/h)</text>')

    # small in-panel captions
    svg.append(f'<text x="{plot_x0 + 6}" y="{alt_y0 + 14}" font-size="11" fill="{MUTE}">'
               f'ALTITUDE</text>')
    svg.append(f'<text x="{plot_x0 + 6}" y="{spd_y0 + 13}" font-size="11" fill="{MUTE}">'
               f'GROUND SPEED</text>')

    # --- Data lines -----------------------------------------------------------
    for sdat, color in ((s_lead, LEADER), (s_bill, BILL)):
        svg.append(f'<polyline points="{path_pts(sdat["mins"], sdat["alt"], sy_alt)}" '
                   f'fill="none" stroke="{color}" stroke-width="2" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
        svg.append(f'<polyline points="{path_pts(sdat["mins"], sdat["spd"], sy_spd)}" '
                   f'fill="none" stroke="{color}" stroke-width="2" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')

    # --- Direct labels at line ends (altitude panel) --------------------------
    for sdat, color in ((s_lead, LEADER), (s_bill, BILL)):
        lx = sx(sdat["mins"][-1])
        ly = sy_alt(sdat["alt"][-1])
        svg.append(f'<text x="{min(lx + 8, plot_x1 + 6):.1f}" y="{ly + 3.5:.1f}" '
                   f'font-size="12" font-weight="600" fill="{color}">{sdat["first"]}</text>')

    # --- Legend (top-right of altitude panel) ---------------------------------
    lgx, lgy = plot_x1 - 4, alt_y0 + 6
    for i, (sdat, color) in enumerate(((s_bill, BILL), (s_lead, LEADER))):
        yy = lgy + i * 18
        svg.append(f'<line x1="{lgx - 150}" y1="{yy}" x2="{lgx - 130}" y2="{yy}" '
                   f'stroke="{color}" stroke-width="3"/>')
        svg.append(f'<text x="{lgx - 124}" y="{yy + 4}" font-size="12" fill="{INK}">'
                   f'{sdat["name"]}</text>')

    svg.append('</svg>')
    svg_str = "\n".join(svg)

    # --- Diagnostics ----------------------------------------------------------
    print(f"Round 6 (group {GROUP_ID}) — Bill Maisey vs Oliver Ladach (same-air leader)")
    print(f"  Bill:   {len(s_bill['mins'])} samples, race {s_bill['t_end']:.1f} min, "
          f"alt {min(s_bill['alt']):.0f}-{max(s_bill['alt']):.0f} m, "
          f"spd 0-{max(s_bill['spd']):.0f} km/h")
    print(f"  Oliver: {len(s_lead['mins'])} samples, race {s_lead['t_end']:.1f} min, "
          f"alt {min(s_lead['alt']):.0f}-{max(s_lead['alt']):.0f} m, "
          f"spd 0-{max(s_lead['spd']):.0f} km/h")
    print(f"  Shared x: 0-{x_max:.1f} min | alt y: {alt_lo:.0f}-{alt_hi:.0f} m | "
          f"spd y: 0-{spd_hi:.0f} km/h")

    # --- HTML shell -----------------------------------------------------------
    caption = (
        f"Round 6 (Heat 6, group {GROUP_ID}) — GPS Triangle. "
        f"Full-resolution GPS tracks, time aligned to each pilot's scored start-line "
        f"crossing (T0 = 0 min). Bill Maisey (10 laps, 42 km/h avg) vs same-air leader "
        f"Oliver Ladach (16 laps, 57 km/h avg). Top panel: altitude. Bottom panel: "
        f"ground speed (compressed). Shared time axis."
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Energy Dual-Panel</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; background: {BG}; color: {INK};
         font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
  .wrap {{ max-width: 1040px; margin: 0 auto; padding: 32px 16px 48px; }}
  h1 {{ font-size: 20px; font-weight: 600; margin: 0 0 4px; }}
  .sub {{ color: {MUTE}; font-size: 13px; margin: 0 0 20px; }}
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
    <h1>Energy picture — altitude &amp; ground speed</h1>
    <p class="sub">Dual-panel prototype · shared run-relative time axis</p>
    <figure>
      {svg_str}
      <figcaption>{caption}</figcaption>
    </figure>
    <div class="note">
      <b>Prototype note.</b> Round 6 chosen for its clear speed contrast so the compressed
      speed panel earns its place. Leader is the same-air pilot from
      <code>analysis/round_data/index.json</code>. T0 is each pilot's scored start-line
      crossing (STA), so the racing phase begins at 0 min; pre-start warm-up is clipped.
      Full resolution — no downsampling. Design-approval prototype only; not the final build.
    </div>
  </div>
</body>
</html>
"""
    OUT.write_text(html)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
