# 🚀 AeroFleet — AI Model Setup Guide

> **What changed**: AeroFleet's LLM roster used to be 4 different models (~80GB combined,
> requiring a dedicated GPU server). It's now **one lightweight model** — the same reasoning
> quality per parameter, chosen specifically to run on ordinary hardware: any laptop with 8GB+
> RAM, Windows or macOS, no discrete GPU required. Setup is now minutes, not hours, and doesn't
> need a dedicated machine at all.
>
> **Last Updated**: September 2026

---

## 🏗️ How This Works Now

```
  YOUR OWN LAPTOP
┌────────────────────────────────┐
│  All project code               │
│  Ollama Server                  │
│  phi4-mini-reasoning (3.2 GB)   │
│  Runs on CPU — no GPU required  │
└────────────────────────────────┘
```

**You don't need a separate GPU server anymore.** Install Ollama, pull one small model, and
everything — code and AI inference — runs on the same machine you're already developing on.

> If you *do* want to contribute spare compute from another machine (e.g. splitting a large
> batch evaluation across several machines in parallel), the same Tailscale networking steps at
> the bottom of this guide still work — that's now optional, not required.

---

## 📋 What You Need To Do (2 Steps)

| Step | What | Time |
|------|------|------|
| 1 | Install Ollama | 5 min |
| 2 | Download the model (3.2 GB) | 2-5 min |

That's it.

---

## 🖥️ Hardware Requirements

| Component | Requirement |
|-----------|-------------|
| **RAM** | 8 GB or more |
| **GPU** | None required — runs fine on CPU. A discrete GPU (even a modest one) speeds it up but isn't needed. |
| **Free Disk** | ~4 GB |
| **OS** | Windows, macOS, or Linux |

This is intentionally a low bar — the model was chosen specifically so it runs on an ordinary
laptop, not just a workstation.

---

## Step 1 — Install Ollama

### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
Download from **https://ollama.com/download/windows** and run the installer.

### macOS
```bash
brew install ollama
# Or download from https://ollama.com/download/mac
```

### Verify it installed:
```bash
ollama --version
```

---

## Step 2 — Download the Model

```bash
ollama pull phi4-mini-reasoning
```

Microsoft's Phi-4 line, reasoning-tuned, 3.8B parameters, ~3.2GB at default quantization
(verified real and pullable against Ollama's own library — not assumed). This single model now
powers every one of AeroFleet's agents (see `aerofleet/agents/factory.py`'s `DEFAULT_MODEL_MAP`).

### Verify it installed:
```bash
ollama list
```
You should see:
```
NAME                       SIZE
phi4-mini-reasoning:latest 3.2 GB
```

### Quick test:
```bash
ollama run phi4-mini-reasoning "Estimate the energy in Wh to fly a 5kg-payload drone 4km at 3.5 Wh/km base rate."
```
Should respond within a few seconds on CPU alone.

> 💡 No time to install Ollama at all? Set `USE_MOCK_AGENTS=true` in `.env` to run the whole
> pipeline against a deterministic offline backend — no Ollama required, for a quick pipeline
> sanity check.

---

## 🗺️ Which Agent Uses Which Model

Every agent — the 11-agent Fleet Dispatch Council, plus the specialist agents (conflict
avoidance, battery-swap planning, governance/legal, cybersecurity, edge-compute feasibility) —
now shares the same `phi4-mini-reasoning` model. They keep distinct roles and system prompts
(that's what makes it a multi-agent architecture); they no longer each pin a different set of
weights.

**Why one shared model, not a mixture of differently-sized ones:** the previous per-role mixture
(4 models, up to 80GB combined) needed more VRAM than most machines have, and on constrained
hardware caused real thrashing — a model getting evicted and reloaded between almost every agent
call, which dominated latency far more than raw compute did. One small model everywhere removes
that failure mode entirely, and means every machine (your laptop, a teammate's, a cloud
notebook) runs the identical real roster — no "smaller substitute used here" methodology caveat
needed anywhere.

---

## 🌐 Optional: Sharing Compute Across Machines (Tailscale)

Only needed if you want to split a large batch run (e.g. the 1,000-case mass forensics study)
across multiple machines in parallel — see `research/merge_batched_results.py` and the
`--only-batches` flag on `scenario_engine/mass_forensics_evaluation.py` for the actual
batch-splitting mechanism. Networking a second machine in:

### Install Tailscale
- **Linux**: `curl -fsSL https://tailscale.com/install.sh | sh`
- **Windows**: **https://tailscale.com/download/windows**
- **macOS**: **https://tailscale.com/download/mac**

### Set it up
```bash
sudo tailscale up          # opens a browser to sign in
tailscale ip -4            # your Tailscale IP, looks like 100.x.x.x
```

### Make Ollama listen on the network, not just localhost

**Linux**: `OLLAMA_HOST=0.0.0.0 ollama serve` (or set `Environment="OLLAMA_HOST=0.0.0.0"` via
`sudo systemctl edit ollama.service` for a permanent setting).

**Windows**: System Environment Variables → New → `OLLAMA_HOST` = `0.0.0.0` → restart Ollama.

**macOS**: `launchctl setenv OLLAMA_HOST "0.0.0.0"` → restart the Ollama app.

Open port **11434** in the firewall (`sudo ufw allow 11434/tcp` on Linux; allow `ollama.exe`
through Windows Firewall for Private networks).

### Verify it's reachable
```bash
curl http://<TAILSCALE_IP>:11434/api/tags
```
A JSON response listing `phi4-mini-reasoning` means it's connected — point `OLLAMA_HOST` in the
main app's Settings panel (or the `OLLAMA_HOST` env var for a batch script) at that IP.

---

## 🔧 Troubleshooting

### "Connection refused"
- Confirm `ollama serve` is actually running: `curl http://localhost:11434/api/tags`
- If connecting across machines: confirm `OLLAMA_HOST=0.0.0.0` is set and Tailscale is connected
  on both ends

### Slow responses
- CPU-only inference is normal and expected to take a few seconds per call, not the tens of
  minutes the old 4-model roster could hit under VRAM pressure
- A discrete GPU (even 4-6GB) will noticeably speed this up if available, but isn't required

### "Out of memory"
- Shouldn't happen at 3.2GB on any 8GB+ RAM machine. If it does: `ollama stop` then
  `ollama serve` again, and close other memory-heavy applications.

### Check disk space
```bash
du -sh ~/.ollama/models/   # Linux/macOS
# Windows: check %USERPROFILE%\.ollama\models\
ollama rm <model-name>     # remove a model if needed
```

---

## ✅ Checklist

- [ ] Ollama installed (`ollama --version` works)
- [ ] Model downloaded (`ollama list` shows `phi4-mini-reasoning`)
- [ ] Quick test responded (`ollama run phi4-mini-reasoning "..."`)
- [ ] (Optional, only for multi-machine batch runs) Tailscale connected and `OLLAMA_HOST=0.0.0.0`
      set

**Once the first three are checked, AeroFleet's full pipeline runs end-to-end on your own
machine — no separate GPU server needed.**
