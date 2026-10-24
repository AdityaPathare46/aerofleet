# Leave-one-out test of the troubleshooting search

Cases: 96 forum crash threads where the expert blamed the aircraft and named a cause. Each was removed from the knowledge base and used as the query. Declared in `eval_troubleshoot.py`.

| Answer | Correct | Rate | 95% CI |
|---|---|---|---|
| Top-1, title only | 19 of 96 | 20% | 13-29% |
| Top-1, title and opening-post terms | 21 of 96 | 22% | 15-31% |
| Top-1 baseline (most frequent cause) | 26 of 96 | 27% | 19-37% |
| Top-3, title only | 54 of 96 | 56% | 46-66% |
| Top-3, title and opening-post terms | 52 of 96 | 54% | 44-64% |
| Top-3 baseline (three most frequent causes) | 60 of 96 | 62% | 53-72% |

Declared criterion (top-1 with the fuller description at least 10 points above the baseline): not met.

Causes in the eligible cases: tuning / configuration 26, GPS / compass / estimator 18, motor / ESC / propeller 16, software / firmware bug 14, vibration / mounting 9, airframe / mechanical 6, battery / power 4, radio or data link 2, pilot input / handling 1.
