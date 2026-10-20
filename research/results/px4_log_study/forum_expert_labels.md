# Expert diagnoses from PX4 forum crash threads

**How the labels were made.** `forum_threads.py` collected 443 discuss.px4.io threads that mention a crash and a Flight Review log; 161 describe a crash and have a reply from PX4 staff, the dev team or an experienced member. One recorder filled the conclusion, cause, who and confirmation for each thread. The recording was AI-assisted (the file was written by a program) and then reviewed by the project owner; there is no second independent recorder yet. 123 of 124 supporting quotes were found word for word in their thread (checked by script). The error rate of the recording has not been measured.

Real crash threads: 148

| Expert conclusion | Threads |
|---|---|
| drone | 88 (59%) |
| unclear | 29 (20%) |
| no diagnosis given | 20 (14%) |
| pilot | 9 (6%) |
| both | 2 (1%) |

## Causes named for drone faults

| Cause | All drone verdicts (88) | Confirmed by the poster (47) |
|---|---|---|
| tuning / configuration | 29 | 15 |
| GPS / compass / estimator | 16 | 6 |
| motor / ESC / propeller | 14 | 9 |
| software / firmware bug | 11 | 7 |
| vibration / mounting | 7 | 5 |
| airframe / mechanical | 5 | 2 |
| battery / power | 4 | 3 |
| radio or data link | 2 | 0 |

## Against the uploaders' Flight Review crash ratings

15 threads link a crash-rated log.

- Rated `crash_sw_hw` (14): expert said drone 9, unclear 5
- Rated `crash_pilot` (1): expert said unclear 1

## Limits

- Forum crashes are a skewed sample: people post hard or puzzling cases, often new builds and hobby setups.
- Expert diagnoses on a forum are sometimes guesses; 'poster confirmed' is the stronger subset.
- AI-assisted recording, one recorder; a second independent recording or a measured spot-check is still needed.
