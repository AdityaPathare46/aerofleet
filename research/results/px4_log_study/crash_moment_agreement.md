# Crash-moment check: automatic status vs one author's reading

Declared in `research/px4_log_study/crash_moment_agreement.py`. One reviewer, not blind to panel titles.

| Automatic status | can't tell | correct | no crash visible | too early | too late |
|---|---|---|---|---|---|
| confirmed | 0 | 11 | 0 | 1 | 0 |
| fallback | 2 | 2 | 18 | 0 | 2 |
| tilt_unconfirmed | 1 | 10 | 0 | 3 | 0 |

Labelled correct: 23 of 50.
Confirmed rule recall: 11 of 23; precision: 11 of 12.
Fallback logs labelled no crash visible: 18 of 24.
