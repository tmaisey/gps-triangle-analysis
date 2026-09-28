"""Analysis - per-round views (Stage 2 content, v2 chart APIs).

Emits one view per round (1-17), each selectable from the Analysis dropdown.
A single :func:`render_round` builds every view. Every round opens (under the
summary) with the RPT-021 "Visual overview of performance" dashboard, then the
RPT-018 Energy Management dual-panel, the RPT-011 ground-track & course
overlay, cumulative laps vs the same-air leader, the biggest-loss segment and
the round's inline recommendation. The three speed sprints (heats 4, 10, 16)
run the same figures over their single flat-out lap; the dashboard auto-labels
single-lap speed and the lap/loss framing acknowledges the one-lap task.

Every figure is captioned (DSN-001), insights are written Point-Evidence-
Explain, and every claim is grounded by an on-page chart and/or the linked
event results (RPT-008).

Anchor / id scheme, per round N (kept stable so the summary bullets and
dropdown keep working):
    view-round-N        the view container (Analysis dropdown selects this)
    rN-top              summary / back-to-top target
    rN-dash             visual-overview dashboard (RPT-021)
    rN-energy           Energy Management dual-panel (RPT-018)
    rN-track            ground-track & course overlay (RPT-011)
    rN-laps             cumulative laps (triangle) / single-lap task (sprint)
    rN-loss             biggest-loss segment
    rN-reco             round's inline recommendation
"""

from __future__ import annotations

from .. import charts, components as C, dashboard
from ..data import TRACK_ALT, TRACK_T, course_geometry, wind_for_round
from ..links import EVENT_URL

# ``EVENT_URL`` is re-exported for callers that imported it from this module
# before the shared link bank existed.
__all__ = ["EVENT_URL", "render", "render_round"]

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


def _window(start_s: float | None, end_s: float | None) -> str:
    """Format an in-flight window as elapsed time, not as a clock reading.

    Offsets are measured from the scored start-line crossing, so a bare
    ``22:25-23:25`` in a round flown at 17:05 reads as a wall-clock range. The
    phrase is qualified and the range uses an en dash.

    Args:
        start_s: window start, seconds after the start-line crossing.
        end_s: window end, seconds after the start-line crossing.

    Returns:
        str: e.g. ``"22:25–23:25 into the flight"``.
    """
    return f"{_mmss(start_s)}–{_mmss(end_s)} into the flight"


#: 16-point compass sectors named as a plot position, for the ground-track
#: caption. Mirrors the clockface placement rule the chart itself uses
#: (RPT-012): the glyph sits on the ray from the plot centre toward the wind's
#: source bearing.
_WIND_SIDES = [
    (22.5, "top"), (67.5, "top-right"), (112.5, "right"),
    (157.5, "bottom-right"), (202.5, "bottom"), (247.5, "bottom-left"),
    (292.5, "left"), (337.5, "top-left"),
]


def _wind_clause(n: int) -> str:
    """Return the caption clause describing where this round's wind glyph sits.

    The glyph is placed at the clockface position of the source bearing, which
    is a different side of the plot in most rounds, so the clause is derived
    from the round's own wind rather than hard-coded.

    Args:
        n: round number (1-17).

    Returns:
        str: e.g. ``"wind vector in the left margin (W 272 degrees, the bearing
        it blows from)"``, or a generic clause when no wind row exists.
    """
    wind = wind_for_round(n) or {}
    deg = wind.get("dir_deg")
    if not isinstance(deg, (int, float)):
        return "wind vector in the margin on the side the wind blows from"
    deg = float(deg) % 360.0
    side = "top"
    for upper, name in _WIND_SIDES:
        if deg < upper:
            side = name
            break
    return (f"wind vector in the {side} margin - the clockface position of the "
            f"bearing it blows from ({int(round(deg)):03d}°), pointing "
            "inward")


