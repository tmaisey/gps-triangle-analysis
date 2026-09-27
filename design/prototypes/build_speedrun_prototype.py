"""Build a standalone PROTOTYPE of the SPEED-RUN dual-panel chart.

Prototype only (spec-free, under design/prototypes/). It does NOT touch the
main build (scripts/build/*) or docs. It renders a self-contained HTML page
with one inline SVG: a stacked dual-panel chart sharing ONE bottom x-axis of
RUN-RELATIVE time.

The speed task (rounds 4/10/16) is a single flat-out lap scored across the
field. Bill and the run leader fly their single runs at different absolute
clock times, so an absolute-time overlay puts them ~49 min apart. Fix here:
normalise each pilot's time to its own start-line crossing (T0 = the STA
event) so both single runs overlay for a like-for-like comparison.

Top panel (~80%): altitude (gpsAlt, m) vs run-time -- they trade height for
speed in the dive. Bottom panel (~20%): ground speed (km/h) vs run-time --
the point of the task (Bill ~109 vs leader ~155 km/h lap average).

Run with: uv run python design/prototypes/build_speedrun_prototype.py
"""

from __future__ import annotations

import datetime as dt
import html
import json
import math
from pathlib import Path

# --- Palette (brief / PRD tokens) -------------------------------------------
BILL_GUID = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"
C_BILL = "#86BC25"      # Bill (green)
C_LEADER = "#00A3E0"    # run leader (teal-blue)
C_INK = "#101820"       # primary text
C_SECOND = "#53565A"    # secondary text
C_HAIR = "#E4E4DF"      # hairline
C_BG = "#FFFFFF"        # white background
C_MUTED = "#75787B"

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "analysis" / "round_data" / "index.json"
TRACKS = ROOT / "data" / "tracks"
OUT = ROOT / "design" / "prototypes" / "speedrun_prototype.html"

# Preferred speed rounds, in order (R4 primary, R10/R16 fallback).
SPEED_ROUNDS = [4, 10, 16]


def _epoch(iso: str) -> float:
    """Parse an ISO-8601 'Z' timestamp to epoch seconds."""
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def _pilot_name(p: dict) -> str:
    pi = p["pilot"]
    return f"{pi.get('name', '')} {pi.get('surname', '')}".strip()


def _sta_time(p: dict) -> float | None:
    """Return T0 for a pilot: STA event, else first motor-off, else first point."""
    evs = p.get("events", [])
    sta = [e for e in evs if e.get("type") == "STA"]
    if sta:
        return _epoch(sta[0]["time"])
    # fallback: first motor-off (engineLevel drops to 0) then first track point
    tail = sorted(p["tail"], key=lambda r: _epoch(r["time"]))
    for r in tail:
        if r.get("engineLevel", 1) == 0:
            return _epoch(r["time"])
    return _epoch(tail[0]["time"]) if tail else None


def _sto_time(p: dict) -> float | None:
    evs = p.get("events", [])
    sto = [e for e in evs if e.get("type") == "STO"]
    return _epoch(sto[0]["time"]) if sto else None


def _interp(series: list[tuple[float, float]], t: float) -> float:
    """Linear-interpolate y at run-time t within a sorted (t, y) series."""
    if t <= series[0][0]:
        return series[0][1]
    if t >= series[-1][0]:
        return series[-1][1]
    for (t0, y0), (t1, y1) in zip(series, series[1:]):
        if t0 <= t <= t1:
            if t1 == t0:
                return y0
            return y0 + (y1 - y0) * (t - t0) / (t1 - t0)
    return series[-1][1]


