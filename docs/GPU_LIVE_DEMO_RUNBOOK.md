# Running a Real, Live Council Debate — GPU Machine Runbook

**Why this document exists:** every verification of this project so far — every phase, every
test, every "live" check — has run with `USE_MOCK_AGENTS=true`, a hand-written deterministic
stand-in for the LLMs. The multi-agent council has never once talked to a real model in this
project's history. This is the first time that changes. Treat this as the highest-priority
thing to get right before showing anyone this project live.

Do this **the moment you have access to the machine**, not right before you need to demo —
model downloads alone can take 20-60+ minutes depending on connection speed and disk.

---

## 1. Install Ollama and confirm it's running

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows: download the installer from https://ollama.com/download
```

```bash
ollama serve   # if it isn't already running as a service
# in another terminal:
ollama list    # should return (possibly empty) without erroring
```

## 2. Check available VRAM before pulling anything

```bash
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
```

This project's default model roster (`aerofleet/agents/factory.py`'s `DEFAULT_MODEL_MAP`) needs
these four distinct models (11 agents share them — Ollama only needs one loaded at a time per
call, not the sum, but each one still needs to *fit individually*):

| Model | Used by | Approx. size |
|---|---|---|
| `llama4:scout` | Dispatcher, Airspace Safety, Autonomy Validator, Contingency | **~55 GB at Q4** — needs a genuinely large GPU (40GB+ card, or a smaller quant — see below) |
| `mistral-small3.2` | Route Planner, Comms, DGCA Compliance | ~15 GB (24b variant) |
| `phi4-reasoning:plus` | Battery, Cost, Payload | ~9-11 GB |
| `gemma4:12b` | Weather, Ops Scheduler | ~8-9 GB |

**If your card has less than ~55GB free**, `llama4:scout` will fail to load. Don't discover this
mid-demo — check now, and if it doesn't fit, override it before you need it (Section 4).

## 3. Run the pre-flight check — do this first, always

```bash
cd "SpaceMissionArchitect"
python tools/preflight_llm_check.py --host http://localhost:11434
```

This connects to your real Ollama instance, tells you exactly which of the 4 required models are
missing (with the exact `ollama pull` command for each), and — for whichever ones are already
present — sends one real, tiny inference call to each and times it. Read its output literally;
it's designed to be handed to someone else to run and understand without you in the room.

Pull whatever it reports missing:

```bash
ollama pull llama4:scout
ollama pull mistral-small3.2
ollama pull phi4-reasoning:plus
ollama pull gemma4:12b
```

Re-run the pre-flight script until it reports `Ready for a live demo.` **Do not proceed to the
actual demo until it says that.**

## 4. If `llama4:scout` doesn't fit (likely, unless the card is 40GB+)

Override just that model via the same `AGENT_MODEL_<ID>` env vars the app already supports —
no code changes needed. Two options, in order of preference:

**Option A — smaller quantization of the same model** (check the exact current tag on
`ollama.com/library/llama4-scout` first — tag naming on Ollama's registry changes; a Q4_K_M
build was reported to fit in ~16GB as of this writing, but confirm before relying on it):

```bash
export AGENT_MODEL_DISPATCHER="llama4-scout:q4_K_M"
export AGENT_MODEL_AIRSPACE_SAFETY="llama4-scout:q4_K_M"
export AGENT_MODEL_AI_VALIDATOR="llama4-scout:q4_K_M"
export AGENT_MODEL_CONTINGENCY="llama4-scout:q4_K_M"
```

**Option B — swap to a model you've already confirmed fits** (e.g. reuse `mistral-small3.2`,
already verified working from Section 3):

```bash
export AGENT_MODEL_DISPATCHER="mistral-small3.2"
export AGENT_MODEL_AIRSPACE_SAFETY="mistral-small3.2"
export AGENT_MODEL_AI_VALIDATOR="mistral-small3.2"
export AGENT_MODEL_CONTINGENCY="mistral-small3.2"
```

Either way, re-run `tools/preflight_llm_check.py` after setting overrides — it respects
`AGENT_MODEL_<ID>` the same way the real app does, so it will check exactly what you're about to
actually run, not the aspirational defaults.

## 5. Start the real API — the only two env vars that matter

```bash
export OLLAMA_HOST="http://localhost:11434"   # or your Tailscale/remote host if not local
# do NOT set USE_MOCK_AGENTS at all — its default is already "false"

cd "SpaceMissionArchitect"
.venv/bin/python -m uvicorn aerofleet.api.app:app --host 0.0.0.0 --port 8000
```

Watch the startup log for `Council initialized with 11 core + 5 specialist agents` — if
`MockLLMBackend active` appears anywhere in the logs instead, `USE_MOCK_AGENTS` is still set
somewhere (check your shell environment and `.env` file — `aerofleet/agents/runtime_settings.py`
reads it via `os.environ.get("USE_MOCK_AGENTS", "false")`).

## 6. Prove it live, in order

1. Dispatch a normal order (`POST /orders/` then `POST /orders/{id}/dispatch`) — confirm it's
   still instant (this path never touches the LLM — that's the whole point of Phase AB; a real
   model being loaded should have zero effect on dispatch latency, and demonstrating *that* is
   itself worth showing).
2. Call `POST /orders/{id}/request-explanation` — this is the actual first-ever real council
   debate in this project's history. Expect it to take real time now (tens of seconds to
   minutes, not the mock's instant response) — that's expected and is itself evidence it's real.
3. Poll `GET /orders/{id}` until `council_explanation_status` is `READY`, and read the
   `council_transcript` — confirm the `model=` field in each agent's reasoning names a real model
   (`llama4:scout`, not `mock-deterministic`), and that the reasoning is genuinely novel text, not
   a fixed template.
4. Check server logs during step 2 for the actual Ollama request/response timing — this is your
   evidence for "yes, this is really calling the model," not just a claim.

## Troubleshooting

- **Connection refused**: `ollama serve` isn't running, or you're pointing at the wrong host/port.
- **Model not found**: `ollama list` to confirm the exact installed tag matches
  `aerofleet/agents/factory.py`'s `DEFAULT_MODEL_MAP` (or your override) exactly — Ollama tags are
  exact-string matches.
- **Timeout / hang**: `config.llm.ollama_timeout` defaults to 300s per call — an 11-agent, up to
  5-round debate can legitimately take minutes total. Don't mistake "slow" for "broken" on a first
  real run; but if a single agent hangs past 300s, that's the real timeout firing, worth noting.
- **Out of memory**: the model didn't fit — go back to Section 4.
