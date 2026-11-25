# Public-archive search: declared test (24-25 Nov 2026)

Declared in `research/archive_search/eval_archive_search.py`, committed and pushed in `ac57848` before the first run.
Word list, sign rules and archive index frozen at `e0c43be`. Full numbers: `results.json`.

Data: 2,521 readable public PX4 logs on this computer; 1,010 carry uploader text; the text names at least one sign by
the fixed word list for 62.5% of them; 514 distinct texts were tested.

| Test | Result | Pass mark | Outcome |
|---|---|---|---|
| A1: do the signs a description's words point to appear in the same flight's log? | 15.8% of flights, against 18.0% with descriptions shuffled (lift 0.88, p = 0.98) | p <= 0.05 and lift >= 1.5 | **Failed** |
| A2: per sign (descriptive) | Battery words: the log shows a low (8 of 26) or critical (8 of 35) battery about 3x as often as overall; vibration words 2.1x (2 of 11); compass 1.0x; position, height, GPS and manual take-over at or below 1x; "mission" words can never match (archive logs have no plan) | none | Reported |
| A3: do flights with similar log signs share outcomes? (descriptive) | Crash share among the 10 most similar flights: 47.9% for 263 crash-rated flights, 40.2% for 449 good-rated (difference 0.077, p = 0.0005) | none | Reported; crash-heavy sample, not a risk score |

What follows for the product: matching logs from a description's words alone did not work, so the search no longer
does it. Logs with the same signs are offered only from one of the user's own reviewed flights, whose signs come from
its log by the same rules. Searching what other pilots wrote stays, labelled as reading, not evidence. The battery and
vibration ratios in A2 were seen after the test; any word list built on them would need its own declared test.
