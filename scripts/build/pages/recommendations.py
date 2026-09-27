"""Recommendations page.

Consolidates the one canonical recommendation set, organised into implementation
themes (RPT-005). Each theme anchor is shared with the inline recommendations in
Analysis so both surfaces link to the same id. Each theme states the
evidence-backed point (back-linked to the Analysis section that proves it),
then drills, further analysis and resources, and cross-refers the Innovations
tier where one is relevant.

Anchor / id scheme (theme section ids, shared with Analysis inline recos):
    rec-top       summary / back-to-top target
    rec-cruise    cruise-speed drills + analysis (highest priority)
    rec-climb     climb-quality (height banked) drills + analysis
    rec-entry     entry-speed (use the cap) drills
    rec-turns     turn / line refinement
    rec-signals   rules-legal live signals (audio vario, speech telemetry)
"""

from __future__ import annotations

from .. import components as C

_SECTIONS = [
    ("rec-cruise", "Cruise speed between thermals"),
    ("rec-climb", "Climb quality - height banked per thermal"),
    ("rec-entry", "Entry speed - use the 120 km/h cap"),
    ("rec-turns", "Turnpoint lines"),
    ("rec-signals", "Rules-legal live signals"),
]

_SUMMARY_BULLETS = [
    ("rec-cruise", "Train faster inter-thermal cruise (top lever)"),
    ("rec-climb", "Bank more height per climb on weak days"),
    ("rec-entry", "Use more of the entry-speed cap"),
    ("rec-turns", "Tighten turnpoint lines (near a strength)"),
    ("rec-signals", "Audio vario and speech telemetry callouts, today"),
]

# Regulations index (general rules mentions link here).
_RULES_URL = "https://gps-triangle.net/gps-triangle/regulations-documents/"

# Resource links, used only where a source adds something useful.
_SM_GPS = "https://www.sm-modellbau.de/GPS-Logger-3"
_OLC = "https://www.onlinecontest.org"
_BMFA_SFTC = "https://silent-flight-tech.bmfa.org/specialisms/gps"


def _xref(page: str, anchor: str, text: str) -> str:
    """Return a cross-page link in the shared xref convention (handler central)."""
    return (
        f'<a class="xref" data-page="{page}" data-anchor="{anchor}">'
        f"{C.esc(text)}</a>"
    )


def _ext(url: str, text: str) -> str:
    """Return an external resource link (new tab, no referrer leak)."""
    return (
        f'<a href="{C.esc(url)}" target="_blank" rel="noopener">'
        f"{C.esc(text)}</a>"
    )


def _block(heading: str, items: list[str]) -> str:
    """Return a labelled sub-list (Drills / Further analysis / Resources)."""
    lis = "".join(f"<li>{it}</li>" for it in items)
    return f"<p class=\"reco-label\">{C.esc(heading)}</p><ul>{lis}</ul>"


def _cruise() -> str:
    point_evidence = (
        "<p><strong>Cruise pace between thermals is the single biggest lever.</strong> "
        "On clean laps Bill glides at 61.9 km/h against the same-air leader's "
        "67.4 km/h, roughly 8% slower, at a shallower glide ratio (9.3 vs 10.3). "
        "That gap is about 90% of his 22 s per-lap clean-lap deficit, and a "
        "pace counterfactual attributes about +2.7 of the roughly three-lap "
        "shortfall to speed alone. Laps decide the score, so cruise pace is the "
        "underlying cause of the lower lap count "
        f"({_xref('analysis', 'ov-levers', 'see the ranked phase levers in Analysis')}).</p>"
    )
    drills = _block("Drills", [
        "Speed-to-fly discipline: hold a higher glide speed between climbs and "
        "resist the instinct to stretch every glide flat.",
        "Fly to a target inter-thermal cruise speed for the day's conditions "
        "rather than a habitual comfortable pace.",
        "Cut altitude spent loitering at low value - convert height into "
        "distance while the air is sinking anyway.",
    ])
    further = _block("Further analysis", [
        "Per-leg speed against wind direction once a task file with turnpoint "
        "coordinates is available, to separate true cruise pace from "
        "head/tail-wind legs.",
    ])
    return point_evidence + drills + further


def _climb() -> str:
    point_evidence = (
        "<p><strong>Climb quality is the second lever, and it decides the weak "
        "days.</strong> Bill actually circles less than the leader in total "
        "(287 vs 402 s), so he is not over-thermalling; but he banks about 35% "
        "less height per thermal (40.7 vs 63.1 m) with wider, slower circles "
        "(39.4 vs 33.2 m radius; 0.89/2.55 vs 1.03/3.64 m/s mean/best climb). "
        "When lift is scarce this makes him land early - three laps in R9, two "
        "in R12 - which is where the lap-count shortfall opens up "
        f"({_xref('analysis', 'ov-levers', 'phase levers')}; "
        f"{_xref('analysis', 'ov-consistency', 'floor-vs-ceiling consistency')}).</p>"
    )
    drills = _block("Drills", [
        "Tighter, better-centred circles: work the core rather than orbiting it.",
        "Bank-angle discipline - a consistent, committed bank to shrink the "
        "turn radius toward the leader's 33 m.",
        "Commit to weak cores instead of leaving to search; patience before "
        "abandoning lift on poor-lift days.",
    ])
    further = _block("Further analysis", [
        "Per-thermal centring traces (drift-corrected) to quantify how much of "
        "the height gap is radius versus core selection.",
    ])
    innov = (
        "<p class=\"reco-label\">Where technology could help</p>"
        "<p>A better real-time picture of climb rate and where the core sits is "
        "exactly what the "
        f"{_xref('innovations', 'inn-navigator', 'navigator AR HUD')} and "
        f"{_xref('innovations', 'inn-live', 'live AI cueing')} tiers target.</p>"
    )
    return point_evidence + drills + further + innov


