"""Reconciliation tests: computed data must match the authoritative results.

Validation alternative to classic TDD for this data/reporting deliverable
(PRD §11): the loaders in :mod:`scripts.build.data` must reconcile to the raw
rcmodelspot standings (``data/scores/results.json``). These should PASS once
``data.py`` is correct.

Covers DATA-001, DATA-002, DATA-003 and ANL-001..ANL-004 acceptance. The
strongest assertions here are *independent* cross-checks against the cached raw
API payloads (``data/scores/results.json``, ``data/tracks/replay_*.json``,
``data/weather_era5_oschatz.json``) rather than against the pipeline's own
outputs: the scored start vs the API's own scored ``gpsTriangleStats`` entry,
the API-implied scoring-lap distance vs the ADR-008 course perimeter, and the
ERA5 hour mapping recomputed from each group's published start time.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta, timezone

import pytest

from scripts.build import data

M_PER_S_TO_KMH = 3.6

#: The regs scoring lap for a 350 m-radius right-isosceles course (ADR-008):
#: base 2R + two legs of R*sqrt(2) => R * (2 + 2*sqrt(2)) ~ 1689.9 m.
COURSE_PERIMETER_M = 350 * (2 + 2 * math.sqrt(2))

#: Rounds flown as one-lap speed sprints rather than distance tasks.
SPEEDRUN_ROUNDS = (4, 10, 16)
DISTANCE_ROUNDS = tuple(r for r in range(1, 18) if r not in SPEEDRUN_ROUNDS)


@pytest.fixture(scope="module")
def official():
    """Bill's reconciled summary from the authoritative standings."""
    return data.bill_official_summary()


@pytest.fixture(scope="module")
def rounds_manifest():
    """The 17-round manifest (round -> group id, Bill and same-air leader)."""
    return json.loads((data.TRACKS / "rounds_manifest.json").read_text())


@pytest.fixture(scope="module")
def api_flights(rounds_manifest):
    """Compact per-pilot facts pulled straight from the cached replay JSON.

    Each replay is loaded once and reduced to a small summary so the whole
    suite makes a single pass over the 64 MB track cache.

    Returns:
        dict: ``(round_no, role)`` -> dict with ``stat`` (the API's scored
        ``gpsTriangleStats`` entry, i.e. the attempt with the longest elapsed
        time), ``scored_start`` (:func:`data.scored_start` of the pilot's event
        log), ``n_stats`` (number of logged start attempts) and ``lap_events``
        (count of lap completions logged after the scored start).
    """
    out: dict[tuple[int, str], dict] = {}
    for rd in rounds_manifest:
        group = data.load_replay(rd["group_id"])
        for role in ("bill", "leader"):
            guid = rd[role]["userGuid"]
            pilot = next(p for p in group if p["pilot"]["userGuid"] == guid)
            stats = pilot["gpsTriangleStats"]
            scored = max(stats, key=lambda s: s["timeElapsedSeconds"])
            t0 = data.scored_start(pilot["events"])
            laps_after_t0 = sum(
                1
                for e in pilot["events"]
                if e.get("lapStat") and data._parse_iso(e["time"]) >= t0 - timedelta(seconds=5)
            )
            out[(rd["round"], role)] = {
                "stat": scored,
                "scored_start": t0,
                "n_stats": len(stats),
                "lap_events": laps_after_t0,
            }
        del group
    return out


def test_bill_total_score_is_12562(official):
    """Event total (17 rounds, worst dropped) equals the published 12,562."""
    assert official["total_score"] == 12562


def test_bill_overall_rank_is_22(official):
    """Bill ranks 22nd when standings are ordered by total score."""
    assert official["rank"] == 22


def test_bill_has_17_flights(official):
    """All 17 rounds are present in the results tree."""
    assert official["n_flights"] == 17


def test_landing_is_600_on_14_distance_rounds(official):
    """Every distance round scores a clean 600 landing (14 of them)."""
    landings = official["distance_landings"]
    assert len(landings) == 14
    assert all(v == 600 for v in landings)


def test_laps_reconcile_to_round_index(official):
    """Per-round laps in the embeddable index match the authoritative results."""
    index = data.load_index()
    official_laps = [r["laps"] for r in official["results"]]
    index_laps = [e["bill"]["laps"] for e in sorted(index, key=lambda e: e["round"])]
    assert index_laps == official_laps


