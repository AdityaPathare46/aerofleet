# AeroFleet demonstration guide

A walk-through that shows each claim the paper makes about the tool (Section 6, Table 12), on real public PX4
flights, with the questions an examiner is likely to ask. About 10 minutes.

Last checked 27 November 2026 on a desktop browser (macOS). Not checked on a headset or with a partner fleet's logs.

> **Two seeded demo fleets:**
> - **`pune-agri [Simulated SITL]` (start here for the Indian operator workflow):** 6 **simulated** ArduCopter SITL v2 4 m Pune spraying flights (`AGRI-01..06`, visibly badged as simulated on screen and printouts) with a shared approved baseline, reconciled `.waypoints` plans (playable in 3D/VR), grounded incident on `AGRI-05` (with 1-click Rule 30 / 2025 AAIB Accident Record), active Nov 2026 CIB&RC Annexure-I spray forms (5.61 acres upper-bound swath), and every readiness outcome (`No rule fired`, `Check first`, `Do not fly`). Seed standalone with `--agri-only` or together via `--reset`.
> - **`demo` & `demo-settings` (empirical study evidence):** 64 real public PX4 flights of 8 unrelated airframes showing the within-drone vibration null, public reference comparison, maintenance logbook before/after, and settings drift.

## 1. Set up (once)

```bash
export AEROFLEET_VENV=~/.venvs/aerofleet
AEROFLEET_PX4_DATA="/Volumes/One Touch/AeroFleet_px4_data" $AEROFLEET_VENV/bin/python tools/seed_demo_fleet.py --reset
./start.sh
```

The seed script loads 64 real flights of 8 public PX4 airframes into the fleet `demo`, through the same code as an
upload in the app. It also writes files for the live steps into `AeroFleet_px4_data/demo_files/`:

| File | What it is |
|---|---|
| `PX4-01_approved.params` | The real settings of drone PX4-01 in its first flight |
| `PX4-01_changed.params` | The same, with the RC-loss failsafe switched off by the script (made up, to show the check) |
| `SURVEY-A/B/C.waypoints` | Three made-up missions over Pune; A and B cross at the same height |
| `../demo_fleet_key.json` | Presenter's key: which flight of each drone the uploader rated a crash |

Then open http://localhost:1420. The app opens on **Overview**. Sign in once (on the Fleet Assurance page); after that
the Overview shows live counts of the demo fleet, and every "Open ..." button there jumps to the right section of the
demo fleet.

**What the demo data is, said plainly.** The eight drones come from the study's within-drone selection: each has
one flight that its uploader rated a crash, and earlier flights. They are unrelated public airframes, not one
operator's fleet, so no settings baseline is set for them. The tool is never given the crash ratings.

## 2. The walk-through

Each step names the paper claim it shows.

### Step 0. The pitch (Overview page, about 3 minutes)

Scroll the Overview from top to bottom; it is written to be read aloud.

1. **What it is.** "Evidence, not verdicts": a ground-side tool that checks the settings, plans and logs an operator
   already has, keeps a signed record, and never names a cause.
2. **The problem.** Rules demand records (three years in the EU and UK; accident reports within 48 hours in India and
   ten days in the US), while tools promise verdicts from logs. We tested whether logs can carry that weight.
3. **What we found.** Six cards, each with its number and "So:" line saying what it means for an operator.
4. **How the tool answers it.** Each design choice next to the finding it comes from; the buttons jump into the demo.
5. **How it is used.** Before a flight, after a flight, over the fleet's life, when something goes wrong.
6. **Benefits, measured results and what is not yet shown.** Read the yellow box out loud: it pre-empts the hardest
   questions.

Every number on that page is checked against the paper and the result files by `docs/paper/check_numbers.py`.

### Step 0a. The use case and Today's fleet (2 minutes)

The use case: **the safety and records back office for agricultural drone service providers in India.** Under Namo
Drone Didi (approved November 2023, Rs 1,261 crore) 15,000 drones were approved for women self-help groups, about 500
delivered under the scheme by March 2026; the groups rent spraying
flights to farmers; pilots get 5 days of flying training plus 10 for agriculture. They need checks that do not depend
on expertise, and records that protect the pilot (third-party insurance is mandatory; spray data must be reported
within 7 days). In our study, the cause experts named most often for aircraft crashes was tuning or configuration
(26 of 94), which is exactly what the settings check covers.

