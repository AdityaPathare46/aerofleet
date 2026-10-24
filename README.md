# AeroFleet 2.0

**A ground-side assurance tool for drone fleets.** It checks a fleet's settings, plans and flight logs
before and after flying, lays out what a flight log shows for the person reviewing it, and keeps a
signed record of every result. It never controls a drone in flight, needs no drone hardware (it works
from uploaded files), and contains no language model: every check, number and verdict comes from
ordinary deterministic code.

> **Status, October 2026.** A student project re-scoped after an outside review. The features below are
> built and tested in software and have been run on real ArduPilot and PX4 logs. No drone operator has
> yet confirmed they need it. The plan and its open items are in
> [`docs/aerofleet2/MASTER_PLAN.md`](docs/aerofleet2/MASTER_PLAN.md); whoever continues should read
> [`docs/aerofleet2/CONTEXT.md`](docs/aerofleet2/CONTEXT.md) first.

## What it does

| Feature | The problem | What AeroFleet does |
|---|---|---|
| **Settings drift** | A failsafe or limit is changed in the field and forgotten | Compares a drone's settings with the fleet's approved baseline and its own last upload. Safety-critical changes block; flight-limit changes need review; an operator can approve an exact value with a reason |
| **Did it fly the plan?** | A compliant plan proves nothing if something else was flown | Compares a flight log (ArduPilot `.tlog` / `.bin`, PX4 `.ulg`) with the approved mission file: how far off route and off height, for how long, where; manual takeovers; time in a no-fly zone; settings changed during the flight |
| **Evidence timeline** | Finding out what happened means opening many plots | Puts the log's events in time order — mode changes (the pilot taking over from an automatic mode is flagged), safety settings changed in flight, low battery and voltage drops, poor GPS, the plan deviations — and lists what happened around each deviation. **It does not name a cause** (see below) |
| **Vibration across the fleet** | Problem airframes look normal flight by flight | Records each flight's vibration and ranks the fleet's drones against others measured the same way; drones above the group's upper quartile are flagged for inspection (mounting, propellers, motors). Not a crash prediction |
| **Something wrong? Describe it** | Operators repeat problems others have already solved | Type what the drone did ("circles in position mode", "wobbles after new props"). You get a checklist of checks and usual fixes in the order PX4 experts most often found each cause in 90 diagnosed crashes, the causes your words mention marked, the most similar past forum threads with links and the expert's cause, and the drone's place in the fleet vibration ranking. Word matching (BM25), no model. **Measured:** held out one case at a time, the cause best matched by the words was the expert's in 20% of cases, below the 32% of always answering the most frequent cause ([`troubleshoot_loo.md`](research/results/px4_log_study/troubleshoot_loo.md)), so the list follows expert frequency, not the words. Knowledge base: `aerofleet/assurance/data/fault_cases.json` (titles, links, labels, key terms; no forum text) |
| **Replay on the VR table** | A table of numbers is hard to picture | Shows a reviewed flight in 3D: the plan dashed, the flown track green within tolerance and red where it deviated, the events pinned where they happened, a playhead. In the app's VR view (desktop or Quest browser) and in the Quest app |
| **Will these missions conflict?** | Drones planned separately can cross at the same place and time | Checks mission files against each other and fixes conflicts with a launch delay or, if allowed, a different cruise height. **Rehearse in 3D** flies all the missions on one clock on the VR table, as planned and as rescheduled, with each loss of separation marked where and when it happens (straight legs at planned speeds, no wind: the plan, not a prediction) |
| **Battery for the wind aloft** | Wind at 100 m is often much stronger than at ground level | Fetches the forecast wind at cruise height and recomputes the mission's energy leg by leg |
| **Pre-flight check and mission file** | Paperwork and planning checks are scattered | DGCA zone, document and link checks for a planned route; a mission file is generated only if they pass. The UIN status comes from the drone registry; everything else the operator types is marked as operator-declared |
| **Signed record** | Reports can be edited afterwards | Every result gets an Ed25519-signed entry linked to the one before, carrying the SHA-256 of the exact files it came from. Each new head is also written to a separate heads file to copy off the machine. An auditor checks an export with `tools/verify_ledger.py`, which needs only Python and the `cryptography` package |

## What has been measured

Every number links to the script and the results file that produced it. Tests that decide something were
declared (rule, thresholds and pass mark committed) before they were run.

- **Can a log tell pilot error from an aircraft fault?** On public PX4 crash logs labelled by their
  uploaders, a fixed rule scored a balanced accuracy of 0.57 on 93 crashes and **0.47 on 112 held-out
  crashes** (0.50 is guessing), and flagged 39% of normal flights. Two signals seen in the first run did not
  hold up on the held-out set. This is why the product shows evidence and names no cause.
  [`research/results/px4_log_study/`](research/results/px4_log_study/)
