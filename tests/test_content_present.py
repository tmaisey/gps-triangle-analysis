"""Content-presence tests (RPT-003/004/009 + DSN-001 figure captioning).

These assert that the four pages carry real content and that the Analysis
Overview and each of the 17 rounds render at least one chart. Against the
Stage 1 STUBS these will LARGELY FAIL by design (the intended red) - Stage 2
and Stage 3 turn them green as page content and per-round figures land.

The figure-caption invariant is expected to hold at every stage.
"""

from __future__ import annotations

import re

import pytest
from bs4 import BeautifulSoup

from scripts.build import assemble, data

SPEED_ROUNDS = (4, 10, 16)
DISTANCE_ROUNDS = [n for n in range(1, 18) if n not in SPEED_ROUNDS]


@pytest.fixture(scope="module")
def soup():
    """Parsed generated document."""
    return BeautifulSoup(assemble.build_html(), "html.parser")


@pytest.mark.parametrize("page_id", ["home", "analysis", "recommendations",
                                     "innovations"])
def test_page_has_real_content_no_stubs(soup, page_id):
    """Each page has substantive content and no remaining [STUB] markers."""
    page = soup.select_one(f"#page-{page_id}")
    assert page is not None
    text = page.get_text(" ", strip=True)
    assert "[STUB]" not in text, f"{page_id} still contains stubs"
    assert len(text) > 400, f"{page_id} content too thin"


def test_overview_renders_a_chart(soup):
    """The Analysis Overview view renders at least one inline-SVG chart."""
    view = soup.select_one("#view-overview")
    assert view is not None
    assert view.find("svg") is not None


@pytest.mark.parametrize("n", list(range(1, 18)))
def test_each_round_renders_a_chart(soup, n):
    """Each of the 17 per-round views renders at least one inline-SVG chart."""
    view = soup.select_one(f"#view-round-{n}")
    assert view is not None, f"round {n} view missing"
    assert view.find("svg") is not None, f"round {n} has no chart"


@pytest.mark.parametrize("n", list(range(1, 18)))
def test_each_round_has_dashboard_energy_and_track(soup, n):
    """Each round view opens with the RPT-021 dashboard (2x4 grid + colour key)
    and carries an Energy Management figure and a ground-track figure."""
    view = soup.select_one(f"#view-round-{n}")
    assert view is not None, f"round {n} view missing"
    # Dashboard: the 8-cell grid plus its colour key legend (RPT-021).
    assert len(view.select(".dash-cell")) == 8, f"round {n} dashboard not 2x4"
    assert view.select_one(".dash-key") is not None, f"round {n} has no colour key"
    # Energy Management dual-panel figure and ground-track figure (RPT-018/011).
    assert view.select_one(f"#r{n}-fig-energy") is not None, f"round {n} no energy fig"
    assert view.select_one(f"#r{n}-fig-track") is not None, f"round {n} no track fig"


def test_overview_four_thematic_sections_with_trajectory_figures(soup):
    """The Overview is organised into the four Title-Case thematic sections in
    order (Headline Result / Scoring, Laps & Speed / Start Energy / Conditions,
    Trajectory & Climbing), led by an 'Overall Read' paragraph above the first
    section, and carries the three new trajectory figures with captions
    (RPT-022/023/024)."""
    view = soup.select_one("#view-overview")
    assert view is not None
    # The four thematic sections exist and appear in this exact DOM order.
    section_ids = [s.get("id") for s in view.select(".section")]
    assert section_ids == ["ov-headline", "ov-scoring",
                           "ov-start-energy", "ov-conditions"], section_ids
    # The 'Overall Read' lead paragraph precedes the first section (ov-headline).
    lead = view.find(lambda t: t.name == "p"
                     and "pee-point" in (t.get("class") or [])
                     and "Overall Read" in t.get_text())
    assert lead is not None, "no 'Overall Read' lead paragraph"
    headline = view.select_one("#ov-headline")
    assert headline is not None
    ordered = view.find_all(True)
    assert ordered.index(lead) < ordered.index(headline), \
        "'Overall Read' must appear before the first section"
    # The three new Overview trajectory figures are present, are <figure>s, and
    # each carries a non-empty caption.
    for fid in ("ov-fig-trajectory", "ov-fig-turn-radius", "ov-fig-r12-track"):
        fig = view.select_one(f"#{fid}")
        assert fig is not None, f"missing {fid}"
        assert fig.name == "figure", f"{fid} is not a <figure>"
        cap = fig.find("figcaption")
        assert cap is not None and cap.get_text(strip=True), \
            f"{fid} has no non-empty caption"


