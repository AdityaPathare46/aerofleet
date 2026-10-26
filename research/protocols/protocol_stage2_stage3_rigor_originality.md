# Pre-Declared Protocol: Stage 2 & Stage 3 Rigor, Originality, and Significance Extensions

**Date:** 26 October 2026  
**Status:** Exploratory ($\dagger$) additions requested in journal peer review.  
**Governing Principle:** All hypotheses, criteria, sampling schemes, feature definitions, and random seeds are committed to version control *before* the corresponding code is executed. Every empirical number must derive strictly from executed code.

---

## 1. Analysis A4: Depth-3 Decision Tree Bootstrap Bounds across Cut-offs

- **Objective:** Evaluate non-linear classification bounds on Task B (pilot vs. drone attribution among uploader-labelled crashes) across all crash-window margins $m \in \{0, 2, 5, 10, 20, 30\}$\,s.
- **Sample Selection:** All uploader-labelled crash flights with usable telemetry windows ($n=148$ at $m=0$\,s, $142$ at $m=2$\,s, $135$ at $m=5$\,s, $114$ at $m=10$\,s, $100$ at $m=20$\,s, $89$ at $m=30$\,s) from `leak_curve_features.jsonl`.
- **Features:** The 11 standard telemetry features (`tune_rms`, `tilt_p95`, `vib_p95`, `clip_rate`, `sat_frac`, `batt_min`, `volt_sag`, `gps_bad`, `failsafe`, `manual_frac`, `stick_p95`), with median imputation on training folds.
- **Model:** Recursive binary classification tree constrained to `max_depth = 3`, `min_samples_split = 5`, splitting on Gini impurity.
- **Validation:** Stratified 5-fold cross-validation.
- **Uncertainty & Decision Criterion:** 1,000 bootstrap resamples over flights (seed `123`). If upper 95% bootstrap bound $\le 0.66$ (the permutation null threshold), non-linear models are bound within the null; if upper bounds exceed 0.66, non-linear models remain inconclusive and the 0.73 estimate is documented as an empirical upper bound at specific margins rather than a global characteristic.

---

## 2. Analysis A8: Permutation Null Variance with Fixed Scores vs. CV Re-fitting

- **Objective:** Determine whether the wider permutation standard deviation (0.090) observed for Task B under 5-fold cross-validation relative to the asymptotic Wilcoxon standard error (0.056) is an artifact of cross-validation fold splitting and model coefficient re-estimation under 3:1 class imbalance (112 drone vs. 36 pilot).
- **Hypothesis $H_{\text{perm}}$:** Under a fixed predictive score vector (no fold splitting or model refitting), the empirical permutation standard deviation over 10,000 label shuffles will match the theoretical asymptotic standard error $\text{SE}_{\text{null}} = \sqrt{(36 + 112 + 1) / (12 \times 36 \times 112)} \approx 0.0555$ within $\pm 0.002$.
- **Procedure:**
  1. Fix the score vector $s \in \mathbb{R}^{148}$ (both random normal scores and in-sample fitted scores).
  2. Perform 10,000 random permutations of the true binary labels $y \in \{0, 1\}^{148}$ (seed `42`).
  3. Compute the Mann-Whitney $U$ / AUC for each permutation.
  4. Compare empirical standard deviation to $\text{SE}_{\text{null}} = 0.0555$.

---

## 3. Analysis A6: Eight-Sign Attribution Rule and Task A Crash-Window Ablation

- **Objective:** Evaluate the sensitivity of the eight hand-coded aircraft fault signs (`D_BATT`, `D_MOTOR`, `D_CLIP`, `D_GPS`, `D_FD`, `D_ERR`, `D_CPU`, `D_FAILSAFE`) and the overall attribution rule across window margins $m \in \{0, 2, 5, 10, 20, 30\}$\,s on all 205 crashes and 143 normal flights.
- **Hypothesis $H_{\text{sign-ablation}}$:** Firing rates of impact/tumble-sensitive signs (specifically `D_MOTOR`, `D_CLIP`, `D_FAILSAFE`) will decline monotonically as $m$ increases from 0 to 30\,s in crashes, but will remain stable in normal flights where no terminal impact occurs. If normal flight firing rates also decline, it indicates that truncation shortens the exposure window rather than isolating crash-induced telemetry artifacts.
- **Procedure:**
  1. Re-evaluate `evidence(u)` with window cut at $t_c - m \times 10^6\,\mu\text{s}$ (crashes: first tilt $>60^\circ$ or disarm; normal: disarm).
  2. Drop logs with feature window $< 10$\,s.
  3. Record individual sign firing frequencies and overall rule predictions (`DRONE`, `PILOT`, `UNKNOWN`).

