"""Data loaders for the report build.

Reads the computed outputs under ``analysis/`` and the authoritative standings
under ``data/scores/`` into clean Python structures, and embeds the compact
per-round track dataset as a JSON blob for the client-side app.

All paths resolve from the repo root so the build is location-independent. The
loaders are read-only (they never mutate the input files) and deterministic.

Reconciliation note (PRD §11): the authoritative event score is the sum of a
pilot's 17 round scores with the single worst round dropped. Bill: 12,562 pts,
rank 22/38, landing 600 on all 14 distance rounds.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from datetime import datetime
from pathlib import Path

# Repo root = two levels up from this file (scripts/build/data.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = REPO_ROOT / "analysis"
ROUND_DATA_DIR = ANALYSIS / "round_data"
SCORES = REPO_ROOT / "data" / "scores"
TASKS = REPO_ROOT / "data" / "tasks"
TRACKS = REPO_ROOT / "data" / "tracks"

BILL_GUID = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"

# rcmodelspot open JSON API (PRD §2). Attachments carry the per-heat .rct task
# file; ReplayGroup carries the full ~1 Hz GPS replay for a heat-group.
API_ATTACHMENT = "https://www.rcmodelspot.com/api/Competition/Attachment/{guid}"
API_REPLAY_GROUP = (
    "https://www.rcmodelspot.com/api/CompetitionGpsTriangle/ReplayGroup/{gid}"
)

# The full working window of a distance task (PRD §3): 30 minutes from the
# scored start-line crossing.
WORKING_WINDOW_S = 1800.0


# --- Low-level helpers ------------------------------------------------------
def _read_json(path: Path) -> dict | list:
    """Load and return parsed JSON from ``path``."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file into a list of row dicts (all values as strings)."""
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _num(val: str) -> float | int | None:
    """Coerce a CSV string to int/float where possible, else ``None``/str."""
    if val is None or val == "":
        return None
    try:
        f = float(val)
        return int(f) if f.is_integer() else f
    except ValueError:
        return val


# --- Round dataset ----------------------------------------------------------
def load_index() -> list[dict]:
    """Return the round index (list of 17 round summary dicts).

    Each entry carries: ``round``, ``heat``, ``group_id``, ``task_type``
    ('triangle' | 'speedrun'), ``leader_name``, ``file``, ``bill`` and
    ``leader`` mini-summaries (laps/speed_kmh/score/rank) and a
    ``biggest_loss_note``.
    """
    return _read_json(ROUND_DATA_DIR / "index.json")  # type: ignore[return-value]


def load_round(round_no: int) -> dict:
    """Return the full compact dataset for one round (1-17).

    Keys: ``round``, ``heat``, ``group_id``, ``task_type``, ``group_size``,
    ``origin_utc``, ``task`` (start_lat/lon, direction_deg, leg_length_m,
    caps, working_time_min), ``bill`` and ``leader`` pilot blocks, and
    ``biggest_loss`` (start_s/end_s/note).

    Each pilot block has: name, country, laps, speed_kmh, score, rank,
    entry_alt_m, entry_speed_kmh, flightStart_s, lap_offsets_s,
    lap_durations_s and ``track`` — a list of rows
    ``[time_offset_s, lat, lon, gpsAlt_m, vario_ms, groundSpeed_kmh]``.

    Args:
        round_no: Round number, 1-17.

    Returns:
        dict: The parsed ``round_NN.json`` payload.
    """
    return _read_json(ROUND_DATA_DIR / f"round_{round_no:02d}.json")  # type: ignore[return-value]


def load_all_rounds() -> list[dict]:
    """Return the full per-round datasets for all 17 rounds, in order."""
    return [load_round(n) for n in range(1, 18)]


# Column offsets into a track row, for readability in charts.py.
TRACK_T, TRACK_LAT, TRACK_LON, TRACK_ALT, TRACK_VARIO, TRACK_GS = range(6)


def embed_round_data_json() -> str:
    """Return a compact JSON string of all round datasets for embedding.

    Produces a single JSON array (one element per round, index order) suitable
    for injecting into a ``<script type="application/json">`` tag in the page.
    Kept compact (no whitespace) to keep the embedded payload small.
    """
    return json.dumps(load_all_rounds(), separators=(",", ":"), ensure_ascii=False)


