# AeroFleet 2.0: complete project dossier for an external review

*Generated from the project repository on DOSSIER_DATE (commit DOSSIER_COMMIT). Part I is written for you, the reviewer.
Part II (the appendices) is copied from the repository's own files: every result write-up, every declared test with
its commit, the full research paper and supplement, the viva notes and the code inventory. Personal names and contact
details have been removed; "the team" means a two-person final-year student team, with a faculty guide.*

---

## 0. What we are asking you to do

We are a two-person final-year B.Tech team (Robotics and AI specialisation, COEP Technological University, Pune, India).
Our project is **AeroFleet 2.0**: a research study of 590 real drone crash logs, and a software product built on what
that study found. The final review (viva, with a printed report) is on **1-5 December 2026**. We have about four days
of development before we must write the report.

We want a **hard, specific, technical critique** and a **prioritised plan**, not encouragement. Please:

1. Find anything **wrong**: a claim not supported by the evidence below, a statistical mistake, a rule that is unsafe or
   misleading, a test whose design does not test what it says, an inconsistency between two numbers.
2. Find what is **weak**: what an examiner (or a real drone operator, or an insurer, or a regulator) would attack first.
3. Propose **improvements that are feasible in about four days by two students with this codebase**, ranked by value
   to the project's credibility and usefulness. For each: what to change, how to test it (we declare every test in
   advance), and what result would count as success or failure.
4. Propose what would make this project **distinctive** (novel, defensible, useful) rather than one more log viewer.
5. Answer the specific questions in section 12.

Constraints you must respect: **no AI or language model may take part in any decision the product makes** (a hard rule
from our own study); every test is **declared before it runs** (rule, data, pass mark committed to git first) and every
result is reported, including failures; **no overclaiming**; no hardware beyond a laptop and a Meta Quest 3 headset;
no real operator data yet.

---

## 1. The project in one paragraph

Small agricultural drone operators in India (for example women's self-help groups under the Namo Drone Didi scheme:
15,000 drones approved, about 500 delivered under the scheme by March 2026) are new pilots with one or two drones, no
maintenance engineer and no fleet software. Drones can fail quietly through a changed setting; regulation asks for
records (a UIN registration number, a seven-day spray-monitoring report, third-party insurance); after an accident
someone asks *whose fault was it?* Meanwhile, many tools claim to read a flight log and name the cause of a crash. **Our
study tested that claim on 590 real crash logs and found that logs cannot reliably tell pilot error from aircraft
fault** (a rule declared in advance scored 0.47 balanced accuracy on 112 held-out crashes, where chance is 0.50).
**AeroFleet** is what we built from that result: a ground-side records and pre-flight assurance tool that never flies
or commands a drone, **never names a cause** ("evidence, not verdicts"), decides only with fixed rules, and keeps a
signed, tamper-evident record.

---

## 2. Timeline and honesty notes

| When | What |
|---|---|
| Earlier semesters | A different project (an AI-agent system for space-mission design), then a pivot |
| Aug-Sep 2026 | AeroFleet 1: an AI-agent drone *delivery* dispatcher (LLM "council", live swarm, VR) |
| Oct 2026 | The crash-log study: declared tests on 590 crash logs (most commits 12-27 Oct) |
| Late Oct-Nov 2026 | Re-scope to AeroFleet 2.0, agricultural use case, evidence-first |
| 17 Nov 2026 | Paper submitted to *Accident Analysis & Prevention* (Elsevier); no reviews yet |
| 20-27 Nov 2026 | Learned model, spray register, Hindi/Marathi, receipts, archive search, DJI CSV, SITL checks, false-alarm measurement, VR study design, packaged Mac app |

Honesty notes: the git history starts on 10 August 2026 (about 3.5 months; nearly all commits by one team member). The
code and text were written with help from an AI coding assistant; this is declared in the paper and will be in the
report. Code from AeroFleet 1 (about 4,000 lines of LLM agents and 8 hidden screens) is still in the repository,
switched off, and a test proves the product's decisions cannot reach it.

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
| Are crash labels reliable? | Blind independent relabelling agreed with uploaders no better than chance; the usual crash-moment tilt rule misses about 7-50% of crashes depending on the rater | † |
| What do experts blame? | Tuning or configuration **26 of 94** aircraft-caused crashes (forum coding agreement kappa 0.81) | Declared |
| Can word matching guess the cause? | Best guess matched the expert 22% (21 of 96), below 27% for always guessing the commonest cause | Declared |
| Do language-model review panels help? | On 97 crash cases none beat a plain rule; one compromised reviewer moved most verdicts | Declared |

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
| LLM review panels added errors; one compromised reviewer moved most verdicts | No language model anywhere in the decision path (a test enforces it) |
| Crash labels unreliable; detectors looked better than they were | The learned model is trained on ordinary flights only, with declared tests |
| Word matching guessed the cause worse than the base rate | "Describe it" is a checklist ordered by expert frequency, never a diagnosis |
| After an accident someone asks whose fault it was | Signed, hash-chained record that protects the pilot with facts |

