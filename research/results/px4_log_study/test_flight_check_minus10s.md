# Test-flight check against expert-diagnosed crashes (window ends 10 s before the crash)

Forum crash logs (expert said drone, named a matching cause): 24; normal flights: 130. Skipped: {'forum: less than 10 s airborne in the window': 11, 'forum: log not downloadable': 35, 'normal: less than 10 s airborne in the window': 13, 'normal: never armed': 6}.
Checks and pass marks were committed before the forum logs were downloaded.

| Expert cause | Check | Fires on expert-cause logs | Fires on normal flights | Useful? |
|---|---|---|---|---|
| tuning / configuration | C_TUNE | 2 of 10 (20%) | 7 of 130 (5%) | no |
| vibration / mounting | C_VIBE | 3 of 3 (100%) | 4 of 38 (11%) | no |
| GPS / compass / estimator | C_MAG or C_GPS | 0 of 3 (0%) | 5 of 130 (4%) | no |
| motor / ESC / propeller | C_MOTOR | 1 of 4 (25%) | 5 of 130 (4%) | no |
| battery / power | C_BATT | 0 of 2 (0%) | 1 of 130 (1%) | no |

## Every check on every forum log (any cause)

| Check | Forum crash logs | Normal flights |
|---|---|---|
| C_TUNE | 5 of 22 | 7 of 130 |
| C_VIBE | 6 of 22 | 4 of 38 |
| C_MAG | 2 of 15 | 3 of 129 |
| C_GPS | 1 of 21 | 2 of 130 |
| C_MOTOR | 6 of 24 | 5 of 130 |
| C_BATT | 5 of 22 | 1 of 130 |

## Limits

- Forum labels were recorded with AI assistance and reviewed by the project owner; quotes verified by script.
- Forum logs include the crash itself; a check that fires only because of the crash is not a pre-flight finding.
- Small numbers per cause. Thresholds are first guesses, declared in advance.
