"""Build-data loader tests (scripts/build/data.py).

Covers the identity resolution the per-round charts depend on. The same-air
leader used to be matched by lower-cased display name with a silent fallback to
an empty track, so a spelling or accent difference between the results tree and
the replay feed would have emptied a chart without failing anything.
"""

from __future__ import annotations

import pytest

from scripts.build import data


ROUNDS = list(range(1, 18))


@pytest.mark.parametrize("n", ROUNDS)
def test_group_leader_guid_resolves_for_every_round(n):
    """Each round's same-air leader resolves to a single userGuid."""
    entry = {e["round"]: e for e in data.load_index()}[n]
    guid = data.group_leader_guid(entry["group_id"])
    assert isinstance(guid, str) and len(guid) == 36, (n, guid)
    standing = {s["userGuid"]: s for s in data.load_standings()}[guid]
    assert standing is not None


@pytest.mark.parametrize("n", ROUNDS)
def test_leader_guid_matches_the_indexed_leader_name(n):
    """The guid-matched leader is the pilot the round index names.

    Guards the switch from name matching to guid matching: the two must agree
    on every round, so the change is a robustness fix and not a data change.
    """
    entry = {e["round"]: e for e in data.load_index()}[n]
    guid = data.group_leader_guid(entry["group_id"])
    replay = data.load_replay(entry["group_id"])
    pilot = next(p for p in replay if p["pilot"].get("userGuid") == guid)
    full = f"{pilot['pilot'].get('name', '')} {pilot['pilot'].get('surname', '')}"
    assert full.strip().lower() == entry["leader_name"].strip().lower(), (n, full)


def test_full_tracks_raise_rather_than_return_an_empty_leader_track():
    """An unresolvable leader raises instead of silently yielding no track."""
    with pytest.raises(KeyError):
        data.group_leader_guid(-1)


@pytest.mark.parametrize("n", [1, 12, 17])
def test_full_tracks_for_round_returns_both_pilots(n):
    """Both pilots' full-resolution tracks are non-empty for sampled rounds."""
    bill_rows, lead_rows = data.full_tracks_for_round(n, clip_to_last_tpc=True)
    assert bill_rows, f"round {n}: no Bill track"
    assert lead_rows, f"round {n}: no leader track"
