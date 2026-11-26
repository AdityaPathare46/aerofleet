# The normal-flight model

AeroFleet's one trained model. For a PX4 flight it gives the range that **vibration** and **battery voltage drop**
usually fall in for a *healthy* flight of a *similar* drone flown in a *similar* way, and says whether the flight was
below, inside or above that range.

It is **context, never a verdict**: it is shown beside a flight review and on Today's fleet, and it never changes
ready / check first / do not fly. It is **not a crash predictor**; it was trained on ordinary flights only.

| | |
|---|---|
| Model | Gradient-boosted trees, quantile loss (scikit-learn `HistGradientBoostingRegressor`), 5th / 50th / 95th percentile |
| Trained on | 1,121 ordinary public PX4 flights of 401 vehicles (no crash labels) |
| Tested | 4 tests, each declared before it ran; 3 passed, 1 failed and was fixed by a declared follow-up |
| In the app | Exported to JSON and evaluated in plain Python: the product imports no ML library |
| Code | `aerofleet/assurance/normal_flight.py` (features and scoring), `research/normal_flight/train_eval.py`, `calibrate.py` |
| Results | `research/results/normal_flight/` (`model_card.md`, `results.json`, `calibration.json`, `features.jsonl`) |

## 1. Why this model exists

The use case is a small agricultural drone operator, often a self-help group with one or two drones and no
maintenance engineer. When a flight's vibration reads 25 or its battery dropped 4% a minute, they have **nothing to
compare it with**. A fleet of one has no history.

The study behind AeroFleet also showed what *not* to build. Crash labels in the public archive are unreliable, and no
rule or model could tell pilot error from aircraft fault (0.47 balanced accuracy against 0.50 chance on 112 held-out
crashes). So this model learns **what normal looks like** from ordinary flights, and makes no claim about crashes.

## 2. What it learns

