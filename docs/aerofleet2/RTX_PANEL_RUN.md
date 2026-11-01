# Running the review-panel test on a machine with an NVIDIA GPU

This runs four small local language models on 97 real crash cases (`research/results/panel_eval/real_cases.jsonl`,
already in the repository). It needs no flight logs, no API keys and no internet after the models are downloaded.
Expected time on an RTX laptop: about 1-3 hours for all four models. Declared in `research/panel_eval/real_cases.py`.

## 1. Install (once)

- **Git**: https://git-scm.com/download
- **Python 3.10 or newer**: https://www.python.org/downloads/ (on Windows, tick "Add python.exe to PATH")
- **Ollama**: https://ollama.com/download . It uses the NVIDIA GPU automatically; update the NVIDIA driver first.

## 2. Get the code and the models

Windows (PowerShell):

```powershell
git clone https://github.com/AdityaPathare46/aerofleet.git
cd aerofleet
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install requests
ollama pull gemma3:4b
ollama pull phi4-mini
ollama pull qwen2.5:3b
ollama pull qwen3:4b
ollama list
```

(macOS/Linux: `source .venv/bin/activate` instead of `.venv\Scripts\Activate.ps1`.)

`ollama list` must show these IDs. If one differs, still run it, but say so when you send the results.

| Model | ID |
|---|---|
| gemma3:4b | 68ceab7e468a |
| phi4-mini:latest | 78fad5d182a7 |
| qwen2.5:3b | 357c53fb659c |
| qwen3:4b | 359d7dd4bcda |

## 3. Run (from the `aerofleet` folder, with the venv active)

Windows (PowerShell):

```powershell
$env:PYTHONPATH = "."
foreach ($m in "gemma3:4b", "phi4-mini", "qwen2.5:3b", "qwen3:4b") { python -m research.panel_eval.real_cases run --model $m }
```

macOS/Linux:

```bash
for m in gemma3:4b phi4-mini qwen2.5:3b qwen3:4b; do PYTHONPATH=. python -m research.panel_eval.real_cases run --model $m; done
```

Each case prints one line. If it stops (sleep, crash), run the same command again: it skips finished cases.
Keep the laptop plugged in and stop it from sleeping. Do not change any code or the case file.

## 4. Send back

1. The four files `research/results/panel_eval/real_gemma3_4b.jsonl`, `real_phi4-mini.jsonl`, `real_qwen2.5_3b.jsonl`,
   `real_qwen3_4b.jsonl` (97 lines each).
2. The output of `ollama list` and of `nvidia-smi` (first 10 lines), as text.
