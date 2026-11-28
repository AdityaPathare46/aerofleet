# Defending AeroFleet: hard questions, honest answers, and where to show the proof

For the final-year project viva. Each answer is short enough to say aloud; **Show** says where to prove it, live.
Numbers are from the paper (`docs/paper/latex/main.tex`) and the result files; `python docs/paper/check_numbers.py`
checks the key ones. Read `docs/DEMO.md` for the walk-through itself.

**The rule for the room: never claim more than this file says.** If a question goes past what we tested, say
"we did not test that" and name the closest thing we did test. Examiners respect a clear limit far more than a guess.

## The 60-second answer: "What is your project?"

AeroFleet is an independent safety assurance and regulatory records platform for small-to-mid Indian PX4 and ArduPilot
drone fleets — Drone-as-a-Service operators, RPTO training academies, and Lead Fertiliser Company / agricultural drone
service aggregators — with a built-in Indian agricultural spraying compliance module (Namo Drone Didi approved 15,000
drones, about 500 delivered under the scheme by March 2026 and 1,094 to SHGs in all, flown by pilots with 5 + 10 days of
training). Every morning it gives field pilots a one-glance go/no-go board in English, Hindi or Marathi; before a job it
checks routes against restricted airspace and battery against wind with realistic airframe profiles; after flying it turns
each log into an Ed25519-signed, offline-verifiable record for insurers and the mandatory 7-day CIB&RC Annexure-I spray
report. What makes it distinctive is the empirical evidence behind every design boundary: we tested what flight logs can
and cannot show on 590 crash logs from a 479,547-log public archive, pre-declaring every test in git first. Logs cannot
assign blame (0.47 balanced accuracy, chance 0.50), so AeroFleet never does; tuning/configuration was the #1 expert-named
cause (26 of 94), so baseline drift and failsafes are checked first; vibration is not a validated screen, so it is shown
as context only.

## The live demonstration order (10 minutes)

1. **Overview** page: the use case and its numbers, the data, six findings, how each design choice follows (3 min).
1b. **Today's fleet** (fleet `pune-agri [Simulated SITL]`): 6-drone simulated ArduCopter 4 m Pune spraying fleet with
    shared baseline, verified/unverified UINs, every status (`AGRI-01/02` No rule fired, `AGRI-06` Check first for
    compass health & expiring insurance, `AGRI-03/04/05` Do not fly for failsafes off, mid-flight geofence disable, and
    grounded motor-failure incident), plus **Spray register** (live Nov 2026 forms, 5.61 acres upper-bound swath) and
    3D/VR planned-vs-flown spraying replay (2 min).
2. **Proof** page: press *Recompute the results*, then *Run five attacks on a copy* (2 min). This answers most
   "how do we know" questions before they are asked.
3. **Fleet Assurance**, fleet `demo`: real public PX4 logs — a flight review (timeline, evidence quality), a drone's
   History, the public comparison column, and optional RFC 3161 TSA-timestamped receipt (2 min).
4. Fleet `demo-settings`: the blocked failsafe and the public-flights column (1 min).
4b. **Route check** ▸ *Try 5 demo missions*: one clear, one needing permission, two not permitted, one conflict (1 min).
5. Settings page: "Language models: none" (30 s).

If the app fails during the viva: the same numbers come from `python -m pytest -q --no-cov tests/unit/test_evidence.py`
and the figures are in the paper. Have the paper PDF open in a second window.

---

## A. The problem and the contribution

**Q1. What is new here? People have analysed drone logs before.**
Four things, all measured: (1) the first pre-declared test of whether pilot-vs-aircraft blame attribution can be shown
with public flight logs and the labels that exist — it cannot (0.47 balanced accuracy on 112 held-out crashes; blind
relabelling agreed with uploaders at κ = −0.10, and the rule failed against expert forum labels too at BA 0.38; note
that 0.47 balanced accuracy and 53/112 wrong = 47% are two different metrics that happen to coincide, and we do not lean
on the post-hoc rule v2 0.68 on 31 answered crashes); (2) an audit showing how much apparent crash-detection skill comes
from evaluation choices (AUC fell by 0.21 [0.06, 0.34] across 32 settings; a published detector fell from 0.94 to 0.63
when whole days were held out); (3) a ten-item reporting checklist and a records tool designed from those limits (whose
green status explicitly reads **"No rule fired — records check only, not an airworthiness sign-off"** because it flags
crash flights only ~1.36× as often as ordinary flights); (4) a normal-flight model trained on 1,121 public flights of
401 vehicles, tested on unseen drones and on real injected faults, used as context only.
*Show:* Overview ▸ findings; paper Table 1 (related work) and Section 6.

**Q2. Isn't a negative result a failed project?**
No. A negative result that is declared in advance and adequately tested is a finding: it stops people trusting
verdicts the data cannot support. In a safety context, "this cannot be done from logs" is exactly what an
investigator or insurer needs to know. The tool is the positive output: it does what the data *can* support.

**Q2b. Your earlier version was a delivery project and was called weak. Why is this different?**
The delivery dispatcher answered a question nobody had measured. This version starts from a real, funded user group
(agricultural drone service providers; Namo Drone Didi alone approved 15,000 drones, about 500 delivered by March 2026) and from measured facts: what crash logs
can and cannot show, which cause experts find most often, how well each check performs on real logs. Every design
choice traces to a number, and the Proof page recomputes those numbers live.

