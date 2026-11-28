# AeroFleet 2.0: complete project dossier for an external review

*Generated from the project repository on DOSSIER_DATE (commit DOSSIER_COMMIT). Part I is written for you, the reviewer.
Part II (the appendices) is copied from the repository's own files: every result write-up, every declared test with
its commit, the full research paper and supplement, the viva notes, the 27 Nov critical review, and the code inventory.
Personal names and contact details have been removed; "the team" means a two-person final-year student team, with a
faculty guide.*

---

## 0. What we are asking you to do

We are a two-person final-year B.Tech team (Robotics and AI specialisation, COEP Technological University, Pune, India).
Our project is **AeroFleet 2.0**: a research study of 590 real drone crash logs, and a software product built on what
that study found. The final review (viva, with a printed report) is on **1-5 December 2026**.

We want a **hard, specific, technical critique** and an honest readiness assessment, not encouragement. Please:

1. Find anything **wrong**: a claim not supported by the evidence below, a statistical mistake, a rule that is unsafe or
   misleading, a test whose design does not test what it says, a wrong statutory citation, or an inconsistency between
   two numbers.
2. Find what is **weak**: what an examiner (or a real drone operator, or an insurer, or a regulator) would attack first.
3. Check whether our complete critical-review remediation (C1/C2 in `fc73ec6` + H1-H5, M1-M5, and L2 on 28 Nov — see
   Appendix H, `docs/CRITICAL_REVIEW_2026-11-27.md`) leaves any remaining safety, security, statistical, or regulatory flaws.
4. Assess the project's **overall rating** across research rigour, safety/code engineering, product-domain fit, and
   viva defensibility.
5. Answer the specific questions in section 12.

Constraints you must respect: **no AI or language model may take part in any decision the product makes** (a hard rule
from our own study); every test is **declared before it runs** (rule, data, pass mark committed to git first) and every
result is reported, including failures; **no overclaiming**; no hardware beyond a laptop and a Meta Quest 3 headset;
no real operator data yet.

---

## 1. The project in one paragraph

AeroFleet 2.0 is an independent safety-assurance and regulatory-records platform for **small-to-mid Indian commercial
and institutional PX4 and ArduPilot drone fleets** — Drone-as-a-Service (DaaS) operators, RPTO training academies, and
Lead Fertiliser Company (LFC) / agricultural drone service aggregators — with an Indian agricultural spraying compliance
vertical built in (for example women's self-help groups under the Namo Drone Didi scheme: 15,000 drones approved, about
500 delivered under the scheme by March 2026 and 1,094 to SHGs in all, flown by pilots with 5 + 10 days of training).
Drones can fail quietly through changed settings or disabled failsafes; Indian law requires UIN registration, third-party
liability insurance, a Remote Pilot Certificate, 48-hour accident reporting on Digital Sky, and a seven-day CIB&RC
Annexure-I spray-monitoring report; after an accident someone asks *whose fault was it?* Meanwhile, many tools claim to
read a flight log and name the cause of a crash. **Our study tested that claim on 590 real crash logs and found that logs
cannot reliably tell pilot error from aircraft fault** (a rule declared in advance scored 0.47 balanced accuracy on 112
held-out crashes, where chance is 0.50). **AeroFleet** is what we built from that result: a ground-side records and
pre-flight assurance tool that never flies or commands a drone, **never names a cause** ("evidence, not verdicts"),
decides only with fixed rules, and keeps an Ed25519-signed, tamper-evident record with optional DigiCert-pinned RFC 3161
trusted timestamps.

---

## 2. Timeline and honesty notes

| When | What |
|---|---|
| Earlier semesters | A different project (an AI-agent system for space-mission design), then a pivot |
| Aug-Sep 2026 | AeroFleet 1: an AI-agent drone *delivery* dispatcher (LLM "council", live swarm, VR) |
| Oct 2026 | The crash-log study: declared tests on 590 crash logs (most commits 12-27 Oct) |
| Late Oct-Nov 2026 | Re-scope to AeroFleet 2.0, Indian commercial/agricultural use case, evidence-first |
| 17 Nov 2026 | Paper submitted to *Accident Analysis & Prevention* (Elsevier); no reviews yet |
| 20-27 Nov 2026 | Learned normal-flight model (H1-H6), spray register, Hindi/Marathi morning board, signed receipts, archive search (A1 failed), DJI CSV reader, ArduPilot SITL v1/v2 (8/8 × 3), FA1/FA2 false-alarm tests, VR study design, packaged Mac app |
| 27-28 Nov 2026 (Audit, domain-fit & critical-review fixes) | Safety-audit fixes (`dbc45d3`), `SA1+FA3` (`e9c4ebc`/`ffd0f27`), RFC 3161 TSA (`bb50242`), Indian airport airspace + spray acreage + simulated `pune-agri` fleet (`21def14`), DGCA compliance ledger + 48h accident record + fleet picker (`8928782`), critical review C1/C2 fixes (`fc73ec6`), and H1-H5 + M1-M5 + L2 remediation (Rule 30/8/14/31/44 citations, 60 m floor in 8-12 km airport band + Baramati, M1 subject/count ledger check, M2 simulated banners, M3 2 s smoothed groundspeed, M4 IST date & missing-insurance check) |