def test_avg_speed_reconciles_to_results(official):
    """Round index avg speed (km/h) matches results speed (m/s x 3.6)."""
    index = {e["round"]: e for e in data.load_index()}
    for i, res in enumerate(official["results"], 1):
        expected_kmh = res["speed"] * M_PER_S_TO_KMH
        got = index[i]["bill"]["speed_kmh"]
        assert got == pytest.approx(expected_kmh, abs=0.1), f"round {i}"


def test_rounds_csv_scores_match_results(official):
    """Per-round scores in bill_oschatz_rounds.csv match the results tree."""
    csv_scores = [row["score"] for row in data.load_rounds_csv()]
    official_scores = [r["score"] for r in official["results"]]
    assert csv_scores == official_scores


def test_three_speedrun_rounds_have_zero_landing(official):
    """The three speed-sprint rounds (4, 10, 16) carry no landing points."""
    zero_landing = [i for i, r in enumerate(official["results"], 1)
                    if r["landing"] == 0]
    assert zero_landing == [4, 10, 16]


# --- DATA-002: scoring flight and same-air leader ---------------------------

def test_data002_scored_start_matches_api_scored_stats(api_flights):
    """DATA-002: our multi-start T0 equals the API's own scored flightStart.

    Independent check: for Bill and the same-air leader in all 17 rounds, the
    start picked by :func:`data.scored_start` must match the ``flightStart`` of
    the ``gpsTriangleStats`` entry the API actually scored (the longest run).
    """
    for (round_no, role), f in sorted(api_flights.items()):
        want = data._parse_iso(f["stat"]["flightStart"])
        delta = abs((f["scored_start"] - want).total_seconds())
        assert delta < 2.0, f"round {round_no} {role}: T0 off by {delta:.1f} s"


def test_data002_multi_start_rounds_are_present_and_isolated(api_flights):
    """DATA-002: the multi-start case is real and the scored attempt is isolated."""
    multi = [k for k, f in api_flights.items() if f["n_stats"] > 1]
    assert multi, "expected at least one multi-start pilot-round in the cache"
    for round_no, role in multi:
        f = api_flights[(round_no, role)]
        assert f["scored_start"] == data._parse_iso(f["stat"]["flightStart"]), (
            f"round {round_no} {role}: scored start not isolated from "
            f"{f['n_stats']} logged attempts")


def test_data002_bill_and_leader_tracks_present_all_rounds():
    """DATA-002: full-resolution Bill and leader tracks exist for all 17 rounds."""
    for round_no in range(1, 18):
        bill_rows, lead_rows = data.full_tracks_for_round(round_no)
        assert bill_rows, f"round {round_no}: no Bill track"
        assert lead_rows, f"round {round_no}: no leader track"


def test_data002_leader_laps_and_speed_reconcile(rounds_manifest):
    """DATA-002: leader rows in per_round_metrics reconcile to the results tree."""
    by_round = {rd["round"]: rd for rd in rounds_manifest}
    leader_rows = [r for r in data.load_per_round_metrics() if r["role"] == "leader"]
    assert len(leader_rows) == 17
    for row in leader_rows:
        want = by_round[row["round"]]["leader"]
        assert row["pilot"] == want["name"], f"round {row['round']}"
        assert row["laps"] == want["laps"], f"round {row['round']}"
        assert row["avg_speed_kmh"] == pytest.approx(
            want["speed_ms"] * M_PER_S_TO_KMH, abs=0.1), f"round {row['round']}"
        assert row["score"] == want["score"], f"round {row['round']}"


# --- DATA-003: ERA5 weather enrichment --------------------------------------

@pytest.fixture(scope="module")
def era5():
    """The cached raw ERA5 archive payload."""
    return json.loads(
        (data.REPO_ROOT / "data" / "weather_era5_oschatz.json").read_text())