# --- Standings / reconciliation --------------------------------------------
def load_standings() -> list[dict]:
    """Return the authoritative standings list (38 pilots) from results.json.

    Each standing has ``userGuid``, ``totalScore``, ``score`` and ``results``
    (17 per-flight result dicts with laps/speed/rawScore/score/landing/...).
    """
    return _read_json(SCORES / "results.json")["standings"]  # type: ignore[index]


def bill_standing() -> dict:
    """Return Bill Maisey's standing entry from the authoritative results."""
    for s in load_standings():
        if s["userGuid"] == BILL_GUID:
            return s
    raise KeyError("Bill's standing not found in results.json")


def bill_official_summary() -> dict:
    """Return Bill's reconciled event summary from authoritative standings.

    Returns:
        dict with keys:
            ``rank`` (int, 1-based over totalScore desc),
            ``total_score`` (int, sum of 17 minus worst round),
            ``n_flights`` (int),
            ``results`` (the 17 raw result dicts, round order),
            ``distance_landings`` (list of landing pts for the 14 distance
            rounds — all 600).
    """
    standings = load_standings()
    ranked = sorted(standings, key=lambda s: s["totalScore"], reverse=True)
    rank = next(i for i, s in enumerate(ranked, 1) if s["userGuid"] == BILL_GUID)
    bill = bill_standing()
    results = bill["results"]
    # Speed-sprint rounds (1-indexed 4, 10, 16) score landing 0; distance
    # rounds carry the 600 landing. Distinguish by landing value.
    distance_landings = [r["landing"] for r in results if r["landing"] > 0]
    return {
        "rank": rank,
        "total_score": bill["totalScore"],
        "n_flights": len(results),
        "results": results,
        "distance_landings": distance_landings,
    }


# --- CSV metric loaders -----------------------------------------------------
def load_rounds_csv() -> list[dict]:
    """Return per-round rows from ``bill_oschatz_rounds.csv`` (numbers coerced).

    One row per round (17): heat, task_type ('distance'|'speed'), group,
    laps, speed_kmh, rawScore, score, landing, within/leader stats, deficits.
    """
    return [
        {k: _num(v) for k, v in row.items()}
        for row in _read_csv(ANALYSIS / "bill_oschatz_rounds.csv")
    ]


def load_per_round_metrics() -> list[dict]:
    """Return rows from ``per_round_metrics.csv`` (one per pilot per round).

    Two rows per round: ``role`` in {'BILL','leader'}. Carries entry alt/speed
    and margins, clean-lap speed, climb rates, turn radius, line-efficiency
    ratio, etc. Numbers are coerced to int/float.
    """
    return [
        {k: _num(v) for k, v in row.items()}
        for row in _read_csv(ANALYSIS / "per_round_metrics.csv")
    ]


def load_phase_summary() -> dict:
    """Return the aggregate phase-decomposition summary (``phase_summary.json``).

    Keys: ``meta``, ``aggregate_phase_metrics`` (start/straight/turns/climbs),
    ``per_lap_time_deficit_decomposition``, ``staying_aloft``,
    ``lap_count_attribution``, ``per_round`` (14 triangle-round breakdowns).
    """
    return _read_json(ANALYSIS / "phase_summary.json")  # type: ignore[return-value]


def load_weather_per_flight() -> list[dict]:
    """Return per-flight weather rows from ``weather_per_flight.csv``.

    Keys include round ('R01'..), start_datetime_local, wind_speed_kmh,
    wind_gust_kmh, temp_c, cloud_pct, shortwave_radiation, cape, laps,
    speed_kmh, normalised_score, within_group_rank.
    """
    return [
        {k: _num(v) for k, v in row.items()}
        for row in _read_csv(ANALYSIS / "weather_per_flight.csv")
    ]


def load_weather_correlations() -> list[dict]:
    """Return the weather-vs-performance correlation rows (target/predictor/r)."""
    return [
        {k: _num(v) for k, v in row.items()}
        for row in _read_csv(ANALYSIS / "weather_correlations.csv")
    ]


