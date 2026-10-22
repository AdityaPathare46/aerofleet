# Running the review-panel evaluation on the college PC

## What this answers

AeroFleet 2.0 can ask a small "review panel" of AI agents why a flight left its plan. Before that
panel is shown in the app it has to earn its place: on the same test cases it must be **right more
often than a plain no-AI rule, and wrong no more often**. This run measures that, for one or more
language models.

Nothing here touches a drone or the app. It reads 60 generated test cases, asks a local model, and
writes a results folder.

## Which models, and why only small ones

AeroFleet is meant to run on the laptops of ordinary fleet operators. A typical laptop has 8–16 GB
of memory and no graphics card, which comfortably runs a model of about **3–4 billion parameters
(a 2–3.5 GB download)**. A 14B or 32B model would not run for most users, so it would not matter if
it did well. The run therefore compares the small models that do fit:

| Model | Download (checked in the Ollama registry, Oct 2026) | Why it is in the run |
|---|---|---|
| `qwen2.5:3b` | 1.93 GB | Known for following a fixed reply format well for its size |
| `phi4-mini` | 2.49 GB | Strong reasoning for its size; same family as the earlier forensics study |
| `gemma3:4b` | 3.35 GB | A recent small model from Google |
| `qwen3:4b` | 2.50 GB | Newer Qwen; a "thinking" model, which the runner tells to answer directly |
| `llama3.2` | 2.02 GB | The baseline that already did badly on the Mac (below) |

**The script runs all five by default.** Whether any of them is good at *this* task is unknown — that
is what the run finds out.

**Optional ceiling check, only if the PC has a graphics card with 12 GB or more:** add `qwen2.5:14b`
(8.99 GB). It is not a model to ship to users. Its job is to answer one question: if even a 14B model
cannot beat the no-AI rule, no small model will, and the AI part can be dropped without more testing.

```powershell
.\research\college_pc_panel_eval.ps1 -Models "qwen2.5:3b,phi4-mini,gemma3:4b,qwen3:4b,llama3.2,qwen2.5:14b"
```

### Two things that matter as much as the model

- **The panel is slow on a laptop.** It makes 11 model calls per finding (about 90 seconds on the Mac
  with a 3B model). The single-agent condition makes one call. If a small model does well as a single
  agent, that is the practical design for users even if the panel scores slightly higher.
- **The no-AI rule may be the answer.** It is instant, needs no download, cannot be manipulated, and on
  the first 24 cases it was right 75% of the time with no wrong calls. If no small model beats it, the
  product ships with the rule and AI stays optional.

## What you need

1. **Ollama**, version 0.5 or newer (it must support fixed reply formats): https://ollama.com/download
2. **Python** 3.10 or newer from python.org. On Windows tick "Add python.exe to PATH".
3. **The repo**: on github.com open the repo, press the green "Code" button, "Download ZIP", extract it.

No git, no account, no keys. The script installs one small Python package (`requests`) in its own folder.

## Run it — Windows