def _ord(n: int) -> str:
    """Format an integer rank as an English ordinal (1 -> '1st', 2 -> '2nd')."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


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


def _energy_pattern(r: dict) -> dict | None:
    """Return Bill-vs-leader mean-altitude deltas for the two halves of a flight.

    Uses the same clipped full-resolution traces the Energy-Management chart
    plots (each ending at the pilot's last turn-point crossing, falling back to
    the embedded compact track if the replay is unavailable), and compares mean
    GPS altitude over the first and second half of the window in which *both*
    pilots are still flying - so the caller can describe *who held more energy
    when* (e.g. led early then faded) without an early landing skewing it.

    Args:
        r: the round dataset dict.

    Returns:
        dict with ``d1``/``d2`` (Bill-minus-leader mean altitude, m, over the
        first/second half of the shared window). ``None`` if unavailable.
    """
    n = r["round"]
    try:
        bt, lt = charts_data_full_tracks(n)
    except Exception:
        bt, lt = [], []
    if not bt:
        bt = r["bill"]["track"]
    if not lt:
        lt = r["leader"]["track"]
    if not bt or not lt:
        return None
    lo = max(bt[0][TRACK_T], lt[0][TRACK_T])
    hi = min(bt[-1][TRACK_T], lt[-1][TRACK_T])
    if hi <= lo:
        return None
    cut = (lo + hi) / 2

    def mean_alt(track: list, a: float, b: float) -> float | None:
        vals = [row[TRACK_ALT] for row in track if a <= row[TRACK_T] < b]
        return sum(vals) / len(vals) if vals else None

    bf, bs = mean_alt(bt, lo, cut), mean_alt(bt, cut, hi + 1)
    lf, ls = mean_alt(lt, lo, cut), mean_alt(lt, cut, hi + 1)
    if None in (bf, bs, lf, ls):
        return None
    return {"d1": bf - lf, "d2": bs - ls}


def charts_data_full_tracks(n: int) -> tuple[list, list]:
    """Return the round's clipped full-res (Bill, leader) tracks (chart source)."""
    from .. import data as D

    return D.full_tracks_for_round(n, clip_to_last_tpc=True)


def _laps_pattern(r: dict) -> dict:
    """Return where the lap deficit against the leader accumulated.

    Splits the combined lap-completion span at its midpoint and counts each
    pilot's laps in the first and second half, so the caller can say whether Bill
    kept pace then fell away, fell behind early, or bled the gap steadily.

    Args:
        r: the round dataset dict.

    Returns:
        dict with ``def1``/``def2`` (leader-minus-Bill laps in the first/second
        half) and ``gap`` (total lap deficit).
    """
    bo, lo = r["bill"]["lap_offsets_s"], r["leader"]["lap_offsets_s"]
    gap = len(lo) - len(bo)
    if not bo or not lo:
        return {"def1": 0, "def2": gap, "gap": gap}
    mid = (min(bo[0], lo[0]) + max(bo[-1], lo[-1])) / 2
    bf = sum(1 for t in bo if t <= mid)
    lf = sum(1 for t in lo if t <= mid)
    return {"def1": lf - bf, "def2": (len(lo) - lf) - (len(bo) - bf), "gap": gap}


def _metrics_for(n: int, ctx: dict) -> dict:
    """Return ``{'BILL': row, 'leader': row}`` from ``ctx['metrics']`` for round n.

    The metrics CSV keys rounds as bare integers (1-17), so both the integer and
    the ``R0N`` spellings are accepted defensively.
    """
    keys = {n, f"R{n:02d}", str(n)}
    out: dict = {}
    for row in ctx.get("metrics", []):
        if row.get("round") in keys and row.get("role") in ("BILL", "leader"):
            out[row["role"]] = row
    return out


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


# --- Section builders --------------------------------------------------------
def _round_conditions(n: int, ctx: dict) -> dict:
    """Return this round's lift/wind context from the shared weather data.

    Reads ``ctx['weather']`` (per-flight rows) and normalises the round's
    shortwave radiation across all 17 rounds into a lift band ('strong' /
    'moderate' / 'weak'), flagging the event extremes.

    Args:
        n: round number (1-17).
        ctx: the shared build context (uses ``ctx['weather']``).

    Returns:
        dict with ``band`` (str), ``extreme`` (a trailing clause or ``''``) and
        ``wind`` (km/h float or ``None``).
    """
    weather = {row.get("round"): row for row in ctx.get("weather", [])}
    row = weather.get(f"R{n:02d}", {})
    rad = row.get("shortwave_radiation")
    wind = row.get("wind_speed_kmh")
    rads = [
        w["shortwave_radiation"]
        for w in weather.values()
        if isinstance(w.get("shortwave_radiation"), (int, float))
    ]
    band, extreme = "moderate", ""
    if rads and isinstance(rad, (int, float)):
        lo, hi = min(rads), max(rads)
        norm = (rad - lo) / ((hi - lo) or 1)
        band = "strong" if norm >= 0.66 else "weak" if norm < 0.33 else "moderate"
        if rad == hi:
            extreme = " - the strongest lift window of all 17 rounds"
        elif rad == lo:
            extreme = " - the weakest lift window of all 17 rounds"
    return {"band": band, "extreme": extreme, "wind": wind}