**Q2c. Couldn't an AI have generated this app?**
An AI can write a screen. It cannot produce the evidence: the 479,547-log archive index, 590 crash logs downloaded and
analysed, tests declared and committed before they ran, an independent blind reviewer, a reference of 292 public
flights read with our own code, injected-deviation tests on 40 real flights. Those took the study; the app is how
an operator uses its results. We used an AI assistant for code and drafting and declared it.

**Q2d. Why agriculture?**
It is where the drones are going in India now (government-funded, at scale), its operators are the least
experienced, it flies near people and crops with chemicals, and it has hard reporting and insurance obligations. The
checks themselves are general: any PX4 or ArduPilot fleet can use them.

**Q3. Who would use this — and why haven't you tested it with real operators yet?**
Fleet supervisors at Indian commercial DaaS operators, RPTO training academies, and Lead Fertiliser Company / agricultural
drone aggregators (settings governance, morning records check, 7-day CIB&RC spray register, 24 h / 48 h accident records),
plus maintenance engineers and insurers. *Honest limit & why it is defensible:* no paying operator has deployed it yet and `pune-agri` uses simulated ArduPilot
SITL logs (**lab and simulation validation only**). In safety-critical software, offline empirical validation (590 real
crash logs, SITL firmware fault injection, false-alarm calibration, and tamper-proofing) must come *before* putting
unvalidated rules in front of pesticide-spraying pilots. Our **declared (git-committed) protocol document** for a
6-month prospective field study (`research/protocols/prospective_and_user_study.md`, not yet run) is the immediate next
stage once an RPTO or LFC partner approves field deployment.

