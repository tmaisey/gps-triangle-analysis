"""Analysis - per-round views (Stage 2 content).

Emits one view per round (1-17), each selectable from the Analysis dropdown.
A single :func:`render_round` builds every view; it branches on ``task_type``
so the 14 endurance (triangle) rounds and the 3 one-lap speed sprints (heats
4, 10, 16) each get figures suited to their task. Every figure is captioned
and every claim is backed by an on-page chart plus the linked event results.

Anchor / id scheme, per round N (kept stable from the Stage 1 scaffold so the
summary bullets and dropdown keep working):
    view-round-N        the view container (Analysis dropdown selects this)
    rN-top              summary / back-to-top target
    rN-energy           altitude / energy trace
    rN-track            ground-track overlay
    rN-laps             cumulative laps (triangle) / single-lap speed (sprint)
    rN-loss             biggest-loss segment
    rN-metrics          per-round metrics strip (incl. weather)
    rN-reco             round's inline recommendation
"""

from __future__ import annotations

from .. import charts, components as C
from ..data import TRACK_ALT, TRACK_T

# The public results page for the whole event (same-air benchmark source).
EVENT_URL = (
    "https://www.rcmodelspot.com/Ranking/f772fc7c-c4c5-406d-9c21-f4e76044ddb7"
)

# Rounds with a stand-out story (central framing from the analysis).
_NEAR_WINS = {7, 17}   # matched the leader lap-for-lap
_WORST = 12            # dropped to 2 laps on a mid-flight thermal-connection loss


# --- Small formatting / stat helpers ---------------------------------------
def _mmss(seconds: float | None) -> str:
    """Format a second offset as ``m:ss`` (blank on ``None``)."""
    if seconds is None:
        return ""
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def _xref(anchor: str, text: str) -> str:
    """Return a cross-page link into the Recommendations page."""
    return (
        f'<a class="xref" data-page="recommendations" '
        f'data-anchor="{anchor}">{C.esc(text)}</a>'
    )


def _event_link(text: str = "event results") -> str:
    """Return an external link to the public event results page."""
    return (
        f'<a href="{EVENT_URL}" target="_blank" rel="noopener">'
        f"{C.esc(text)}</a>"
    )


def _alt_stats(track: list) -> dict:
    """Return simple altitude statistics from a track (for grounding PEE).

    Args:
        track: list of track rows ``[t, lat, lon, alt, vario, gs]``.

    Returns:
        dict with ``entry`` (first alt), ``peak``, ``low`` and ``total_climb``
        (summed positive altitude deltas, m). Empty dict on an empty track.
    """
    alts = [row[TRACK_ALT] for row in track] if track else []
    if not alts:
        return {}
    total_climb = sum(max(0.0, alts[i] - alts[i - 1]) for i in range(1, len(alts)))
    return {
        "entry": alts[0],
        "peak": max(alts),
        "low": min(alts),
        "total_climb": total_climb,
    }


def _weather_for(ctx: dict, n: int) -> dict:
    """Return the weather row for round ``n`` (keyed ``R01``..``R17``)."""
    key = f"R{n:02d}"
    for row in ctx.get("weather", []):
        if row.get("round") == key:
            return row
    return {}


def _dominant_lever(r: dict) -> str:
    """Classify the round's dominant improvement lever.

    Returns one of ``'speed'`` (sprint top-end), ``'climb'`` (weak-lift /
    thermalling low) or ``'cruise'`` (slow lap / weak glide line), read from
    the task type, lap count and the biggest-loss note.
    """
    if r["task_type"] == "speedrun":
        return "speed"
    note = (r["biggest_loss"].get("note") or "").lower()
    if r["bill"]["laps"] <= 4:
        return "climb"  # weak-lift day: he lands early when he cannot connect
    if "thermalling low" in note or "sinking" in note or "searching" in note:
        return "climb"
    return "cruise"