def test_analysis_is_insight_first_no_pee_labels(soup):
    """Analysis pages are insight-first (RPT-003/004, updated): no literal
    'Point.'/'Evidence.'/'Explain.' bold labels; the Overview keeps a
    'What to do.' recommendation cue, and every per-round view carries
    substantive, quantitative prose."""
    ov = soup.select_one("#view-overview").get_text(" ", strip=True)
    assert "Point." not in ov and "Evidence." not in ov and "Explain." not in ov
    assert "What to do." in ov  # recommendation cue kept
    for n in range(1, 18):
        txt = soup.select_one(f"#view-round-{n}").get_text(" ", strip=True)
        assert "Point." not in txt and "Evidence." not in txt, f"round {n} has a PEE label"
        assert "km/h" in txt and len(txt) > 400, f"round {n} prose thin/unquantified"


def test_every_figure_has_a_nonempty_caption(soup):
    """Every <figure> anywhere in the report has a non-empty <figcaption>."""
    figures = soup.find_all("figure")
    assert figures, "no figures rendered at all"
    for fig in figures:
        cap = fig.find("figcaption")
        assert cap is not None and cap.get_text(strip=True)


# --- Home (RPT-009) ---------------------------------------------------------
def test_home_summary_and_exactly_three_linked_section_headings(soup):
    """Home carries a summary paragraph and exactly three linked headings.

    RPT-009 calls for "the three sections listed as linked headings", so the
    links are asserted to sit inside heading elements (a document outline for
    screen readers), and Home is asserted to stay minimal (no collapsibles).
    """
    home = soup.select_one("#page-home")
    assert home is not None
    assert home.find("p") and "Bill Maisey" in home.get_text()
    xrefs = home.select("a.xref")
    assert [(a["data-page"], a.get_text(strip=True)) for a in xrefs] == [
        ("analysis", "Performance Analysis"),
        ("recommendations", "Recommendations"),
        ("innovations", "Innovations"),
    ]
    for a in xrefs:
        assert a.find_parent(["h2", "h3"]) is not None, \
            f"{a.get_text(strip=True)} is not a linked heading"
    assert not home.select(".section"), "Home should stay minimal"


# --- Start Energy airframe note (RPT-025) -----------------------------------
def test_start_energy_names_the_top_airframe_families(soup):
    """The airframe note names the four top-field families and the framing.

    RPT-025 requires the note to show the mix (Pike Paradigm, Phantom,
    SkyTouch, Apollo), not merely assert one, and to ground it.
    """
    section = soup.select_one("#ov-start-energy")
    assert section is not None
    txt = section.get_text(" ", strip=True)
    for family in ("Pike Paradigm", "Phantom", "SkyTouch", "Apollo"):
        assert family in txt, f"airframe note never names {family}"
    assert "technique" in txt and "not an equipment" in txt
    hrefs = {a.get("href", "") for a in section.select("a[href^=http]")}
    assert any("rcmodelspot" in h for h in hrefs), \
        "airframe/equipment claim carries no event-data source link"