**Q4. Why should a regulator care?**
EU and UK operators must keep operation and maintenance records for at least three years. In India, two overlapping
frameworks apply — both verified directly against the downloaded Government of India Gazette PDFs on 28 Nov 2026: (1)
**Drone Rules, 2021** (`G.S.R. 589(E)`, 25 Aug 2021, `egazette.gov.in/WriteReadData/2021/229221.pdf`, amended by
`G.S.R. 108(E)` on 11 Feb 2022 and in 2023) require a verified UIN (**Rule 14(1)**, Gazette p. 29), Type Certificate
(**Rule 8**, p. 28; exemptions **Rule 13**, p. 29), Remote Pilot Certificate (**Rule 31** / **Rule 34**, p. 31, renamed
from "remote pilot licence" by `G.S.R. 108(E)`), third-party liability insurance (**Rule 44**, p. 33), and an accident
report on Digital Sky within **48 hours** (**Rule 30 — "Mandatory reporting of an accident"**, Gazette p. 31; Rule 29 on
the same page is *"Right of way"*, confirming Mondaq's summary misnumbered Rule 30 as Rule 29); and (2) the **Aircraft
(Investigation of Accidents and Incidents) Rules, 2025** (`G.S.R. 829(E)`, 7 Nov 2025, under Bharatiya Vayuyan
Adhiniyam, 2024, `civilaviation.gov.in/sites/default/files/2026-05/aaib-rules-2025.pdf`; preamble amended by
`G.S.R. 647(E)`, 17 Jul 2026) explicitly cover unmanned aircraft with State design or operational approval (**Rule
2(1)(a)(ii) & Explanation (2)**, Gazette pp. 24-25), require **24-hour notification to AAIB and DGCA** by the remote
pilot-in-command (**Rule 4(1) & Proviso**, p. 28; Schedule Table 2 p. 42), and explicitly mandate that the sole
objective is **accident prevention, not apportioning blame or liability** (**Rule 3**, p. 28, aligned with ICAO Annex
13). AeroFleet tracks those credentials in the signed record, enforces expired insurance/RPC/UIN (IST date) on *Today's
fleet* (with a two-tier record-age rule: non-blocking note at 15–90 days for seasonal sprayers, escalating to *Check
first* past 90 days so a years-old log never stays green), and generates a one-click printable **Accident Record
prepared for Digital Sky & AAIB** showing both the 24 h and 48 h statutory windows with exact Gazette citations, the
statutory-definition scope caveat, and a dynamic check on `type_certificate_no` (flagging "may not apply" on the 24 h
AAIB line when no State design/operational approval is on record per Rule 2(1)(a)(ii) Explanation (2)) — matching
India's no-blame principle while never claiming to be an official DGCA/AAIB form.

## B. Data

**Q5. Where does the data come from, and are you allowed to use it?**
PX4 Flight Review (review.px4.io), where PX4 users upload logs publicly: 479,547 logs indexed on 20 October 2026,
442,929 from real hardware, 38,320 vehicles. We release derived features and code, not the raw logs (they stay on
the public site, referenced by identifier). Forum text is not redistributed. *Show:* Overview ▸ The data.

**Q6. Uploader labels are self-reported. How can you trust them?**
We don't, and we measured how far they can be trusted: a blind independent reviewer agreed with uploaders no better
than chance (κ = −0.10 [−0.34, 0.17]); the standard tilt rule misses 7 to 50% of crashes depending on the rater; and
pilot-rated logs show a crash-like tilt half as often as aircraft-rated ones (23% vs 45%), so a classifier could
separate the labels without learning a cause. We also used a second, independent label source: 148 crashes
diagnosed by PX4 experts on the forum, coded twice blind (κ = 0.81 on the conclusion). The rule was no better there.

**Q7. Isn't the archive biased? People upload crashes to ask for help.**
Yes, and that is why we never estimate a crash rate for drones in general. Comparisons are within the archive:
crash against matched non-crash drones (same hardware, firmware and vehicle type), and crash flights against the same
drone's earlier flights. The base rate we quote (crash-rated logs on 0.741% of vehicles) is described as the
archive's, not the world's.

**Q8. Only 590 crashes. Is that enough?**
Enough to rule out large effects, not small ones, and we say which. For pilot-vs-aircraft, a permutation analysis
showed about 80% power only for AUC 0.72 or more, so we claim "no usable separation", not "no separation at all".
The within-drone result excludes a rise as large as the between-drone difference (upper bound 0.58).

## C. Method and statistics

**Q9. What does "declared before running" mean, and how can we check it?**
Each test's hypothesis, data selection and pass mark were written into the script and committed to git before the
data was downloaded or the test run; the result was committed after. *Show:* Proof ▸ each result shows its
declaration commit and its result commit, minutes or hours apart (for example `af6fab2` 17:28 → `da92ec3` 17:40 on
20 October 2026).

**Q10. You control the git history. Couldn't you fake the dates?**
On our own machine, yes, and we say so. The repository is public on GitHub and was archived by Software Heritage on
25 October 2026, which fixes everything up to that date independently of us; the paper states that tests declared
before then rest on author-controlled timestamps. Analyses added after the declared protocol are marked † everywhere.

**Q11. Why balanced accuracy and not accuracy?**
The classes are unequal (more aircraft-blamed than pilot-blamed crashes). A rule that always says "aircraft" would
score high accuracy and learn nothing; balanced accuracy averages the recall of both classes, so chance is 0.50.

**Q12. What is "leakage" and why does it matter?**
Information in the test that would not exist when the model is used. Two kinds mattered here: the crash itself in
the log (impact, tumbling) making a "detector" look good, and the same drone or the same day appearing in training
and test folds so the model recognises the aircraft, not the fault. Grouping folds by vehicle was the one factor
that clearly mattered (AUC drop 0.062 [0.034, 0.087]).

**Q13. You ran many tests. Multiple comparisons?**
Declared tests are Holm-corrected within their family. The between-drone vibration result is reported three ways:
Holm-adjusted p 0.016 as declared, 0.08 when clustered by airframe, 0.45 with operator sites weighted equally. We call
it suggestive because of the last two, not significant because of the first.

**Q14. Why a mean scaled rank instead of a t-test?**
Vibration units differ between firmware and are heavily skewed; ranks within matched sets need no shared scale and
no normality. The p-value comes from the exact null (each drone's rank uniform over its possible positions), drawn
100,000 times. *Show:* Proof ▸ the between-drone p = 0.0023 is recomputed from that exact null.

**Q15. Did you try machine learning? Deep learning?**
Yes, twice, for two different jobs. (1) As the object of the study: logistic models, boosted stumps, depth-3 trees and a
re-implemented convolutional fault detector all failed to tell pilot from aircraft or held up only under weak testing
(the detector fell from AUC 0.94 to 0.63 with days held out). So no crash predictor is in the tool. (2) As a tool
feature: the **normal-flight model**, gradient-boosted trees trained on **1,121 ordinary public PX4 flights of 401
vehicles**, which learns the expected range of vibration and battery voltage drop for a drone like this one flown like
this. It uses no crash labels, so it avoids exactly what the study found unreliable. *Show:* Proof ▸ *Show the model
and its tests*; any flight review ▸ "Compared with healthy flights of similar drones".

**Q15b. How was the model trained and tested?**
Data rules, model settings and three pass/fail tests were committed before any training log was read (`de4382a`).
Vehicles were held out (GroupKFold by vehicle), our own checklist item 2. Results: the middle estimate beat always
guessing the median (error 48% lower for vibration, 15% for battery); on 220 real flights with injected motor faults
(RflyMAD) the score rose after the fault (p = 0.0005); and the first calibration test **failed**: the "5-95%" range
held only 73% of unseen drones' flights.

**Q15c. One of your tests failed. Isn't that bad?**
It is the most useful result. It showed the ranges were too narrow for drones the model had never seen. We declared a
fix before running it (conformal calibration, `76db013`), marked it as added after the failure, and it passed: the
widened range holds 90.4% and 90.8% of unseen flights. The app uses the widened range and the Proof page shows both
the failure and the fix. A model reported only with its successes would be the thing to distrust.

**Q15d. Does the model detect faults?**
No, and we say so. The score rose after injected motor faults, but the shift was small (no flight crossed its range),
sensor faults raised it too and fault-free flights fell at the same point in the flight, so part of it is the phase of
flight. It is context for an inspector ("this battery drained 7.5 times faster than similar flights") and never changes
a readiness verdict.

**Q15e. Is that not "AI in the decision path"?**
No decision uses it: it is shown as context, and the readiness verdict comes only from fixed rules. It is also not a
black box in the product: the trees are exported to a file and evaluated in plain Python, reproducing scikit-learn to
3e-14, so the no-AI test still passes (no ML library is reachable from the product code).

## D. The results

**Q16. If logs can't attribute blame, what *can* they show?**
What happened and when (mode changes, the pilot taking over, battery, GPS, the autopilot's own sensor reports),
whether the drone flew its plan, and how a drone compares with its own history. That is exactly what the tool shows.

**Q17. Drones that later crashed vibrated more. Why not use that to predict crashes?**
Three reasons: (1) on the newer accelerometer metric the signal **did not replicate** (pooled rank 0.58, p = 0.25; new
cases only 0.50, p = 0.58 — consistent with a metric or firmware-era artifact); (2) against 412 non-crash drones,
flagging the top 10% gave a lift of only 1.77 [1.00, 2.60], spanning 1.00 (random inspection); and (3) within a drone,
the crash flight showed no rise (mean rank 0.48, p = 0.67). So the tool shows vibration as context only, with no alarm
line. *Show:* Fleet Assurance ▸ vibration table (no flags) and History; Proof ▸ results 2–4.

**Q18. Your re-implemented detector didn't reach the published accuracy. Isn't the comparison unfair?**
Fair point, and the paper says so. The published code and weights were not released, so we fixed the open choices
before training and declared them. The finding does not depend on matching their number: our own model's accuracy
dropped by 0.33 [0.28, 0.38] between random windows and held-out days. The point is the drop, not the level.

**Q19. What about the language models? Everyone is using them.**
Two reasons — one empirical on real logs and one architectural. Empirically, lead with the **blind test on 97 real
crash logs** using four **small local models (3–4B parameters, not frontier cloud models)**: the fixed rule itself was
right in only 26 and wrong in 62 (so it was not a strawman winner either), no voting panel beat it, one compromised
reviewer flipped **16 to 89 of the 97 verdicts**, and Mac vs RTX panel agreement was only **16 of 33**. Architecturally,
safety-assurance records must be **deterministic, offline-auditable, reproducible across machines, and free of
prompt-injection paths** — none of which an LLM can guarantee. That is why AeroFleet uses zero AI in its decision path.
*Show:* Settings ▸ "Language models: none"; the static no-AI import test.

## E. The tool

**Q20. You say no AI, but the code has an "agents" folder and a "council".**
Those belong to the earlier prototype, which this project replaced after an outside review. They are hidden unless
"Show legacy screens" is switched on, and their background workers start only with `AEROFLEET_LEGACY_AI=1`. An
automated test follows every import from the product code and fails if it can reach any AI agent, the language-model
panel or an ML library. *Show:* `tests/unit/test_no_ai_in_decision_path.py` (it also shows the same walk *does* find
`ollama` when started from the old agent code, so it can fail).

**Q21. How is the vibration number computed?**
The 95th percentile of the autopilot's own vibration metric over the flight, leaving out the last 10 seconds so an
impact cannot inflate it. A drone's value is the median over its last five reviewed flights. Drones are compared only
with drones of the same kind (multirotor, fixed wing) whose logs report the same measurement.

**Q22. Where does the "public PX4 flights" comparison come from? Is it a limit?**
292 public flights from 141 vehicles that never had a crash-rated log, rated good or great by their pilots, at most
five per vehicle, read with the tool's own code (`tools/build_public_reference.py`). It is a description, not a limit,
and the screen says so. Its value: a small operator with one to three drones gets a comparison at all.

**Q23. What does "Blocked" mean on the settings screen? Do you stop the drone?**
No. AeroFleet never flies or commands an aircraft (the optional bench inspection on the Drone register page reads a
flight controller's settings over USB and changes nothing). "Blocked" is a status: a safety-critical setting (a failsafe, a geofence,
battery limits) differs from the fleet's approved configuration and nobody has approved the change. An operator can
approve it with a written reason, and the approval is signed into the record.

**Q23b. What is the map for? This used to be a delivery project.**
The delivery dispatcher was dropped when the project was re-scoped; its screens are hidden as legacy. The map is now a
pre-flight **Route check**: load the missions planned for a period and each route is checked against red and yellow
airspace, the 120 m limit, and the other planned routes, then signed into the record. *Honest limit:* full local zones
(airports + military/restricted sites) are loaded for Pune and Mumbai; across the rest of India, 37 civil airport
perimeters (including Baramati) are checked using MoCA's September 2021 airspace map distances with a 1.5 km perimeter
allowance around each airport reference point: **0–5 km RED**, **5–8 km YELLOW at any height**, and **8–12 km YELLOW
only above 60 m (200 ft)** (so 4 m agricultural spraying passes in the 8–12 km band are not over-restricted). Routes
outside mapped zones return "not checked" (`UNCHECKED`), never "clear", and the screen states plainly that this is an
approximation, not the official Digital Sky map. *Show:* Route check ▸ *Try 5 demo jobs*.

**Q23c. How does "Today's fleet" decide, and why trust it?**
Fixed rules only, each shown with its reason: **Do not fly** if a safety-critical setting changed without approval, there
is no UIN on record (Rule 14), third-party insurance has expired (Rule 44, IST date), the assigned pilot's RPC has expired
(Rule 31, IST date), or the drone is grounded in the maintenance logbook after a reported incident/crash without a later
inspection clearance. **Check first** if a flight-limit setting changed, settings have not been compared with an approved
baseline (`NO_REFERENCE`), a failsafe or safety check is switched off (ArduPilot failsafes & `ARMING_CHECK=0`; PX4
`NAV_RCL_ACT=0`, `COM_LOW_BAT_ACT=0`, `GF_ACTION=0`, `CBRK_SUPPLY_CHK=894281`; PX4 firmware-default `CBRK_IO_SAFETY=22027`
is shown as a non-blocking setting note and `CBRK_FLIGHTTERM` is not checked), the UIN is unverified, insurance expiry is
missing on a compliance record or expires within 14 days, settings were never checked, the last flight was a partial
CSV/GPX export, or the last flight's log shows sustained in-air warnings (sensor or GPS complaints lasting 3 s or more
while airborne — altitude > 2 m or smoothed 2 s groundspeed ≥ 1.5 m/s — an airborne autopilot error report, a mid-air
critical battery drop > 15 s before touchdown, a safety-critical setting changed in flight, or leaving the plan). A
low-battery landing (< 10% near touchdown) is shown as a pilot note, not a reason, and vibration / the learned model are
context only. *Show:* Today's fleet ▸ fleet `pune-agri [Simulated SITL]`.

**Q23d. What happens in a real season with this tool?**
Morning: *Today's fleet* says which drones can fly. Evening: the operator selects all the day's logs at once; each is
matched to its drone by the flight controller's own id, reviewed, signed, and scored against the learned model. When
work is done on a drone it goes into the *maintenance logbook*, and AeroFleet shows the flights before vs after
("vibration fell 58%"), with the caveat that a few flights cannot prove a fix. Weekly: *Fleet trends* shows flying
hours, warnings per flight and which drones drift from what is expected. For reporting: a CSV operations log, one row
per flight with the UIN and the fingerprint of its signed review.

**Q23e. How can you be sure a log is matched to the right drone?**
PX4 logs carry the flight controller's unique id. The first time, the file name tells AeroFleet which drone it is;
after that the id is recognised. A log with an unknown id and no drone in its name is not reviewed, and the screen
says why: a log is never guessed onto a drone. If a flight controller is moved to another airframe, the operator
names the file again. (ArduPilot logs carry no such id, so they are matched by file name only.)

**Q24. How do you know the planned-versus-flown check works?**
We injected known deviations into 40 real PX4 flights: it found 36 of 40 sideways deviations of 35 m and 39 of 40
upward deviations of 20 m, with no false alarms on the untouched flights when plans had a waypoint every 5 s (9 of 40
with 10 s, from fast flights cutting corners). *Limit:* the public archive holds only six real missions with their
plans, too few for a real-world false-alarm rate.

**Q25. The "describe a problem" search: does it diagnose?**
No, and we measured why not: on 96 expert-diagnosed crashes, its best guess matched the expert 22% of the time, below
the 27% of always guessing the most common cause. So it orders a checklist by how often experts found each cause and
shows similar past threads to read. It says this on screen.

**Q26. How fast is it?**
On 36 real PX4 logs of 0.9 to 92.8 MB on a laptop: median 0.23 s per review; the largest (92.8 MB, a 28-minute
flight) in 2.44 s (`docs/measurements/review_speed.md`).

**Q27. What happens with a corrupted log, or the wrong file?**
It gets a clear message, never a crash: tested with empty files, random bytes, a mission file renamed as a log and
a photo. A log cut off mid-flight (as a crash often does) is reviewed from the part that was written; nothing is
invented for the rest. *Show:* `tests/integration/test_assurance_api.py`.

## F. Security and integrity

**Q28. How does the signed record work?**
Each result is hashed (SHA-256), the entry carries the hash of the entry before it (a chain), and the entry is signed
with the install's Ed25519 key. Changing, deleting or reordering anything breaks a hash, a link or a signature, and
the check says which entry. *Show:* Proof ▸ *Run five attacks on a copy*: all five caught, the real record untouched.

**Q29. Can't someone with access just rebuild the whole chain?**
With both the private key and the database, yes, and we say so. The defence is the heads file: each new head is also
written to a separate file meant to be kept by someone else (an auditor); a rebuilt chain no longer contains the old
heads. Timestamps come from the computer's clock; there is no trusted hardware. The record proves the history was
not altered afterwards, not that the uploaded file was genuine.

**Q30. Can an auditor check it without trusting your software?**
Yes: *Export for an auditor*, then `python tools/verify_ledger.py export.json` needs only Python and the
`cryptography` package.

## G. Engineering quality

**Q31. How do you know the code is correct?**
776 automated unit and integration tests, run before every commit, plus TypeScript strict typechecking. Beyond unit tests:
the numbers in the paper are checked against the result files (`check_numbers.py`, 30 checks), the paper's headline
results are recomputed and compared in a test, and the "no AI" claim is enforced statically across all 2.0 routes and
assurance modules. *Show:* `python -m pytest -q --no-cov tests/unit tests/integration`.

**Q32. Why Python and React? Why not a mobile app?**
Python has the standard log libraries (`pyulog` for PX4, `pymavlink` for ArduPilot); the desktop app is a web front
end in a Tauri shell, so the same screens run in a browser. Reviews happen on the ground after flight, where a laptop
is the normal tool.

## H. Limits and ethics

**Q33. What are the biggest weaknesses of this work?**
(1) Public, self-selected data with self-reported labels; (2) no operator has used the tool; (3) PX4 only for the
study (the tool also reads ArduPilot); (4) the between-drone vibration signal is suggestive only; (5) the
re-implemented detector did not reach its published accuracy. Each is stated in the paper's threats section.

**Q34. Did you use AI to write this?**
Yes, an AI assistant helped write analysis code and draft text, declared in the manuscript as the journal requires.
Every analysis was declared and run by us, every number is checked against its result file, and we can recompute the
headline results live. Authorship and responsibility are ours.

**Q35. Any ethical issues with the data?**
The logs are public and uploaded voluntarily. We store no locations: take-off positions used for the operator
clustering test were computed in memory and only cluster sizes reported. Forum text is not redistributed; the blind
reviewer's workbooks are not released.

**Q36. What would you do with six more months?**
Run the declared prospective study with a partner fleet (8+ drones, 6 months), a user study with 12 to 16 operators
under ethics approval, real-mission false-alarm rates from a fleet's own plans, and a headset test of the VR replay.

## I. Market, competitors and the latest features

**Q37. How many Drone Didi drones are actually flying? Is 15,000 real?**
15,000 is the approved target (2023-24 to 2025-26, Rs 1,261 crore), not delivery. By March 2026 the government reported
500 delivered under the scheme itself and 1,094 given to women SHGs by lead fertiliser companies in all. DGCA had
41,196 drones of all kinds registered by July 2026. So the fleets are small and new, which is the point: a fleet of one
needs the public reference and the learned model, not its own history.

**Q38. Why not Airdata, DJI FlightHub or AeroGCS?**
Airdata is a mature global logbook, but has no India UIN or CIB&RC SOP logic and no offline-verifiable signed record.
FlightHub serves DJI hardware only, and DJI native logs are encrypted. AeroGCS is the closest Indian rival and ships with
many spraying drones, but it is the manufacturer's own system, not an independent third-party audit record. FlightMD
(open source) is closest in spirit; AeroFleet adds baseline approvals, a morning go/no-go board, the 7-day spray register,
an offline-verifiable Ed25519 ledger with external receipts, and a pre-declared (git-committed) empirical study. Honest weak points:
full telemetry/settings/vibration checks require PX4 or ArduPilot (closed controllers are limited to CSV/GPX exports),
no mobile app yet, and no live operator field trial yet.

**Q39. Who would pay?**
Probably not the self-help group. Lead fertiliser companies, which the scheme asks to help with repair and
maintenance of many SHG drones, and service aggregators are the natural buyers of a fleet-wide view. Insurers are a
later conversation. Willingness to pay is unproven.

**Q40. What does the spray register actually save the operator?**
The SOP asks for its Annexure-I form within seven days of each spraying. A log already knows the date, start and end
time, height and speed, moving airborne distance, and often the spray direction; the drone's previous form knows the
sprayer and track spacing (`5-13`); the logbook knows the last calibration. From moving airborne distance × track spacing
AeroFleet also computes a **geometric swath area estimate (acres and hectares)** with an explicit caveat that turns are
included and no flow sensor is read — directly answering the acreage metric agri-operators track and bill on. Overdue
7-day spray forms also surface as a non-blocking compliance link on *Today's fleet* without altering physical airworthiness
verdicts. *Show:* Spray register (fleet `pune-agri`) ▸ 5.61 acres total across 5 active Nov 2026 flights, open `AGRI-03` with three SOP problems.

**Q41. Why are there no wind or height limits in the spray checks?**
Because the SOP gives none: it says "appropriate" wind speed, temperature, humidity and height. Inventing a number
would be the kind of overclaim the study argues against. The checks that exist quote a sentence with a number or a
fact in it: 24 h notice, 100 m from water, PPE, expiry date, UIN.

**Q42. The height in the form says 3 m. Above what?**
Above the take-off point, from the log. The log cannot see the crop canopy, so the form labels it and lets the
operator correct it; if the entered value differs from the log by more than 1 m, the form keeps both and says so.

**Q43. Why Hindi and Marathi, and are the translations right?**
The pilots are new operators, many more comfortable in Hindi or Marathi, and the industry review named "English only" as a
weakness against Indian competitors. Only *Today's fleet* is translated, because it is the screen a pilot reads. The
verdicts come with a code, so the rule never changes with the language. Every Hindi and Marathi line in `readinessText.ts`
(all 17 rule codes + labels) has verified key parity (`test_readiness_translations.py`) and was read by a Marathi-native
team member on 27 Nov 2026; honest limit: an independent outside reader per language (especially for Hindi) has not yet
signed off (`CRITICAL_REVIEW_2026-11-27.md`, H3).

**Q44. You said the operator can rebuild the whole chain or fake the computer's clock. What did you do about it?**
Two layers: (1) A **signed receipt** handed weekly to someone outside the operator's control (the fertiliser company,
aggregator, or insurer); checking it (`Check a receipt` or `verify_ledger.py --receipt`) catches a chain rebuilt even
with the operator's own key. (2) **Optional RFC 3161 trusted timestamping** (`Save TSA-timestamped receipt`,
`GET /ledger/receipt?tsa=true`): AeroFleet sends **only the 32-byte SHA-256 hash** of the receipt to an independent
Time-Stamping Authority (DigiCert; the only allowed URL), embeds the signed CMS `TimeStampResp` token, and verifies its
messageImprint digest, nonce, CMS signature, ESS signing-certificate binding, `id-kp-timeStamping` EKU, validity at
`genTime`, and the chain to a **pinned root** (`aerofleet/assurance/data/tsa_roots.pem`, DigiCert Trusted Root G4; an
auditor may pass their own bundle with `verify_ledger.py --tsa-ca`). A token signed by a self-made CA is rejected (the
first version accepted it: critical review 27 Nov, C2). So the receipt's date no longer depends on the operator's clock,
and no flight data leaves the machine. Limit: it proves the receipt existed by that time, not that the flights in it are
genuine.
In addition, `GET /ledger/verify` now cross-checks stored `FlightReview` and `SprayForm` rows in SQLite against their
signed ledger hashes.

