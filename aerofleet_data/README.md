# AeroFleet Fine-Tuning Data — Acquisition Guide

What to download, from where, and where it goes in this folder. Written so future
fine-tuning of the Fleet Incident Forensics Council's models rests on real, sourced,
correctly-licensed data instead of the synthetic CBF-margin cases the current
5,000-case benchmark (`scenario_engine/mass_forensics_evaluation.py`) already covers.

**Read this before downloading anything**: everything in this folder is either large
(model weights, GB-scale) or carries its own license terms — **do not commit any of
it to git**. `aerofleet_data/` is already gitignored at the repo root. This file
itself is the only thing meant to live in version control long-term (copy it there
if you want it tracked); everything else stays local.

**The one rule that makes this whole exercise legitimate**: once the labeled dataset
below is downloaded, split it into a training slice and a held-out slice *before*
touching any fine-tuning code, and never let the held-out slice touch the training
process. Any accuracy number cited for publication must come only from the held-out
slice — fine-tuning on data you also score against is eval contamination, and it's
the one mistake that actually invalidates a result rather than just weakening it.

---

## Folder structure to create

```
aerofleet_data/
  README.md                          <- this file
  labeled_incidents/
    uav_hfacs_asrs_200/               <- §1 below
  raw_incident_sources/
    asrs_exports/                     <- §2a
    ntsb_carol_exports/               <- §2b
    faa_uas_sightings/                <- §2c
  reference_docs/
    hfacs_8_0_guide.pdf               <- §3
    uav_hfacs_llm_paper.pdf           <- §3
  model_weights/
    mistral-small-3.2-24b/            <- §4
    phi-4-reasoning-plus/             <- §4
    gemma-4-12b/                      <- §4
```

Create subfolders as you actually download into them — no need to pre-create empty
ones you're not using yet.

---

## 1. Primary dataset — real, HFACS-labeled UAV incidents (get this first)