---

## 4. Analysis A7: Between-Drone Robustness, Heterogeneity, and GPS Ordering

- **Objective:** Address four residual methodological questions on the between-drone vibration result:
  1. **Source Heterogeneity:** Test whether the mean scaled rank on the older estimator metric ($\bar r = 0.68, n=48$) differs significantly from the newer accelerometer metric ($\bar r = 0.58, n=19$ pooled; $\bar r = 0.50, n=10$ new) using a two-sample permutation test (100,000 draws).
  2. **GPS Crash-Day Ordering:** Parse absolute GPS epoch timestamps for all 25 sets with crash-day flights to verify that pre-crash exposure flights strictly preceded the crash log, excluding any ambiguous or post-crash flights.
  3. **Experimental Airframe Proxies:** Correlate drone pre-crash vibration ranks against indicators of experimental or prototype testing: manual flight mode proportion, flights per vehicle, and flight duration variability.
  4. **Control Clustering Adjustment:** Re-evaluate the between-drone rank test using a cluster bootstrap (2,000 resamples over unique control airframes, seed `314`) to verify that the 17 reused control drones do not artificially narrow the confidence interval or inflate significance.

---

## 5. Analysis O1: Factorial Decomposition of Model Separation

- **Objective:** Provide a full factorial decomposition ($2 \times 2 \times 2 \times 2 = 16$ cells) on a single fixed flight cohort ($n=372$ flights across 67 airframes: 67 crash flights and 305 earlier flights, paired with 134 matched other-aircraft controls).
- **Factors:**
  1. **Comparison Population:** Same airframe longitudinal flights vs. other aircraft matched controls.
  2. **Cross-Validation Scheme:** Standard stratified 5-fold CV vs. Vehicle-Grouped CV (Group-CV).
  3. **Duration Matching:** Uncalipered vs. Caliper-matched ($|\Delta \ln(\text{duration})| \le 0.50$).
  4. **Window Cut:** Full flight ($m=0$\,s) vs. Crash-window removed ($m=10$\,s).
- **Statistic:** Logistic regression ROC AUC with two-stage cluster bootstrap 95% confidence intervals (2,000 resamples, seed `2026`).
- **Payoff:** Quantifies the exact percentage of the $0.88 \to 0.53$ drop attributable to each factor and interaction term via ANOVA/variance decomposition.

---

## 6. Significance Extensions S1, S2, and S4

- **S1 (Operator Requirements Statement):** Derive minimum analytical specifications for operational deployment:
  - Required AUC for automated responsibility verdict ($\ge 0.85$).
  - Required sample size for 80% statistical power given observed permutation noise ($\ge 250$ independently verified pilot-fault crashes).
  - Required sensitivity and fleet base rate for operational vibration screening to achieve $\text{PPV} \ge 10\%$ at $\le 10$ inspections per true positive.
- **S2 (Inspection-Cost Curve):** Plot inspections needed per detected crash as a function of the operational flag rate (1% to 50%), incorporating a 95% bootstrap band reflecting both case sensitivity uncertainty and reference control quantile estimation uncertainty.
- **S4 (Reporting Checklist):** Formulate an 8-item normative evaluation checklist for drone log diagnostic studies:
  1. Event-window leakage exclusion ($\ge 10$\,s pre-impact cutoff).
  2. Longitudinal within-airframe baseline matching.
  3. Cluster-grouped cross-validation by vehicle identifier.
  4. Flight duration caliper matching ($|\Delta \ln| \le 0.50$).
  5. Multi-rater ground-truth provenance and inter-coder agreement ($\kappa \ge 0.70$).
  6. Operational base-rate calibration and exact Bayes PPV.
  7. Pre-registration of hypotheses and pass marks in immutable version control.
  8. Code, raw telemetry, and derived feature deposit in persistent open archives.
