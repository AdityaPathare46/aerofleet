# FlightMD re-evaluation

Declared in `research/px4_log_study/flightmd_eval.py`. Exploratory (dagger).

```
{
 "declared_in": "research/px4_log_study/flightmd_eval.py docstring",
 "tool": "FlightMD 306d0cb",
 "parse_errors": {
  "no armed period": 16
 },
 "n_scored": 765,
 "F1": {
  "all": {
   "n_crash": 89,
   "n_normal": 124,
   "auc_whole": 0.7882837984777094,
   "auc_whole_ci": [
    0.6660602579652003,
    0.8700364653238158
   ],
   "auc_m0": 0.7400326205146792,
   "auc_m0_ci": [
    0.6074570210108126,
    0.8303136792490854
   ],
   "auc_m10": 0.7153407031533164,
   "auc_m10_ci": [
    0.5762356297894611,
    0.80975161425924
   ],
   "drop_whole_m0": 0.048251177963030134,
   "drop_whole_m0_ci": [
    0.018438769535298192,
    0.0894651701538012
   ],
   "drop_m0_m10": 0.02469191736136278,
   "drop_m0_m10_ci": [
    0.001984861661466725,
    0.05384880941842969
   ],
   "share_below60_whole": {
    "crash": 0.0898876404494382,
    "normal": 0.016129032258064516
   },
   "share_below60_m0": {
    "crash": 0.07865168539325842,
    "normal": 0.016129032258064516
   },
   "share_below60_m10": {
    "crash": 0.06741573033707865,
    "normal": 0.016129032258064516
   }
  },
  "tilt_multicopter": {
   "n_crash": 24,
   "n_normal": 124,
   "auc_whole": 0.8990255376344086,
   "auc_whole_ci": [
    0.7740311176648518,
    0.9694103101071295
   ],
   "auc_m0": 0.8331653225806451,
   "auc_m0_ci": [
    0.6873126827485381,
    0.9310427557722596
   ],
   "auc_m10": 0.7963709677419355,
   "auc_m10_ci": [
    0.6402285477495856,
    0.9097353142076502
   ],
   "drop_whole_m0": 0.0658602150537635,
   "drop_whole_m0_ci": [
    0.016057405829950563,
    0.14015715187590183
   ],
   "drop_m0_m10": 0.03679435483870963,
   "drop_m0_m10_ci": [
    0.011956182670696725,
    0.0716675824175824
   ],
   "share_below60_whole": {
    "crash": 0.20833333333333334,
    "normal": 0.016129032258064516
   },
   "share_below60_m0": {
    "crash": 0.16666666666666666,
    "normal": 0.016129032258064516
   },
   "share_below60_m10": {
    "crash": 0.125,
    "normal": 0.016129032258064516
   }
  },
  "wording": {
   "separates_before_window": true,
   "window_leakage_material": false,
   "postcrash_inflates": false
  }
 },
 "F2": {
  "whole": {
   "n": 148,
   "n_pilot": 36,
   "ba": 0.5213293650793651,
   "ba_ci": [
    0.4357560239518084,
    0.609091964537011
   ],
   "recall_aircraft": 0.3482142857142857,
   "recall_pilot": 0.6944444444444444,
   "auc_badness": 0.45808531746031744,
   "auc_badness_ci": [
    0.3620698484635882,
    0.560313253894403
   ],
   "passes_0_70": false
  },
  "m0": {
   "n": 148,
   "n_pilot": 36,
   "ba": 0.5213293650793651,
   "ba_ci": [
    0.43514479972865466,
    0.6114942119114434
   ],
   "recall_aircraft": 0.3482142857142857,
   "recall_pilot": 0.6944444444444444,
   "auc_badness": 0.4681299603174603,
   "auc_badness_ci": [
    0.36867541988038754,
    0.5682120359260305
   ],
   "passes_0_70": false
  },
  "m10": {
   "n": 114,
   "n_pilot": 27,
   "ba": 0.4814814814814815,
   "ba_ci": [
    0.3762482083134257,
    0.5851359045118422
   ],
   "recall_aircraft": 0.3333333333333333,
   "recall_pilot": 0.6296296296296297,
   "auc_badness": 0.446360153256705,
   "auc_badness_ci": [
    0.32607274651369683,
    0.5602482200667845
   ],
   "passes_0_70": false
  }
 },
 "F3": {
  "m10": {
   "n_drones": 46,
   "mean_rank": 0.4793478260869565,
   "p": 0.6581,
   "above_median": 0.4782608695652174,
   "warning": false
  },
  "m0": {
   "n_drones": 59,
   "mean_rank": 0.5573446327683615,
   "p": 0.10453,
   "above_median": 0.559322033898305,
   "warning": false
  }
 },
 "F4": {
  "n_normal": 139,
  "labels": {
   "Caution": 13,
   "Good": 103,
   "Excellent": 21,
   "Warning": 2
  },
  "share_below60": 0.014388489208633094,
  "top_findings": [
   [
    "warning: High C-Rate Stress",
    48
   ],
   [
    "warning: Yaw-Axis Oscillation at 1.1 Hz",
    42
   ],
   [
    "warning: Yaw-Axis Oscillation at 1.0 Hz",
    38
   ],
   [
    "warning: EKF Innovation Ratio Exceeded: timestamp_sample",
    34
   ],
   [
    "warning: Pitch-Axis Oscillation at 1.1 Hz",
    28
   ],
   [
    "warning: Roll-Axis Oscillation at 1.1 Hz",
    22
   ],
   [
    "warning: Pitch-Axis Oscillation at 1.0 Hz",
    22
   ],
   [
    "warning: Roll-Axis Oscillation at 1.0 Hz",
    21
   ],
   [
    "warning: Pitch-Axis Oscillation at 1.2 Hz",
    21
   ],
   [
    "warning: GPS Satellite Count Drop",
    15
   ]
  ]
 },
 "F5": {
  "m0": {
   "oscillation": {
    "crash": 67.47058823529412,
    "normal": 62.056451612903224
   },
   "ekf": {
    "crash": 58.23529411764706,
    "normal": 91.65322580645162
   },
   "battery": {
    "crash": 88.48837209302326,
    "normal": 93.83064516129032
   },
   "gps": {
    "crash": 90.06024096385542,
    "normal": 94.43548387096774
   },
   "parameters": {
    "crash": 58.42696629213483,
    "normal": 59.395161290322584
   },
   "vibration": {
    "crash": 89.46666666666667,
    "normal": 95.41666666666667
   },
   "motors": {
    "crash": 100.0,
    "normal": 100.0
   }
  },
  "m10": {
   "oscillation": {
    "crash": 67.0,
    "normal": 63.104838709677416
   },
   "ekf": {
    "crash": 63.11764705882353,
    "normal": 91.65322580645162
   },
   "battery": {
    "crash": 88.83720930232558,
    "normal": 92.74193548387096
   },
   "gps": {
    "crash": 90.42168674698796,
    "normal": 94.43548387096774
   },
   "parameters": {
    "crash": 58.42696629213483,
    "normal": 59.395161290322584
   },
   "vibration": {
    "crash": 90.46666666666667,
    "normal": 95.20833333333333
   },
   "motors": {
    "crash": 100.0,
    "normal": 100.0
   }
  }
 }
}
```
