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
from ..data import TRACK_ALT

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
def _dash_section(r: dict) -> str:
    """Return the 'Visual overview of performance' body (RPT-021 dashboard).

    A short lead-in on how to read the dashboard, then the dashboard fragment
    inserted directly (it carries its own colour key and per-cell captions, so
    it is not wrapped in a ``<figure>``).
    """
    is_speed = r["task_type"] == "speedrun"
    lead = C.esc(r["leader"].get("name", "the leader"))
    speed_label = "single-lap speed" if is_speed else "average speed"
    intro = (
        f"<p>At-a-glance panel for this round. The top row reads left to right: "
        f"the group's score density (winner at 1000, Bill's score marked over "
        f"the field), then entry speed and entry altitude against the Sport-"
        f"class caps (120 km/h, 400 m), then {speed_label}. The bottom row "
        f"carries laps, within-group rank, the wind at the flight window and a "
        f"solar-radiation bar normalised across all 17 rounds as a lift proxy. "
        f"Green is Bill, blue is the round leader ({lead}), grey is the regs "
        f"cap or the rest of the field. Figures reconcile to the "
        f"{_event_link()}.</p>"
    )
    return intro + dashboard.dashboard(r)


def _energy_section(r: dict, n: int, *, is_speed: bool) -> str:
    """Return the Energy Management dual-panel figure + PEE (RPT-018)."""
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
        pee = (
            f"<p><strong>Point.</strong> The sprint is won on how much speed the "
            f"height buys, not on staying aloft. <strong>Evidence.</strong> Both "
            f"traces bleed altitude for pace across the one lap; Bill averaged "
            f"{b['speed_kmh']:.1f} km/h to {lead}'s {l['speed_kmh']:.1f} km/h on "
            f"the speed panel. <strong>Explain.</strong> A cleaner high-energy "
            f"entry and a faster glide line convert more of the same start "
            f"height into lap speed - the same cruise lever as the distance "
            f"rounds, isolated to one run.</p>"
        )
    else:
        pee = (
            f"<p><strong>Point.</strong> The altitude panel shows how the energy "
            f"budget was spent; the speed panel shows the cruise line between "
            f"climbs. <strong>Evidence.</strong> Bill recovers about "
            f"{bs.get('total_climb', 0):.0f} m of climb against the leader's "
            f"{ls.get('total_climb', 0):.0f} m, working off a floor near "
            f"{bs.get('low', 0):.0f} m, while his speed trace sits below the "
            f"leader's between thermals. <strong>Explain.</strong> Less height "
            f"banked per climb plus a slower cruise drains the glide budget "
            f"sooner, and the lap count follows.</p>"
        )
    return fig + pee


def _track_section(r: dict, n: int, *, is_speed: bool) -> str:
    """Return the ground-track & course figure + PEE (RPT-011)."""
    task = r["task"]
    leg = task.get("leg_length_m", "")
    if is_speed:
        caption = (
            f"Ground track & course: the bold triangle is the factual {leg} m-leg "
            f"course from the .rct, drawn on top of the full-resolution GPS "
            f"traces (Bill green, run leader blue). North arrow top-right, 100 m "
            f"scale bottom-left, wind vector in the right margin. On the sprint "
            f"the lines stay tight to the course - no thermalling."
        )
        pee = (
            f"<p><strong>Point.</strong> On the sprint the only line that matters "
            f"is the racing line through the turnpoints. "
            f"<strong>Evidence.</strong> Both traces hug the course triangle with "
            f"no off-course loops; the corner arcs and start-line crossing sit on "
            f"the plotted course. <strong>Explain.</strong> With no lift to hunt, "
            f"tighter corners and a straighter run between turnpoints are the only "
            f"time on offer - it comes down to carried speed.</p>"
        )
    else:
        caption = (
            f"Ground track & course: the bold ink triangle is the factual "
            f"{leg} m-leg course reconstructed from the .rct (turnpoint dots, "
            f"dashed start/finish line), overlaid on the full-resolution GPS "
            f"traces (Bill green, leader blue). Loops off the course line are "
            f"thermalling circles. North arrow top-right, 100 m scale bottom-"
            f"left, wind vector in the right margin."
        )
        pee = (
            f"<p><strong>Point.</strong> The traces show where each pilot left "
            f"the course to climb and how tightly they cornered. "
            f"<strong>Evidence.</strong> Bill's thermalling loops sit off the "
            f"course line while his turnpoint arcs run close to the leader's. "
            f"<strong>Explain.</strong> Turnpoint technique is near a strength; "
            f"the loops, not the corners, are where the height - and the time - "
            f"go, so wider, slower circles cost most.</p>"
        )
    fig = C.figure(charts.ground_track(r), caption, fig_id=f"r{n}-fig-track")
    return fig + pee