Open **Today's fleet** (fleet `demo`): 3 do not fly, 5 check first, 0 no rule fired (because the public PX4 logs are years old, crossing the 90-day record-age check), each with its reason, all from real
public logs: PX4-04's critical-battery threshold changed between flights, PX4-08's geofence distance changed (and its
low-battery failsafe only warns), PX4-06's autopilot rejected position data for 4 s in the air. PX4-05 has no UIN on
record and PX4-07's is not verified (demo registrations, labelled DEMO). PX4-01 shows a **pilot note**: its last
flight landed below 10% battery, which says how it was flown, not whether the drone is fit today. Press a reason's
button to open its evidence.

Say: the verdict comes only from fixed rules and recorded facts. Vibration is shown but never changes the verdict,
because the study found it is not a validated warning. A GPS or sensor complaint counts only in the air and only if it
lasts 3 s: with the earlier 1 s rule, 28.8% of healthy public flights were flagged (FA1, failed); with this rule, 11.1%
of held-out healthy flights (FA2, passed).

**Be ready for this question:** the uploaders rated every demo drone's last flight a crash, yet three (`PX4-01`,
`PX4-02`, `PX4-03`) fired **zero** flight-telemetry or settings rules — they are on *Check first* solely because their
2017–2018 public logs are more than 90 days old (15–90 days shows a non-blocking age note so seasonal sprayers idle
between crop cycles are not flooded with alarms; past 90 days escalates to *Check first* so a years-old log never stays
green). At the time those flights ran, no telemetry rule fired: that is the study's own finding on screen (SA1: ~37% of
archive crashes flagged vs 27.1% of ordinary flights, 1.36× — descriptive re-measurement on shipped HEAD), which is why the green state on `pune-agri` (`AGRI-01`,
`AGRI-02`) reads **No rule fired (records check only — not an airworthiness sign-off)** rather than *Ready*. An operator
who knows a drone crashed records it in the maintenance logbook to ground it to *Do not fly* (as on `AGRI-05`).

Press **मराठी** (or **हिन्दी**) at the top: the same verdicts and reasons, worded for the pilot. Say that the rule does
not change with the language, log messages stay in English, and the translations were reviewed by the Marathi-speaking
team member (an independent external operator review is still recommended before field deployment).

### Step 0b. Proof (2 minutes)

Open **Proof** and press *Recompute the results*: the paper's four headline results are recomputed from the
committed data, each with the commit that declared the test and the later one that added its result. Then press
*Run five attacks on a copy*: every attack on the signed record is caught and the real record is untouched. The hard
questions and their answers are in `docs/VIVA.md`.

### Step 0c. The learned model (1 minute)

On **Proof**, press *Show the model and its tests*: 1,121 ordinary flights of 401 vehicles, tests declared before
training, the failed calibration test and the declared fix that passed. Then on **Today's fleet**, PX4-01 ▸
*Last flight →*: "Compared with healthy flights of similar drones" shows its battery drained 7.5 times faster than
typical, matching the timeline's "Battery below 10%". Say: context, never a verdict.

### Step 0d. Season view, logbook, evening upload, records (2 minutes)

1. **Fleet trends**: 64 flights, 9 h, 1.3 warnings per flight, 14% of flights outside the learned range (about 10%
   expected by chance), flights per month, and a per-drone table. Press PX4-06 ▸ *History →*.
2. In PX4-06's history, the purple line is a **maintenance logbook** entry ("Propellers replaced", a DEMO entry made up
   between real flights): vibration fell 58% and battery drain vs expected 21%, median of the flights either side,
   with the caveat that a few flights cannot prove a fix. Add an entry with the form to show it is signed.
3. Fleet Assurance ▸ *Upload the day's logs*: select several logs at once. Each is matched to its drone by the flight
   controller's own id (PX4 sys_uuid) or, the first time, by a file name like PX4-07_evening.ulg; unknown logs are not
   guessed onto a drone.
4. Fleet trends ▸ *Download CSV*: one row per flight with UIN, minutes, distance, outline area (a field-size estimate),
   take-off point and the fingerprint of its signed review: the record a spray report is filled from.
5. **Spray register**: press *As of the last spraying flight* (the demo logs are years old, so counted from today
   every form is overdue). PX4-08's last four flights carry DEMO forms, labelled DEMO, one per state: submitted,
   complete but not sent, one with three problems (product expired, notice sent 6 h ahead, no protective clothing),
   and one set aside as not a spray flight. Open the problem form: each problem quotes its SOP clause; fields marked
   *from the log* came from the flight. Tick three flights and *Print form*: the Annexure-I layout, six columns.
6. Fleet Assurance ▸ Signed record ▸ *Save a receipt*, then *Check a receipt* with the saved file: "Receipt matches".
   Say who should keep it (the fertiliser company or insurer) and why: on the operator's machine alone the record
   could be rebuilt; a test shows a rebuilt chain fails the receipt.