**Q45. The forum numbers say 96 in one place and 94 in another.**
94 threads blamed the aircraft alone, 2 blamed both pilot and aircraft. The configuration count (26 of 94) is over the
94; the troubleshooter test uses all 96 that named an aircraft cause, aircraft alone or both.

**Q46. Is "0 of 40 false alarms" true in general?**
Only with a waypoint every 5 s. With 10 s spacing the same check gave 9 of 40 false alarms, from fast flights cutting
corners of plans built from the track. Quote the spacing with the number.

**Q47. Is the draft Civil Drone Bill law?**
No. The *Draft Civil Drone (Promotion and Regulation) Bill, 2025* was released for public comment on 16 September 2025
and remains at the draft stage (not yet introduced or passed in Parliament as of Nov 2026). The **Drone Rules, 2021**
(`G.S.R. 589(E)`, 25 Aug 2021, as amended by `G.S.R. 108(E)` in 2022 and in 2023) remain in force, alongside the
**Aircraft (Investigation of Accidents and Incidents) Rules, 2025** (`G.S.R. 829(E)`, 7 Nov 2025, under the Bharatiya
Vayuyan Adhiniyam, 2024; preamble amended by `G.S.R. 647(E)`, 17 Jul 2026), which extend 24-hour no-blame accident
reporting (Rules 3 & 4(1), Gazette p. 28) to State-approved unmanned aircraft (Rule 2(1)(a)(ii) & Explanation (2), pp. 24-25).

