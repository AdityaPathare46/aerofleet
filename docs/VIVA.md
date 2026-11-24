# Defending AeroFleet: hard questions, honest answers, and where to show the proof

For the final-year project viva. Each answer is short enough to say aloud; **Show** says where to prove it, live.
Numbers are from the paper (`docs/paper/latex/main.tex`) and the result files; `python docs/paper/check_numbers.py`
checks the key ones. Read `docs/DEMO.md` for the walk-through itself.

**The rule for the room: never claim more than this file says.** If a question goes past what we tested, say
"we did not test that" and name the closest thing we did test. Examiners respect a clear limit far more than a guess.

## The 60-second answer: "What is your project?"

AeroFleet is the safety and records back office for agricultural drone service providers in India. Namo Drone
Didi alone approved 15,000 spraying drones for women self-help groups (about 500 delivered under the scheme by March
2026, 1,094 to SHGs in all), flown by pilots with 5 + 10 days of training,
who rent flights to farmers. Every morning AeroFleet tells them which drones can fly and why; before a job it checks
the route against restricted airspace; after flying it turns each log into a signed, time-ordered record for the
insurer and the 7-day spray report. What makes it more than a dashboard is the evidence behind each design choice:
we tested what flight logs can and cannot show on 590 crash logs from a 479,547-log public archive, declaring every
test first. Logs cannot assign blame (0.47 balanced accuracy, chance is 0.50), so AeroFleet never does; the cause
experts named most was configuration (26 of 94), so settings are checked first; vibration is not a validated warning,
so it is shown as context only.

## The live demonstration order (10 minutes)

1. **Overview** page: the use case and its numbers, the data, six findings, how each design choice follows (3 min).
1b. **Today's fleet**: the morning go / no-go board, every reason linked to its evidence (1 min).
2. **Proof** page: press *Recompute the results*, then *Run five attacks on a copy* (2 min). This answers most
   "how do we know" questions before they are asked.
3. **Fleet Assurance**, fleet `demo`: a flight review (timeline, evidence quality), a drone's History, the public
   comparison column (3 min).
4. Fleet `demo-settings`: the blocked failsafe and the public-flights column (1 min).
4b. **Route check** ▸ *Try 5 demo missions*: one clear, one needing permission, two not permitted, one conflict (1 min).
5. Settings page: "Language models: none" (30 s).

If the app fails during the viva: the same numbers come from `python -m pytest -q --no-cov tests/unit/test_evidence.py`
and the figures are in the paper. Have the paper PDF open in a second window.

---

## A. The problem and the contribution

**Q1. What is new here? People have analysed drone logs before.**
Four things, all measured: (1) the first test, declared in advance, of whether public flight logs can attribute
crashes to pilot or aircraft, and they cannot; (2) an audit showing how much of the apparent crash-detection skill
comes from evaluation choices (AUC fell by 0.21 [0.06, 0.34] across 32 settings; a published detector fell from 0.94
to 0.63 when whole days were held out); (3) a ten-item reporting checklist and a tool designed from those limits; (4) a normal-flight model trained on
1,121 public flights of 401 vehicles, tested on unseen drones and on real injected faults, used as context only.
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

**Q3. Who would use this?**
Fleet operators (settings, flight reviews, records), maintenance engineers (which drone to look at first),
investigators and insurers (a signed, time-ordered account and a clear statement of its limits), and anyone building
log diagnostics (the checklist). *Honest limit:* no operator has used it yet; a prospective study is declared but not
run (`research/protocols/prospective_and_user_study.md`).

**Q4. Why should a regulator care?**
EU and UK operators must keep operation and maintenance records for at least three years; India requires an accident
report within 48 hours, the US within ten days. The signed record makes those records tamper-evident; the study
warns against reading blame out of them.

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
Because when we measured it as a screen against 412 non-crash drones, flagging the top 10% gave a lift of only 1.77
[1.00, 2.60]: the interval reaches 1.00, which is random inspection. And within a drone, the crash flight showed no
rise (mean rank 0.48, p = 0.67). So the tool shows the position as context, with no alarm line.
*Show:* Fleet Assurance ▸ vibration table (no flags) and History; Proof ▸ results 2–4.

**Q18. Your re-implemented detector didn't reach the published accuracy. Isn't the comparison unfair?**
Fair point, and the paper says so. The published code and weights were not released, so we fixed the open choices
before training and declared them. The finding does not depend on matching their number: our own model's accuracy
dropped by 0.33 [0.28, 0.38] between random windows and held-out days. The point is the drop, not the level.

**Q19. What about the language models? Everyone is using them.**
We tested four small local models as single reviewers and as voting panels. On 97 real crash cases with independent
labels, no panel beat a fixed rule, and one compromised reviewer moved most of the panel's verdicts (between 16 and
89 of the 97). That is why AeroFleet uses none. *Show:* Settings ▸ "Language models: none"; the no-AI test.

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
airspace, the 120 m limit, and the other planned routes, then signed into the record. *Honest limit:* the zones are
our approximations from the Drone Rules 2021 distances around known airports and military sites in Pune and Mumbai,
not the official Digital Sky map (which cannot be queried automatically), and the screen says so; a route outside
those cities is reported "not checked", never "clear". *Show:* Route check ▸ *Try 5 demo missions*.

