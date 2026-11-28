# SA1 + FA3: Sensitivity and Vehicle-Clustered False Alarms of Today's Fleet

Declared in `research/false_alarms/measure_sa1_fa3.py`. Full JSON in `sa1_fa3_results.json`.

## FA3: False-alarm rate on ordinary public PX4 flights (vehicle-clustered)

FA1 pre-change baseline (same split): H good/great 25.3% [19.6, 31.9] (n=190), D good/great 34.9% [26.6, 44.2] (n=109).

| Cohort | Flights | Flagged | Flight Wilson 95% CI | Vehicle-Cluster 95% CI | Vehicles flagged | Mid-air batt <10% |
|---|---:|---:|---|---|---|---:|
| H good/great (primary) | 190 | 27 | 14.2% [10.0, 19.9] | 14.2% [8.5, 20.7] | 20/55 (36.4% [24.9, 49.6]) | 7 |
| H unrated ordinary | 382 | 129 | 33.8% [29.2, 38.6] | 33.8% [26.6, 40.7] | 59/148 (39.9% [32.3, 47.9]) | 41 |
| H all ordinary | 572 | 156 | 27.3% [23.8, 31.1] | 27.3% [22.1, 33.2] | 79/200 (39.5% [33.0, 46.4]) | 48 |
| D good/great (ref) | 109 | 23 | 21.1% [14.5, 29.7] | 21.1% [11.2, 33.9] | 13/37 (35.1% [21.8, 51.2]) | 3 |

FA3 pass mark (<= 20% of H good/great): **Met**.

## SA1: Sensitivity on known faults, expert-diagnosed crashes, and archive crashes

| Stratum | Flights | Flagged | Flight Wilson 95% CI | Vehicle-Cluster 95% CI |
|---|---:|---:|---|---|
| RflyMAD sensor faults | 197 | 106 | 53.8% [46.8, 60.6] | 53.8% [48.5, 64.6] |
| RflyMAD motor faults | 242 | 48 | 19.8% [15.3, 25.3] | 19.8% [8.7, 39.7] |
| RflyMAD fault-free (control) | 50 | 0 | 0.0% [0.0, 7.1] | 0.0% [0.0, 0.0] |
| Forum expert: aircraft-caused | 32 | 12 | 37.5% [22.9, 54.8] | 37.5% [21.9, 56.2] |
| Forum expert: pilot-caused | 4 | 2 | 50.0% [15.0, 85.0] | 50.0% [0.0, 100.0] |
| Archive real-hardware crashes | 133 | 49 | 36.8% [29.1, 45.3] | 36.8% [27.8, 46.0] |
| Crashed drones' prior flights (`within/`) | 445 | 118 | 26.5% [22.6, 30.8] | 26.5% [17.3, 35.2] |

SA1-RflyMAD pass mark (Real-Sensors >= 50% and Real-No_Fault <= 5%): **Met**.

## Descriptive Re-measurement on Shipped HEAD (post-M3 smoothed groundspeed, 28 Nov 2026)

Re-run of `measure_sa1_fa3.py` on shipped `HEAD` after adding the M3 2 s smoothed groundspeed filter in `evidence._airborne_spans()` (full JSON in `sa1_fa3_head_remeasure.json`; **descriptive**, on the same evaluation splits — original `ffd0f27` numbers above are preserved untouched). Flight-log rules only; whole-board false-alarm rate including settings and 90-day record age (**FA4**) remains unmeasured.

| Stratum | `ffd0f27` (pre-M3) | Shipped `HEAD` (post-M3, descriptive) | Vehicle-Cluster 95% CI (`HEAD`) |
|---|---:|---:|---|
| FA3 H good/great | 27/190 (14.2%) | **27/190 (14.2%)** | 14.2% [8.5, 20.7] |
| FA3 H unrated ordinary | 129/382 (33.8%) | **128/382 (33.5%)** | 33.5% [26.3, 40.6] |
| FA3 H all ordinary | 156/572 (27.3%) | **155/572 (27.1%)** | 27.1% [21.9, 32.7] |
| FA3 D good/great (ref) | 23/109 (21.1%) | **23/109 (21.1%)** | 21.1% [10.7, 33.7] |
| SA1 RflyMAD sensor faults | 106/197 (53.8%) | **106/197 (53.8%)** | 53.8% [48.5, 64.6] |
| SA1 RflyMAD motor faults | 48/242 (19.8%) | **48/242 (19.8%)** | 19.8% [8.7, 39.7] |
| SA1 RflyMAD fault-free (control) | 0/50 (0.0%) | **0/50 (0.0%)** | 0/50 (Wilson 95% upper bound 7.1%; bootstrap degenerate at 0) |
| SA1 Forum expert: aircraft-caused | 12/32 (37.5%) | **11/32 (34.4%)** | 34.4% [18.8, 50.0] |
| SA1 Forum expert: pilot-caused | 2/4 (50.0%) | **2/4 (50.0%)** | 50.0% [0.0, 100.0] |
| SA1 Archive real-hardware crashes | 49/133 (36.8%) | **49/133 (36.8%)** | 36.8% [27.9, 45.6] |
| SA1 Crashed drones' prior flights (`within/`) | 118/445 (26.5%) | **120/445 (27.0%)** | 27.0% [18.0, 35.7] |