def load_field_summary() -> list[dict]:
    """Return per-heat field distribution / percentile rows."""
    return [
        {k: _num(v) for k, v in row.items()}
        for row in _read_csv(ANALYSIS / "oschatz_field_summary.csv")
    ]


# --- Round labels (for the Analysis dropdown) ------------------------------
def round_labels() -> dict[int, str]:
    """Map round number -> a human date-time label for the Analysis dropdown.

    Labels are built from the per-flight local start datetime where available
    (``weather_per_flight.csv``), falling back to the round's ``origin_utc``.

    Returns:
        dict[int, str]: e.g. ``{1: "3 Aug 12:55"}``.
    """
    labels: dict[int, str] = {}
    wx = {}
    for row in load_weather_per_flight():
        rnd = row.get("round")
        if isinstance(rnd, str) and rnd.startswith("R"):
            wx[int(rnd[1:])] = row.get("start_datetime_local")
    for entry in load_index():
        n = entry["round"]
        dt = wx.get(n)
        labels[n] = _pretty_datetime(dt) if dt else f"Round {n}"
    return labels


_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _pretty_datetime(local: str) -> str:
    """Render '2026-08-03 12:55' as '3 Aug 12:55'. Falls back to input."""
    try:
        date_part, time_part = local.split(" ")
        _y, m, d = date_part.split("-")
        return f"{int(d)} {_MONTHS[int(m)]} {time_part}"
    except (ValueError, IndexError, AttributeError):
        return str(local)


# --- Geometry: one shared equirectangular projection -----------------------
# A single projection is used identically for the course and every GPS track so
# they overlay in one consistent metre grid (RPT-011). Longitude is scaled by
# cos(lat0); at Oschatz (51.3N) the small-area distortion is negligible.
EARTH_M_PER_DEG = 111_320.0


def projector(lat0: float, lon0: float):
    """Return an equirectangular ``(lat, lon) -> (x_east_m, y_north_m)`` map.

    The origin is ``(lat0, lon0)``. ``x`` grows east, ``y`` grows north (both in
    metres). Longitude is scaled by ``cos(lat0)`` so east/west distances are
    correct near the origin. The same projector must be applied to the course
    geometry and to every flown track for a like-for-like overlay.

    Args:
        lat0: origin latitude (degrees), typically the task start.
        lon0: origin longitude (degrees).

    Returns:
        Callable[[float, float], tuple[float, float]]: the projection function.
    """
    mlon = EARTH_M_PER_DEG * math.cos(math.radians(lat0))

    def to_xy(lat: float, lon: float) -> tuple[float, float]:
        return (lon - lon0) * mlon, (lat - lat0) * EARTH_M_PER_DEG

    return to_xy


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two lat/lon points."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --- Course geometry from the .rct task -------------------------------------
def fetch_rct(guid: str) -> Path:
    """Return the local path to a heat's ``.rct`` task file, fetching if absent.

    The file is cached under ``data/tasks/<guid>.rct``. If it is not present the
    attachment is fetched from the rcmodelspot API and written to the cache.

    Args:
        guid: the heat's ``taskAttachmentGuid``.

    Returns:
        Path: the cached ``.rct`` file path.
    """
    path = TASKS / f"{guid}.rct"
    if not path.exists():
        import requests  # local import: keep the module importable offline

        TASKS.mkdir(parents=True, exist_ok=True)
        resp = requests.get(API_ATTACHMENT.format(guid=guid), timeout=30)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def parse_rct_task(path: str | Path) -> dict:
    """Parse the ``T:`` header of a ``.rct`` file into a task-geometry dict.

    The ``T:`` line is ``name,lat,lon,?,axis_deg,length_m,alt_cap,speed_cap,?,
    minutes`` — where ``length_m`` is the turnpoint RADIUS from the start (350 m
    at Oschatz), NOT the flown leg (RPT-011).

    Args:
        path: path to a ``.rct`` file.

    Returns:
        dict: ``start_lat``, ``start_lon``, ``axis_deg``, ``radius_m``,
        ``max_entry_alt_m``, ``max_entry_speed_kmh``, ``working_time_min``.
    """
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("T:"):
            f = line[2:].split(",")
            return {
                "start_lat": float(f[1]),
                "start_lon": float(f[2]),
                "axis_deg": float(f[4]),
                "radius_m": float(f[5]),
                "max_entry_alt_m": float(f[6]),
                "max_entry_speed_kmh": float(f[7]),
                "working_time_min": float(f[9]) if len(f) > 9 else 30.0,
            }
    raise ValueError(f"no T: header found in {path}")