def _dash_insights(r: dict, n: int, ctx: dict) -> str:
    """Return 3-5 sentences of round-specific key insights (the dashboard lead).

    Generated from the round's own numbers rather than a template: laps vs the
    same-air leader, whether the gap was cruise pace or staying aloft (from the
    speed delta), the entry-speed energy left against the 120 km/h cap, the lift
    band + wind, and where the biggest single loss fell. Near-wins read as
    toe-to-toe, the bombout as a thermal-connection failure, and the three
    sprints as the isolated one-lap dash.

    Args:
        r: the round dataset dict (bill/leader/biggest_loss/task).
        n: round number (1-17).
        ctx: shared build context (for ``ctx['weather']``).

    Returns:
        str: an HTML ``<p>`` of key insights, grounded in the {event_link}.
    """
    b, l = r["bill"], r["leader"]
    lead = C.esc(l.get("name", "the leader"))
    is_speed = r["task_type"] == "speedrun"
    cond = _round_conditions(n, ctx)
    band, extreme, wind = cond["band"], cond["extreme"], cond["wind"]
    wind_txt = (f"{wind:.0f} km/h wind"
                if isinstance(wind, (int, float)) else "the day's wind")
    loss = r["biggest_loss"]
    note = C.esc((loss.get("note") or "").strip())
    gate_gap = l["entry_speed_kmh"] - b["entry_speed_kmh"]
    s: list[str] = []

    if is_speed:
        delta = l["speed_kmh"] - b["speed_kmh"]
        alt_below, lead_below = 400 - b["entry_alt_m"], 400 - l["entry_alt_m"]
        s.append(
            f"Round {n} is the one-lap speed dash - a separate flat-out task "
            f"scored across all 38 pilots, not the group's endurance race."
        )
        s.append(
            f"Bill clocked {b['speed_kmh']:.1f} km/h on the single lap to run "
            f"leader {lead}'s {l['speed_kmh']:.1f} km/h - a {delta:.1f} km/h "
            f"shortfall for {_ord(b['rank'])} of {r['group_size']} and "
            f"{b['score']} points."
        )
        if alt_below - lead_below > 15:
            s.append(
                f"He crossed the start about {alt_below:.0f} m under the 400 m "
                f"ceiling while {lead} banked nearly the full height "
                f"({l['entry_alt_m']:.0f} m), so the leader had more stored "
                f"energy to trade for speed."
            )
        else:
            s.append(
                f"Both entered near the 400 m ceiling ({b['entry_alt_m']:.0f} m "
                f"to {l['entry_alt_m']:.0f} m), so the margin is carried speed "
                f"rather than entry height."
            )
        s.append(
            "With no lift to work, the whole gap is top-end cruise and a "
            "full-energy entry - the same speed lever as the distance rounds, "
            "isolated to one run."
        )
    elif n in _NEAR_WINS:
        s.append(
            f"Round {n} is one of Bill's near-wins: he went toe-to-toe with "
            f"{lead}, matching {b['laps']} laps for {b['score']} of a possible "
            f"1000 and {_ord(b['rank'])} of {r['group_size']}."
        )
        s.append(
            f"His cruise held level too - {b['speed_kmh']:.1f} km/h to the "
            f"winner's {l['speed_kmh']:.1f} - so the round came down to margins, "
            f"not pace, over {band} lift{extreme} in {wind_txt}."
        )
        if gate_gap > 8:
            s.append(
                f"The one visible slack is the gate: he entered at "
                f"{b['entry_speed_kmh']:.1f} km/h to {lead}'s "
                f"{l['entry_speed_kmh']:.1f}, well under the 120 km/h cap - free "
                f"opening-lap energy left on the table."
            )
        if note:
            s.append(f"Even the biggest single loss was slight: {note}")
    elif n == _WORST:
        delta = l["speed_kmh"] - b["speed_kmh"]
        s.append(
            f"Round {n} was Bill's worst of the week: only {b['laps']} laps to "
            f"{lead}'s {l['laps']} for {b['score']} of 1000 and "
            f"{_ord(b['rank'])} of {r['group_size']}."
        )
        s.append(
            f"This was a thermal-connection failure, not the conditions - lift "
            f"was {band}{extreme} - and once he sank out his average fell to "
            f"{b['speed_kmh']:.1f} km/h against {lead}'s {l['speed_kmh']:.1f}."
        )
        s.append(
            f"The damage is concentrated in one window "
            f"({_window(loss['start_s'], loss['end_s'])}): {note}"
        )
        s.append(
            "A single failed re-centre, not a string of slow laps, cost the "
            "flight."
        )
    else:
        lap_gap = l["laps"] - b["laps"]
        speed_delta = b["speed_kmh"] - l["speed_kmh"]
        s.append(
            f"Bill completed {b['laps']} laps to {lead}'s {l['laps']} - "
            f"{lap_gap} short - for {b['score']} of a possible 1000 and "
            f"{_ord(b['rank'])} of {r['group_size']} in the group."
        )
        if speed_delta >= -1.0:
            s.append(
                f"The gap was not pace: he actually cruised at "
                f"{b['speed_kmh']:.1f} km/h to {lead}'s {l['speed_kmh']:.1f}, so "
                f"it was staying aloft that cost him - fewer, lower climbs left "
                f"him {lap_gap} laps down, not slower ones."
            )
        else:
            s.append(
                f"The gap was cruise pace: {b['speed_kmh']:.1f} km/h to "
                f"{lead}'s {l['speed_kmh']:.1f} ({abs(speed_delta):.1f} km/h "
                f"slower), a deficit that compounds over the window into the "
                f"{lap_gap}-lap shortfall."
            )
        if band == "weak":
            s.append(
                f"It was a weak-lift window{extreme} in {wind_txt} - the "
                f"scarce-height conditions where Bill fades relatively."
            )
        else:
            s.append(f"Lift was {band}{extreme}, with {wind_txt}.")
        if gate_gap > 10:
            s.append(
                f"He also left energy at the gate, crossing at "
                f"{b['entry_speed_kmh']:.1f} km/h to {lead}'s "
                f"{l['entry_speed_kmh']:.1f} and well under the 120 km/h cap."
            )
        if note:
            s.append(
                f"The steepest divergence came at "
                f"{_window(loss['start_s'], loss['end_s'])}: {note}"
            )

    body = " ".join(s)
    return f"<p>{body} Figures reconcile to the {_event_link()}.</p>"


