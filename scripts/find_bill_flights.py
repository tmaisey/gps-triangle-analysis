"""Locate Bill Maisey's flights in the competition results tree.

Scans the Results JSON, finds every group Bill flew in, and reports his
score plus his group-relative ranking and the top-scoring pilot (his
same-air benchmark) in each group.
"""
import json
from pathlib import Path

BILL = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"
ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "scores" / "results.json"


def name_lookup(comp):
    """Build userGuid -> 'First Last (country)' from the competition user list."""
    out = {}
    for u in comp["user"]:
        out[u["userGuid"]] = f"{u['name']} {u['surname']} ({u.get('country','?')})"
    return out


def main():
    d = json.load(open(RESULTS))
    names = name_lookup(d["competition"])
    print(f"Bill = {names.get(BILL, 'UNKNOWN')}\n")

    for heat in d["competitionGpsTriangleHeat"]:
        for g in heat["competitionGpsTriangleGroup"]:
            res = g["competitionGpsTriangleResult"]
            # rank within group by score (desc)
            ranked = sorted(res, key=lambda r: (r["score"], r["rawScore"]), reverse=True)
            bill = next((r for r in res if r["userGuid"] == BILL), None)
            if not bill:
                continue
            gid = g["competitionGpsTriangleGroupId"]
            pos = ranked.index(bill) + 1
            leader = ranked[0]
            print(f"{heat['name']} / {g['name']}  groupId={gid}  (n={len(res)})")
            print(f"  BILL   rank {pos}/{len(res)}  laps={bill['laps']} speed={bill['speed']:.2f} "
                  f"rawScore={bill['rawScore']} score={bill['score']} landing={bill['landing']} "
                  f"illegal={bill['isIllegal']} flightGuid={bill['flightPart']['flight']['flightGuid']}")
            tag = "SAME as Bill" if leader["userGuid"] == BILL else names.get(leader["userGuid"], leader["userGuid"])
            print(f"  LEADER {tag}  laps={leader['laps']} speed={leader['speed']:.2f} "
                  f"rawScore={leader['rawScore']} score={leader['score']} "
                  f"flightGuid={leader['flightPart']['flight']['flightGuid']}")
            print()


if __name__ == "__main__":
    main()
