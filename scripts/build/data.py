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
from pathlib import Path

# Repo root = two levels up from this file (scripts/build/data.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = REPO_ROOT / "analysis"
ROUND_DATA_DIR = ANALYSIS / "round_data"
SCORES = REPO_ROOT / "data" / "scores"

BILL_GUID = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"


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
