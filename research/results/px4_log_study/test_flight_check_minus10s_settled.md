# Test-flight check against expert-diagnosed crashes (window ends 10 s before the crash) — settled labels (after second coding)

Forum crash logs (expert said drone, named a matching cause): 26; normal flights: 130. Skipped: {'forum: less than 10 s airborne in the window': 11, 'forum: log not downloadable': 36, 'normal: less than 10 s airborne in the window': 13, 'normal: never armed': 6}.
Checks and pass marks were committed before the forum logs were downloaded.

| Expert cause | Check | Fires on expert-cause logs | Fires on normal flights | Useful? |
|---|---|---|---|---|
| tuning / configuration | C_TUNE | 1 of 9 (11%) | 7 of 130 (5%) | no |
| vibration / mounting | C_VIBE | 3 of 5 (60%) | 4 of 38 (11%) | no |
| GPS / compass / estimator | C_MAG or C_GPS | 1 of 4 (25%) | 5 of 130 (4%) | no |
| motor / ESC / propeller | C_MOTOR | 0 of 4 (0%) | 5 of 130 (4%) | no |
| battery / power | C_BATT | 0 of 2 (0%) | 1 of 130 (1%) | no |

## Every check on every forum log (any cause)

| Check | Forum crash logs | Normal flights |
|---|---|---|
| C_TUNE | 6 of 23 | 7 of 130 |
| C_VIBE | 5 of 23 | 4 of 38 |
| C_MAG | 3 of 17 | 3 of 129 |
| C_GPS | 1 of 22 | 2 of 130 |
| C_MOTOR | 5 of 26 | 5 of 130 |
| C_BATT | 4 of 24 | 1 of 130 |

## Limits

- Forum labels were recorded with AI assistance and reviewed by the project owner; quotes verified by script.
- Forum logs include the crash itself; a check that fires only because of the crash is not a pre-flight finding.
- Small numbers per cause. Thresholds are first guesses, declared in advance.
