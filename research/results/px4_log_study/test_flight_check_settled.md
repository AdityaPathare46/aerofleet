# Test-flight check against expert-diagnosed crashes — settled labels (after second coding)

Forum crash logs (expert said drone, named a matching cause): 37; normal flights: 143. Skipped: {'forum: log not downloadable': 36, 'normal: never armed': 6}.
Checks and pass marks were committed before the forum logs were downloaded.

| Expert cause | Check | Fires on expert-cause logs | Fires on normal flights | Useful? |
|---|---|---|---|---|
| tuning / configuration | C_TUNE | 10 of 12 (83%) | 18 of 142 (13%) | no |
| vibration / mounting | C_VIBE | 3 of 5 (60%) | 7 of 48 (15%) | no |
| GPS / compass / estimator | C_MAG or C_GPS | 1 of 5 (20%) | 10 of 143 (7%) | no |
| motor / ESC / propeller | C_MOTOR | 1 of 9 (11%) | 8 of 143 (6%) | no |
| battery / power | C_BATT | 0 of 4 (0%) | 4 of 143 (3%) | no |

## Every check on every forum log (any cause)

| Check | Forum crash logs | Normal flights |
|---|---|---|
| C_TUNE | 26 of 34 | 18 of 142 |
| C_VIBE | 10 of 34 | 7 of 48 |
| C_MAG | 3 of 25 | 4 of 140 |
| C_GPS | 1 of 32 | 7 of 143 |
| C_MOTOR | 8 of 37 | 8 of 143 |
| C_BATT | 4 of 35 | 4 of 143 |

## Limits

- Forum labels were recorded with AI assistance and reviewed by the project owner; quotes verified by script.
- Forum logs include the crash itself; a check that fires only because of the crash is not a pre-flight finding.
- Small numbers per cause. Thresholds are first guesses, declared in advance.