Honesty notes: the git history starts on 10 August 2026 (about 3.5 months; nearly all commits by one team member). Code
and text were written with help from AI coding assistants (Claude and Antigravity, recorded in commit co-author trailers
and to be disclosed in both paper and report). Code from AeroFleet 1 (about 4,000 lines of LLM agents and 8 hidden
screens) is still in the repository, switched off, and a static import test proves the product's decisions cannot reach
it. The `pune-agri` agricultural demo fleet is seeded from **simulated ArduPilot SITL** flights, not field sprayer logs.

---

## 3. The research study

**Paper:** *Evidence, not verdicts: what 590 public PX4 crash logs can and cannot tell a drone fleet operator.* Full
LaTeX in Appendix F, supplement in Appendix G.

**Data.** The public PX4 Flight Review archive index: 479,547 logs (442,929 from real hardware, 38,320 distinct
vehicles). 590 logs rated as crashes by their uploaders (402 "aircraft" fault, 188 "pilot"; 520 from real hardware, 70
simulator logs excluded, from 284 airframes). 21,112 logs rated good or great, of which 477 were selected as matched
comparison flights (same firmware, controller and airframe). 443 candidate PX4 forum crash threads, 161 with an expert
diagnosis, 148 describing a real crash (94 attributed to the aircraft, 9 to the pilot, 2 to both, 43 unclear). External
data: RflyMAD (real flights with motor and sensor faults injected in the firmware; 240 motor-fault, 197 sensor-fault,
51 fault-free).

**Method.** Every confirmatory test was declared (rule, data, pass mark) and committed to git before it ran; later
exploratory analyses are marked †. A script checks that the numbers in the paper match the result files.

### Figure 1: study flow (from the public index to each analysis)

The index splits into three streams: crash-rated logs (590), normal comparison flights (21,112 rated good/great; 477
selected), and forum threads (443 found; 161 diagnosed; 148 real crashes). Per question:

| Analysis | Candidate pool | Exclusions | Analysed |
|---|---|---|---|
| Q1 parameters | 100 crash, 477 normal | 43% of crash logs lack factory defaults | 57 crash, 113 normal |
| Q2 fixed rule | 205 crashes, 143 normal | none (93 development + 112 held out) | 205 crashes, 143 normal |
| Q2/Q3a leak curve | 205 crashes, 143 normal | 57 dropped (missing topics / window under 10 s) | 148 crash + 139 normal (m = 0 s); 89 + 124 (m = 30 s) |
| Q3b within-drone | 101 crashed drones | 34 dropped (single flight / window under 10 s) | 67 multi-flight drones (372 flights); 61 vibration, 46 tracking |
| Q3c between-drone | 66 matched sets (101 cases) | 6 sets dropped (unmatched sensor metric) | 60 vibration sets (124 controls); 47 rate-tracking sets |
| Q4 expert cases | 148 real crash threads | 105 logs unhosted or expired | 43 downloadable (38 aircraft, 5 pilot); 35 with fault categories |

### Headline results

| Question | Result | Status |
|---|---|---|
| Can a log tell pilot error from aircraft fault? | Declared rule: **0.47** balanced accuracy on 112 held-out crashes (pass mark 0.70, chance 0.50); models near chance, also on multicopters; a published log checker (FlightMD) no better | Declared; failed |
| Does evaluation design create apparent skill? | Across 32 settings, AUC fell by **0.21** [0.06, 0.34] (0.06 from grouping folds by vehicle); a re-implemented published fault detector (RflyMAD LeNet-5) fell from AUC **0.94 to 0.63** once whole days were held out | † exploratory |
| Does a drone warn before it crashes (within drone)? | Vibration mean scaled rank **0.48** [0.38, 0.58], p = 0.67, 61 drones: no | Declared |
| Do rougher drones crash more (between drones)? | Mean rank **0.67**, p = 0.0023 as declared; **p = 0.012** resampling airframes, **p = 0.076** with operator sites weighted equally: **suggestive** | Declared; dependence tests † |
| Can vibration pick drones to inspect? | Top-decile screen lift **1.77** [1.00, 2.60]: not shown to beat random inspection | † |
| Are crash labels reliable? | Blind independent relabelling agreed with uploaders no better than chance (κ = −0.10); the usual crash-moment tilt rule misses about 7-50% of crashes depending on the rater | † |
| What do experts blame? | Tuning or configuration **26 of 94** aircraft-caused crashes (forum coding agreement kappa 0.81) | Declared |
| Can word matching guess the cause? | Best guess matched the expert 22% (21 of 96), below 27% for always guessing the commonest cause | Declared |
| Do language-model review panels help? | On 97 crash cases none beat a plain rule; one compromised reviewer moved most verdicts (16-89 of 97) | Declared |

### Figure 2: the paper at a glance

(a) Apparent skill falls as evaluation gets stricter (AUC; for the last column, the FlightMD own-history value as mean
rank):

| Split | Our features, archive crashes | FlightMD (published, untrained) | Published LeNet-5 detector, RflyMAD |
|---|---|---|---|
| Usual split | 0.88 | 0.79 | 0.94 |
| Flights or vehicles held out | 0.83 | (not shown) | 0.92 |
| Strictest split | 0.67 | 0.72 | 0.63 (days held out) |
| Same aircraft's own history | 0.46 | 0.48 | (not applicable) |

(b) No attribution test reaches the pass mark (balanced accuracy, pilot vs aircraft, 95% intervals; pass mark 0.70,
chance 0.50): rule on uploader labels (held out) 0.47; rule on multicopters (held out) 0.43 [0.33, 0.54]; rule against
independent relabelling 0.55 [0.42, 0.66]; rule against expert diagnoses 0.38 [0.25, 0.61]; FlightMD verdict 0.52
[0.44, 0.61].