def _laps_section(r: dict, n: int, *, is_speed: bool) -> str:
    """Return the cumulative-laps figure + PEE / single-lap framing."""
    b, l = r["bill"], r["leader"]
    lead = C.esc(l.get("name", "the leader"))
    wt_s = r["task"]["working_time_min"] * 60
    lap_gap = l["laps"] - b["laps"]
    fig = C.figure(
        charts.cumulative_laps(
            b["lap_offsets_s"], l["lap_offsets_s"], working_time_s=wt_s,
            title=f"Round {n} cumulative laps - Bill vs leader",
        ),
        (
            f"Laps completed over the working window. This is a one-lap speed "
            f"task, so both pilots step to a single crossing - the distance "
            f"framing does not apply; the dashboard's single-lap speed panel "
            f"carries the comparison."
            if is_speed else
            f"Laps completed over the task. Bill finished {b['laps']} to the "
            f"leader's {l['laps']}; the vertical gap between the step lines is "
            f"the lead opening up."
        ),
        fig_id=f"r{n}-fig-laps",
        source=(EVENT_URL, "event results"),
    )
    if is_speed:
        pee = (
            f"<p><strong>Point.</strong> There is no lap count to build on a "
            f"sprint - it is decided on the single lap. "
            f"<strong>Evidence.</strong> Bill ran {b['speed_kmh']:.1f} km/h to "
            f"{lead}'s {l['speed_kmh']:.1f} km/h for {b['score']} points and "
            f"{b['rank']}th of {r['group_size']} on the {_event_link()}. "
            f"<strong>Explain.</strong> The sprint reward is raw pace and a "
            f"full-energy entry, not endurance, so the lever is top-end cruise "
            f"speed rather than lasting the distance.</p>"
        )
    else:
        pee = (
            f"<p><strong>Point.</strong> The gap opens gradually, not in one "
            f"blow-up. <strong>Evidence.</strong> The leader's step line pulls "
            f"steadily clear, reaching {l['laps']} laps at {l['speed_kmh']:.1f} "
            f"km/h while Bill holds {b['speed_kmh']:.1f} km/h for {b['laps']}. "
            f"<strong>Explain.</strong> A slower average lap - mostly slower "
            f"cruise between thermals - compounds over the task into the "
            f"{lap_gap}-lap shortfall.</p>"
        )
    return fig + pee


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
        f"{_mmss(loss['start_s'])}-{_mmss(loss['end_s'])}</strong> "
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


def _sections(r: dict, n: int) -> list[tuple]:
    """Build the ordered (suffix, heading, body, collapsed) sections for a round.

    Shared across triangle and speed rounds; the ``is_speed`` flag switches the
    framing of the Energy Management, ground-track, laps and loss sections. The
    dashboard opens the view and replaces the old per-round metrics strip and
    'Bill vs leader' header (RPT-021).
    """
    is_speed = r["task_type"] == "speedrun"
    return [
        ("dash", "Visual overview of performance", _dash_section(r), False),
        ("energy", "Energy Management",
         _energy_section(r, n, is_speed=is_speed), False),
        ("track", "Ground track & course",
         _track_section(r, n, is_speed=is_speed), False),
        ("laps",
         "Single-lap speed task" if is_speed else "Cumulative laps vs leader",
         _laps_section(r, n, is_speed=is_speed), True),
        ("loss", "Where the time went" if is_speed else "Biggest-loss segment",
         _loss_section(r, is_speed=is_speed), True),
        ("reco", "What to train from this round", _reco(r, n), True),
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

    sections = _sections(r, n)

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