**Q48. A pilot describes a problem. How do you find similar flights, and is that a diagnosis?**
Two ways, both shown as places to look. Words: BM25 against what uploaders wrote about their own flights in the public
PX4 archive, with the uploader's rating. Logs: once the pilot picks one of their reviewed flights, the public logs on
this computer whose logs show the same signs, computed by the same rules as the pilot's own review. We first also
matched logs from the words (a fixed word list mapping "compass", "GPS", ... to signs) and tested it, declared before
running: on 514 public flights the signs a description named were in that flight's own log 15.8% of the time, against
18.0% with descriptions shuffled. It failed, so we removed it. Only battery words pointed the right way (about 3x), seen
after the test, so not used. Flights with similar log signs did share outcomes a little (47.9% against 40.2% crashes
among look-alikes, p = 0.0005), in a crash-heavy sample, so it is not a risk score. Not a diagnosis: our troubleshooter test showed words guess the expert's cause less often than always naming
the commonest cause, and two flights with the same signs can have different causes. *Show:* Fleet Assurance ▸
Something wrong? ▸ type "compass error, it circles" ▸ Search the public log archive.

**Q49. Which flight controllers can it read?**
PX4 and ArduPilot logs in full, and any MAVLink autopilot through its ground station's .tlog. For other controllers
(DJI Agras, closed agricultural controllers) a CSV export or a GPX track, which give position, time and, in a CSV,
battery, GPS and mode: enough for the timeline, the spray form and the operations log, not for settings or vibration.
DJI flight-record CSVs are tested on three real public DJI Mini 4 Pro flights: heights match the files' own maximum
column, and modes, battery and satellites come through. Testing on real files found four faults that our made-up test
files had missed; that is why we tested. Airdata's export layout is still untested on a real file.

