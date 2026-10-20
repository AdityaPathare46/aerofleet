# PX4 crash study, first pass

Logs read: 577; not read: {}. Source: PX4 Flight Review public logs, selection by `select_logs.py` (seed 1).

| Group | Logs | Has default record | ≥1 safety-critical setting off default | ≥1 flight-limit setting off default | ≥1 protection switched off (vs default) | Median settings off default (critical) |
|---|---|---|---|---|---|---|
| crash (all) | 100 | 57 | 57 (100%) | 57 (100%) | 29 (51%) | 5 |
| crash: drone (sw/hw) | 66 | 37 | 37 (100%) | 37 (100%) | 15 (41%) | 5 |
| crash: pilot | 34 | 20 | 20 (100%) | 20 (100%) | 14 (70%) | 5 |
| control (good/great) | 477 | 113 | 112 (99%) | 113 (100%) | 52 (46%) | 5 |

Protection switched off, crash vs control: Fisher exact p = 0.626

## Which protections were switched off (logs with a default record only)

| Setting | Crash | Control |
|---|---|---|
| `CBRK_SUPPLY_CHK` | 25 of 57 | 38 of 113 |
| `COM_RCL_EXCEPT` | 1 of 57 | 32 of 113 |
| `NAV_RCL_ACT` | 0 of 57 | 27 of 113 |
| `GF_ACTION` | 1 of 57 | 8 of 113 |
| `CBRK_AIRSPD_CHK` | 2 of 57 | 3 of 113 |

## Safety-critical settings most often off default

| Setting | Crash | Control |
|---|---|---|
| `RTL_RETURN_ALT` | 47 | 98 |
| `RTL_DESCEND_ALT` | 48 | 95 |
| `CBRK_SUPPLY_CHK` | 25 | 38 |
| `COM_POS_FS_DELAY` | 8 | 41 |
| `NAV_RCL_ACT` | 18 | 31 |
| `COM_POS_FS_EPH` | 8 | 30 |
| `NAV_DLL_ACT` | 12 | 26 |
| `COM_VEL_FS_EVH` | 7 | 29 |
| `COM_RCL_EXCEPT` | 1 | 32 |
| `BAT_CRIT_THR` | 17 | 9 |
| `GF_ACTION` | 4 | 19 |
| `COM_LOW_BAT_ACT` | 7 | 15 |
| `COM_RC_LOSS_T` | 3 | 19 |
| `COM_POS_FS_EPV` | 7 | 15 |
| `COM_PREARM_MODE` | 6 | 15 |
| `CBRK_IO_SAFETY` | 1 | 19 |
| `GF_MAX_VER_DIST` | 14 | 4 |
| `GF_MAX_HOR_DIST` | 14 | 4 |
| `BAT_LOW_THR` | 9 | 8 |
| `BAT_EMERGEN_THR` | 6 | 11 |
| `COM_POS_LOW_EPH` | 1 | 14 |
| `NAV_TRAFF_AVOID` | 1 | 12 |
| `CBRK_AIRSPD_CHK` | 9 | 3 |
| `COM_ARM_SDCARD` | 8 | 4 |
| `COM_POS_FS_GAIN` | 3 | 7 |

## Safety settings changed during the flight (crash logs only; control logs were read header-only)

0 of 100 crash logs.


## Limits

- Ratings are the uploader's own; nobody checked them. 'Good' logs are a self-selected comparison group.
- Default records exist only on newer firmware; logs without them are left out of the off-default columns.
- Control logs were downloaded only up to 2 MB, so in-flight changes are counted for crashes only.
- A protection being off is not shown to have caused any crash; this is association, on a small sample.
