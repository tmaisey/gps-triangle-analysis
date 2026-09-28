"""Flight-phase decomposition for the RC GPS-Triangle pilot analysis.

Segments each post-start (motor-off) triangle flight into four phases -- START,
STRAIGHT/CRUISE, TURNPOINT TURN and THERMAL CLIMB -- for Bill Maisey and his
same-air group leader in the 14 triangle rounds, then aggregates the Bill-vs-leader
comparison and attributes his per-lap time deficit to slower straights vs slower/
wider turns.

Method summary (see phase_summary.md for the full caveat list):
  * Race window = from the scored flight start (gpsTriangleStats.flightStart) to the
    last lap-completion crossing. Motor is off throughout.
  * TURNPOINT TURNS are anchored on the OFFICIAL corner crossing events
    (SECTORA/B/C TPCs) -- ground truth, not a bearing-rate guess -- and their extent
    is grown around the crossing while |bearing-rate| stays high.
  * THERMAL CLIMBS are detected on the 1 Hz tail as sustained circling: a run of
    consecutive high-|bearing-rate| points, >= MIN_CLIMB_DUR s long, accumulating
    >= MIN_CLIMB_TURN deg of heading and net-positive altitude, and NOT part of a
    corner window. Duration/continuity is what separates a climb from a corner turn.
  * START = flight start -> first SECTORA crossing (the opening dive into lap 1).
  * STRAIGHT/CRUISE = the remaining motor-off points (the glide legs).

Usage: uv run python scripts/phase_decomp.py
Writes: analysis/phase_summary.json, analysis/phase_summary.md
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKS = ROOT / "data" / "tracks"
ANALYSIS = ROOT / "analysis"
BILL_GUID = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"

# ---- segmentation thresholds (documented; tuned for the 350 m-radius,
# ---- right-isosceles course of ADR-008: 700 m base, ~495 m legs) ---------------
TURN_THRESH = 7.0        # deg/s smoothed bearing-rate above which a point is "turning"
BR_SMOOTH = 3            # points in the bearing-rate smoothing window (~3 s)
VARIO_SMOOTH = 5         # points in the vario smoothing window (~5 s)
MIN_CLIMB_DUR = 12.0     # s: a circling run must last this long to be a thermal climb
MIN_CLIMB_TURN = 270.0   # deg: cumulative heading change over the run (near a full circle)
MIN_CLIMB_GAIN = 2.0     # m: net altitude gain over the run
CORNER_MAX_HALF = 9.0    # s: max half-width grown around a corner crossing
CORNER_SPD_WIN = 3.0     # s: window before/after a turn to measure entry/exit speed
CLEAN_LAP_MAX_RATIO = 1.6  # a lap longer than this x the pilot's median lap is "thermal-heavy"


def parse_t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def wrap180(d: float) -> float:
    """Wrap a heading difference into (-180, 180]."""
    return (d + 180.0) % 360.0 - 180.0


def load_replay(group_id: int):
    return json.load(open(TRACKS / f"replay_{group_id}.json"))


def find_pilot(replay, guid):
    for p in replay:
        if p["pilot"]["userGuid"] == guid:
            return p
    return None


def local_xy(lat, lon, lat0, lon0):
    x = (lon - lon0) * math.cos(math.radians(lat0)) * 111320.0
    y = (lat - lat0) * 110540.0
    return x, y


def smooth(arr, win):
    n = len(arr)
    if win <= 1 or n == 0:
        return list(arr)
    half = win // 2
    out = []
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        seg = [a for a in arr[lo:hi] if a is not None]
        out.append(sum(seg) / len(seg) if seg else None)
    return out


class Flight:
    """Parsed, phase-segmented single flight for one pilot in one round."""

    def __init__(self, pilot, task):
        self.pilot = pilot
        self.name = pilot["pilot"]["name"]
        self.task = task
        self.lat0 = task["startLatitude"]
        self.lon0 = task["startLongitude"]
        self._parse_events()
        self._parse_tail()
        self._segment()

    # -- events -----------------------------------------------------------------
    def _parse_events(self):
        ev = self.pilot["events"]
        gts = self.pilot.get("gpsTriangleStats") or []
        self.flight_start = parse_t(gts[0]["flightStart"]) if gts and gts[0].get("flightStart") else None
        # corner crossings and lap completions (lap completions carry a lapStat)
        self.corners = []       # (t_datetime, sector) sector in A/B/C
        self.lap_crossings = [] # datetimes of STARTSTARTTPC that complete a lap
        self.lap_times = []     # authoritative per-lap durations (s)
        for e in ev:
            desc = e.get("description")
            t = parse_t(e["time"])
            if desc in ("SECTORA", "SECTORB", "SECTORC"):
                self.corners.append((t, desc[-1]))
            if e["type"] == "TPC" and desc == "STARTSTARTTPC" and e.get("lapStat"):
                self.lap_crossings.append(t)
                self.lap_times.append(e["lapStat"]["time"])
        # fall back if flightStart missing: first corner minus a nominal lead-in
        if self.flight_start is None and self.corners:
            self.flight_start = self.corners[0][0]

    # -- tail -------------------------------------------------------------------
    def _parse_tail(self):
        start = self.flight_start
        end = self.lap_crossings[-1] if self.lap_crossings else None
        pts = []
        for p in self.pilot["tail"]:
            t = parse_t(p["time"])
            if start and t < start:
                continue
            if end and t > end:
                continue
            pts.append(p)
        self.t = [(parse_t(p["time"]) - start).total_seconds() for p in pts]
        self.lat = [p["latitude"] for p in pts]
        self.lon = [p["longitude"] for p in pts]
        self.alt = [p.get("gpsAlt", 0) for p in pts]
        self.vario = [p.get("vario", 0.0) for p in pts]
        self.gs = [p.get("groundSpeed", 0) / 3.6 for p in pts]  # km/h -> m/s
        self.xy = [local_xy(la, lo, self.lat0, self.lon0) for la, lo in zip(self.lat, self.lon)]
        self.n = len(pts)
        # course bearing from successive positions + bearing rate (deg/s)
        self.cb = [None] * self.n
        for i in range(self.n - 1):
            dx = self.xy[i + 1][0] - self.xy[i][0]
            dy = self.xy[i + 1][1] - self.xy[i][1]
            if dx == 0 and dy == 0:
                self.cb[i] = self.cb[i - 1] if i > 0 else 0.0
            else:
                self.cb[i] = math.degrees(math.atan2(dx, dy)) % 360.0
        if self.n >= 2:
            self.cb[-1] = self.cb[-2]
        self.br = [0.0] * self.n
        for i in range(1, self.n):
            dt = self.t[i] - self.t[i - 1]
            if dt > 0 and self.cb[i] is not None and self.cb[i - 1] is not None:
                self.br[i] = wrap180(self.cb[i] - self.cb[i - 1]) / dt
        self.br_s = smooth([abs(b) for b in self.br], BR_SMOOTH)
        self.vario_s = smooth(self.vario, VARIO_SMOOTH)

    def _idx_at(self, tsec):
        """Nearest tail index to a race-relative time (s)."""
        best, bd = None, 1e9
        for i, tt in enumerate(self.t):
            d = abs(tt - tsec)
            if d < bd:
                bd, best = d, i
        return best

    def _seg_dt(self, i):
        if i == 0:
            return self.t[1] - self.t[0] if self.n > 1 else 1.0
        return self.t[i] - self.t[i - 1]

    # -- segmentation -----------------------------------------------------------
    def _segment(self):
        self.phase = ["cruise"] * self.n  # per-point label
        if self.n < 3 or self.flight_start is None:
            self.climbs, self.turns = [], []
            self.start_phase = None
            return
        fs = self.flight_start
        # relative times of corner crossings AFTER the scored start (drop pre-start
        # practice/early-attempt crossings, which have negative relative time)
        self.corner_rel = [((t - fs).total_seconds(), s) for t, s in self.corners
                           if (t - fs).total_seconds() > 0.5]

        # START phase: flight start -> first SECTORA crossing
        first_a = next((tt for tt, s in self.corner_rel if s == "A"), None)
        if first_a is not None:
            for i in range(self.n):
                if self.t[i] <= first_a:
                    self.phase[i] = "start"
        self.start_end_t = first_a

        # TURNPOINT TURNS anchored on official corner crossings ------------------
        self.turns = []
        used = set()
        for tt, sec in self.corner_rel:
            if first_a is not None and tt <= first_a and sec == "A":
                # the very first A is the end of the start dive, still a corner turn
                pass
            ci = self._idx_at(tt)
            if ci is None:
                continue
            # grow window while turning, bounded to +-CORNER_MAX_HALF seconds
            lo = ci
            while lo - 1 >= 0 and (tt - self.t[lo - 1]) <= CORNER_MAX_HALF and self.br_s[lo - 1] and self.br_s[lo - 1] > TURN_THRESH:
                lo -= 1
            hi = ci
            while hi + 1 < self.n and (self.t[hi + 1] - tt) <= CORNER_MAX_HALF and self.br_s[hi + 1] and self.br_s[hi + 1] > TURN_THRESH:
                hi += 1
            if hi == lo:  # ensure at least a 1-step turn
                hi = min(self.n - 1, ci + 1)
                lo = max(0, ci - 1)
            for i in range(lo, hi + 1):
                if self.phase[i] != "start":
                    self.phase[i] = "turn"
                used.add(i)
            self.turns.append(self._turn_metrics(sec, lo, hi))

        # THERMAL CLIMBS: sustained circling runs not already a corner/start -----
        self.climbs = []
        i = 0
        while i < self.n:
            if self.br_s[i] and self.br_s[i] > TURN_THRESH and self.phase[i] == "cruise":
                j = i
                cum = 0.0
                while j < self.n and self.br_s[j] and self.br_s[j] > TURN_THRESH and self.phase[j] in ("cruise",):
                    if j > i:
                        cum += self.br[j] * self._seg_dt(j)
                    j += 1
                lo, hi = i, j - 1
                dur = self.t[hi] - self.t[lo]
                gain = self.alt[hi] - self.alt[lo]
                if dur >= MIN_CLIMB_DUR and abs(cum) >= MIN_CLIMB_TURN and gain >= MIN_CLIMB_GAIN:
                    for k in range(lo, hi + 1):
                        self.phase[k] = "climb"
                    self.climbs.append(self._climb_metrics(lo, hi))
                i = j
            else:
                i += 1

    def _turn_metrics(self, sector, lo, hi):
        # entry/exit speed measured in a short window just outside the turn
        t_lo, t_hi = self.t[lo], self.t[hi]
        ent = [self.gs[i] for i in range(self.n) if t_lo - CORNER_SPD_WIN <= self.t[i] < t_lo]
        ext = [self.gs[i] for i in range(self.n) if t_hi < self.t[i] <= t_hi + CORNER_SPD_WIN]
        entry_v = statistics.mean(ent) if ent else self.gs[lo]
        exit_v = statistics.mean(ext) if ext else self.gs[hi]
        # path length through the turn vs straight chord (entry->exit): extra distance
        path = 0.0
        for i in range(lo, hi):
            dx = self.xy[i + 1][0] - self.xy[i][0]
            dy = self.xy[i + 1][1] - self.xy[i][1]
            path += math.hypot(dx, dy)
        chord = math.hypot(self.xy[hi][0] - self.xy[lo][0], self.xy[hi][1] - self.xy[lo][1])
        return {
            "sector": sector,
            "dur_s": round(self.t[hi] - self.t[lo], 1),
            "entry_v_kmh": round(entry_v * 3.6, 1),
            "exit_v_kmh": round(exit_v * 3.6, 1),
            "scrub_kmh": round((entry_v - exit_v) * 3.6, 1),
            "path_m": round(path, 1),
            "chord_m": round(chord, 1),
            "extra_m": round(path - chord, 1),
        }

    def _climb_metrics(self, lo, hi):
        dur = self.t[hi] - self.t[lo]
        gain = self.alt[hi] - self.alt[lo]
        # median circle radius r = v / omega ; omega = |bearing rate| in rad/s
        radii = []
        for i in range(lo, hi + 1):
            om = abs(self.br[i]) * math.pi / 180.0
            if om > 0.05 and self.gs[i] > 3:
                radii.append(self.gs[i] / om)
        best = max((self.vario_s[i] for i in range(lo, hi + 1) if self.vario_s[i] is not None), default=0.0)
        return {
            "dur_s": round(dur, 1),
            "gain_m": round(gain, 1),
            "mean_climb_ms": round(gain / dur, 2) if dur > 0 else 0.0,
            "best_climb_ms": round(best, 2),
            "median_radius_m": round(statistics.median(radii), 1) if radii else None,
        }

    # -- per-phase aggregates for this flight -----------------------------------
    def phase_time(self, label):
        return sum(self._seg_dt(i) for i in range(self.n) if self.phase[i] == label)

    def cruise_stats(self):
        vs, glides = [], []
        for i in range(1, self.n):
            if self.phase[i] != "cruise":
                continue
            vs.append(self.gs[i])
            dt = self._seg_dt(i)
            dz = self.alt[i] - self.alt[i - 1]
            dh = self.gs[i] * dt
            if dz < -0.3 and dh > 0:  # descending glide segment
                glides.append(dh / -dz)  # glide ratio (horizontal per vertical)
        return {
            "mean_cruise_kmh": round(statistics.mean(vs) * 3.6, 1) if vs else None,
            "cruise_glide_ratio": round(statistics.median(glides), 1) if glides else None,
        }

    def start_stats(self):
        # peak groundspeed carried through the whole start dive (flight start -> corner A)
        win = [self.gs[i] for i in range(self.n) if self.phase[i] == "start"]
        peak = max(win) if win else (self.gs[0] if self.n else 0)
        return {
            "start_peak_kmh": round(peak * 3.6, 1),
            "start_dur_s": round(self.start_end_t, 1) if self.start_end_t else None,
        }

    def lap_summary(self):
        """Per-lap wall-clock/cruise/turn/climb times, and clean-lap flags.

        Lap time is the crossing-to-crossing wall clock (t1-t0) so that
        cruise_t + turn_t + climb_t == lap_t by construction (additive
        decomposition). Lap 1 is never "clean" because it contains the start
        dive, which is analysed separately as the START phase.
        """
        if not self.lap_crossings:
            return []
        fs = self.flight_start
        bounds = [0.0] + [(t - fs).total_seconds() for t in self.lap_crossings]
        durs = [bounds[i + 1] - bounds[i] for i in range(len(self.lap_crossings))]
        med = statistics.median(durs)
        laps = []
        for li in range(len(self.lap_crossings)):
            t0, t1 = bounds[li], bounds[li + 1]
            cruise_t = turn_t = climb_t = 0.0
            for i in range(1, self.n):
                if t0 < self.t[i] <= t1:
                    dt = self._seg_dt(i)
                    ph = self.phase[i]
                    if ph == "climb":
                        climb_t += dt
                    elif ph == "turn":
                        turn_t += dt
                    else:  # cruise or start
                        cruise_t += dt
            lap_t = t1 - t0
            clean = (li > 0) and climb_t < 3.0 and lap_t <= CLEAN_LAP_MAX_RATIO * med
            laps.append({
                "lap": li + 1,
                "lap_t": round(lap_t, 1),
                "cruise_t": round(cruise_t, 1),
                "turn_t": round(turn_t, 1),
                "climb_t": round(climb_t, 1),
                "clean": clean,
            })
        return laps


def agg(vals):
    vals = [v for v in vals if v is not None]
    return round(statistics.mean(vals), 2) if vals else None


def summarize_flight(fl: Flight, laps_scored=None):
    laps = fl.lap_summary()
    clean = [lp for lp in laps if lp["clean"]]
    cs = fl.cruise_stats()
    ss = fl.start_stats()
    climbs = fl.climbs
    turns = fl.turns
    lap1 = next((lp["lap_t"] for lp in laps if lp["lap"] == 1), None)
    aloft = round(sum(lp["lap_t"] for lp in laps), 1) if laps else None
    return {
        "pilot": fl.name,
        "laps": laps_scored if laps_scored is not None else len(fl.lap_crossings),
        "laps_flown_track": len(fl.lap_crossings),
        "aloft_time_s": aloft,
        "lap1_time_s": lap1,
        "start": ss,
        "cruise": cs,
        "n_turns": len(turns),
        "mean_turn_scrub_kmh": agg([t["scrub_kmh"] for t in turns]),
        "mean_turn_extra_m": agg([t["extra_m"] for t in turns]),
        "mean_turn_entry_kmh": agg([t["entry_v_kmh"] for t in turns]),
        "n_climbs": len(climbs),
        "mean_climb_gain_m": agg([c["gain_m"] for c in climbs]),
        "mean_climb_rate_ms": agg([c["mean_climb_ms"] for c in climbs]),
        "best_climb_rate_ms": max([c["best_climb_ms"] for c in climbs], default=None),
        "median_climb_radius_m": agg([c["median_radius_m"] for c in climbs]),
        "total_climb_time_s": round(fl.phase_time("climb"), 1),
        "extra_dist_per_lap_m": round(sum(t["extra_m"] for t in turns) / max(1, len(fl.lap_times)), 1),
        "clean_laps": len(clean),
        "clean_lap_time_s": agg([lp["lap_t"] for lp in clean]),
        "clean_cruise_t_s": agg([lp["cruise_t"] for lp in clean]),
        "clean_turn_t_s": agg([lp["turn_t"] for lp in clean]),
        "_laps": laps,
    }


def main():
    manifest = json.load(open(TRACKS / "rounds_manifest.json"))
    per_round = []
    for m in manifest:
        if m["task_type"] != "triangle":
            continue
        gid = m["group_id"]
        replay = load_replay(gid)
        bill_p = find_pilot(replay, BILL_GUID)
        lead_p = find_pilot(replay, m["leader"]["userGuid"])
        if bill_p is None or lead_p is None:
            continue
        task = bill_p["task"]
        bf = Flight(bill_p, task)
        lf = Flight(lead_p, task)
        per_round.append({
            "round": m["round"],
            "group_id": gid,
            "leader_name": m["leader"]["name"],
            "bill": summarize_flight(bf, m["bill"]["laps"]),
            "leader": summarize_flight(lf, m["leader"]["laps"]),
        })
    return per_round


if __name__ == "__main__":
    data = main()
    out = ANALYSIS / "phase_perround_raw.json"
    json.dump(data, open(out, "w"), indent=1)
    print(f"processed {len(data)} triangle rounds -> {out}")
    for r in data:
        b, l = r["bill"], r["leader"]
        print(f"R{r['round']:>2} laps B{b['laps']}/L{l['laps']} "
              f"cruise B{b['cruise']['mean_cruise_kmh']}/L{l['cruise']['mean_cruise_kmh']} "
              f"climbs B{b['n_climbs']}({b['mean_climb_gain_m']}m)/L{l['n_climbs']}({l['mean_climb_gain_m']}m) "
              f"cleanlaps B{b['clean_laps']}/L{l['clean_laps']}")
