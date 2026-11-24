# AeroFleet 2.0

**The safety and records back office for agricultural drone fleets.**

Each morning AeroFleet tells a drone service provider which drones can fly today and why. Before a job it checks the
route against restricted airspace and the other planned flights. After flying it turns each drone's log into a signed,
time-ordered record, compares the flight with what a healthy flight of a similar drone looks like, and keeps the
history that maintenance, insurers and reporting need.

It is built on a study of **590 real crash logs from a 479,547-log public archive** (PX4 Flight Review), which tested
what flight logs can and cannot show. The answer shaped every design choice: logs cannot tell pilot error from an
aircraft fault, so AeroFleet **never names a cause**; it checks what can be checked by rule and shows the rest as
evidence. **Evidence, not verdicts.**

> **Status, November 2026.** A final-year BTech project (Department of Mechanical Engineering, COEP Technological
> University). Built and tested in software and run on real public PX4 and ArduPilot logs. No operator has used it on
> their own fleet yet. Walk-through: [`docs/DEMO.md`](docs/DEMO.md). Hard questions and answers:
> [`docs/VIVA.md`](docs/VIVA.md). Handover for whoever continues: [`docs/HANDOFF.md`](docs/HANDOFF.md).

---

## Who it is for, and why now

| | |
|---|---|
| **15,000 approved, about 500 delivered** | Namo Drone Didi (approved 29 November 2023, outlay Rs 1,261 crore for 2023-24 to 2025-26) set a target of 15,000 drones for women self-help groups, who rent crop-spraying and nano-fertiliser flights to farmers ([PIB](https://pib.gov.in/PressReleasePage.aspx?PRID=1980683)). By March 2026 the government reported 500 drones delivered under the scheme itself, and 1,094 given to women SHGs by lead fertiliser companies in all ([Ministry of Rural Development reply, March 2026](https://www.dord.gov.in/static/uploads/2026/03/9560d26d651fff5e66666c6a88a7aef7.pdf)). |
| **5 + 10 days of training** | Pilots are trained for 5 days to fly plus 10 days for applying nutrients and pesticides: new operators, not career pilots. [PIB](https://pib.gov.in/PressReleasePage.aspx?PRID=1980683) |
| **7 days to report** | The crop-protection drone SOP asks operators to submit spray monitoring data within seven days. [PIB](https://pib.gov.in/PressReleasePage.aspx?PRID=1783937) |
| **Mandatory insurance** | The Drone Rules 2021 require third-party insurance for every drone above nano class, so after an accident someone asks whose fault it was. [Drone Rules 2021](https://digitalsky.dgca.gov.in/assets/files/UasRules.pdf) |
| **26 of 94** | In our study, tuning or configuration was the cause PX4 experts named most often for aircraft-caused crashes. Settings are the first thing AeroFleet checks. |

A self-help group with one or two drones has no maintenance engineer and no fleet software, while new tools promise
to read a log and say who was to blame. AeroFleet gives them checks that need no expertise, and records that protect
the pilot. The checks themselves are general: any PX4 or ArduPilot fleet can use them.

## A day with AeroFleet

| When | Screen | What happens |
|---|---|---|
| Morning | **Today's fleet** | Every drone: *ready*, *check first* or *do not fly*, each reason written out with a button to its evidence |
| Planning | **Route check** | Each spraying route against red and yellow airspace, the 120 m limit and the other jobs |
| Evening | **Fleet Assurance ▸ Upload the day's logs** | All logs at once, each matched to its drone, reviewed, signed and compared with healthy flights |
| Within 7 days | **Spray register** | Each spraying flight's SOP Spray Monitoring Form, part-filled from its log, with the days left to submit it |
| After work on a drone | **Maintenance logbook** | Record the fix; AeroFleet compares the flights before and after |
| Weekly | **Fleet trends** | Flying hours, warnings per flight, drones drifting from what is expected; CSV operations log for reporting |
| Weekly | **Fleet Assurance ▸ Signed record** | Save a signed receipt and send it to someone outside your control |
| In the viva | **Proof** | The study's results recomputed live, the learned model's tests, and a tamper demonstration |

## What it does, screen by screen

### Today's fleet: the morning go / no-go

One row per drone. The verdict comes **only from fixed rules and recorded facts**:

- **Do not fly**: a safety-critical setting (failsafe, geofence, battery limit, ...) differs from the approved
  configuration and nobody approved it; or the drone has no UIN on record (the Drone Rules require one).
- **Check first**: a flight-limit setting changed; the UIN is not verified; the settings were never checked; or the
  last flight's log shows warnings (sensor data rejected by the autopilot, poor GPS, critical battery, a safety
  setting changed in flight, leaving the plan).
- **Ready**: none of these.

Vibration and the learned model are shown as **context and never change the verdict**: the study found vibration is
not a validated warning. Module: `aerofleet/assurance/readiness.py`.

The screen is in **English, Hindi and Marathi** (buttons at the top). Each reason comes from the API with a code, so the
wording changes and the rule does not; log warnings and setting names stay in English, as the autopilot writes them.
The translations have not yet been checked by native speakers, and the screen says so until they are
(`tauri-app/src/lib/readinessText.ts`, `REVIEWED`). A test checks that every reason the rules can give has all three.

### Spray register: the seven-day report

The crop-protection SOP (CIB&RC, 434th Registration Committee meeting, 30 November 2021, section 7) asks the operator
to submit its **Spray Monitoring Form** (Annexure-I) within **seven days** of spraying pesticide by drone. Every reviewed
flight gets that form, field for field (1-1 Date ... 7-3 Who was informed), plus two items from the SOP's pre-spray list
(the written notice to the Gram Panchayat and Agriculture Officer at least 24 h ahead, and no water source within 100 m).

- **Filled from the log**, and labelled so: date, start and end time, height above take-off, ground speed and, when
  most of the distance runs along one axis, the spray direction. The log does not know the crop, so the height is
  above take-off, not the canopy; the operator can correct any value and the form keeps both.
- **Copied** from the drone's previous form (sprayer type, maker, model, nozzles) and from the maintenance logbook
  (the date of last calibration).
- **Fixed checks that quote the SOP**: product past its expiry date, notice sent less than 24 h ahead, no protective
  clothing, water within 100 m, no UIN. The SOP says "appropriate" wind, temperature and height without numbers, so
  AeroFleet invents no threshold for them.
- **Deadline**: due = spraying date + 7 days; overdue, due soon, incomplete, complete, submitted. A test or survey
  flight can be set aside as *not a spray flight*. Every save, set-aside and submission is signed; once recorded as
  submitted the form is frozen. **Print** gives the Annexure-I layout, up to six flights side by side as on the
  paper form. AeroFleet does not send the form; it records when and how it was sent.

Module: `aerofleet/assurance/spray_form.py`; API `aerofleet/api/routes/spray.py`.

### Fleet Assurance: the records

| Feature | What AeroFleet does |
|---|---|
| **Settings drift** | Compares a drone's settings with the fleet's approved baseline and its own last upload. Safety-critical changes block, flight-limit changes need review; an operator approves an exact value with a written reason. Each safety-critical value also shows how often public PX4 flights use it ("8% use this value; most use 2") |
| **Flight review** | A log (PX4 `.ulg`, ArduPilot `.tlog` / `.bin`), with or without a mission file: events in time order (mode changes, the pilot taking over, battery, poor GPS, what the autopilot itself reported about its sensors, settings changed in flight), the quality of the evidence, and, with a plan, how far and how long it left the route. **No cause is named.** Printable report |
| **Compared with healthy flights** | The learned normal-flight model's expected range for vibration and battery drain, for a drone like this one flown like this, and whether the flight was below, inside or above it (see below) |
| **Evening batch upload** | Up to 60 logs at once. Each is matched to its drone by the flight controller's own id (PX4 `sys_uuid`) or, the first time, by a file name like `PX4-07_evening.ulg`. A log it cannot identify is never guessed onto a drone |
| **Vibration and history** | Each drone flight by flight, in the order flown (GPS time, not upload date), against its own earlier flights, against drones of the same kind in the fleet, and against 292 public PX4 flights of 141 vehicles that never crashed (works for a fleet of one). The last 10 s of each flight are left out so an impact cannot inflate it. Nothing is flagged |
| **Maintenance logbook** | Record work on a drone (propellers, motor, battery, calibration, ...), signed. AeroFleet compares the flights before and after: vibration and battery drain relative to what the model expects, with the caveat that a few flights cannot prove a fix |
| **Something wrong? Describe it** | A checklist ordered by how often PX4 experts found each cause in 96 diagnosed crashes, the causes your words mention, and the most similar past forum threads. Word matching (BM25), no model. Measured: its best guess matched the expert in 22% of cases, below the 27% of always guessing the most common cause, so it is not used as a diagnosis |
| **Will these missions conflict?** | Checks mission files against each other and fixes conflicts with a launch delay or a different height; *Rehearse in 3D* flies them on one clock |
| **Battery for the wind aloft** | Recomputes a mission's energy leg by leg with the forecast wind at cruise height |
| **Signed record** | Every baseline, approval, check, review and maintenance entry gets an Ed25519-signed entry linked to the one before, with the SHA-256 of the exact file it came from. *Export for an auditor*; `tools/verify_ledger.py` checks it with only Python and the `cryptography` package. *Save a receipt* gives a signed note of the newest entry for someone else to keep; *Check a receipt* (or `verify_ledger.py --receipt`) later shows whether the record was rebuilt since |

### Fleet trends: the season view

Flights and hours per week or month (months with warnings highlighted), warnings per flight, the share of flights
outside the learned range (about 10% are expected by chance), and a per-drone table. **Download CSV** gives one row
per flight (date, drone, UIN, minutes, distance, area of the outline flown, take-off point, warnings and the
fingerprint of its signed review): the record a spray report is filled from, not the official form.

### Route check: before the day's jobs

Planned missions (`.waypoints`) drawn over the airspace and checked: **clear**, **needs ATC permission** (yellow
zone), **not permitted** (red zone or above 120 m), or **not checked** (outside the supported cities), with the
planned flights that would cross each other. The zones are approximations from the Drone Rules 2021 distances
around known airports and military sites in Pune and Mumbai, **not the official Digital Sky map**, and the screen says
so. Five demo jobs show each outcome. Module: `aerofleet/assurance/airspace_check.py`.

### Drone register

Each drone's DGCA registration (UIN) and airworthiness checks. The optional bench inspection reads a flight
controller's settings over USB and runs its own pre-arm checks; it changes nothing, and the bench motor test is
blocked unless live control is switched on.

### VR Safety View

A reviewed flight replayed on a 3D table (plan against flown track, events where they happened) and planned
missions rehearsed on one clock, on the desktop or in a Quest 3 browser (WebXR). A paired Quest app is in
`unity/AeroFleetVR`. Not yet tested on a headset.

### Proof

Answers "how do we know?" live, on this computer:

1. **The study's results recomputed** from the committed data, each with the git commit that declared the test and
   the later commit that added its result (for example declared 17:28, result 17:40 on 20 October 2026).
2. **The learned model**: what it was trained on and every declared test, failures included.
3. **Five attacks on a copy of the signed record** (change a user, swap a result, delete an entry, re-sign with
   another key, edit a stored review): all caught, the real record untouched.
4. What the tool was measured to do, and what is checked automatically on every change.

## The learned normal-flight model

For an operator with one or two drones, "is this flight normal?" has no answer without something to compare with.
AeroFleet ships a model trained on **1,121 ordinary public PX4 flights of 401 vehicles** that gives the range of
vibration and battery voltage drain expected for a drone like this one (vehicle kind, flight controller, firmware)
flown like this (speed, height, manual flying, flight length, battery cells).

- **No crash labels.** It is trained on ordinary flights only, avoiding exactly what the study found unreliable.
- **Model:** scikit-learn `HistGradientBoostingRegressor`, quantile loss (5%, 50%, 95%), settings fixed in advance.
  Exported as trees and evaluated in plain Python in the app (matching scikit-learn to within 3e-14), so no
  machine-learning library is part of the product.
- **Context only.** It never changes a readiness verdict.

All tests were declared and pushed before training (`de4382a`); vehicles were held out (GroupKFold by vehicle):

| Test | Result | Pass mark | Outcome |
|---|---|---|---|
| Error of the middle estimate vs always guessing the median | 48% lower (vibration), 15% lower (battery) | at least 10% lower | Passed |
| Vibration score after injected motor faults (220 real RflyMAD flights) | rose in 60% of flights, p = 0.0005 | p < 0.025 | Passed, with caveats |
| Raw 5-95% range on unseen drones | held 72.7% and 73.3% of flights | 85-95% | **Failed** |
| Conformal calibration, declared after that failure (`76db013`) | 90.4% and 90.8% | 85-95% | Passed |

Caveats on the fault test: the shift is small (no flight crossed its range), sensor faults raised the score too and
fault-free flights fell at the same point in the flight, so part of the effect is the phase of flight. The model
responds to faults; it is not a fault detector. Model card:
[`research/results/normal_flight/model_card.md`](research/results/normal_flight/model_card.md). Scripts:
`research/normal_flight/train_eval.py`, `research/normal_flight/calibrate.py`.

## The study behind it

Every test that decides something was declared (rule, data, pass mark committed and pushed) before it ran. Scripts
and results: [`research/px4_log_study/`](research/px4_log_study/),
[`research/results/px4_log_study/`](research/results/px4_log_study/). Paper: [`docs/paper/`](docs/paper/).

- **Can a log tell pilot error from an aircraft fault?** No. A fixed rule declared in advance reached **0.47 balanced
  accuracy on 112 held-out crashes** (pass mark 0.70; chance is 0.50); trained models and a published log checker did
  no better. A blind independent relabelling agreed with the uploaders no better than chance.
- **Much apparent crash-detection skill came from how models were tested.** Across 32 evaluation settings, AUC fell
  by 0.21 [0.06, 0.34]; a re-implemented published fault detector fell from AUC 0.94 to 0.63 once whole days were
  held out.
- **Crash labels are shaky.** The usual tilt rule misses roughly 7-50% of crashes, depending on the rater, and
  pilot-rated logs show a crash-like tilt half as often as aircraft-rated ones.
- **No warning within a drone.** The flight that crashed vibrated no more than the same drone's earlier flights
  (mean rank 0.48, p = 0.67, 61 drones).
- **Rougher drones crashed more often, but not enough to screen on.** Later-crashed drones vibrated more than
  matched drones (mean rank 0.67, p = 0.0023 as declared; weaker under stricter tests), but a top-decile screen
  against 412 non-crash drones gave a lift of only 1.77 [1.00, 2.60].
- **Language-model review panels added errors.** On 97 real crash cases no panel beat a plain rule, and one
  compromised reviewer moved most verdicts.
- **What experts found.** In 148 PX4 forum crash threads, tuning or configuration was the cause named most often
  (26 of 94 aircraft-caused); a blind second coding agreed with kappa 0.81.

## How the tool itself was checked

| Check | Result |
|---|---|
| Automated tests | **715 pass** (`python -m pytest -q --no-cov tests/unit tests/integration`) |
| No AI in the decision path | A test follows every import from the product code and fails if it can reach an AI agent, the language-model panel or any ML library (`tests/unit/test_no_ai_in_decision_path.py`) |
| Numbers stay true | `docs/paper/check_numbers.py` checks key numbers in the paper and every number on the Overview page against the result files (30 of 30 agree) |
| Results recompute | The headline results are recomputed in a test and compared with the paper; each declaration predates its result (`tests/unit/test_evidence.py`) |
| Planned-versus-flown check | Deviations injected into 40 real PX4 flights: 36/40 sideways (35 m) and 39/40 upward (20 m) found; 0/40 false alarms with a waypoint every 5 s ([`injection_reconcile.md`](research/results/px4_log_study/injection_reconcile.md)) |
| Speed | 36 real PX4 logs of 0.9 to 92.8 MB: median 0.23 s per review; the 92.8 MB, 28-minute flight in 2.44 s ([`docs/measurements/review_speed.md`](docs/measurements/review_speed.md)) |
| Damaged files | Empty files, random bytes, a renamed mission file and a log cut off mid-flight get a clear message, never a crash |
| Tampering | Every attack on the Proof page is also an automated test |

## Where AI is and is not used

- **No language model, anywhere in the product.** The study tested language-model review panels and they added
  errors; they are kept only as research code (`aerofleet/assurance/review_panel.py`, `research/panel_eval/`), and the
  earlier prototype's AI workers start only if the server is run with `AEROFLEET_LEGACY_AI=1`.
- **One trained statistical model**, the normal-flight model above, gives context and never a decision.
- **Every verdict comes from fixed rules.**
- An AI assistant was used to write code and draft text; this is declared in the paper.

## What it does not do

- **It does not fly or command drones.** It reads files. Commands from the earlier product are refused unless
  `AEROFLEET_LIVE_CONTROL=on`; disarm and emergency stop always work.
- **It does not say why something went wrong.** It shows what the log recorded and when.
- **It does not predict crashes.** Neither vibration nor the learned model is a validated warning.
- **The airspace zones are not Digital Sky.** Check every route on Digital Sky before flight.
- **The signed record is tamper-evident, not tamper-proof** (below).
- **Positions are only as good as the GPS.** Each review states its sample rate, GPS quality, height reference and
  clock.
- **Not yet shown:** that operators find it useful, that it reduces crashes, or the false-alarm rate on real
  missions (the public archive holds only 6 distinct missions with their plans).

## Threat model for the signed record

| Who | Can they cheat? | What stops them |
|---|---|---|
| Someone editing a stored record later | No | Signatures and the hash chain; the check names the entry |
| Someone swapping an uploaded file after the fact | No | Each record carries the file's SHA-256 |
| A pilot editing a log **before** upload | **Yes** | Nothing in software can. Prefer logs taken straight from the aircraft |
| The operator, who holds the key and the database | **Yes, they can rebuild the whole chain** | A signed receipt (*Save a receipt*) or a copy of the heads file kept by someone else: a rebuilt chain no longer contains the entry it names. Only as strong as how often receipts go out |
| Anyone, on timestamps | **Yes** | Times come from the server's clock; no trusted timestamping |
| A regulator or insurer | Unknown | No authority has endorsed this format: evidence support, not certification |

## Run it

Needs Python 3.10+ and Node 18+.

```bash
AEROFLEET_VENV=~/.venvs/aerofleet ./start.sh
```

It creates the Python environment and installs packages the first time, starts the API (http://localhost:8000,
reference at `/docs`) and the app, and opens http://localhost:1420. Ctrl-C stops both; logs are in `logs/`. Sign in
(or create a local account) and the app opens on **Overview**. Setting a baseline or approving a change needs an
operator account.

Load the demo fleet (64 real public PX4 flights of 8 drones, demo registrations, a demo maintenance entry, a
`demo-settings` fleet and the route-check jobs):

```bash
AEROFLEET_PX4_DATA="/path/to/AeroFleet_px4_data" python tools/seed_demo_fleet.py --reset
```

Run the tests:

```bash
python -m pytest -q --no-cov tests/unit tests/integration
```

Retrain the normal-flight model (needs the downloaded public logs; about 30 minutes, mostly reading logs):

```bash
AEROFLEET_PX4_DATA="/path/to/AeroFleet_px4_data" python research/normal_flight/train_eval.py
python research/normal_flight/calibrate.py
```

## Repository

| Path | What is there |
|---|---|
| `aerofleet/assurance/` | **The product's logic**: `flightlog` (PX4 and ArduPilot readers), `params`, `drift`, `static_checks`, `reconcile`, `evidence` (timeline), `vibration`, `public_reference`, `normal_flight` (learned model evaluator), `readiness`, `maintenance`, `trends`, `operations_log`, `airspace_check`, `deconflict`, `wind`, `ledger`, `report_html`, `troubleshoot`; `data/` holds the model, the public reference and the forum knowledge base. `review_panel` is research only |
| `aerofleet/api/routes/assurance.py` | The product's HTTP endpoints (plus `evidence.py`, `compliance.py`, `fc_compliance.py`, `missions.py`, `vr.py`, `auth.py`) |
| `aerofleet/evidence.py` | The live recomputation behind the Proof page |
| `tauri-app/src/pages/` | The screens: `Overview`, `Readiness` (Today's fleet), `Trends`, `FleetAssurance`, `RouteCheck`, `HardwarePanel` (Drone register), `VRSafetyView`, `Proof`, `Settings`; numbers shown on the Overview live in `src/lib/studyFacts.ts` |
| `research/normal_flight/`, `research/results/normal_flight/` | Training, calibration, results and model card of the normal-flight model |
| `research/px4_log_study/`, `research/results/px4_log_study/` | The study: every declared test and its result |
| `research/panel_eval/`, `research/protocols/` | The language-model panel test; declared future studies |
| `tools/` | `seed_demo_fleet.py`, `build_public_reference.py`, `benchmark_review.py`, `verify_ledger.py` |
| `docs/` | `DEMO.md`, `VIVA.md`, `HANDOFF.md`, `measurements/`, `paper/` |
| `unity/AeroFleetVR/` | The Quest app's scripts |
| `tests/` | Unit and integration tests; `test_assurance_*`, `test_no_ai_in_decision_path.py`, `test_evidence.py` cover the product |

**Legacy code (the earlier AI dispatch prototype), kept because parts are still imported:** `aerofleet/` outside
`assurance/`, `api/`, `data/` and `utils/` (agents, council, dispatch, safety, swarm, city, fleet, ...),
`scenario_engine/`, `agent_memory/`, and the screens hidden behind **Settings ▸ Show legacy screens**. Do not build
on it.

## Licence

No licence file has been added to this repository yet, so no reuse terms are granted.