---

## 4. The product: architecture

- **Desktop app**: Tauri (Rust shell) + React/TypeScript front end (about 10,800 lines), 11 screens in 2.0.
- **Local API**: Python FastAPI + SQLAlchemy over SQLite, on the operator's own computer. Nothing is sent anywhere.
- **Assurance core**: `aerofleet/assurance/` (about 3,800 lines): log readers, readiness rules, settings drift,
  planned-vs-flown reconciliation, evidence timeline, signed ledger, spray form, normal-flight model evaluator,
  airspace check, deconfliction, wind, maintenance, trends, archive search.
- **No ML library and no LLM** in the decision path; the one trained model is exported to JSON and evaluated in plain
  Python. `tests/unit/test_no_ai_in_decision_path.py` follows every import from product code and fails if it reaches an
  AI agent, the LLM panel or an ML library.
- **Tests**: 752 unit and integration tests; statement coverage of the 2.0 core 93% (whole package 78%, including the
  old product's code).
- **Packaging**: the macOS app builds and, opened like an installed app, starts its own backend (it still needs the
  project folder and its Python environment on the same machine).

**Flight review data flow**: upload → `read_flight_log` (format by extension) → `reconcile` with the mission if given,
otherwise log-only → `evidence.timeline` (events) → vibration value, normal-flight expected range (context) → stored as
a FlightReview → `ledger.append` (signed) → Today's fleet reads the latest review and the settings.

---

## 5. The product: every rule, with its exact numbers

### 5.1 Logs read

| Log | How | What is available |
|---|---|---|
| PX4 `.ulg` | pyulog, full | settings, modes, battery, GPS, vibration (estimator or IMU metric), estimator test ratios (compass, velocity, position, height), estimator faults, failsafe flag, commanded thrust, hardware, firmware, vehicle id, GPS time |
| ArduPilot `.bin` | pymavlink, full | settings (and changes in flight), modes, battery, GPS, vibration (VIBE), plus the autopilot's own health: ERR reports (subsystem and code, named as in ArduPilot's AP_Logger.h), per-compass health (MAG), EKF3 test ratios (XKF4), tilt (ATT), motor outputs (RCOU) |
| ArduPilot / MAVLink `.tlog` | pymavlink | position, modes, battery, GPS, settings, vibration |
| `.csv` export | columns found by name; feet → metres; epoch in s/ms/µs/ns; DJI "1m 5.3s" text | position, time, battery, satellites, mode. Tested on 3 real public DJI Mini 4 Pro flight-record exports; Airdata layout untested on a real file |
| `.gpx` track | XML | position and time only |

Only numbers are read, never the free-text messages in logs.

### 5.2 Evidence timeline (`aerofleet/assurance/evidence.py`)

- Flight-mode changes (a "pilot took control" notice when an automatic mode switches to a pilot mode).
- Safety-critical setting changed in flight: warning; flight-limit setting changed: notice.
- Battery below 20%: notice; **below 10%: warning**; voltage fell more than 25% over the flight: notice.
- Poor GPS (fewer than 6 satellites, no 3D fix, or HDOP above 2.5) for 2 s or more.
- Autopilot health reports for 1 s or more (PX4 estimator rejections, faults, failsafe; ArduPilot items above).
- **Warning vs notice (since FA1/FA2, section 8.4)**: a GPS or health complaint is a *warning* only for the part that
  happened in the air (track more than 2 m above home) and only if that part lasts at least 3 s; a single ArduPilot
  error report counts only if it happened in the air; otherwise it is listed as a *notice*.
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
| **Do not fly** | an unapproved safety-critical setting change; or no UIN on record |
| **Check first** | a flight-limit change; **a failsafe switched off** in the drone's settings, whatever the baseline says (ArduPilot: compliance rules for the low- and critical-battery failsafes, RC-loss failsafe, EKF failsafe, geofence; PX4: `NAV_RCL_ACT` = 0, `COM_LOW_BAT_ACT` = 0, `GF_ACTION` = 0); an unverified UIN; settings never checked; or a warning in the air in the last flight (5.2) |
| **Ready** | none of these |

