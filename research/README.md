# Research

Every number in the paper and README traces back to a file here. Each study script's docstring is its declaration:
what was tested, on which data, and the pass mark, committed before the script was run.

| Path | What |
|---|---|
| `px4_log_study/` | The PX4 Flight Review study (Q1-Q4), the tool's validation tests (injected deviations, real missions, leave-one-out search, newer-metric replication), forum label tools and `SECOND_CODER.md` |
| `results/px4_log_study/` | All results: markdown summaries and per-log jsonl; forum labels (settled) and the first recording |
| `panel_eval/`, `results/panel_eval/` | The language-model review-panel test (research only; no AI in the product) |
| `protocols/` | Declared future studies: prospective vibration test, 3D user study |
| `deconflict_scale.py`, `drift_catalogue_check.py`, `wind_altitude_study.py` | Engineering checks of the deconfliction, drift catalogue and wind features (results in `results/`) |

Raw logs and forum text are not in git: logs are on the One Touch drive (`AeroFleet_px4_data/`, see `docs/HANDOFF.md`)
and public on PX4 Flight Review by log id.