def _dash_section(r: dict, n: int, ctx: dict) -> str:
    """Return the 'Visual overview of performance' body (RPT-021 dashboard).

    Round-specific key insights (:func:`_dash_insights`, generated from the
    round's own numbers) as the lead-in, then the dashboard fragment inserted
    directly (it carries its own colour key and per-cell captions, so it is not
    wrapped in a ``<figure>``). The old boilerplate description of how to read
    the panel is dropped - the dashboard speaks for itself.

    On the three speed sprints the rank cell is relabelled: that task is scored
    across the whole 38-pilot field rather than within a heat group, which is
    what the surrounding prose says, so "Within-group rank / N pilots in group"
    contradicted it. The dashboard component is shared by both task types, so
    the page relabels its own copy rather than branching the component.
    """
    frag = dashboard.dashboard(r)
    if r["task_type"] == "speedrun":
        frag = frag.replace(">Within-group rank<", ">Field rank<")
        frag = frag.replace(f'{r["group_size"]} pilots in group',
                            f'{r["group_size"]} pilots in the field')
    return _dash_insights(r, n, ctx) + frag


def _energy_section(r: dict, n: int, *, is_speed: bool) -> str:
    """Return the Energy Management figure + a data-derived insight (RPT-018).

    The prose opens with the actual energy story for this round - who held more
    height in the first half versus the second, computed from the two altitude
    traces - rather than a description of the panels.
    """
    b, l = r["bill"], r["leader"]
    lead = C.esc(l.get("name", "the leader"))
    bs, ls = _alt_stats(b["track"]), _alt_stats(l["track"])
    if is_speed:
        caption = (
            f"Energy Management for the speed sprint: altitude (top) and ground "
            f"speed (bottom) over the single flat-out lap, both pilots on one "
            f"relative-time axis from the start-line crossing. Bill is green, "
            f"run leader {lead} blue."
        )
    else:
        caption = (
            f"Energy Management: altitude (top panel) and ground speed (bottom) "
            f"on one shared relative-time axis spanning the 30-minute task. Bill "
            f"is green, same-air leader {lead} blue; each trace ends at that "
            f"pilot's last turn-point crossing."
        )
    fig = C.figure(
        charts.energy_management(r),
        caption,
        fig_id=f"r{n}-fig-energy",
        source=(EVENT_URL, "event results"),
    )
    if is_speed:
        insight = (
            f"Off much the same start height, Bill turned less of it into pace "
            f"than {lead} - {b['speed_kmh']:.1f} km/h to {l['speed_kmh']:.1f} "
            f"km/h over the single lap. Both traces bleed altitude for speed "
            f"through the lap, but his ground-speed line sits below the leader's "
            f"from the first straight. A cleaner high-energy entry and a faster "
            f"glide line would convert the same height into more lap speed - the "
            f"cruise lever isolated to one run."
        )
    else:
        p = _energy_pattern(r)
        d1 = p["d1"] if p else 0.0
        d2 = p["d2"] if p else 0.0
        th = 8.0

        def _state(d: float) -> str:
            return "above" if d >= th else "below" if d <= -th else "level"

        early, late = _state(d1), _state(d2)
        e1, e2 = abs(d1), abs(d2)
        if early == "above" and late == "below":
            s1 = (
                f"Bill managed his energy well through the first half, holding "
                f"about {e1:.0f} m more height on average than {lead}, then lost "
                f"that edge in the latter half to sit roughly {e2:.0f} m below "
                f"him."
            )
        elif early == "level" and late == "below":
            s1 = (
                f"Bill stayed with {lead} on height early (within {e1:.0f} m on "
                f"average), then bled energy away in the latter half to fall "
                f"about {e2:.0f} m below him."
            )
        elif early == "below" and late == "below":
            widening = " - and the gap widened" if e2 > e1 + 20 else ""
            s1 = (
                f"Bill flew lower than {lead} for essentially the whole flight, "
                f"averaging about {e1:.0f} m down early and {e2:.0f} m down "
                f"late{widening}."
            )
        elif early == "above" and late == "above":
            s1 = (
                f"Bill held more height than {lead} across the whole flight, "
                f"averaging about {e1:.0f} m higher early and {e2:.0f} m higher "
                f"late, so energy was not where this round was lost."
            )
        elif early == "below" and late == "above":
            s1 = (
                f"Bill started lower than {lead} - about {e1:.0f} m down early - "
                f"then out-climbed him in the back half to average roughly "
                f"{e2:.0f} m higher."
            )
        elif early == "above" and late == "level":
            s1 = (
                f"Bill led {lead} on height early by about {e1:.0f} m, then the "
                f"leader clawed back to level by the finish."
            )
        elif early == "below" and late == "level":
            s1 = (
                f"Bill flew about {e1:.0f} m below {lead} early, then recovered "
                f"to roughly level height through the back half."
            )
        elif early == "level" and late == "above":
            s1 = (
                f"Bill matched {lead} on height early, then out-climbed him late "
                f"to average about {e2:.0f} m higher."
            )
        else:
            s1 = (
                f"Bill and {lead} tracked each other closely on height, staying "
                f"within a few metres on average through both halves of the "
                f"flight."
            )
        insight = (
            f"{s1} Across the task he banked about {bs.get('total_climb', 0):.0f} "
            f"m of climb to the leader's {ls.get('total_climb', 0):.0f} m, "
            f"working off a low near {bs.get('low', 0):.0f} m, while his speed "
            f"trace runs below the leader's between thermals. Less height in hand "
            f"forces earlier, slower glides, and the lap count follows."
        )
    return f"<p>{insight}</p>" + fig


