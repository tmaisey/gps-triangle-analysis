"""Map Bill Maisey's 17 flights to ERA5 weather at each flight's start hour.

Reads the competition results tree and the raw ERA5 JSON, extracts every group
Bill flew in (heat, group start/end, laps, speed, scores, within-group rank,
field size, and the group leader's laps/speed by top rawScore), converts each
group's UTC start time to Europe/Berlin local, snaps to the nearest hour, and
joins the hourly weather. Writes ``analysis/weather_per_flight.csv`` plus a
richer ``analysis/bill_flights_weather_full.csv`` for downstream analysis.

CAPE is requested from the archive but ERA5 returns it null for every hour of
the event, so it is not carried into either CSV; boundary-layer height is the
secondary thermal proxy alongside shortwave radiation.
"""
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "scores" / "results.json"
WEATHER = ROOT / "data" / "weather_era5_oschatz.json"
OUT_MAIN = ROOT / "analysis" / "weather_per_flight.csv"
OUT_FULL = ROOT / "analysis" / "bill_flights_weather_full.csv"

BILL = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"


def load_weather_index(wx):
    """Build a dict from Berlin-local hour-string to a weather record.

    Args:
        wx: Decoded Open-Meteo archive JSON.

    Returns:
        Tuple ``(index, offset_seconds)`` where ``index`` maps ``"YYYY-MM-DDTHH:00"``
        (local) to a dict of variable->value, and ``offset_seconds`` is the site's
        UTC offset used to align flight times to the local hourly grid.
    """
    h = wx["hourly"]
    times = h["time"]
    varnames = [k for k in h if k != "time"]
    index = {}
    for i, t in enumerate(times):
        index[t] = {v: h[v][i] for v in varnames}
    return index, wx["utc_offset_seconds"]


def nearest_hour_local(start_utc_str, offset_s):
    """Convert a UTC ISO start time to the nearest local hour key.

    Args:
        start_utc_str: e.g. ``"2026-08-03T09:00:00Z"``.
        offset_s: Site UTC offset in seconds (from the weather payload).

    Returns:
        Tuple ``(local_dt, hour_key)`` where ``hour_key`` matches the hourly grid.
    """
    utc = datetime.fromisoformat(start_utc_str.replace("Z", "+00:00"))
    local = utc.astimezone(timezone(timedelta(seconds=offset_s)))
    rounded = (local + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
    return local, rounded.strftime("%Y-%m-%dT%H:00")


def extract_flights(d):
    """Extract Bill's per-flight records with same-air leader benchmarks.

    Args:
        d: Decoded results.json.

    Returns:
        List of dicts, one per heat Bill flew, ordered by heat order.
    """
    heats = sorted(d["competitionGpsTriangleHeat"], key=lambda h: h["order"])
    flights = []
    for heat in heats:
        for g in heat["competitionGpsTriangleGroup"]:
            res = g["competitionGpsTriangleResult"]
            bill = next((r for r in res if r["userGuid"] == BILL), None)
            if not bill:
                continue
            # within-group rank by normalised score desc (tie-break rawScore)
            ranked = sorted(res, key=lambda r: (r["score"], r["rawScore"]), reverse=True)
            rank = ranked.index(bill) + 1
            # leader = top rawScore in the group (same-air benchmark)
            leader = max(res, key=lambda r: r["rawScore"])
            task_type = "speed" if heat["name"].split()[-1] in ("4", "10", "16") else "distance"
            flights.append({
                "heat": heat["name"],
                "heat_order": heat["order"],
                "task_type": task_type,
                "group": g["name"],
                "group_size": len(res),
                "start_utc": g["startTime"],
                "end_utc": g["endTime"],
                "laps": bill["laps"],
                "speed_ms": bill["speed"],
                "speed_kmh": round(bill["speed"] * 3.6, 2),
                "rawScore": bill["rawScore"],
                "score": bill["score"],
                "landing": bill["landing"],
                "isIllegal": bill["isIllegal"],
                "within_grp_rank": rank,
                "leader_laps": leader["laps"],
                "leader_speed_kmh": round(leader["speed"] * 3.6, 2),
                "leader_is_bill": leader["userGuid"] == BILL,
            })
    return flights


def main():
    """Join flights to weather and write the per-flight CSVs."""
    d = json.load(open(RESULTS))
    wx = json.load(open(WEATHER))
    index, offset_s = load_weather_index(wx)
    flights = extract_flights(d)

    main_rows, full_rows = [], []
    for i, f in enumerate(flights, 1):
        local_dt, hour_key = nearest_hour_local(f["start_utc"], offset_s)
        w = index.get(hour_key, {})
        rnd = f"R{i:02d}"
        main_rows.append({
            "round": rnd,
            "heat": f["heat"],
            "task_type": f["task_type"],
            "start_datetime_local": local_dt.strftime("%Y-%m-%d %H:%M"),
            "wx_hour_local": hour_key,
            "wind_speed_kmh": w.get("windspeed_10m"),
            "wind_gust_kmh": w.get("windgusts_10m"),
            "wind_dir_deg": w.get("winddirection_10m"),
            "temp_c": w.get("temperature_2m"),
            "cloud_pct": w.get("cloudcover"),
            "shortwave_radiation": w.get("shortwave_radiation"),
            "laps": f["laps"],
            "speed_kmh": f["speed_kmh"],
            "normalised_score": f["score"],
            "within_group_rank": f["within_grp_rank"],
        })
        full = dict(main_rows[-1])
        full.update({
            "group": f["group"],
            "group_size": f["group_size"],
            "rawScore": f["rawScore"],
            "rel_humidity": w.get("relative_humidity_2m"),
            "cloud_low_pct": w.get("cloudcover_low"),
            "surface_pressure": w.get("surface_pressure"),
            "boundary_layer_height": w.get("boundary_layer_height"),
            "leader_laps": f["leader_laps"],
            "leader_speed_kmh": f["leader_speed_kmh"],
            "laps_deficit": f["laps"] - f["leader_laps"],
            "speed_deficit_kmh": round(f["speed_kmh"] - f["leader_speed_kmh"], 2),
        })
        full_rows.append(full)

    with open(OUT_MAIN, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(main_rows[0].keys()))
        w.writeheader()
        w.writerows(main_rows)
    with open(OUT_FULL, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(full_rows[0].keys()))
        w.writeheader()
        w.writerows(full_rows)

    print(f"Wrote {OUT_MAIN} ({len(main_rows)} rows)")
    print(f"Wrote {OUT_FULL} ({len(full_rows)} rows)")
    def s(v):
        return "NA" if v is None else v
    for r in main_rows:
        print(f"{r['round']} {r['heat']:8} {r['start_datetime_local']} "
              f"wind={s(r['wind_speed_kmh'])} gust={s(r['wind_gust_kmh'])} "
              f"rad={s(r['shortwave_radiation'])} "
              f"laps={r['laps']} score={r['normalised_score']} rank={r['within_group_rank']}")


if __name__ == "__main__":
    main()
