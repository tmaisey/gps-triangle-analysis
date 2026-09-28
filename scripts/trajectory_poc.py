"""Trajectory-level analysis of Bill Maisey vs same-group leaders (coaching PoC).

For two contrasting flights (Bill's strongest and weakest group-relative
results) this parses the ReplayGroup track JSON and computes per-flight
trajectory metrics comparing Bill to the top-scoring pilot who flew the SAME
air (same group / time slot). Outputs a metrics CSV and three charts.

Metrics: start entry altitude/speed vs caps; altitude bleed rate; time
climbing vs gliding (vario); lap count, per-lap time and speed, gap growth;
ground-track distance per lap vs geometric perimeter (line efficiency).
"""
import csv
import json
import math
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
TRACKS = ROOT / "data" / "tracks"
ANALYSIS = ROOT / "analysis"
CHARTS = ANALYSIS / "charts"
BILL = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"

# (groupId, label, human tag) — chosen from the results tree.
FLIGHTS = [
    (5815, "strong", "Heat17/GroupB (Bill score 999, rank 2/10)"),
    (5769, "weak", "Heat12/GroupA (Bill score 418, rank 6/10)"),
]

MS_TO_KMH = 3.6
COURSE_RADIUS_M = 350.0  # task 'length' is the radius / half-base (ADR-008)
PERIMETER_M = COURSE_RADIUS_M * (2 + 2 * math.sqrt(2))  # right-isosceles lap, ~1689.9 m


def parse_time(s):
    """Parse an ISO-8601 UTC timestamp (with optional fractional seconds)."""
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres between two lat/lon points."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def leader_of(group):
    """Top-scoring pilot in a group: max laps, then max avg triangle speed."""
    def key(p):
        st = p["gpsTriangleStats"][0]
        return (st["laps"], st["allTrianglesAvgSpeed"])
    return max(group, key=key)


def track_arrays(pilot):
    """Return parsed tail as parallel lists: t(datetime), alt(m), vario, lat, lon, gs(m/s)."""
    t, alt, vario, lat, lon, gs = [], [], [], [], [], []
    for pt in pilot["tail"]:
        t.append(parse_time(pt["time"]))
        alt.append(pt["gpsAlt"])
        vario.append(pt.get("vario", 0) or 0)
        lat.append(pt["latitude"])
        lon.append(pt["longitude"])
        gs.append(pt.get("groundSpeed", 0) or 0)
    return t, alt, vario, lat, lon, gs


def lap_boundaries(pilot):
    """Per-lap markers from lapStat events.

    lapStat.time is the DURATION of that individual lap in seconds (verified
    against the monotonic event timestamps); abs_time is the wall-clock
    completion time (monotonic), used for lap segmentation and cumulative plots.
    """
    out = []
    for e in pilot["events"]:
        ls = e.get("lapStat")
        if ls:
            out.append({"num": ls["num"], "dur": ls["time"], "alt": ls["alt"],
                        "altGainLos": ls["altGainLos"], "abs_time": parse_time(e["time"])})
    return out


def climbing_gliding(t, vario):
    """Seconds with vario>0 (climbing) vs vario<=0 (gliding), from ~1 Hz samples."""
    climb = glide = 0.0
    for i in range(1, len(t)):
        dt = (t[i] - t[i - 1]).total_seconds()
        if dt <= 0 or dt > 10:  # guard gaps
            continue
        if vario[i] > 0:
            climb += dt
        else:
            glide += dt
    return climb, glide


def ground_dist_between(t, lat, lon, start_abs, end_abs):
    """Cumulative haversine ground-track distance for points in [start_abs, end_abs]."""
    d = 0.0
    prev = None
    for i in range(len(t)):
        if t[i] < start_abs or t[i] > end_abs:
            continue
        if prev is not None:
            d += haversine(lat[prev], lon[prev], lat[i], lon[i])
        prev = i
    return d