- **Does the planned-versus-flown check catch what it should?** Known deviations were injected into 40 real PX4
  flights. After switching to whole-flight ordered alignment (the first version matched each position to the
  nearest leg anywhere and missed half of 35–50 m deviations on looping routes), it catches 90% of 35 m and 95% of
  50 m sideways deviations and 92–98% of 20 m height deviations, with 0 false alarms in 40 untouched flights when the
  plan has a waypoint every 5 s (22% with one every 10 s, from fast flights cutting long legs).
  [`injection_reconcile.md`](research/results/px4_log_study/injection_reconcile.md)
- **Which drones crash: the one useful signal.** Against matched drones with no recorded crash (same flight
  controller, firmware and vehicle type), drones that later crashed were already vibrating more on their ordinary
  flights (60 matched sets, mean rank 0.67, p = 0.002). But the flight that crashed was no rougher than the same
  drone's earlier flights (61 drones, 0.48, p = 0.67). Logs show which drones are at risk, not which flight will
  crash; that is what the fleet vibration ranking uses. The effect comes mostly from the older vibration
  estimate: a declared replication on the newer accelerometer metric (19 sets) was inconclusive (0.58, p = 0.25,
  [`rough_drone_newer.md`](research/results/px4_log_study/rough_drone_newer.md)). [`rough_drone.md`](research/results/px4_log_study/rough_drone.md),
  [`within_drone.md`](research/results/px4_log_study/within_drone.md), [`leak_curve.md`](research/results/px4_log_study/leak_curve.md)
- **Do crashed drones fly with different settings?** No: a protection was switched off (versus the firmware
  default) in 51% of crash logs and 46% of good ones (p = 0.63), and 0 of 100 crash logs changed a safety
  setting in flight. [`summary.md`](research/results/px4_log_study/summary.md)
- **What do experts say caused crashes?** In 148 PX4 forum crash threads with a reply from PX4 staff or an
  experienced member, the expert blamed the aircraft in 59%, the pilot in 6%, and was unclear in about a
  third; tuning/configuration was named most often. (Recorded with AI assistance and reviewed by the project
  owner; every quote was checked against the thread; the error rate is not yet measured.)
  [`forum_expert_labels.md`](research/results/px4_log_study/forum_expert_labels.md)
- **Do simple log checks find the fault the expert named?** Not reliably: once the last 10 s before the crash
  are excluded, a tuning check found 2 of 10 tuning-diagnosed crashes; only a vibration check stood out (3 of
  3, too few to rely on). [`test_flight_check_minus10s.md`](research/results/px4_log_study/test_flight_check_minus10s.md)
- **Small language models as reviewers.** On 60 generated cases, a plain no-AI rule was right 45 times and
  wrong 0 times. Four small local models (3–4B, the size an ordinary laptop runs) all lost to it as a
  five-reviewer panel; one compromised reviewer could change the panel's answer in 45 to 56 of the 60 cases.
  [`docs/aerofleet2/PANEL_EVAL_RUNBOOK.md`](docs/aerofleet2/PANEL_EVAL_RUNBOOK.md)
- **Wind aloft, Pune.** 720 hourly forecast values: median wind 2.2 m/s at 10 m and 3.5 m/s at 100 m. For a
  3 km out-and-back at 100 m with a 20% battery margin, 11.9% of flight-hours pass on the ground wind but
  fail on the wind aloft. [`research/results/wind_altitude_study.md`](research/results/wind_altitude_study.md)
- **Conflicts at scale.** Synthetic plans from six depots over ten minutes: delays alone clear every conflict
  at 10 missions; with 20 m of height separation, every conflict up to 50 and all but 0.3 of 100.
  [`research/results/deconflict_scale.md`](research/results/deconflict_scale.md)
- **Which settings are safety-critical.** The list was checked against the ArduPilot (5,799 settings) and
  PX4 (3,111) references. [`research/results/drift_catalogue_check.md`](research/results/drift_catalogue_check.md)
- **Need and competitors.** No accident dataset counts misconfiguration as a cause; the clearest written need
  is UK/EU record-keeping (a technical log per aircraft, kept 3 years, protected from alteration).
  [`reports/Drone fleet needs evidence.md`](reports/Drone%20fleet%20needs%20evidence.md),
  [`docs/aerofleet2/COMPETITOR_CHECK.md`](docs/aerofleet2/COMPETITOR_CHECK.md)

## Where AI is and is not used

Nowhere in the product. An AI "review panel" that would have suggested a likely cause was built and tested
(above); it lost to a plain rule and is kept only as research code (`aerofleet/assurance/review_panel.py`,
`research/panel_eval/`). The plain rule itself is not used either, because on real crash logs it could not
tell pilot from aircraft.

## What it does not do