### Figure 3: within-drone and between-drone comparison (mean scaled rank of the crashed drone, 95% bootstrap CI)

| Comparison | Mean rank | 95% CI | n |
|---|---|---|---|
| Vibration vs the same drone's earlier flights | 0.48 | 0.38-0.58 | 61 |
| Rate-tracking error vs the same drone's earlier flights | 0.50 | 0.38-0.63 | 46 |
| Vibration vs matched drones that did not crash | 0.67 | 0.56-0.77 | 60 |
| Rate-tracking error vs matched drones | 0.57 | 0.44-0.70 | 47 |

### Figure 4: robustness of the between-drone vibration result (mean scaled rank; 0.5 = no difference)

| Variant | Mean rank | n | p |
|---|---|---|---|
| Declared test (all controls, all sources) | 0.67 | 60 | 0.002 |
| S1 controls with the same airframe | 0.69 | 39 | 0.008 |
| S2 no case flights from the crash day | 0.76 | 25 | 0.003 |
| S3 older-firmware estimator metric only | 0.68 | 48 | 0.005 |
| S3 newer accelerometer metric (exploratory subset) | 0.62 | 12 | 0.191 |
| S8 vibration adjusted for flight duration | 0.69 | 57 | < 0.001 |
| Newer accelerometer metric replication (all usable) | 0.58 | 19 | 0.251 |
| Newer accelerometer metric replication (new cases only) | 0.50 | 10 | 0.576 |

### Figure 5: leakage curve (cross-validated ROC AUC as the analysis window ends further before the crash moment)

| Seconds removed before the crash | 0 | 2 | 5 | 10 | 20 | 30 |
|---|---|---|---|---|---|---|
| Crash vs normal (n = 213) | 0.895 | 0.876 | 0.873 | 0.868 | 0.862 | 0.864 |
| Pilot vs aircraft (n = 89) | 0.45 | 0.45 | 0.45 | 0.45 | 0.46 | 0.46 |

Crash vs normal stays high (mostly differences between aircraft, not the crash); pilot vs aircraft stays at or below
chance whatever is removed.

### Figure 6: how often each aircraft-fault sign fired (share of logs, %; read from the figure, about ±0.5)

| Sign | Aircraft-caused crashes | Pilot-caused crashes | Normal flights |
|---|---|---|---|
| Battery warning | 15.1 | 18.4 | 2.8 |
| Motor output at 95% or more | 22.5 | 28.9 | 1.4 |
| Accelerometer clipping | 24.1 | 8.3 | 14.6 |
| Poor GPS | 3.3 | 5.4 | 1.4 |
| Error message | 19.2 | 10.3 | 20.3 |
| Failsafe | 17.8 | 7.7 | 13.3 |

Several "aircraft-fault" signs fire as often or more in pilot-caused crashes, which is why a sign-based rule cannot
attribute blame.

### Figure 7: causes named by PX4 experts in forum crash threads (aircraft-fault diagnoses)

| Cause | All diagnoses (n = 94) | Confirmed by the original poster (n = 47) |
|---|---|---|
| Tuning / configuration | 26 | 14 |
| GPS / compass / estimator | 18 | 6 |
| Motor / ESC / propeller | 16 | 9 |
| Software / firmware bug | 14 | 8 |
| Vibration / mounting | 9 | 5 |
| Airframe / mechanical | 5 | 2 |
| Battery / power | 4 | 3 |
| Radio or data link | 2 | 0 |

### What the study means for the product (finding → design decision)

| Finding | Design decision |
|---|---|
| Logs cannot separate pilot error from aircraft fault | The tool never names a cause; it shows a timeline and how good the evidence is |
| Tuning/configuration is the commonest expert-named cause | Settings drift is the first check; safety-critical changes block until approved with a reason |
| No within-drone warning; between-drone signal weak; screen lift 1.77 | Vibration and the learned model are context only, never a verdict |
| LLM review panels added errors; one compromised reviewer moved most verdicts | No language model anywhere in the decision path (a static import test enforces it) |
| Crash labels unreliable; detectors looked better than they were | The learned model is trained on ordinary flights only, with declared tests |
| Word matching guessed the cause worse than the base rate | "Describe it" is a checklist ordered by expert frequency, never a diagnosis |
| After an accident someone asks whose fault it was | Ed25519-signed, hash-chained record with DigiCert-pinned RFC 3161 receipts and printable 48h accident dossier |

---

## 4. The product: architecture

- **Desktop app**: Tauri (Rust shell) + React/TypeScript front end (11 screens in 2.0, strict `tsc --noEmit` clean), with
  a shared 1-click `<FleetPicker />` across Today's fleet, Spray register, and Fleet trends.
- **Local API**: Python FastAPI + SQLAlchemy over SQLite, on the operator's own computer. Nothing leaves the machine
  unless the user explicitly requests a wind forecast (Open-Meteo) or an optional RFC 3161 receipt timestamp (32-byte
  SHA-256 hash only, sent to allow-listed DigiCert).
