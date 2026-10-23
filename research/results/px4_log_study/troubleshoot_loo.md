# Leave-one-out test of the troubleshooting search

Cases: 90 forum crash threads where the expert blamed the aircraft and named a cause. Each was removed from the knowledge base and used as the query. Declared in `eval_troubleshoot.py`.

| Answer | Correct | Rate | 95% CI |
|---|---|---|---|
| Top-1, title only | 17 of 90 | 19% | 12-28% |
| Top-1, title and opening-post terms | 18 of 90 | 20% | 13-29% |
| Top-1 baseline (most frequent cause) | 29 of 90 | 32% | 23-42% |
| Top-3, title only | 45 of 90 | 50% | 40-60% |
| Top-3, title and opening-post terms | 48 of 90 | 53% | 43-63% |
| Top-3 baseline (three most frequent causes) | 59 of 90 | 66% | 55-75% |

Declared criterion (top-1 with the fuller description at least 10 points above the baseline): not met.

Causes in the eligible cases: tuning / configuration 29, GPS / compass / estimator 16, motor / ESC / propeller 14, software / firmware bug 11, vibration / mounting 7, airframe / mechanical 6, battery / power 4, radio or data link 2, pilot input / handling 1.