# --- Triangle (endurance) round ---------------------------------------------
def _triangle_sections(r: dict, ctx: dict, n: int, top: str) -> list[tuple]:
    """Build the six (suffix, heading, body, collapsed) sections for a
    distance round."""
    b, l = r["bill"], r["leader"]
    task, loss = r["task"], r["biggest_loss"]
    wt_s = task["working_time_min"] * 60
    lap_gap = l["laps"] - b["laps"]
    bs, ls = _alt_stats(b["track"]), _alt_stats(l["track"])

    # -- energy / altitude trace --
    energy_fig = C.figure(
        charts.altitude_trace(
            b["track"], l["track"],
            bill_laps_s=b["lap_offsets_s"], leader_laps_s=l["lap_offsets_s"],
            title=f"Round {n} altitude vs time - Bill and same-air leader",
        ),
        f"Altitude over the 30-minute task for Bill (green) and same-air "
        f"leader {C.esc(l['name'])} (teal); dots mark lap crossings. Both "
        f"start near the 400 m cap and glide the budget down, topping up on "
        f"thermals. Source: {_event_link()}.",
        fig_id=f"r{n}-fig-energy",
    )
    if lap_gap <= 0:
        energy_pee = (
            f"<p><strong>Point.</strong> Bill matched {C.esc(l['name'])} "
            f"lap-for-lap ({b['laps']} each), so the energy budget held up all "
            f"the way to time. <strong>Evidence.</strong> The two traces track "
            f"together, with lap dots falling at nearly the same moments and "
            f"Bill banking {bs.get('total_climb', 0):.0f} m of climb against "
            f"the leader's {ls.get('total_climb', 0):.0f} m. "
            f"<strong>Explain.</strong> When his climbs keep pace, the "
            f"lap-count gap closes to nothing - the ceiling is here.</p>"
        )
    else:
        energy_pee = (
            f"<p><strong>Point.</strong> Bill and the leader enter within a "
            f"few metres of the cap ({b['entry_alt_m']:.0f} m vs "
            f"{l['entry_alt_m']:.0f} m), yet he ends {lap_gap} lap(s) short. "
            f"<strong>Evidence.</strong> Across the flight he recovers "
            f"{bs.get('total_climb', 0):.0f} m of height against the leader's "
            f"{ls.get('total_climb', 0):.0f} m, from a floor of "
            f"{bs.get('low', 0):.0f} m. <strong>Explain.</strong> Similar "
            f"entry energy but less height banked per thermal means the glide "
            f"budget drains sooner, so the lap count trails.</p>"
        )

    # -- ground track --
    track_fig = C.figure(
        charts.ground_track(
            b["track"], l["track"], task,
            title=f"Round {n} ground track - Bill and leader over the course",
        ),
        f"Ground track: the dashed triangle is the {task['leg_length_m']} m "
        f"course; green is Bill, teal the leader. Loops off the course line "
        f"are thermalling circles - where each pilot stopped to climb.",
        fig_id=f"r{n}-fig-track",
    )
    track_pee = (
        f"<p><strong>Point.</strong> The lines show where Bill left the course "
        f"to search for lift and how tightly he cornered. "
        f"<strong>Evidence.</strong> His thermalling loops sit off the course "
        f"line; his turnpoint arcs run slightly wider than the leader's. "
        f"<strong>Explain.</strong> Turnpoint technique is close to a strength "
        f"(about 2 s/lap); the loops, not the corners, are where the time "
        f"goes - wider, slower circles bank less height.</p>"
    )

    # -- cumulative laps --
    laps_fig = C.figure(
        charts.cumulative_laps(
            b["lap_offsets_s"], l["lap_offsets_s"], working_time_s=wt_s,
            title=f"Round {n} cumulative laps - Bill vs leader",
        ),
        f"Laps completed over the task. Bill finished {b['laps']} to the "
        f"leader's {l['laps']}; the vertical gap between the steps is the "
        f"lead opening up. Source: {_event_link()}.",
        fig_id=f"r{n}-fig-laps",
    )
    laps_pee = (
        f"<p><strong>Point.</strong> The gap opens gradually, not in one "
        f"blow-up. <strong>Evidence.</strong> The leader's step line pulls "
        f"steadily clear, reaching {l['laps']} laps at "
        f"{l['speed_kmh']:.1f} km/h while Bill holds {b['speed_kmh']:.1f} km/h "
        f"for {b['laps']}. <strong>Explain.</strong> A slower average lap - "
        f"mostly slower cruise between thermals - compounds over 30 minutes "
        f"into the {lap_gap}-lap shortfall.</p>"
    )

    # -- biggest-loss segment --
    dur = int(round(loss["end_s"] - loss["start_s"]))
    loss_body = (
        f"<p><strong>Single biggest-loss window: "
        f"{_mmss(loss['start_s'])}-{_mmss(loss['end_s'])}</strong> "
        f"({dur} s). {C.esc(loss['note'])}</p>"
        f"<p>This is the steepest part of the divergence on the cumulative-laps "
        f"and altitude charts above: one weak segment where the leader banked a "
        f"clean lap and Bill did not. Recovering even half of these windows "
        f"across the week is worth roughly a lap a round. Source: "
        f"{_event_link()}.</p>"
    )

    # -- metrics + weather --
    metrics_body = _metrics_row(r, ctx, n, sprint=False)

    # -- recommendation --
    reco_body = _reco(r, n)

    return [
        ("energy", "Energy / altitude trace", energy_fig + energy_pee, False),
        ("track", "Ground-track overlay", track_fig + track_pee, False),
        ("laps", "Cumulative laps vs leader", laps_fig + laps_pee, True),
        ("loss", "Biggest-loss segment", loss_body, True),
        ("metrics", "Round metrics and weather", metrics_body, True),
        ("reco", "What to train from this round", reco_body, True),
    ]