**Two targets** (measured from each flight's own log):

| Target | Definition |
|---|---|
| Vibration | 95th percentile of the autopilot's vibration metric over the flight, last 10 s left out so an impact cannot inflate it; modelled on a log scale |
| Battery voltage drop | Drop in battery voltage from the first to the last tenth of the flight, as % of the starting voltage, per minute |

**Conditions** (what the expected range depends on), all read from the same log by `features()`:

| Input | Why it matters |
|---|---|
| Vibration source (which PX4 metric) | Different metrics, different units: never mixed |
| Vehicle kind (multirotor / fixed wing / other) | A plane and a quadcopter vibrate differently |
| Flight-controller hardware (15 most common, others pooled) | Boards and mountings differ |
| Firmware version | Metric definitions changed between PX4 releases |
| Minutes, ground speed, median and maximum height | How hard and how long it flew |
| Share of time in pilot-controlled modes | Manual flying is less smooth |
| Battery cells, starting volts per cell (battery target only) | A fresh 6S pack drops differently from a tired 4S |

Missing values stay missing; the trees learned which way to send them.

## 3. Training data

From the 3,279 PX4 logs downloaded for the study, looked up in the archive index (479,547 logs):

| Step | Flights |
|---|---|
| Excluded: rated crash or unsatisfactory by the uploader | 589 |
| Excluded: the eight demo-fleet drones (so the app never scores a drone it trained on) | 154 |
| Excluded: over 10 flights per vehicle (random cap, seed 7, so no airframe dominates) | 320 |
| Excluded: unreadable, not PX4, or under 60 s | 1,071 |
| Excluded: cut-short downloads | 24 |
| **Kept** | **1,121 flights of 401 vehicles** (1,104 with vibration, 1,056 with battery) |

## 4. The model

One model per target and per quantile (5%, 50%, 95%), so six models in all. Settings fixed **in advance and never
tuned**: 300 iterations, learning rate 0.05, 15 leaves, at least 20 flights per leaf, L2 regularisation 1.0, seed 0.

Quantile loss (pinball loss) makes the 5% model aim below 95% of flights and the 95% model above them, so the pair
gives a range rather than a single guess.

**No ML library in the product.** The trees are exported to `aerofleet/assurance/data/normal_flight_model.json`
(about 2.7 MB) and walked in plain Python (`_tree`, `_predict`). The export reproduces scikit-learn's predictions to
within 3e-14 on every training row. A test fails if the product's decision code can import any AI or ML library
(`tests/unit/test_no_ai_in_decision_path.py`).

## 5. How it was tested

All tests were written down with their pass marks and committed **before** anything was trained. Vehicles were held
out with GroupKFold (5 folds, grouped by vehicle), so the model is always judged on drones it has never seen.

| Test | Result | Pass mark | Outcome |
|---|---|---|---|
| H1: does the raw 5-95% range hold about 90% of held-out flights? | 72.7% vibration, 73.3% battery | 85-95% | **Failed** |
| H2: is the middle estimate better than always guessing the median? | 47.6% lower error (vibration), 15.4% lower (battery) | at least 10% lower | Passed |
| H3: does the vibration score rise after a real injected motor fault? (RflyMAD, 220 flights) | Rose in 60% of flights, p = 0.0005 | p < 0.025 | Passed, with caveats |
| H4†: after conformal calibration, does the range hold about 90%? | 90.4% vibration, 90.8% battery | 85-95% | Passed |

† H4 was declared *after* H1 failed, as a fix, so it is exploratory, and H1 stays reported as failed.

**H1 failed** because the ranges were too narrow for drones the model had not seen. **The fix** (H4, conformalised
quantile regression, Romano et al. 2019) widens each range by a fixed amount learned out-of-fold, tested nested so the
widening is never fitted on the drones it is tested on. The ranges became about 1.5 times wider and now hold what they
say. Fixed-wing vibration alone reached 84.8%, just under the pass mark.

**H3 caveats.** The shift is small: no flight crossed its range before or after the fault. Sensor faults raised the
score too, and fault-free flights changed at the same point in the flight, so part of the effect is the phase of
flight. The model *responds* to faults; it is **not a fault detector**.

Commits: `de4382a` (H1-H3 declared), `a53e245` (H1-H3 results), `76db013` (H4 declared), `98bb3f5` (H4 result).

## 6. How the app uses it

| Where | What is shown |
|---|---|
| Flight review | "Expected range (~90% of healthy flights)": observed value, the range, the middle, and below / inside / above |
| Today's fleet | The last flight's position, labelled "context", under the verdict (never part of it) |
| Fleet trends | Share of flights outside the range (about 10% are expected by chance) and battery drop against the middle |
| Maintenance logbook | Vibration and battery drop relative to the model before and after work on a drone |
| Proof | The four tests and their results |

## 7. Reproduce it

```bash
AEROFLEET_PX4_DATA="/Volumes/One Touch/AeroFleet_px4_data" python research/normal_flight/train_eval.py
```

```bash
python research/normal_flight/calibrate.py
```

The first rebuilds the features, runs H1-H3 and exports the model; the second runs H4 and writes the widening into the
model file. Both need the downloaded logs on the data drive.

## 8. Limits

- **PX4 only.** No ArduPilot, DJI or CSV/GPX flights in training, so those logs get no expected range.
- **Not spraying drones specifically.** The public archive does not mark agricultural drones; the ranges describe
  ordinary public PX4 flying.
- **Self-uploaded flights** are not a random sample of all drones.
- **Wide ranges on purpose.** After calibration, "outside the range" is uncommon, so it is worth a look when it happens.
- **Not a prediction.** Being outside the range was not shown to mean a drone will fail.

## 9. Questions to expect in the viva

- *Why not train on crashes?* The study showed crash labels and crash predictors are unreliable; this model avoids
  them entirely.
- *Why quantile trees?* A range is what an operator needs, the trees handle missing values and mixed inputs, and the
  model is small enough to export and run without an ML library.
- *Your calibration test failed. Isn't that bad?* It was declared, it failed, and we report it. The fix was declared
  before it ran, is labelled exploratory, and passed.
- *How do you know it didn't memorise the drones?* Every test holds out whole vehicles, and the demo-fleet drones were
  never in training.

More in `docs/VIVA.md` (Q15 to Q15e).
