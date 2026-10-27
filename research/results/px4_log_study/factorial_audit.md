# Factorial optimism audit

Declared in `research/px4_log_study/factorial_audit.py` (docstring). Exploratory (dagger), declared after Round 14. Status: **completed**.

Sets: {'C1': 103, 'C1e': 12, 'C2': 67, 'N1': 100, 'N2': 372, 'S': 311}; vehicles overlapping a crash set removed: {'N1': 39, 'N2': 0}.
Anchors: {'A1': 0.8905077879444019, 'A2': 0.5589723513579642}; extractor check: {'agree': 374, 'total': 374}; permutation control: {'mean': 0.4953256226904065, 'sd': 0.05413754702354039}; logs not on disk: 0.

## Stage 1: 2 x 2 (m = 10 s, vehicle-grouped CV, full window, one extractor)

| Crashes vs comparison | n crash | n comp | AUC | SD over repeats | 95% cluster CI |
|---|---|---|---|---|---|
| C1 vs N1 | 78 | 91 | 0.825 | 0.015 | [0.699, 0.908] |
| C1 vs N2 | 78 | 311 | 0.686 | 0.008 | [0.591, 0.777] |
| C1e vs N1 (underpowered) | 10 | 91 | 0.557 | 0.090 | [0.317, 0.834] |
| C1e vs N2 (underpowered) | 10 | 311 | 0.709 | 0.017 | [0.472, 0.927] |
| C2 vs N1 | 67 | 91 | 0.673 | 0.054 | [0.540, 0.838] |
| C2 vs N2 | 67 | 311 | 0.623 | 0.018 | [0.523, 0.716] |

| Effect | Estimate | 95% CI | Supported (abs >= 0.05, CI excludes 0) |
|---|---|---|---|
| E_N | +0.094 | [-0.014, +0.197] | no |
| E_C | +0.108 | [-0.037, +0.224] | no |
| E_CN | +0.088 | [-0.145, +0.262] | no |
| E_rule | +0.122 | [-0.093, +0.317] | no |
| E_pool | -0.015 | [-0.238, +0.206] | no |

Declared wording: **The AUC depends on the comparison set; the cause is not isolated.**

## Stage 2: full factorial (descriptive)

Constant-subset crashes: {'C1': 63, 'C2': 60}. 

Total drop, most optimistic to most conservative other-aircraft cell: 0.212 [0.062, 0.335].

| Factor | Shapley share of the drop | 95% CI | Material | Main effect (drop) | 95% CI |
|---|---|---|---|---|---|
| C | +0.064 | [-0.062, +0.186] | no | +0.075 | [-0.058, +0.203] |
| N | +0.070 | [-0.033, +0.157] | no | +0.081 | [-0.021, +0.168] |
| m | +0.014 | [+0.007, +0.023] | no | +0.015 | [+0.007, +0.023] |
| CV | +0.062 | [+0.034, +0.087] | yes | +0.072 | [+0.036, +0.098] |
| W | +0.001 | [-0.031, +0.034] | no | +0.005 | [-0.026, +0.038] |

| Interaction | Estimate | 95% CI |
|---|---|---|
| CxN | +0.064 | [-0.117, +0.233] |
| Cxm | -0.009 | [-0.027, +0.008] |
| CxCV | -0.045 | [-0.086, +0.032] |
| CxW | +0.018 | [-0.041, +0.079] |
| Nxm | +0.021 | [+0.010, +0.038] |
| NxCV | +0.082 | [+0.006, +0.122] |
| NxW | +0.047 | [-0.009, +0.104] |
| mxCV | -0.006 | [-0.011, +0.003] |
| mxW | +0.030 | [+0.015, +0.046] |
| CVxW | -0.010 | [-0.041, +0.006] |

Further step N2 -> same aircraft (S) at the conservative settings: -0.211.

