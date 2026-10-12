# AeroFleet 2.0

**A ground-side pre-flight assurance tool for drone fleets.** It checks a fleet's settings, plans and
flight logs before and after flying. It never controls a drone in flight, needs no drone hardware (it
works from uploaded files), and every check and verdict comes from ordinary deterministic code — no
language model calculates, checks or approves anything.

> **Status, October 2026.** This is a student project re-scoped after an outside review. The five
> features below are built and tested in software. No drone operator has yet confirmed they need it,
> and nothing here has been validated on real-world flights — the logs it was tested on come from the
> real ArduPilot firmware flying in a simulator. The plan and its open items are in
> [`docs/aerofleet2/MASTER_PLAN.md`](docs/aerofleet2/MASTER_PLAN.md).

## What it does

| Feature | The problem | What AeroFleet does |
|---|---|---|
| **Settings drift** | A failsafe or limit is changed in the field and forgotten | Compares a drone's settings file with the fleet's approved baseline and its own last upload. Safety-critical changes block; flight-limit changes need review; an operator can approve an exact value with a reason |
| **Did it fly the plan?** | A compliant plan proves nothing if the pilot flew something else | Compares a flight log with the approved mission file: how far off route and off height, for how long, where; manual takeovers; time in a no-fly zone; **settings changed during the flight** |
| **Will these missions conflict?** | Drones planned separately can cross at the same place and time | Checks a set of mission files against each other and fixes conflicts with a launch delay or, if the fleet allows it, a different cruise height |
| **Battery for the wind aloft** | Wind at 100 m is often much stronger than at ground level | Fetches the forecast wind at cruise height and recomputes the mission's energy leg by leg |
| **Signed record** | Reports can be edited afterwards | Every result gets a signed entry linked to the one before; any later change is detectable with only the public key |

Also in the app: 59 flight-controller compliance checks run on a settings file (it says which ones it
could not answer without a live drone), and a VR table for looking at a fleet in 3D (see
[VR](#vr)).

## What has been measured

Every number links to the script and the results file that produced it.

- **Wind aloft, Pune.** 720 hourly forecast values over 30 days: median wind 2.2 m/s at 10 m and
  3.5 m/s at 100 m (ratio 1.58). For a 3 km out-and-back at 100 m with a 20% battery margin, **11.9%
  of flight-hours pass on the ground wind but fail on the wind aloft** (27.5% at a 10% margin, 5.7% at
  30%). Forecast-model values, one site, one month.
  [`research/results/wind_altitude_study.md`](research/results/wind_altitude_study.md)
- **Conflicts at scale.** Synthetic plans from six depots over ten minutes. Delays alone clear every
  conflict at 10 missions; allowing 20 m of height separation clears every conflict up to 50 and
  leaves 0.3 of 100 unresolved. About 3.4 s to fix 300 missions. Beyond that the depots saturate and
  the tool says which missions it could not clear.
  [`research/results/deconflict_scale.md`](research/results/deconflict_scale.md)
- **Which settings are safety-critical.** The list was checked against the official ArduPilot Copter
  (5,799 settings) and PX4 (3,111) references; 20 of my original 113 names had been renamed in current
  firmware and are now covered in both spellings.
  [`research/results/drift_catalogue_check.md`](research/results/drift_catalogue_check.md)
- **Real log files.** The reader was run on 5 real ArduCopter onboard logs and 2 telemetry logs. One
  shows the geofence switched on and its ceiling cut from 100 m to 50 m ten seconds into a flight, then
  restored a minute later — invisible in the final settings, listed by the flight review.
- **Hostile text in uploads.** 8 attack strings planted in 5 places an uploader controls: **0 of 40
  reached a language-model prompt**.
  [`research/results/panel_eval/injection_reach.md`](research/results/panel_eval/injection_reach.md)
- **Tests.** 99 automated tests cover the assurance code.

## Where AI is and is not used

Not used for any check, number or verdict. The one place a language model appears is an optional
**review panel** that suggests the *likely cause* of a finding the code has already made. Each
reviewer sees only numbered facts from its own area, must cite them, and a fixed counting rule
decides; disagreement goes to a person.

**It is not switched on in the app.** On the first 24 test cases a small local model (`llama3.2`)
named the right cause in 2, a wrong cause in 17, while a plain no-AI rule was right in 18 and wrong in
none. The panel will only be enabled if a model beats that rule; the test is packaged in
[`docs/aerofleet2/PANEL_EVAL_RUNBOOK.md`](docs/aerofleet2/PANEL_EVAL_RUNBOOK.md).

## What it does not do

- **It does not fly drones.** Arming, take-off and go-to commands from the earlier product are refused
  unless an administrator sets `AEROFLEET_LIVE_CONTROL=on`. Disarm and emergency stop always work.
- **It does not guarantee separation or endurance.** The conflict fix holds only if drones launch on
  schedule and fly their plans; the wind check assumes constant airspeed and ignores climb, hover and
  gusts. Both say so in their results.
- **The signed record is tamper-evident, not tamper-proof.** It shows whether a record was changed
  later. It does not prove the uploaded files were genuine.
- **PX4 flight logs are not read yet** (ArduPilot `.tlog` and `.bin` are).

## Run it

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn aerofleet.api.app:app --host 127.0.0.1 --port 8000     # API; first start takes a minute or two
npm install --prefix tauri-app && npm run dev --prefix tauri-app          # app at http://localhost:1420
```

Open the app, sign in, and go to **Fleet Assurance**. Setting a baseline or approving a change needs an
operator account. API reference: `http://localhost:8000/docs`, under `/api/v1/assurance`.

```bash
python -m pytest tests/unit/test_assurance_*.py tests/integration/test_assurance_*.py -q --no-cov
```

## VR

A Quest 3 / desktop app (`unity/AeroFleetVR`) shows a city, its no-fly zones and a fleet on a 3D
table, with inspection of a selected drone. It was built for the earlier product. Its 2.0 role —
rehearsing a fleet plan before and after the conflict fix, and replaying planned against flown — is
not built yet. Guide: [`docs/VR_QUEST3_GUIDE.md`](docs/VR_QUEST3_GUIDE.md).

## Repository

| Path | What is there |
|---|---|
| `aerofleet/assurance/` | The 2.0 code: `params`, `drift`, `static_checks`, `flightlog`, `reconcile`, `deconflict`, `wind`, `ledger`, `review_panel`, `live_control` |
| `aerofleet/api/routes/assurance.py` | The API for all of it |
| `tauri-app/src/pages/FleetAssurance.tsx` | The app screen |
| `research/` | Studies and their results; `research/panel_eval/` is the review-panel test |
| `docs/aerofleet2/` | Master plan, context for whoever continues, the product definition, the panel runbook |
| `tests/` | `test_assurance_*` for 2.0; the rest covers the earlier product |

## The earlier product

AeroFleet began as an AI multi-agent drone *dispatch* system. That code — the 16-agent council, live
MAVLink control, the dispatch console — is still here, hidden in the app behind **Settings ▸ Show
legacy screens** and off by default in the backend. Its README is kept at
[`docs/LEGACY_AI_DISPATCH_README.md`](docs/LEGACY_AI_DISPATCH_README.md).

## License

MIT — see [LICENSE](LICENSE).
