# AeroFleet Data & Reference Acquisition Guide

**Status: everything marked ✅ below has already been downloaded into this folder.**
Everything marked ⛔ could not be fetched automatically (bot-blocked publisher/.mil
sites, or an interactive-only search interface with no bulk URL) — see the **"Not
downloaded — do these manually"** list near the bottom for exactly what's left and
why. Model weights were deliberately not attempted; see that section for why.

Everything real, drone/DGCA-related, and downloadable that's worth pulling in for
this project — not just fine-tuning data. Two different purposes, kept separate
below: **§0** grounds the *app itself* (the regulatory rules and real coordinates
`aerofleet/city/restricted_sites.py`'s zone model is built on) in official sources;
**§1 onward** is data for a future, legitimate fine-tuning pass on the Fleet
Incident Forensics Council's models, instead of the synthetic CBF-margin cases the
current 5,000-case benchmark (`scenario_engine/mass_forensics_evaluation.py`)
already covers.

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
  regulatory_docs/
    dgca_drone_rules_2021.pdf          <- §0a
    dgca_car_s3_x_part1_2018.pdf       <- §0a
  geospatial/
    in_airports_ourairports.csv        <- §0b
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

## 0. Grounding the app itself — DGCA regulations & real airspace coordinates ✅ downloaded

Not fine-tuning data — this is for `aerofleet/city/restricted_sites.py`, the module
that already models DGCA-style Red/Yellow/Green airspace zones. Its own docstring is
upfront that it's "rule-grounded rather than shapefile-precise," and that Digital
Sky's live NPNT platform "isn't publicly queryable by automated means" — confirmed
true, still, via search: there's no bulk KML/shapefile export of the actual
Digital Sky airspace map anywhere public. That part doesn't change. What *can*
genuinely improve is the two things the module's radii and coordinates are built
from.

### 0a. Official DGCA regulatory documents ✅
- **Drone Rules, 2021** — DGCA's own server (`dgca.gov.in`) serves this behind a
  JavaScript PDF viewer that doesn't return the raw file to a script, so this was
  fetched from a real mirror instead: a Telangana High Court document repository
  (`.nic.in`, Indian government domain) that hosts the identical 25-page gazette
  notification. Saved to `aerofleet_data/regulatory_docs/dgca_drone_rules_2021.pdf`
  (8.0 MB, verified by page count).
- **CAR Section 3, Series X, Part I (2018)** — fetched directly from DGCA's own S3
  bucket, no mirror needed. Drone weight categories (Nano/Micro/Small/Medium/Large),
  useful to sanity-check the app's fleet defaults (`config/default.yaml`'s
  `drone_payload_kg: 5.0`, `battery_capacity_wh: 500.0`) against a real DGCA
  category. Saved to `aerofleet_data/regulatory_docs/dgca_car_s3_x_part1_2018.pdf`
  (711 KB, 37 pages, verified — document metadata identifies it as the real
  `D3X-X1.docx` CAR filed by DGCA in 2018).
- **License**: Indian government public documents — free to read/cite; not
  redistributable as your own work without attribution to DGCA/Ministry of Civil
  Aviation.