**Q23c. How does "Today's fleet" decide, and why trust it?**
Fixed rules only, each shown with its reason: do not fly if a safety-critical setting changed without approval or
there is no UIN on record; check first if a flight-limit setting changed, the UIN is unverified, settings were never
checked, or the last flight's log shows warnings (sensor data rejected, poor GPS, critical battery, a safety setting
changed in flight, leaving the plan). Vibration is displayed but never changes the verdict. *Show:* Today's fleet ▸
PX4-04, whose critical-battery threshold really changed between two of its public flights.

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
677 automated tests, run before every commit. Beyond unit tests: the numbers in the paper are checked against the
result files (`check_numbers.py`, 30 checks), the paper's headline results are recomputed and compared in a test, and
the "no AI" claim is a test. *Show:* `python -m pytest -q --no-cov tests/unit tests/integration`.

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
Airdata is a mature global logbook, but has no India UIN or SOP logic and no signed record we could verify offline.
FlightHub serves DJI hardware only, and DJI logs are closed. AeroGCS is the closest Indian rival and ships with many
spraying drones, but it is the manufacturer's own system, not an independent record. FlightMD (open source) is closest
in spirit; AeroFleet adds approvals, a go / no-go, the spray form, the signed record and a pre-registered study. The
honest weak points: we read only PX4 and ArduPilot logs, have no mobile app, and no operator has used it.

**Q39. Who would pay?**
Probably not the self-help group. Lead fertiliser companies, which the scheme asks to help with repair and
maintenance of many SHG drones, and service aggregators are the natural buyers of a fleet-wide view. Insurers are a
later conversation. Willingness to pay is unproven.

**Q40. What does the spray register actually save the operator?**
The SOP asks for its Annexure-I form within seven days of each spraying. A log already knows the date, start and end
time, height and speed, and often the spray direction; the drone's previous form knows the sprayer; the logbook knows
the last calibration. So the operator types only what a log cannot know (field, crop, product, weather, PPE), sees
the days left, and gets a printable form in the official layout. *Show:* Spray register ▸ As of the last spraying
flight ▸ open the form with three problems.

**Q41. Why are there no wind or height limits in the spray checks?**
Because the SOP gives none: it says "appropriate" wind speed, temperature, humidity and height. Inventing a number
would be the kind of overclaim the study argues against. The checks that exist quote a sentence with a number or a
fact in it: 24 h notice, 100 m from water, PPE, expiry date, UIN.

**Q42. The height in the form says 3 m. Above what?**
Above the take-off point, from the log. The log cannot see the crop canopy, so the form labels it and lets the
operator correct it; if the entered value differs from the log by more than 1 m, the form keeps both and says so.

**Q43. Why Hindi and Marathi, and are the translations right?**
The pilots are new operators, many more comfortable in Hindi or Marathi, and the friend's industry review named
"English only" as a weakness against Skylark. Only *Today's fleet* is translated, because it is the screen a pilot
reads. The verdicts come with a code, so the rule never changes with the language. The translations were drafted with
an AI assistant and the screen says they are unchecked until a native speaker has read them.

**Q44. You said the operator can rebuild the whole chain. What did you do about it?**
A signed receipt. Each week the operator saves a receipt of the newest entry and sends it to someone outside their
control, such as the fertiliser company. Later, *Check a receipt* (or `verify_ledger.py --receipt`) shows whether that
exact entry is still in the record. A test rebuilds the chain with the operator's own key: the chain passes its own
check and fails the receipt. It is only as strong as how often receipts are sent, and the clock is still the
machine's.

**Q45. The forum numbers say 96 in one place and 94 in another.**
94 threads blamed the aircraft alone, 2 blamed both pilot and aircraft. The configuration count (26 of 94) is over the
94; the troubleshooter test uses all 96 that named an aircraft cause, aircraft alone or both.

**Q46. Is "0 of 40 false alarms" true in general?**
Only with a waypoint every 5 s. With 10 s spacing the same check gave 9 of 40 false alarms, from fast flights cutting
corners of plans built from the track. Quote the spacing with the number.

**Q47. Is the draft Civil Drone Bill law?**
No. It was released for comment on 16 September 2025 (comments to 15 October 2025); we found no record of it being
introduced in Parliament. The Drone Rules 2021 apply. Check again before the review.

**Q48. A pilot describes a problem. How do you find similar flights, and is that a diagnosis?**
Two ways, both shown as places to look. Words: BM25 against what uploaders wrote about their own flights in the public
PX4 archive, with the uploader's rating. Logs: the public logs on this computer whose logs show the same signs as the
pilot's flight (or as the signs the words name, by a fixed word list), computed by the same rules as the pilot's own
review. Not a diagnosis: our troubleshooter test showed words guess the expert's cause less often than always naming
the commonest cause, and two flights with the same signs can have different causes. *Show:* Fleet Assurance ▸
Something wrong? ▸ type "compass error, it circles" ▸ Search the public log archive.

**Q49. Which flight controllers can it read?**
PX4 and ArduPilot logs in full, and any MAVLink autopilot through its ground station's .tlog. For other controllers
(DJI Agras, closed agricultural controllers) a CSV export or a GPX track, which give position, time and, in a CSV,
battery, GPS and mode: enough for the timeline, the spray form and the operations log, not for settings or vibration.
DJI flight-record CSVs are tested on three real public DJI Mini 4 Pro flights: heights match the files' own maximum
column, and modes, battery and satellites come through. Testing on real files found four faults that our made-up test
files had missed; that is why we tested. Airdata's export layout is still untested on a real file.

## Questions to answer with "we did not test that"

- "Does AeroFleet reduce crashes?" Not tested; that needs the prospective study.
- "Does it work on DJI drones?" No: DJI logs are not open; the tool reads PX4 and ArduPilot.
- "Would vibration work as a screen on a bigger dataset?" Unknown. About 247 matched sets would be needed if the true
  effect is the smaller replicated one, more than the archive holds.
- "Is the VR replay useful?" Built and tested in a browser; not tested on a headset or with users.
