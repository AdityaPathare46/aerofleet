# Round 22 audit

Declared in `research/px4_log_study/r22_audit.py`. Exploratory (dagger).

```
{
 "declared_in": "research/px4_log_study/r22_audit.py docstring",
 "A": {
  "n_reviewed_multicopter": 34,
  "n_tilt": 15,
  "share_tilt": 0.3870967741935484,
  "A": {
   "n_tilt": 15,
   "n_fallback": 19,
   "tilt_correct": 15,
   "fallback_correct": 2,
   "missed": 0.07279693486590033,
   "ci": [
    0.0,
    0.22040019285732493
   ],
   "missed_ignoring_fallback_found": 0.2183908045977011,
   "ci_ignoring": [
    0.0,
    0.3809264625760453
   ]
  },
  "B": {
   "n_tilt": 15,
   "n_fallback": 19,
   "tilt_correct": 15,
   "fallback_correct": 5,
   "missed": 0.30787037037037046,
   "ci": [
    0.15312118819531548,
    0.4583658486697683
   ],
   "missed_ignoring_fallback_found": 0.5277777777777779,
   "ci_ignoring": [
    0.4237995824634656,
    0.6112258002568504
   ]
  },
  "C": {
   "n_tilt": 15,
   "n_fallback": 19,
   "tilt_correct": 13,
   "fallback_correct": 2,
   "missed": 0.5027777777777778,
   "ci": [
    0.33835873726151366,
    0.6537014382638598
   ],
   "missed_ignoring_fallback_found": 0.5907407407407408,
   "ci_ignoring": [
    0.46970504547248637,
    0.7002830827836952
   ]
  },
  "majority": {
   "n_tilt": 15,
   "n_fallback": 15,
   "tilt_correct": 15,
   "fallback_correct": 2,
   "missed": 0.28148148148148144,
   "ci": [
    0.08091286475596296,
    0.45529699684751934
   ],
   "missed_ignoring_fallback_found": 0.4222222222222223,
   "ci_ignoring": [
    0.22704779133575384,
    0.555171584067294
   ]
  },
  "wording_most": {
   "A": false,
   "B": false,
   "C": false,
   "majority": false
  }
 },
 "C": {
  "C1_auc_pre_length": 0.6667564050791942,
  "C1_auc_whole_length": 0.5989590344146812,
  "C2_matched_features": {
   "n": 488,
   "n_fault": 437,
   "stratified": {
    "auc": 0.8564275137972809,
    "perm_p": 0.004975124378109453
   },
   "by_day": {
    "auc": 0.7488850002243461,
    "perm_p": 0.004975124378109453
   }
  },
  "wording": "survives length matching"
 },
 "B": {
  "B1_fault_vs_normal_by_day": {
   "per_day": [
    {
     "day": "2023-5-25",
     "n_windows": 209,
     "n_neg": 190,
     "auc": 0.8282548476454293
    },
    {
     "day": "2023-5-31",
     "n_windows": 679,
     "n_neg": 561,
     "auc": 0.6427384513127284
    },
    {
     "day": "2023-6-15",
     "n_windows": 596,
     "n_neg": 596,
     "auc": NaN
    },
    {
     "day": "2023-6-2",
     "n_windows": 283,
     "n_neg": 201,
     "auc": 0.3395219026817134
    }
   ],
   "one_class_days": [
    "2023-6-15"
   ],
   "weighted_mean": 0.6025699146525725
  },
  "B1_prefault_by_day": {
   "per_day": [
    {
     "day": "2023-5-25",
     "n_windows": 134,
     "n_neg": 66,
     "auc": 0.7649286987522281
    },
    {
     "day": "2023-5-31",
     "n_windows": 348,
     "n_neg": 170,
     "auc": 0.4777594183740912
    },
    {
     "day": "2023-6-15",
     "n_windows": 230,
     "n_neg": 230,
     "auc": NaN
    },
    {
     "day": "2023-6-2",
     "n_windows": 200,
     "n_neg": 40,
     "auc": 0.379609375
    }
   ],
   "one_class_days": [
    "2023-6-15"
   ],
   "weighted_mean": 0.5053997041451355
  },
  "B2_matched_prefault": {
   "n_windows": 3241,
   "n_pos": 2735,
   "by_flight": {
    "auc": 0.847269186580052,
    "perm_p": 0.009900990099009901
   },
   "by_day": {
    "auc": 0.5329611029618978,
    "perm_p": 0.1188118811881188
   }
  },
  "wording": "separates fault flights before the fault even with matched windows"
 }
}
```