### Step 1. Events in time order, no verdict (attribution finding, Q1 and Q2)

1. In **Flight reviews**, open the newest flight of `PX4-08` (the one the uploader rated a crash).
2. Show the timeline: mode changes with times, "pilot took control" where the pilot took over from an automatic
   mode, and on some flights "Estimator rejected compass data for N s" (the autopilot's own report).
3. Show **Evidence quality**: position rate, GPS satellites and HDOP, how height and time were measured.
4. Point at the sentence under the timeline: the tool does not name a cause.

Say: on 590 public crash logs, neither a fixed rule nor a trained model separated pilot-caused from aircraft-caused
crashes better than chance (balanced accuracy 0.47 on held-out crashes). So the tool puts the facts in order and
leaves the judgement to a person.

### Step 2. Vibration against the drone's own history (within-drone finding, Q3)

1. In **Vibration across the fleet**, press **History** on `PX4-01`.
2. The orange point is the flight the uploader rated a crash. It is lower than all 7 earlier flights.
3. Press **History** on `PX4-03`: there the last flight is higher than 5 of its 7 earlier flights.

Say: this is the paper's within-drone result seen on single drones. Across 61 drones the flight before a crash did
not vibrate more than the drone's own earlier flights (mean rank 0.48, p = 0.67). One drone goes up, another goes
down. That is why the screen calls a rise "a reason to look, not a warning".

Also point out: flights are ordered by GPS time, not upload date. In the archive 85 of 210 same-day "earlier"
flights had been flown after the crash.

### Step 3. Position among comparable drones, with no flag line (between-drone finding)

1. Stay on the vibration table. Each drone has a bar, a position ("3 of 8") and a multiple of the group median.
2. There is no "inspect" flag and no threshold.

Say: between drones there was an association (mean rank 0.67 over 60 matched sets), but it weakened under stricter
tests (Holm-adjusted p 0.016 as declared, 0.08 clustered by airframe, 0.45 with operator sites weighted equally),
and measured against 412 non-crash drones a top-decile threshold gave a lift of only 1.77 [1.00, 2.60]. So the tool
shows the position and draws no line. An earlier version flagged the top quarter; that was removed because it
claimed a validation the study does not have.

Also: the last 10 seconds of every flight are left out of the value, so an impact cannot make a drone look rough
(the review shows both values).

### Step 4. Settings drift (deterministic check)

1. Type `demo-settings` in the Fleet box (the seed script prepared it) and press **View** on `PX4-01`.
2. The drone is marked Blocked: the RC-loss failsafe (`NAV_RCL_ACT`) is 0 where the approved value is 2.
3. Point at the **Public PX4 flights** column: only 8% of public PX4 flights rated good or great switch it off; 86%
   use 2. That is context from real flying, not a rule.
4. With an operator account, write a reason and approve it, to show that an approval is recorded with who and why.
   (Setting a baseline and approving need an operator account; the seed script sets the baseline so the demo
   does not.)

Say: this is plain comparison code. The change in the second file was made by our script; the first file is real.

### Step 4b. Compared with the public archive (works for a fleet of one)

1. Back in fleet `demo`, the vibration table's **Against public PX4 flights** column places each drone among real
   public flights with the same measurement and kind of vehicle (multirotors with multirotors, fixed wing with fixed
   wing). PX4-01 shows "no public reference": too few public flights of its kind to compare with, and it says so.
2. Open a **History**: the grey dotted line is the median of public flights.
3. Open any flight review: the summary line says where its vibration stands among public flights.

Say: the in-fleet comparison needs four drones of the same kind; a small operator has none. The reference is 292
public flights of 141 vehicles that never crashed, rated good or great by their pilots, read with the same code as
an upload (`tools/build_public_reference.py`). It is a description, not a limit, and the screen says so.

### Step 4c. Route check before flying (Route check page)

1. Open **Route check** and press *Try 5 demo jobs* (made-up spraying and mapping jobs around Pune, one per outcome).
2. SPRAY-NEAR-CANTONMENT: not permitted, inside the red zone of Pune Cantonment. CROP-MAP-150M: not permitted,
   planned at 150 m. SPRAY-NEAR-AIRPORT: needs air traffic control permission (the airport's yellow zone).
   SPRAY-FIELD-A and SPRAY-FIELD-B: clear, but they cross each other at the same height and time. Spraying jobs are
   planned at 5 m above the take-off point, as crop spraying is flown just above the crop.
3. Click a mission to zoom to it on the map.

Say: full local zones are loaded for Pune and Mumbai, and 37 Indian civil airport perimeters (MoCA Sep 2021 distances with 1.5 km perimeter allowance: 0–5 km RED, 5–8 km YELLOW all heights, 8–12 km YELLOW above 60 m / 200 ft) are checked nationwide; routes outside mapped zones return "not checked", never "clear". Every check is signed.

### Step 5. Mission conflict and wind (pre-flight checks)

1. **Will these missions conflict?** Choose `SURVEY-A`, `SURVEY-B` and `SURVEY-C` together, then **Check and fix**.
2. A and B conflict at the crossing (about 1 m apart at the same height); the tool proposes a staggered start.
3. Optional: **Rehearse in 3D**.

Say: these missions are made up for the demonstration.

### Step 6. Signed record (audit integrity)

1. Scroll to **Signed record**, press **Check the record**: every review, baseline and approval is there, each
   signed (Ed25519) and linked to the one before, with the SHA-256 of the uploaded file.
2. Press **Export for an auditor**, then run the standalone checker on the file:
   `python tools/verify_ledger.py <exported file>`
3. Open the printable report of a flight review: it states whether it matches its entry in the record.

Say: the record shows whether anything was altered afterwards. It does not prove the uploaded files were genuine.

## 3. Questions an examiner may ask

**Does the tool predict crashes?**
No. The paper found no per-flight warning within a drone, and the between-drone association did not beat random
inspection as a screening rule. The tool shows evidence and position; it gives no alarm.

**Then what is the use of it?**
Three things an operator can use today: (1) one place where a flight's events are in time order with the quality
of the evidence, (2) settings checked against an approved configuration, (3) a signed history of who checked what.
The study's main value is the negative results and the ten-item checklist for anyone who builds log diagnostics.

**Why no machine learning in the tool, when the paper trains models?**
The models were the object of study. They failed at attribution, and a published detector we re-implemented fell
from AUC 0.94 to 0.63 once whole days were held out. Putting such a model in the tool would repeat the error the
paper documents.

**Why no AI or language model?**
We tested language-model review panels. On 97 real crash cases no panel beat a plain rule, and one compromised
reviewer changed between 16 and 89 of the 97 verdicts. So every number in the tool comes from fixed code.

**The demo drones all crashed. Is that a fair fleet?**
It is not a fleet and we do not present it as one. It is the study's within-drone sample, chosen because each drone
has a rated crash and earlier flights, which is what the within-drone finding is about. A fair fleet needs a
partner operator's logs; that is declared future work (prospective test and user study).

**Who said those flights were crashes?**
The uploader, in the public archive. The paper shows that label is weak: independent reviewers disagreed on whether
a log contains the crash (the usual tilt rule misses 7 to 50% of multicopter crashes depending on the rater). The
tool never uses the label.

**What does "Estimator rejected compass data" mean? Is that a fault?**
It is the autopilot's own report that a sensor reading disagreed with its estimate for that long. The tool repeats
it with its time. It does not say why, and it is not counted as a fault.

**Where does the "public PX4 flights" comparison come from? Is it a safety limit?**
From the study's downloaded public logs: flights their pilots rated good or great, real hardware, vehicles with no
crash-rated log, at most five per vehicle (292 flights, 141 vehicles). It is not a limit: in the study, vibration was
not shown to beat random inspection, and settings did not differ between crashed and normal flights. It tells an
operator what ordinary PX4 flying looks like.

**Is the vibration value comparable between drones?**
Only between drones whose logs report the same measurement, and only when at least four share it. Units differ
between autopilots and firmware versions; the "Measured as" column shows which one.

**Could someone tamper with the signed record?**
Editing or deleting an entry breaks the chain and the check says where. Someone with the private key and the
database could rebuild the whole chain; a copy of the heads file kept by someone else exposes that. Timestamps
come from this computer's clock, and no trusted hardware is involved.

**Has it been tested with real operators?**
No. 776 automated tests pass and it was checked by hand on a desktop. No operator has used it, and no headset test
has been done. The paper says so.

**Does it work with ArduPilot?**
Log reading, the timeline, settings and vibration work for ArduPilot `.tlog` and `.bin` logs and are covered by
tests. The sensor-health lines are read from PX4 logs only. The study itself used PX4 logs only.

## 4. Known limits of this demonstration

- The demo fleet is 8 unrelated public airframes, all with a crash-rated flight. It shows the tool working on real
  logs; it is not evidence for any claim.
- The changed settings file and the three missions are made up by the seed script.
- The local database location is set in `.env`. If it points into `/tmp`, macOS can wipe it; the signed record will
  then (correctly) report that earlier entries are missing. Keep the database somewhere permanent before a demo.
- The 3D view and the Quest headset path were not re-checked for this guide.