- **Assurance core**: `aerofleet/assurance/` (~4,500 lines): log readers, readiness rules, settings drift,
  planned-vs-flown reconciliation, evidence timeline, signed ledger, RFC 3161 TSA client/verifier + pinned DigiCert
  Trusted Root G4 (`data/tsa_roots.pem`), spray form + swath area estimator, DGCA 48-hour accident dossier generator
  (`accident_report.py`), normal-flight model evaluator, airspace check (Pune/Mumbai + 36 Indian civil airports),
  deconfliction, wind (decoupled from legacy dispatch, with sprayer/survey airframe profiles), maintenance + grounding,
  trends + service intervals, archive search.
- **No ML library and no LLM** in the decision path; the one trained model is exported to JSON and evaluated in plain
  Python. `tests/unit/test_no_ai_in_decision_path.py` follows every import from all 2.0 product routes (including
  `spray.py` and `vr_study.py`) and assurance modules and fails if it reaches any AI agent, LLM panel, or ML library.
- **License**: MIT (`LICENSE` at repository root).
- **Tests**: **774 unit and integration tests** passing (`pytest tests/unit tests/integration`); TypeScript strict
  typecheck clean; 30/30 paper-to-code number checks agree.
- **Packaging**: the macOS app builds and starts its own backend (it still needs the project folder and its Python
  environment on the same machine).

**Flight review data flow**: upload → `read_flight_log` (format by extension) → `reconcile` with the mission if given,
otherwise log-only → `evidence.timeline` (events) → vibration value, normal-flight expected range (context) → stored as
a `FlightReview` → `ledger.append` (Ed25519-signed) → Today's fleet reads the latest review, settings, maintenance
grounding, UIN, and DGCA compliance metadata.

---

## 5. The product: every rule, with its exact numbers

### 5.1 Logs read

| Log | How | What is available |
|---|---|---|
| PX4 `.ulg` | pyulog, full | settings, modes, battery, GPS, vibration (estimator or IMU metric), estimator test ratios (compass, velocity, position, height), estimator faults, failsafe flag, commanded thrust, hardware, firmware, vehicle id, GPS time |
| ArduPilot `.bin` | pymavlink, full | settings (and changes in flight), modes, battery, GPS, vibration (VIBE), plus autopilot health: ERR reports (subsystem and code, including EKF3 primary core switches subsys 24), per-compass health (MAG), EKF3 test ratios (XKF4), tilt (ATT), motor outputs (RCOU) |
| ArduPilot / MAVLink `.tlog` | pymavlink | position, modes, battery, GPS, settings, vibration |
| `.csv` export | columns found by name; feet → metres; epoch in s/ms/µs/ns; DJI "1m 5.3s" text | position, time, battery, satellites, mode. Tested on 3 real public DJI Mini 4 Pro flight-record exports; Airdata layout untested on a real file |
| `.gpx` track | XML | position and time only |

Only numbers are read, never the free-text messages in logs.

### 5.2 Evidence timeline (`aerofleet/assurance/evidence.py`)

- Flight-mode changes (a "pilot took control" notice when an automatic mode switches to a pilot mode).
- Safety-critical setting changed in flight: warning; flight-limit setting changed: notice.
- Battery below 20%: notice; **mid-air below 10% (`> 15 s` before touchdown)**: warning (`in_flight=True`); **landing
  below 10% (`≤ 15 s` before touchdown)**: pilot note, not a readiness reason; voltage fell > 25%: notice.
- Poor GPS (fewer than 6 satellites, no 3D fix, or HDOP above 2.5) for 2 s or more.
- Autopilot health reports for 1 s or more (PX4 estimator rejections, faults, failsafe; ArduPilot items above).
- **Warning vs notice**: a GPS or health complaint is a *warning* only for the part overlapping a contiguous airborne
  span (`alt > 2.0 m` **or** smoothed horizontal ground speed `≥ 1.5 m/s` measured over a sliding `≥ 2.0 s` window so
  parked 5-10 Hz GPS jitter does not trigger airborne — M3) lasting at least **3 s**; an ArduPilot ERR report counts if
  it occurs while airborne; otherwise it is listed as a *notice*.
- Plan deviations: off the planned route (beyond 30 m), off the planned height (beyond 15 m), inside a no-fly zone, each
  for at least 3 s.

### 5.3 Settings drift (`drift.py`)

Curated catalogue, checked against the official ArduPilot Copter and PX4 parameter lists (ArduPilot: 5,799 documented
parameters; 219 CRITICAL, 215 HIGH, 393 TUNING, 4,888 INFO, 84 IGNORED).

- **CRITICAL**: failsafes, battery failsafes, geofence, arming checks, RTL altitude, PX4 circuit breakers. An
  unapproved change against the approved baseline **blocks**.
- **HIGH**: flight envelope and airframe definition. Needs review.
- **TUNING**: gains and estimator settings; reported only. **IGNORED**: values the autopilot rewrites itself.

An operator approves an exact value with a written reason, and the approval is signed.

### 5.4 Today's fleet (`readiness.py`): the morning go / no-go

| Verdict | When |
|---|---|
| **Do not fly** | an unapproved safety-critical setting change; no UIN on record; drone grounded in maintenance logbook after a reported incident/crash without a subsequent clearance; expired third-party insurance (when recorded); expired assigned pilot RPC (when recorded) |
| **Check first** | a flight-limit change; settings not yet compared against an approved baseline (`NO_REFERENCE`); **a failsafe or safety check switched off** (ArduPilot: low/critical battery failsafe, RC-loss failsafe, EKF failsafe, geofence, `ARMING_CHECK=0`; PX4: `NAV_RCL_ACT=0`, `COM_LOW_BAT_ACT=0`, `GF_ACTION=0`, `CBRK_SUPPLY_CHK=894281`); an unverified UIN; third-party insurance expiring within 14 days; settings never checked; last flight from a partial CSV/GPX export; or an in-air warning / route deviation / mid-air critical parameter change on the last flight (5.2) |
| **Ready** | none of these |

