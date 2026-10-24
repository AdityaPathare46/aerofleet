# Expert diagnoses from PX4 forum crash threads

**How the labels were made.** `forum_threads.py` collected 443 discuss.px4.io threads that mention a crash and a Flight Review log; 161 describe a crash and have a reply from PX4 staff, the dev team or an experienced member. One recorder filled the conclusion, cause, who and confirmation for each thread. The recording was AI-assisted (the file was written by a program) and then reviewed by the project owner; 123 of 124 supporting quotes were found word for word in their thread (checked by script). **Second, blind coding (25 Oct 2026):** a co-author coded all threads without seeing this recording; agreement on 147 threads was kappa 0.81 (95% CI 0.71-0.88) for the conclusion and 0.73 (0.65-0.81) for the cause, above the declared 0.60 ([`forum_agreement.md`](forum_agreement.md)). The 45 threads that differ were settled by the two coders ([`forum_disagreements_settled.csv`](forum_disagreements_settled.csv)).

**Labels below are the settled labels** (first recording, blind second coding, 45 disagreements settled by discussion; 13 labels changed). The first recording is kept in `forum_expert_labels_first_recording.csv`.

Real crash threads: 148

| Expert conclusion | Threads |
|---|---|
| drone | 94 (64%) |
| unclear | 25 (17%) |
| no diagnosis given | 18 (12%) |
| pilot | 9 (6%) |
| both | 2 (1%) |

## Causes named for drone faults

| Cause | All drone verdicts (94) | Confirmed by the poster (47) |
|---|---|---|
| tuning / configuration | 26 | 14 |
| GPS / compass / estimator | 18 | 6 |
| motor / ESC / propeller | 16 | 9 |
| software / firmware bug | 14 | 8 |
| vibration / mounting | 9 | 5 |
| airframe / mechanical | 5 | 2 |
| battery / power | 4 | 3 |
| radio or data link | 2 | 0 |

## Against the uploaders' Flight Review crash ratings

15 threads link a crash-rated log.

- Rated `crash_sw_hw` (14): expert said drone 11, unclear 3
- Rated `crash_pilot` (1): expert said unclear 1

## Limits

- Forum crashes are a skewed sample: people post hard or puzzling cases, often new builds and hobby setups.
- Expert diagnoses on a forum are sometimes guesses; 'poster confirmed' is the stronger subset.
- First recording AI-assisted; blind second coding agreed with kappa 0.81 (conclusion) and 0.73 (cause); disagreements settled by the two coders.