### 0b. Real airport coordinates (for precise Red/Yellow zone anchor points) ✅
- **Source**: [OurAirports — India](https://ourairports.com/countries/IN/) /
  [raw CSV via GitHub](https://github.com/davidmegginson/ourairports-data)
- **License**: Public domain, no warranty of accuracy stated by the maintainer —
  cross-check any coordinate you actually use against the DGCA rule text before
  relying on it.
- **What**: Downloaded and filtered to `iso_country == "IN"` — **651 India
  airports**, saved to `aerofleet_data/geospatial/in_airports_ourairports.csv`.
  Verified present: Pune International Airport (18.5821, 73.919701) and
  Chhatrapati Shivaji Maharaj International Airport, Mumbai (19.088699, 72.867897)
  — real coordinates to cross-check against whatever's currently hand-typed in
  `restricted_sites.py`. The 5 km/12 km radii stay exactly as DGCA's rule text
  specifies (the radii were never the imprecise part — the anchor points were).

---

## 1. Primary dataset — real, HFACS-labeled UAV incidents (get this first) ✅ downloaded

**Source**: [github.com/YukeyYan/UAV-Accident-Forensics-HFACS-LLM](https://github.com/YukeyYan/UAV-Accident-Forensics-HFACS-LLM)
→ cloned in full to `aerofleet_data/labeled_incidents/uav_hfacs_asrs_200/` (32 MB).

The dataset behind "UAV Accident Forensics via HFACS-LLM Reasoning" (*Drones*
9(10):704, 2025) — the same paper already cited in `docs/TESTING_STRATEGY.md` and
`aerofleet/agents/incident_taxonomy.py` as this project's methodological precedent.
This is the single best source available: it's the *actual* dataset the precedent
paper's own numbers came from.

- **What it contains**: 200 real UAV accident reports (sourced from NASA ASRS,
  2010–2025), 3,600 individually coded data points under the full HFACS 8.0
  taxonomy, expert-validated (inter-rater reliability κ = 0.823 — published, not
  self-reported). Verified: `data/ground_truth/dataset_info.json` confirms
  200 records, 62 columns, 18 HFACS categories, with an MD5 checksum.
- **⚠️ Use the right file**: the repo's own `DATASET_CORRECTION_NOTICE.md` states
  that earlier documentation incorrectly pointed at `data/ASRS_DBOnline_Report.csv`
  (also present, 193 rows) as the experimental dataset. **The actual one is
  `data/ground_truth/ground_truth_standard_coded.csv`** (200 rows) — use that file,
  not the raw ASRS export sitting next to it.
- **License**: CC BY 4.0 — free for academic and commercial use, attribution
  required. The repo's own `LICENSE` and `DATASET_README.md` came down with the
  clone, so the attribution trail is intact.
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

### 2a. NASA ASRS Database (the same source the paper drew from) ⛔ interactive only
- **Source**: [asrs.arc.nasa.gov](https://asrs.arc.nasa.gov/)
- **License**: Public domain (NASA-curated).
- **What**: Searchable database of real aviation safety narratives. **Attempted and
  confirmed not scriptable**: the ASRS Database Online (DBOL) requires building a
  report set through its interactive search form — no single bulk-download URL
  exists. Manual steps: open DBOL, search/filter for UAS-tagged reports, export the
  report set (PDF, 50 records per file) yourself, save into
  `aerofleet_data/raw_incident_sources/asrs_exports/`.

### 2b. NTSB CAROL (Case Analysis and Reporting Online) ⛔ could not locate a working bulk URL
- **Source**: [data.ntsb.gov/carol-main-public](https://data.ntsb.gov/carol-main-public/)
- **License**: Public (U.S. federal government data).
- **What**: Full aviation accident database, 1962–present. The site references
  bulk downloadable sets (`avall.zip`, `PRE1982.zip`), but **two guessed direct URLs
  both failed** (one 404, one returned an HTML page instead of a file) — the real
  download link isn't guessable and needs to be found by navigating the CAROL site
  itself. Manual steps: open the link above, use the Custom Search Builder to filter
  toward UAS-involved investigations (not drone-specific data — filtering matters),
  and use whatever bulk-export option the current UI offers. Save to
  `aerofleet_data/raw_incident_sources/ntsb_carol_exports/`.

### 2c. FAA UAS Data Delivery System (UDDS) ⛔ wrong dataset family — corrected
- **Source**: [udds-faa.opendata.arcgis.com](https://udds-faa.opendata.arcgis.com/)
- **License**: Public (U.S. federal government data).
- **Correction from the original version of this guide**: checked the portal's own
  data catalog directly (28 datasets total) — it does **not** contain a "UAS
  Sightings Report" narrative dataset. What it actually has is US airspace
  geospatial data: FAA UAS FacilityMap, National Security UAS Flight Restrictions,
  Active UAS NOTAMs, Recognized Identification Areas — real and programmatically
  queryable (ArcGIS REST API, CSV/GeoJSON/KML export per dataset), but US-specific
  regulatory geometry, not incident narratives, and not directly useful for
  AeroFleet's India/DGCA context.
- The actual **FAA UAS Sightings Report** (drone sighting narratives, the thing
  this section originally meant) is published separately as periodic file releases
  on [faa.gov/uas/resources/public_records/uas_sightings_report](https://www.faa.gov/uas/resources/public_records/uas_sightings_report)
  — not part of the ArcGIS catalog, no single bulk URL, download the periodic
  release files manually. Save to
  `aerofleet_data/raw_incident_sources/faa_uas_sightings/`.

### Checked and not usable right now
**DGCA India incident reports specifically** (as opposed to the regulatory documents
in §0a, which are real and downloadable) — no centralized public *incident* database
exists today. Worth re-checking periodically; not a source you can pull from as of
this writing.

---

## 3. Reference docs (for the manual HFACS-to-AeroFleet-taxonomy mapping) ⛔ both blocked

Both attempted directly and both refused automated access — real bot-detection
(Akamai/Edgesuite on the .mil sites, Cloudflare-style blocking on MDPI), not broken
links. Open these in an actual browser and save manually; a script can't get past
this kind of protection, and shouldn't try to spoof its way past it either.

- **DAF HFACS 8.0 Guide** (official Air Force Safety Center document, the current
  DoD-endorsed taxonomy version the labeled dataset in §1 uses):
  [safety.af.mil — DAF HFACS 8 Guide, 1 April 2023 (PDF)](https://www.safety.af.mil/Portals/71/documents/Human%20Factors/DAF%20HFACS%208%20Guide%201%20April%202023.pdf)
  — `.mil` returned HTTP 403 (Akamai Edgesuite bot block) on every attempt,
  including a mirror at `navalsafetycommand.navy.mil`. → save as
  `aerofleet_data/reference_docs/hfacs_8_0_guide.pdf`
- **The precedent paper itself** (methodology, category definitions, scoring
  approach): [doi.org/10.3390/drones9100704](https://doi.org/10.3390/drones9100704)
  — MDPI returned HTTP 403 on the article page and the direct PDF link alike. Note:
  the cloned dataset repo (§1) already includes the paper's *appendix* materials
  under `05_Paper/Appendix/`, just not the full paper PDF itself. → save as
  `aerofleet_data/reference_docs/uav_hfacs_llm_paper.pdf`

---

## 4. Base model weights — only the ones actually fine-tunable on a single RTX 5090 ⛔ not attempted, on purpose

**Deliberately not downloaded here.** Two separate reasons, not just "it's big":
1. **Size**: 24B + 14B + 12B dense models at full precision is realistically
   80–150GB combined depending on format — a real, meaningful chunk of disk on
   whatever machine this lands on, not something to pull down silently.
2. **Access**: Gemma's repo is gated on Hugging Face — it requires a logged-in HF
   account clicking through Google's license acceptance on the model page first;
   there's no way to do that from a script without a personal HF token, which isn't
   something to embed here anyway.

Run these yourself, from whichever machine will actually train (the college PC with
the 5090, not this one) — commands and full sourcing detail unchanged from below:

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

## Not downloaded — do these manually

Everything below was actually attempted (not skipped) and confirmed to need a real
browser session or a machine other than this one. Nothing here is a guess at what
might work — each was tried and the specific failure is noted.

| # | What | Why it couldn't be automated | Manual URL |
|---|---|---|---|
| §2a | NASA ASRS raw exports | Interactive search form only, no bulk URL | [asrs.arc.nasa.gov](https://asrs.arc.nasa.gov/) |
| §2b | NTSB CAROL bulk accident data | Two guessed direct URLs both failed (404 / wrong content); real link needs the site's own UI | [data.ntsb.gov/carol-main-public](https://data.ntsb.gov/carol-main-public/) |
| §2c | FAA UAS Sightings Report | Not in the ArcGIS UDDS catalog at all (confirmed by reading the catalog directly); lives as periodic file releases on a separate FAA page | [faa.gov/uas/resources/public_records/uas_sightings_report](https://www.faa.gov/uas/resources/public_records/uas_sightings_report) |
| §3 | DAF HFACS 8.0 Guide (PDF) | `.mil` sites returned HTTP 403 — Akamai/Edgesuite bot protection, on two different `.mil` mirrors | [safety.af.mil PDF](https://www.safety.af.mil/Portals/71/documents/Human%20Factors/DAF%20HFACS%208%20Guide%201%20April%202023.pdf) |
| §3 | The precedent paper PDF | MDPI returned HTTP 403 on both the article page and the direct PDF link | [doi.org/10.3390/drones9100704](https://doi.org/10.3390/drones9100704) |
| §4 | Mistral Small 3.2, Phi-4-reasoning-plus, Gemma 4 12B weights | Not attempted deliberately — 80-150GB combined, and Gemma requires a personal HF account clicking through a license first | commands given in §4 |
| §4 | Llama 4 Scout weights | Not attempted deliberately — excluded from fine-tuning entirely (needs ~71GB VRAM, exceeds the target 5090) | not recommended to download at all |

## Summary checklist

- [x] ~~Save the DGCA Drone Rules 2021 + CAR S3-X-Part1 PDFs (§0a)~~ — done
- [x] ~~Pull the OurAirports India CSV (§0b)~~ — done, 651 India airports
- [x] ~~Clone the labeled HFACS-UAV dataset (§1)~~ — done, 200 verified records
- [ ] NASA ASRS / NTSB CAROL / FAA sightings (§2) — optional, manual only if 200
      cases proves too small (see table above)
- [ ] HFACS 8.0 guide + precedent paper PDF (§3) — manual, both bot-blocked (see
      table above)
- [ ] Download weights for Mistral Small 3.2, Phi-4-reasoning-plus, and Gemma 4
      12B only (§4) — skip Llama 4 Scout, deliberately not done here
- [ ] Install the fine-tuning stack + llama.cpp (§5)
- [ ] Split the labeled dataset into train/held-out **before** writing any
      fine-tuning code
