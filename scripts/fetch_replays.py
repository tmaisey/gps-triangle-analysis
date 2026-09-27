"""Fetch ReplayGroup track JSON for each of Bill Maisey's 17 competition groups.

Builds the round manifest from the already-saved Results tree (heat -> group ->
results), identifies Bill's group and the top-scoring leader (same-air benchmark)
in each, then downloads the full ~1 Hz track replay for every such group to
data/tracks/replay_{groupId}.json. Politely rate-limited; skips groups already
on disk. Also writes a compact round manifest to data/tracks/rounds_manifest.json
for the downstream metrics step.
"""
import json
import time
from pathlib import Path

import requests

BASE = "https://www.rcmodelspot.com/api"
COMP = "f772fc7c-c4c5-406d-9c21-f4e76044ddb7"
BILL = "2e6eb0fb-d61f-410c-a08e-313b1dd87977"
ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "scores" / "results.json"
COMPETITORS = ROOT / "data" / "scores" / "competitors.json"
TRACKS = ROOT / "data" / "tracks"
HEADERS = {"User-Agent": "gps-triangle-analysis/1.0 (coaching insights)"}


def name_lookup():
    """Build userGuid -> {'name','club','country'} from the competitor list."""
    d = json.load(open(RESULTS))
    out = {}
    for u in d["competition"]["user"]:
        out[u["userGuid"]] = {
            "name": f"{u['name']} {u['surname']}".strip(),
            "club": u.get("club"),
            "country": u.get("country"),
        }
    return out


def build_manifest():
    """One record per round Bill flew: heat/group ids, Bill & leader results."""
    d = json.load(open(RESULTS))
    names = name_lookup()
    rounds = []
    for hi, heat in enumerate(d["competitionGpsTriangleHeat"], start=1):
        for g in heat["competitionGpsTriangleGroup"]:
            res = g["competitionGpsTriangleResult"]
            bill = next((r for r in res if r["userGuid"] == BILL), None)
            if not bill:
                continue
            ranked = sorted(res, key=lambda r: (r.get("score", 0), r.get("rawScore", 0)), reverse=True)
            leader = ranked[0]
            gid = g["competitionGpsTriangleGroupId"]
            # whole-group ~1 lap => speedrun task
            laps_list = [r.get("laps", 0) or 0 for r in res]
            max_laps = max(laps_list) if laps_list else 0
            task_type = "speedrun" if max_laps <= 1 else "triangle"

            def pack(r):
                nm = names.get(r["userGuid"], {})
                return {
                    "userGuid": r["userGuid"],
                    "name": nm.get("name", r["userGuid"]),
                    "club": nm.get("club"),
                    "country": nm.get("country"),
                    "laps": r.get("laps", 0) or 0,
                    "speed_ms": r.get("speed", 0) or 0,
                    "rawScore": r.get("rawScore", 0) or 0,
                    "score": r.get("score", 0) or 0,
                    "landing": r.get("landing", 0) or 0,
                    "isIllegal": r.get("isIllegal", False),
                    "zoneEntered": r.get("zoneEntered"),
                    "flightGuid": r["flightPart"]["flight"]["flightGuid"],
                }

            rounds.append({
                "round": len(rounds) + 1,
                "heat": heat["name"],
                "heat_index": hi,
                "group_name": g["name"],
                "group_id": gid,
                "group_size": len(res),
                "task_type": task_type,
                "bill_rank": ranked.index(bill) + 1,
                "bill": pack(bill),
                "leader": pack(leader),
                "leader_is_bill": leader["userGuid"] == BILL,
            })
    return rounds


def get(path):
    r = requests.get(f"{BASE}/{path}", headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r.json()


def main():
    TRACKS.mkdir(parents=True, exist_ok=True)
    rounds = build_manifest()
    (TRACKS / "rounds_manifest.json").write_text(json.dumps(rounds, indent=1))
    print(f"Manifest: {len(rounds)} rounds -> {TRACKS/'rounds_manifest.json'}")

    for rd in rounds:
        gid = rd["group_id"]
        out = TRACKS / f"replay_{gid}.json"
        if out.exists():
            print(f"  round {rd['round']:>2} group {gid}: already on disk ({out.stat().st_size} B)")
            continue
        print(f"  round {rd['round']:>2} group {gid} ({rd['task_type']}, n={rd['group_size']}): fetching...", flush=True)
        try:
            data = get(f"CompetitionGpsTriangle/ReplayGroup/{gid}")
            out.write_text(json.dumps(data))
            print(f"      saved {out.stat().st_size} B, pilots={len(data)}")
        except Exception as e:  # noqa: BLE001
            print(f"      FAILED: {e}")
        time.sleep(1.0)

    total = sum(p.stat().st_size for p in TRACKS.glob("replay_*.json"))
    print(f"Total tracks on disk: {total/1e6:.1f} MB")


if __name__ == "__main__":
    main()