# --- Speed-sprint round ------------------------------------------------------
def _sprint_sections(r: dict, ctx: dict, n: int, top: str) -> list[tuple]:
    """Build the sections for a one-lap speed sprint (heats 4, 10, 16).

    The sprint is a separate task over the whole 38-pilot field with no
    landing score, so it gets speed-focused, lighter content rather than the
    triangle endurance visuals.
    """
    b, l = r["bill"], r["leader"]
    task = r["task"]
    pct_slower = (l["speed_kmh"] - b["speed_kmh"]) / l["speed_kmh"] * 100

    # -- altitude of the single run --
    energy_fig = C.figure(
        charts.altitude_trace(
            b["track"], l["track"],
            bill_laps_s=b["lap_offsets_s"], leader_laps_s=l["lap_offsets_s"],
            title=f"Round {n} speed run - altitude, Bill and fastest pilot",
        ),
        f"Speed task: altitude through the single flat-out lap for Bill "
        f"(green) and the run leader {C.esc(l['name'])} (teal). Both trade "
        f"height for speed; the dot marks the finish crossing. Source: "
        f"{_event_link()}.",
        fig_id=f"r{n}-fig-energy",
    )
    energy_note = (
        f"<p>This is the <strong>speed sprint</strong>, run in heats 4, 10 and "
        f"16 - a separate one-lap dash scored across all 38 pilots, with no "
        f"landing points. It is judged on top-end pace, not endurance, so it "
        f"reads differently from the distance rounds.</p>"
    )

    # -- ground track of the single lap --
    track_fig = C.figure(
        charts.ground_track(
            b["track"], l["track"], task,
            title=f"Round {n} speed run - single-lap ground track",
        ),
        f"The single {task['leg_length_m']} m-leg lap flown flat out; green is "
        f"Bill, teal the run leader. The lines stay tight to the course - "
        f"there is no thermalling on the sprint.",
        fig_id=f"r{n}-fig-track",
    )

    # -- speed comparison (repurposed 'laps' section) --
    speed_fig = C.figure(
        charts.bullet_bar(
            b["speed_kmh"], l["speed_kmh"],
            title=f"Round {n} single-lap speed - Bill vs run leader",
            label="Lap speed", unit=" km/h",
        ),
        f"Single-lap speed: Bill's green bar against the run leader's marker "
        f"({l['speed_kmh']:.1f} km/h). Field leaders sit around 150-156 km/h "
        f"all three sprints.",
        fig_id=f"r{n}-fig-laps",
    )
    speed_pee = (
        f"<p><strong>Point.</strong> On the sprint Bill gives up the most "
        f"ground of any task. <strong>Evidence.</strong> He clocked "
        f"{b['speed_kmh']:.1f} km/h against {C.esc(l['name'])}'s "
        f"{l['speed_kmh']:.1f} km/h - about {pct_slower:.0f}% slower - for "
        f"{b['score']} points and {b['rank']}th of {r['group_size']}. "
        f"<strong>Explain.</strong> Pure top-end speed and a clean high-energy "
        f"entry drive this task; it is a separable weakness from the distance "
        f"rounds but points at the same cruise-speed lever.</p>"
    )

    # -- loss note (sprint window is not a usable time range) --
    loss_body = (
        f"<p>{C.esc(r['biggest_loss'].get('note', ''))} The whole gap is the "
        f"single run - there is no in-flight segment to isolate, so the "
        f"speed bar above carries the story. Source: {_event_link()}.</p>"
    )

    metrics_body = _metrics_row(r, ctx, n, sprint=True)
    reco_body = _reco(r, n)

    return [
        ("energy", "Speed-run altitude", energy_fig + energy_note, False),
        ("track", "Single-lap ground track", track_fig, False),
        ("laps", "Single-lap speed vs leader", speed_fig + speed_pee, True),
        ("loss", "Where the time went", loss_body, True),
        ("metrics", "Round metrics and weather", metrics_body, True),
        ("reco", "What to train from this round", reco_body, True),
    ]


