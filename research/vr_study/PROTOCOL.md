# VR debrief study: declared protocol

Declared before the first participant (this file, `make_trials.py`, the trial files and `analyse.py` are committed
and pushed first). Anything decided after that is marked † and reported as exploratory.

## Question

AeroFleet's VR view is meant for one job: after a flight, a trainer or supervisor shows a pilot where and how high the
drone went compared with its plan. Does seeing a flight on the 3D table in a headset make it easier to tell **whether
and how a flight left its plan** than the usual 2D view (a map from above and a height profile)?

## Trials (fixed before anyone takes part)

Built by `make_trials.py` (seed 2026) with the method of the injection experiment
(`research/px4_log_study/injection_reconcile.py`): 33 real public PX4 multirotor flights, each at least 120 s
airborne; the plan is built from the flight itself (a waypoint every 5 s); a known deviation is injected for 30 s with
3 s ramps, centred at a random point between 25% and 75% of the flight.

| Version | Answer | Flights |
|---|---|---|
| Unchanged | stayed on the plan | 6 |
| Sideways 15 m or 35 m, left or right of travel | went off sideways | 6 + 6 |
| Upward 8 m or 20 m | went off in height | 6 + 6 |

Two sets of 15 (A, B), three of each version per set; three practice flights (P: unchanged, sideways 50 m, upward
30 m), with the answer shown after each, never analysed. The answers are in `trials_key.json`; the app never receives
them for measured trials.

## Conditions (same flights drawn the same way; only the view differs)

* **2D**: on a laptop, a map from above (plan dashed blue, flown green, scale bar, north) and a height profile along
  the route (plan and flight each against the share of their own route covered). Mouse clicks on three buttons.
* **Headset**: Meta Quest 3, seated, the same plan and track on the 3D table (AeroFleet's VR view, vertical
  exaggeration as the view sets it), in the Quest Browser (WebXR). Three buttons in the scene, chosen with the
  controller.

Neither condition shows warnings, deviation colours, the playhead or any judgement.

## Design

Within subjects: each participant does both conditions, with different flight sets. Group = participant number mod 4:

| Group | Block 1 | Block 2 |
|---|---|---|
| 0 | 2D, set A | headset, set B |
| 1 | headset, set A | 2D, set B |
| 2 | 2D, set B | headset, set A |
| 3 | headset, set B | 2D, set A |

Trial order in a block is shuffled per participant (seed from the code). Each block starts with the three practice
flights. After both blocks: "Which view made it easier to tell?" (2D / headset / no difference).

## Participants

12 participants, P01 to P12 (three per group), students who are not on the project team and have not seen the trials.
P00 is a pilot run by a team member to check the setup; it is not analysed. A participant who stops is replaced by the
next code in the same group (P13 for group 1, and so on), and the stop is reported.

## Measures and tests

Each answer is right or wrong against the key; time is from the flight appearing (on screen, or once inside the
headset) to the answer.

* **V1 (primary)**: share of the 15 measured flights answered right, headset against 2D, paired by participant.
  Wilcoxon signed-rank test, two-sided, alpha 0.05. *Supported* if the headset share is higher with p < 0.05. If 2D is
  higher with p < 0.05, that is reported as the result. Otherwise: no difference detectable with 12 participants.
* **V2**: median seconds per flight, headset against 2D, paired; Wilcoxon, two-sided.
* **V3 (descriptive)**: share right per version and size, and the confusion between answers, per condition.
* **V4 (descriptive)**: the preference counts.
* **V5 (descriptive)**: share right in block 1 against block 2 (learning).

With 12 people only a large difference can be detected; a null result does not show the views are equal.

## Ethics and safety

Low-risk usability study, run only after the guide has agreed. Consent sheet (`CONSENT.md`) read and signed on paper
before starting; participants can stop at any time without giving a reason. Seated throughout; the headset part lasts
about 10 minutes; anyone who feels unwell stops. No names, photos or recordings are stored: only the code, the answers,
the times and the preference. The paper consent sheets are kept by the guide, apart from the codes.

## Running it

1. Laptop: start AeroFleet (`./start.sh`), sign in, open **VR study**.
2. Headset: connect the Quest 3 by USB-C with developer mode on, then on the laptop
   `adb reverse tcp:1420 tcp:1420` and `adb reverse tcp:8000 tcp:8000`, so the Quest Browser reaches the app at
   `http://localhost:1420` (WebXR needs a secure address, and localhost counts). Sign in there too.
3. Enter the participant code on whichever device runs the current block; answers go to the same server, so the study
   resumes where it stopped on either device.
4. After the last participant: `python research/vr_study/analyse.py`, then commit its outputs whatever they show.
