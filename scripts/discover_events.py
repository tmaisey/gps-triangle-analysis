"""Task B: enumerate every rcmodelspot GPS Triangle event Bill Maisey appears in.

Strategy: the YearlyResults/{year} league lists, per class, every pilot and the
events (guid+name+score) they scored in that year. We scan all cached years and
classes for Bill's userGuid, collect his event guids, then fetch each event's
Results to grab his finishing position and field size (headline only).

Writes analysis/events_bill.csv.
"""
import json
import time
import pathlib
import csv
import requests

BASE = "https://www.rcmodelspot.com/api"
D = pathlib.Path("/Users/twm/code/projects/gps-triangle/data/scores")
A = pathlib.Path("/Users/twm/code/projects/gps-triangle/analysis")
BILL = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"
HEADERS = {"User-Agent": "gps-triangle-analysis/1.0 (coaching insights)"}
ANCHOR = "f772fc7c-c4c5-406d-9c21-f4e76044ddb7"


def get(path):
    r = requests.get(f"{BASE}/{path}", headers=HEADERS, timeout=60)
    r.raise_for_status()
    time.sleep(0.6)
    return r.json()


def main():
    # 1. Collect Bill's events from yearly leagues (all classes)
    found = {}  # guid -> {name, year, class, league_score}
    for year in (2022, 2023, 2024, 2025, 2026):
        p = D / f"yearly_{year}.json"
        if not p.exists():
            continue
        data = json.load(open(p))
        for class_block in data:
            cid = class_block.get("classId")
            for cr in class_block.get("classResults", []):
                if cr["user"]["userGuid"] == BILL:
                    for ev in cr.get("results", []):
                        g = ev["guid"]
                        found.setdefault(g, {
                            "guid": g, "name": ev["name"], "year": year,
                            "classId": cid, "league_score": round(ev["score"], 1),
                            "best_counted": ev.get("best"),
                        })
    # ensure anchor is present
    found.setdefault(ANCHOR, {"guid": ANCHOR, "name": "World Masters Sport class Oschatz",
                              "year": 2026, "classId": 2, "league_score": None, "best_counted": None})

    print(f"Bill appears in {len(found)} distinct events across yearly leagues")

    # 2. For each event, fetch results to get finishing position + field size + meta date
    rows = []
    for g, info in found.items():
        pos = field = date = totalScore = None
        try:
            comps = get(f"Competition/Competitors/{g}")
            in_field = any(c["userGuid"] == BILL for c in comps) if isinstance(comps, list) else None
            field = len(comps) if isinstance(comps, list) else None
        except Exception as e:  # noqa: BLE001
            in_field = None
            print(f"  competitors fail {info['name']}: {e}")
        try:
            r = get(f"CompetitionGpsTriangle/Results/{g}")
            standings = sorted(r.get("standings", []), key=lambda s: -s.get("totalScore", 0))
            field = len(standings) or field
            for i, s in enumerate(standings, 1):
                if s["userGuid"] == BILL:
                    pos = i
                    totalScore = s.get("totalScore")
            (D / f"event_{g}.json").write_text(json.dumps(r))
        except Exception as e:  # noqa: BLE001
            print(f"  results fail {info['name']}: {e}")
        try:
            meta = get(f"CompetitionGpsTriangle/{g}")
            date = meta.get("startTime", "")[:10]
            loc = meta.get("location")
            country = meta.get("country")
        except Exception:  # noqa: BLE001
            loc = country = None
        rows.append({
            "name": info["name"], "date": date, "guid": g,
            "classId": info["classId"], "location": loc, "country": country,
            "field_size": field, "bill_position": pos, "bill_totalScore": totalScore,
            "league_score": info["league_score"], "year": info["year"],
        })
        print(f"  {info['name'][:40]:40} {str(date):10} pos={pos}/{field}")

    rows.sort(key=lambda x: (str(x["date"]) or "", x["name"]))
    cols = ["name", "date", "guid", "classId", "location", "country",
            "field_size", "bill_position", "bill_totalScore", "league_score", "year"]
    with open(A / "events_bill.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote analysis/events_bill.csv ({len(rows)} events)")


if __name__ == "__main__":
    main()