def _track_section(r: dict, n: int, ctx: dict, *, is_speed: bool) -> str:
    """Return the ground-track & course figure + a data-derived insight (RPT-011).

    The prose opens with the round's actual line/turn story against the leader -
    line-length efficiency and turn radius from the per-round metrics - rather
    than a description of the overlay.
    """
    task = r["task"]
    # ADR-008: the .rct ``length`` (stored as ``leg_length_m``) is the turnpoint
    # RADIUS, not the flown leg. Caption geometry is derived so the numbers the
    # reader sees are the ones the triangle is drawn from.
    geom = course_geometry(task)
    course_txt = (
        f"{geom['radius_m']:.0f} m turnpoint radius, {geom['leg_m']:.0f} m legs "
        f"and a {geom['hypotenuse_m']:.0f} m base for a "
        f"{geom['perimeter_m']:.0f} m lap"
    )
    lead = C.esc(r["leader"].get("name", "the leader"))
    mt = _metrics_for(n, ctx)
    bm, lm = mt.get("BILL", {}), mt.get("leader", {})
    eff = bm.get("line_eff_ratio_bill_vs_leader")
    btr, ltr = bm.get("turn_radius_m"), lm.get("turn_radius_m")

    def _turn_clause() -> str:
        if not isinstance(btr, (int, float)) or not isinstance(ltr, (int, float)):
            return ""
        if is_speed:
            # One-lap sprints give a handful of turn samples; the averaged
            # radius is a thin-sample artefact (R4 216 m, R10 463 m), so it is
            # not quoted.
            return ""
        if btr > ltr * 1.1:
            return (f" His turn circles ran wider too, averaging {btr:.0f} m to "
                    f"{lead}'s {ltr:.0f} m.")
        if btr < ltr * 0.9:
            return (f" His corners were actually tighter than {lead}'s "
                    f"({btr:.0f} m to {ltr:.0f} m radius).")
        return f" Turn radii were comparable ({btr:.0f} m to {ltr:.0f} m)."

    if is_speed:
        caption = (
            f"Ground track & course: the bold triangle is the factual "
            f"right-isosceles course from the .rct - {course_txt} - drawn on top "
            f"of the full-resolution GPS traces (Bill green, run leader blue). "
            f"North arrow top-right, 100 m scale bottom-left, {_wind_clause(n)}. "
            f"On the sprint the lines stay tight to the course - no thermalling."
        )
        insight = (
            f"With no lift to hunt, both lines stay pinned to the course, so the "
            f"sprint turns on how much speed each carried through the corners."
            f"{_turn_clause()} Tighter corners and a straighter run between "
            f"turnpoints are the only time on offer - it comes down to carried "
            f"speed."
        )
    else:
        caption = (
            f"Ground track & course: the bold ink triangle is the factual "
            f"right-isosceles course reconstructed from the .rct - {course_txt} "
            f"- with turnpoint dots and a dashed start/finish line, overlaid on "
            f"the full-resolution GPS traces (Bill green, leader blue). Loops "
            f"off the course line are thermalling circles. North arrow "
            f"top-right, 100 m scale bottom-left, {_wind_clause(n)}."
        )
        if isinstance(eff, (int, float)) and eff >= 1.15:
            s1 = (
                f"Bill flew a markedly longer line than {lead} - about "
                f"{eff:.2f}× the ground distance over the same course - the extra "
                f"length is off-course loops spent searching for and working "
                f"lift."
            )
        elif isinstance(eff, (int, float)) and eff >= 1.05:
            s1 = (
                f"Bill covered a little more ground than {lead} for the same "
                f"laps (line ratio {eff:.2f}), his thermalling loops adding "
                f"distance the leader's tighter line avoided."
            )
        elif isinstance(eff, (int, float)):
            s1 = (
                f"Bill's racing line was about as efficient as {lead}'s (line "
                f"ratio {eff:.2f}), so the ground track was not where this round "
                f"was lost."
            )
        else:
            s1 = (
                f"Bill's thermalling loops sit off the course line while his "
                f"turnpoint arcs run close to {lead}'s."
            )
        wider = (isinstance(btr, (int, float)) and isinstance(ltr, (int, float))
                 and btr > ltr * 1.1)
        cost = ("so wider, slower circles cost most." if wider else
                "so where the loops go, and how soon they connect, cost most.")
        insight = (
            f"{s1}{_turn_clause()} Turnpoint technique is near a strength; the "
            f"loops, not the corners, are where the height - and the time - go, "
            f"{cost}"
        )
    fig = C.figure(charts.ground_track(r), caption, fig_id=f"r{n}-fig-track")
    return f"<p>{insight}</p>" + fig