def build_run(p: dict) -> dict:
    """Normalise one pilot's run to run-relative time from its start line.

    Returns run-relative (t, altitude) and (t, groundSpeed) series clipped to
    the [start-line, finish-line] window, with exact endpoints interpolated so
    every trace begins at t=0.
    """
    t0 = _sta_time(p)
    tsto = _sto_time(p)
    tail = sorted(p["tail"], key=lambda r: _epoch(r["time"]))
    alt_all = [(_epoch(r["time"]) - t0, float(r["gpsAlt"])) for r in tail]
    gs_all = [(_epoch(r["time"]) - t0, float(r["groundSpeed"])) for r in tail]
    # run window: start line (t=0) to finish line (STO), else to last point.
    t_end = (tsto - t0) if tsto else alt_all[-1][0]

    def clip(series: list[tuple[float, float]]) -> list[tuple[float, float]]:
        inner = [pt for pt in series if 0.0 <= pt[0] <= t_end]
        out = []
        # exact t=0 endpoint (interpolated) so both traces start together
        if not inner or inner[0][0] > 0.0:
            out.append((0.0, _interp(series, 0.0)))
        out.extend(inner)
        if not inner or inner[-1][0] < t_end:
            out.append((t_end, _interp(series, t_end)))
        return out

    return {
        "name": _pilot_name(p),
        "t0": t0,
        "t_end": t_end,
        "alt": clip(alt_all),
        "gs": clip(gs_all),
        "peak_gs": max(y for _, y in gs_all),
    }


def select_pilots(replay: list[dict], leader_name: str) -> tuple[dict, dict]:
    """Return (bill, leader) pilot dicts. Leader = named pilot, else fastest non-Bill."""
    bill = next(p for p in replay if p["pilot"]["userGuid"] == BILL_GUID)
    leader = None
    if leader_name:
        target = leader_name.strip().lower()
        for p in replay:
            if _pilot_name(p).strip().lower() == target:
                leader = p
                break
    if leader is None:  # fallback: fastest non-Bill by peak ground speed
        cands = [p for p in replay if p["pilot"]["userGuid"] != BILL_GUID]
        leader = max(cands, key=lambda p: max(r["groundSpeed"] for r in p["tail"]))
    return bill, leader


# --- SVG helpers ------------------------------------------------------------
def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _nice_ticks(dmin: float, dmax: float, n: int = 5) -> list[float]:
    if dmin == dmax:
        return [dmin]
    raw = (dmax - dmin) / n
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    step = mag
    for mult in (1, 2, 2.5, 5, 10):
        step = mult * mag
        if raw <= step:
            break
    start = math.floor(dmin / step) * step
    ticks, v = [], start
    while v <= dmax + step * 0.5:
        if v >= dmin - step * 0.5:
            ticks.append(round(v, 6))
        v += step
    return ticks


def _fmt(v: float) -> str:
    return str(int(v)) if v == int(v) else f"{v:.1f}"


def _polyline(pts: list[tuple[float, float]], color: str, width: float = 2.2) -> str:
    if not pts:
        return ""
    s = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return (
        f'<polyline points="{s}" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>'
    )


