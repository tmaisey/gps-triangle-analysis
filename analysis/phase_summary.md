# Flight-phase decomposition — Bill Maisey vs same-air group leaders

14 triangle rounds (speedruns 4/10/16 excluded). Motor-off racing only. Values are means across rounds; Bill vs the top scorer in his group each round.

## 1. Aggregate phase metrics (Bill vs leader)

| Phase | Metric | Bill | Leader | Gap |
|---|---|---|---|---|
| START | Entry speed at gate (km/h) | 70.8 | 94.5 | **-23.7** |
| START | Unused margin to 120 cap (km/h) | 49.2 | 25.5 | Bill wastes 23.7 more |
| START | Lap-1 time (s, incl. settling) | 245.4 | 200.8 | +44.6 |
| STRAIGHT | Cruise speed (km/h) | 61.9 | 67.4 | **-5.6 (8.2%)** |
| STRAIGHT | Glide ratio (glide legs) | 9.3 | 10.3 | -1.0 |
| TURN | Speed scrubbed per corner (km/h) | 0.6 | -1.8 | Bill loses, leader gains |
| TURN | Extra distance per corner (m) | 36.7 | 31.6 | +5.0 |
| TURN | Extra distance per lap (m) | 111.7 | 96.3 | **+15.4** |
| CLIMB | Height banked per thermal (m) | 40.7 | 63.1 | **-22.4** |
| CLIMB | Mean climb rate (m/s) | 0.89 | 1.03 | -0.14 |
| CLIMB | Best climb rate (m/s) | 2.55 | 3.64 | -1.09 |
| CLIMB | Median circle radius (m) | 39.4 | 33.2 | **+6.1 (wider)** |
| CLIMB | Total time thermalling (s) | 287.0 | 402.2 | Bill circles LESS |
| ALOFT | Mean racing time used (s of 1800) | 1479.0 | 1703.5 | **-224.5** |

**Reads:** entry speed confirms the under-used-start pattern — Bill crosses 23.7 km/h slower than the leader and leaves ~49.2 km/h of the 120 cap unused (leader leaves half that). Cruise is 8% slow and glide is slightly worse. Corners: leader carries/gains speed through the apex; Bill scrubs a little and rounds ~15.4 m wider per lap. Climbs confirm the hypothesis with a twist — Bill banks ~35% LESS height per thermal, climbs slower, and circles WIDER (39 vs 33 m radius), yet spends LESS total time circling. He is not over-thermalling; he under-banks and then runs out of air, landing early and using ~225 s less of the 30-min window than the leader.

## 2. Per-lap time-deficit decomposition (clean laps, paired per round)

Bill's mean **clean-lap deficit = 22.0 s/lap** slower than his leader (rounds used: [1, 2, 5, 6, 7, 8, 9, 11, 13, 14, 15, 17]; excluded for no clean lap: [3, 12]).

| Component | s/lap | Share |
|---|---|---|
| Slower STRAIGHTS (cruise) | 19.8 | **90.2%** |
| Slower/wider TURNS | 2.1 | 9.6% |
| **Total per-lap deficit** | **22.0** | 100% |

**Method:** on clean laps (no thermal circling; lap 1 excluded as it holds the start dive) lap time = cruise time + turn time by construction, so the deficit splits additively. Paired per round (same air), then averaged. **Limit:** turn windows are anchored on official corner crossings, so any extra height/speed loss Bill takes mid-leg lands in the 'straight' bucket — the straight share is therefore an upper bound and absorbs general line/energy inefficiency, not only raw airspeed.

## 3. Lap-count gap — the climb/aloft story (separate from per-lap time)

Leaders average **3 more laps**. A counterfactual `laps=(1800-climb_time)/clean_lap_time` attributes this almost entirely to **racing pace** (pace effect 2.67 laps); the climb-*time* term is negative (-0.63 laps) because the leader actually spends MORE time circling. So Bill does not lose laps by thermalling too much. The climb cost is instead **qualitative**: banking ~35% less height and circling wider means less altitude to convert into speed, and Bill lands early in rounds [6, 9, 12, 13, 15] (catastrophically in R9=3 laps, R12=2 laps). Better climbs would show up as staying aloft the full window and as a higher sustainable cruise, i.e. they feed phases 1 and 2 rather than adding laps directly.

## 4. Phase cost ranking (biggest lever first)

1. **STRAIGHT / cruise speed — biggest lever.** ~90% of the 22 s/lap deficit and the dominant driver of the lap-count gap. An 8% cruise gain closes most of the per-lap deficit and adds laps.

2. **THERMAL CLIMBS (height banked / circle discipline) — second lever, drives lap COUNT.** Bill banks 35% less height, circles ~6 m wider, climbs slower. This is why he lands early and has less energy to sustain cruise. Affects score via laps, not per-lap time.

3. **START entry speed — modest, easy win.** 24 km/h below the leader and ~49 km/h under the 120 cap; costs a one-off ~few s on lap 1 and forfeits free energy. Cheap to fix (dive harder to the gate).

4. **TURNPOINT TURNS — smallest cost / near a strength.** Only ~10% of the per-lap deficit (~2 s/lap); Bill rounds 15 m wider per lap and scrubs a touch where leaders gain speed, but the absolute penalty is small.

**Where Bill matches or beats leaders (strengths):** R7 and R17 — lap-for-lap level with the leader (cruise and turns competitive); in several rounds (R2, R5, R9) Bill's cruise or aloft time equals or beats the leader. His turn technique and thermalling *duration discipline* are not the problem — raw cruise speed and height-per-climb are.

## Method & caveats

- **Corners = ground truth:** turnpoint turns are anchored on the official SECTOR A/B/C crossing events, not a bearing-rate guess, so corner timing is reliable.

- **Climb vs turn separation:** thermals are detected as sustained circling (>=12 s, >=270 deg cumulative heading, net-positive altitude) on the 1 Hz tail, explicitly excluding the corner windows. Bearing-rate segmentation still blends brief thermal snatches near corners into 'turn' and vice-versa; the duration/continuity gate mitigates this but does not eliminate it.

- **Small-sample noise:** low-lap rounds (R3, R9, R12) yield 0-2 clean laps and are down-weighted or dropped from the paired per-lap decomposition (rounds used are listed in §2). Climb metrics on 1-climb rounds are noisy.

- **Entry speed** uses the prior agent's gate-crossing `entry_speed_kmh` (comparable to the 120 cap); the raw dive-peak can exceed the cap and is not used for that comparison.

- **Lap count** is the official competition result (manifest); the track shows a few extra start-line crossings (lead-in / out-of-window) that do not affect per-lap timing.