**Source**: [github.com/YukeyYan/UAV-Accident-Forensics-HFACS-LLM](https://github.com/YukeyYan/UAV-Accident-Forensics-HFACS-LLM)

The dataset behind "UAV Accident Forensics via HFACS-LLM Reasoning" (*Drones*
9(10):704, 2025) — the same paper already cited in `docs/TESTING_STRATEGY.md` and
`aerofleet/agents/incident_taxonomy.py` as this project's methodological precedent.
This is the single best source available: it's the *actual* dataset the precedent
paper's own numbers came from.

- **What it contains**: 200 real UAV accident reports (sourced from NASA ASRS,
  2010–2025), 3,600 individually coded data points under the full HFACS 8.0
  taxonomy, expert-validated (inter-rater reliability κ = 0.823 — published, not
  self-reported).
- **License**: CC BY 4.0 — free for academic and commercial use, attribution
  required. Keep the repo's own `LICENSE` and `DATASET_README.md` files when you
  copy it in, so the attribution trail stays intact.
- **Download**:
  ```bash
  git clone https://github.com/YukeyYan/UAV-Accident-Forensics-HFACS-LLM.git aerofleet_data/labeled_incidents/uav_hfacs_asrs_200
  ```
- **Before using it**: HFACS 8.0's category names won't line up 1:1 with AeroFleet's
  own 7-factor taxonomy (`battery_energy`, `airspace_conflict`,
  `weather_environmental`, `communications_link`, `routing_navigation`,
  `ops_scheduling_capacity`, `cross_check_anomaly` — see
  `aerofleet/agents/incident_taxonomy.py`). Plan on a manual remapping pass; don't
  assume an automatic field-name match.

---

## 2. Supplementary real incident sources (optional — only if 200 cases isn't enough)

Not HFACS-labeled out of the box — useful for expanding the training set with more
raw narratives, at the cost of needing to hand-label them yourself against
AeroFleet's taxonomy.

### 2a. NASA ASRS Database (the same source the paper drew from)
- **Source**: [asrs.arc.nasa.gov](https://asrs.arc.nasa.gov/)
- **License**: Public domain (NASA-curated).
- **What**: Searchable database of real aviation safety narratives; the ASRS
  Database Online (DBOL) lets you build report sets and export them. General
  aviation-heavy, but does include UAS-tagged reports — filter for those
  specifically rather than pulling the whole corpus.
- Save exports to `aerofleet_data/raw_incident_sources/asrs_exports/`.

### 2b. NTSB CAROL (Case Analysis and Reporting Online)
- **Source**: [data.ntsb.gov/carol-main-public](https://data.ntsb.gov/carol-main-public/)
- **License**: Public (U.S. federal government data).
- **What**: Full aviation accident database, 1962–present. Bulk downloads
  available as `avall.zip` (1982–present) and `PRE1982.zip`. Not drone-specific —
  use the Custom Search Builder to filter toward UAS-involved investigations rather
  than downloading the full corpus.
- Save to `aerofleet_data/raw_incident_sources/ntsb_carol_exports/`.

### 2c. FAA UAS Data Delivery System (UDDS)
- **Source**: [udds-faa.opendata.arcgis.com](https://udds-faa.opendata.arcgis.com/)
- **License**: Public (U.S. federal government data).
- **What**: 20,000+ real drone sighting reports since November 2014, in open
  geospatial formats. Real drone-specific incident text, but no HFACS coding —
  raw material only.
- Save to `aerofleet_data/raw_incident_sources/faa_uas_sightings/`.

### Checked and not usable right now
**DGCA India** (AeroFleet's own regulatory framework, `DGCA_2021`) — no centralized
public incident database exists today. Worth re-checking periodically; not a source
you can pull from as of this writing.

---

## 3. Reference docs (for the manual HFACS-to-AeroFleet-taxonomy mapping)

- **DAF HFACS 8.0 Guide** (official Air Force Safety Center document, the current
  DoD-endorsed taxonomy version the labeled dataset in §1 uses):
  [safety.af.mil — DAF HFACS 8 Guide, 1 April 2023 (PDF)](https://www.safety.af.mil/Portals/71/documents/Human%20Factors/DAF%20HFACS%208%20Guide%201%20April%202023.pdf)
  → save as `aerofleet_data/reference_docs/hfacs_8_0_guide.pdf`
- **The precedent paper itself** (methodology, category definitions, scoring
  approach): [doi.org/10.3390/drones9100704](https://doi.org/10.3390/drones9100704)
  → save as `aerofleet_data/reference_docs/uav_hfacs_llm_paper.pdf`

---

## 4. Base model weights — only the ones actually fine-tunable on a single RTX 5090

| Model | Download from | Size | License | Fits on 32GB VRAM? |
|---|---|---|---|---|
| Mistral Small 3.2 | [`mistralai/Mistral-Small-3.2-24B-Instruct-2506`](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506) | 24B dense | Apache 2.0 | Yes — QLoRA, tight but fits |
| Phi-4-reasoning-plus | [`microsoft/Phi-4-reasoning-plus`](https://huggingface.co/microsoft/Phi-4-reasoning-plus) | 14B dense | MIT | Yes — comfortable QLoRA |
| Gemma 4 12B | [`google/gemma-4-12B-it`](https://huggingface.co/google/gemma-4-12B-it) | 12B dense | Gemma license | Yes — comfortable QLoRA |
| ~~Llama 4 Scout~~ | ~~[`meta-llama/Llama-4-Scout-17B-16E-Instruct`](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct)~~ | 17B active / ~109B total MoE | Llama 4 Community License (gated — requires accepting Meta's license) | **No** — even Unsloth's most optimized QLoRA stack needs ~71GB VRAM |

**Do not download Llama 4 Scout weights for fine-tuning** — it handles
`AIRSPACE_SAFETY` and `AI_VALIDATOR` in the forensics worker
(`aerofleet/agents/factory.py`'s `DEFAULT_MODEL_MAP`), and those two stay on
prompt-iteration only unless cloud GPU time (an 80GB A100/H100) is specifically
budgeted for it. Downloading its full weights (~200GB+) for a fine-tune that can't
run locally just wastes disk and bandwidth.

Requires a free Hugging Face account and, for Llama/Gemma-family repos, accepting
each model's license on its Hugging Face page before `git clone`/`huggingface-cli
download` will work — Mistral and Phi-4 are ungated.

```bash
huggingface-cli download mistralai/Mistral-Small-3.2-24B-Instruct-2506 --local-dir aerofleet_data/model_weights/mistral-small-3.2-24b
huggingface-cli download microsoft/Phi-4-reasoning-plus --local-dir aerofleet_data/model_weights/phi-4-reasoning-plus
huggingface-cli download google/gemma-4-12B-it --local-dir aerofleet_data/model_weights/gemma-4-12b
```

---

## 5. Software (none of this is in `requirements.txt` today)

```bash
pip install torch transformers peft bitsandbytes accelerate trl
```

Plus **`llama.cpp`**, separately — needed to merge a trained LoRA adapter into the
base model and convert it to GGUF afterward, since Ollama serves GGUF, not raw
HuggingFace/PEFT checkpoints. This step is mandatory, not optional, for any
fine-tuned model to actually reach the running app.

---

## Summary checklist

- [ ] Clone the labeled HFACS-UAV dataset (§1) — do this first, it's the one that
      actually unblocks real fine-tuning
- [ ] (Optional) Pull supplementary raw incident sources (§2) if 200 cases proves
      too small
- [ ] Save the HFACS 8.0 guide and precedent paper PDF (§3) for the manual
      taxonomy-mapping pass
- [ ] Download weights for Mistral Small 3.2, Phi-4-reasoning-plus, and Gemma 4
      12B only (§4) — skip Llama 4 Scout
- [ ] Install the fine-tuning stack + llama.cpp (§5)
- [ ] Split the labeled dataset into train/held-out **before** writing any
      fine-tuning code