def test_data003_every_flight_maps_to_its_own_start_hour(era5):
    """DATA-003: each flight's weather hour is its group start time, rounded.

    Recomputed independently from the group ``startTime`` published in
    ``results.json`` and the archive's own ``utc_offset_seconds``.
    """
    results = json.loads((data.SCORES / "results.json").read_text())
    offset = timezone(timedelta(seconds=era5["utc_offset_seconds"]))
    starts = []
    for heat in sorted(results["competitionGpsTriangleHeat"], key=lambda h: h["order"]):
        for group in heat["competitionGpsTriangleGroup"]:
            if any(r["userGuid"] == data.BILL_GUID
                   for r in group["competitionGpsTriangleResult"]):
                starts.append(group["startTime"])
    assert len(starts) == 17

    rows = data.load_weather_per_flight()
    assert len(rows) == 17
    for row, start_utc in zip(rows, starts):
        local = datetime.fromisoformat(start_utc.replace("Z", "+00:00")).astimezone(offset)
        expect = (local + timedelta(minutes=30)).replace(
            minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00")
        assert row["wx_hour_local"] == expect, f"{row['round']}"
        assert row["start_datetime_local"] == local.strftime("%Y-%m-%d %H:%M")


def test_data003_weather_values_come_from_the_archive_hour(era5):
    """DATA-003: joined weather values equal the ERA5 row for that hour."""
    hourly = era5["hourly"]
    idx = {t: i for i, t in enumerate(hourly["time"])}
    for row in data.load_weather_per_flight():
        i = idx[row["wx_hour_local"]]
        assert row["wind_speed_kmh"] == pytest.approx(hourly["windspeed_10m"][i])
        assert row["temp_c"] == pytest.approx(hourly["temperature_2m"][i])
        assert row["shortwave_radiation"] == pytest.approx(
            hourly["shortwave_radiation"][i])


def test_data003_cape_is_null_in_the_archive_and_absent_from_the_csv(era5):
    """DATA-003: ERA5 returns no CAPE, so the column is not carried forward."""
    assert all(v is None for v in era5["hourly"]["cape"])
    with open(data.ANALYSIS / "weather_per_flight.csv", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert "cape" not in header
    with open(data.ANALYSIS / "bill_flights_weather_full.csv", encoding="utf-8") as fh:
        full_header = next(csv.reader(fh))
    assert "cape" not in full_header


# --- ANL-001: per-round metric bundle ---------------------------------------

def test_anl001_api_implied_lap_distance_is_the_course_perimeter(api_flights):
    """ANL-001: ``avg_speed * elapsed / laps`` equals the ADR-008 lap, 1689.9 m.

    The API's distance fields are all zero, so this is the check the data does
    support: it validates the course geometry and the m/s-to-km/h conversions
    together, on every scored flight.
    """
    for (round_no, role), f in sorted(api_flights.items()):
        st = f["stat"]
        implied = st["allTrianglesAvgSpeed"] * st["timeElapsedSeconds"] / st["laps"]
        assert implied == pytest.approx(COURSE_PERIMETER_M, abs=1.0), (
            f"round {round_no} {role}: implied lap {implied:.1f} m")


def test_anl001_perimeter_constants_match_the_adr008_course():
    """ANL-001/ADR-008: analysis scripts use the right-isosceles perimeter."""
    from scripts import compute_metrics, trajectory_poc

    geom = data.course_geometry({"start_lat": 51.297718, "start_lon": 13.082957,
                                 "direction_deg": 74.8, "leg_length_m": 350})
    assert geom["perimeter_m"] == pytest.approx(COURSE_PERIMETER_M, abs=0.01)
    assert compute_metrics.PERIMETER_M == pytest.approx(COURSE_PERIMETER_M, abs=0.01)
    assert trajectory_poc.PERIMETER_M == pytest.approx(COURSE_PERIMETER_M, abs=0.01)


def test_anl001_track_derived_lap_count_matches_official(official):
    """ANL-001: laps counted off the track equal the authoritative lap count."""
    index = {e["round"]: e for e in data.load_index()}
    for i, res in enumerate(official["results"], 1):
        flown = len(index[i]["bill"]["lap_durations_s"]) if "lap_durations_s" in index[i]["bill"] else None
        if flown is None:  # index carries headline numbers only; use the round file
            flown = len(data.load_round(i)["bill"]["lap_durations_s"])
        assert flown == res["laps"], f"round {i}: {flown} lap markers vs {res['laps']}"


def test_anl001_clean_lap_efficiency_column_is_named_for_the_course():
    """ANL-001: the line-efficiency column names the course, not a stale 1050 m."""
    with open(data.ANALYSIS / "per_round_metrics.csv", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert "fastest_clean_lap_eff_vs_1050" not in header
    assert "fastest_clean_lap_eff_vs_course" in header


def test_anl001_clean_lap_speed_is_consistent_with_the_course_perimeter():
    """ANL-001: clean-lap speed is the ADR-008 perimeter over the lap time."""
    for round_no in DISTANCE_ROUNDS:
        rnd = data.load_round(round_no)
        for role in ("bill", "leader"):
            durs = rnd[role]["lap_durations_s"]
            if not durs:
                continue
            fastest = min(durs)
            implied = COURSE_PERIMETER_M / fastest * M_PER_S_TO_KMH
            row = next(r for r in data.load_per_round_metrics()
                       if r["round"] == round_no
                       and r["role"] == ("BILL" if role == "bill" else "leader"))
            # the reported clean lap is the fastest NON-climbing lap, so it can
            # only be slower than (or equal to) the fastest lap overall.
            assert 0 < row["fastest_clean_lap_speed_kmh"] <= implied + 0.5, (
                f"round {round_no} {role}")


# --- ANL-002: flight-phase decomposition ------------------------------------

@pytest.fixture(scope="module")
def phase_rounds():
    """Per-round raw phase decomposition (14 distance rounds)."""
    return json.loads((data.ANALYSIS / "phase_perround_raw.json").read_text())


def test_anl002_speedrun_rounds_are_excluded(phase_rounds):
    """ANL-002: the three one-lap sprints carry no phase decomposition."""
    assert [r["round"] for r in phase_rounds] == list(DISTANCE_ROUNDS)
    meta = data.load_phase_summary()["meta"]
    assert sorted(meta["excluded_speedruns"]) == list(SPEEDRUN_ROUNDS)


def test_anl002_phase_times_sum_to_lap_time(phase_rounds):
    """ANL-002: cruise + turn + climb reconstructs each lap's duration."""
    worst = 0.0
    for rnd in phase_rounds:
        for role in ("bill", "leader"):
            for lap in rnd[role]["_laps"]:
                got = lap["cruise_t"] + lap["turn_t"] + lap["climb_t"]
                worst = max(worst, abs(got - lap["lap_t"]))
    assert worst < 1.0, f"worst phase-sum residual {worst:.2f} s"


def test_anl002_lap_times_sum_to_aloft_time(phase_rounds):
    """ANL-002: the per-lap times partition the aloft window exactly."""
    for rnd in phase_rounds:
        for role in ("bill", "leader"):
            total = sum(lap["lap_t"] for lap in rnd[role]["_laps"])
            assert total == pytest.approx(rnd[role]["aloft_time_s"], abs=2.0), (
                f"round {rnd['round']} {role}")


def test_anl002_aloft_time_matches_api_elapsed(phase_rounds, api_flights):
    """ANL-002: aloft time equals the API's ``timeElapsedSeconds``.

    Independent cross-check, restricted to the single-attempt flights. Where a
    pilot logged several start attempts the decomposition spans the whole event
    log (see :func:`test_anl002_multi_start_aloft_spans_all_attempts`), so the
    scored attempt's elapsed time is not the right comparator there.
    """
    checked = 0
    for rnd in phase_rounds:
        for key, role in (("bill", "bill"), ("leader", "leader")):
            f = api_flights[(rnd["round"], role)]
            if f["n_stats"] != 1:
                continue
            checked += 1
            assert rnd[key]["aloft_time_s"] == pytest.approx(
                f["stat"]["timeElapsedSeconds"], abs=2.0), (
                f"round {rnd['round']} {role}")
    assert checked >= 20, f"only {checked} single-start flights cross-checked"


def test_anl002_multi_start_aloft_spans_all_attempts(phase_rounds, api_flights):
    """ANL-002: known limitation — multi-start aloft time covers every attempt.

    ``phase_decomp`` keys its window off the *first* logged ``flightStart`` and
    counts every lap marker, so on a re-started flight the aloft window spans
    the aborted attempts too. Pinned here so the behaviour cannot drift
    unnoticed: it must never fall below the scored attempt's elapsed time.
    """
    multi = 0
    for rnd in phase_rounds:
        for key, role in (("bill", "bill"), ("leader", "leader")):
            f = api_flights[(rnd["round"], role)]
            if f["n_stats"] == 1:
                continue
            multi += 1
            assert rnd[key]["aloft_time_s"] >= f["stat"]["timeElapsedSeconds"] - 2.0
    assert multi, "expected multi-start flights among the 14 distance rounds"


# --- ANL-003: condition dependence ------------------------------------------

def test_anl003_distance_only_score_correlations_are_reported():
    """ANL-003: the score-vs-conditions row is available over the 14 distance rounds."""
    rows = data.load_weather_correlations()
    dist = [r for r in rows
            if r["target"].startswith("normalised_score") and r["n"] == 14]
    assert dist, "no distance-only normalised_score correlation row"
    assert all("distance" in r["target"] for r in dist)
    predictors = {r["predictor"] for r in dist}
    assert "radiation (thermal proxy)" in predictors


def test_anl003_all_17_score_row_is_labelled_as_such():
    """ANL-003: the all-rounds row stays, explicitly labelled with its n."""
    rows = data.load_weather_correlations()
    all17 = [r for r in rows
             if r["target"].startswith("normalised_score") and r["n"] == 17]
    assert all17
    assert all("all 17" in r["target"] for r in all17)


def test_anl003_radiation_association_is_positive_and_suggestive():
    """ANL-003: thermal strength associates positively with relative standing.

    Distance-only (n=14); asserted as a direction and a magnitude band, not as
    a significance claim — the critical |r| at n=14 is ~0.53.
    """
    rows = data.load_weather_correlations()
    row = next(r for r in rows
               if r["target"].startswith("normalised_score") and r["n"] == 14
               and r["predictor"] == "radiation (thermal proxy)")
    assert 0.3 < row["spearman_rho"] < 0.8
    assert row["pearson_r"] > 0.0


def test_anl003_laps_correlations_use_the_14_distance_rounds():
    """ANL-003: the laps / speed targets are computed over distance rounds only."""
    rows = data.load_weather_correlations()
    for prefix in ("laps (", "speed_kmh ("):
        subset = [r for r in rows if r["target"].startswith(prefix)]
        assert subset
        assert all(r["n"] == 14 for r in subset), prefix


# --- ANL-004: week-long progression -----------------------------------------

def test_anl004_progression_is_chronological_over_14_distance_rounds():
    """ANL-004: distance rounds are in date order with both series populated."""
    rows = [r for r in data.load_weather_per_flight()
            if r["task_type"] == "distance"]
    assert len(rows) == 14
    stamps = [r["start_datetime_local"] for r in rows]
    assert stamps == sorted(stamps)
    assert stamps[0].startswith("2026-08-03")
    assert stamps[-1].startswith("2026-08-08")
    assert len({s[:10] for s in stamps}) == 6, "expected six competition days"
    for r in rows:
        assert r["normalised_score"] is not None
        assert r["laps"] is not None


def test_anl004_progression_scores_match_the_results_tree(official):
    """ANL-004: the plotted normalised scores are the authoritative round scores."""
    by_round = {int(r["round"][1:]): r for r in data.load_weather_per_flight()}
    for i, res in enumerate(official["results"], 1):
        assert by_round[i]["normalised_score"] == res["score"], f"round {i}"


# --- Presentation hygiene in generated analysis text ------------------------

def test_biggest_loss_notes_pluralise_laps_properly():
    """Generated notes read as prose: '1 lap' / '2 laps', never '1 lap(s)'."""
    notes = [e["biggest_loss_note"] for e in data.load_index()]
    assert notes
    assert not any("lap(s)" in n for n in notes)
    singular = [n for n in notes if "gained 1 lap" in n]
    assert singular, "expected at least one one-lap window"
    assert all(not n.split("gained 1 lap")[1].startswith("s") for n in singular)


def test_fetch_script_writes_relative_to_the_repo_root():
    """Re-fetching is reproducible on any machine (no hard-coded home path)."""
    src = (data.REPO_ROOT / "scripts" / "fetch_data.py").read_text()
    assert "/Users/" not in src
    assert "Path(__file__)" in src
