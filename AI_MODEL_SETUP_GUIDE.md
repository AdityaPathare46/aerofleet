# 🚀 AeroFleet — AI GPU Server Setup Guide

> **What this is**: Your PC will act as a **remote AI GPU server**. You only need to install Ollama and download the AI models. Aditya handles all the code, datasets, and development on his laptop — your PC just runs the AI brains.
>
> **Last Updated**: March 2026

---

## 🏗️ How This Setup Works

```
  ADITYA'S LAPTOP                         YOUR PC (GPU Server)
┌───────────────────────┐                ┌───────────────────────┐
│                       │    "Hey AI,    │                       │
│  All project code     │    analyze     │  Ollama Server        │
│  Datasets & PDFs      │ ──this mission──►  4 AI Models (~80GB) │
│  Dashboard UI         │                │  Running on your GPU  │
│  Physics engine       │ ◄──response────│                       │
│  Reports              │    text        │  That's ALL you need! │
│                       │                │                       │
└───────────────────────┘                └───────────────────────┘
         Connected via Tailscale / Local Network
```

**Your PC is just a GPU server** — like a remote brain. You don't need the project code, Python, datasets, or anything else. Just Ollama + models + network.

> Once this is set up, connecting to it from the AeroFleet app doesn't require editing any config
> files anymore — the desktop app's **Settings** panel has a "Tailscale" tab where the Tailscale
> IP just gets typed in and tested directly, saved without a restart.

---

## 📋 What You Need To Do (4 Steps)

| Step | What | Time |
|------|------|------|
| 1 | Install Ollama | 5 min |
| 2 | Download 4 AI models | 1-2 hours (~80 GB) |
| 3 | Install Tailscale (for remote access) | 5 min |
| 4 | Start Ollama on network mode | 1 min |

That's it. No Python, no code, no project files.

---

## 🖥️ Hardware Requirements

| Component | **Minimum** | **Recommended** |
|-----------|-------------|-----------------|
| **GPU** | RTX 4070 Ti (16 GB VRAM) | RTX 4090 (24 GB) or 2× RTX 3090 |
| **RAM** | 64 GB DDR5 | 128 GB DDR5 |
| **Free Disk** | 100 GB SSD | 150 GB NVMe SSD |
| **CPU** | Ryzen 7 7700X / i7-13700K | Ryzen 9 7950X / i9-14900K |
| **Internet** | Stable connection | Wired ethernet preferred |

> **Note**: With 24 GB VRAM, the smaller models (14B) run at 30-50 tokens/sec on GPU. The larger models (70B) use CPU offloading and run at 2-5 tokens/sec — slower but totally functional.

---

## Step 1 — Install Ollama

Ollama is the AI model server. It's a single-app install.

### Linux (Recommended for best GPU performance)
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
# Should print something like: ollama version 0.x.x
```

---

## Step 2 — Download All 5 AI Models

Open a terminal and run these commands **one by one**. Each model downloads and stays on your disk permanently.

All five are open-weight and non-Chinese-origin (Meta / Mistral AI / Google / Microsoft).

### Small/Medium Models (Download First — Fastest)

```bash
# Model 1: Phi-4-reasoning-plus (14B, Microsoft) — Powers the BATTERY, COST, PAYLOAD agents
ollama pull phi4-reasoning:plus

# Model 2: Mistral-Small 3.2 (24B, Mistral AI) — Powers the ROUTE, COMMS agents
ollama pull mistral-small3.2

# Model 3: Gemma 4 (12B, Google) — Powers the WEATHER, OPS agents
ollama pull gemma4:12b
```

### Large Models (Longest Download — Be Patient!)

```bash
# Model 4: Mistral Large 3 (Mistral AI) — Powers the COMPLIANCE agent (regulatory citation accuracy)
ollama pull mistral-large-3

# Model 5: Llama 4 Scout (109B total / 17B active, MoE, Meta) — Powers the DISPATCHER,
# AIRSPACE_SAFETY, AI_VALIDATOR agents
# ~67 GB download — will take 30-90 minutes
ollama pull llama4:scout
```

> ⚠️ **Do NOT close the terminal or interrupt these downloads.** If a download fails, just run the same command again — it resumes where it left off.

### Verify All Models Installed

```bash
ollama list
```

You should see **all 5 models** listed:

```
NAME                     SIZE
phi4-reasoning:plus      11 GB
mistral-small3.2         15 GB
gemma4:12b               7.6 GB
mistral-large-3          (varies)
llama4:scout             67 GB
```

### Quick Test (Optional but Recommended)

Test that a model actually runs on your GPU:

```bash
ollama run phi4-reasoning:plus "Estimate the energy in Wh to fly a 5kg-payload drone 4km at 3.5 Wh/km base rate."
```

You should get a response within 15-30 seconds. Press `Ctrl+C` to stop.

> 💡 No GPU server available yet, or just want to try the demo? Set `USE_MOCK_AGENTS=true` in
> `.env` to run the whole pipeline against a deterministic offline backend — no Ollama required.

---

## Step 3 — Install Tailscale (Remote Network Access)

Tailscale creates a secure private network between your PC and Aditya's laptop, even if you're in different locations. It's free.

### Install Tailscale

- **Linux**: `curl -fsSL https://tailscale.com/install.sh | sh`
- **Windows**: Download from **https://tailscale.com/download/windows**
- **macOS**: Download from **https://tailscale.com/download/mac**

### Set It Up

```bash
# 1. Start Tailscale and log in
sudo tailscale up

# 2. It will open a browser — sign in with Google/GitHub/Microsoft

# 3. Get your Tailscale IP (looks like 100.x.x.x)
tailscale ip -4
```