**Q50. What does VR add to a spraying-drone tool?**
One job: a flight debrief. A trainer puts a reviewed flight on a 3D table and shows the pilot where and how high it went
against its plan. Whether 3D actually helps is tested, not assumed: a declared study (research/vr_study/PROTOCOL.md)
has 12 students judge real flights with known injected deviations on a 2D map and height profile and on the table in a
Quest 3, counterbalanced, with the answers fixed in advance. *Then give the result, whatever it is.* If 3D was no
better, VR is a presentation and training aid and we say so.

**Q51. Is that study fair to the 2D view?**
Same flights drawn the same way, no warnings or colours in either; the 2D height profile is the one mission planners
show (height against the share of the route covered). Each participant sees different flights in each view, and half
start with the headset. The trials, the key, the counterbalancing and the analysis were committed before the first
participant.

**Q52. Did you ever run it on a real autopilot?**
On the real ArduCopter flight code, yes: ArduPilot SITL runs the exact firmware that flies on a Pixhawk, with a
simulated quadcopter, and writes the same DataFlash `.bin` log. We flew a spraying mission at 4 m near Pune, 8 scenarios,
3 runs each, declared first (`research/sitl_check/PROTOCOL.md`). In v1: caught every time were GPS lost for 20 s, low
battery, geofence switched off in flight, and no false alarm on normal flights or in 8 m/s wind; S1 failed its initial
expectation because ArduPilot ships with `BATT_FS_LOW_ACT=0` by default, and S6/S7 exposed that we did not yet read
ArduPilot's onboard `ERR`/`MAG`/`XKF4`/`ATT`/`RCOU` health records (fixed and retested in v2 below). What SITL cannot
give: real sensor noise and real frame vibration.