# --- Shared section builders -------------------------------------------------
def _metrics_row(r: dict, ctx: dict, n: int, *, sprint: bool) -> str:
    """Return the KPI tile row (result + entry-vs-cap + weather) for a round."""
    b, l = r["bill"], r["leader"]
    wx = _weather_for(ctx, n)
    wind = wx.get("wind_speed_kmh")
    solar = wx.get("shortwave_radiation")
    tiles = [
        C.stat_tile(str(b["laps"]), "Laps", f"leader {l['laps']}"),
        C.stat_tile(f"{b['speed_kmh']:.1f}", "Avg speed (km/h)",
                    f"leader {l['speed_kmh']:.1f}"),
        C.stat_tile(f"{b['rank']}/{r['group_size']}", "Within-group rank",
                    "same-air field" if sprint else "same-air heat"),
        C.stat_tile(f"{b['entry_alt_m']:.0f} m", "Entry altitude",
                    "cap 400 m"),
        C.stat_tile(f"{b['entry_speed_kmh']:.0f}", "Entry speed (km/h)",
                    "cap 120 km/h"),
        C.stat_tile(str(b["score"]), "Normalised score", "leader 1000"),
    ]
    if wind is not None:
        tiles.append(C.stat_tile(f"{wind:.1f}", "Wind (km/h)", "at start hour"))
    if solar is not None:
        tiles.append(C.stat_tile(f"{solar:.0f}", "Solar radiation",
                                 "W/m2 - lift proxy"))
    intro = (
        "<p>Result, entry conditions against the Sport-class caps, and the "
        "weather at the flight window. Entry altitude is already at the cap; "
        "the entry-speed tile shows the margin left unused.</p>"
    )
    return intro + C.kpi_row(tiles)


def _reco(r: dict, n: int) -> str:
    """Return the round's 1-2 sentence takeaway, tied to its dominant lever."""
    lever = _dominant_lever(r)
    b, l = r["bill"], r["leader"]
    if n in _NEAR_WINS:
        return (
            f"<p>Round {n} is a near-win: Bill matched {C.esc(l['name'])} "
            f"lap-for-lap for {b['score']} points, with clean turns and a "
            f"clean landing. Holding {_xref('rec-cruise', 'cruise speed')} and "
            f"{_xref('rec-climb', 'climb height')} at this level across weaker "
            f"days is what turns a strong round into a podium.</p>"
        )
    if n == _WORST:
        return (
            f"<p>Round {n} was the worst of the week - {b['laps']} laps and "
            f"dropped - from a mid-flight thermal that would not connect, not "
            f"from the conditions. The lever is "
            f"{_xref('rec-climb', 'climb quality and searching for lift')}: a "
            f"more decisive re-centre would have saved the flight.</p>"
        )
    if lever == "speed":
        return (
            f"<p>The sprint reward is raw pace and a full-energy start. Train "
            f"{_xref('rec-cruise', 'top-end cruise speed')} and use more of the "
            f"{_xref('rec-entry', 'entry-speed allowance')} - Bill leaves a "
            f"large slice of the 120 km/h cap unused.</p>"
        )
    if lever == "climb":
        climb_link = _xref(
            "rec-climb",
            "climb quality - banking more height per thermal with tighter "
            "circles",
        )
        return (
            f"<p>This was a weak-lift round where Bill faded: the lever is "
            f"{climb_link}. On scarce-lift days that is what keeps him aloft "
            f"for the extra laps.</p>"
        )
    cruise_link = _xref("rec-cruise", "faster inter-thermal cruise")
    entry_link = _xref("rec-entry", "entry speed")
    return (
        f"<p>The gap here is cruise pace between thermals - the biggest lever "
        f"overall. Focus on {cruise_link}, with free opening-lap energy "
        f"available from a fuller {entry_link}.</p>"
    )


