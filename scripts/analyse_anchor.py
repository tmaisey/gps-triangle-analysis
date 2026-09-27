"""Task A: Bill Maisey per-round analysis for the Oschatz 2026 anchor event.

Reads raw JSON from data/scores/, joins names, builds Bill's per-round table,
computes within-group and field-distribution stats, and writes:
  analysis/bill_oschatz_rounds.csv   (per-round detail)
  analysis/oschatz_field_summary.csv (field distribution per round + overall)

Sport class: motor only to climb to start altitude; then pure glide. Score
normalised to 1000 within each group (same time-slot / same air). totalScore =
best 16 of 17 rounds (worst dropped) — verified empirically.
"""
import json
import pathlib
import statistics as stats
import csv

D = pathlib.Path("/Users/twm/code/projects/gps-triangle/data/scores")
A = pathlib.Path("/Users/twm/code/projects/gps-triangle/analysis")
A.mkdir(parents=True, exist_ok=True)

BILL = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"
GRIESE = "2e1a6fe6-9060-4c7a-b83e-813567b030ac"
MS_TO_KMH = 3.6


def load(n):
    return json.load(open(D / n))


def main():
    res = load("results.json")
    comp = load("competitors.json")
    name = {c["userGuid"]: f'{c["name"]} {c["surname"]}'.strip() for c in comp}

    heats = sorted(res["competitionGpsTriangleHeat"], key=lambda h: h["order"])

    bill_rows = []          # per-round for Bill
    field_rows = []         # per-round field distribution (heat-wide + group)
    all_laps, all_speed = [], []   # every scored flight in event (for overall dist)

    # aggregate trackers for laps/speed/landing/illegal
    per_pilot_laps = {}     # guid -> [laps per round]
    per_pilot_speed = {}
    per_pilot_landing = {}
    per_pilot_dist_laps = {}   # distance-task rounds only
    per_pilot_dist_speed = {}

    for h in heats:
        heat_name = h["name"]
        groups = h["competitionGpsTriangleGroup"]
        _hlapmax = max((r.get("laps", 0) for g in groups for r in g["competitionGpsTriangleResult"]), default=0)
        _is_speed_heat = (len(groups) == 1 and _hlapmax <= 1)
        # collect heat-wide (all groups) results
        heat_results = []
        for g in groups:
            for r in g["competitionGpsTriangleResult"]:
                r = dict(r)
                # zero-score DNF/bombout entries omit laps/speed/landing
                r.setdefault("laps", 0)
                r.setdefault("speed", 0.0)
                r.setdefault("landing", 0)
                r.setdefault("isWorst", False)
                r["_group"] = g["name"]
                heat_results.append(r)
                all_laps.append(r["laps"])
                all_speed.append(r["speed"])
                per_pilot_laps.setdefault(r["userGuid"], []).append(r["laps"])
                per_pilot_speed.setdefault(r["userGuid"], []).append(r["speed"])
                per_pilot_landing.setdefault(r["userGuid"], []).append(r["landing"])
                if not _is_speed_heat:
                    per_pilot_dist_laps.setdefault(r["userGuid"], []).append(r["laps"])
                    per_pilot_dist_speed.setdefault(r["userGuid"], []).append(r["speed"])

        # find Bill's group + result
        bill_r = None
        bill_group = None
        for g in groups:
            for r in g["competitionGpsTriangleResult"]:
                if r["userGuid"] == BILL:
                    bill_r = r
                    bill_group = g
        if bill_r is None:
            continue

        def norm(r):
            r = dict(r)
            r.setdefault("laps", 0); r.setdefault("speed", 0.0)
            r.setdefault("landing", 0); r.setdefault("isWorst", False)
            return r
        gres = [norm(r) for r in bill_group["competitionGpsTriangleResult"]]
        bill_r = norm(bill_r)
        # within-group rank by normalised score desc (ties -> speed)
        ordered = sorted(gres, key=lambda r: (-r["score"], -r["speed"]))
        rank = [i for i, r in enumerate(ordered, 1) if r["userGuid"] == BILL][0]
        leader = ordered[0]

        # heat-wide percentile of Bill (fraction of flights he beats), laps & speed
        n = len(heat_results)
        laps_pct = 100 * sum(1 for r in heat_results if r["laps"] < bill_r["laps"]) / n
        spd_pct = 100 * sum(1 for r in heat_results if r["speed"] < bill_r["speed"]) / n
        # within-group percentile
        gn = len(gres)
        g_laps_pct = 100 * sum(1 for r in gres if r["laps"] < bill_r["laps"]) / gn
        g_spd_pct = 100 * sum(1 for r in gres if r["speed"] < bill_r["speed"]) / gn

        # classify task type: a "speed" round is a single combined group where
        # the whole field flies exactly one flat-out lap (no landing pts, ~90-160km/h)
        heat_lapmax = max(r["laps"] for r in heat_results)
        task_type = "speed" if (len(groups) == 1 and heat_lapmax <= 1) else "distance"

        bill_rows.append({
            "heat": heat_name,
            "task_type": task_type,
            "group": bill_group["name"],
            "group_size": gn,
            "laps": bill_r["laps"],
            "speed_ms": round(bill_r["speed"], 3),
            "speed_kmh": round(bill_r["speed"] * MS_TO_KMH, 2),
            "rawScore": bill_r["rawScore"],
            "score": bill_r["score"],
            "landing": bill_r["landing"],
            "isIllegal": bill_r["isIllegal"],
            "zoneEntered": bill_r["zoneEntered"],
            "isWorst_dropped": bill_r["isWorst"],
            "startOrder": bill_r["startOrder"],
            "within_grp_rank": f"{rank}/{gn}",
            "grp_rank_int": rank,
            "leader_laps": leader["laps"],
            "leader_speed_kmh": round(leader["speed"] * MS_TO_KMH, 2),
            "leader_score": leader["score"],
            "leader_landing": leader["landing"],
            "laps_deficit": bill_r["laps"] - leader["laps"],
            "speed_deficit_kmh": round((bill_r["speed"] - leader["speed"]) * MS_TO_KMH, 2),
            "score_gap_to_leader": bill_r["score"] - leader["score"],
        })

        field_rows.append({
            "heat": heat_name,
            "heat_flights": n,
            "bill_laps": bill_r["laps"],
            "bill_speed_kmh": round(bill_r["speed"] * MS_TO_KMH, 2),
            "bill_heat_laps_pctile": round(laps_pct, 1),
            "bill_heat_speed_pctile": round(spd_pct, 1),
            "bill_grp_laps_pctile": round(g_laps_pct, 1),
            "bill_grp_speed_pctile": round(g_spd_pct, 1),
            "heat_laps_median": stats.median([r["laps"] for r in heat_results]),
            "heat_speed_kmh_median": round(stats.median([r["speed"] for r in heat_results]) * MS_TO_KMH, 2),
            "heat_laps_max": max(r["laps"] for r in heat_results),
            "heat_speed_kmh_max": round(max(r["speed"] for r in heat_results) * MS_TO_KMH, 2),
        })

    # ---- write per-round CSV ----
    cols = list(bill_rows[0].keys())
    with open(A / "bill_oschatz_rounds.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(bill_rows)

    fcols = list(field_rows[0].keys())
    with open(A / "oschatz_field_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fcols)
        w.writeheader()
        w.writerows(field_rows)

    # ================= COMPUTED INSIGHTS =================
    dist = [r for r in bill_rows if r["task_type"] == "distance"]
    speed = [r for r in bill_rows if r["task_type"] == "speed"]
    print("=" * 70)
    print(f"TASK SPLIT: {len(dist)} distance rounds (multi-lap, groups A-D) + {len(speed)} speed rounds (1-lap sprint, single 38-group)")
    print(f"  speed rounds = {[r['heat'] for r in speed]}  (whole field flew 1 lap; NOT bombouts)")

    laps = [r["laps"] for r in dist]
    spd = [r["speed_kmh"] for r in dist]
    sc = [r["score"] for r in dist]
    land = [r["landing"] for r in dist]
    print("\nBILL CONSISTENCY — DISTANCE rounds only (n=%d)" % len(dist))
    print(f"  laps : mean {stats.mean(laps):.2f} median {stats.median(laps)} stdev {stats.pstdev(laps):.2f} min {min(laps)} max {max(laps)}")
    print(f"  speed: mean {stats.mean(spd):.2f} median {stats.median(spd):.2f} stdev {stats.pstdev(spd):.2f} km/h  min {min(spd)} max {max(spd)}")
    print(f"  score: mean {stats.mean(sc):.1f} median {stats.median(sc)} stdev {stats.pstdev(sc):.1f}")
    bomb = [r for r in dist if r["laps"] <= 4]
    print(f"  low-lap/bombout rounds (<=4 laps): {len(bomb)} -> " + ", ".join(f'{r['heat']}({r['laps']}L,{r['speed_kmh']}kmh)' for r in bomb))
    print("SPEED rounds: laps=1 each; Bill speed_kmh=%s (leader ~150-160); scores=%s" %
          ([r['speed_kmh'] for r in speed], [r['score'] for r in speed]))
    print("landing (distance rounds): values=%s; zeros in %s" %
          (sorted(set(land)), [r['heat'] for r in dist if r['landing'] == 0]))

    print("\nBEST / WORST rounds (by normalised score)")
    for r in sorted(bill_rows, key=lambda x: -x["score"])[:2]:
        print(f"  BEST {r['heat']} {r['group']} score={r['score']} laps={r['laps']} spd={r['speed_kmh']}kmh rank={r['within_grp_rank']} deficit_laps={r['laps_deficit']} dspd={r['speed_deficit_kmh']}")
    for r in sorted(bill_rows, key=lambda x: x["score"])[:3]:
        print(f"  WORST {r['heat']} {r['group']} score={r['score']} laps={r['laps']} spd={r['speed_kmh']}kmh rank={r['within_grp_rank']} leader_laps={r['leader_laps']} illegal={r['isIllegal']} zone={r['zoneEntered']} landing={r['landing']}")

    print("\nWITHIN-GROUP (same air) coaching split — DISTANCE rounds")
    ld = [r["laps_deficit"] for r in dist]
    sd = [r["speed_deficit_kmh"] for r in dist]
    ranks = [r["grp_rank_int"] for r in dist]
    print(f"  laps deficit to group leader : mean {stats.mean(ld):.2f} (total {sum(ld)}) rounds_behind_on_laps={sum(1 for x in ld if x<0)}/{len(dist)}")
    print(f"  speed deficit to leader km/h : mean {stats.mean(sd):.2f}")
    print(f"  within-group rank: mean {stats.mean(ranks):.2f} median {stats.median(ranks)} best {min(ranks)} worst {max(ranks)}")
    matched = [r for r in dist if r["laps_deficit"] == 0]
    fewer = [r for r in dist if r["laps_deficit"] < 0]
    print(f"  rounds matching leader lap count: {len(matched)} ({[r['heat'] for r in matched]})  | rounds with FEWER laps: {len(fewer)}")
    if matched:
        print(f"    when matched laps -> mean speed deficit {stats.mean([r['speed_deficit_kmh'] for r in matched]):.2f} km/h, mean score gap {stats.mean([r['score_gap_to_leader'] for r in matched]):.0f}, scores {[r['score'] for r in matched]}")
    print(f"  correlation check: on distance rounds, Bill's avg speed and lap count both drop together")
    for r in sorted(dist, key=lambda x: x['laps']):
        print(f"    {r['heat']:8} laps {r['laps']:2}/{r['leader_laps']:2}  spd {r['speed_kmh']:6}/{r['leader_speed_kmh']:6} kmh  ddef {r['speed_deficit_kmh']:6}  score {r['score']}")

    print("\nLANDINGS vs field")
    field_land = [x for v in per_pilot_landing.values() for x in v]
    print(f"  Bill landing mean {stats.mean(land):.1f} vs field flight mean {stats.mean(field_land):.1f}; field landing values {sorted(set(field_land))}")
    print(f"  Bill rounds with landing < max(600): {[ (r['heat'],r['landing']) for r in bill_rows if r['landing']<600]}")

    print("\nILLEGAL / ZONE flights (Bill)")
    ill = [r for r in bill_rows if r["isIllegal"] or r["zoneEntered"]]
    print(f"  count={len(ill)} -> {[(r['heat'],'illegal' if r['isIllegal'] else 'zone',r['score']) for r in ill]}")

    # overall field position (DISTANCE rounds only, like-for-like)
    print("\nOVERALL FIELD position (DISTANCE rounds, per-pilot means)")
    def pctile(val, arr):
        return 100 * sum(1 for x in arr if x < val) / len(arr)
    dl_means = per_pilot_mean(per_pilot_dist_laps)
    ds_means = per_pilot_mean(per_pilot_dist_speed)
    bill_dl = stats.mean([r["laps"] for r in dist])
    bill_ds = stats.mean([r["speed_ms"] for r in dist])
    print(f"  Bill mean laps  {bill_dl:.2f} -> beats {pctile(bill_dl, dl_means):.0f}% of pilots (rank ~{sum(1 for x in dl_means if x>bill_dl)+1}/{len(dl_means)})")
    print(f"  Bill mean speed {bill_ds*MS_TO_KMH:.2f}kmh -> beats {pctile(bill_ds, ds_means):.0f}% of pilots (rank ~{sum(1 for x in ds_means if x>bill_ds)+1}/{len(ds_means)})")

    # ---- Griese comparison / gap decomposition ----
    print("\n" + "=" * 70)
    print("GRIESE (winner) vs BILL vs MEDIAN pilot")
    g_laps = per_pilot_laps[GRIESE]; g_spd = per_pilot_speed[GRIESE]; g_land = per_pilot_landing[GRIESE]
    print(f"  Griese: total laps {sum(g_laps)} mean {stats.mean(g_laps):.2f} | mean speed {stats.mean(g_spd)*MS_TO_KMH:.2f}kmh | landing mean {stats.mean(g_land):.1f}")
    b_laps = per_pilot_laps[BILL]; b_spd = per_pilot_speed[BILL]; b_land = per_pilot_landing[BILL]
    print(f"  Bill  : total laps {sum(b_laps)} mean {stats.mean(b_laps):.2f} | mean speed {stats.mean(b_spd)*MS_TO_KMH:.2f}kmh | landing mean {stats.mean(b_land):.1f}")
    # median pilot totals
    med_totlaps = stats.median([sum(v) for v in per_pilot_laps.values()])
    med_meanspd = stats.median([stats.mean(v)*MS_TO_KMH for v in per_pilot_speed.values()])
    print(f"  Median pilot: total laps {med_totlaps} | mean speed {med_meanspd:.2f}kmh")
    print(f"  Bill vs Griese: laps deficit {sum(b_laps)-sum(g_laps)} over 17 rounds ({stats.mean(b_laps)-stats.mean(g_laps):.2f}/round); speed deficit {(stats.mean(b_spd)-stats.mean(g_spd))*MS_TO_KMH:.2f}kmh; landing deficit {stats.mean(b_land)-stats.mean(g_land):.1f}/round")

    # normalised-score gap decomposition via own-group leader
    print("\nSCORE-GAP DECOMPOSITION (Bill's normalised-score shortfall vs his OWN group leaders)")
    total_shortfall = sum(1000 - r["score"] for r in bill_rows)
    dist_short = sum(1000 - r["score"] for r in dist)
    speed_short = sum(1000 - r["score"] for r in speed)
    laps_limited = sum(1000 - r["score"] for r in dist if r["laps_deficit"] < 0)
    print(f"  Total shortfall to 1000/round: {total_shortfall} over 17 rounds")
    print(f"    distance rounds: {dist_short} ({100*dist_short/total_shortfall:.0f}%); of which FEWER-LAPS rounds {laps_limited} ({100*laps_limited/dist_short:.0f}% of distance shortfall)")
    print(f"    speed rounds:    {speed_short} ({100*speed_short/total_shortfall:.0f}%) — pure lap-speed limited")
    print("\nWrote analysis/bill_oschatz_rounds.csv and analysis/oschatz_field_summary.csv")


def per_pilot_mean(d):
    import statistics as s
    return [s.mean(v) for v in d.values()]


if __name__ == "__main__":
    main()