def _entry() -> str:
    point_evidence = (
        "<p><strong>Entry speed is a cheap early win.</strong> Bill crosses the "
        "start gate at 70.8 km/h against the leader's 94.5 km/h, leaving about "
        "49 km/h of the 120 km/h cap unused - roughly twice the leader's unused "
        "margin. His entry altitude is already at the cap, so this is free "
        "opening-lap energy left on the table "
        f"({_xref('analysis', 'ov-levers', 'see the entry-speed lever')}).</p>"
    )
    drills = _block("Drills", [
        "Build and carry start-gate speed up toward the 120 km/h cap on the "
        "run-in, so the first lap starts with the energy the rules allow.",
        "Practise the timed dive-to-gate so the peak speed lands on the line, "
        "not before or after it.",
    ])
    return point_evidence + drills


def _turns() -> str:
    point_evidence = (
        "<p><strong>Turnpoint lines are already close to a strength - treat "
        "this as fine-tuning.</strong> Bill's lines run about 15 m per lap "
        "wider than the leader's, and turn technique costs only around 2 s per "
        "lap (about 10% of the deficit), the smallest of the four levers "
        f"({_xref('analysis', 'ov-levers', 'phase levers, ranked')}).</p>"
    )
    drills = _block("Drills", [
        "Modest line tightening at the turnpoints, without bleeding the speed "
        "that the cruise lever is there to build - the two must not fight.",
    ])
    return point_evidence + drills


def _signals() -> str:
    point_evidence = (
        "<p><strong>Several live aids are legal today and need no new rules.</strong> "
        "A pilot may field one navigator whose role includes relaying "
        "telemetry, and both an audio vario and spoken telemetry callouts are "
        "explicitly permitted. None of these feed data into control of the "
        "model, so they stay inside the "
        f"{_ext(_RULES_URL, 'Sport-class rules')} "
        f"({_xref('innovations', 'inn-live', 'the same permitted channel the live-cueing tier builds on')}).</p>"
    )
    aids = _block("Set up now", [
        "Audio vario tuning: shape the tone gradient tightly around the core so "
        "small changes in climb rate are audible, not just present or absent.",
        "Speech telemetry callouts through the radio - climb rate, altitude "
        "band, distance-to-turn - so Bill keeps his eyes on the model.",
        "A navigator working the ground station, calling the telemetry picture "
        "and the tactical decision points.",
    ])
    resources = _block("Resources", [
        _ext(_SM_GPS, "SM-Modellbau GPS-Logger 3") + " - logger with audio "
        "vario and speech telemetry output.",
        _ext(_OLC, "OLC-RC (Online Contest)") + " - track upload and "
        "comparison for structured post-session review.",
        _ext(_BMFA_SFTC, "BMFA Silent Flight Technical Committee - GPS")
        + " - the discipline's rules and equipment guidance.",
    ])
    innov = (
        "<p class=\"reco-label\">Future extensions</p>"
        "<p>These same permitted channels are the foundation the "
        f"{_xref('innovations', 'inn-navigator', 'navigator AR HUD')}, "
        f"{_xref('innovations', 'inn-live', 'live AI cueing')} and "
        f"{_xref('innovations', 'inn-postflight', 'post-flight AI coach')} "
        "tiers extend.</p>"
    )
    return point_evidence + aids + resources + innov


_BUILDERS = {
    "rec-cruise": _cruise,
    "rec-climb": _climb,
    "rec-entry": _entry,
    "rec-turns": _turns,
    "rec-signals": _signals,
}


def render(ctx: dict) -> str:
    """Render the Recommendations page fragment.

    Args:
        ctx: shared build context.

    Returns:
        str: the Recommendations page inner HTML.
    """
    summary = C.summary(
        "The recommendations that follow from the analysis, grouped by "
        "implementation theme and ordered by how much each would move Bill's "
        "score. Each theme links back to the evidence that motivates it and, "
        "where relevant, out to the matching Innovations tier.",
        _SUMMARY_BULLETS,
        top_id="rec-top",
    )
    sections = [
        C.collapsible(sid, heading, _BUILDERS[sid](), top_id="rec-top")
        for sid, heading in _SECTIONS
    ]
    return (
        "<h1>Recommendations</h1>"
        + summary + C.expand_collapse_controls() + "".join(sections)
    )