def analyse(pilot, task, flight_start_abs):
    """Compute the full trajectory metric bundle for one pilot's flight."""
    st = pilot["gpsTriangleStats"][0]
    t, alt, vario, lat, lon, gs = track_arrays(pilot)
    laps = lap_boundaries(pilot)
    climb_s, glide_s = climbing_gliding(t, vario)

    # per-lap: duration (lapStat.time), scoring avg speed, ground-track distance.
    # A lap window runs from the previous completion (or flight start) to this
    # completion; long-duration laps fold a thermal climb into that window and
    # so carry inflated ground distance (flagged via climbed).
    per_lap = []
    prev_abs = flight_start_abs
    for lp in laps:
        dur = lp["dur"]
        dist = ground_dist_between(t, lat, lon, prev_abs, lp["abs_time"])
        per_lap.append({
            "num": lp["num"],
            "dur_s": dur,
            "avg_speed_ms": (PERIMETER_M / dur) if dur > 0 else 0,
            "ground_dist_m": dist,
            "efficiency_ratio": dist / PERIMETER_M if dist else 0,
            "alt_at_lap": lp["alt"],
            "alt_gain_los": lp["altGainLos"],
            "abs_time": lp["abs_time"],
            "climbed": lp["altGainLos"] > 15,  # net climb during the lap window
        })
        prev_abs = lp["abs_time"]

    # Line efficiency (fair): cleanest racing laps only — the shortest-duration
    # laps that did NOT net-climb, so distance reflects the flown line not a
    # thermalling loop. Take up to the 3 fastest such laps.
    racing = sorted((l for l in per_lap if not l["climbed"]), key=lambda l: l["dur_s"])[:3]
    clean_dist = (sum(l["ground_dist_m"] for l in racing) / len(racing)) if racing else 0
    clean_dur = (sum(l["dur_s"] for l in racing) / len(racing)) if racing else 0

    total_track = ground_dist_between(t, lat, lon, t[0], t[-1])
    flight_dur = (t[-1] - t[0]).total_seconds()
    alt_start, alt_end = alt[0], alt[-1]
    return {
        "pilot": f"{pilot['pilot']['name']} {pilot['pilot']['surname']}",
        "is_bill": pilot["pilot"]["userGuid"] == BILL,
        "laps": st["laps"],
        "entry_alt_m": st["startEntryAlti"],
        "entry_speed_ms": st["startEntrySpeed"],
        "entry_speed_kmh": st["startEntrySpeed"] * MS_TO_KMH,
        "avg_tri_speed_ms": st["allTrianglesAvgSpeed"],
        "flight_dur_s": flight_dur,
        "duration_field_s": pilot["duration"],
        "climb_s": climb_s,
        "glide_s": glide_s,
        "climb_frac": climb_s / (climb_s + glide_s) if (climb_s + glide_s) else 0,
        "alt_min": min(alt),
        "alt_max": max(alt),
        "alt_landing_m": alt_end,
        "per_lap": per_lap,
        "clean_lap_dist_m": clean_dist,
        "clean_lap_dur_s": clean_dur,
        "clean_lap_eff": clean_dist / PERIMETER_M if clean_dist else 0,
        "total_track_m": total_track,
        "_series": (t, alt, lat, lon),
    }


def main():
    rows = []
    chart_data = {}
    for gid, label, tag in FLIGHTS:
        group = json.load(open(TRACKS / f"replay_{gid}.json"))
        task = group[0]["task"]
        bill = next(p for p in group if p["pilot"]["userGuid"] == BILL)
        leader = leader_of(group)
        fs_bill = parse_time(bill["gpsTriangleStats"][0]["flightStart"])
        fs_lead = parse_time(leader["gpsTriangleStats"][0]["flightStart"])
        mb = analyse(bill, task, fs_bill)
        ml = analyse(leader, task, fs_lead)
        chart_data[label] = {"tag": tag, "task": task, "bill": mb, "leader": ml}

        for m in (mb, ml):
            rows.append({
                "flight": label, "group_id": gid, "context": tag,
                "pilot": m["pilot"], "role": "BILL" if m["is_bill"] else "leader",
                "laps": m["laps"],
                "entry_alt_m": round(m["entry_alt_m"], 1),
                "entry_alt_below_cap_m": round(task["maxEntryAltitude"] - m["entry_alt_m"], 1),
                "entry_speed_kmh": round(m["entry_speed_kmh"], 1),
                "entry_speed_below_cap_kmh": round(task["maxEntrySpeed"] - m["entry_speed_kmh"], 1),
                "avg_tri_speed_ms": round(m["avg_tri_speed_ms"], 2),
                "avg_tri_speed_kmh": round(m["avg_tri_speed_ms"] * MS_TO_KMH, 1),
                "flight_dur_s": round(m["flight_dur_s"]),
                "climb_s": round(m["climb_s"]),
                "glide_s": round(m["glide_s"]),
                "climb_frac": round(m["climb_frac"], 3),
                "alt_min_m": m["alt_min"], "alt_max_m": m["alt_max"],
                "alt_landing_m": m["alt_landing_m"],
                "total_track_km": round(m["total_track_m"] / 1000, 2),
                "clean_lap_dist_m": round(m["clean_lap_dist_m"]),
                "clean_lap_dur_s": round(m["clean_lap_dur_s"], 1),
                "clean_lap_eff_vs_course": round(m["clean_lap_eff"], 2),
            })

    # ---- CSV ----
    ANALYSIS.mkdir(exist_ok=True)
    cols = list(rows[0].keys())
    with open(ANALYSIS / "trajectory_poc.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print("Wrote", ANALYSIS / "trajectory_poc.csv")

    # per-lap detail CSV (bonus)
    with open(ANALYSIS / "trajectory_poc_perlap.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["flight", "role", "pilot", "lap", "dur_s", "avg_speed_kmh",
                    "ground_dist_m", "efficiency_ratio", "alt_at_lap_m"])
        for label in chart_data:
            for role, m in (("BILL", chart_data[label]["bill"]),
                            ("leader", chart_data[label]["leader"])):
                for l in m["per_lap"]:
                    w.writerow([label, role, m["pilot"], l["num"], round(l["dur_s"], 1),
                                round(l["avg_speed_ms"] * MS_TO_KMH, 1),
                                round(l["ground_dist_m"]), round(l["efficiency_ratio"], 3),
                                l["alt_at_lap"]])
    print("Wrote", ANALYSIS / "trajectory_poc_perlap.csv")

    make_charts(chart_data)
    return rows


