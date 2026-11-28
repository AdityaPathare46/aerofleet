# AeroFleet 2.0: the complete project guide

For anyone on the team who needs to understand, run, demonstrate and defend the whole project. Written 27 November
2026, before the final review (1-5 December 2026). Every number here comes from a file in this repository; the file is
named next to it so you can check it yourself.

**If you have 10 minutes:** read sections 1, 2 and 13. **If you have an hour:** read everything, then run the demo
(section 10). **Before the viva:** read section 12 (our weak points) and `docs/VIVA.md`.

Contents

1. The project in one page
2. How we got here
3. The research study (the paper)
4. The product, screen by screen
5. The learned model
6. How we checked the tool
7. Code map
8. Where the data lives
9. How to run everything
10. The demonstration
11. Rules we work by
12. Critical review: our weak points, and what to say
13. What we must show at the review, and who does what
14. Glossary

---

## 1. The project in one page

**Title (report):** AeroFleet 2.0: an evidence-first safety and records platform for agricultural drone fleets.
**Team:** credited work by Aditya Pathare and Atharv Waghmare. Guide: Dr. N. K. Chougule. COEP Technological University.

**The problem.** Small agricultural drone operators in India (for example women's self-help groups under Namo Drone
Didi) are new pilots with one or two drones, no maintenance engineer and no fleet software. Their drones can fail
quietly through a changed setting; the law asks for records (UIN registration, a seven-day spray report, third-party
insurance); and after an accident someone asks *whose fault was it?* Meanwhile, a wave of tools claims to read a
flight log and name the cause of a crash.

**What we found first (the study).** On 590 real crash logs from a public archive of 479,547 PX4 flight logs, a rule
declared in advance could not tell pilot error from aircraft fault (0.47 balanced accuracy, chance is 0.50), and
trained models and a published log checker did no better. Logs support **evidence, not verdicts**.

**What we built from that (the product).** A ground-side back office that never flies or commands a drone and never
names a cause. Every day it answers four questions with fixed rules and recorded facts:

| Question | Screen |
|---|---|
| Can each drone fly today, and why not? | Today's fleet: *No rule fired / Check first / Do not fly* (records check only), each reason written out |
| Is this spraying route allowed? | Route check: approximate restricted airspace, the 120 m limit, conflicts between jobs |
| What happened in the flight, and can we prove it later? | Fleet Assurance: event timeline, signed and hash-chained record, comparison with healthy flights |
| Is the seven-day spray report done? | Spray register: the government's Spray Monitoring Form, part-filled from the log, with days left |

**No AI in any decision.** One small trained model gives *context* (the normal range of vibration and battery drop)
and never changes a verdict. A test fails the build if the decision code can import an AI or ML library.

**What it does not do:** fly drones, predict crashes, name causes, replace Digital Sky (the official airspace map), or
send anything to the government. **What is not yet shown:** that a real operator finds it useful, that it reduces
crashes, or how often it raises false alarms on a real fleet.

---

## 2. How we got here

Be ready to tell this as the three-semester story; it is true and it is a strength (we changed direction because
of evidence).

| When | What | Evidence in the repository |
|---|---|---|
| Earlier semesters | Space Mission Architect: an AI-agent system for space-mission design | `docs/SPACE_MISSION_ARCHITECT_README.md` (not committed; keep your own dated copies of earlier review slides and the synopsis) |
| Aug-Sep 2026 | AeroFleet 1: an AI-agent drone delivery dispatcher (LLM "council", live swarm, VR) | First commit 10 Aug 2026; midterm deck `research/aerofleet_midterm_review.pptx` (16 Sep, not committed) |
| Oct 2026 | The study: can logs tell who caused a crash? Declared tests, 590 crash logs | `research/px4_log_study/`, results in `research/results/px4_log_study/`, most commits dated 12-27 Oct |
| Late Oct-Nov 2026 | AeroFleet 2.0: re-scoped to evidence, not verdicts; agricultural use case | `docs/HANDOFF.md` section 6 |
| 17 Nov 2026 | Paper submitted to *Accident Analysis & Prevention* (Elsevier) | `docs/paper/submission/` |
| 20-27 Nov 2026 | Learned model, spray register, Hindi/Marathi, receipts, archive search, DJI CSV, SITL checks, VR study | git history |

