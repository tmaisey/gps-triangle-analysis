"""Per-round coaching metrics + compact embeddable dataset for Bill Maisey.

For each of Bill's 17 Oschatz-2026 rounds this loads the group's ReplayGroup
track (one at a time, freed after use), extracts Bill and the same-air group
LEADER, and computes a full per-flight metric bundle (start-line margins,
energy, thermalling, pacing, line efficiency, biggest-loss-vs-leader segment).

Outputs:
  analysis/per_round_metrics.csv   one row per pilot per round (scalars)
  analysis/per_round_metrics.md    human-readable summary table
  analysis/round_data/round_NN.json  downsampled tracks + geometry + lap times
  analysis/round_data/index.json     round index with headline numbers

Parsing facts (verified in the PoC): groundSpeed is km/h; lapStat.time is a
per-lap DURATION (s); use gpsAlt for altitude; haversine on lat/lon for
distance. The scoring lap is the ADR-008 right-isosceles course: the task
``length`` (350 m) is the RADIUS / half-base, so the perimeter is
350 x (2 + 2*sqrt(2)) ~ 1689.9 m — confirmed by the API's own
``allTrianglesAvgSpeed * timeElapsedSeconds / laps`` on all 17 rounds.
"""
import csv
import json
import math
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKS = ROOT / "data" / "tracks"
ANALYSIS = ROOT / "analysis"
ROUND_DATA = ANALYSIS / "round_data"
BILL = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"

CAP_ALT_M = 400.0
CAP_SPEED_KMH = 120.0
COURSE_RADIUS_M = 350.0   # task 'length' = radius / half-base (ADR-008)
PERIMETER_M = COURSE_RADIUS_M * (2 + 2 * math.sqrt(2))  # ~1689.9 m regs lap
MS_TO_KMH = 3.6
TARGET_PTS = 300          # downsample target per track
DP_GAP_S = 60.0           # bin size for biggest-loss gap-growth scan


# ---------- primitives ----------

