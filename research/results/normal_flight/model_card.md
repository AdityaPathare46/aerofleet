# Model card: AeroFleet normal-flight model v1

**What it does.** For a PX4 flight it gives the range that vibration and battery voltage drop usually fall in for a
healthy flight of a similar drone flown in a similar way, and says whether the flight was below, inside or above it.

**What it is for.** Context for whoever maintains a drone, for example a self-help group with one or two spraying
drones and nothing to compare them with. It appears in each flight review and as context on Today's fleet.

**What it is not.** Not a crash predictor and not a verdict. It never changes a readiness verdict. It was trained on
ordinary flights only, with no crash labels, because the study behind AeroFleet found crash labels and crash
predictors unreliable (0.47 balanced accuracy for pilot-or-aircraft attribution on held-out crashes).

## Training data

| | |
|---|---|
| Source | Public PX4 Flight Review logs already downloaded for the study (3,279 logs) |
| Kept | **1,121 flights of 401 vehicles** (vibration 1,104; battery 1,056) |
| Excluded | 589 crash or unsatisfactory ratings; 154 flights of the eight demo-fleet drones; 320 over the 10-per-vehicle cap; 1,071 unreadable, not PX4 or under 60 s; 24 truncated downloads |
| Inputs | vibration source, vehicle kind, flight-controller hardware (15 most common), firmware, minutes, ground speed, median and maximum height, share of pilot-flown time, battery cells, starting volts per cell |
| Targets | vibration 95th percentile (last 10 s left out; log scale); battery voltage drop, % per minute |

## Model

scikit-learn `HistGradientBoostingRegressor`, quantile loss, one model per target and quantile (5%, 50%, 95%);
300 iterations, learning rate 0.05, 15 leaves, at least 20 flights per leaf, L2 1.0, seed 0. Settings fixed in
advance, not tuned. Exported as trees to `aerofleet/assurance/data/normal_flight_model.json` and evaluated in plain
Python in the app; the export reproduces scikit-learn to within 3e-14. The range is widened by conformal
calibration (below).

## Evaluation (all declared before running; vehicles held out with GroupKFold, 5 folds)

| Test | Result | Pass mark | Outcome |
|---|---|---|---|
| H1 calibration of the raw 5-95% range | 72.7% vibration, 73.3% battery | 85-95% | **Not supported** |
| H2 error of the middle estimate vs always guessing the median | 47.6% lower (vibration), 15.4% lower (battery) | at least 10% lower | Supported |
| H3 vibration score after injected motor faults, same flight (RflyMAD, 220 flights) | rose in 60% of flights, p = 0.0005 | p < 0.025 | Supported, with caveats |
| H4† conformal calibration (declared after H1 failed) | 90.4% vibration, 90.8% battery (fixed-wing vibration alone 84.8%) | 85-95% | Supported |

H3 caveats: the shift is small (no flight crossed its range before or after the fault); sensor faults raised the
score as well (p = 0.005, two-sided) and fault-free flights fell at the same point in the flight (p = 0.016), so part
of the effect is the phase of flight. The model responds to faults; it is not a fault detector.

Declarations and results: `de4382a` (declared), `a53e245` (H1-H3 results), `76db013` (H4 declared), `98bb3f5` (H4
result). Scripts: `research/normal_flight/train_eval.py`, `research/normal_flight/calibrate.py`.

## Limits

- PX4 only; no ArduPilot flights in training.
- Public, self-uploaded flights: they are not a random sample of all drones, and agricultural spraying drones are not
  identified in the archive. The ranges describe ordinary public PX4 flying, not spraying specifically.
- The ranges are wide (calibration widened them about 1.5 times), so "outside the range" is uncommon on purpose.
- Being outside the range was not shown to mean a drone will fail.
