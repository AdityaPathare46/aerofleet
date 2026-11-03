# Round 21 audit

Declared in `research/px4_log_study/r21_audit.py`. Exploratory (dagger).

```
{
 "declared_in": "research/px4_log_study/r21_audit.py docstring",
 "B": {
  "mixed_days": 4,
  "pre": {
   "per_day": [
    {
     "day": "2023-5-25",
     "n": 16,
     "n_nofault": 11,
     "auc": 0.9636363636363636
    },
    {
     "day": "2023-5-31",
     "n": 61,
     "n_nofault": 10,
     "auc": 0.8509803921568627
    },
    {
     "day": "2023-6-15",
     "n": 41,
     "n_nofault": 20,
     "auc": 0.31666666666666665
    },
    {
     "day": "2023-6-2",
     "n": 45,
     "n_nofault": 10,
     "auc": 0.6828571428571428
    }
   ],
   "weighted_mean": 0.6812263220960442
  },
  "fault": {
   "per_day": [
    {
     "day": "2023-5-25",
     "n": 16,
     "n_nofault": 11,
     "auc": 0.9454545454545454
    },
    {
     "day": "2023-5-31",
     "n": 61,
     "n_nofault": 10,
     "auc": 0.7980392156862746
    },
    {
     "day": "2023-6-15",
     "n": 41,
     "n_nofault": 20,
     "auc": 0.5571428571428572
    },
    {
     "day": "2023-6-2",
     "n": 45,
     "n_nofault": 10,
     "auc": 0.7628571428571429
    }
   ],
   "weighted_mean": 0.7422030273347489
  },
  "whole": {
   "per_day": [
    {
     "day": "2023-5-25",
     "n": 16,
     "n_nofault": 11,
     "auc": 0.36363636363636365
    },
    {
     "day": "2023-5-31",
     "n": 61,
     "n_nofault": 10,
     "auc": 0.6431372549019608
    },
    {
     "day": "2023-6-15",
     "n": 41,
     "n_nofault": 20,
     "auc": 0.780952380952381
    },
    {
     "day": "2023-6-2",
     "n": 45,
     "n_nofault": 10,
     "auc": 0.6314285714285715
    }
   ],
   "weighted_mean": 0.6471342803713789
  },
  "B2": {
   "fault": {
    "median_pre_s": 35.806687,
    "median_whole_s": 111.069164,
    "share_whole_over_120s": 0.47139588100686497
   },
   "no_fault": {
    "median_pre_s": 20.0,
    "median_whole_s": 69.03234,
    "share_whole_over_120s": 0.39215686274509803
   }
  }
 },
 "C": {
  "fixed-wing": {
   "tilt_unconfirmed": 4,
   "tilt_unconfirmed|C_correct": 4,
   "fallback": 2,
   "fallback|C_correct": 0,
   "confirmed": 1,
   "confirmed|C_correct": 1
  },
  "multicopter": {
   "fallback": 19,
   "fallback|C_correct": 2,
   "confirmed": 10,
   "confirmed|C_correct": 8,
   "tilt_unconfirmed": 5,
   "tilt_unconfirmed|C_correct": 5
  },
  "VTOL": {
   "tilt_unconfirmed": 5,
   "tilt_unconfirmed|C_correct": 5,
   "fallback": 3,
   "fallback|C_correct": 0,
   "confirmed": 1,
   "confirmed|C_correct": 1
  }
 },
 "D": {
  "holdout": {
   "n": 86,
   "undecided": 4,
   "n_decided": 82,
   "ba_decided": 0.4554326610279766,
   "ci": [
    0.3475093193843194,
    0.5637041709316956
   ],
   "recall_aircraft": 0.5660377358490566,
   "recall_pilot": 0.3448275862068966
  },
  "modelled": {
   "n": 108,
   "undecided": 9,
   "n_decided": 99,
   "ba_decided": 0.40437302423603794,
   "ci": [
    0.31043762575452716,
    0.5075837320574162
   ],
   "recall_aircraft": 0.6164383561643836,
   "recall_pilot": 0.19230769230769232
  }
 },
 "A": {
  "windows": {
   "PRE": 3013,
   "FAULT": 2258,
   "NORMAL_PRE": 506,
   "NORMAL_POST": 1042
  },
  "flights": 291,
  "A1_random_window_split": {
   "n_windows": 3806,
   "n_fault": 2258,
   "accuracy": 0.878215223097113,
   "auc": 0.9432567223134718,
   "accuracy_by_seed": [
    0.8713910761154856,
    0.8779527559055118,
    0.8779527559055118,
    0.889763779527559,
    0.8740157480314961
   ]
  },
  "A2_grouped_by_flight": {
   "n_windows": 3806,
   "n_pos": 2258,
   "accuracy": 0.8576983709931687,
   "auc": 0.9210769975487672,
   "perm_p": 0.009900990099009901,
   "null_mean": 0.48250575978341737
  },
  "A3_grouped_by_day": {
   "n_windows": 3806,
   "n_pos": 2258,
   "accuracy": 0.6209668943772989,
   "auc": 0.6261663954518302,
   "perm_p": 0.009900990099009901,
   "null_mean": 0.48022354148351015
  },
  "A1_minus_A3": {
   "a1_window_cv_auc": 0.964122110760935,
   "a3_auc": 0.6348266742652595,
   "diff": 0.3292954364956755,
   "ci": [
    0.2756384414830388,
    0.38082901405710007
   ]
  },
  "A4_pre_onset_grouped_by_flight": {
   "n_windows": 3519,
   "n_pos": 3013,
   "accuracy": 0.8554703040636544,
   "auc": 0.8486609409292276,
   "perm_p": 0.009900990099009901,
   "null_mean": 0.4808919569769653
  },
  "A5_pre_onset_grouped_by_day": {
   "n_windows": 3519,
   "n_pos": 3013,
   "accuracy": 0.7454958795112249,
   "auc": 0.56664972208703,
   "perm_p": 0.009900990099009901,
   "null_mean": 0.48830170536113016
  },
  "wording": {
   "published_accuracy_reproduced_random_split": false,
   "split_inflates": true,
   "separates_without_fault": true
  }
 }
}
```