def parse_time(s):
    """Parse an ISO-8601 UTC timestamp (optional fractional seconds)."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres between two lat/lon points."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bearing_diff(b2, b1):
    """Signed smallest angular difference b2-b1 in degrees, wrapped to [-180,180]."""
    return ((b2 - b1 + 180) % 360) - 180


def track_arrays(pilot, origin):
    """Return parallel arrays keyed to a common clock origin.

    Returns dict of lists: off (s from origin), t (datetime), alt, vario, lat,
    lon, gs_ms (ground speed m/s), bearing, eng (engine level).
    """
    off, t, alt, vario, lat, lon, gs, brg, eng = [], [], [], [], [], [], [], [], []
    for pt in pilot["tail"]:
        tt = parse_time(pt["time"])
        t.append(tt)
        off.append((tt - origin).total_seconds())
        alt.append(pt["gpsAlt"])
        vario.append(pt.get("vario", 0) or 0)
        lat.append(pt["latitude"])
        lon.append(pt["longitude"])
        gs.append((pt.get("groundSpeed", 0) or 0) / MS_TO_KMH)
        brg.append(pt.get("bearing", 0) or 0)
        eng.append(pt.get("engineLevel", 0) or 0)
    return {"off": off, "t": t, "alt": alt, "vario": vario, "lat": lat,
            "lon": lon, "gs_ms": gs, "brg": brg, "eng": eng}


def lap_events(pilot, origin):
    """Per-lap markers from lapStat events: duration, completion offset, alt, gain."""
    out = []
    for e in pilot["events"]:
        ls = e.get("lapStat")
        if ls:
            out.append({
                "num": ls["num"],
                "dur_s": ls["time"],
                "alt": ls["alt"],
                "gain": ls["altGainLos"],
                "off": (parse_time(e["time"]) - origin).total_seconds(),
            })
    return out


# ---------- Douglas-Peucker downsample (by index) ----------

def _rdp_mask(xs, ys, eps, keep):
    """Iterative Ramer-Douglas-Peucker; marks kept indices in `keep`."""
    stack = [(0, len(xs) - 1)]
    keep[0] = keep[-1] = True
    while stack:
        i0, i1 = stack.pop()
        if i1 <= i0 + 1:
            continue
        x0, y0, x1, y1 = xs[i0], ys[i0], xs[i1], ys[i1]
        dx, dy = x1 - x0, y1 - y0
        denom = math.hypot(dx, dy) or 1e-12
        dmax, idx = -1.0, -1
        for i in range(i0 + 1, i1):
            d = abs(dy * (xs[i] - x0) - dx * (ys[i] - y0)) / denom
            if d > dmax:
                dmax, idx = d, i
        if dmax > eps:
            keep[idx] = True
            stack.append((i0, idx))
            stack.append((idx, i1))


def downsample_indices(lat, lon, target=TARGET_PTS, force=()):
    """Choose <= ~target indices preserving ground-track shape (RDP on lat/lon).

    Scales lon by cos(lat) so metric shape is preserved, bisects the RDP
    tolerance to land near `target` points, then unions any `force` indices
    (e.g. lap crossings) so no marker is lost.
    """
    n = len(lat)
    if n <= target:
        return list(range(n))
    lat0 = math.radians(sum(lat) / n)
    xs = [lo * math.cos(lat0) for lo in lon]
    ys = list(lat)
    lo_e, hi_e = 1e-7, 1e-2
    best = None
    for _ in range(24):
        eps = math.sqrt(lo_e * hi_e)
        keep = [False] * n
        _rdp_mask(xs, ys, eps, keep)
        k = sum(keep)
        if k > target:
            lo_e = eps
        else:
            best = keep
            hi_e = eps
        if abs(k - target) <= target * 0.1:
            best = keep
            break
    keep = best if best else keep
    for i in force:
        if 0 <= i < n:
            keep[i] = True
    return [i for i in range(n) if keep[i]]


def nearest_index(off, target_s):
    """Index of the sample whose offset is closest to target_s."""
    return min(range(len(off)), key=lambda i: abs(off[i] - target_s))


# ---------- per-pilot metrics ----------

def select_stat(pilot, res):
    """Pick the SCORING gpsTriangleStats entry for a pilot.

    A pilot may log several start attempts (each a gpsTriangleStats entry);
    only one is scored. The scoring entry is the one matching the results-tree
    lap count, tie-broken by closeness to the results avg speed. (Non-scoring
    attempts carry a placeholder bestAvgIndex of 500/5000.)
    """
    stats = pilot["gpsTriangleStats"]
    rl = res.get("laps", 0) or 0
    rs = res.get("speed_ms", 0) or 0
    return min(stats, key=lambda s: (abs((s.get("laps", 0) or 0) - rl),
                                     abs((s.get("allTrianglesAvgSpeed", 0) or 0) - rs)))


def analyse_pilot(pilot, origin, task, res):
    """Compute the full metric bundle for one pilot's scoring flight.

    `res` is the pilot's authoritative results record (laps, speed_ms, ...),
    used to select the scoring start attempt and label speedruns.
    """
    st = select_stat(pilot, res)
    a = track_arrays(pilot, origin)
    fs = parse_time(st["flightStart"])
    fs_off = (fs - origin).total_seconds()
    # keep only lap crossings belonging to the scoring flight (after its start);
    # earlier aborted start attempts log their own lapStat events too.
    laps = [l for l in lap_events(pilot, origin) if l["off"] >= fs_off - 5]

    off, t, alt, vario = a["off"], a["t"], a["alt"], a["vario"]
    gs, brg, eng = a["gs_ms"], a["brg"], a["eng"]
    n = len(t)

    # post-start indices (racing phase, motor nominally off)
    post = [i for i in range(n) if off[i] >= fs_off]
    if not post:
        post = list(range(n))

    # --- energy / climb-glide over the racing phase ---
    climb_s = glide_s = 0.0
    height_gain = 0.0
    for k in range(1, len(post)):
        i, j = post[k - 1], post[k]
        dt = off[j] - off[i]
        if dt <= 0 or dt > 10:
            continue
        if vario[j] > 0:
            climb_s += dt
        else:
            glide_s += dt
        d_alt = alt[j] - alt[i]
        if d_alt > 0:
            height_gain += d_alt
    climb_frac = climb_s / (climb_s + glide_s) if (climb_s + glide_s) else 0.0

    peak_alt = max(alt)
    alt_start = st["startEntryAlti"]
    alt_end = alt[-1]
    racing_dur = off[post[-1]] - fs_off if len(post) > 1 else 0.0
    overall_sink = (alt_start - alt_end) / racing_dur if racing_dur > 0 else 0.0

    # --- thermalling ---
    climb_varios = [vario[i] for i in post if vario[i] > 0]
    mean_climb = sum(climb_varios) / len(climb_varios) if climb_varios else 0.0
    # best sustained climb: max 20 s rolling-mean vario within racing phase
    best_sustained = 0.0
    win = 20.0
    for s in range(len(post)):
        i0 = post[s]
        acc, cnt, j = 0.0, 0, s
        while j < len(post) and off[post[j]] - off[i0] <= win:
            acc += vario[post[j]]
            cnt += 1
            j += 1
        if cnt >= 5:
            best_sustained = max(best_sustained, acc / cnt)
    # circling turn radius while climbing: r = v / yaw_rate
    radii = []
    for k in range(1, len(post)):
        i, j = post[k - 1], post[k]
        dt = off[j] - off[i]
        if dt <= 0 or dt > 5:
            continue
        if vario[j] <= 0:
            continue
        yaw = abs(bearing_diff(brg[j], brg[i])) / dt  # deg/s
        if yaw < 3:  # not circling tightly
            continue
        omega = math.radians(yaw)
        v = gs[j]
        if omega > 0 and v > 3:
            radii.append(v / omega)
    radii.sort()
    turn_radius = radii[len(radii) // 2] if radii else 0.0

    # time-to-connect: from the first early-flight altitude low (the post-start
    # glide-down bottom, restricted to the first 60% of the racing phase so the
    # landing isn't mistaken for it) to the onset of the next sustained climb.
    ttc = None
    if len(post) > 10 and racing_dur > 0:
        cutoff = fs_off + 0.6 * racing_dur
        early = [i for i in post if off[i] <= cutoff] or post
        lo_i = min(early, key=lambda i: alt[i])
        lo_off = off[lo_i]
        for k in range(len(post)):
            i = post[k]
            if off[i] < lo_off:
                continue
            acc, cnt, j = 0.0, 0, k
            while j < len(post) and off[post[j]] - off[i] <= 10:
                acc += vario[post[j]]
                cnt += 1
                j += 1
            if cnt >= 5 and acc / cnt > 0.3:
                ttc = off[i] - lo_off
                break

    # --- pacing (per-lap) ---
    per_lap = []
    prev_off = fs_off
    for lp in laps:
        dur = lp["dur_s"]
        per_lap.append({
            "num": lp["num"],
            "dur_s": dur,
            "avg_speed_kmh": (PERIMETER_M / dur) * MS_TO_KMH if dur > 0 else 0.0,
            "alt": lp["alt"],
            "gain": lp["gain"],
            "off": lp["off"],
            "climbed": lp["gain"] > 15,
        })
        prev_off = lp["off"]

    # fastest clean (non-climbing) lap + its ground-track distance
    clean = [l for l in per_lap if not l["climbed"]]
    fastest_clean = min(clean, key=lambda l: l["dur_s"]) if clean else None
    clean_speed = fastest_clean["avg_speed_kmh"] if fastest_clean else 0.0
    clean_dist = clean_eff = 0.0
    if fastest_clean:
        idx = per_lap.index(fastest_clean)
        start_off = per_lap[idx - 1]["off"] if idx > 0 else fs_off
        end_off = fastest_clean["off"]
        prev = None
        for i in range(n):
            if off[i] < start_off or off[i] > end_off:
                continue
            if prev is not None:
                clean_dist += haversine(a["lat"][prev], a["lon"][prev],
                                        a["lat"][i], a["lon"][i])
            prev = i
        clean_eff = clean_dist / PERIMETER_M if clean_dist else 0.0

    return {
        "arrays": a,
        "fs_off": fs_off,
        "laps": st["laps"],
        "avg_speed_kmh": st["allTrianglesAvgSpeed"] * MS_TO_KMH,
        "entry_alt_m": alt_start,
        "entry_speed_kmh": st["startEntrySpeed"] * MS_TO_KMH,
        "alt_margin_m": CAP_ALT_M - alt_start,
        "speed_margin_kmh": CAP_SPEED_KMH - st["startEntrySpeed"] * MS_TO_KMH,
        "peak_alt_m": peak_alt,
        "alt_start_m": alt_start,
        "alt_end_m": alt_end,
        "racing_dur_s": racing_dur,
        "overall_sink_ms": overall_sink,
        "climb_s": climb_s,
        "glide_s": glide_s,
        "climb_frac": climb_frac,
        "height_gain_m": height_gain,
        "mean_climb_ms": mean_climb,
        "best_sustained_climb_ms": best_sustained,
        "turn_radius_m": turn_radius,
        "time_to_connect_s": ttc,
        "per_lap": per_lap,
        "fastest_clean_lap_speed_kmh": clean_speed,
        "fastest_clean_lap_dist_m": clean_dist,
        "fastest_clean_lap_eff": clean_eff,
        "zoneEntered": st.get("zoneEntered"),
    }


# ---------- biggest-loss segment ----------

def cumlaps_at(per_lap, s):
    """Cumulative laps completed by common-clock offset s."""
    c = 0
    for l in per_lap:
        if l["off"] <= s:
            c = l["num"]
    return c


def biggest_loss(bill_m, lead_m, task_type):
    """Window where the leader's lap lead over Bill grew fastest (+ a note)."""
    b_off, l_off = bill_m["arrays"]["off"], lead_m["arrays"]["off"]
    b_alt, l_alt = bill_m["arrays"]["alt"], lead_m["arrays"]["alt"]
    b_var = bill_m["arrays"]["vario"]
    t0 = max(bill_m["fs_off"], lead_m["fs_off"])
    t1 = min(b_off[-1], l_off[-1])
    if task_type == "speedrun" or not bill_m["per_lap"] or t1 <= t0:
        dv = lead_m["avg_speed_kmh"] - bill_m["avg_speed_kmh"]
        return {"start_s": round(t0, 1), "end_s": round(t1, 1),
                "note": f"Speed-run: leader {dv:.0f} km/h faster on the single run."}
    best_bin, best_growth = None, -1.0
    s = t0
    while s < t1:
        e = min(s + DP_GAP_S, t1)
        g0 = cumlaps_at(lead_m["per_lap"], s) - cumlaps_at(bill_m["per_lap"], s)
        g1 = cumlaps_at(lead_m["per_lap"], e) - cumlaps_at(bill_m["per_lap"], e)
        growth = g1 - g0
        if growth > best_growth:
            best_growth, best_bin = growth, (s, e)
        s = e
    if not best_bin or best_growth <= 0:
        return {"start_s": round(t0, 1), "end_s": round(t1, 1),
                "note": "Gap accrued steadily; no single dominant window."}
    s, e = best_bin
    # what was Bill doing in that window?
    idx = [i for i in range(len(b_off)) if s <= b_off[i] <= e]
    gained = int(best_growth)
    note = f"Leader gained {gained} lap{'' if gained == 1 else 's'} here"
    if idx:
        d_alt = b_alt[idx[-1]] - b_alt[idx[0]]
        mean_v = sum(b_var[i] for i in idx) / len(idx)
        if mean_v > 0.2 or d_alt > 20:
            note += f" while Bill was thermalling low (climbed {d_alt:+.0f} m)."
        elif d_alt < -30:
            note += f" while Bill was sinking ({d_alt:+.0f} m, searching for lift)."
        else:
            note += " while Bill held station (slow lap / weak line)."
    return {"start_s": round(s, 1), "end_s": round(e, 1), "note": note}