- **Non-blocking context & notes**: low-battery landing (`pilot_notes`), PX4 firmware-default safety-switch bypass
  `CBRK_IO_SAFETY=22027` (`setting_notes`, fixed under C1; `CBRK_FLIGHTTERM` is not checked at all), overdue 7-day
  spray forms (amber link button to Spray register), vibration, and the learned normal-flight model never change the
  verdict.
- **Languages**: English, Hindi, and Marathi (`readinessText.ts`). All 16 reason codes and UI labels have verified key
  parity across all three languages (`test_readiness_translations.py`). `REVIEWED` was set to `true` after a team
  self-review on 27 Nov 2026 (see section 9 H3: independent outside reader per language still recommended).

### 5.5 Planned vs flown (`reconcile.py`)

Mission file (`.waypoints`) compared with the flown track in flying order (shadowing bug in `ordered=False` fixed in
`dbc45d3`); defaults 30 m sideways, 15 m height, at least 3 s. Reports episodes, furthest deviation, and events around
each episode.

### 5.6 Route check (`airspace_check.py`)

India's Drone Rules 2021 / MoCA Airspace Map (24 Sep 2021) zones, approximated from public distances:
- **Pune & Mumbai**: full local approximations (airports + military/cantonment/strategic sites).
- **Rest of India**: **37 civil airports** (including Maharashtra farming-district aerodromes such as Baramati) with a
  documented **1.5 km perimeter allowance** around each airport reference point: **0-5 km RED** (all heights),
  **5-8 km YELLOW** (all heights), and **8-12 km YELLOW above 60 m / 200 ft only** (so 4 m agricultural spraying passes
  in the 8-12 km band are not over-restricted — H5). Routes outside airport zones return **`UNCHECKED`** (never
  `CLEAR`), with a banner instructing verification on Digital Sky.
- Also checks the 120 m green-zone height limit and multi-mission conflicts.

### 5.7 Spray register (`spray_form.py`)

The crop-protection SOP (CIB&RC 434th Registration Committee meeting, 30 Nov 2021, section 7) requires the Spray
Monitoring Form (Annexure-I) within seven days of pesticide spraying by drone. Each flight gets the form field for
field (1-1 Date ... 7-3 Who was informed) plus two SOP pre-spray items (24 h written notice to the Gram Panchayat and
Agriculture Officer; no water source within 100 m). Filled from the log: date, start/end time, height above take-off
(median in the air), ground speed (median when moving), spray direction (axial mean of track bearings when ≥ 60% of
distance lies along one axis), and **geometric swath area estimate** (moving airborne distance × track spacing `5-13`,
reported in **acres and hectares** in the table, printable Annexure-I, and CSV — explicitly labelled as including turns
with no flow sensor). Copied from the drone's previous form: sprayer type, maker, model, nozzles. From the maintenance
logbook: last calibration. Checks citing the SOP: product past expiry, notice under 24 h, no protective clothing, water
within 100 m, no UIN; entered height or speed differing from the log is noted. No thresholds for wind, temperature or
height, because the SOP gives none. Overdue 7-day forms also surface as a non-blocking jump link on Today's fleet.

### 5.8 Signed record (`ledger.py` & `tsa.py`)

Each entry: sequence number, kind, subject, SHA-256 of the payload (and of the exact input file), previous entry's
hash, timestamp, user; the entry hash is signed with Ed25519. Every committed head is also appended to a heads file.
`GET /ledger/verify` verifies the Ed25519 chain and cross-checks stored `FlightReview` and `SprayForm` rows against the
ledger's payload hashes (see section 9 M1 for remaining swap/deletion hardening).
- **Receipts & RFC 3161 trusted timestamps**: `GET /ledger/receipt?tsa=true` sends **only the 32-byte SHA-256 digest**
  of the receipt to allow-listed DigiCert (`http://timestamp.digicert.com`), embeds the CMS `TimeStampResp`, and
  `tsa.py` verifies messageImprint, nonce, CMS signature, content-type (`id-ct-TSTInfo`), ESS `signingCertificate`/v2,
  signer match by issuer + serial, `id-kp-timeStamping` EKU, validity at `genTime`, and chain to the **pinned root**
  `aerofleet/assurance/data/tsa_roots.pem` (DigiCert Trusted Root G4). A token from a self-made CA is rejected both
  offline and through `/ledger/check-receipt` (C2 fixed in `fc73ec6`, live-verified against DigiCert).
- `tools/verify_ledger.py` checks exports, receipts, and TSA tokens independently with Python + `cryptography`.
- `tools/backup.py` makes a consistent copy of the database and keys and verifies the record in the copy.

### 5.9 Other features

- **DGCA compliance & 48-hour accident record (G.S.R. 589(E))**: `DroneCompliance` table (`GET/PUT /drones/{id}/compliance`,
  signed) stores Rule 44 third-party insurance, Rule 8 Type Certificate/DAN, and Rule 31 assigned pilot RPC inside
  `Drone register` (checked against **IST date**; missing insurance on a compliance record flags `CHECK_FIRST`, expired
  insurance/RPC grounds to `DO_NOT_FLY`). `accident_report.py` (`GET .../accident-dossier` HTML & `.json`) generates an
  operator-prepared print-to-PDF **Accident Record for Digital Sky (Rule 30)** with a 48-hour IST/UTC filing countdown,
  telemetry timeline (no blame), maintenance history, simulated-fleet banner when applicable, and Ed25519 verification
  block.
