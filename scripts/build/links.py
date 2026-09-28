"""Verified external source URLs used for grounding (RPT-008 / RPT-016).

Every outbound link in the report resolves to one of the constants collected
here, so a URL is defined once and checked once. The page modules import from
this module rather than declaring their own copies - three separate
``_RULES_URL`` definitions previously drifted onto WordPress-style paths that
``gps-triangle.net`` never served, shipping eight dead anchors.

:data:`ALLOWED_EXTERNAL_URLS` is the allowlist the build test asserts against:
an external ``href`` that is not in it fails the suite, so a new or edited URL
cannot reach the deliverable without a human having resolved it first. The test
performs no network access - resolution is verified by hand when a constant is
added or changed, and recorded in the note beside it.
"""

from __future__ import annotations

# --- Event / telemetry source ----------------------------------------------
# The public rcmodelspot ranking page for the anchor event (PRD section 2).
EVENT_URL = (
    "https://www.rcmodelspot.com/Ranking/f772fc7c-c4c5-406d-9c21-f4e76044ddb7"
)

# --- Rules --------------------------------------------------------------------
# Regulations index on the (static, Mobirise) gps-triangle.net site. Verified
# 2026-09-28: serves <title>Regulations</title> and links the class PDFs below.
RULES_INDEX_URL = "https://gps-triangle.net/page1.html"

# Sport-class regulations, current release. Verified 2026-09-28: the document's
# contents list carries "2.7 Gyros, Auto Pilots & Telemetry", the section the
# report cites for the telemetry / model-control rule.
RULES_PDF_URL = (
    "https://gps-triangle.net/assets/files/"
    "regulations_sport_en_V1.9_release01.pdf"
)

# --- Weather ------------------------------------------------------------------
# ERA5 reanalysis archive used for the per-flight conditions (PRD section 2).
WEATHER_URL = "https://open-meteo.com/"

# --- Recommendation / innovation resources -----------------------------------
# Logger with audio-vario and speech-telemetry output (rec-signals).
SM_GPS_URL = "https://www.sm-modellbau.de/GPS-Logger-3"
# Track upload and comparison for structured post-session review.
OLC_URL = "https://www.onlinecontest.org"
# The UK discipline body's GPS specialism pages (rules and equipment guidance).
BMFA_SFTC_URL = "https://silent-flight-tech.bmfa.org/specialisms/gps"
# AR display-glasses vendors referenced by the navigator-HUD tier.
XREAL_URL = "https://www.xreal.com"
ROKID_URL = "https://www.rokid.com"
# Meta's smart-glasses range. Verified 2026-09-28: lists the camera-and-audio
# "Ray-Ban Meta" line separately from the display-equipped "Meta Ray-Ban
# Display" - the distinction the navigator-HUD hardware note rests on.
META_GLASSES_URL = "https://www.meta.com/ai-glasses/"

#: Every external URL the build is permitted to emit.
ALLOWED_EXTERNAL_URLS = frozenset({
    EVENT_URL,
    RULES_INDEX_URL,
    RULES_PDF_URL,
    WEATHER_URL,
    SM_GPS_URL,
    OLC_URL,
    BMFA_SFTC_URL,
    XREAL_URL,
    ROKID_URL,
    META_GLASSES_URL,
})