# --- View + render -----------------------------------------------------------
def render_round(entry: dict, ctx: dict) -> str:
    """Render one round's full view (summary + figures + metrics + reco).

    Args:
        entry: the round's index entry (carries ``round``/``task_type``/...).
        ctx: shared build context (rounds, weather, round_labels).

    Returns:
        str: a ``<div class="view" id="view-round-N">`` fragment.
    """
    n = entry["round"]
    top = f"r{n}-top"
    r = ctx["rounds"][n - 1]
    label = ctx["round_labels"].get(n, f"Round {n}")
    b, l = r["bill"], r["leader"]

    if r["task_type"] == "speedrun":
        sections = _sprint_sections(r, ctx, n, top)
        intro = (
            f"Round {n} ({C.esc(label)}) is the <strong>speed sprint</strong> - "
            f"a one-lap flat-out task scored across all 38 pilots, distinct "
            f"from the endurance rounds. Bill ran {b['speed_kmh']:.1f} km/h to "
            f"the run leader {C.esc(l['name'])}'s {l['speed_kmh']:.1f} km/h, "
            f"placing {b['rank']}th for {b['score']} points. Full field on the "
            f"{_event_link()}."
        )
    else:
        sections = _triangle_sections(r, ctx, n, top)
        lap_gap = l["laps"] - b["laps"]
        if n in _NEAR_WINS:
            verdict = (f"matched {C.esc(l['name'])} lap-for-lap "
                       f"({b['laps']} each) for {b['score']} points - a "
                       f"near-win and one of his best rounds")
        elif n == _WORST:
            verdict = (f"managed only {b['laps']} laps and dropped - his worst "
                       f"round, a thermal that would not connect rather than "
                       f"the conditions")
        else:
            verdict = (f"completed {b['laps']} laps to the same-air leader "
                       f"{C.esc(l['name'])}'s {l['laps']} ({lap_gap} short), "
                       f"scoring {b['score']} of a possible 1000")
        intro = (
            f"Round {n} ({C.esc(label)}, {C.esc(r['heat'])}) is a distance "
            f"task. Bill {verdict}. The benchmark is the top scorer in his own "
            f"heat - same time slot, same air. Full standings on the "
            f"{_event_link()}."
        )

    bullets = [(f"r{n}-{suf}", heading) for suf, heading, _b, _c in sections]
    summary = C.summary(intro, bullets, top_id=top)
    section_html = "".join(
        C.collapsible(f"r{n}-{suf}", heading, body, top_id=top,
                      collapsed=collapsed)
        for suf, heading, body, collapsed in sections
    )
    inner = (
        f"<h2>Round {n} - {C.esc(label)}</h2>"
        + summary + C.expand_collapse_controls() + section_html
    )
    return f'<div class="view" id="view-round-{n}">{inner}</div>'


def render(ctx: dict) -> str:
    """Render all 17 per-round view fragments, concatenated.

    Args:
        ctx: shared build context (uses ``index``, ``rounds``, ``weather``,
            ``round_labels``).

    Returns:
        str: 17 ``<div class="view" id="view-round-N">`` fragments.
    """
    return "".join(render_round(entry, ctx) for entry in ctx["index"])