# --- Per-round summary bullets (RPT-007) ------------------------------------
@pytest.mark.parametrize("n", list(range(1, 18)))
def test_round_summary_bullets_are_key_points_not_section_titles(soup, n):
    """Each round summary bullet is a round-specific key point.

    RPT-007 asks for "~5 bullets of key points/recommendations"; a bullet that
    merely repeats its section heading is a table of contents. Anchors must
    still resolve to on-page section ids.
    """
    view = soup.select_one(f"#view-round-{n}")
    assert view is not None
    summ = view.select_one(".summary")
    assert summ is not None and summ.find("p").get_text(strip=True)
    ids = {e["id"] for e in view.select("[id]")}
    titles = {s.select_one("h2, h3").get_text(strip=True)
              for s in view.select(".section")}
    bullets = summ.select("li a")
    assert 3 <= len(bullets) <= 7, f"round {n} has {len(bullets)} bullets"
    for a in bullets:
        assert a["href"][1:] in ids, f"round {n}: dangling bullet {a['href']}"
        text = a.get_text(strip=True)
        assert text not in titles, \
            f"round {n}: bullet '{text}' is a section title, not a key point"
        assert len(text) > 18, f"round {n}: bullet too thin: {text}"
    assert len(view.select("a.back-to-top")) == len(view.select(".section"))
    assert len(view.select(".controls button")) == 2


# --- Recommendations (RPT-005) ----------------------------------------------
WEAKNESS_SECTIONS = ["rec-cruise", "rec-climb", "rec-entry", "rec-turns"]


@pytest.mark.parametrize("sid", WEAKNESS_SECTIONS)
def test_each_weakness_has_drill_further_analysis_and_backlink(soup, sid):
    """Every top-level weakness carries a drill, further analysis and evidence."""
    body = soup.select_one(f"#{sid} .section-body")
    assert body is not None, f"{sid} missing"
    labels = {s.get_text(strip=True).rstrip(".") for s in body.find_all("strong")}
    assert "Drills" in labels, (sid, labels)
    assert "Further Analysis" in labels, (sid, labels)
    assert body.select("a.xref[data-page=analysis]"), \
        f"{sid} has no Analysis back-link"


def test_every_recommendation_theme_links_back_to_analysis(soup):
    """Every themed recommendation, rec-signals included, cites its evidence."""
    for sec in soup.select("#page-recommendations .section"):
        assert sec.select("a.xref[data-page=analysis]"), \
            f"{sec.get('id')} has no back-link to Analysis evidence"


def test_every_rec_anchor_is_referenced_inline_from_analysis(soup):
    """The canonical recommendation set is surfaced inline in Analysis too."""
    rec_ids = {s["id"] for s in soup.select("#page-recommendations .section")}
    linked = {a["data-anchor"]
              for a in soup.select("#page-analysis a.xref[data-page=recommendations]")}
    assert rec_ids - {"rec-signals"} <= linked, rec_ids - linked


# --- Innovations cross-links (RPT-006) --------------------------------------
def test_analysis_links_out_to_innovations(soup):
    """Analysis cross-links into Innovations tiers (PRD section 8 requires both
    directions; the Recommendations -> Innovations direction already exists)."""
    anchors = [a["data-anchor"]
               for a in soup.select("#page-analysis a.xref[data-page=innovations]")]
    assert len(anchors) >= 2, f"only {len(anchors)} Analysis->Innovations links"
    tiers = {s["id"] for s in soup.select("#page-innovations .section")}
    assert set(anchors) <= tiers, set(anchors) - tiers


def test_innovations_tiers_each_carry_a_legality_consideration(soup):
    """Each of the four Innovations tiers states its legality consideration."""
    ids = [s["id"] for s in soup.select("#page-innovations .section")]
    assert ids == ["inn-postflight", "inn-navigator", "inn-live",
                   "inn-flywheel"], ids
    for sec in soup.select("#page-innovations .section"):
        assert sec.select_one("p.legality") is not None, sec.get("id")