def render_svg(bill: dict, leader: dict) -> str:
    """Render the stacked dual-panel SVG (altitude over ground-speed, shared x)."""
    W = 920
    PL, PR = 68, 30          # left / right padding
    TITLE_H = 26             # headroom band for each panel's inline title
    TOP_T = 14               # top margin
    # panel geometry: altitude ~80%, ground speed ~20%, shared x underneath
    ALT_H = 360
    GAP = 34                 # vertical gap so panels never collide
    GS_H = 92
    X_AX = 40                # shared x-axis label band
    alt_top = TOP_T + TITLE_H
    alt_bot = alt_top + ALT_H
    gs_top = alt_bot + GAP + TITLE_H
    gs_bot = gs_top + GS_H
    H = gs_bot + X_AX

    # x scale: run-relative seconds, 0..max run duration across both pilots
    t_max = max(bill["t_end"], leader["t_end"])
    xs = lambda t: PL + (t / t_max) * (W - PL - PR) if t_max else PL

    # altitude y scale (shared min..max across both)
    alt_vals = [y for _, y in bill["alt"] + leader["alt"]]
    a_min, a_max = min(alt_vals), max(alt_vals)
    pad_a = (a_max - a_min) * 0.06 or 1
    a_lo, a_hi = a_min - pad_a, a_max + pad_a
    ys_alt = lambda v: alt_bot - (v - a_lo) / (a_hi - a_lo) * (alt_bot - alt_top)

    # ground speed y scale (compressed panel; baseline at 0)
    gs_vals = [y for _, y in bill["gs"] + leader["gs"]]
    g_max = max(gs_vals)
    g_hi = math.ceil(g_max / 20) * 20
    ys_gs = lambda v: gs_bot - (v / g_hi) * (gs_bot - gs_top)

    parts: list[str] = []
    parts.append(
        f'<svg viewBox="0 0 {W} {H}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="Speed-run altitude and ground speed vs run-relative time" '
        f'xmlns="http://www.w3.org/2000/svg" font-family="system-ui, sans-serif">'
    )
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{C_BG}"/>')

    # ---- ALTITUDE panel ----
    for tv in _nice_ticks(a_lo, a_hi):
        y = ys_alt(tv)
        parts.append(
            f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" '
            f'stroke="{C_HAIR}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{PL-9}" y="{y+4:.1f}" text-anchor="end" fill="{C_MUTED}" '
            f'font-size="11" font-variant-numeric="tabular-nums">{_fmt(tv)}</text>'
        )
    parts.append(
        f'<text x="16" y="{(alt_top+alt_bot)/2:.1f}" text-anchor="middle" '
        f'fill="{C_SECOND}" font-size="12.5" '
        f'transform="rotate(-90 16 {(alt_top+alt_bot)/2:.1f})">Altitude (m)</text>'
    )
    parts.append(
        f'<text x="{PL}" y="{alt_top-12}" fill="{C_INK}" font-size="13" '
        f'font-weight="600">Altitude &#8212; height traded for speed in the dive</text>'
    )
    parts.append(_polyline([(xs(t), ys_alt(v)) for t, v in leader["alt"]], C_LEADER))
    parts.append(_polyline([(xs(t), ys_alt(v)) for t, v in bill["alt"]], C_BILL))

    # ---- GROUND SPEED panel ----
    for tv in _nice_ticks(0, g_hi, 3):
        y = ys_gs(tv)
        parts.append(
            f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" '
            f'stroke="{C_HAIR}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{PL-9}" y="{y+4:.1f}" text-anchor="end" fill="{C_MUTED}" '
            f'font-size="11" font-variant-numeric="tabular-nums">{_fmt(tv)}</text>'
        )
    parts.append(
        f'<text x="16" y="{(gs_top+gs_bot)/2:.1f}" text-anchor="middle" '
        f'fill="{C_SECOND}" font-size="12.5" '
        f'transform="rotate(-90 16 {(gs_top+gs_bot)/2:.1f})">Speed (km/h)</text>'
    )
    parts.append(
        f'<text x="{PL}" y="{gs_top-8}" fill="{C_INK}" font-size="13" '
        f'font-weight="600">Ground speed &#8212; the point of the task</text>'
    )
    parts.append(_polyline([(xs(t), ys_gs(v)) for t, v in leader["gs"]], C_LEADER))
    parts.append(_polyline([(xs(t), ys_gs(v)) for t, v in bill["gs"]], C_BILL))

    # ---- SHARED x-axis (run-relative time, seconds) ----
    parts.append(
        f'<line x1="{PL}" y1="{gs_bot:.1f}" x2="{W-PR}" y2="{gs_bot:.1f}" '
        f'stroke="{C_SECOND}" stroke-width="1.4"/>'
    )
    for tv in _nice_ticks(0, t_max, 8):
        if tv < 0 or tv > t_max:
            continue
        x = xs(tv)
        parts.append(
            f'<line x1="{x:.1f}" y1="{gs_bot:.1f}" x2="{x:.1f}" y2="{gs_bot+5:.1f}" '
            f'stroke="{C_SECOND}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{gs_bot+19:.1f}" text-anchor="middle" '
            f'fill="{C_MUTED}" font-size="11" '
            f'font-variant-numeric="tabular-nums">{_fmt(tv)}</text>'
        )
    parts.append(
        f'<text x="{(PL+W-PR)/2:.1f}" y="{H-4}" text-anchor="middle" '
        f'fill="{C_SECOND}" font-size="12.5">Run time from start-line crossing (s)</text>'
    )
    # t=0 start-line marker across both panels
    parts.append(
        f'<line x1="{xs(0):.1f}" y1="{alt_top:.1f}" x2="{xs(0):.1f}" '
        f'y2="{gs_bot:.1f}" stroke="{C_HAIR}" stroke-width="1" stroke-dasharray="3 3"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def build_html(replay: list[dict], meta: dict) -> str:
    bill_p, leader_p = select_pilots(replay, meta["leader_name"])
    bill = build_run(bill_p)
    leader = build_run(leader_p)
    svg = render_svg(bill, leader)

    caption = (
        f"Round {meta['round']} (Heat {meta['round']}, group {meta['group_id']}) "
        f"&#8212; single flat-out speed lap. Each run normalised to its own "
        f"start-line crossing (T0 = STA), so the two runs overlay despite being "
        f"flown ~{meta['gap_min']} min apart on the clock. "
        f"Bill finished his lap in {bill['t_end']:.0f}s; "
        f"{leader['name']} in {leader['t_end']:.0f}s."
    )
    legend = (
        f'<span class="chip"><span class="sw" style="background:{C_BILL}"></span>'
        f'Bill Maisey &#183; {meta["bill_speed"]} km/h avg</span>'
        f'<span class="chip"><span class="sw" style="background:{C_LEADER}"></span>'
        f'{_esc(leader["name"])} (leader) &#183; {meta["leader_speed"]} km/h avg</span>'
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Speed-run prototype &#8212; R{meta['round']}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{
    margin: 0; background: {C_BG}; color: {C_INK};
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; padding: 32px 16px 48px; }}
  .eyebrow {{ font-size: 12px; letter-spacing: .08em; text-transform: uppercase;
    color: {C_MUTED}; margin: 0 0 6px; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .sub {{ color: {C_SECOND}; font-size: 14px; margin: 0 0 18px; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 18px; margin: 0 0 10px; }}
  .chip {{ display: inline-flex; align-items: center; gap: 8px; font-size: 13px;
    color: {C_INK}; font-variant-numeric: tabular-nums; }}
  .sw {{ width: 14px; height: 4px; border-radius: 2px; display: inline-block; }}
  .card {{ border: 1px solid {C_HAIR}; border-radius: 10px; padding: 14px 10px 6px;
    background: {C_BG}; }}
  figcaption {{ color: {C_SECOND}; font-size: 12.5px; line-height: 1.5;
    margin: 14px 2px 0; }}
  .note {{ color: {C_MUTED}; font-size: 12px; margin-top: 22px; }}
</style>
</head>
<body>
  <div class="wrap">
    <p class="eyebrow">GPS Triangle report &#183; prototype</p>
    <h1>Speed-run: altitude &amp; ground speed, overlaid on run time</h1>
    <p class="sub">Rounds 4 / 10 / 16 are the SPEED task &#8212; one flat-out lap
      scored across the 38-pilot field. This prototype shows R{meta['round']}.</p>
    <div class="legend">{legend}</div>
    <figure class="card" style="margin:0">
      {svg}
      <figcaption>{caption}</figcaption>
    </figure>
    <p class="note">Prototype only (spec-free). Not wired into the build.
      Design mirrors the endurance energy chart: stacked panels, one shared
      run-relative x-axis, altitude ~80% over ground speed ~20%.</p>
  </div>
</body>
</html>
"""


def main() -> None:
    index = json.loads(INDEX.read_text())
    by_round = {r["round"]: r for r in index}
    chosen = None
    for rn in SPEED_ROUNDS:
        r = by_round.get(rn)
        if r and (TRACKS / f"replay_{r['group_id']}.json").exists():
            chosen = r
            break
    if chosen is None:
        raise SystemExit("No speed round track available")

    replay = json.loads((TRACKS / f"replay_{chosen['group_id']}.json").read_text())
    bill_p, leader_p = select_pilots(replay, chosen["leader_name"])
    gap_min = round(abs(_sta_time(leader_p) - _sta_time(bill_p)) / 60.0)
    meta = {
        "round": chosen["round"],
        "group_id": chosen["group_id"],
        "leader_name": chosen["leader_name"],
        "bill_speed": chosen["bill"]["speed_kmh"],
        "leader_speed": chosen["leader"]["speed_kmh"],
        "gap_min": gap_min,
    }
    OUT.write_text(build_html(replay, meta))
    print(f"Wrote {OUT}")
    print(f"Round {meta['round']} group {meta['group_id']} | Bill vs {meta['leader_name']}")
    print(f"Absolute-clock gap between the two runs: ~{gap_min} min (overlaid at t=0)")


if __name__ == "__main__":
    main()
