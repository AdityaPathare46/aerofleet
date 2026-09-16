# AeroFleet — Live-LLM Testing Guide (College GPU PC)

**What this file is for:** every subsystem in this project that touches an LLM, tested against a
real Ollama server, with copy-pasteable commands and a clear pass/fail signal for each step. This
supersedes `docs/GPU_LIVE_DEMO_RUNBOOK.md` (kept for its VRAM-sizing notes, referenced below) —
that file only covered the explanation path; this one covers all three legitimate LLM use cases
(explanation, policy tuning, incident forensics) plus the evaluation harnesses that put a number on
LLM output quality.

Do Part 1 (install + preflight) **the moment you have the machine**, not right before you need to
show anyone anything — model pulls alone can take 20–60+ minutes.

Work through the checkboxes top to bottom. Every step says exactly what "it worked" looks like.

---

## Part 1 — Install & Preflight (do this first, always)

- [ ] **Install Ollama**
  ```bash
  # Linux
  curl -fsSL https://ollama.com/install.sh | sh
  # Windows: installer from https://ollama.com/download
  ```
- [ ] **Start it and confirm it responds**
  ```bash
  ollama serve   # if not already running as a service
  ollama list    # should return without erroring (possibly empty list)
  ```
- [ ] **Clone/copy the project onto the machine, then set up the environment**
  ```bash
  cd AeroFleet   # or wherever you placed it
  python3.10 -m venv .venv
  source .venv/bin/activate        # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  ```

- [ ] **Run the pre-flight check**
  ```bash
  python tools/preflight_llm_check.py --host http://localhost:11434
  ```
  Pull whatever it reports missing (now just one model, no VRAM check needed — it's ~3.2GB and
  runs fine on CPU alone):
  ```bash
  ollama pull phi4-mini-reasoning
  ```
  **Pass signal:** the script prints `Ready for a live demo.` Re-run until it does — don't proceed
  before this.

---

## Part 2 — Start the Real Stack

- [ ] **Start the API in live mode** — the only two things that matter are that `OLLAMA_HOST`
  points at your real server and `USE_MOCK_AGENTS` is *not* set to true:
  ```bash
  export OLLAMA_HOST="http://localhost:11434"
  unset USE_MOCK_AGENTS      # or explicitly: export USE_MOCK_AGENTS=false

  # optional but recommended for this test session — mint yourself an admin
  # account once you've registered a user (Part 3, step 1) instead of raw SQL:
  export AEROFLEET_BOOTSTRAP_ADMIN_USERNAME=<the username you'll register>

  .venv/bin/python -m uvicorn aerofleet.api.app:app --host 0.0.0.0 --port 8000
  ```
  **Pass signal:** startup log shows `Council initialized with 11 core + 5 specialist agents`.
  If `MockLLMBackend active` appears anywhere, `USE_MOCK_AGENTS` is still set somewhere — check
  your shell env and any `.env` file.

- [ ] **Start the desktop/dev frontend** (separate terminal)
  ```bash
  cd tauri-app && npm install && npm run dev
  # open http://localhost:1420 in a browser, or `npm run tauri dev` for the native window
  ```

- [ ] **Register a user and log in** (via the UI, or curl):
  ```bash
  curl -s -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" \
    -d '{"username":"<you>","email":"<you>@example.com","password":"TestPass123!"}'
  ```
  If you set `AEROFLEET_BOOTSTRAP_ADMIN_USERNAME` above, **restart the API once** now that the
  user exists (bootstrap runs once at startup) to grant yourself admin — check the log line
  `Bootstrap admin granted to '<you>'`. Then in the app's Settings → Admin tab, grant yourself
  Operator too (needed for the manual policy-trigger step in Part 5).

---

## Part 3 — Test 1: Post-Hoc Explanation (the council's core use case)