- **It does not fly drones.** Commands from the earlier product are refused unless an administrator sets
  `AEROFLEET_LIVE_CONTROL=on`. Disarm and emergency stop always work.
- **It does not say why something went wrong.** It shows what the log recorded and when.
- **It does not guarantee separation or endurance.** The conflict fix holds only if drones launch on schedule
  and fly their plans; the wind check assumes constant airspeed and ignores climb, hover and gusts.
- **The signed record is tamper-evident, not tamper-proof.** See the threat model below.
- **Positions are only as good as the GPS.** Each review states its sample rate, GPS quality, height reference
  and clock; deviations under the fleet's tolerances (default 30 m sideways, 15 m height, operating choices rather
  than regulatory limits) are not reported.
- **The DGCA checklist citations are not verified** (each item says so), and a UIN in the registry is
  operator-entered: Digital Sky has no public lookup.

## Threat model for the signed record

| Who | Can they cheat? | What stops them |
|---|---|---|
| Someone editing a stored record later | No | Signatures and the hash chain; `tools/verify_ledger.py` names the entry |
| Someone swapping an uploaded file after the fact | No | Each record carries the file's SHA-256; compare with the original |
| A pilot editing a log **before** upload | **Yes** | Nothing in software can. Prefer logs taken straight from the aircraft; a log's own embedded settings are used where present |
| The operator, who holds the key and the database | **Yes, they can rebuild the whole chain** | Only a copy of the heads file (or the head hash and key fingerprint from `GET /ledger/head`) kept by someone else: a rebuilt chain no longer contains the old heads |
| Anyone, on timestamps | **Yes** | Times come from the server's clock; no trusted timestamping |
| A regulator or insurer | Unknown | No authority has endorsed this format; it is evidence support, not certification |

## Run it

```bash
./start.sh
```

That is all: it creates `.venv` and installs the Python packages the first time (a few minutes), starts the API,
installs and starts the app, and opens http://localhost:1420. Ctrl-C stops both; logs are in `logs/`.
`./start.sh api` starts only the API. Needs Python 3.10+ and Node 18+.

Open the app, sign in, and go to **Fleet Assurance**. Setting a baseline or approving a change needs an
operator account. API reference: `http://localhost:8000/docs` (`/api/v1/assurance`, `/api/v1/compliance`,
`/api/v1/missions`).

```bash
python -m pytest tests/unit/test_assurance_*.py tests/integration/test_assurance_*.py tests/integration/test_missions_compliance_api.py -q --no-cov
```

## VR

The app's **VR Safety View** runs on the desktop and in a Quest 3 browser (WebXR). From a flight review,
**Show on the VR table** opens the flight replay there, and **Rehearse in 3D** (after a conflict check) flies the planned missions on one clock before anyone takes off; a paired Quest app (`unity/AeroFleetVR`, project at
`/Volumes/UnityWork/UnityProjects/Aerofleet`) follows and shows the same replay. The flight replay in the
Quest app compiles but has not yet been run on a headset. The live-swarm view is from the
earlier product. Guide: [`docs/VR_QUEST3_GUIDE.md`](docs/VR_QUEST3_GUIDE.md).

## Repository

| Path | What is there |
|---|---|
| `aerofleet/assurance/` | The 2.0 code: `params`, `drift`, `static_checks`, `flightlog` (ArduPilot and PX4), `reconcile`, `evidence`, `vibration`, `deconflict`, `wind`, `ledger`, `report_html`, `live_control`; `review_panel` is research only |
| `aerofleet/api/routes/` | `assurance.py`, `compliance.py`, `missions.py`, `vr.py` |
| `tauri-app/src/pages/FleetAssurance.tsx`, `VRSafetyView.tsx` | The app screens |
| `unity/AeroFleetVR/` | Mirror of the Quest app's scripts |
| `research/` | Studies and their results; `px4_log_study/` is the crash-log benchmark, `panel_eval/` the AI-panel test |
| `docs/aerofleet2/` | Master plan, context for whoever continues, product definition, panel runbook, competitor check, pitch |
| `docs/paper/` | The research paper draft (manuscript, figures, build script) and where to submit it |
| `tests/` | `test_assurance_*`, `test_missions_compliance_api.py`, `test_vr_pairing_api.py` for 2.0; the rest covers the earlier product |

## The earlier product

AeroFleet began as an AI multi-agent drone *dispatch* system. That code — the 16-agent council, live
MAVLink control, the dispatch console and its other screens — is still here, hidden in the app behind
**Settings ▸ Show legacy screens** and off by default in the backend. Its README is kept at
[`docs/LEGACY_AI_DISPATCH_README.md`](docs/LEGACY_AI_DISPATCH_README.md).

## Licence

No licence file has been added to this repository yet, so no reuse terms are granted.