**Send this IP address to Aditya** — he will use it to connect to your Ollama server.

> 💡 **Alternative (Same Room / Same WiFi)**: If you're both on the same WiFi network, you can skip Tailscale. Just find your local IP:
> - **Linux/macOS**: `hostname -I` or `ifconfig`  
> - **Windows**: `ipconfig` → look for IPv4 Address (e.g., `192.168.1.105`)

---

## Step 4 — Start Ollama in Network Mode

By default, Ollama only accepts connections from `localhost`. You need to make it listen on all network interfaces so Aditya's laptop can reach it.

### Linux

```bash
# Option A: One-time start
OLLAMA_HOST=0.0.0.0 ollama serve

# Option B: Set permanently (recommended)
# Edit the systemd service:
sudo systemctl edit ollama.service

# Add these lines:
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0"

# Then restart:
sudo systemctl restart ollama
```

### Windows

1. Open **System Environment Variables** (search for "environment variables" in Start menu)
2. Under **System Variables**, click **New**
3. Variable name: `OLLAMA_HOST`
4. Variable value: `0.0.0.0`
5. Click OK and **restart Ollama**

### macOS

```bash
launchctl setenv OLLAMA_HOST "0.0.0.0"
# Restart the Ollama app
```

### Firewall Rule

Make sure port **11434** is open:

```bash
# Linux (UFW)
sudo ufw allow 11434/tcp

# Windows: Allow through Windows Firewall
# → "Allow an app through firewall" → Add ollama.exe → Enable for Private networks
```

### Verify It's Accessible

Ask Aditya to run this from his laptop:

```bash
curl http://<YOUR_TAILSCALE_IP>:11434/api/tags
```

If he gets a JSON response listing your models, **you're connected!** 🎉

---

## 🗺️ Which AI Model Powers Which Agent

AeroFleet's actual 16-agent roster (`aerofleet/agents/factory.py`'s `DEFAULT_MODEL_MAP`) — only 5
distinct model tags across all 16 agents, since several agents in the same domain family share a
model:

| # | Agent | Domain | AI Model on Your PC |
|---|-------|--------|-------------------|
| 1 | Fleet Dispatcher | dispatch | `llama4:scout` |
| 2 | Route Planner | route | `mistral-small3.2` |
| 3 | Battery & Power Engineer | battery | `phi4-reasoning:plus` |
| 4 | Airspace Safety Officer | safety | `llama4:scout` |
| 5 | Weather Agent | weather | `gemma4:12b` |
| 6 | Comms / RF Link Agent | comms | `mistral-small3.2` |
| 7 | Cost Economist | cost | `phi4-reasoning:plus` |
| 8 | Ops Scheduler | operations | `gemma4:12b` |
| 9 | DGCA Compliance Advisor | compliance | `mistral-large-3` |
| 10 | Autonomy Validator | validation | `llama4:scout` |
| 11 | Payload / Delivery Specialist | payload | `phi4-reasoning:plus` |
| 12 | Conflict Avoidance Planner | conflict_avoidance | `llama4:scout` |
| 13 | Battery Swap Planner | battery_swap_planning | `phi4-reasoning:plus` |
| 14 | AI Governance Validator | governance_legal | `llama4:scout` |
| 15 | Cyber Security Auditor | cybersecurity | `llama4:scout` |
| 16 | Edge Compute Feasibility Agent | edge_compute | `phi4-reasoning:plus` |

> Models are loaded **one at a time** — Ollama swaps them automatically. Your GPU runs one model,
> finishes, then loads the next. (This table previously listed the pre-pivot Space Mission
> Architect's 12-agent roster and Qwen/DeepSeek/Llama-3.3 model names — stale from before the
> project's pivot to drone-fleet dispatch and corrected here.)

---

## 🔧 Troubleshooting

### "Connection refused" from Aditya's laptop
- Make sure `ollama serve` is running on your PC
- Verify `OLLAMA_HOST` is set to `0.0.0.0` (not `localhost`)
- Check firewall allows port 11434
- Verify Tailscale is connected on both machines

### Models download very slowly
- Use a wired ethernet connection if possible
- Don't download multiple models at once — do them one at a time
- If a download fails halfway, run the same `ollama pull` command again — it resumes

### Models run very slowly
- Run `nvidia-smi` to check GPU usage — if 0%, drivers may need updating
- Close other GPU-heavy apps (games, video editing, etc.)
- The 70B models are naturally slower (2-5 tokens/sec with CPU offload) — this is normal
- 14B models should run at 30-50 tokens/sec on a 24GB GPU

### "Out of memory" errors
- Shouldn't happen since Ollama manages VRAM automatically
- If it does: restart Ollama with `ollama stop` then `ollama serve`
- Close any other programs using the GPU

### Check disk space
```bash
# See how much space models are using:
du -sh ~/.ollama/models/   # Linux/macOS
# Windows: check %USERPROFILE%\.ollama\models\

# Remove a model if needed:
ollama rm <model-name>
```

---

## ✅ Checklist — Send a Screenshot To Aditya When Done

- [ ] Ollama installed (`ollama --version` works)
- [ ] All 4 models downloaded (`ollama list` shows 4 models)
- [ ] Tailscale installed and connected (or share your local IP)
- [ ] Ollama running in network mode (`OLLAMA_HOST=0.0.0.0`)
- [ ] Firewall allows port 11434
- [ ] Aditya confirmed he can reach your server (`curl` test passed)

**Once all boxes are checked, Aditya can start running AeroFleet from his laptop using your GPU for AI inference!**

---

> **Questions?** Call or message Aditya — he'll help debug any issues.