- **Vibration history**: each drone flight by flight in GPS-time order against its own earlier flights, comparable fleet
  drones, and 292 public PX4 flights of 141 never-crashed vehicles; last 10 s left out.
- **Maintenance logbook**: work recorded and signed (including `"Incident / crash reported (grounded for inspection)"`
  and `"Post-incident inspection cleared"`); flights before/after compared relative to model expectation.
- **Fleet trends**: flights and hours per week/month, warnings per flight, **flights & hours since last maintenance**
  per drone, per-drone trends, operations-log CSV.
- **Wind & battery margin (`wind.py`)**: decoupled from legacy delivery dispatcher, with realistic airframe presets
  (`agri_sprayer_10l`, `agri_sprayer_16l`, `light_survey`, `light_multirotor`) and custom power/speed inputs plus
  low-altitude (`≤ 10 m`) wind-shear note.
- **Describe it & Public-archive search**: expert-frequency checklist + BM25 over 14,259 public descriptions + log-sign
  matching over 2,521 local public logs (word-to-log matching failed A1 and was removed).
- **Mission deconfliction**, **Drone register** (UIN + DGCA compliance + 59 FC compliance rules), **VR Safety View**
  (3D tabletop flight replay & mission rehearsal in desktop/Quest 3 WebXR), and **Proof screen** (recomputes 4 headline
  results live + 5 tamper attacks on a copy).

---

## 6. The learned normal-flight model

**Purpose**: give a small operator something to compare a flight with: the 5th-95th percentile range of **vibration**
and **battery voltage drop (% per minute)** for a healthy flight of a similar drone flown in a similar way. Context
only; never a verdict; not a crash predictor.

**Data**: 1,121 ordinary public PX4 flights of 401 vehicles (excluded: 589 crash/unsatisfactory ratings; 154 demo-fleet
vehicle flights; 320 over 10 per vehicle; 1,071 unreadable, not PX4 or under 60 s; 24 cut short). No crash labels.

**Inputs**: vibration source, vehicle kind, flight-controller hardware (15 most common), firmware, minutes, ground
speed, median and maximum height, share of pilot-controlled time, battery cells, starting volts per cell (battery
target). **Targets**: vibration p95 over the flight minus the last 10 s (log scale); battery voltage drop % per minute.

**Model**: scikit-learn HistGradientBoostingRegressor, quantile loss, one model per target and quantile (5%, 50%, 95%);
300 iterations, learning rate 0.05, 15 leaves, at least 20 per leaf, L2 1.0, seed 0; fixed in advance. Exported trees
reproduce scikit-learn within 3e-14.

| Test (vehicles held out, GroupKFold 5) | Result | Pass mark | Outcome |
|---|---|---|---|
| H1 raw 5-95% range coverage | 72.7% vibration, 73.3% battery | 85-95% | **Failed** |
| H2 middle estimate vs always-median | 47.6% / 15.4% lower error | ≥ 10% lower | Passed |
| H3 vibration score after injected motor faults (RflyMAD, 220 flights) | rose in 60% of flights, p = 0.0005 | p < 0.025 | Passed, with caveats (phase of flight) |
| H4† conformal calibration (nested) | 90.4% / 90.8% | 85-95% | Passed (fixed-wing vibration 84.8%) |
| H5 add measured loading (commanded thrust) | battery error 6.2% lower (0.826 → 0.775); vibration −0.3% | ≥ 10% lower | **Failed**; model not changed |
| H6 coverage with loading | 91.4% / 90.9% | 85-95% | Passed (not sufficient to ship) |

Limits: PX4 only; not trained on spraying drones (archive holds ~20 flights from 4 vehicles mentioning spraying, no
payload logged); ranges ~1.5× wider after calibration; usefulness for a decision never tested.

---

## 7. Demonstration fleets

Two seeded fleets serve distinct demonstration roles (1-click switchable via `<FleetPicker />`):

1. **`pune-agri` (simulated ArduPilot SITL spraying fleet — default view):** 6 drones (`AGRI-01`..`AGRI-06`) seeded from
   ArduCopter SITL v2 4 m spraying `.bin` logs and paired `.waypoints` plans near Pune, with a shared approved baseline,
   reconciled tracks playable in 3D/VR, DEMO UINs/insurance/RPCs, live Nov 2026 spray forms totaling **5.61 acres**
   (2.275 ha), and every readiness state (`AGRI-01/02` Ready; `AGRI-06` Check first for unverified UIN, insurance
   expiring in 9 days, and compass unhealthy 110 s; `AGRI-03` Do not fly for failsafes off + 3 SOP spray problems;
   `AGRI-04` Do not fly for mid-flight geofence disable; `AGRI-05` Do not fly grounded after motor failure with a live
   48-hour accident dossier). *Note (M2): screens must explicitly label this fleet as simulated (ArduPilot SITL).*
2. **`demo` & `demo-settings` (real public PX4 study evidence):** 64 real public PX4 flights of 8 unrelated airframes
   (each with one crash-rated flight and earlier flights, no shared baseline — un-baselined drones now show `Check first`
   rather than silently passing as `Ready`), DEMO registrations, one maintenance entry (`PX4-06`), four DEMO spray forms,
   and `demo-settings` showing a blocked RC-loss failsafe (`NAV_RCL_ACT` 2 → 0).