**Honest note:** the git history starts on 10 August 2026 and shows 287 commits by Aditya and 2 by Atharv. The earlier
semesters are only provable with dated documents (synopsis, review slides, guide's notes). Collect them for the
report's timeline appendix. Never invent dates or commits.

---

## 3. The research study (the paper)

**Title:** *Evidence, not verdicts: what 590 public PX4 crash logs can and cannot tell a drone fleet operator.*
**Status:** submitted to *Accident Analysis & Prevention* on 17 November 2026; no reviews yet.
**Files:** `docs/paper/latex/main.tex`, `docs/paper/submission/` (PDF, Word, supplement, cover letter).

**How we worked (pre-registration).** Before each test ran, we wrote down the rule, the data and the pass mark, and
committed and pushed that to git. Then we ran it once and committed the result, whether it passed or failed. Tests
added after seeing a result are marked † and called exploratory. `docs/paper/check_numbers.py` checks that the numbers
in the paper and in the app match the result files (30 of 30 agree).

**Data.** The public PX4 Flight Review archive (479,547 logs); 590 crash logs studied; 148 PX4 forum crash threads with
expert diagnoses; 488 real fault-injection flights from the RflyMAD dataset.

| Question | Result | What it means |
|---|---|---|
| Can a log tell pilot error from aircraft fault? | Declared rule: **0.47** balanced accuracy on 112 held-out crashes (pass mark 0.70, chance 0.50); models near chance | The tool never names a cause |
| Why do published detectors look good? | Across 32 evaluation settings, AUC fell by 0.21; a published detector fell from 0.94 to 0.63 once whole days were held out | Evaluation design creates much of the apparent skill |
| Does a drone warn before it crashes? | No: vibration within a drone, mean rank 0.48, p = 0.67, 61 drones | No crash prediction |
| Do rougher drones crash more? | Mean rank 0.67, p = 0.0023 as declared; p = 0.012 by airframe and **0.076** with operator sites weighted equally: *suggestive* | Vibration is context, never a verdict |
| Can vibration pick drones to inspect? | Top-10% screen lift 1.77 [1.00, 2.60]: not shown to beat random inspection | No vibration flag |
| What do experts blame most? | Tuning or configuration, 26 of 94 aircraft-caused crashes (kappa 0.81) | Settings are checked first |

Always quote the "rougher drones" result with its two stricter p-values. "26 of 94" counts crashes blamed on the
aircraft alone; the troubleshooter test used 96 (94 plus 2 blamed on both pilot and aircraft).

---

## 4. The product, screen by screen

The app is a desktop app (Tauri + React) talking to a local Python API (FastAPI + SQLite). Sign in first.

| Screen | What it does | Code |
|---|---|---|
| **Overview** | The story: use case, study findings, design decisions, measured results, what is not shown | `tauri-app/src/pages/Overview.tsx`, `lib/studyFacts.ts` (every number has a source checked by `check_numbers.py`) |
| **Today's fleet** | Morning go / no-go per drone. *Do not fly*: an unapproved safety-critical setting change, or no UIN. *Check first*: a flight-limit change, **a failsafe switched off** (even if approved), an unverified UIN, settings never checked, warnings in the air in the last flight (a GPS or sensor complaint lasting 3 s, an autopilot error report). A landing below 10% battery is a pilot note. Vibration and the model shown as context only. English, Hindi, Marathi | `aerofleet/assurance/readiness.py`, `pages/Readiness.tsx`, `lib/readinessText.ts` |
| **Spray register** | The SOP's Spray Monitoring Form (Annexure-I, CIB&RC 434th meeting, 30 Nov 2021) per spraying flight, part-filled from the log (date, times, height above take-off, speed, spray direction), fixed checks quoting the SOP, deadline = spraying date + 7 days, printable form, signed saves, frozen once submitted | `aerofleet/assurance/spray_form.py`, `api/routes/spray.py`, `pages/SprayRegister.tsx` |
| **Fleet trends** | Flights and hours per week or month, warnings per flight, per-drone trends, operations-log CSV | `assurance/trends.py`, `assurance/operations_log.py` |
| **Fleet Assurance** | Settings drift against the approved baseline (with named approvals); flight review of a log (events in time order, evidence quality, planned vs flown); evening batch upload (drone matched by its flight-controller id); vibration history; maintenance logbook; "Something wrong? Describe it" (expert-cause checklist) and **public-archive search**; mission conflict check and fix; battery for the wind aloft; signed record, export, **receipts** | `assurance/drift.py`, `reconcile.py`, `evidence.py`, `vibration.py`, `maintenance.py`, `troubleshoot.py`, `archive_search.py`, `deconflict.py`, `wind.py`, `ledger.py` |
| **Route check** | Planned missions against approximate red / yellow zones (Pune, Mumbai), the 120 m limit and each other | `assurance/airspace_check.py`, `pages/RouteCheck.tsx` |
| **Drone register** | UIN per drone (recorded or verified) and the flight-controller compliance rules | `pages/HardwarePanel.tsx`, `hardware/compliance_rules.py` |
| **VR Safety View** | A reviewed flight on a 3D table (plan vs flown, events in place) and mission rehearsal; desktop or Quest 3 (WebXR); paired Unity app in `unity/AeroFleetVR` | `pages/VRSafetyView.tsx`, `components/vr/` |
| **VR study** | Runs the declared 2D-vs-headset debrief study; stores participant codes and answers only | `pages/VrStudy.tsx`, `api/routes/vr_study.py` |
| **Proof** | Recomputes the four headline study results live, shows when each was declared, runs five attacks on a copy of the signed record | `pages/Proof.tsx`, `aerofleet/evidence.py` |
| **Settings** | Users and permissions; legacy screens switch (off by default) | `pages/Settings.tsx` |

**Logs it reads:** PX4 `.ulg` in full; ArduPilot `.bin` and `.tlog`; any MAVLink autopilot's `.tlog`; `.csv` exports
(DJI flight-record and Airdata column names, our template); `.gpx` tracks. From ArduPilot `.bin` it also reads the
autopilot's own error reports, compass health, estimator test ratios, tilt above 60° and motor saturation.

**The signed record.** Every baseline, approval, settings check, flight review, spray-form save and maintenance entry
gets an entry signed with Ed25519 and linked to the previous one by its SHA-256 hash, together with the hash of the
exact file it came from. Editing, deleting or reordering anything breaks the chain. `tools/verify_ledger.py` checks an
export with only Python. A signed **receipt** of the newest entry, kept by someone outside the operator's control
(the fertiliser company, an insurer), shows later if the operator rebuilt the chain. It is tamper-*evident*, not
tamper-proof.

---

## 5. The learned model

Full write-up: `research/normal_flight/README.md`. In short: quantile gradient-boosted trees trained on **1,121
ordinary public PX4 flights of 401 vehicles** (no crash labels) give the 5-95% range of vibration and battery voltage
drop for a drone like this flown like this. Four declared tests: H1 calibration **failed** (72.7% / 73.3% instead of
85-95%), H2 skill passed (47.6% / 15.4% lower error than the median), H3 motor faults passed with caveats, H4†
conformal calibration passed (90.4% / 90.8%). A later declared attempt to add the drone's measured loading (H5) did
not reach its pass mark (6.2% lower error, mark 10%), so the shipped model is unchanged. Exported to JSON and run in
plain Python: no ML library in the product.

---

## 6. How we checked the tool

| Check | Result | Where |
|---|---|---|
| Automated tests | **752 pass** | `tests/unit`, `tests/integration` |
| Numbers in paper and app vs result files | 30 of 30 agree | `docs/paper/check_numbers.py` |
| No AI in the decision path | A test follows every import | `tests/unit/test_no_ai_in_decision_path.py` |
| Planned vs flown, 40 real flights with injected deviations | 36/40 sideways 35 m and 39/40 upward 20 m found; 0/40 false alarms **with a waypoint every 5 s** (9/40 at 10 s) | `research/results/px4_log_study/injection_reconcile.md` |
| Speed | 36 logs of 0.9-92.8 MB: median 0.23 s, largest 2.44 s | `docs/measurements/review_speed.md` |
| Tampering | Five attacks, all caught; also automated tests | Proof page |
| Real autopilot firmware (ArduPilot SITL, v1) | Met 3/3: normal, GPS lost, low battery, fence off in flight, wind. **Not met**: failsafes off (expectation wrong: ArduPilot's battery failsafe is off by default). Not shown: motor and compass failure | `research/results/sitl_check/summary.md` |
| SITL retest after fixes (v2, fresh flights) | **All 8 scenarios met 3/3**; normal and windy flights clean | `research/results/sitl_check_v2/summary.md` |
| Real DJI exports | 3 DJI Mini 4 Pro flight-record CSVs read correctly; heights match the files' own maximum; 4 reader faults found and fixed. Airdata layout untested on a real file | `tests/integration/test_real_dji_exports.py` |
| Public-archive search | Matching logs from words **failed** (15.8% vs 18.0% by chance), so it was removed; logs matched only from a real flight | `research/results/archive_search/summary.md` |
| False alarms of Today's fleet on healthy public flights (FA1) | 28.8% of good-or-great flights flagged: **failed** (pass mark 20%) | `research/results/false_alarms/summary.md` |
| Revised rule on held-out drones (FA2) | **11.1%** [7.3, 16.3] flagged: passed; real motor-fault flights still flagged 19.4% (was 21.5%) | `research/results/false_alarms/fa2_summary.md` |
| VR debrief study | Declared, **not yet run** | `research/vr_study/PROTOCOL.md` |

---

## 7. Code map

```
aerofleet/
  assurance/      the 2.0 product logic (readiness, drift, reconcile, evidence, ledger, spray_form, normal_flight,
                  flightlog readers, archive_search, log_signs, airspace_check, deconflict, wind, maintenance, trends)
  compliance/     flight checks and report calculators used by 2.0
  hardware/       flight-controller compliance rules (59 rules, with ArduPilot sources) and the read-only inspector
  api/routes/     assurance.py, spray.py, vr_study.py, evidence.py, auth.py, registrations.py, settings.py (+ legacy)
  data/models/    SQLite tables (SQLAlchemy)
  agents/, fleet/, fault_tolerance/, safety/, event_bus/, city/, vr/   mostly the earlier AI-dispatch product (legacy)
tauri-app/src/    pages/ (one file per screen), components/vr/, lib/ (studyFacts, readinessText, policy)
research/         px4_log_study (the paper), normal_flight, archive_search, sitl_check, vr_study, panel_eval
tools/            seed_demo_fleet, verify_ledger, build_archive_index, build_public_reference, benchmark_review
tests/            unit, integration (run these); property, hardware (legacy / need hardware)
docs/             HANDOFF, DEMO, VIVA, VR_PURPOSE, this guide, paper/
unity/            AeroFleetVR (Quest app)
```

**How a flight review flows:** upload → `flightlog.read_flight_log` (format by extension) → `reconcile` (if a plan was
given) or log-only → `evidence.timeline` (events) → `vibration`, `normal_flight.assess` (context) → stored as a
`FlightReview` → `ledger.append` (signed) → Today's fleet reads the latest review and the settings.

**Legacy code.** About 4,000 lines in `aerofleet/agents/` and several other packages, plus 8 legacy screens, belong to
the earlier product. They are hidden (Settings ▸ Show legacy screens) and their AI workers start only with
`AEROFLEET_LEGACY_AI=1`. Not deleted because they are part of the project's history.

---

## 8. Where the data lives

| What | Where | In git? |
|---|---|---|
| App database (users, reviews, signed record) | `~/Library/Application Support/AeroFleet/aerofleet.db` (`DATABASE_URL` in `.env`) | No |
| Signing key, heads file, archive index | same folder | No, never |
| Public PX4 logs, archive index `dbinfo.json` | `/Volumes/One Touch/AeroFleet_px4_data/` | No |
| SITL logs | `AeroFleet_px4_data/sitl/`, `sitl_v2/`; ArduPilot build in `~/aerofleet_sitl/` | No |
| DJI sample CSVs | `AeroFleet_px4_data/external/dji_samples/` | No |
| Result files, declarations, model JSON | `research/results/`, `aerofleet/assurance/data/` | Yes |

**Never commit:** `.env`, keys, raw logs, forum post text, the archive index (other people's text), review
spreadsheets, `aerofleet/README.md`, `aerofleet/parse_results.py`, `aerofleet/results (1).jsonl`,
`docs/SPACE_MISSION_ARCHITECT_README.md`, `research/aerofleet_midterm_review.pptx`, reference PDFs,
`.claude/launch.json` changes.

---

## 9. How to run everything

```bash
AEROFLEET_VENV=~/.venvs/aerofleet ./start.sh
```

Starts the API (port 8000) and the app (port 1420). On the exFAT drive the Python environment must live outside the
repo, hence `AEROFLEET_VENV`. Create a user from the sign-in card, or use the local test account in `.env`.

| Task | Command |
|---|---|
| Load the demo fleet (64 real public flights of 8 drones) | `python tools/seed_demo_fleet.py --reset` |
| Remake the demo spray forms only | `python tools/seed_demo_fleet.py --spray-only` |
| All tests | `python -m pytest -q --no-cov tests/unit tests/integration` |
| Check the paper's numbers | `python docs/paper/check_numbers.py` |
| Check a signed record without the app | `python tools/verify_ledger.py export.json --receipt receipt.json` |
| Back up the database and keys (safe while running) | `python tools/backup.py` (to `~/AeroFleet_backups/<date>`; keep it off this laptop and out of git) |
| Build the archive search index (about 20 min) | `python tools/build_archive_index.py` |
| Fly the SITL checks | `python research/sitl_check/run_v2.py` then `evaluate_v2.py` (needs `~/aerofleet_sitl`) |
| VR on a Quest 3 | `docs/VR_QUEST3_GUIDE.md`; for the study, `research/vr_study/PROTOCOL.md` (adb reverse ports 1420 and 8000) |

---

## 10. The demonstration

Step by step in `docs/DEMO.md`. The 10-minute version:

1. **Overview**: the use case and the study in one screen.
2. **Today's fleet** (fleet `demo`): 3 do not fly, 2 check first, 3 ready, each reason with a button to its evidence;
   switch to मराठी.
3. **Fleet Assurance**: open a flight review (events, evidence quality, expected range); a drone's vibration history;
   the signed record ▸ *Check the record*.
4. **Spray register** ▸ *As of the last spraying flight*: open the DEMO form with three problems; print the form.
5. **Route check** ▸ *Try 5 demo jobs*.
6. **Proof**: recompute the study live; run the five attacks.
7. Optional live SITL: fly a mission, switch the geofence off mid-flight, upload, see it flagged.

---

## 11. Rules we work by

1. **No AI or language model in any decision.** Verdicts come from fixed rules; the model is context.
2. **Declare every test before running it** (rule, data, pass mark committed and pushed), report every result.
3. **Never overclaim.** Say what is not shown. Quote caveats with numbers.
4. **Evidence, not verdicts.** Never name the cause of a crash.
5. **Credit only real work.** Aditya and Atharv. Never fake dates, commits or contributions.
6. **No secrets in files**; the test account is for this computer only.

---

## 12. Critical review: our weak points, and what to say

Ranked by how hard an examiner can push on them. "Say" is the honest answer; "Fix" is what would close it.

### A. Nobody outside the team has used it

1. **No real operator, no real Indian agricultural log.** The demo fleet is 64 public PX4 flights, mostly hobby and
   research drones, not sprayers. The use case is argued from government documents, not from users.
   *Say:* built and tested in software on public logs and on the real autopilot firmware; no operator yet. *Fix:* one
   conversation with an operator or a Krishi Vigyan Kendra, with their feedback written down.
2. **False alarms: measured, failed, fixed, and still only on public flights.** With the original rule (any warning
   in the last log, sensor complaints from 1 s, battery under 10% a reason) 28.8% of healthy public flights rated good or
   great got *Check first* (FA1, declared, **failed** the 20% pass mark). The rule was changed on half the drones
   (complaints count only in the air and from 3 s; a low-battery landing is a pilot note) and tested on the other half:
   **11.1% [7.3, 16.3]** (FA2, declared, passed); 19.8% of all held-out flights. Cost: real motor-fault flights flagged
   19.4% instead of 21.5%. *Still open:* the rate on real spraying drones. Files: `research/results/false_alarms/`.
3. **The VR claim is untested** until the study runs. *Say:* declared study, results reported whatever they show.
4. **No real hardware.** SITL runs the real ArduCopter code but simulates sensors, frame vibration and weather.

### B. The study

5. **Labels are unreliable** (blind relabelling agreed with uploaders no better than chance), so the negative result
   could partly be label noise. The paper says so.
6. **One archive, self-uploaded flights.** Not a random sample of drones and no agricultural sprayers identified.
7. **The one positive finding is weak** (p = 0.076 when operator sites count once). Never quote p = 0.0023 alone.
8. **The paper is not reviewed yet.** List it as "under review", never as published.

### C. The model

9. **Not trained on spraying drones.** Spraying drones are heavier and their payload changes during the flight (the
   tank empties); battery drop depends on payload, and payload and mass are not inputs. Ranges for a sprayer may be
   wrong. The app now says so beside every expected range. We tried adding the drone's loading measured from its
   own log (the thrust the autopilot commanded): declared test H5 **failed** (battery error only 6.2% lower, mark 10%),
   so the model was not changed. *Fix:* sprayer logs.
10. **Its calibration test failed**; the fix (H4) is exploratory and widened the ranges about 1.5 times, so "outside
    the range" is rare and may rarely help. Usefulness was never tested: no decision was shown to improve.
11. **PX4 only.** ArduPilot, DJI and CSV/GPX flights get no expected range.
12. **H3 is confounded** by the phase of flight (fault-free flights also changed at the same point).

### D. The product

13. **Airspace zones are approximate and only for Pune and Mumbai.** Not Digital Sky; every route must be checked there.
14. **The signed record trusts the operator's computer**: the operator holds the key, the clock is the computer's, and
    receipts work only if someone actually sends them.
15. **The spray form comes from a 2021 SOP copy** (CropLife India's reproduction of the CIB&RC minutes); the form may
    have changed, and it has never been compared with one an operator actually filled. AeroFleet does not submit it.
16. **Translations are not checked** by native speakers (the screen says so).
17. **Log coverage gaps:** closed agricultural controllers and DJI's own encrypted logs are not read; the Airdata CSV
    layout is untested on a real file; ArduPilot `.tlog` files and PX4 logs do not yet get the tilt and motor
    readings.
18. **Archive search:** matching from words failed its test; the local logs over-represent crashes.
19. **Legacy code is still in the repository** (about 4,000 lines of AI agents and 8 hidden screens). It cannot run in
    the product's decisions (a test proves it), but an examiner may open it. *Say:* kept as the project's history.
20. **Partly addressed:** `tools/backup.py` now makes a consistent, fingerprinted copy of the database and keys and
    verifies the signed record inside the copy. The macOS app now builds (`npx tauri build --bundles app`) and,
    opened like any installed app, starts its own backend against the same database as `start.sh` (three launcher
    bugs fixed on 27 Nov). It still needs this project folder and its Python environment on the same machine; it is
    not a self-contained installer. Not checked: Windows build since the changes, multi-user use, very large fleets.
21. **Test coverage** is 93% of the 2.0 core's statements (section 13), lower in `log_signs.py` (75%); coverage shows
    which lines ran, not that they are right.

### E. Process and team

22. **The git history covers 3.5 months and one main author.** Three semesters and two contributors must be shown
    with dated documents and with Atharv's own work this week.
23. **AI-assisted code and text.** Declared in the paper; must be declared in the report, and everyone must be able to
    explain the core modules (readiness, drift, ledger, the model) in their own words.
24. **The report is not written.** Biggest risk for 1-5 December.
25. **Some of our own declared expectations failed** (H1 calibration, SITL v1 S1, archive search A1). This is a
    strength if shown openly: it is what makes the passed tests believable.

---

## 13. What we must show at the review, and who does what

| Must show | Status | Owner |
|---|---|---|
| The report (40-70 pages, COEP format) with the abstract on the CMS portal | Not started | Aditya |
| Live demonstration (section 10) | Ready | Aditya |
| VR study results (pilot P00, then P01-P12) | Declared, not run | Atharv |
| The learned model explained (section 5, its README) | Ready | Atharv |
| SITL results, and optionally a live SITL run | Ready | Aditya |
| Dated documents from earlier semesters for the timeline appendix | To collect | Both |
| Contribution statement approved by the guide | To write | Both |
| Paper status (Editorial Manager screenshot; preprint if the journal allows) | To do | Aditya |

**Test coverage** (measured 27 Nov 2026 with `pytest --cov`): **93%** of the statements in the 2.0 core
(`aerofleet/assurance`, `aerofleet/evidence.py`, and the assurance, spray and VR-study API routes: 3,295 statements, 233
not run by any test); 78% across the whole `aerofleet` package, which includes the old product's code. Lowest in the
core: `log_signs.py` (75%), `flightlog_text.py` and `spray.py` (87%). Coverage says which lines ran, not that they are
right.

**Viva preparation:** `docs/VIVA.md` has 65 questions with answers. The hardest ones: Q1-Q2d (what is new, a
negative result, could an AI have built this), Q10 (couldn't you fake the dates), Q15-Q15e (the model), Q20 (the
"agents" folder), Q33 (weaknesses), Q37-Q47 (market, spray register, translations, receipts), Q48 (archive search
failure), Q50-Q53 (VR, SITL).

---

## 14. Glossary

| Term | Meaning |
|---|---|
| PX4, ArduPilot | The two open-source autopilot firmwares; their logs are `.ulg` (PX4) and `.bin` / `.tlog` (ArduPilot) |
| SITL | Software-in-the-loop: the real autopilot code running on a computer with a simulated drone |
| UIN | Unique Identification Number for a drone, from Digital Sky (DGCA) |
| Digital Sky | India's official drone airspace and registration platform |
| SOP, Annexure-I | The crop-protection drone Standard Operating Procedure and its Spray Monitoring Form |
| CIB&RC | Central Insecticides Board and Registration Committee |
| SHG | Self-help group |
| Failsafe | What the drone does by itself when something goes wrong (radio lost, battery low, fence crossed) |
| Baseline | The fleet's approved settings; changes against it are "drift" |
| EKF | The autopilot's state estimator; its test ratios above 1 mean it rejected a sensor's data |
| Balanced accuracy | Average of the accuracy on each class; 0.50 is chance for two classes |
| AUC | Area under the ROC curve; 0.5 is chance |
| Pre-registration / declared test | Rule, data and pass mark committed before the test runs |
| Conformal calibration | Widening a prediction range so it holds its stated share of new cases |
| Ed25519, SHA-256 | A digital signature scheme and a hash function, used for the signed record |
| WebXR | Running VR in a web browser (used on the Quest 3) |
