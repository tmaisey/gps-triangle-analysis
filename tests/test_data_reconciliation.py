"""Reconciliation tests: computed data must match the authoritative results.

Validation alternative to classic TDD for this data/reporting deliverable
(PRD §11): the loaders in :mod:`scripts.build.data` must reconcile to the raw
rcmodelspot standings (``data/scores/results.json``). These should PASS once
``data.py`` is correct.

Covers DATA-001 / ANL-001 acceptance: Bill's 17 flights reconcile on laps and
average speed; the event total (worst round dropped) is 12,562; overall rank is
22/38; landing is 600 on all 14 distance rounds.
"""

from __future__ import annotations

import pytest

from scripts.build import data

M_PER_S_TO_KMH = 3.6


@pytest.fixture(scope="module")
def official():
    """Bill's reconciled summary from the authoritative standings."""
    return data.bill_official_summary()


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
