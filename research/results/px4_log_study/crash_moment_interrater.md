# Crash-moment check: two reviewers

Declared in `research/px4_log_study/crash_moment_interrater.py`.

```
{
 "n": 50,
 "cross_table_A_rows_B_cols": {
  "correct": {
   "correct": 23
  },
  "too early": {
   "correct": 3,
   "too early": 1
  },
  "too late": {
   "too late": 1,
   "too early": 1
  },
  "no crash visible": {
   "too early": 1,
   "too late": 8,
   "no crash visible": 5,
   "correct": 4
  },
  "can't tell": {
   "can't tell": 2,
   "too early": 1
  }
 },
 "five_labels": {
  "agreement": 0.64,
  "kappa": 0.46428571428571436
 },
 "contains_crash": {
  "n_both_decided": 47,
  "agreement": 0.723404255319149,
  "kappa": 0.32186459489456176
 },
 "crash_moment_right": {
  "n": 47,
  "agreement": 0.851063829787234,
  "kappa": 0.7038703870387039
 },
 "correct_by_status": {
  "A": {
   "confirmed": [
    11,
    12
   ],
   "tilt_unconfirmed": [
    10,
    14
   ],
   "fallback": [
    2,
    24
   ]
  },
  "B": {
   "confirmed": [
    12,
    12
   ],
   "tilt_unconfirmed": [
    12,
    14
   ],
   "fallback": [
    6,
    24
   ]
  }
 },
 "archive_estimate": {
  "A": {
   "contains_given_tilt": [
    25,
    25
   ],
   "contains_given_fallback": [
    4,
    22
   ],
   "estimate": 0.49853372434017595,
   "ci95": [
    0.39814382831245004,
    0.6155691815515862
   ]
  },
  "B": {
   "contains_given_tilt": [
    26,
    26
   ],
   "contains_given_fallback": [
    17,
    22
   ],
   "estimate": 0.8607038123167156,
   "ci95": [
    0.7504365502532658,
    0.9698747000799788
   ]
  },
  "agreed_logs": {
   "contains_given_tilt": [
    25,
    25
   ],
   "contains_given_fallback": [
    4,
    9
   ],
   "estimate": 0.6594982078853047,
   "ci95": [
    0.465623981753014,
    0.8631638970348647
   ]
  }
 },
 "limits": "two reviewers; A not blind to the automatic verdict; 50 logs from the modelled sample"
}
```