# ---------- compact track packing ----------

def pack_track(m):
    """Downsample a pilot's track to <=~target points as compact rows.

    Row = [offset_s, lat, lon, gpsAlt, vario, groundSpeed_kmh].
    Lap-crossing samples are force-kept so lap markers align with the track.
    """
    a = m["arrays"]
    off = a["off"]
    force = [nearest_index(off, l["off"]) for l in m["per_lap"]]
    force.append(nearest_index(off, m["fs_off"]))
    idxs = downsample_indices(a["lat"], a["lon"], TARGET_PTS, force)
    rows = []
    for i in idxs:
        rows.append([
            round(off[i], 1),
            round(a["lat"][i], 6),
            round(a["lon"][i], 6),
            int(round(a["alt"][i])),
            round(a["vario"][i], 2),
            int(round(a["gs_ms"][i] * MS_TO_KMH)),
        ])
    return rows


# ---------- main ----------

def main():
    ROUND_DATA.mkdir(parents=True, exist_ok=True)
    manifest = json.load(open(TRACKS / "rounds_manifest.json"))
    csv_rows = []
    index = []

    for rd in manifest:
        gid = rd["group_id"]
        group = json.load(open(TRACKS / f"replay_{gid}.json"))
        task = group[0]["task"]
        origin = None
        bill_p = next(p for p in group if p["pilot"]["userGuid"] == BILL)
        lead_p = next(p for p in group if p["pilot"]["userGuid"] == rd["leader"]["userGuid"])
        # common clock origin = earliest first-sample of the two tracks
        o_b = parse_time(bill_p["tail"][0]["time"])
        o_l = parse_time(lead_p["tail"][0]["time"])
        origin = min(o_b, o_l)

        bm = analyse_pilot(bill_p, origin, task, rd["bill"])
        lm = analyse_pilot(lead_p, origin, task, rd["leader"])
        loss = biggest_loss(bm, lm, rd["task_type"])

        # line-efficiency ratio is only meaningful Bill-vs-leader
        eff_ratio = (bm["fastest_clean_lap_dist_m"] / lm["fastest_clean_lap_dist_m"]
                     if lm["fastest_clean_lap_dist_m"] else None)

        for role, m, meta, rank in (
            ("BILL", bm, rd["bill"], rd["bill_rank"]),
            ("leader", lm, rd["leader"], 1),
        ):
            csv_rows.append({
                "round": rd["round"], "heat": rd["heat"], "group_id": gid,
                "task_type": rd["task_type"], "role": role,
                "pilot": meta["name"], "country": meta.get("country"),
                "rank": rank, "group_size": rd["group_size"],
                "laps": m["laps"],
                "avg_speed_kmh": round(m["avg_speed_kmh"], 1),
                "rawScore": meta["rawScore"], "score": meta["score"],
                "landing_pts": meta["landing"],
                "isIllegal": meta["isIllegal"], "zoneEntered": m["zoneEntered"],
                "entry_alt_m": round(m["entry_alt_m"], 1),
                "entry_alt_margin_m": round(m["alt_margin_m"], 1),
                "entry_speed_kmh": round(m["entry_speed_kmh"], 1),
                "entry_speed_margin_kmh": round(m["speed_margin_kmh"], 1),
                "peak_alt_m": round(m["peak_alt_m"]),
                "alt_start_m": round(m["alt_start_m"], 1),
                "alt_end_m": round(m["alt_end_m"], 1),
                "racing_dur_s": round(m["racing_dur_s"]),
                "overall_sink_ms": round(m["overall_sink_ms"], 3),
                "climb_frac": round(m["climb_frac"], 3),
                "height_gain_m": round(m["height_gain_m"]),
                "mean_climb_ms": round(m["mean_climb_ms"], 2),
                "best_sustained_climb_ms": round(m["best_sustained_climb_ms"], 2),
                "turn_radius_m": round(m["turn_radius_m"], 1),
                "time_to_connect_s": (round(m["time_to_connect_s"], 1)
                                      if m["time_to_connect_s"] is not None else ""),
                "fastest_clean_lap_speed_kmh": round(m["fastest_clean_lap_speed_kmh"], 1),
                "fastest_clean_lap_dist_m": round(m["fastest_clean_lap_dist_m"]),
                "fastest_clean_lap_eff_vs_course": round(m["fastest_clean_lap_eff"], 2),
                "line_eff_ratio_bill_vs_leader": (round(eff_ratio, 3)
                                                  if role == "BILL" and eff_ratio else ""),
                "biggest_loss_note": loss["note"] if role == "BILL" else "",
            })

        # ---- compact round JSON ----
        def pilot_block(m, meta, rank):
            return {
                "name": meta["name"], "country": meta.get("country"),
                "laps": m["laps"], "speed_kmh": round(m["avg_speed_kmh"], 1),
                "score": meta["score"], "rank": rank,
                "entry_alt_m": round(m["entry_alt_m"], 1),
                "entry_speed_kmh": round(m["entry_speed_kmh"], 1),
                "flightStart_s": round(m["fs_off"], 1),
                "lap_offsets_s": [round(l["off"], 1) for l in m["per_lap"]],
                "lap_durations_s": [round(l["dur_s"], 1) for l in m["per_lap"]],
                "track": pack_track(m),
            }

        round_json = {
            "round": rd["round"], "heat": rd["heat"], "group_id": gid,
            "task_type": rd["task_type"], "group_size": rd["group_size"],
            "origin_utc": origin.isoformat().replace("+00:00", "Z"),
            "task": {
                "start_lat": task["startLatitude"], "start_lon": task["startLongitude"],
                "direction_deg": task["direction"], "leg_length_m": task["length"],
                "max_entry_alt_m": task["maxEntryAltitude"],
                "max_entry_speed_kmh": task["maxEntrySpeed"],
                "working_time_min": task["workingTime"],
            },
            "bill": pilot_block(bm, rd["bill"], rd["bill_rank"]),
            "leader": pilot_block(lm, rd["leader"], 1),
            "biggest_loss": loss,
        }
        out = ROUND_DATA / f"round_{rd['round']:02d}.json"
        out.write_text(json.dumps(round_json, separators=(",", ":")))

        index.append({
            "round": rd["round"], "heat": rd["heat"], "group_id": gid,
            "task_type": rd["task_type"], "leader_name": rd["leader"]["name"],
            "file": out.name,
            "bill": {"laps": bm["laps"], "speed_kmh": round(bm["avg_speed_kmh"], 1),
                     "score": rd["bill"]["score"], "rank": rd["bill_rank"]},
            "leader": {"laps": lm["laps"], "speed_kmh": round(lm["avg_speed_kmh"], 1),
                       "score": rd["leader"]["score"]},
            "biggest_loss_note": loss["note"],
        })

        n_pts = len(round_json["bill"]["track"]) + len(round_json["leader"]["track"])
        print(f"  round {rd['round']:>2} g{gid} {rd['task_type']:<9} "
              f"bill {bm['laps']}L/{bm['avg_speed_kmh']:.0f} vs "
              f"{rd['leader']['name'][:16]:<16} {lm['laps']}L/{lm['avg_speed_kmh']:.0f} "
              f"pts={n_pts} ({out.stat().st_size} B)")
        del group  # free the big raw payload before the next round

    (ROUND_DATA / "index.json").write_text(json.dumps(index, separators=(",", ":")))

    # ---- CSV ----
    cols = list(csv_rows[0].keys())
    with open(ANALYSIS / "per_round_metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(csv_rows)

    write_md(csv_rows, index)

    total = sum(p.stat().st_size for p in ROUND_DATA.glob("*.json"))
    print(f"\nround_data/ total: {total/1e6:.3f} MB across {len(list(ROUND_DATA.glob('round_*.json')))} rounds + index")
    print(f"Wrote {ANALYSIS/'per_round_metrics.csv'} and .md")


def write_md(rows, index):
    """Human-readable per-round summary table (Markdown)."""
    by_round = {}
    for r in rows:
        by_round.setdefault(r["round"], {})[r["role"]] = r
    lines = ["# Bill Maisey — Oschatz 2026 per-round metrics",
             "",
             "Bill vs the top-scoring pilot in **his own group** (same air/time slot).",
             "Triangle laps rule; avg speed is the tie-break. Heats 4/10/16 were 1-lap speed-runs.",
             "",
             "| R | Heat | Task | Bill L/spd/score | Rank | Leader | Ldr L/spd/score | Biggest-loss note |",
             "|---|------|------|------------------|------|--------|-----------------|-------------------|"]
    for rn in sorted(by_round):
        b = by_round[rn]["BILL"]
        l = by_round[rn]["leader"]
        lines.append(
            f"| {rn} | {b['heat']} | {b['task_type']} | "
            f"{b['laps']}L / {b['avg_speed_kmh']:.0f} / {b['score']} | "
            f"{b['rank']}/{b['group_size']} | {l['pilot']} | "
            f"{l['laps']}L / {l['avg_speed_kmh']:.0f} / {l['score']} | "
            f"{b['biggest_loss_note']} |")
    lines += ["",
              "## Start-line, energy & thermalling (Bill vs leader)",
              "",
              "| R | Role | Entry alt (marg) | Entry spd (marg) | Peak | Climb% | Mean/Best climb m/s | Turn r (m) | TTC s | Fastest clean lap km/h |",
              "|---|------|------------------|------------------|------|--------|---------------------|-----------|-------|------------------------|"]
    for rn in sorted(by_round):
        for role in ("BILL", "leader"):
            m = by_round[rn][role]
            lines.append(
                f"| {rn} | {role} | {m['entry_alt_m']:.0f} ({m['entry_alt_margin_m']:+.0f}) | "
                f"{m['entry_speed_kmh']:.0f} ({m['entry_speed_margin_kmh']:+.0f}) | "
                f"{m['peak_alt_m']} | {m['climb_frac']*100:.0f}% | "
                f"{m['mean_climb_ms']:.1f}/{m['best_sustained_climb_ms']:.1f} | "
                f"{m['turn_radius_m']:.0f} | {m['time_to_connect_s']} | "
                f"{m['fastest_clean_lap_speed_kmh']:.0f} |")
    (ANALYSIS / "per_round_metrics.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