def course_geometry(task: dict) -> dict:
    """Build the right-isosceles course geometry in the shared metre grid.

    Construction rule (RPT-011): the three turnpoints sit at ``radius`` from the
    start on bearings ``{axis, axis+180, axis-90}``; the apex (right angle) is at
    ``axis-90``; the base/hypotenuse (``2*radius``) runs along the axis with the
    start at its midpoint; the two legs are ``radius*sqrt(2)``. The start/finish
    is the line perpendicular to the axis through the start.

    Coordinates are returned in the metre grid produced by
    :func:`projector` centred on the task start (start = origin ``(0, 0)``), so
    they overlay flown tracks directly.

    Args:
        task: a task dict carrying ``start_lat``/``start_lon`` and either
            ``axis_deg``+``radius_m`` (from :func:`parse_rct_task`) or the
            round-dataset spelling ``direction_deg``+``leg_length_m``.

    Returns:
        dict: ``start`` (0,0), ``turnpoints`` (3 corner ``(x,y)`` in draw order
        axis→apex→opposite), ``apex`` (the right-angle corner), ``start_finish``
        (two ``(x,y)`` endpoints of the perpendicular start line),
        ``axis_deg``, ``radius_m``, ``leg_m``, ``hypotenuse_m``, ``perimeter_m``.
    """
    axis = task.get("axis_deg", task.get("direction_deg"))
    radius = task.get("radius_m", task.get("leg_length_m"))

    def off(bearing_deg: float, dist: float) -> tuple[float, float]:
        b = math.radians(bearing_deg)
        return (dist * math.sin(b), dist * math.cos(b))

    tp_axis = off(axis, radius)
    tp_opp = off(axis + 180, radius)
    apex = off(axis - 90, radius)
    # Start/finish line: perpendicular to the axis (i.e. along axis-90 / axis+90)
    # through the start, half a radius each side for a legible marker.
    sf_half = radius * 0.5
    sf_a = off(axis - 90, sf_half)
    sf_b = off(axis + 90, sf_half)
    leg = radius * math.sqrt(2)
    return {
        "start": (0.0, 0.0),
        "turnpoints": [tp_axis, apex, tp_opp],
        "apex": apex,
        "start_finish": [sf_a, sf_b],
        "axis_deg": axis,
        "radius_m": radius,
        "leg_m": leg,
        "hypotenuse_m": 2 * radius,
        "perimeter_m": 2 * radius + 2 * leg,
    }


# --- Wind per round ---------------------------------------------------------
def wind_for_round(round_no: int) -> dict | None:
    """Return the per-round wind from ``weather_per_flight.csv``.

    Args:
        round_no: round number (1-17).

    Returns:
        dict with ``dir_deg`` (bearing the wind blows FROM), ``speed_kmh`` and
        ``speed_kn`` (knots), or ``None`` if the round has no weather row.
    """
    key = f"R{round_no:02d}"
    for row in load_weather_per_flight():
        if row.get("round") == key:
            spd = row.get("wind_speed_kmh")
            return {
                "dir_deg": row.get("wind_dir_deg"),
                "speed_kmh": spd,
                "speed_kn": (spd / 1.852) if isinstance(spd, (int, float)) else None,
            }
    return None