def _laps_section(r: dict, n: int, *, is_speed: bool) -> str:
    """Return the cumulative-laps figure + PEE / single-lap framing.

    The three speed sprints render **no** cumulative-laps figure (RPT-013): the
    two pilots fly sequential slots, so their raw lap offsets sit 15-52 minutes
    apart on a shared clock and the chart showed two lone steps at opposite
    ends of a mostly empty axis. The dashboard's single-lap speed panel already
    carries that comparison, so the section keeps its prose and its anchor and
    drops the misleading plot.
    """
    b, l = r["bill"], r["leader"]
    lead = C.esc(l.get("name", "the leader"))
    wt_s = r["task"]["working_time_min"] * 60
    lap_gap = l["laps"] - b["laps"]
    fig = "" if is_speed else C.figure(
        charts.cumulative_laps(
            b["lap_offsets_s"], l["lap_offsets_s"], working_time_s=wt_s,
            title=f"Round {n} cumulative laps - Bill vs leader",
        ),
        (
            f"Laps completed over the task. Bill finished {b['laps']} to the "
            f"leader's {l['laps']}; the vertical gap between the step lines is "
            f"the lead opening up."
        ),
        fig_id=f"r{n}-fig-laps",
        source=(EVENT_URL, "event results"),
    )
    if is_speed:
        insight = (
            f"There is no lap count to build on the sprint - the result is one "
            f"flat-out lap, and Bill's ran {b['speed_kmh']:.1f} km/h to {lead}'s "
            f"{l['speed_kmh']:.1f} km/h. That was worth {b['score']} points and "
            f"{_ord(b['rank'])} of {r['group_size']} on the {_event_link()}. "
            f"Because the two pilots fly the sprint in separate slots there is "
            f"no shared clock to plot them on, so the single-lap speed panel on "
            f"the dashboard above carries the comparison. The reward is raw pace "
            f"and a full-energy entry, not endurance, so the lever is top-end "
            f"cruise speed rather than lasting the distance."
        )
    elif lap_gap == 0:
        insight = (
            f"Bill matched {lead} lap-for-lap the whole way, the two step lines "
            f"staying locked together to {b['laps']} laps each. Their cruise was "
            f"level too, {b['speed_kmh']:.1f} km/h to {l['speed_kmh']:.1f}. On a "
            f"round this close the result turns on fractions - clean turns and a "
            f"tidy landing - rather than lap count."
        )
    else:
        p = _laps_pattern(r)
        if p["def2"] > p["def1"]:
            s1 = (
                f"Bill kept pace with {lead} through the first half, then fell "
                f"away in the back half where most of the {lap_gap}-lap gap "
                f"opened."
            )
        elif p["def1"] > p["def2"]:
            s1 = (
                f"Bill fell behind {lead} early - most of the {lap_gap}-lap gap "
                f"was already open by mid-flight - then roughly held the "
                f"leader's pace to the finish."
            )
        else:
            s1 = (
                f"The {lap_gap}-lap gap to {lead} opened steadily across the "
                f"task rather than in a single collapse."
            )
        insight = (
            f"{s1} He held {b['speed_kmh']:.1f} km/h to the leader's "
            f"{l['speed_kmh']:.1f} while that step line pulled clear to "
            f"{l['laps']} laps. A slower average lap - mostly slower cruise "
            f"between thermals - is what compounds into the shortfall."
        )
    return f"<p>{insight}</p>" + fig