- [ ] **Dispatch a normal order** and confirm it's still instant — this path never touches the LLM:
  ```bash
  TOKEN=<paste your access_token from /auth/login>
  curl -s -X POST http://localhost:8000/api/v1/orders/ -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" -d '{
      "city": "pune", "origin_depot_id": "DEPOT-1",
      "destination_lat": 18.55, "destination_lon": 73.87,
      "payload_kg": 1.0, "priority": "STANDARD", "deadline_minutes": 30
    }'
  # note the returned order_id, then:
  curl -s -X POST http://localhost:8000/api/v1/orders/<order_id>/dispatch -H "Authorization: Bearer $TOKEN"
  ```
  **Pass signal:** response returns in well under a second, with a `verdict` field — no LLM
  involved yet, on purpose.

- [ ] **Request the explanation** — this is the actual first real council debate:
  ```bash
  curl -s -X POST http://localhost:8000/api/v1/orders/<order_id>/request-explanation \
    -H "Authorization: Bearer $TOKEN"
  ```
  **Pass signal:** this call returns *immediately* (it just enqueues a job) — if it hangs, the
  worker isn't running.

- [ ] **Poll until ready and inspect the transcript:**
  ```bash
  watch -n 3 "curl -s http://localhost:8000/api/v1/orders/<order_id> -H 'Authorization: Bearer $TOKEN' | python3 -m json.tool | grep -A2 council_explanation_status"
  ```
  **Pass signal, in order:**
  1. `council_explanation_status` moves `PENDING` → `READY` — expect **tens of seconds to a few
     minutes**, not instant. Slow here is expected and is itself evidence it's real.
  2. Each transcript entry's `model` field names the real tag (`phi4-mini-reasoning`) — never
     `mock-deterministic`.
  3. The reasoning text is genuinely different each time you try this (re-dispatch a new order
     and request again) — a fixed template would read identically every time.
  4. Check the API server's own logs during this step for real outbound HTTP calls to
     `OLLAMA_HOST` — this is your hard evidence, not just the claim.
  5. In the desktop app, open **Council Room**, find this order, confirm the same transcript
     renders there.

---

## Part 4 — Test 2: Auto-Triggered Incident Forensics (no request needed)

This is the most interesting live-LLM path to demo — nobody asks for it, it fires itself.

- [ ] **Dispatch to a real DGCA Red Zone** so the CBF gate actually rejects it. Pune Airport
  (Lohegaon) is a real, named restricted site already in `city/restricted_sites.py`:
  ```bash
  curl -s -X POST http://localhost:8000/api/v1/orders/ -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" -d '{
      "city": "pune", "origin_depot_id": "DEPOT-1",
      "destination_lat": 18.5822, "destination_lon": 73.9197,
      "payload_kg": 1.0, "priority": "STANDARD", "deadline_minutes": 30
    }'
  curl -s -X POST http://localhost:8000/api/v1/orders/<order_id>/dispatch -H "Authorization: Bearer $TOKEN"
  ```
  **Pass signal:** the dispatch response itself is `409` / a rejection verdict — this part is
  still instant and deterministic, exactly like Part 3's pass case.

- [ ] **Check the Incident Forensics list within a few seconds — do not request anything:**
  ```bash
  curl -s http://localhost:8000/api/v1/incidents/ -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
  ```
  **Pass signal:** a new `IncidentReport` already exists with `status` moving
  `PENDING` → `INVESTIGATING` → `READY` on its own — you never called an incident-forensics
  endpoint to start it.

- [ ] **Read the finished report** (via the same endpoint, or the desktop app's **Incident
  Forensics** page):
  **Pass signal:** `contributing_factors` shows `airspace_conflict: CONTRIBUTED` (matching the
  real geofence rejection), `root_cause_summary` is coherent prose citing the real numbers, and
  `investigation_transcript` shows 8 entries (7 domain agents + 1 regulatory agent), each with a
  real model name.

