# Test-flight check against expert-diagnosed crashes

Forum crash logs (expert said drone, named a matching cause): 35; normal flights: 143. Skipped: {'forum: log not downloadable': 35, 'normal: never armed': 6}.
Checks and pass marks were committed before the forum logs were downloaded.

| Expert cause | Check | Fires on expert-cause logs | Fires on normal flights | Useful? |
|---|---|---|---|---|
| tuning / configuration | C_TUNE | 13 of 15 (87%) | 18 of 142 (13%) | no |
| vibration / mounting | C_VIBE | 3 of 3 (100%) | 7 of 48 (15%) | no |
| GPS / compass / estimator | C_MAG or C_GPS | 0 of 4 (0%) | 10 of 143 (7%) | no |
| motor / ESC / propeller | C_MOTOR | 2 of 7 (29%) | 8 of 143 (6%) | no |
| battery / power | C_BATT | 0 of 4 (0%) | 4 of 143 (3%) | no |

## Every check on every forum log (any cause)

| Check | Forum crash logs | Normal flights |
|---|---|---|
| C_TUNE | 25 of 33 | 18 of 142 |
| C_VIBE | 11 of 33 | 7 of 48 |
| C_MAG | 2 of 23 | 4 of 140 |
| C_GPS | 1 of 31 | 7 of 143 |
| C_MOTOR | 9 of 35 | 8 of 143 |
| C_BATT | 5 of 33 | 4 of 143 |

## Limits

- Forum labels were recorded with AI assistance and reviewed by the project owner; quotes verified by script.
- Forum logs include the crash itself; a check that fires only because of the crash is not a pre-flight finding.
- Small numbers per cause. Thresholds are first guesses, declared in advance.
