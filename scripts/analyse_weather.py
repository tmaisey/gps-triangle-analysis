"""Correlate Oschatz weather conditions with Bill Maisey's performance.

Consumes ``analysis/bill_flights_weather_full.csv`` and reports Pearson and
Spearman associations between conditions (wind, gusts, thermal proxies,
time-of-day) and Bill's normalised within-group score (conditions-controlled)
and raw laps (distance heats only; conditions+skill). Also derives the triangle
course orientation from the task geometry. Writes ``analysis/weather_correlations.csv``.

n is small (17 flights; 14 distance) so all associations are suggestive only.
The two-sided p<0.05 critical |r| for n=17 (df=15) is ~0.482; for n=14 ~0.532.
"""
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "analysis" / "bill_flights_weather_full.csv"
OUT = ROOT / "analysis" / "weather_correlations.csv"

# Task geometry (from GPS-track task block; identical across all replays)
START_LAT, START_LON = 51.297718, 13.082957
COURSE_DIR = 74.8  # degrees: axis / apex bearing from start
LEG_LEN = 350      # metres, equilateral GPS-triangle side


def pearson(x, y):
    """Pearson correlation of two equal-length numeric lists."""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def ranks(v):
    """Average-tie ranks of a list (1-based)."""
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(x, y):
    """Spearman rank correlation."""
    return pearson(ranks(x), ranks(y))


def crit_r(df, r):
    """Rough p<0.05 two-sided significance flag from critical |r|.

    Args:
        df: Degrees of freedom (n-2).
        r: Observed correlation.

    Returns:
        '*' if |r| exceeds the ~0.05 critical value, else '' (heuristic, no scipy).
    """
    # critical |r| ~ t_crit / sqrt(df + t_crit^2); t_crit(0.05,2-sided) ~2.13(df15),2.18(df12)
    tcrit = 2.13 if df >= 15 else 2.18
    rc = tcrit / math.sqrt(df + tcrit ** 2)
    return "*" if abs(r) >= rc else ""


def fnum(v):
    """Parse a CSV cell to float or None."""
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def geometry():
    """Print the derived triangle course orientation and candidate leg bearings."""
    print("\n=== TRIANGLE COURSE ORIENTATION (Task 5) ===")
    print(f"Start line: lat {START_LAT}, lon {START_LON}")
    print(f"Course axis (task 'direction'): {COURSE_DIR}deg (ENE); leg length {LEG_LEN} m; equilateral.")
    # In a closed triangular loop successive flight-leg bearings differ by 120deg.
    # Convention: apex at course bearing; base perpendicular; one circulation sense.
    base = COURSE_DIR
    legs_ccw = [(base + k * 120) % 360 for k in range(3)]
    print("Under 'flight legs 120deg apart, first leg on axis' convention, leg flight-bearings:")
    print(f"  candidate set: {[round(b, 1) for b in legs_ccw]} deg (and the reverse-circulation set +180).")
    print("  NOTE: exact vertex order / rotation sense needs the .rct task file "
          "(taskAttachmentGuid b7dd856d...), not present. Axis 74.8deg is firm; "
          "per-leg headwind/tailwind is derivable once the sense is fixed.")


def main():
    """Compute and report all correlations, morning/afternoon splits, geometry."""
    rows = list(csv.DictReader(open(FULL)))
    dist = [r for r in rows if r["task_type"] == "distance"]

    predictors = [
        ("wind_speed_kmh", "wind speed"),
        ("wind_gust_kmh", "wind gust"),
        ("shortwave_radiation", "radiation (thermal proxy)"),
        ("boundary_layer_height", "BL height (thermal proxy)"),
        ("temp_c", "temperature"),
    ]

    def hour(r):
        return int(r["start_datetime_local"][11:13]) + int(r["start_datetime_local"][14:16]) / 60

    out_rows = []
    print("=== CAVEAT: n small (17/14); associations SUGGESTIVE only. CAPE all-null in ERA5 archive. ===")

    for target_name, subset, tgt_key, df in [
        ("normalised_score (all 17, conditions-controlled)", rows, "normalised_score", 15),
        ("laps (distance heats, n=14, conditions+skill)", dist, "laps", 12),
        ("speed_kmh (distance heats, n=14)", dist, "speed_kmh", 12),
        ("laps_deficit vs same-air leader (distance, n=14)", dist, "laps_deficit", 12),
    ]:
        print(f"\n--- {target_name} ---")
        y = [fnum(r[tgt_key]) for r in subset]
        thour = [hour(r) for r in subset]
        for pk, plabel in predictors:
            x = [fnum(r[pk]) for r in subset]
            if any(v is None for v in x):
                print(f"  {plabel:28} : NA (missing values)")
                continue
            pr, sr = pearson(x, y), spearman(x, y)
            print(f"  {plabel:28} : Pearson r={pr:+.3f}{crit_r(df, pr)}  Spearman rho={sr:+.3f}{crit_r(df, sr)}")
            out_rows.append({"target": target_name, "predictor": plabel,
                             "pearson_r": round(pr, 3), "spearman_rho": round(sr, 3),
                             "n": len(subset), "sig_flag": crit_r(df, pr)})
        # time-of-day
        pr, sr = pearson(thour, y), spearman(thour, y)
        print(f"  {'time-of-day (local hour)':28} : Pearson r={pr:+.3f}{crit_r(df, pr)}  Spearman rho={sr:+.3f}{crit_r(df, sr)}")
        out_rows.append({"target": target_name, "predictor": "time-of-day (local hour)",
                         "pearson_r": round(pr, 3), "spearman_rho": round(sr, 3),
                         "n": len(subset), "sig_flag": crit_r(df, pr)})

    # morning vs afternoon (split at 13:00 local)
    print("\n--- Morning (<13:00) vs Afternoon (>=13:00) ---")
    for label, subset in [("all 17", rows), ("distance only", dist)]:
        am = [r for r in subset if hour(r) < 13]
        pm = [r for r in subset if hour(r) >= 13]
        def mean(g, k):
            vals = [fnum(r[k]) for r in g]
            return sum(vals) / len(vals) if vals else float("nan")
        print(f"  [{label}] AM n={len(am)} PM n={len(pm)} | "
              f"score AM={mean(am,'normalised_score'):.0f} PM={mean(pm,'normalised_score'):.0f} | "
              f"laps AM={mean(am,'laps'):.1f} PM={mean(pm,'laps'):.1f} | "
              f"rank AM={mean(am,'within_group_rank'):.1f} PM={mean(pm,'within_group_rank'):.1f}")

    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["target", "predictor", "pearson_r", "spearman_rho", "n", "sig_flag"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"\nWrote {OUT}")

    geometry()


if __name__ == "__main__":
    main()