- [ ] **(Optional) Promote the finding to a policy proposal** — requires Operator role:
  ```bash
  curl -s -X POST http://localhost:8000/api/v1/incidents/<incident_id>/promote-to-policy-proposal \
    -H "Authorization: Bearer $TOKEN"
  ```
  **Pass signal:** `GET /api/v1/policy/proposals?city=pune` now lists it, `status: PENDING_REVIEW`.

---

## Part 5 — Test 3: Fleet-Level Policy Review (slow-cadence, manually fired for testing)

The real cadence is every 6 hours — for a demo, fire it manually (requires Operator role):

- [ ] ```bash
  curl -s -X POST "http://localhost:8000/api/v1/policy/trigger-review?city=pune" \
    -H "Authorization: Bearer $TOKEN"
  ```
  **Pass signal:** response includes `proposals_created` (0 or more — 0 is a legitimate outcome
  if the council found nothing worth changing, not a failure). If ≥1, `GET
  /api/v1/policy/proposals?city=pune` shows a new proposal with a written rationale citing real
  fleet statistics.

---

## Part 6 — Evaluation Harnesses (put a number on LLM output quality)

- [ ] **Incident Forensics accuracy** — runs the labeled synthetic-incident set through the real
  pipeline against your live models and reports per-category precision/recall/F1:
  ```bash
  python -m scenario_engine.incident_forensics_evaluation
  ```
  **Pass signal:** a report prints to stdout and writes to `scenario_reports/`; compare the
  macro-F1 to the mock-agent baseline already recorded in `PROJECT_SUMMARY.md` — a live-model run
  legitimately scoring lower than the mock baseline is a real, reportable finding, not something
  to hide.

- [ ] **D2D degradation study** (deterministic — no LLM, but worth re-running on real hardware for
  a clean, freshly-timestamped report to cite):
  ```bash
  python -m scenario_engine.d2d_degradation_study --trials 5000 --seed 42 --stress-fraction 0.5
  ```

- [ ] **Full automated test suite** (confirms nothing about the environment itself is broken):
  ```bash
  pytest tests/ -q
  ```
  **Pass signal:** same result as documented in `PROJECT_SUMMARY.md` — all passing except the one
  pre-existing, unrelated `test_config.py` failure, 2 hardware-marked tests deselected. This suite
  runs against `USE_MOCK_AGENTS` regardless of your shell's live setting (tests set it themselves),
  so it isn't itself a live-LLM test — it's your baseline confirmation that Parts 3–5 above failing
  would mean an *environment* problem, not a pre-existing code problem.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` | `ollama serve` not running, or wrong host/port | check `OLLAMA_HOST`, run `ollama serve` |
| Preflight reports a model missing after you pulled it | tag mismatch | `ollama list` — Ollama tags are exact-string matches against `DEFAULT_MODEL_MAP` |
| Explanation/incident status stuck on `PENDING` forever | worker didn't start, or `USE_MOCK_AGENTS` leaking from a stale shell/`.env` | check startup log for `Council initialized`; `env \| grep -i mock` |
| A single agent call hangs past ~5 min | real 300s-per-call timeout (`config.llm.ollama_timeout`) firing repeatedly across retries | check that specific model actually loads standalone: `ollama run <model> "hello"` |
| Out of memory | shouldn't happen at ~3.2GB on any 8GB+ RAM machine | `ollama stop` then `ollama serve` again; check nothing else is consuming unusual memory |
| Dispatch to Pune Airport coords doesn't reject | wrong city selected, or airport coords typo | re-check `18.5822, 73.9197` exactly; confirm `"city": "pune"` in the order body |
| Incident never appears after a rejection | `incident_forensics_worker` didn't start | check startup log for `Incident forensics worker started`; confirm you're hitting the same API process that logged it |

---

## What "done" looks like

By the end of this file you will have, for the first time against real models rather than the
mock backend: a real council explanation, a real auto-triggered incident investigation, a real
manually-fired policy proposal, and a real accuracy number for incident-forensics output quality —
plus the exact server logs and transcripts to show as evidence for each, not just a claim that it
works.