---

## 8. Verification of the product (all declared before running unless marked)

### 8.1 Planned-vs-flown on 40 real flights with injected deviations

| Version | False alarms | Sideways 35 m | Sideways 50 m | Upward 20 m |
|---|---|---|---|---|
| Nearest leg anywhere (first version) | 16/40 | 20/40 | 23/40 | 39/40 |
| Greedy order (rejected) | 32/40 | 39/40 | 39/40 | 35/40 |
| Whole-flight ordered alignment, waypoint every 10 s | 9/40 | 36/40 | 38/40 | 37/40 |
| Same, waypoint every 5 s | **0/40** | 36/40 | 38/40 | 39/40 |

### 8.2 Speed and robustness

36 real PX4 logs of 0.9-92.8 MB: median 0.23 s per review, largest (28 min) 2.44 s. Empty, random, renamed and
truncated files get a clear message. Five tamper attacks on a copy of the record are all caught.

### 8.3 Real autopilot firmware (ArduPilot SITL, ArduCopter master 3d6ebed)

A spraying-style mission (passes 8 m apart at 4 m over an 80 × 40 m field near Pune), 8 scenarios × 3 runs.

| Scenario | v1 (as first built) | v2 retest after fixes, fresh flights on new fields |
|---|---|---|
| S0 normal | met 3/3 (no false alarm) | met 3/3 |
| S1 throttle and battery failsafes off | **not met 0/3** (battery failsafe off by ArduPilot default; throttle failsafe caught) | met 3/3 (both named; failsafe-off rule) |
| S2 GPS lost 20 s | met 3/3 | met 3/3 |
| S3 battery low | met 3/3 | met 3/3 |
| S4 geofence switched off in flight | met 3/3 | met 3/3 |
| S5 8 m/s wind | met 3/3 (max sideways 0.9-1.5 m) | met 3/3 |
| S6 motor failure | not shown (descriptive) | met 3/3 (autopilot thrust-loss report, motor saturation) |
| S7 compass failure | not shown (known gap) | met 3/3 (compass 1 unhealthy, autopilot compass report) |

### 8.4 False alarms and sensitivity of Today's fleet (FA1, FA2, and SA1+FA3)

- **FA1** (declared `5f44b0b`): 1,121 ordinary flights; pass mark ≤ 20% of good-or-great flights. Result: **28.8%**
  [23.9, 34.1%] of 299 good-or-great flights, 40.7% of all; **failed**.
- **FA2** (declared `481987a`): rule revised on development half D only (airborne > 2 m, ≥ 3 s, landing battery as
  pilot note), tested on untouched held-out half H: **11.1%** [7.3, 16.3%] of 190 good-or-great flights, 19.8% of all
  572; **passed**.
- **SA1 + FA3** (`e9c4ebc` / `ffd0f27`, after adding `speed ≥ 1.5 m/s` airborne spans and mid-air `< 10%` battery):
  - **FA3 (re-measured on H, NOT an independent held-out test — see H1):** good-or-great **14.2%** (27/190; flight
    Wilson [10.0, 19.9%], **vehicle-cluster 95% CI [8.5, 20.7%]**, 20/55 vehicles; upper bound crosses 20%); all H
    ordinary **27.3%** (unrated 33.8%).
  - **SA1 (descriptive — see H2, RflyMAD 53.8% was already observed during D development):** RflyMAD injected sensor
    faults **53.8%** (106/197), fault-free control **0.0%** (0/50), motor faults **19.8%** (48/242); forum expert
    aircraft crashes **37.5%** (12/32; pilot crashes 2/4); archive real-hardware crashes **36.8%** (49/133) vs crashed
    drones' *prior* ordinary flights **26.5%** (118/445) — virtually identical to ordinary H (27.3%), showing the board
    flags crash flights ~1.35× as often as normal flights and confirms the within-drone null on the product itself.
- **Settings-rule check on 200 random public PX4 logs (C1, 27 Nov):** before C1 fix, `CBRK_FLIGHTTERM` (199/200) and
  `CBRK_IO_SAFETY` (142/200) flagged **199/200** stock PX4 drones. After dropping `CBRK_FLIGHTTERM` and moving
  `CBRK_IO_SAFETY` to a setting note (`fc73ec6`), **152/200** flag — of which **145** are `COM_LOW_BAT_ACT = 0`
  (warning-only battery default, intentionally kept to match ArduPilot), 32 `CBRK_SUPPLY_CHK`, 22 `NAV_RCL_ACT = 0`, 8
  `GF_ACTION = 0`. A fresh whole-board test (**FA4**, flight + settings rules on new logs) is not yet run.

### 8.5 Public-archive search (declared)

On 514 public flights whose uploader text names a sign, the signs the words pointed to appeared in that flight's own
log 15.8% of the time, against 18.0% with texts shuffled (lift 0.88, p = 0.98): **failed**; matching logs from words
was removed. Only battery words pointed the right way (~3×; seen after the test). Flights with similar log signs
shared outcomes slightly in a crash-heavy sample (47.9% vs 40.2% crashes among 10 nearest, p = 0.0005).

### 8.6 Real DJI exports

Three public DJI Mini 4 Pro flight-record CSVs (MIT licence): first run found four reader faults, all fixed; heights
matched each file's own maximum-height column exactly (120.2 m, 61.6 m, 119.8 m).