A landing below 10% battery is shown as a *pilot note*, not a reason. Vibration and the learned model are shown as
context and never change the verdict. Screen available in English, Hindi and Marathi (translations not yet checked
by native speakers); a test checks that every reason code has all three wordings.

### 5.5 Planned vs flown (`reconcile.py`)

Mission file (`.waypoints`) compared with the flown track in flying order; defaults 30 m sideways, 15 m height, at
least 3 s. Reports episodes, furthest deviation and the events around each episode.

### 5.6 Route check (`airspace_check.py`)

India's Drone Rules 2021 zones, approximated from public distances around known sites: airports (red 5 km, yellow
12 km lateral band) and military/strategic sites, **only around Pune and Mumbai**; the 120 m green-zone height limit;
conflicts between planned jobs. Verdicts CLEAR / NEEDS_PERMISSION / NOT_PERMITTED / UNCHECKED (outside the supported
cities, never "clear"). Not the official Digital Sky map.

### 5.7 Spray register (`spray_form.py`)

The crop-protection SOP (CIB&RC 434th Registration Committee meeting, 30 Nov 2021, section 7) requires the Spray
Monitoring Form (Annexure-I) within seven days of pesticide spraying by drone. Each flight gets the form field for
field (1-1 Date ... 7-3 Who was informed) plus two SOP pre-spray items (24 h written notice to the Gram Panchayat and
Agriculture Officer; no water source within 100 m). Filled from the log: date, start/end time, height above take-off
(median in the air), ground speed (median when moving), spray direction (axial mean of track bearings when at least
60% of the distance lies along one axis). Copied from the drone's previous form: sprayer type, maker, model, nozzles.
From the maintenance logbook: last calibration. Checks citing the SOP: product past expiry, notice under 24 h, no
protective clothing, water within 100 m, no UIN; entered height or speed differing from the log is noted. No
thresholds for wind, temperature or height, because the SOP gives none. Deadline states: overdue, due soon (two days
or less, incomplete), incomplete, complete, submitted. Every save is signed; a submitted form is frozen. Printable in
the Annexure-I layout (six flights per sheet). AeroFleet does not submit the form.

### 5.8 Signed record (`ledger.py`)

Each entry: sequence number, kind, subject, SHA-256 of the payload (and of the exact input file), previous entry's
hash, timestamp, user; the entry hash is signed with Ed25519. Every committed head is also appended to a heads file.
`tools/verify_ledger.py` checks an export with only Python and the `cryptography` package. **Receipts**: a signed note
of the newest entry for someone outside the operator's control to keep; a later chain that no longer contains that
entry fails. Threat model: catches edits, deletions, reordering, re-signing with another key, and (with receipts) a
chain rebuilt with the operator's own key; does not catch a log edited before upload, and trusts the computer's clock.
`tools/backup.py` makes a consistent copy of the database and keys and verifies the record in the copy.

### 5.9 Other features

- **Vibration history**: each drone flight by flight in GPS-time order against its own earlier flights, against drones
  of the same kind in the fleet, and against 292 public PX4 flights of 141 never-crashed vehicles; last 10 s left out.
- **Maintenance logbook**: work recorded and signed; flights before and after compared (3 each side) relative to the
  model's expectation.
- **Fleet trends**: flights and hours per week/month, warnings per flight, per-drone trends, operations-log CSV.
- **Describe it**: a checklist ordered by how often experts found each cause (BM25 word matching to mark mentioned
  causes and show similar forum threads).
- **Public-archive search**: what uploaders wrote about 14,259 public flights (BM25), and, from one of the user's own
  flights, the 2,521 local public logs that show the same log "signs". Matching logs from words alone was tested and
  removed (section 8.5).
- **Mission deconfliction** (launch delay or a different height) and **battery for the wind aloft** (energy per leg
  with the forecast wind at cruise height).
- **Drone register**: UIN per drone (recorded or verified) and 59 flight-controller compliance rules.
- **VR Safety View**: a reviewed flight on a 3D table (plan vs flown, events in place) and mission rehearsal, on the
  desktop or a Quest 3 (WebXR); a Unity Quest app also exists. Its stated job: a flight debrief by a trainer.
- **Proof screen**: recomputes the four headline study numbers live and runs five attacks on a copy of the record.

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
| H3 vibration score after injected motor faults (RflyMAD, 220 flights) | rose in 60% of flights, p = 0.0005 | p < 0.025 | Passed, with caveats (sensor faults and fault-free flights also changed at the same point: phase of flight) |
| H4† conformal calibration (nested) | 90.4% / 90.8% | 85-95% | Passed (fixed-wing vibration 84.8%) |
| H5 add measured loading (commanded thrust) | battery error 6.2% lower (0.826 → 0.775); vibration −0.3% | ≥ 10% lower | **Failed**; model not changed |
| H6 coverage with loading | 91.4% / 90.9% | 85-95% | Passed (not sufficient to ship) |

