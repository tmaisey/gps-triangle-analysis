"""Sanity-check ERA5 wind against Bill's GPS ground-track drift (optional).

For the two flights where Bill's GPS tail is available (group 5769 = Heat 12,
group 5815 = Heat 17), estimates wind from the groundspeed-vs-heading signature:
a glider at ~constant airspeed shows peak groundspeed flying downwind and trough
upwind, so wind_speed ~ (Vmax - Vmin)/2 and wind-FROM ~ heading of minimum
groundspeed. Compared to ERA5 as a rough sanity note only (glider airspeed is
not constant, so this is indicative, not authoritative).
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BILL = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"
REPLAYS = {"data/tracks/replay_5769.json": "Heat 12 (R12)",
           "data/tracks/replay_5815.json": "Heat 17 (R17)"}
# ERA5 at the mapped start hour (from weather_per_flight output / raw JSON)
ERA5 = {"Heat 12 (R12)": (16.9, None), "Heat 17 (R17)": (8.3, None)}


def haversine(a, b):
    """Great-circle distance in metres between (lat,lon) tuples."""
    R = 6371000
    dlat = math.radians(b[0] - a[0])
    dlon = math.radians(b[1] - a[1])
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def bearing(a, b):
    """Initial compass bearing (deg) from point a to point b."""
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    x = math.sin(dlon) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def main():
    """Estimate and print GPS-derived wind for each tracked Bill flight."""
    for path, label in REPLAYS.items():
        d = json.load(open(ROOT / path))
        entry = next((e for e in d if (e.get("pilot") or {}).get("userGuid") == BILL), None)
        tail = entry["tail"]
        # per-segment groundspeed & heading
        bins = {i: [] for i in range(12)}  # 30-deg bins
        gs_all = []
        for p, q in zip(tail, tail[1:]):
            t0 = p["time"]; t1 = q["time"]
            from datetime import datetime
            dt = (datetime.fromisoformat(t1.replace("Z", "+00:00")) -
                  datetime.fromisoformat(t0.replace("Z", "+00:00"))).total_seconds()
            if dt <= 0:
                continue
            A = (p["latitude"], p["longitude"]); B = (q["latitude"], q["longitude"])
            dist = haversine(A, B)
            gs = dist / dt  # m/s
            if gs < 2 or gs > 80:  # drop stationary/GPS-glitch segments
                continue
            hd = bearing(A, B)
            bins[int(hd // 30) % 12].append(gs)
            gs_all.append(gs)
        means = {i: (sum(v) / len(v)) for i, v in bins.items() if v}
        if len(means) < 6:
            print(f"{label}: too few heading bins ({len(means)}); skip")
            continue
        vmax_bin = max(means, key=means.get)
        vmin_bin = min(means, key=means.get)
        vmax, vmin = means[vmax_bin], means[vmin_bin]
        wind_ms = (vmax - vmin) / 2
        wind_kmh = wind_ms * 3.6
        # wind FROM ~ heading of minimum groundspeed (flying into wind)
        wind_from = (vmin_bin * 30 + 15)
        era = ERA5[label][0]
        print(f"\n{label}: {len(gs_all)} segments, mean GS {sum(gs_all)/len(gs_all)*3.6:.1f} km/h")
        print(f"  GS peak {vmax*3.6:.1f} km/h heading ~{vmax_bin*30+15}deg (downwind); "
              f"trough {vmin*3.6:.1f} km/h heading ~{vmin_bin*30+15}deg (upwind)")
        print(f"  GPS-derived wind ~ {wind_kmh:.1f} km/h FROM ~{wind_from:.0f}deg")
        print(f"  ERA5 wind at start hour: {era} km/h  ->  ratio GPS/ERA5 = {wind_kmh/era:.2f}")


if __name__ == "__main__":
    main()
