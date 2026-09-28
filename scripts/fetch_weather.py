"""Fetch ERA5 historical weather for the Oschatz task site and save raw JSON.

Pulls hourly variables from the Open-Meteo ERA5 archive (free, no key) for the
World Masters Oschatz 2026 event window. Requests the full requested variable
set; if the API rejects any variable it probes each one and refetches with only
the accepted set, recording which were dropped. Raw JSON lands in ``data/``.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "weather_era5_oschatz.json"

BASE = "https://archive-api.open-meteo.com/v1/archive"
LAT = 51.297718
LON = 13.082957
START = "2026-08-03"
END = "2026-08-08"
TZ = "Europe/Berlin"

WANTED = [
    "temperature_2m",
    "relative_humidity_2m",
    "windspeed_10m",
    "winddirection_10m",
    "windgusts_10m",
    "cloudcover",
    "cloudcover_low",
    "shortwave_radiation",
    "cape",  # requested, but the ERA5 archive returns null for every hour
    "surface_pressure",
    "boundary_layer_height",
]


def fetch(hourly_vars):
    """Call the archive API for the given hourly variables.

    Args:
        hourly_vars: List of Open-Meteo hourly variable names.

    Returns:
        Tuple ``(ok, payload)`` where ``ok`` is True and ``payload`` is the
        decoded JSON on success, or False and the error text on failure.
    """
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": START,
        "end_date": END,
        "timezone": TZ,
        "windspeed_unit": "kmh",
        "hourly": ",".join(hourly_vars),
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return True, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return False, e.read().decode()


def main():
    """Fetch weather with variable-rejection fallback and persist raw JSON."""
    ok, payload = fetch(WANTED)
    dropped = []
    if not ok:
        print(f"Full request rejected: {payload[:200]}\nProbing variables individually...")
        accepted = []
        for v in WANTED:
            vok, _ = fetch([v])
            (accepted if vok else dropped).append(v)
            print(f"  {v}: {'OK' if vok else 'REJECTED'}")
        if not accepted:
            sys.exit("No variables accepted; aborting.")
        ok, payload = fetch(accepted)
        if not ok:
            sys.exit(f"Refetch failed: {payload[:200]}")

    payload["_meta"] = {
        "requested": WANTED,
        "dropped": dropped,
        "returned_vars": [k for k in payload.get("hourly", {}) if k != "time"],
        "source": BASE,
        "note": "ERA5 hourly archive; windspeed_unit=kmh",
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"\nSaved {OUT}")
    print("Returned vars:", payload["_meta"]["returned_vars"])
    print("Dropped:", dropped or "none")
    print("Grid point:", payload.get("latitude"), payload.get("longitude"),
          "elev", payload.get("elevation"), "utc_offset_s", payload.get("utc_offset_seconds"))


if __name__ == "__main__":
    main()
