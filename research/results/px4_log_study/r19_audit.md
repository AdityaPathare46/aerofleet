# Round 19 audit

Declared in `research/px4_log_study/r19_audit.py`. Exploratory (dagger).

```
{
 "declared_in": "research/px4_log_study/r19_audit.py docstring",
 "A1": {
  "modelled": {
   "multicopter": {
    "fallback": 67,
    "confirmed": 29,
    "tilt_unconfirmed": 12
   },
   "fixed-wing": {
    "tilt_unconfirmed": 13,
    "confirmed": 2,
    "fallback": 3
   },
   "VTOL": {
    "fallback": 6,
    "confirmed": 9,
    "tilt_unconfirmed": 7
   }
  },
  "reviewed": {
   "VTOL": {
    "tilt_unconfirmed": 5,
    "tilt_unconfirmed|A_correct": 2,
    "tilt_unconfirmed|B_correct": 4,
    "fallback": 3,
    "fallback|A_correct": 0,
    "fallback|B_correct": 0,
    "confirmed": 1,
    "confirmed|A_correct": 0,
    "confirmed|B_correct": 1
   },
   "multicopter": {
    "fallback": 19,
    "fallback|A_correct": 2,
    "fallback|B_correct": 5,
    "confirmed": 10,
    "confirmed|A_correct": 10,
    "confirmed|B_correct": 10,
    "tilt_unconfirmed": 5,
    "tilt_unconfirmed|A_correct": 5,
    "tilt_unconfirmed|B_correct": 5
   },
   "fixed-wing": {
    "tilt_unconfirmed": 4,
    "tilt_unconfirmed|A_correct": 3,
    "tilt_unconfirmed|B_correct": 3,
    "confirmed": 1,
    "confirmed|A_correct": 1,
    "confirmed|B_correct": 1,
    "fallback": 2,
    "fallback|A_correct": 0,
    "fallback|B_correct": 1
   }
  },
  "factorial_tilt_multicopter_crashes": {
   "C1": 29,
   "C2": 16
  }
 },
 "A2": {
  "all|all_features": {
   "n_crash": 89,
   "n_normal": 124,
   "auc_m0": 0.8334360275462125,
   "auc_m10": 0.7986770569046756,
   "drop": 0.03475897064153688,
   "drop_ci95": [
    0.004805501046572489,
    0.07698580695395134
   ]
  },
  "all|no_tilt_stick": {
   "n_crash": 89,
   "n_normal": 124,
   "auc_m0": 0.7808988764044944,
   "auc_m10": 0.7183218557448351,
   "drop": 0.06257702065965931,
   "drop_ci95": [
    0.022650211413828523,
    0.10879250419691598
   ]
  },
  "tilt|all_features": {
   "n_crash": 43,
   "n_normal": 124,
   "auc_m0": 0.8832708177044261,
   "auc_m10": 0.799662415603901,
   "drop": 0.08360840210052511,
   "drop_ci95": [
    0.0183881566945163,
    0.13887128963183176
   ]
  },
  "tilt|no_tilt_stick": {
   "n_crash": 43,
   "n_normal": 124,
   "auc_m0": 0.8629032258064516,
   "auc_m10": 0.7482745686421606,
   "drop": 0.11462865716429105,
   "drop_ci95": [
    0.04423564223478338,
    0.1880655461433702
   ]
  },
  "tilt_multicopter|all_features": {
   "n_crash": 24,
   "n_normal": 124,
   "auc_m0": 0.8781586021505378,
   "auc_m10": 0.7644489247311828,
   "drop": 0.113709677419355,
   "drop_ci95": [
    0.026760189478313604,
    0.22219926350245486
   ]
  },
  "tilt_multicopter|no_tilt_stick": {
   "n_crash": 24,
   "n_normal": 124,
   "auc_m0": 0.7989919354838708,
   "auc_m10": 0.583467741935484,
   "drop": 0.2155241935483868,
   "drop_ci95": [
    0.0861565486606542,
    0.401746557729621
   ]
  },
  "confirmed|all_features": {
   "n_crash": 25,
   "n_normal": 124,
   "auc_m0": 0.8671612903225807,
   "auc_m10": 0.7638064516129032,
   "drop": 0.10335483870967754,
   "drop_ci95": [
    0.027248317805382973,
    0.18807358057416032
   ]
  },
  "confirmed|no_tilt_stick": {
   "n_crash": 25,
   "n_normal": 124,
   "auc_m0": 0.784258064516129,
   "auc_m10": 0.659741935483871,
   "drop": 0.12451612903225806,
   "drop_ci95": [
    0.013497479930669545,
    0.24663120707675168
   ]
  },
  "confirmed_multicopter|all_features": {
   "n_crash": 18,
   "n_normal": 124,
   "auc_m0": 0.8271505376344086,
   "auc_m10": 0.6591397849462365,
   "drop": 0.16801075268817212,
   "drop_ci95": [
    0.04786232242056956,
    0.3399928365550033
   ]
  },
  "confirmed_multicopter|no_tilt_stick": {
   "n_crash": 18,
   "n_normal": 124,
   "auc_m0": 0.6808243727598566,
   "auc_m10": 0.5260752688172043,
   "drop": 0.1547491039426523,
   "drop_ci95": [
    -0.03176738488011072,
    0.4907235450621594
   ]
  }
 },
 "A3": {
  "all_features": {
   "diff_m0_minus_m10": 0.08915268957605028,
   "ci95": [
    0.018961302462205374,
    0.16844828511537688
   ],
   "n_crash": {
    "C1": 21,
    "C2": 16
   }
  },
  "no_tilt_stick": {
   "diff_m0_minus_m10": 0.13133036101048273,
   "ci95": [
    0.04200202814680662,
    0.22612445354624433
   ],
   "n_crash": {
    "C1": 21,
    "C2": 16
   }
  },
  "abstract_keeps_material": true,
  "carried_by_tilt_stick": false
 },
 "A4": {
  "shapley_window_share": {
   "value": 0.01437056458881308,
   "ci95": [
    0.006557863565678249,
    0.023192600792045236
   ],
   "material": false
  },
  "mean_four_cell_difference_all": {
   "diff_m0_minus_m10": 0.013581354587763272,
   "ci": [
    -0.02696760347436879,
    0.03776391724967378
   ],
   "cells": {
    "C1|N1|0": {
     "auc": 0.8132820512820512,
     "n_crash": 78,
     "n_comp": 100
    },
    "C1|N1|10": {
     "auc": 0.8248802479571712,
     "n_crash": 78,
     "n_comp": 91
    },
    "C1|N2|0": {
     "auc": 0.6922100122100122,
     "n_crash": 78,
     "n_comp": 315
    },
    "C1|N2|10": {
     "auc": 0.686289059279413,
     "n_crash": 78,
     "n_comp": 311
    },
    "C2|N1|0": {
     "auc": 0.7213432835820897,
     "n_crash": 67,
     "n_comp": 100
    },
    "C2|N1|10": {
     "auc": 0.6728226996883714,
     "n_crash": 67,
     "n_comp": 91
    },
    "C2|N2|0": {
     "auc": 0.6341340914475243,
     "n_crash": 67,
     "n_comp": 315
    },
    "C2|N2|10": {
     "auc": 0.6226520132456688,
     "n_crash": 67,
     "n_comp": 311
    }
   }
  }
 },
 "B1": {
  "auc": 0.5308641975308642,
  "ci95": [
   0.4277504105090312,
   0.6333482142857142
  ],
  "n": 108
 },
 "B2": {
  "tilt_multicopter": {
   "n": 41,
   "n_pilot": 9,
   "auc": 0.6333333333333333,
   "null_sd": 0.12242810792707998,
   "p": 0.1044776119402985,
   "approx_bounds": [
    0.3933742417962566,
    0.87329242487041
   ]
  },
  "no_tilt_multicopter": {
   "n": 67,
   "n_pilot": 18,
   "auc": 0.6188208616780045,
   "null_sd": 0.09590865883755122,
   "p": 0.11442786069651742,
   "approx_bounds": [
    0.43083989035640413,
    0.806801832999605
   ]
  }
 },
 "B3": {
  "0": {
   "n": 148,
   "ba_all": 0.45982142857142855,
   "ci_all": [
    0.3807167926753621,
    0.5415040639702268
   ],
   "ba_decided": 0.49643061107938324,
   "ci_decided": [
    0.4113395408375297,
    0.5866230093372301
   ],
   "undecided_share": 0.07432432432432433,
   "recall_aircraft": 0.6696428571428571,
   "recall_pilot": 0.25,
   "aircraft_sign_share": 0.6756756756756757
  },
  "5": {
   "n": 135,
   "ba_all": 0.45398951659871867,
   "ci_all": [
    0.36665898617511516,
    0.5432520736002627
   ],
   "ba_decided": 0.49690934065934067,
   "ci_decided": [
    0.40228762981256333,
    0.5956719675367406
   ],
   "undecided_share": 0.08888888888888889,
   "recall_aircraft": 0.6138613861386139,
   "recall_pilot": 0.29411764705882354,
   "aircraft_sign_share": 0.6222222222222222
  },
  "10": {
   "n": 114,
   "ba_all": 0.39272030651340994,
   "ci_all": [
    0.3053170769816037,
    0.4955652764381211
   ],
   "ba_decided": 0.4341025641025641,
   "ci_decided": [
    0.33556059610747113,
    0.5379547817047816
   ],
   "undecided_share": 0.09649122807017543,
   "recall_aircraft": 0.5632183908045977,
   "recall_pilot": 0.2222222222222222,
   "aircraft_sign_share": 0.5964912280701754
  },
  "20": {
   "n": 100,
   "ba_all": 0.3713850837138508,
   "ci_all": [
    0.27571231617647063,
    0.47065286012296875
   ],
   "ba_decided": 0.4173076923076923,
   "ci_decided": [
    0.3105015142021721,
    0.5217391304347826
   ],
   "undecided_share": 0.11,
   "recall_aircraft": 0.5205479452054794,
   "recall_pilot": 0.2222222222222222,
   "aircraft_sign_share": 0.56
  },
  "30": {
   "n": 89,
   "ba_all": 0.3501221001221001,
   "ci_all": [
    0.25274725274725274,
    0.44908932963025766
   ],
   "ba_decided": 0.39433811802232854,
   "ci_decided": [
    0.2835610902255639,
    0.5023624236579877
   ],
   "undecided_share": 0.11235955056179775,
   "recall_aircraft": 0.5079365079365079,
   "recall_pilot": 0.19230769230769232,
   "aircraft_sign_share": 0.550561797752809
  }
 },
 "C": {
  "A": {
   "n": 47,
   "agreement": 0.9148936170212766,
   "kappa": 0.8199233716475096,
   "kappa_ci95": [
    0.6178688886436374,
    0.9571558796718322
   ]
  },
  "B": {
   "n": 48,
   "agreement": 0.7291666666666666,
   "kappa": 0.3246753246753245,
   "kappa_ci95": [
    0.10588235294117646,
    0.5714285714285715
   ]
  },
  "normal_false_alarm": [
   45,
   139
  ],
  "cue_counts_normals": {
   "impact": 40,
   "tilt": 1,
   "in_air": 4
  },
  "cue_counts_crashes": {
   "tilt": 73,
   "impact": 23,
   "descent": 21,
   "in_air": 24
  },
  "gate_passed": false
 }
}
```