# --- Overview insight structure (RPT-003 / RPT-022) -------------------------
def test_every_overview_insight_carries_evidence(soup):
    """Each Overview insight is backed by a figure, a number or a source link.

    RPT-003 step 2: "each Overview insight has an evidence figure/number and an
    explain/recommendation". Evidence is asserted per insight; the
    recommendation cue is asserted per thematic section.
    """
    view = soup.select_one("#view-overview")
    leads = view.select("p.pee-point")
    assert len(leads) >= 20, f"only {len(leads)} Overview insights"
    for lead in leads:
        title = lead.find("strong").get_text(strip=True)
        has_number = bool(re.search(r"\d", lead.get_text()))
        nxt = lead.find_next(["figure", "p"])
        has_figure = nxt is not None and nxt.name == "figure"
        has_link = bool(lead.select("a[href^=http]"))
        assert has_number or has_figure or has_link, \
            f"ungrounded Overview insight: {title}"
    for sec in view.select(".section"):
        assert "What to do." in sec.get_text(), \
            f"{sec.get('id')} carries no recommendation cue"


def test_overview_grouped_bar_figures_and_section_index(soup):
    """The five RPT-022 grouped-bar figures render and the index links all four
    thematic sections."""
    view = soup.select_one("#view-overview")
    for fid in ("ov-fig-sum-score", "ov-fig-sum-laps", "ov-fig-sum-speed",
                "ov-fig-sum-entryspd", "ov-fig-sum-entryalt"):
        fig = view.select_one(f"#{fid}")
        assert fig is not None and fig.name == "figure", f"missing {fid}"
    index_targets = {a["href"][1:] for a in view.select(".summary li a")}
    assert index_targets == {"ov-headline", "ov-scoring", "ov-start-energy",
                             "ov-conditions"}, index_targets


# --- Per-round section order (RPT-004) --------------------------------------
@pytest.mark.parametrize("n", DISTANCE_ROUNDS)
def test_round_sections_run_title_then_insight_then_visual(soup, n):
    """Distance rounds carry the three mandated titles, each Title -> text ->
    visual (RPT-004)."""
    view = soup.select_one(f"#view-round-{n}")
    titles = [s.select_one("h2, h3").get_text(strip=True)
              for s in view.select(".section")]
    for t in ("Energy Management", "Ground Track & Course",
              "Cumulative Laps vs Leader"):
        assert t in titles, (n, titles)
    for sec in view.select(".section"):
        body = sec.select_one(".section-body")
        fig = body.find("figure")
        if fig is None:
            continue
        els = body.find_all(True)
        prose = " ".join(e.get_text(" ", strip=True)
                         for e in els[:els.index(fig)] if e.name == "p")
        assert len(prose) > 150, (n, sec.get("id"), len(prose))


@pytest.mark.parametrize("n", SPEED_ROUNDS)
def test_speed_rounds_drop_the_cumulative_laps_figure(soup, n):
    """The sprint has one lap, so the cumulative-laps framing is not rendered.

    RPT-013: the two pilots fly sequential slots, so a shared lap-offset axis
    put them 15-52 minutes apart on an otherwise empty chart.
    """
    view = soup.select_one(f"#view-round-{n}")
    assert view.select_one(f"#r{n}-fig-laps") is None, \
        f"round {n} still renders the cumulative-laps figure"
    assert view.select_one(f"#r{n}-laps") is not None, \
        f"round {n} lost its single-lap section anchor"


# --- Captions and labels ----------------------------------------------------
#: Clockface side the wind glyph is drawn on, by source-bearing sector
#: (RPT-012). Mirrors the placement rule, so the caption is checked against the
#: geometry rather than against itself.
def _expected_wind_side(deg: float) -> str:
    """Return the plot side the wind glyph sits on for a source bearing."""
    deg %= 360.0
    for upper, name in [(22.5, "top"), (67.5, "top-right"), (112.5, "right"),
                        (157.5, "bottom-right"), (202.5, "bottom"),
                        (247.5, "bottom-left"), (292.5, "left"),
                        (337.5, "top-left")]:
        if deg < upper:
            return name
    return "top"