**Q52b. And after that? You fixed things after seeing the results. Isn't that cheating?**
The first results stand as recorded. We then changed the product (failsafes switched off are flagged whatever the
baseline says; the ArduPilot reader now reads the autopilot's own error reports, compass health, estimator test ratios,
tilt and motor saturation), declared a retest with new expectations, and flew fresh flights over fields never flown
before. All 8 scenarios met in every run, and normal and windy flights stayed clean. The first logs were development
data; the retest logs were not seen before the declaration. "Motor held at maximum output" also appears when a battery
runs flat, so it marks a drone at its power limit, not a failed motor: we still name no cause.

**Q53. Why not a real Pixhawk on the bench?**
Time. SITL runs the same flight code and lets us put faults in on purpose with a known right answer, which a bench or
field flight cannot. It is the standard step before real flights; a bench session is in future work.

**Q54. How often does Today's fleet cry wolf — and does it actually catch real faults?**
We measured both in three stages on the product's exact code, being transparent about what is held out vs re-measured:
- **FA1** (`5f44b0b`, pre-declared, failed): the original rule flagged **28.8%** [23.9, 34.1%] of good-or-great public flights (pass mark ≤ 20%).
- **FA2** (`481987a`, pre-declared, passed on untouched held-out half H): restricting GPS/health complaints to ≥ 3 s in the air and demoting low-battery landings cut H good-or-great to **11.1%** [7.3, 16.3%] (from an H baseline of 25.3%).
- **SA1 + FA3** (`e9c4ebc`, re-measurement + descriptive sensitivity after adding airborne speed and mid-air battery rules, with **vehicle-cluster bootstrap CIs** matching Checklist Item #2):
  - **FA3 (descriptive, re-measured on shipped HEAD post-M3 on H — NOT an untouched held-out test, H1):** good-or-great **14.2%** (27/190; flight Wilson [10.0, 19.9%], **vehicle-cluster 95% CI [8.5, 20.7%]** — unchanged from `ffd0f27`, upper bound crosses 20%, so only the point estimate is under 20%); all H ordinary **27.1%** (155/572; unrated 33.5%, down 1 flight from pre-M3 27.3%); RflyMAD fault-free **0.0%** (0/50). **Board-level false-alarm rate (FA4) is unmeasured:** FA3 measures flight-log rules only, and two board-level rule changes came after FA3 (C1 settings + 90-day staleness).
  - **SA1 (descriptive, re-measured on shipped HEAD post-M3 — H2, because RflyMAD 53.8% had already been observed during D development):** RflyMAD injected sensor faults **53.8%** (106/197), motor faults **19.8%** (48/242); expert-diagnosed forum aircraft crashes **34.4%** (11/32, down 1 flight from pre-M3 12/32; pilot 2/4); archive real-hardware crashes **36.8%** (49/133), whereas crashed drones' *prior* ordinary flights flagged at **27.0%** (120/445, vs pre-M3 26.5%) — virtually identical to ordinary H (27.1%), meaning the shipped flight-log rules flag crash flights **1.36×** as often as ordinary flights and directly mirror the paper's within-drone null. Not yet measured on real spraying drones.

**Q54b. Why not train the model on spraying drones, with payload as an input?**
There is no data for it: no public log records payload weight, and the public archive has about 20 flights from 4
vehicles that mention spraying. So we measured loading from each log instead (the collective thrust the autopilot
commanded, which rises with weight and falls as a tank empties) and declared a test: battery-drop error must fall at
least 10%. It fell 6.2%, so by our own rule the model was not changed. Likely, public drones carry too little payload
for it to matter; on sprayers it may, and the code is ready for that retrain once we have sprayer logs.

**Q55. Some crashed drones show no flight-log warnings. Why does the green badge say "No rule fired" instead of "Ready"?**
Because calling it "Ready" would be unsafe: our own SA1 numbers (re-measured on shipped HEAD, descriptive) show the
flight-log rules flag only 36.8% of archive crashes and 19.8% of RflyMAD motor faults (about 1.36× as often as ordinary
flights). It is a **records check, not an airworthiness
sign-off**. So the UI explicitly labels the green state **"No rule fired"** and reminds the pilot to perform a physical
pre-flight check. If a drone's last reviewed flight is older than 14 days, a non-blocking **record-age note** warns the
pilot to confirm no unlogged flights occurred since (kept non-blocking so seasonal sprayers sitting idle between crop
cycles are not stuck on false-alarm Check first). And when an operator knows a drone crashed, recording `"Incident /
crash reported (grounded for inspection)"` in the maintenance logbook (as on `AGRI-05`) immediately turns Today's fleet
to **Do not fly** until signed inspection clearance is logged.

**Q56. Why didn't you turn the ML model into an onboard emergency-takeover controller?**
Because our own study proved ML fault detectors fail on unseen flight days (LeNet-5 dropped from AUC 0.94 to 0.63) and
even tuned log rules carry double-digit flag rates on healthy flights. Putting an uncertified ML model in charge of
mid-air takeover would force-land healthy drones into hazards and violate aviation safety principles. Onboard emergency
handling belongs to the flight controller's deterministic failsafes (ArduPilot/PX4 RTL/LAND); AeroFleet's job is to
verify before takeoff that those failsafes are enabled and uncorrupted.

**Q57. How does a desktop app and a Meta Quest 3 fit a rural SHG Drone Didi pilot?**
Two distinct personas. The rural field pilot needs only the one-glance morning `Today's fleet` board (English, Hindi or
Marathi) at the cluster hub. The **desktop app, baseline governance, 7-day spray register, and Quest 3 3D debrief table**
are for the **Lead Fertiliser Company / agri-drone aggregator supervisor, commercial DaaS operations lead, or RPTO chief
instructor** who manages maintenance, compliance, and pilot debriefing across a multi-drone fleet.

## Questions to answer with "we did not test that"

- "Does AeroFleet reduce crashes?" Not tested; that needs the declared 6-month prospective study protocol (not yet run).
- "Does it read native encrypted DJI logs?" No: DJI native logs are encrypted; AeroFleet reads converted DJI CSV exports
  (tested on 3 real DJI Mini 4 Pro flights) for position, battery, GPS, mode, spray forms and signed records — not
  settings, vibration or autopilot health checks.
- "Would vibration work as a screen on a bigger dataset?" Unknown. About 247 matched sets would be needed if the true
  effect is the smaller replicated one, more than the archive holds.
- "Is the VR replay proven to improve debriefing?" Built and tested in a browser with a pre-declared (git-committed) 12-person Quest 3
  study protocol (`research/vr_study/PROTOCOL.md`); not yet run on users unless noted from completed study results.
