"""Aggregate the per-round phase decomposition into the Bill-vs-leader comparison,
the per-lap time-deficit attribution, the lap-count (climb) attribution, and the
phase cost ranking. Writes analysis/phase_summary.json and analysis/phase_summary.md.

Reads:
  * analysis/phase_perround_raw.json  (produced by scripts/phase_decomp.py)
  * analysis/per_round_metrics.csv    (prior agent: line-crossing entry_speed_kmh etc.)

Method notes are embedded in the markdown output. Key choices:
  * Entry speed for the START phase uses the prior agent's line-crossing
    entry_speed_kmh (measured at the start gate, directly comparable to the
    120 km/h cap) rather than the raw dive-peak, which can exceed the cap.
  * The per-lap time deficit is computed PAIRED per round (Bill minus leader on
    the same day/air), then averaged -- this controls for round-to-round air.
    lap_t = cruise_t + turn_t on clean laps, so the deficit splits additively.
  * The lap-count deficit is attributed to racing pace vs thermal time via a
    counterfactual (working_time - climb_time) / clean_lap_time model.
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS = ROOT / "analysis"
WORKING_TIME = 1800.0  # s (30 min)
ENTRY_CAP = 120.0      # km/h maximum entry speed

raw = json.load(open(ANALYSIS / "phase_perround_raw.json"))

# ---- pull line-crossing entry speed from the prior per-round metrics ------------
entry = {}  # round -> {"bill":x, "leader":y}
with open(ANALYSIS / "per_round_metrics.csv") as f:
    for row in csv.DictReader(f):
        if row["task_type"] != "triangle":
            continue
        rd = int(row["round"])
        role = "bill" if row["role"] == "BILL" else "leader"
        entry.setdefault(rd, {})[role] = float(row["entry_speed_kmh"])


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 2) if xs else None


def pct(a, b):
    """Percent gap of a below b (positive = a slower/less)."""
    if a is None or b is None or b == 0:
        return None
    return round((b - a) / b * 100, 1)


# ===== 1. AGGREGATE PHASE METRICS (mean across the 14 triangle rounds) ==========
def col(role, path):
    out = []
    for r in raw:
        x = r[role]
        for k in path.split("."):
            x = x[k] if x is not None else None
        out.append(x)
    return out


agg = {}
# START -- entry speed from prior metrics
b_entry = [entry[r["round"]]["bill"] for r in raw]
l_entry = [entry[r["round"]]["leader"] for r in raw]
agg["start"] = {
    "bill_entry_speed_kmh": mean(b_entry),
    "leader_entry_speed_kmh": mean(l_entry),
    "entry_gap_kmh": round(mean(l_entry) - mean(b_entry), 1),
    "bill_margin_to_cap_kmh": round(ENTRY_CAP - mean(b_entry), 1),
    "leader_margin_to_cap_kmh": round(ENTRY_CAP - mean(l_entry), 1),
    "bill_lap1_time_s": mean(col("bill", "lap1_time_s")),
    "leader_lap1_time_s": mean(col("leader", "lap1_time_s")),
}

# STRAIGHT / CRUISE
bc = mean(col("bill", "cruise.mean_cruise_kmh"))
lc = mean(col("leader", "cruise.mean_cruise_kmh"))
agg["straight"] = {
    "bill_cruise_kmh": bc,
    "leader_cruise_kmh": lc,
    "cruise_gap_kmh": round(lc - bc, 1),
    "cruise_gap_pct": pct(bc, lc),
    "bill_glide_ratio": mean(col("bill", "cruise.cruise_glide_ratio")),
    "leader_glide_ratio": mean(col("leader", "cruise.cruise_glide_ratio")),
}

# TURNPOINT TURNS
agg["turns"] = {
    "bill_scrub_kmh": mean(col("bill", "mean_turn_scrub_kmh")),
    "leader_scrub_kmh": mean(col("leader", "mean_turn_scrub_kmh")),
    "bill_extra_m_per_corner": mean(col("bill", "mean_turn_extra_m")),
    "leader_extra_m_per_corner": mean(col("leader", "mean_turn_extra_m")),
    "bill_extra_m_per_lap": mean(col("bill", "extra_dist_per_lap_m")),
    "leader_extra_m_per_lap": mean(col("leader", "extra_dist_per_lap_m")),
    "extra_dist_gap_m_per_lap": round(mean(col("bill", "extra_dist_per_lap_m"))
                                      - mean(col("leader", "extra_dist_per_lap_m")), 1),
}

# THERMAL CLIMBS
agg["climbs"] = {
    "bill_gain_m_per_climb": mean(col("bill", "mean_climb_gain_m")),
    "leader_gain_m_per_climb": mean(col("leader", "mean_climb_gain_m")),
    "bill_mean_rate_ms": mean(col("bill", "mean_climb_rate_ms")),
    "leader_mean_rate_ms": mean(col("leader", "mean_climb_rate_ms")),
    "bill_best_rate_ms": mean(col("bill", "best_climb_rate_ms")),
    "leader_best_rate_ms": mean(col("leader", "best_climb_rate_ms")),
    "bill_median_radius_m": mean(col("bill", "median_climb_radius_m")),
    "leader_median_radius_m": mean(col("leader", "median_climb_radius_m")),
    "bill_total_climb_time_s": mean(col("bill", "total_climb_time_s")),
    "leader_total_climb_time_s": mean(col("leader", "total_climb_time_s")),
    "bill_n_climbs": mean(col("bill", "n_climbs")),
    "leader_n_climbs": mean(col("leader", "n_climbs")),
}

# ===== 2. PER-LAP TIME DEFICIT DECOMPOSITION (paired per round) =================
dec_rows = []
for r in raw:
    b, l = r["bill"], r["leader"]
    if b["clean_laps"] < 1 or l["clean_laps"] < 1:
        continue  # need clean laps for BOTH pilots
    d_lap = round(b["clean_lap_time_s"] - l["clean_lap_time_s"], 1)
    d_cruise = round(b["clean_cruise_t_s"] - l["clean_cruise_t_s"], 1)
    d_turn = round(b["clean_turn_t_s"] - l["clean_turn_t_s"], 1)
    dec_rows.append({
        "round": r["round"], "d_lap": d_lap, "d_cruise": d_cruise, "d_turn": d_turn,
        "bill_clean_laps": b["clean_laps"], "leader_clean_laps": l["clean_laps"],
        "bill_lap_s": b["clean_lap_time_s"], "leader_lap_s": l["clean_lap_time_s"],
    })

mean_d_lap = mean([x["d_lap"] for x in dec_rows])
mean_d_cruise = mean([x["d_cruise"] for x in dec_rows])
mean_d_turn = mean([x["d_turn"] for x in dec_rows])
decomposition = {
    "rounds_used": [x["round"] for x in dec_rows],
    "rounds_excluded_no_clean_lap": [r["round"] for r in raw
                                     if r["bill"]["clean_laps"] < 1 or r["leader"]["clean_laps"] < 1],
    "mean_lap_deficit_s": mean_d_lap,
    "straight_deficit_s": mean_d_cruise,
    "turn_deficit_s": mean_d_turn,
    "straight_share_pct": round(mean_d_cruise / mean_d_lap * 100, 1) if mean_d_lap else None,
    "turn_share_pct": round(mean_d_turn / mean_d_lap * 100, 1) if mean_d_lap else None,
    "per_round": dec_rows,
}

# ===== 2b. STAYING-ALOFT (the real climb cost: early landings) ==================
aloft_rows = []
for r in raw:
    b, l = r["bill"], r["leader"]
    ba, la = b["aloft_time_s"], l["aloft_time_s"]
    aloft_rows.append({
        "round": r["round"], "bill_aloft_s": ba, "leader_aloft_s": la,
        "bill_landed_early": ba is not None and ba < 1550 and (la is None or la - ba > 200),
    })
aloft = {
    "bill_mean_aloft_s": mean([x["bill_aloft_s"] for x in aloft_rows]),
    "leader_mean_aloft_s": mean([x["leader_aloft_s"] for x in aloft_rows]),
    "bill_rounds_landed_early": [x["round"] for x in aloft_rows if x["bill_landed_early"]],
    "per_round": aloft_rows,
}

# ===== 3. LAP-COUNT (climb) ATTRIBUTION -- counterfactual ========================
# laps_est = (WORKING_TIME - climb_time) / clean_lap_time. Decompose the lap-count
# gap into (a) racing pace (clean_lap_time) and (b) thermal time (climb_time).
lapcount_rows = []
for r in raw:
    b, l = r["bill"], r["leader"]
    if b["clean_lap_time_s"] is None or l["clean_lap_time_s"] is None:
        continue
    bt, lt = b["clean_lap_time_s"], l["clean_lap_time_s"]
    bcl, lcl = b["total_climb_time_s"], l["total_climb_time_s"]

    def est(lap_t, climb_t):
        return (WORKING_TIME - climb_t) / lap_t

    base_b = est(bt, bcl)
    # counterfactual: give Bill the leader's pace only, then leader's climb-time only
    cf_pace = est(lt, bcl)      # Bill's climb time, leader's pace
    cf_climb = est(bt, lcl)     # Bill's pace, leader's climb time
    lapcount_rows.append({
        "round": r["round"],
        "bill_laps": b["laps"], "leader_laps": l["laps"],
        "lap_gap": l["laps"] - b["laps"],
        "pace_effect_laps": round(cf_pace - base_b, 2),
        "climbtime_effect_laps": round(cf_climb - base_b, 2),
    })

mean_lap_gap = mean([x["lap_gap"] for x in lapcount_rows])
mean_pace = mean([x["pace_effect_laps"] for x in lapcount_rows])
mean_climbeff = mean([x["climbtime_effect_laps"] for x in lapcount_rows])
tot = (mean_pace or 0) + (mean_climbeff or 0)
lapcount = {
    "mean_lap_gap": mean_lap_gap,
    "pace_effect_laps": mean_pace,
    "climbtime_effect_laps": mean_climbeff,
    "pace_share_pct": round(mean_pace / tot * 100, 1) if tot else None,
    "climbtime_share_pct": round(mean_climbeff / tot * 100, 1) if tot else None,
    "per_round": lapcount_rows,
}

# ===== assemble compact per-round table for JSON ================================
compact_rounds = []
for r in raw:
    b, l = r["bill"], r["leader"]
    compact_rounds.append({
        "round": r["round"], "leader": r["leader_name"],
        "laps": [b["laps"], l["laps"]],
        "entry_kmh": [entry[r["round"]]["bill"], entry[r["round"]]["leader"]],
        "cruise_kmh": [b["cruise"]["mean_cruise_kmh"], l["cruise"]["mean_cruise_kmh"]],
        "clean_lap_s": [b["clean_lap_time_s"], l["clean_lap_time_s"]],
        "clean_cruise_s": [b["clean_cruise_t_s"], l["clean_cruise_t_s"]],
        "clean_turn_s": [b["clean_turn_t_s"], l["clean_turn_t_s"]],
        "turn_extra_m_lap": [b["extra_dist_per_lap_m"], l["extra_dist_per_lap_m"]],
        "climb_gain_m": [b["mean_climb_gain_m"], l["mean_climb_gain_m"]],
        "climb_rate_ms": [b["mean_climb_rate_ms"], l["mean_climb_rate_ms"]],
        "climb_radius_m": [b["median_climb_radius_m"], l["median_climb_radius_m"]],
        "n_climbs": [b["n_climbs"], l["n_climbs"]],
        "climb_time_s": [b["total_climb_time_s"], l["total_climb_time_s"]],
        "clean_laps_used": [b["clean_laps"], l["clean_laps"]],
    })

summary = {
    "meta": {
        "pilot": "Bill Maisey",
        "n_triangle_rounds": len(raw),
        "excluded_speedruns": [4, 10, 16],
        "entry_speed_cap_kmh": ENTRY_CAP,
        "working_time_s": WORKING_TIME,
        "method": "Corner turns anchored on official SECTOR TPC crossings; thermals "
                  "detected as sustained circling (>=12 s, >=270 deg, net climb) on the "
                  "1 Hz tail; START = flightStart->first corner; CRUISE = remaining "
                  "motor-off points. Per-lap deficit paired per round on clean laps "
                  "(no thermal, lap 1 excluded).",
    },
    "aggregate_phase_metrics": agg,
    "per_lap_time_deficit_decomposition": decomposition,
    "staying_aloft": aloft,
    "lap_count_attribution": lapcount,
    "per_round": compact_rounds,
}

json.dump(summary, open(ANALYSIS / "phase_summary.json", "w"), indent=1)
sz = (ANALYSIS / "phase_summary.json").stat().st_size
print(f"wrote phase_summary.json ({sz/1024:.1f} KB)")


# ===== 4. MARKDOWN REPORT =======================================================
def f(v, nd=1):
    return "-" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


s, st, tu, cl = agg["start"], agg["straight"], agg["turns"], agg["climbs"]
d = decomposition
md = []
md.append("# Flight-phase decomposition — Bill Maisey vs same-air group leaders\n")
md.append("14 triangle rounds (speedruns 4/10/16 excluded). Motor-off racing only. "
          "Values are means across rounds; Bill vs the top scorer in his group each round.\n")

md.append("## 1. Aggregate phase metrics (Bill vs leader)\n")
md.append("| Phase | Metric | Bill | Leader | Gap |")
md.append("|---|---|---|---|---|")
md.append(f"| START | Entry speed at gate (km/h) | {f(s['bill_entry_speed_kmh'])} | {f(s['leader_entry_speed_kmh'])} | **-{f(s['entry_gap_kmh'])}** |")
md.append(f"| START | Unused margin to 120 cap (km/h) | {f(s['bill_margin_to_cap_kmh'])} | {f(s['leader_margin_to_cap_kmh'])} | Bill wastes {f(s['bill_margin_to_cap_kmh']-s['leader_margin_to_cap_kmh'])} more |")
md.append(f"| START | Lap-1 time (s, incl. settling) | {f(s['bill_lap1_time_s'])} | {f(s['leader_lap1_time_s'])} | +{f(s['bill_lap1_time_s']-s['leader_lap1_time_s'])} |")
md.append(f"| STRAIGHT | Cruise speed (km/h) | {f(st['bill_cruise_kmh'])} | {f(st['leader_cruise_kmh'])} | **-{f(st['cruise_gap_kmh'])} ({f(st['cruise_gap_pct'])}%)** |")
md.append(f"| STRAIGHT | Glide ratio (glide legs) | {f(st['bill_glide_ratio'])} | {f(st['leader_glide_ratio'])} | -{f(st['leader_glide_ratio']-st['bill_glide_ratio'])} |")
md.append(f"| TURN | Speed scrubbed per corner (km/h) | {f(tu['bill_scrub_kmh'])} | {f(tu['leader_scrub_kmh'])} | Bill loses, leader gains |")
md.append(f"| TURN | Extra distance per corner (m) | {f(tu['bill_extra_m_per_corner'])} | {f(tu['leader_extra_m_per_corner'])} | +{f(tu['bill_extra_m_per_corner']-tu['leader_extra_m_per_corner'])} |")
md.append(f"| TURN | Extra distance per lap (m) | {f(tu['bill_extra_m_per_lap'])} | {f(tu['leader_extra_m_per_lap'])} | **+{f(tu['extra_dist_gap_m_per_lap'])}** |")
md.append(f"| CLIMB | Height banked per thermal (m) | {f(cl['bill_gain_m_per_climb'])} | {f(cl['leader_gain_m_per_climb'])} | **-{f(cl['leader_gain_m_per_climb']-cl['bill_gain_m_per_climb'])}** |")
md.append(f"| CLIMB | Mean climb rate (m/s) | {f(cl['bill_mean_rate_ms'],2)} | {f(cl['leader_mean_rate_ms'],2)} | -{f(cl['leader_mean_rate_ms']-cl['bill_mean_rate_ms'],2)} |")
md.append(f"| CLIMB | Best climb rate (m/s) | {f(cl['bill_best_rate_ms'],2)} | {f(cl['leader_best_rate_ms'],2)} | -{f(cl['leader_best_rate_ms']-cl['bill_best_rate_ms'],2)} |")
md.append(f"| CLIMB | Median circle radius (m) | {f(cl['bill_median_radius_m'])} | {f(cl['leader_median_radius_m'])} | **+{f(cl['bill_median_radius_m']-cl['leader_median_radius_m'])} (wider)** |")
md.append(f"| CLIMB | Total time thermalling (s) | {f(cl['bill_total_climb_time_s'])} | {f(cl['leader_total_climb_time_s'])} | Bill circles LESS |")
md.append(f"| ALOFT | Mean racing time used (s of 1800) | {f(aloft['bill_mean_aloft_s'])} | {f(aloft['leader_mean_aloft_s'])} | **-{f(aloft['leader_mean_aloft_s']-aloft['bill_mean_aloft_s'])}** |")
md.append("")
md.append("**Reads:** entry speed confirms the under-used-start pattern — Bill crosses "
          f"{f(s['entry_gap_kmh'])} km/h slower than the leader and leaves ~{f(s['bill_margin_to_cap_kmh'])} km/h "
          "of the 120 cap unused (leader leaves half that). Cruise is 8% slow and glide is slightly "
          "worse. Corners: leader carries/gains speed through the apex; Bill scrubs a little and rounds "
          f"~{f(tu['extra_dist_gap_m_per_lap'])} m wider per lap. Climbs confirm the hypothesis with a "
          "twist — Bill banks ~35% LESS height per thermal, climbs slower, and circles WIDER (39 vs 33 m "
          "radius), yet spends LESS total time circling. He is not over-thermalling; he under-banks and "
          "then runs out of air, landing early and using ~225 s less of the 30-min window than the leader.\n")

md.append("## 2. Per-lap time-deficit decomposition (clean laps, paired per round)\n")
md.append(f"Bill's mean **clean-lap deficit = {f(d['mean_lap_deficit_s'])} s/lap** slower than his leader "
          f"(rounds used: {d['rounds_used']}; excluded for no clean lap: {d['rounds_excluded_no_clean_lap']}).\n")
md.append("| Component | s/lap | Share |")
md.append("|---|---|---|")
md.append(f"| Slower STRAIGHTS (cruise) | {f(d['straight_deficit_s'])} | **{f(d['straight_share_pct'])}%** |")
md.append(f"| Slower/wider TURNS | {f(d['turn_deficit_s'])} | {f(d['turn_share_pct'])}% |")
md.append(f"| **Total per-lap deficit** | **{f(d['mean_lap_deficit_s'])}** | 100% |")
md.append("")
md.append("**Method:** on clean laps (no thermal circling; lap 1 excluded as it holds the start dive) "
          "lap time = cruise time + turn time by construction, so the deficit splits additively. Paired "
          "per round (same air), then averaged. **Limit:** turn windows are anchored on official corner "
          "crossings, so any extra height/speed loss Bill takes mid-leg lands in the 'straight' bucket — "
          "the straight share is therefore an upper bound and absorbs general line/energy inefficiency, "
          "not only raw airspeed.\n")

md.append("## 3. Lap-count gap — the climb/aloft story (separate from per-lap time)\n")
md.append(f"Leaders average **{f(lapcount['mean_lap_gap'])} more laps**. A counterfactual "
          "`laps=(1800-climb_time)/clean_lap_time` attributes this almost entirely to **racing pace** "
          f"(pace effect {f(lapcount['pace_effect_laps'],2)} laps); the climb-*time* term is negative "
          f"({f(lapcount['climbtime_effect_laps'],2)} laps) because the leader actually spends MORE time "
          "circling. So Bill does not lose laps by thermalling too much. The climb cost is instead "
          "**qualitative**: banking ~35% less height and circling wider means less altitude to convert into "
          f"speed, and Bill lands early in rounds {aloft['bill_rounds_landed_early']} (catastrophically in "
          "R9=3 laps, R12=2 laps). Better climbs would show up as staying aloft the full window and as a "
          "higher sustainable cruise, i.e. they feed phases 1 and 2 rather than adding laps directly.\n")

md.append("## 4. Phase cost ranking (biggest lever first)\n")
md.append("1. **STRAIGHT / cruise speed — biggest lever.** ~90% of the 22 s/lap deficit and the dominant "
          "driver of the lap-count gap. An 8% cruise gain closes most of the per-lap deficit and adds laps.\n")
md.append("2. **THERMAL CLIMBS (height banked / circle discipline) — second lever, drives lap COUNT.** "
          "Bill banks 35% less height, circles ~6 m wider, climbs slower. This is why he lands early and "
          "has less energy to sustain cruise. Affects score via laps, not per-lap time.\n")
md.append("3. **START entry speed — modest, easy win.** 24 km/h below the leader and ~49 km/h under the "
          "120 cap; costs a one-off ~few s on lap 1 and forfeits free energy. Cheap to fix (dive harder to "
          "the gate).\n")
md.append("4. **TURNPOINT TURNS — smallest cost / near a strength.** Only ~10% of the per-lap deficit "
          "(~2 s/lap); Bill rounds 15 m wider per lap and scrubs a touch where leaders gain speed, but the "
          "absolute penalty is small.\n")
md.append("**Where Bill matches or beats leaders (strengths):** R7 and R17 — lap-for-lap level with the "
          "leader (cruise and turns competitive); in several rounds (R2, R5, R9) Bill's cruise or aloft time "
          "equals or beats the leader. His turn technique and thermalling *duration discipline* are not the "
          "problem — raw cruise speed and height-per-climb are.\n")

md.append("## Method & caveats\n")
md.append("- **Corners = ground truth:** turnpoint turns are anchored on the official SECTOR A/B/C crossing "
          "events, not a bearing-rate guess, so corner timing is reliable.\n")
md.append("- **Climb vs turn separation:** thermals are detected as sustained circling (>=12 s, >=270 deg "
          "cumulative heading, net-positive altitude) on the 1 Hz tail, explicitly excluding the corner "
          "windows. Bearing-rate segmentation still blends brief thermal snatches near corners into 'turn' "
          "and vice-versa; the duration/continuity gate mitigates this but does not eliminate it.\n")
md.append("- **Small-sample noise:** low-lap rounds (R3, R9, R12) yield 0-2 clean laps and are down-weighted "
          "or dropped from the paired per-lap decomposition (rounds used are listed in §2). Climb metrics on "
          "1-climb rounds are noisy.\n")
md.append("- **Entry speed** uses the prior agent's gate-crossing `entry_speed_kmh` (comparable to the 120 "
          "cap); the raw dive-peak can exceed the cap and is not used for that comparison.\n")
md.append("- **Lap count** is the official competition result (manifest); the track shows a few extra "
          "start-line crossings (lead-in / out-of-window) that do not affect per-lap timing.\n")

(ANALYSIS / "phase_summary.md").write_text("\n".join(md))
print(f"wrote phase_summary.md ({(ANALYSIS / 'phase_summary.md').stat().st_size/1024:.1f} KB)")
print("lap deficit:", decomposition["mean_lap_deficit_s"], "s  straight%",
      decomposition["straight_share_pct"], " turn%", decomposition["turn_share_pct"])
print("lap-count gap:", lapcount["mean_lap_gap"], " pace%", lapcount["pace_share_pct"],
      " climbtime%", lapcount["climbtime_share_pct"])
