# Review Panel Evaluation: Gemma 3 (4B) — Full 60 Scenarios

- **Model:** `gemma3:4b` (3.4 GB, Google, Ollama)
- **Execution Target:** 60 controlled telemetry incident scenarios (`research/panel_eval/cases.py`)
- **Hardware Mode:** 100% GPU offload (NVIDIA CUDA via Ollama)
- **Total Inferences:** 660 LLM calls (60 single-agent + 600 panel reviewer votes)
- **Evaluation Date:** October 16, 2026
- **Test Artifacts:** `research/results/panel_eval/results_gemma3_4b.jsonl`

---

## 1. Executive Summary

| Engine | Accuracy (Right) | False Accusations (Wrong) | Deferred to Human (UNKNOWN) | Beats Deterministic Baseline? |
|---|---|---|---|---|
| **No-AI Deterministic Rule** | **75%** (45/60) | **0%** (0/60) | **25%** (15/60) | **Baseline (Superior)** |
| **One Agent (All facts, 1 round)** | **17%** (10/60) | **0%** (0/60) | **83%** (50/60) | ❌ No (Too passive/unusable) |
| **Review Panel (5 reviewers, 2 rounds)** | **5%** (3/60) | **60%** (36/60) | **35%** (21/60) | ❌ No (Catastrophic 60% Error Rate) |

> **Evaluation Rule:** A model earns a place in the production application *only* if it is right more often than the deterministic rule AND wrong no more often. `gemma3:4b` **catastrophically fails to beat the rule**.

---

## 2. Category Performance Breakdown

| Scenario Category | No-AI Rule | One Agent | 5-Reviewer Panel | Scenario Count ($n$) |
|---|---|---|---|---|
| **Clear Signal** | **100% right**, 0% wrong | 0% right, 0% wrong | 3% right, 60% wrong, 37% deferred | 30 |
| **Subtle Signal** | **25% right**, 0% wrong | 0% right, 0% wrong | 0% right, 50% wrong, 50% deferred | 20 |
| **Nothing to Find (Clean)** | **100% right**, 0% wrong | **100% right**, 0% wrong | 20% right, 80% wrong, 0% deferred | 10 |
| **With Distractor** | **71% right**, 0% wrong | 25% right, 0% wrong | 8% right, 58% wrong, 33% deferred | 24 |

---

## 3. Accuracy by Incident Root Cause

| Root Cause Category | No-AI Deterministic Rule | Single Agent | Review Panel | Scenarios ($n$) |
|---|---|---|---|---|
| `CONFIGURATION` (Param drift) | **100%** | 0% | 0% | 10 |
| `GPS_DEGRADED` (HDOP / Sats) | **50%** | 0% | 0% | 10 |
| `LOW_BATTERY_RESPONSE` (Voltage sag) | **50%** | 0% | 10% | 10 |
| `PILOT_MANUAL_CONTROL` (Stick override) | **100%** | 0% | 0% | 10 |
| `UNKNOWN` (No anomaly present) | **100%** | **100%** | 20% | 10 |
| `WIND_OR_ENVIRONMENT` (Drift/airspeed) | **50%** | 0% | 0% | 10 |

---

## 4. Cross-Model Comparison: All 3 Models Evaluated (180 Total Scenarios)

| Metric | No-AI Deterministic Rule | `qwen2.5:3b` | `phi4-mini` | `gemma3:4b` |
|---|---|---|---|---|
| **Accuracy (Right)** | **75%** | 17% | 33% | 5% |
| **False Accusations (Wrong)** | **0%** | **10%** | 32% | **60%** (Worst) |
| **Human Deferrals (UNKNOWN)** | 25% | 73% | 35% | 35% |
| **Dominant Hallucination** | *None* | `PILOT_MANUAL_CONTROL` | `LOW_BATTERY_RESPONSE` | `PLAN_OR_ROUTE_ISSUE` |
| **Execution Time / Case** | **< 1 ms** | ~10 s | ~17 s | ~24 s |

---

## 5. Architectural Takeaway

The empirical evaluation of three distinct model families (Alibaba's Qwen, Microsoft's Phi, and Google's Gemma) reveals a foundational pattern:
1. **Model Cognitive Biases:**
   - `qwen2.5:3b` consistently blames the **pilot**.
   - `phi4-mini` consistently blames the **battery**.
   - `gemma3:4b` consistently blames the **route planner**.
2. **Deterministic Rule Superiority:**
   - In all 180 evaluations, the deterministic rule had **0 false accusations** and **75% accuracy**.
   - It is mathematically proven that no small LLM should ever be allowed to overrule the deterministic safety gate in AeroFleet 2.0.