# --- Full-resolution replay tracks (multi-start isolation) ------------------
def _parse_iso(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp (trailing ``Z`` allowed) to an aware datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def fetch_replay(group_id: int) -> Path:
    """Return the local path to a heat-group's replay JSON, fetching if absent.

    Cached under ``data/tracks/replay_<group_id>.json``; fetched from the
    rcmodelspot ReplayGroup endpoint when missing.

    Args:
        group_id: the heat-group id.

    Returns:
        Path: the cached replay file path.
    """
    path = TRACKS / f"replay_{group_id}.json"
    if not path.exists():
        import requests

        TRACKS.mkdir(parents=True, exist_ok=True)
        resp = requests.get(API_REPLAY_GROUP.format(gid=group_id), timeout=60)
        resp.raise_for_status()
        path.write_text(resp.text, encoding="utf-8")
    return path


def load_replay(group_id: int) -> list[dict]:
    """Return the full replay (list of pilot dicts) for a heat-group.

    Each pilot dict carries ``pilot`` (identity), ``events`` (ARM/STA/TPC/PZE)
    and ``tail`` (the ~1 Hz sample list). Fetches and caches on first use.
    """
    return _read_json(fetch_replay(group_id))  # type: ignore[return-value]


def scored_start(events: list[dict]) -> datetime:
    """Return the scored start-line crossing (T0) from a multi-start replay.

    A replay can hold several ARM/STA cycles (aborted starts). The scored run is
    the one whose STA begins the LONGEST run to the next ARM/STA marker (the last
    STA's run extends to the end of the event log). That STA time is T0.

    Args:
        events: a pilot's event list.

    Returns:
        Datetime of the scored start-line crossing.
    """
    markers = sorted(
        (_parse_iso(e["time"]), e["type"])
        for e in events
        if e.get("type") in ("STA", "ARM")
    )
    end = max(_parse_iso(e["time"]) for e in events)
    best: datetime | None = None
    best_dur = -1.0
    for i, (t, ty) in enumerate(markers):
        if ty != "STA":
            continue
        nxt = markers[i + 1][0] if i + 1 < len(markers) else end
        dur = (nxt - t).total_seconds()
        if dur > best_dur:
            best_dur, best = dur, t
    if best is None:  # no STA at all — fall back to first sample time
        return end
    return best


def pilot_track_run_relative(pilot: dict, *, window_s: float = WORKING_WINDOW_S,
                             clip_to_last_tpc: bool = False) -> list[list]:
    """Return a pilot's full-resolution track in run-relative time.

    Time is measured from the scored start (T0 = 0 s). Samples are kept for the
    window ``[0, window_s]`` (the 30-minute task by default). Row layout matches
    the compact-track convention (:data:`TRACK_T` .. :data:`TRACK_GS`):
    ``[t_rel_s, lat, lon, gpsAlt_m, vario_ms, groundSpeed_kmh]``.

    Args:
        pilot: a replay pilot dict (``events`` + ``tail``).
        window_s: keep samples with ``0 <= t <= window_s``.
        clip_to_last_tpc: if True, also clip the tail at the pilot's last
            turn-point crossing (drops the final descent/rollout, matching the
            Energy-Management prototype).

    Returns:
        list[list]: run-relative track rows, time-ordered.
    """
    t0 = scored_start(pilot["events"])
    hi = window_s
    if clip_to_last_tpc:
        tpc = [
            (_parse_iso(e["time"]) - t0).total_seconds()
            for e in pilot["events"]
            if e.get("type") == "TPC"
        ]
        tpc = [t for t in tpc if 0 <= t <= window_s]
        if tpc:
            hi = min(window_s, max(tpc))
    rows: list[list] = []
    for pt in pilot.get("tail", []):
        t = (_parse_iso(pt["time"]) - t0).total_seconds()
        if t < 0 or t > hi + 0.01:
            continue
        rows.append([
            t,
            pt["latitude"],
            pt["longitude"],
            float(pt["gpsAlt"]),
            float(pt.get("vario", 0.0)),
            float(pt.get("groundSpeed", 0.0)),
        ])
    return rows


def full_tracks_for_round(round_no: int, *, clip_to_last_tpc: bool = False
                          ) -> tuple[list[list], list[list]]:
    """Return ``(bill_rows, leader_rows)`` full-res run-relative tracks for a round.

    Bill is matched by ``userGuid``; the same-air leader by the name recorded in
    the round index. Falls back to an empty list for a pilot not found in the
    replay. Uses the cached replay (fetches it if missing).

    Args:
        round_no: round number (1-17).
        clip_to_last_tpc: passed to :func:`pilot_track_run_relative`.

    Returns:
        tuple[list, list]: Bill's and the leader's run-relative track rows.
    """
    idx = {e["round"]: e for e in load_index()}[round_no]
    replay = load_replay(idx["group_id"])
    leader_name = (idx.get("leader_name") or "").strip().lower()

    def full_name(p: dict) -> str:
        pi = p["pilot"]
        return f"{pi.get('name', '')} {pi.get('surname', '')}".strip().lower()

    bill = next((p for p in replay if p["pilot"].get("userGuid") == BILL_GUID), None)
    leader = next((p for p in replay if full_name(p) == leader_name), None)
    bill_rows = pilot_track_run_relative(bill, clip_to_last_tpc=clip_to_last_tpc) if bill else []
    lead_rows = pilot_track_run_relative(leader, clip_to_last_tpc=clip_to_last_tpc) if leader else []
    return bill_rows, lead_rows


def group_scores(group_id: int) -> list[int]:
    """Return the sorted-descending normalised scores for a heat-group.

    Sourced from the authoritative results tree (``results.json``). Used by the
    per-round score-density (violin) dashboard component.

    Args:
        group_id: the heat-group id.

    Returns:
        list[int]: group scores, highest first (empty if the group is absent).
    """
    results = _read_json(SCORES / "results.json")
    for heat in results.get("competitionGpsTriangleHeat", []):  # type: ignore[union-attr]
        for grp in heat.get("competitionGpsTriangleGroup", []):
            if grp.get("competitionGpsTriangleGroupId") == group_id:
                return sorted(
                    (r["score"] for r in grp.get("competitionGpsTriangleResult", [])),
                    reverse=True,
                )
    return []


# --- Trajectory pooling: distance-from-course & thermalling turn radius -----
# The 14 distance (triangle) rounds: every round except the three speed sprints
# (4, 10, 16), which are point-to-point runs with no triangle outline to
# measure against. Bill flew all 14 and each is pooled equally at the point
# level (~1 Hz samples => time-weighted).
DISTANCE_ROUNDS = [1, 2, 3, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 17]


def _seg_distance(px: float, py: float, ax: float, ay: float,
                  bx: float, by: float) -> float:
    """Return the distance from point ``(px, py)`` to segment ``a-b`` (metres).

    Distances are computed in the flat local metre grid from :func:`projector`.
    """
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / l2
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def _dist_from_course(x: float, y: float,
                      turnpoints: list[tuple[float, float]]) -> float:
    """Return the straight-line distance from ``(x, y)`` to the course outline.

    The outline is the closed three-leg triangle through the three turnpoints;
    the value is the minimum distance to any of the three legs (metres).
    """
    a, b, c = turnpoints
    return min(
        _seg_distance(x, y, a[0], a[1], b[0], b[1]),
        _seg_distance(x, y, b[0], b[1], c[0], c[1]),
        _seg_distance(x, y, c[0], c[1], a[0], a[1]),
    )


def _wrap180(deg: float) -> float:
    """Wrap a signed angle in degrees into the range ``(-180, 180]``."""
    return (deg + 180.0) % 360.0 - 180.0


def _histogram(values: list[float], edges: list[float]) -> list[int]:
    """Count ``values`` into the half-open bins defined by ``edges``.

    A value at or beyond the last edge falls into the final bin (so a long tail
    is not silently dropped).
    """
    counts = [0] * (len(edges) - 1)
    for v in values:
        for i in range(len(edges) - 1):
            if edges[i] <= v < edges[i + 1]:
                counts[i] += 1
                break
        else:
            if v >= edges[-1]:
                counts[-1] += 1
    return counts


def _density(values: list[float], edges: list[float],
             *, median_values: list[float] | None = None) -> dict:
    """Return a density record ``{frac, n, median}`` for ``values`` over ``edges``.

    ``frac`` is each bin's share of the total (sums to ~1); ``median`` is taken
    over ``median_values`` when given (e.g. a wider sane set than the display
    window), else over ``values``.
    """
    counts = _histogram(values, edges)
    total = sum(counts) or 1
    med_src = median_values if median_values is not None else values
    return {
        "frac": [c / total for c in counts],
        "n": len(med_src),
        "median": round(statistics.median(med_src), 1) if med_src else None,
    }


def pooled_distance_from_course(rounds: list[int] | None = None, *,
                                bin_width_m: int = 20,
                                max_m: int = 600) -> dict:
    """Pool the distance-from-course-outline distribution across distance rounds.

    For every ~1 Hz track point of Bill and of that round's same-air winner, the
    straight-line distance to the nearest of the three triangle legs is measured
    in the shared local metre grid (:func:`projector` + :func:`course_geometry`).
    Because samples are ~1 Hz, each bin's share is a share of *flight time*.

    Args:
        rounds: round numbers to pool (default :data:`DISTANCE_ROUNDS`).
        bin_width_m: histogram bin width in metres (default 20).
        max_m: last bin edge / display ceiling in metres (default 600). The
            median is computed over the full uncapped sample.

    Returns:
        dict: ``edges`` (bin edges, m) and ``bill``/``leader`` records, each
        ``{frac: list[float], n: int, median: float}`` where ``frac`` is the
        share of flight time per bin and ``median`` is in metres.
    """
    rounds = rounds if rounds is not None else DISTANCE_ROUNDS
    edges = list(range(0, max_m + bin_width_m, bin_width_m))
    vals: dict[str, list[float]] = {"bill": [], "leader": []}
    for n in rounds:
        r = load_round(n)
        turnpoints = course_geometry(r["task"])["turnpoints"]
        proj = projector(r["task"]["start_lat"], r["task"]["start_lon"])
        bill_rows, lead_rows = full_tracks_for_round(n, clip_to_last_tpc=True)
        for role, rows in (("bill", bill_rows), ("leader", lead_rows)):
            for row in rows:
                x, y = proj(row[TRACK_LAT], row[TRACK_LON])
                vals[role].append(_dist_from_course(x, y, turnpoints))
    return {
        "edges": edges,
        "bill": _density(vals["bill"], edges),
        "leader": _density(vals["leader"], edges),
    }


def _sustained_climb_radii(rows: list[list], proj, *,
                           min_duration_s: float = 12.0,
                           min_turn_deg: float = 270.0,
                           min_gain_m: float = 2.0) -> list[float]:
    """Return per-point turn radii ``r = v / omega`` inside sustained climbs.

    A sustained climb is a continuous run of circling (smoothed bearing rate
    above a threshold) lasting at least ``min_duration_s``, sweeping at least
    ``min_turn_deg`` of net turn and with a net height gain of at least
    ``min_gain_m`` — the same thermal-circling detector the phase decomposition
    uses. Within each such run, ``r`` is the ground speed (m/s) divided by the
    angular rate (rad/s) at each point.

    Args:
        rows: run-relative track rows (``[t, lat, lon, alt, vario, gs_kmh]``).
        proj: the shared ``(lat, lon) -> (x, y)`` metre-grid projector.
        min_duration_s: minimum run length in seconds.
        min_turn_deg: minimum absolute net turn over the run, in degrees.
        min_gain_m: minimum net altitude gain over the run, in metres.

    Returns:
        list[float]: turn radii in metres, one per qualifying point.
    """
    n = len(rows)
    if n < 2:
        return []
    xy = [proj(row[TRACK_LAT], row[TRACK_LON]) for row in rows]
    course_bearing: list[float | None] = [None] * n
    for i in range(n - 1):
        dx = xy[i + 1][0] - xy[i][0]
        dy = xy[i + 1][1] - xy[i][1]
        if dx or dy:
            course_bearing[i] = math.degrees(math.atan2(dx, dy)) % 360.0
        else:
            course_bearing[i] = course_bearing[i - 1] if i else 0.0
    course_bearing[-1] = course_bearing[-2]
    bearing_rate = [0.0] * n
    for i in range(1, n):
        dt = rows[i][TRACK_T] - rows[i - 1][TRACK_T]
        if dt > 0 and course_bearing[i] is not None and course_bearing[i - 1] is not None:
            bearing_rate[i] = _wrap180(course_bearing[i] - course_bearing[i - 1]) / dt
    gs_ms = [rows[i][TRACK_GS] / 3.6 for i in range(n)]
    absbr = [abs(b) for b in bearing_rate]
    smooth = []
    for i in range(n):
        lo, hi = max(0, i - 1), min(n, i + 2)
        smooth.append(sum(absbr[lo:hi]) / (hi - lo))
    turn_threshold = 7.0  # deg/s: a wing genuinely circling, not weaving
    radii: list[float] = []
    i = 0
    while i < n:
        if smooth[i] > turn_threshold:
            j = i
            cum = 0.0
            while j < n and smooth[j] > turn_threshold:
                if j > i:
                    cum += bearing_rate[j] * (rows[j][TRACK_T] - rows[j - 1][TRACK_T])
                j += 1
            lo, hi = i, j - 1
            dur = rows[hi][TRACK_T] - rows[lo][TRACK_T]
            gain = rows[hi][TRACK_ALT] - rows[lo][TRACK_ALT]
            if dur >= min_duration_s and abs(cum) >= min_turn_deg and gain >= min_gain_m:
                for k in range(lo, hi + 1):
                    omega = abs(bearing_rate[k]) * math.pi / 180.0
                    if omega > 0.05 and gs_ms[k] > 3:
                        radii.append(gs_ms[k] / omega)
            i = j
        else:
            i += 1
    return radii


def pooled_turn_radius(rounds: list[int] | None = None, *,
                       bin_width_m: int = 5, max_m: int = 100,
                       sane_max_m: int = 200) -> dict:
    """Pool the thermalling turn-radius distribution across distance rounds.

    For Bill and each round's same-air winner, per-point turn radii inside
    detected sustained climbs (:func:`_sustained_climb_radii`) are pooled over
    the distance rounds. The density is taken over the display window
    ``(3, max_m)`` m; each pilot's median is taken over the wider sane set
    ``(3, sane_max_m)`` m so a few wide arcs still count.

    Args:
        rounds: round numbers to pool (default :data:`DISTANCE_ROUNDS`).
        bin_width_m: histogram bin width in metres (default 5).
        max_m: last bin edge / display ceiling in metres (default 100).
        sane_max_m: upper bound (m) for the median sample (default 200).

    Returns:
        dict: ``edges`` (bin edges, m) and ``bill``/``leader`` records, each
        ``{frac: list[float], n: int, median: float}`` where ``frac`` is the
        share of circling time per bin and ``median`` is in metres.
    """
    rounds = rounds if rounds is not None else DISTANCE_ROUNDS
    edges = list(range(0, max_m + bin_width_m, bin_width_m))
    radii: dict[str, list[float]] = {"bill": [], "leader": []}
    for n in rounds:
        r = load_round(n)
        proj = projector(r["task"]["start_lat"], r["task"]["start_lon"])
        bill_rows, lead_rows = full_tracks_for_round(n, clip_to_last_tpc=True)
        for role, rows in (("bill", bill_rows), ("leader", lead_rows)):
            radii[role].extend(_sustained_climb_radii(rows, proj))
    out: dict = {"edges": edges}
    for role in ("bill", "leader"):
        disp = [x for x in radii[role] if 3 < x < max_m]
        sane = [x for x in radii[role] if 3 < x < sane_max_m]
        out[role] = _density(disp, edges, median_values=sane)
    return out


def build_context() -> dict:
    """Assemble the shared context dict passed to every page's ``render``.

    Returns:
        dict: keys ``index``, ``rounds`` (all 17 datasets), ``rounds_csv``,
        ``metrics`` (per-pilot-per-round), ``phase`` (summary), ``weather``,
        ``weather_corr``, ``field``, ``official`` (Bill's reconciled summary)
        and ``round_labels``.
    """
    return {
        "index": load_index(),
        "rounds": load_all_rounds(),
        "rounds_csv": load_rounds_csv(),
        "metrics": load_per_round_metrics(),
        "phase": load_phase_summary(),
        "weather": load_weather_per_flight(),
        "weather_corr": load_weather_correlations(),
        "field": load_field_summary(),
        "official": bill_official_summary(),
        "round_labels": round_labels(),
    }