Open PowerShell in the extracted folder (the one that contains the `research` folder):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\research\college_pc_panel_eval.ps1
```

To choose models or run fewer cases:

```powershell
.\research\college_pc_panel_eval.ps1 -Models "qwen2.5:3b,phi4-mini"
.\research\college_pc_panel_eval.ps1 -N 30
```

## Run it — Linux or macOS

```bash
bash research/college_pc_panel_eval.sh
MODELS="qwen2.5:3b,phi4-mini" N=30 bash research/college_pc_panel_eval.sh
```

## How long it takes

Each case makes 11 model calls. On the Mac, `llama3.2` took about **94 seconds a case**, so 60 cases
is roughly an hour and a half per model, and **the five default models take about seven to eight
hours** without a graphics card. A graphics card should be several times faster. The script prints one
line per case, so the pace is visible after the first few.

To get a first answer sooner, run 30 cases first and the rest later — the second run continues from
where the first stopped:

```powershell
.\research\college_pc_panel_eval.ps1 -N 30
.\research\college_pc_panel_eval.ps1            # later: completes the remaining 30 for each model
```

**You can stop it at any time** (Ctrl+C, close the window, reboot) and run the same command again: it
continues from the last finished case. Each model has its own results file, so models do not mix.

## What to send back

The whole folder **`research\results\panel_eval`**. It contains one `results_<model>.jsonl` per model
(every case, every reply), `summary.md` (the tables) and `injection_reach.md`.

## How to read `summary.md`

The first table has one row per model:

- **Right** — named the true cause, or correctly deferred when there was nothing to find.
- **Wrong** — named a different cause. This is the harmful outcome: it sends a person down the wrong path.
- **Deferred** — said "needs human review" although a cause was there. Safe, but no help.
- **Panel beats the rule?** — "yes" only if the panel is right in more cases *and* wrong in no more
  cases than the no-AI rule.

Decision:

- **"yes" for some small model** — the AI suggestion goes into the app with that model, as advice only. If the single agent with that model also beats the rule, use the single agent: one call instead of eleven.
- **"no" for every small model** — the panel stays out of the app. The no-AI rule, which is already built,
  gives the likely cause instead. That is a valid result and goes in the report as measured.

Each model's own section also shows the subtle cases (where the plain rule is weak and the panel is
supposed to help), how many votes the checks threw out, and how often one compromised reviewer could
swing the panel.

## Result (college PC, October 2026) — the decision is made

Atharv ran 60 cases with four small models. The no-AI rule was right 45 times and wrong 0 times in every run.

| Model | One agent (right / wrong) | Panel (right / wrong) | One compromised reviewer changed the panel's answer |
|---|---|---|---|
| `gemma3:4b` | 10 / 0 (almost always deferred) | 3 / 36 | 49 of 60 |
| `phi4-mini` | 10 / 0 | 20 / 19 | 56 of 60 |
| `qwen2.5:3b` | 9 / 44 | 10 / 6 | 54 of 60 |
| `qwen3:4b` | 0 / 41 | 17 / 38 | 45 of 60 |

By the rule declared above, the panel stays out of the app. The product names no cause at all (the plain
rule also failed on real PX4 crash logs — `research/results/px4_log_study/`); flight reviews show an evidence
timeline instead. The rest of this runbook is kept so the test can be repeated.

## What we knew before the college run

**Mac, `llama3.2`, first 24 of 60 cases (run stopped early, 12 October 2026):**

| Method | Right | Wrong | Deferred |
|---|---|---|---|
| No-AI rule | 18 (75%) | 0 | 6 |
| One agent shown every fact | 4 (17%) | 0 | 20 |
| Panel, 5 reviewers, 2 rounds | 2 (8%) | 17 (71%) | 5 |

One compromised reviewer could push the panel to a chosen wrong cause in 13 of those 24 cases. So
with this small model the panel is worse than the rule and should not be used. These 24 cases are not
in the repo; the college run starts fresh.

**Planted text (no model needed):** 8 hostile strings were planted in 5 places an uploader controls
(the log's status text, a settings file, a flight-mode name, a setting name, the file name). **0 of 40
reached a model prompt** (`research/results/panel_eval/injection_reach.md`).

## Limits of this test

- The cases are generated (`research/panel_eval/cases.py`), not real incidents. It measures whether a
  model can read numbered evidence correctly, not how often each cause happens in the field.
- The subtle cases are built to sit inside the plain rule's thresholds, so the rule cannot do well on
  them by design. A better rule could close that gap without any AI.
- One prompt wording was used. A model that fails here might do better with a different prompt; any
  prompt changes should be tried on a different seed, not tuned on these 60 cases.

## If something goes wrong

| Symptom | Likely cause | What to do |
|---|---|---|
| "Ollama isn't installed" | Ollama missing or not on PATH | Install it, open a new PowerShell window |
| Every case shows `single UNKNOWN \| panel UNKNOWN` and finishes in a second or two | The model is not answering (wrong name, not downloaded, Ollama too old) | Run `ollama run qwen2.5:3b "hi"` to check; update Ollama |
| The PC freezes or Ollama crashes | The model is too big for the memory | Use the next smaller model in the table |
| "run this from the extracted repo folder" | Wrong folder | `cd` into the folder that contains `research` |
| Very slow (several minutes a case) | No graphics card in use | Let it run overnight, or use `-N 30` |
| `qwen3:4b` fails with an error mentioning "think" | Ollama too old for the setting that turns thinking off | Update Ollama, or drop `qwen3:4b` from `-Models` |
