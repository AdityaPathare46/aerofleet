# Defending AeroFleet: hard questions, honest answers, and where to show the proof

For the final-year project viva. Each answer is short enough to say aloud; **Show** says where to prove it, live.
Numbers are from the paper (`docs/paper/latex/main.tex`) and the result files; `python docs/paper/check_numbers.py`
checks the key ones. Read `docs/DEMO.md` for the walk-through itself.

**The rule for the room: never claim more than this file says.** If a question goes past what we tested, say
"we did not test that" and name the closest thing we did test. Examiners respect a clear limit far more than a guess.

## The 60-second answer: "What is your project?"

Drone operators are told flight logs can say why a drone crashed and which drone will fail next. We tested that on
the largest public archive of real autopilot logs (479,547 PX4 logs, 590 crash-rated), declaring every test before
running it. Logs could not tell pilot error from aircraft fault (0.47 balanced accuracy on held-out crashes; chance is
0.50), much of the "accuracy" in the literature comes from how models are tested, and even the crash labels are
shaky. So we built AeroFleet the other way round: a ground-side tool that checks settings, plans and logs, puts
the evidence in order, compares each drone with its own history and with public flights, keeps a tamper-evident
record, and **never names a cause**.

## The live demonstration order (10 minutes)

1. **Overview** page: problem, data, six findings, how each design choice follows (3 min).
2. **Proof** page: press *Recompute the results*, then *Run five attacks on a copy* (2 min). This answers most
   "how do we know" questions before they are asked.
3. **Fleet Assurance**, fleet `demo`: a flight review (timeline, evidence quality), a drone's History, the public
   comparison column (3 min).
4. Fleet `demo-settings`: the blocked failsafe and the public-flights column (1 min).
5. Settings page: "Language models: none" (30 s).

If the app fails during the viva: the same numbers come from `python -m pytest -q --no-cov tests/unit/test_evidence.py`
and the figures are in the paper. Have the paper PDF open in a second window.

---

## A. The problem and the contribution

**Q1. What is new here? People have analysed drone logs before.**
Three things, all measured: (1) the first test, declared in advance, of whether public flight logs can attribute
crashes to pilot or aircraft, and they cannot; (2) an audit showing how much of the apparent crash-detection skill
comes from evaluation choices (AUC fell by 0.21 [0.06, 0.34] across 32 settings; a published detector fell from 0.94
to 0.63 when whole days were held out); (3) a ten-item reporting checklist and a tool designed from those limits.
*Show:* Overview ▸ findings; paper Table 1 (related work) and Section 6.

**Q2. Isn't a negative result a failed project?**
No. A negative result that is declared in advance and adequately tested is a finding: it stops people trusting
verdicts the data cannot support. In a safety context, "this cannot be done from logs" is exactly what an
investigator or insurer needs to know. The tool is the positive output: it does what the data *can* support.

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
Yes: logistic models, boosted stumps and depth-3 trees for attribution (all near chance on held-out crashes), and a
re-implementation of a published convolutional fault detector (LeNet-5 style), which fell from AUC 0.94 to 0.63 once
whole days were held out. Machine learning was the thing under test, not the tool's engine.

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
No. AeroFleet never talks to an aircraft. "Blocked" is a status: a safety-critical setting (a failsafe, a geofence,
battery limits) differs from the fleet's approved configuration and nobody has approved the change. An operator can
approve it with a written reason, and the approval is signed into the record.

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

## Questions to answer with "we did not test that"

- "Does AeroFleet reduce crashes?" Not tested; that needs the prospective study.
- "Does it work on DJI drones?" No: DJI logs are not open; the tool reads PX4 and ArduPilot.
- "Would vibration work as a screen on a bigger dataset?" Unknown. About 247 matched sets would be needed if the true
  effect is the smaller replicated one, more than the archive holds.
- "Is the VR replay useful?" Built and tested in a browser; not tested on a headset or with users.
