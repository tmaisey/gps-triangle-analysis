"""Innovations page.

The forward-looking coaching-technology roadmap (RPT-006), standalone and
rules-grounded. Each tier gets a stable anchor id so Analysis and
Recommendations can link to it in context, and each states its legality gate
(competition vs training) against the Sport-class rules.

Rules framing (Sport-class regs): passive telemetry display and relay are
permitted and a navigator may relay them; nothing may feed data into control of
the model (regs section 2.7); a pilot may field one navigator; an audio vario
and speech telemetry are explicitly allowed. AR and wearables are not named, so
a navigator-worn HUD re-presenting permitted telemetry is plausibly legal at
Contest-Director discretion, while a pilot-worn HUD is safest treated as
training-only.

Anchor / id scheme (tier section ids, link targets from other pages):
    inn-top          summary / back-to-top target
    inn-postflight   post-flight AI coach (most tractable)
    inn-navigator    navigator AR HUD (CD discretion)
    inn-live         live AI cueing (audio vario / speech telemetry channel)
    inn-flywheel     the data flywheel
"""

from __future__ import annotations

from .. import components as C

_SECTIONS = [
    ("inn-postflight", "Post-flight AI coach"),
    ("inn-navigator", "Navigator AR HUD"),
    ("inn-live", "Live AI cueing"),
    ("inn-flywheel", "The data flywheel"),
]

_SUMMARY_BULLETS = [
    ("inn-postflight", "Post-flight AI coach on this same data (most tractable)"),
    ("inn-navigator", "Navigator AR HUD (organiser discretion)"),
    ("inn-live", "Live cueing within the rules"),
    ("inn-flywheel", "A season-long data flywheel"),
]

_RULES_URL = "https://gps-triangle.net/gps-triangle/regulations-documents/"
_EVENT_URL = (
    "https://www.rcmodelspot.com/Ranking/"
    "f772fc7c-c4c5-406d-9c21-f4e76044ddb7"
)
_OLC = "https://www.onlinecontest.org"
_XREAL = "https://www.xreal.com"
_ROKID = "https://www.rokid.com"


def _xref(page: str, anchor: str, text: str) -> str:
    """Return a cross-page link in the shared xref convention (handler central)."""
    return (
        f'<a class="xref" data-page="{page}" data-anchor="{anchor}">'
        f"{C.esc(text)}</a>"
    )


def _ext(url: str, text: str) -> str:
    """Return an external link (new tab, no referrer leak)."""
    return (
        f'<a href="{C.esc(url)}" target="_blank" rel="noopener">'
        f"{C.esc(text)}</a>"
    )


def _gate(text: str) -> str:
    """Return the plainly-stated legality gate line for a tier."""
    return f'<p class="reco-label">Legality gate</p><p>{text}</p>'


def _postflight() -> str:
    return (
        "<p><strong>A post-flight AI coach is the most tractable step, and this "
        "report is the proof of concept.</strong> The same pipeline that built "
        "this analysis can be pointed at any event or flight - straight from "
        "the open "
        f"{_ext(_EVENT_URL, 'rcmodelspot')} data, or from an IGC log - to "
        "generate the round-by-round, phase-by-phase read automatically. On "
        "top of that it can drive a ghost replay of Bill against the same-air "
        "leader and flag recurring decision points, such as the glides where "
        "he consistently gives back cruise time or the climbs he leaves early.</p>"
        + _gate(
            "No competition constraint: this is offline analysis of flights "
            "already flown, so it sits entirely in the training and debrief "
            "space. Track upload and comparison already exist through "
            f"{_ext(_OLC, 'OLC-RC')}."
        )
    )


def _navigator() -> str:
    return (
        "<p><strong>A navigator AR HUD re-presents telemetry that is already "
        "permitted, in a form that is faster to read.</strong> Climb rate, "
        "energy state, distance-to-turn, line deviation and a live thermal map "
        "could sit in the navigator's field of view instead of being read off "
        "a screen and spoken. Hardware matters here: today's Ray-Ban Meta "
        "glasses are audio and camera only with no display, so a visual HUD "
        "needs display-class glasses (for example Ray-Ban Display) or AR "
        "glasses such as "
        f"{_ext(_XREAL, 'Xreal')} or {_ext(_ROKID, 'Rokid')}.</p>"
        + _gate(
            "The regulations do not name AR or wearables. A navigator-worn HUD "
            "that only re-presents permitted passive telemetry - feeding "
            "nothing into control of the model - is plausibly legal at Contest-"
            "Director discretion; a pilot-worn HUD is safest treated as "
            f"training-only until organisers rule on it ({_ext(_RULES_URL, 'Sport-class regulations')})."
        )
    )


def _live() -> str:
    return (
        "<p><strong>Live AI cueing turns the permitted speech channel into "
        "tactical calls.</strong> Telemetry streamed to a real-time engine "
        "could produce spoken prompts - commit to this core, push the glide, "
        "turn now - relayed by the navigator, plus a structured debrief the "
        "moment the flight lands. It is the natural extension of the audio "
        "vario and speech callouts that are "
        f"{_xref('recommendations', 'rec-signals', 'already worth setting up today')}.</p>"
        + _gate(
            "Spoken telemetry and an audio vario are explicitly permitted, and "
            "a navigator may relay them, so the audio path is legal in "
            "competition provided the cue is passive relay and nothing feeds "
            "into control of the model (regs section 2.7). The post-session "
            "debrief is unconstrained training use."
        )
    )


def _flywheel() -> str:
    return (
        "<p><strong>A data flywheel compounds every flight into sharper "
        "coaching.</strong> Accumulating Bill's tracks together with the wider "
        "field's would support counterfactual what-if-you-had-stayed "
        "simulation on the climbs he left early, condition playbooks that map "
        "the day's weather to a tactical plan, and opponent profiling of how "
        "the strongest pilots handle weak lift. Each event ingested makes the "
        "next read better - the "
        f"{_xref('innovations', 'inn-postflight', 'post-flight coach')} is the "
        "first turn of this wheel.</p>"
        + _gate(
            "Purely offline and historical: no in-flight component, so no "
            "competition constraint. It depends only on the open track data "
            "already published per event."
        )
    )


_BUILDERS = {
    "inn-postflight": _postflight,
    "inn-navigator": _navigator,
    "inn-live": _live,
    "inn-flywheel": _flywheel,
}


def render(ctx: dict) -> str:
    """Render the Innovations page fragment.

    Args:
        ctx: shared build context.

    Returns:
        str: the Innovations page inner HTML.
    """
    intro = (
        "The art of the possible for coaching technology, ordered from the most "
        "tractable to the most ambitious. Each tier is framed against the "
        f'Sport-class rules (<a href="{C.esc(_RULES_URL)}" target="_blank" '
        'rel="noopener">regulations</a>): passive telemetry display and relay '
        "are permitted and a navigator may relay them, but nothing may feed "
        "data into control of the model (section 2.7). Where a tier touches "
        "competition rather than training, the legality gate is stated plainly."
    )
    summary = C.summary(intro, _SUMMARY_BULLETS, top_id="inn-top")
    sections = [
        C.collapsible(sid, heading, _BUILDERS[sid](), top_id="inn-top")
        for sid, heading in _SECTIONS
    ]
    return (
        "<h1>Innovations</h1>"
        + summary + C.expand_collapse_controls() + "".join(sections)
    )
