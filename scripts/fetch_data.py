"""Fetch rcmodelspot GPS Triangle raw JSON for the anchor event and discovery.

Saves all raw payloads to data/scores/ so downstream analysis never re-hits the API.
Polite: small sleeps between calls.
"""
import json
import time
import pathlib

import requests

BASE = "https://www.rcmodelspot.com/api"
COMP = "f772fc7c-c4c5-406d-9c21-f4e76044ddb7"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "scores"
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "gps-triangle-analysis/1.0 (coaching insights)"}


def get(path):
    """GET a JSON endpoint under the rcmodelspot API base.

    Args:
        path: API path relative to :data:`BASE`.

    Returns:
        The decoded JSON payload.
    """
    url = f"{BASE}/{path}"
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    time.sleep(0.6)
    return r.json()


def save(name, obj):
    """Write a payload to ``data/scores/<name>`` and report its size.

    Args:
        name: output file name.
        obj: JSON-serialisable payload.
    """
    p = OUT / name
    p.write_text(json.dumps(obj))
    print(f"saved {name} ({p.stat().st_size} bytes)")


def main():
    """Fetch the anchor event's payloads plus the yearly league results."""
    # Anchor event
    save("meta.json", get(f"CompetitionGpsTriangle/{COMP}"))
    save("results.json", get(f"CompetitionGpsTriangle/Results/{COMP}"))
    save("competitors.json", get(f"Competition/Competitors/{COMP}"))

    # Yearly league results for discovery
    for year in (2022, 2023, 2024, 2025, 2026):
        try:
            save(f"yearly_{year}.json", get(f"CompetitionGpsTriangle/YearlyResults/{year}"))
        except Exception as e:  # noqa: BLE001
            print(f"yearly {year} FAILED: {e}")


if __name__ == "__main__":
    main()