def test_ground_track_captions_describe_the_course_geometry(soup):
    """Ground-track captions state the ADR-008 geometry, not a "350 m leg".

    The .rct ``length`` is the turnpoint radius; the legs are radius*sqrt(2),
    the base is 2*radius and the lap is ~1690 m. The wind clause names the side
    the glyph is actually drawn on, which is the clockface position of that
    round's source bearing - not a fixed right margin.
    """
    html = str(soup)
    stale = [p for p in ("350 m-leg", "350 m leg") if p in html]
    assert not stale, f"captions still call the radius a leg: {stale}"
    geom = data.course_geometry(data.load_round(1)["task"])
    for n in list(range(1, 18)):
        cap = soup.select_one(f"#r{n}-fig-track figcaption").get_text(" ", strip=True)
        assert f"{geom['radius_m']:.0f} m turnpoint radius" in cap, (n, cap)
        assert f"{geom['leg_m']:.0f} m legs" in cap, (n, cap)
        assert f"{geom['perimeter_m']:.0f} m lap" in cap, (n, cap)
        side = _expected_wind_side(data.wind_for_round(n)["dir_deg"])
        assert f"wind vector in the {side} margin" in cap, (n, side, cap)


@pytest.mark.parametrize("n", DISTANCE_ROUNDS)
def test_elapsed_windows_are_labelled_as_elapsed_time(soup, n):
    """Loss windows read as elapsed flight time, not as a clock time."""
    txt = soup.select_one(f"#view-round-{n}").get_text(" ", strip=True)
    assert re.search(r"\d{1,2}:\d{2}–\d{1,2}:\d{2} into the flight", txt), \
        f"round {n} has no elapsed-labelled loss window"
    assert not re.search(r"\d{1,2}:\d{2}-\d{1,2}:\d{2}", txt), \
        f"round {n} still renders a bare mm:ss-mm:ss range"


@pytest.mark.parametrize("n", SPEED_ROUNDS)
def test_speed_round_rank_tile_is_field_scoped(soup, n):
    """The sprint is scored across the whole field, so the tile says so."""
    view = soup.select_one(f"#view-round-{n}")
    dash = view.select_one(".dash").get_text(" ", strip=True)
    assert "Within-group rank" not in dash, (n, dash[:200])
    assert "Field rank" in dash, (n, dash[:200])
    assert "pilots in group" not in dash


# --- Pooled-density reconciliation (RPT-023 / RPT-024) ----------------------
def test_trajectory_and_turn_radius_prose_reconcile_to_the_pooled_helpers(soup):
    """The Overview's density numbers match the pooled helpers exactly, and the
    turn-radius figure carries a median marker per pilot."""
    dfc = data.pooled_distance_from_course()
    txt = soup.select_one("#ov-fig-trajectory").find_previous(
        "p", class_="pee-point").get_text(" ", strip=True)
    assert f"{dfc['bill']['median']:.1f}" in txt
    assert f"{dfc['leader']['median']:.1f}" in txt
    edges = dfc["edges"]

    def tail_pct(role: str) -> float:
        return 100 * sum(f for e, f in zip(edges[:-1], dfc[role]["frac"])
                         if e >= 300)

    assert f"{tail_pct('leader'):.1f}%" in txt, txt
    assert f"{tail_pct('bill'):.1f}%" in txt, txt
    assert "bimodal" not in txt

    tr = data.pooled_turn_radius()
    tr_txt = soup.select_one("#ov-fig-turn-radius").find_previous(
        "p", class_="pee-point").get_text(" ", strip=True)
    assert f"{tr['bill']['median']:.1f}" in tr_txt
    assert f"{tr['leader']['median']:.1f}" in tr_txt
    svg = str(soup.select_one("#ov-fig-turn-radius svg"))
    assert svg.count("median") >= 2, "turn-radius figure lacks median markers"


def test_conditions_dependence_uses_distance_rounds_only(soup):
    """The conditions scatter plots the 14 distance rounds, not all 17.

    The three speed sprints score on a different task, so including them
    inflated the quoted correlation (rho 0.608 over 17 vs 0.543 over 14).
    """
    fig = soup.select_one("#ov-fig-conditions")
    assert fig is not None
    points = str(fig).count('<circle')
    assert points == 14, f"conditions scatter plots {points} rounds, expected 14"
    lead = fig.find_previous("p", class_="pee-point").get_text(" ", strip=True)
    assert "+0.5" in lead and "+0.6" not in lead, lead