| Cell (factors at conservative level) | n crash | n comp | AUC | SD over repeats | 95% CI |
|---|---|---|---|---|---|
| none | 63 | 86 | 0.878 | 0.010 | [0.771, 0.949] |
| W | 63 | 86 | 0.841 | 0.021 | [0.711, 0.926] |
| CV | 63 | 86 | 0.818 | 0.017 | [0.679, 0.925] |
| CV|W | 63 | 86 | 0.763 | 0.025 | [0.614, 0.873] |
| m | 63 | 86 | 0.850 | 0.011 | [0.732, 0.936] |
| W|m | 63 | 86 | 0.841 | 0.021 | [0.711, 0.926] |
| CV|m | 63 | 86 | 0.783 | 0.017 | [0.634, 0.897] |
| CV|W|m | 63 | 86 | 0.763 | 0.025 | [0.614, 0.873] |
| N | 63 | 271 | 0.723 | 0.023 | [0.630, 0.814] |
| N|W | 63 | 271 | 0.720 | 0.026 | [0.629, 0.809] |
| CV|N | 63 | 271 | 0.694 | 0.015 | [0.583, 0.796] |
| CV|N|W | 63 | 271 | 0.689 | 0.018 | [0.577, 0.788] |
| N|m | 63 | 271 | 0.712 | 0.023 | [0.615, 0.807] |
| N|W|m | 63 | 271 | 0.720 | 0.026 | [0.629, 0.809] |
| CV|N|m | 63 | 271 | 0.685 | 0.017 | [0.574, 0.786] |
| CV|N|W|m | 63 | 271 | 0.689 | 0.018 | [0.577, 0.788] |
| C | 60 | 86 | 0.816 | 0.020 | [0.671, 0.907] |
| C|W | 60 | 86 | 0.784 | 0.027 | [0.626, 0.890] |
| C|CV | 60 | 86 | 0.702 | 0.058 | [0.541, 0.882] |
| C|CV|W | 60 | 86 | 0.608 | 0.082 | [0.460, 0.768] |
| C|m | 60 | 86 | 0.767 | 0.020 | [0.584, 0.872] |
| C|W|m | 60 | 86 | 0.784 | 0.027 | [0.626, 0.890] |
| C|CV|m | 60 | 86 | 0.609 | 0.079 | [0.439, 0.834] |
| C|CV|W|m | 60 | 86 | 0.608 | 0.082 | [0.460, 0.768] |
| C|N | 60 | 271 | 0.668 | 0.015 | [0.564, 0.759] |
| C|N|W | 60 | 271 | 0.690 | 0.018 | [0.580, 0.789] |
| C|CV|N | 60 | 271 | 0.625 | 0.029 | [0.513, 0.720] |
| C|CV|N|W | 60 | 271 | 0.666 | 0.023 | [0.557, 0.770] |
| C|N|m | 60 | 271 | 0.661 | 0.014 | [0.560, 0.753] |
| C|N|W|m | 60 | 271 | 0.690 | 0.018 | [0.580, 0.789] |
| C|CV|N|m | 60 | 271 | 0.618 | 0.034 | [0.513, 0.717] |
| C|CV|N|W|m | 60 | 271 | 0.666 | 0.023 | [0.557, 0.770] |
| same aircraft m0 full strat | 60 | 301 | 0.552 | 0.040 | [0.457, 0.619] |
| same aircraft m0 full group | 60 | 301 | 0.562 | 0.012 | [0.491, 0.621] |
| same aircraft m0 first30 strat | 60 | 301 | 0.393 | 0.047 | [0.257, 0.424] |
| same aircraft m0 first30 group | 60 | 301 | 0.455 | 0.018 | [0.377, 0.507] |
| same aircraft m10 full strat | 60 | 301 | 0.511 | 0.048 | [0.420, 0.575] |
| same aircraft m10 full group | 60 | 301 | 0.534 | 0.014 | [0.466, 0.591] |
| same aircraft m10 first30 strat | 60 | 301 | 0.393 | 0.047 | [0.257, 0.424] |
| same aircraft m10 first30 group | 60 | 301 | 0.455 | 0.018 | [0.377, 0.507] |

Bootstrap CIs resample vehicles from fixed out-of-fold scores (models not refitted). SD over repeats is the spread across CV seeds, not an interval.