### 8.7 VR debrief study (declared, not yet run)

12 students; 2D map + height profile vs 3D table in a Meta Quest 3; 15 real flights each way with known injected
deviations; counterbalanced; trials, key, and analysis committed before any participant.

### 8.8 Number checks & independent critical review

- `docs/paper/check_numbers.py`: **30 of 30** numbers in the paper and app Overview agree with the result files.
- `docs/CRITICAL_REVIEW_2026-11-27.md` (included in Appendix H): independent line-by-line review of commits
  `24c814f..8928782`; critical findings **C1** and **C2** fixed and live-verified in `fc73ec6` (**773 tests passing**).

---

## 9. Known weak points (honest status as of 28 Nov 2026)

1. **No real user or field sprayer logs.** No operator has used the tool; `pune-agri [Simulated SITL]` is simulated
   ArduPilot SITL (visibly badged on screens and printouts); `demo` is public PX4 hobby/research flights.
2. **Remaining verification & governance limits (post-C1/C2/H1-H5/M1-M5 fixes):**
   - **FA4 not yet run:** a fresh whole-board false-alarm test (combining flight rules with smoothed 2 s groundspeed +
     settings rules after C1) on unseen logs has not been declared or run yet; FA3 (14.2%, cluster CI [8.5, 20.7%]) was
     a re-measurement on H rather than an untouched held-out test, and SA1-RflyMAD (53.8%) is descriptive.
   - **Translations (H3):** Hindi and Marathi lines were team-reviewed by a Marathi-native member; an independent outside
     reader per language (especially Hindi) is still recommended before field deployment.
   - **Per-pilot RPC schema (M4 remainder):** RPC is currently stored per drone (`DroneCompliance`) rather than in a
     separate `pilots` table (a pilot often flies multiple drones); missing insurance passes only when no compliance row
     exists at all (legacy/public logs).
   - **RSA-PSS timestamps (L4):** `tsa.py` verifies PKCS#1 v1.5 and ECDSA signatures (failing closed on RSA-PSS).
3. **The normal-flight model** is PX4-only, not trained on sprayers (H5 failed), ranges are wide, and decision utility
   is untested.
4. **The research study**: unreliable self-reported labels; one self-uploaded archive; between-drone vibration is
   suggestive only (p = 0.076 site-weighted); paper unreviewed.
5. **Log coverage**: closed agricultural controllers and native encrypted DJI logs are unread; Airdata CSV untested.
6. **Legacy code**: ~4,000 lines of AeroFleet 1 LLM agents and 8 hidden screens remain in the repo (isolated and
   verified unreachable by the no-AI test).

---

## 10. Remaining work before the 1-5 December viva

1. Write and print the **7-chapter B.Tech final project report** with every number aligned to commit `HEAD`.
2. Optional if time allows before 1 Dec: obtain one external Hindi/Marathi proof-reader sign-off, declare and run
   **FA4** on fresh logs never used in FA1/FA2/FA3, and run the 12-participant Quest 3 VR debrief study.

---

## 11. What we believe is distinctive

1. A product designed around a **pre-registered negative result**: it refuses to name crash causes because declared
   tests on 590 crashes showed logs cannot support blame attribution.
2. **Pre-declared product verification with failures and critical reviews published openly** (H1, H5, FA1, archive
   search A1, SITL S1, and `CRITICAL_REVIEW_2026-11-27.md` C1/C2 fixes).
3. A **tamper-evident governance layer** (approved baseline with signed reasons, failsafe-off checks, Ed25519 ledger,
   offline auditor CLI, and DigiCert-pinned RFC 3161 trusted timestamps).
4. **End-to-end Indian DGCA & CIB&RC operator workflow**: UIN, third-party insurance, Type Certificate, Pilot RPC,
   nationwide 36-airport + Pune/Mumbai route check, 7-day Annexure-I spray register with swath acreage, maintenance
   grounding + service intervals, 48-hour accident dossier, and English/Hindi/Marathi morning board.
5. **Works for a fleet of one** via 292 never-crashed public reference flights and a conformally calibrated
   normal-flight context model.

---

## 12. Specific questions for you

1. Is the core argument sound: *because logs cannot attribute blame, a fleet tool should not name causes*? What is the
   strongest counter-argument, and how should we answer it?
2. After C1 and C2 were fixed in `fc73ec6`, are there any remaining critical safety, security, or statistical flaws
   beyond H1-H5 and M1-M4?
3. How should we present FA2 (11.1%, held out), FA3 (14.2%, cluster CI up to 20.7%, re-measured on H), and SA1 (36.8%
   archive crashes vs 26.5% prior flights vs 53.8% RflyMAD sensor faults) in the B.Tech report without overclaiming?
4. Is the normal-flight model worth keeping given H1/H5 failed and usefulness is untested?
5. With 3 days until the 1-5 December review, which of H4, H5, M1-M4, and FA4 must be done before writing the report,
   and which should be left as documented limits?
6. What will a hostile viva panel attack first now that the major engineering gaps are closed?
7. How should the 7-chapter B.Tech report unify the negative research study and the Indian operator product cleanly?
8. Is anything in the current product still unsafe (false clear or chronic alarm fatigue)?
9. How does AeroFleet now compare objectively against Airdata, DJI FlightHub, AeroGCS, and FlightMD?
10. Point out any remaining contradiction between Part I and Appendices A-H.

---

# Part II: Appendices (copied from the repository)