def _elapsed_min(t):
    return [(x - t[0]).total_seconds() / 60 for x in t]


def make_charts(cd):
    """Render the three PoC charts."""
    CHARTS.mkdir(parents=True, exist_ok=True)

    # (a) altitude vs time — strong flight
    d = cd["strong"]
    for role, color in (("bill", "#2563eb"), ("leader", "#dc2626")):
        m = d[role]
        t, alt, *_ = m["_series"]
        plt.plot(_elapsed_min(t), alt, color=color, lw=1.3,
                 label=f"{'Bill Maisey' if role=='bill' else m['pilot']} ({m['laps']} laps)")
    plt.axhline(400, ls="--", color="#666", lw=0.8,
                label="400 m start-entry cap (applies at start line only)")
    plt.xlabel("Elapsed time (min)"); plt.ylabel("GPS altitude (m)")
    plt.title(f"Altitude vs time — strong flight\n{d['tag']}")
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(CHARTS / "a_altitude_vs_time_strong.png", dpi=130); plt.close()

    # (b) ground-track overlay — strong flight
    d = cd["strong"]; task = d["task"]
    for role, color in (("bill", "#2563eb"), ("leader", "#dc2626")):
        m = d[role]
        _, _, lat, lon = m["_series"]
        plt.plot(lon, lat, color=color, lw=0.7, alpha=0.8,
                 label=f"{'Bill Maisey' if role=='bill' else m['pilot']}")
    plt.plot(task["startLongitude"], task["startLatitude"], "k*", ms=12, label="Start/turn ref")
    plt.xlabel("Longitude"); plt.ylabel("Latitude")
    plt.title(f"Ground-track overlay (triangle circuit) — strong flight\n{d['tag']}")
    plt.legend(fontsize=8); plt.grid(alpha=0.3); plt.axis("equal"); plt.tight_layout()
    plt.savefig(CHARTS / "b_groundtrack_overlay_strong.png", dpi=130); plt.close()

    # (c) cumulative laps vs time — both flights, Bill vs leader
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=False)
    for ax, label in zip(axes, ("strong", "weak")):
        d = cd[label]
        t_origin = min(d["bill"]["_series"][0][0], d["leader"]["_series"][0][0])
        for role, color in (("bill", "#2563eb"), ("leader", "#dc2626")):
            m = d[role]
            # cumulative laps vs wall-clock, using monotonic lap-completion times
            xs = [0.0]; ys = [0]
            for l in m["per_lap"]:
                xs.append((l["abs_time"] - t_origin).total_seconds() / 60)
                ys.append(l["num"])
            ax.step(xs, ys, where="post", color=color, lw=1.6,
                    label=f"{'Bill' if role=='bill' else m['pilot'].split()[-1]} ({m['laps']})")
        ax.set_title(f"{label} — {d['tag']}", fontsize=9)
        ax.set_xlabel("Wall-clock time from group start (min)"); ax.set_ylabel("Cumulative laps")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.suptitle("Cumulative laps over time — Bill vs same-group leader")
    fig.tight_layout()
    fig.savefig(CHARTS / "c_cumulative_laps.png", dpi=130); plt.close()

    print("Wrote 3 charts to", CHARTS)


if __name__ == "__main__":
    main()
