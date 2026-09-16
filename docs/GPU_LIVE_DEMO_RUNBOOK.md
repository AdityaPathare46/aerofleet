# Running a Real, Live Council Debate — GPU Machine Runbook

**Why this document exists:** every verification of this project so far — every phase, every
test, every "live" check — has run with `USE_MOCK_AGENTS=true`, a hand-written deterministic
stand-in for the LLMs. The multi-agent council has never once talked to a real model in this
project's history. This is the first time that changes. Treat this as the highest-priority
thing to get right before showing anyone this project live.

Do this **before you need to demo**, though it's now quick — the model is ~3.2GB, a few minutes
on any reasonable connection.

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

## 2. Pull the model and run the pre-flight check

The default roster (`aerofleet/agents/factory.py`'s `DEFAULT_MODEL_MAP`) is now a single shared
model, `phi4-mini-reasoning` (Microsoft, 3.8B, ~3.2GB) — every one of the 11 core agents plus
the specialist agents use it. No VRAM check needed first: it comfortably fits on CPU alone on
any 8GB+ RAM machine, let alone a GPU box. (A prior version of this roster split 4 differently-
sized models across agents, needing up to ~55GB VRAM for the largest — that requirement no
longer applies.)

```bash
ollama pull phi4-mini-reasoning
```

```bash
cd "SpaceMissionArchitect"
python tools/preflight_llm_check.py --host http://localhost:11434
```

This connects to your real Ollama instance, confirms the model is present (with the exact
`ollama pull` command if it's missing), and sends one real, tiny inference call to time it. Read
its output literally; it's designed to be handed to someone else to run and understand without
you in the room. Re-run it until it reports `Ready for a live demo.` **Do not proceed to the
actual demo until it says that.**

## 3. Start the real API — the only two env vars that matter

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

## 4. Prove it live, in order

1. Dispatch a normal order (`POST /orders/` then `POST /orders/{id}/dispatch`) — confirm it's
   still instant (this path never touches the LLM — that's the whole point of Phase AB; a real
   model being loaded should have zero effect on dispatch latency, and demonstrating *that* is
   itself worth showing).
2. Call `POST /orders/{id}/request-explanation` — this is the actual first-ever real council
   debate in this project's history. Expect it to take real time now (tens of seconds to
   minutes, not the mock's instant response) — that's expected and is itself evidence it's real.
3. Poll `GET /orders/{id}` until `council_explanation_status` is `READY`, and read the
   `council_transcript` — confirm the `model=` field in each agent's reasoning names a real model
   (`phi4-mini-reasoning`, not `mock-deterministic`), and that the reasoning is genuinely novel
   text, not a fixed template.
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
- **Out of memory**: shouldn't happen at ~3.2GB on any 8GB+ RAM machine — check nothing else is
  consuming unusual memory, then `ollama stop` and `ollama serve` again.