def _loss_section(r: dict, *, is_speed: bool) -> str:
    """Return the biggest-loss segment body (with sprint framing)."""
    loss = r["biggest_loss"]
    note = C.esc(loss.get("note", ""))
    if is_speed:
        return (
            f"<p>{note} On a one-lap speed task the whole gap is the single "
            f"run - there is no in-flight window to isolate, so the single-lap "
            f"speed panel on the dashboard carries the story. Source: "
            f"{_event_link()}.</p>"
        )
    dur = int(round(loss["end_s"] - loss["start_s"]))
    return (
        f"<p><strong>Single biggest-loss window: "
        f"{_window(loss['start_s'], loss['end_s'])}</strong> "
        f"({dur} s). {note}</p>"
        f"<p>This is the steepest part of the divergence on the cumulative-laps "
        f"and Energy Management charts above: one weak segment where the leader "
        f"banked a clean lap and Bill did not. Recovering even half of these "
        f"windows across the week is worth roughly a lap a round. Source: "
        f"{_event_link()}.</p>"
    )


def _reco(r: dict, n: int) -> str:
    """Return the round's 1-2 sentence takeaway, tied to its dominant lever."""
    lever = _dominant_lever(r)
    b, l = r["bill"], r["leader"]
    lead = C.esc(l.get("name", "the leader"))
    if n in _NEAR_WINS:
        return (
            f"<p>Round {n} is a near-win: Bill matched {lead} lap-for-lap for "
            f"{b['score']} points, with clean turns and a clean landing. Holding "
            f"{_xref('rec-cruise', 'cruise speed')} and "
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


def _summary_bullets(r: dict, n: int, ctx: dict) -> list[tuple[str, str]]:
    """Return the round's summary bullets as key points, one per section.

    RPT-007 asks the summary for "key points/recommendations", not a table of
    contents, so each bullet states what that section found for *this* round,
    drawn from the same facts its prose uses. The anchor ids are unchanged, so
    the bullets still jump to their sections.

    Args:
        r: the round dataset dict.
        n: round number (1-17).
        ctx: shared build context (per-round metrics, weather).

    Returns:
        list[tuple[str, str]]: ``(anchor_id, bullet_text)`` in section order.
    """
    b, l = r["bill"], r["leader"]
    lead = l.get("name", "the leader")
    is_speed = r["task_type"] == "speedrun"
    mt = _metrics_for(n, ctx)
    eff = mt.get("BILL", {}).get("line_eff_ratio_bill_vs_leader")
    btr = mt.get("BILL", {}).get("turn_radius_m")
    ltr = mt.get("leader", {}).get("turn_radius_m")
    bs, ls = _alt_stats(b["track"]), _alt_stats(l["track"])
    loss = r["biggest_loss"]
    cond = _round_conditions(n, ctx)

    if is_speed:
        delta = l["speed_kmh"] - b["speed_kmh"]
        if isinstance(eff, (int, float)):
            corner_pt = (f"Ran {eff:.2f}× the leader's ground distance over "
                         f"the lap - a wider line on a course with no lift to "
                         f"hunt")
        else:
            corner_pt = ("Both lines stayed pinned to the course - carried "
                         "speed, not lift, decides the sprint")
        points = [
            f"One flat-out lap at {b['speed_kmh']:.1f} km/h for {b['score']} "
            f"points, {_ord(b['rank'])} of {r['group_size']} in the field",
            f"Crossed the gate at {b['entry_alt_m']:.0f} m and "
            f"{b['entry_speed_kmh']:.0f} km/h, then traded height for pace",
            corner_pt,
            f"{delta:.1f} km/h behind {lead} over the single lap",
            "No in-flight window to isolate: the whole gap is the one run",
            "Train top-end cruise speed and a fuller start-gate entry",
        ]
    else:
        lap_gap = l["laps"] - b["laps"]
        pat = _laps_pattern(r)
        if lap_gap == 0:
            laps_pt = (f"Step lines locked together all task; cruise level at "
                       f"{b['speed_kmh']:.1f} to {l['speed_kmh']:.1f} km/h")
        elif pat["def2"] > pat["def1"]:
            laps_pt = (f"Kept pace early; most of the {lap_gap}-lap gap opened "
                       f"in the back half")
        elif pat["def1"] > pat["def2"]:
            laps_pt = (f"Fell behind early - most of the {lap_gap}-lap gap was "
                       f"open by mid-flight")
        else:
            laps_pt = f"The {lap_gap}-lap gap opened steadily across the task"

        if isinstance(eff, (int, float)) and eff >= 1.15:
            track_pt = (f"Covered {eff:.2f}× the leader's ground distance - "
                        f"off-course loops hunting lift")
        elif isinstance(eff, (int, float)) and eff >= 1.05:
            track_pt = (f"Line ratio {eff:.2f}: thermalling loops added distance "
                        f"the leader's line avoided")
        elif isinstance(eff, (int, float)):
            track_pt = (f"Racing line as efficient as the leader's (ratio "
                        f"{eff:.2f}) - not where the round was lost")
        elif isinstance(btr, (int, float)) and isinstance(ltr, (int, float)):
            track_pt = f"Turn circles {btr:.0f} m to {lead}'s {ltr:.0f} m"
        else:
            track_pt = "Thermalling loops sit off the course line"

        climb_pt = (f"Banked {bs.get('total_climb', 0):.0f} m of climb to "
                    f"{lead}'s {ls.get('total_climb', 0):.0f} m")
        # The takeaway and loss bullets mirror the round's own recommendation
        # section, near-win and worst-round special cases included, so the
        # summary and the sections cannot say different things.
        if n in _NEAR_WINS:
            reco_pt = "Hold this cruise and climb level on the weaker days"
            loss_pt = ("Even the biggest single loss was slight, at "
                       f"{_window(loss['start_s'], loss['end_s'])}")
        else:
            loss_pt = ("Steepest single loss at "
                       f"{_window(loss['start_s'], loss['end_s'])}")
            reco_pt = (
                "Lever this round: a decisive re-centre in weak lift"
                if n == _WORST else
                {"climb": "Lever this round: climb quality in weak lift"}.get(
                    _dominant_lever(r),
                    "Lever this round: cruise pace between thermals")
            )
        headline_pt = (
            f"Matched {lead} lap-for-lap ({b['laps']} each) for {b['score']} "
            f"points in {cond['band']} lift"
            if lap_gap == 0 else
            f"{b['laps']} laps to {lead}'s {l['laps']} for {b['score']} points "
            f"in {cond['band']} lift"
        )
        points = [
            headline_pt,
            climb_pt,
            track_pt,
            laps_pt,
            loss_pt,
            reco_pt,
        ]
    order = ["dash", "energy", "track", "laps", "loss", "reco"]
    return [(f"r{n}-{suf}", text) for suf, text in zip(order, points)]


def _sections(r: dict, n: int, ctx: dict) -> list[tuple]:
    """Build the ordered (suffix, heading, body, collapsed) sections for a round.

    Shared across triangle and speed rounds; the ``is_speed`` flag switches the
    framing of the Energy Management, ground-track, laps and loss sections. The
    dashboard opens the view (with round-specific key insights as its lead-in)
    and replaces the old per-round metrics strip and 'Bill vs leader' header
    (RPT-021).
    """
    is_speed = r["task_type"] == "speedrun"
    return [
        ("dash", "Visual Overview of Performance", _dash_section(r, n, ctx), False),
        ("energy", "Energy Management",
         _energy_section(r, n, is_speed=is_speed), False),
        ("track", "Ground Track & Course",
         _track_section(r, n, ctx, is_speed=is_speed), False),
        ("laps",
         "Single-Lap Speed Task" if is_speed else "Cumulative Laps vs Leader",
         _laps_section(r, n, is_speed=is_speed), True),
        ("loss", "Where the Time Went" if is_speed else "Biggest-Loss Segment",
         _loss_section(r, is_speed=is_speed), True),
        ("reco", "What to Train from This Round", _reco(r, n), True),
    ]


# --- View + render -----------------------------------------------------------
def render_round(entry: dict, ctx: dict) -> str:
    """Render one round's full view (summary + dashboard + figures + reco).

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
    lead = C.esc(l.get("name", "the leader"))

    sections = _sections(r, n, ctx)

    if r["task_type"] == "speedrun":
        intro = (
            f"Round {n} ({C.esc(label)}) is the <strong>speed sprint</strong> - "
            f"a one-lap flat-out task scored across all 38 pilots, distinct "
            f"from the endurance rounds. Bill ran {b['speed_kmh']:.1f} km/h to "
            f"the run leader {lead}'s {l['speed_kmh']:.1f} km/h, placing "
            f"{b['rank']}th for {b['score']} points. Full field on the "
            f"{_event_link()}."
        )
    else:
        lap_gap = l["laps"] - b["laps"]
        if n in _NEAR_WINS:
            verdict = (f"matched {lead} lap-for-lap ({b['laps']} each) for "
                       f"{b['score']} points - a near-win and one of his best "
                       f"rounds")
        elif n == _WORST:
            verdict = (f"managed only {b['laps']} laps and dropped - his worst "
                       f"round, a thermal that would not connect rather than "
                       f"the conditions")
        else:
            verdict = (f"completed {b['laps']} laps to the same-air leader "
                       f"{lead}'s {l['laps']} ({lap_gap} short), scoring "
                       f"{b['score']} of a possible 1000")
        intro = (
            f"Round {n} ({C.esc(label)}, {C.esc(r['heat'])}) is a distance "
            f"task. Bill {verdict}. The benchmark is the top scorer in his own "
            f"heat - same time slot, same air. Full standings on the "
            f"{_event_link()}."
        )

    summary = C.summary(intro, _summary_bullets(r, n, ctx), top_id=top)
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