Limits: PX4 only; not trained on spraying drones (the archive holds about 20 flights from 4 vehicles mentioning
spraying, and no log records payload); ranges about 1.5x wider after calibration; usefulness for a decision never
tested.

---

## 7. Demonstration fleet

64 real public PX4 flights of 8 drones (all eight drones' last flights were rated crashes by their uploaders),
demo registrations (labelled DEMO: one drone with no UIN, one unverified), one demo maintenance entry, four demo spray
forms, a second fleet with a settings-drift case (`NAV_RCL_ACT` 2 → 0). Today's fleet currently shows 3 do not fly,
2 check first, 3 ready. Three crash-rated drones show *Ready* because their logs show nothing in the air that the rules
flag, which is the study's own finding (crash flights showed no warning) on screen.

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
| S1 throttle and battery failsafes off | **not met 0/3** (battery failsafe already off by ArduPilot default; throttle failsafe caught, drone blocked) | met 3/3 (both named; failsafe-off rule) |
| S2 GPS lost 20 s | met 3/3 | met 3/3 |
| S3 battery low | met 3/3 | met 3/3 |
| S4 geofence switched off in flight | met 3/3 | met 3/3 |
| S5 8 m/s wind | met 3/3 (max sideways 0.9-1.5 m) | met 3/3 |
| S6 motor failure | not shown (descriptive) | met 3/3 (autopilot thrust-loss report, motor saturation) |
| S7 compass failure | not shown (known gap) | met 3/3 (compass 1 unhealthy, autopilot compass report) |

### 8.4 False alarms of Today's fleet on healthy public flights

FA1 (declared): 1,121 ordinary flights, read as the product reads them; pass mark at most 20% of good-or-great flights
flagged. Result: **28.8%** [23.9, 34.1] of 299 good-or-great flights, 40.7% of all; **failed**. Main causes: estimator
compass (16.2%) and velocity (11.8%) rejections, landing under 10% battery (16.2%), failsafe flag (11.2%).
Rule revised on the development half of the vehicles only (exploratory; variants and real fault flights shown below),
then **FA2** (declared) on the held-out half: **11.1%** [7.3, 16.3] of 190 good-or-great flights, 19.8% of all 572;
**passed**.

| Variant (development half D) | Healthy good/great flagged | RflyMAD motor-fault flights flagged | Sensor-fault | No-fault |
|---|---|---|---|---|
| Original | 34.9% | 21.5% | 58.4% | 0% |
| In the air only | 23.9% | 20.2% | 56.3% | 0% |
| In the air, ≥ 3 s (chosen) | 19.3% | 19.4% | 53.8% | 0% |
| In the air, ≥ 5 s | 18.4% | 12.4% | 49.2% | 0% |

### 8.5 Public-archive search (declared)

On 514 public flights whose uploader text names a sign, the signs the words pointed to appeared in that flight's own
log 15.8% of the time, against 18.0% with texts shuffled (lift 0.88, p = 0.98): **failed**; matching logs from words
was removed. Only battery words pointed the right way (about 3x; seen after the test). Flights with similar log signs
shared outcomes a little in a crash-heavy sample (47.9% vs 40.2% crashes among the 10 nearest, p = 0.0005).

### 8.6 Real DJI exports

Three public DJI Mini 4 Pro flight-record CSVs (MIT licence): first run found four reader faults (date column name,
text fly-time column, older battery columns, an idle battery read as empty), all fixed; heights then matched each
file's own maximum-height column exactly (120.2 m, 61.6 m, 119.8 m).

### 8.7 VR debrief study (declared, not yet run)

12 students; 2D map + height profile vs the 3D table in a Meta Quest 3; 15 real flights each way with known injected
deviations (none; sideways 15 or 35 m; upward 8 or 20 m); answer "stayed on plan / off sideways / off in height";
counterbalanced order and flight sets; primary measure share answered right, paired Wilcoxon, two-sided. Trials,
answer key and analysis committed before any participant.

### 8.8 Number checks

`docs/paper/check_numbers.py`: 30 of 30 numbers in the paper and in the app's Overview agree with the result files.

---

## 9. Known weak points (our own critical review)

1. **No real user.** No operator has used it; no real Indian agricultural log; the demo fleet is public, mostly hobby
   and research PX4 flights, not sprayers. The use case rests on policy documents, not interviews.
2. **False alarms on real sprayers unknown.** FA2 passed on public flights only. Most remaining flags are the
   autopilot's failsafe flag and estimator rejections lasting ≥ 3 s in the air.
3. **Thresholds are conventions** (6 satellites, HDOP 2.5, 10%/20% battery, 25% voltage sag, 60° tilt, 30 m / 15 m
   corridor, 3 s), except the 3 s rule which was set on half the data and tested on the other half.
4. **The model is not for sprayers** and adding loading did not pass; its usefulness for any decision is untested; PX4
   only; ranges are wide.
5. **The study**: unreliable labels; one self-uploaded archive; the one positive finding is weak (p = 0.076 site
   weighted); the paper is unreviewed.
6. **Airspace** approximate and only Pune/Mumbai.
7. **Signed record** trusts the operator's computer (key and clock); receipts depend on discipline; no trusted
   timestamping.
8. **Spray form** taken from a 2021 SOP copy (an industry reproduction of the CIB&RC minutes); never compared with a
   form an operator filled; no spray flow, volume or coverage measurement (most spraying controllers' logs are closed).
9. **Translations unchecked**; no mobile app; desktop only.
10. **Log coverage**: closed agricultural controllers and DJI's encrypted logs not read; Airdata CSV untested.
11. **Legacy code** (about 4,000 lines of old LLM agents, 8 hidden screens) still in the repository.
12. **Process**: 3.5-month git history; one main author; AI-assisted code; report not yet written.

---

## 10. Our current improvement ideas (for you to rank or replace)

- Declared test of Today's fleet on crash flights: what share of crash-rated flights would get "Check first" from the
  flights *before* the crash (sensitivity, to pair with FA2's specificity).
- Read the same tilt and motor-saturation signs from PX4 logs and ArduPilot `.tlog` files (today `.bin` only).
- Nationwide airport zones from a public airport list (routes outside Pune/Mumbai would say "airports only").
- Trusted timestamps for receipts (RFC 3161), so a record's date does not depend on the operator's clock.
- A "pilot debrief" report combining the flight timeline, the VR replay and the spray form, for SHG trainers.
- A mobile upload path (phone camera of the controller's flight log export, or a simple web upload).
- Removing or quarantining the legacy LLM code into a separate folder.

---

## 11. What we believe is distinctive

1. A product designed around a **published negative result**: it refuses to name causes because a declared test showed
   logs cannot support it.
2. **Declared tests for the product itself**, including failures reported (H1, H5, FA1, archive search A1, SITL S1).
3. A **governance layer** (approved baseline with written reasons, failsafe-off rule, signed record with receipts)
   rather than another log viewer.
4. **India-specific workflow**: UIN checks, Drone Rules 2021 zones, the SOP's seven-day Spray Monitoring Form,
   Hindi/Marathi.
5. **Works for a fleet of one** (public reference of 292 never-crashed flights; the normal-flight model).

---

## 12. Specific questions for you

1. Is the core argument sound: *because logs cannot attribute blame, a fleet tool should not name causes*? What is the
   strongest counter-argument, and how should we answer it?
2. Are any of our statistical choices wrong or weak (balanced accuracy, mean scaled rank with permutation tests,
   GroupKFold by vehicle, conformal widening, Wilson intervals, the D/H split for FA2)? Is FA2's development-then-test
   procedure valid, and what else should we report?
3. Today's fleet: is "Check first" for a 3-second in-air estimator rejection a good rule for agricultural drones? What
   should the readiness rules be, given what logs can and cannot show? How should we measure sensitivity (crash
   flights) without trusting the unreliable crash labels?
4. The model: is it worth keeping given H1 failed, H4 is exploratory, H5 failed, and usefulness is untested? What
   would make it genuinely useful to an operator, or should it be removed?
5. Which three improvements (ours in section 10 or yours) would most raise the project's credibility in four days?
6. What will a viva panel ask that we are not ready for? Give the hardest ten questions with model answers.
7. How should the B.Tech report (40-70 pages, 7 chapters) be structured to present a negative research result plus a
   product without looking like two unrelated projects?
8. Is anything in the product **unsafe** (could lead an operator to fly when they should not, or ground a drone
   wrongly), and how should we change it?
9. What would make this genuinely **novel** in the drone-safety-software space, compared with Airdata, DJI FlightHub,
   FlightMD, AeroGCS and the AI "why did it crash" tools?
10. Point out any number in this document that contradicts another number in it.

---

# Part II: Appendices (copied from the repository)
