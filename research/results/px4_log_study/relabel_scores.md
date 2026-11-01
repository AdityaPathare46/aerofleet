# Independent relabelling

Declared in `research/px4_log_study/score_relabel.py`.

```
{
 "n_cases": 72,
 "n_returned": 72,
 "cross_table_expert_x_uploader": {
  "pilot|aircraft": 16,
  "aircraft|pilot": 16,
  "pilot|pilot": 12,
  "aircraft|aircraft": 14,
  "environment|pilot": 7,
  "environment|aircraft": 6,
  "can't tell|pilot": 1
 },
 "R1_R3_all": {
  "n_decided": 58,
  "agreement": 0.4482758620689655,
  "kappa": -0.10476190476190479,
  "kappa_ci": [
   -0.3448275862068966,
   0.1657472894210199
  ],
  "rule_ba_vs_expert": 0.5464285714285714,
  "rule_ba_ci": [
   0.42378776241679467,
   0.6641271455787583
  ],
  "rule_ba_vs_uploader_same_cases": 0.35595238095238096,
  "flightmd_ba_vs_expert": 0.5238095238095238,
  "flightmd_ba_ci": [
   0.4050409226190476,
   0.6397589083710404
  ],
  "tilt_auc_vs_expert": 0.5357142857142857,
  "tilt_auc_ci": [
   0.41096529308310514,
   0.6604011873543121
  ]
 },
 "R4_high_medium": {
  "n_decided": 58,
  "agreement": 0.4482758620689655,
  "kappa": -0.10476190476190479,
  "kappa_ci": [
   -0.3448275862068966,
   0.1657472894210199
  ],
  "rule_ba_vs_expert": 0.5464285714285714,
  "rule_ba_ci": [
   0.42378776241679467,
   0.6641271455787583
  ],
  "rule_ba_vs_uploader_same_cases": 0.35595238095238096,
  "flightmd_ba_vs_expert": 0.5238095238095238,
  "flightmd_ba_ci": [
   0.4050409226190476,
   0.6397589083710404
  ],
  "tilt_auc_vs_expert": 0.5357142857142857,
  "tilt_auc_ci": [
   0.41096529308310514,
   0.6604011873543121
  ]
 },
 "R2": {
  "pilot": {
   "n": 36,
   "called_aircraft": 16,
   "ci": [
    0.2954102987654314,
    0.6041921268399659
   ],
   "cant_tell": 1,
   "environment": 7,
   "no_crash_visible": 1
  },
  "aircraft": {
   "n": 36,
   "called_pilot": 16,
   "ci": [
    0.2954102987654314,
    0.6041921268399659
   ],
   "cant_tell": 0,
   "environment": 6,
   "no_crash_visible": 0
  }
 },
 "wording": "not explained by uploader labels",
 "limits": "one expert; 72 cases; plots, not the raw log; balanced sample, R2 shares are per rating"
}
```
