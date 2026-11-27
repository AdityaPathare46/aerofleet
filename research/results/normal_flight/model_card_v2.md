# Normal-flight model v2: measured loading as an input (declared test)

Declared in `research/normal_flight/train_eval_v2.py`. Full numbers in `results_v2.json`.

Flights kept: 1121 of 401 vehicles (v1: 1,121). With a thrust value: battery 995 of 1056, vibration 1035 of 1104.

| Test | v1 | v2 | Result | Pass mark | Outcome |
|---|---|---|---|---|---|
| H5 battery drop, error of the middle estimate on held-out drones | 0.826 | 0.775 | 6.2% lower | at least 10% lower | Not supported |
| H5v vibration (log scale), same | 0.968 | 0.971 | -0.3% lower | at least 10% lower | Not supported |
| H6 battery, calibrated coverage of v2 | | 91.4% | | 85-95% | Supported |
| H6 vibration, calibrated coverage of v2 | | 90.9% | | 85-95% | Supported |

Shipped by the declared rule: battery stays v1, vibration stays v1.

## Notes, written after seeing the result

- **H5 not supported; nothing shipped.** Measured loading lowered the battery-drop error by 6.2% (0.826 to 0.775), under
  the declared 10%, and did not change the vibration error. By the rule fixed in advance the model file is unchanged
  (still v1). The calibration (H6) would have held, but that does not decide shipping on its own.
- A likely reason, stated as a guess: public PX4 flights are mostly light drones without payload, so loading varies
  little in these data and adds little. On spraying drones, whose weight changes by many kilograms as the tank
  empties, it may matter much more; that cannot be tested without sprayer logs.
- The reader keeps the commanded thrust (`FlightLog.thrust`) and `features()` computes `thrust` and `thrust_change`
  (95% of flights have them); the shipped model does not use them. They are ready for a retrain on sprayer logs.
- The app's note stays: the model was not trained on spraying drones and payload is not an input.
