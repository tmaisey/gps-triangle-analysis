"""Tests for the Stage-1 shared foundation of the v2 report.

Covers the new data helpers (course geometry, multi-start isolation, projection,
wind), the ported chart generators (Energy Management dual-panel, RPT-011 ground
track, RPT-022 grouped bars/strips), the per-round dashboard components, the
retitle/label/legality changes and the RPT-019 font inlining.

Data-reconciliation style (PRD §11): assertions check computed geometry against
the authoritative construction rule and the observable chart/HTML contract, not
implementation detail.

Spec: RPT-011, RPT-012, RPT-013, RPT-014, RPT-015, RPT-017, RPT-018, RPT-019,
RPT-022, DSN-001.
"""

from __future__ import annotations

import math

import pytest

from scripts.build import assemble, charts, components as C, dashboard, data, design


# --- data helpers -----------------------------------------------------------
def test_course_geometry_is_right_isosceles():
    """Turnpoints sit at the radius on {axis, axis+180, axis-90}; the triangle
    is right-isosceles (hypotenuse 2*radius, legs radius*sqrt2, right angle at
    the apex) — RPT-011."""
    g = data.course_geometry(data.load_round(17)["task"])
    r = g["radius_m"]
    assert g["hypotenuse_m"] == pytest.approx(2 * r, rel=1e-6)
    assert g["leg_m"] == pytest.approx(r * math.sqrt(2), rel=1e-6)
    # right angle at the apex: the two leg vectors are perpendicular
    a, apex, b = g["turnpoints"]
    ca = (a[0] - apex[0], a[1] - apex[1])
    cb = (b[0] - apex[0], b[1] - apex[1])
    assert ca[0] * cb[0] + ca[1] * cb[1] == pytest.approx(0, abs=1e-6)
    # start is the midpoint of the hypotenuse
    assert (a[0] + b[0]) / 2 == pytest.approx(0, abs=1e-6)
    assert (a[1] + b[1]) / 2 == pytest.approx(0, abs=1e-6)


def test_projection_matches_haversine():
    """The shared equirectangular projection reproduces haversine distance for
    two nearby points (used identically for course and tracks)."""
    task = data.load_round(17)["task"]
    to_xy = data.projector(task["start_lat"], task["start_lon"])
    lat2, lon2 = task["start_lat"] + 0.001, task["start_lon"] + 0.0015
    x, y = to_xy(lat2, lon2)
    proj = math.hypot(x, y)
    hav = data.haversine_m(task["start_lat"], task["start_lon"], lat2, lon2)
    assert proj == pytest.approx(hav, rel=0.01)


def test_scored_start_isolates_longest_run_window():
    """The scored track is a single 30-min window from the scored start; both
    pilots are isolated (RPT-013)."""
    bill, leader = data.full_tracks_for_round(6)
    assert bill and leader
    for rows in (bill, leader):
        assert rows[0][0] >= 0
        assert rows[-1][0] <= data.WORKING_WINDOW_S + 1
        # time is monotonic and run-relative (starts at/after zero)
        assert rows[0][0] < 60  # begins near T0, not a 25-min clock offset


def test_wind_for_round_has_knots():
    """Per-round wind carries a knots conversion for the plot annotation."""
    w = data.wind_for_round(17)
    assert w["speed_kn"] == pytest.approx(w["speed_kmh"] / 1.852, rel=1e-6)


# --- charts -----------------------------------------------------------------
def test_energy_management_two_panels_both_pilots():
    """Energy Management renders altitude + speed panels for both pilots on one
    shared x-axis, single title, no per-panel titles (RPT-018)."""
    svg = charts.energy_management(data.load_round(6))
    assert "Altitude (m)" in svg and "Ground speed (km/h)" in svg
    # exactly one visible figure title, no per-panel titles
    assert svg.count(">Energy Management</text>") == 1
    # both series drawn on both panels => at least 4 polylines
    assert svg.count("<polyline") >= 4


def test_ground_track_has_course_wind_and_orientation_marks():
    """The RPT-011/012 ground track draws the bold course polygon, a wind vector
    with a knots label, a North arrow and a 100 m scale bar."""
    svg = charts.ground_track(data.load_round(17))
    assert "<polygon" in svg          # course triangle
    assert "WIND" in svg and "kn" in svg
    assert ">N</text>" in svg
    assert "100 m" in svg


def test_ground_track_legacy_signature_still_works():
    """The legacy track-list ground_track call remains supported (pages depend
    on it until Stage 2 migrates)."""
    r = data.load_round(17)
    svg = charts.ground_track(r["bill"]["track"], r["leader"]["track"], r["task"])
    assert svg.startswith("<svg")


def test_grouped_bar_rounds_three_series():
    """Grouped bars render three series across all rounds (RPT-022)."""
    rounds = list(range(1, 18))
    svg = charts.grouped_bar_rounds(
        rounds,
        [("Round winner", [1] * 17, "leader"),
         ("Event winner", [2] * 17, "field"),
         ("Bill", [3] * 17, "bill")],
        title="Score", ylabel="pts",
    )
    assert svg.count("<rect") >= 17 * 3  # a bar per series per round


def test_conditions_and_rank_strips_render():
    """Conditions strip and rank strip return SVGs for per-round arrays."""
    assert charts.conditions_strip([100, 200, 300]).startswith("<svg")
    assert charts.rank_strip([2, 1, 5], group_sizes=[9, 9, 10]).startswith("<svg")


# --- dashboard --------------------------------------------------------------
def test_dashboard_grid_and_colour_key():
    """The per-round dashboard is a 2x4 grid (8 cells) with the top-right
    colour-key legend naming Bill, the round leader and the regs limit."""
    frag = dashboard.dashboard(data.load_round(17))
    assert frag.count("dash-cell") == 8
    assert "Bill Maisey" in frag
    assert "Round Leader" in frag
    assert "Regs limit / Other pilots" in frag


def test_dashboard_speedrun_labels_single_lap():
    """A speed round labels the speed cell 'Single-lap speed'."""
    frag = dashboard.dashboard(data.load_round(4))
    assert "Single-lap speed" in frag


# --- components / design ----------------------------------------------------
def test_title_retitled():
    """TITLE_TEXT is the World Masters title (RPT-017)."""
    assert C.TITLE_TEXT == "GPS Triangle World Masters, Oschatz 2026"


def test_collapsible_label_is_dynamic():
    """The collapsible control reads 'Expand' when collapsed and 'Collapse' when
    expanded; no static 'toggle' label remains (RPT-014)."""
    collapsed = C.collapsible("s1", "H", "body", collapsed=True)
    expanded = C.collapsible("s2", "H", "body", collapsed=False)
    assert ">Expand<" in collapsed
    assert ">Collapse<" in expanded
    assert ">toggle<" not in collapsed and ">toggle<" not in expanded


def test_legality_consideration_is_inline_bold_not_heading():
    """The legality helper renders bold inline body text, not a heading
    element, and uses the new wording (RPT-015)."""
    frag = C.legality_consideration("navigator telemetry is CD discretion.")
    assert "Legality Consideration" in frag
    assert "<strong" in frag
    assert "<h" not in frag
    assert "Legality gate" not in frag


def test_fonts_inlined_no_remote_link():
    """Fonts are embedded as base64 woff2 @font-face and there is no remote font
    link (RPT-019)."""
    face = design.font_face_css()
    assert face.count("@font-face") == 8
    assert "data:font/woff2;base64," in face
    html = assemble.build_html()
    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html
    assert "data:font/woff2;base64," in html
