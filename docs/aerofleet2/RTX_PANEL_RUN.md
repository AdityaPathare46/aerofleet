# Running the drone-crash language-model test on your RTX laptop

Thanks for helping. This runs four small AI models (2-4 GB each) on 97 real drone-crash cases and records their
answers. Everything runs locally on your GPU: no accounts, no API keys, no data leaves your laptop, and you do not
need any flight logs (the 97 cases are already in the repository).

- **Your time:** about 20 minutes to set up, then leave it running.
- **Run time:** roughly 1-3 hours for all four models on an RTX GPU.
- **Disk space:** about 12 GB (mostly the models).
- **What you send back:** four small text files and two command outputs (step 5).

Please do not change any code or the case file: the test was declared in advance, so the results must come from the
code exactly as it is.

## 1. Install three things (skip any you already have)

1. **Git**: https://git-scm.com/download/win
2. **Python 3.10 or newer**: https://www.python.org/downloads/
   During setup, tick **"Add python.exe to PATH"**.
3. **Ollama** (runs the models on your GPU): https://ollama.com/download
   Update your NVIDIA driver first (GeForce Experience or https://www.nvidia.com/drivers). After installing, Ollama
   runs in the background (llama icon near the clock).

Close and reopen PowerShell after installing, so it finds the new programs.

## 2. Get the code (PowerShell)

Open **PowerShell** (Start menu, type "PowerShell"), go to a folder with space, and run these one at a time:

```powershell
git clone https://github.com/AdityaPathare46/aerofleet.git
cd aerofleet
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install requests
```

Your prompt should now start with `(.venv)`.

## 3. Download the four models

```powershell
ollama pull gemma3:4b
ollama pull phi4-mini
ollama pull qwen2.5:3b
ollama pull qwen3:4b
ollama list
```

Check the **ID** column of `ollama list` against this table. If one is different, run it anyway, but tell us.

| Model | ID |
|---|---|
| gemma3:4b | 68ceab7e468a |
| phi4-mini:latest | 78fad5d182a7 |
| qwen2.5:3b | 357c53fb659c |
| qwen3:4b | 359d7dd4bcda |

## 4. Run the test

Plug the laptop in and stop it from sleeping (Settings > System > Power > Screen and sleep: "Never" while plugged
in). Then, in the same PowerShell window (prompt starts with `(.venv)`, inside the `aerofleet` folder):

```powershell
$env:PYTHONPATH = "."
foreach ($m in "gemma3:4b", "phi4-mini", "qwen2.5:3b", "qwen3:4b") { python -m research.panel_eval.real_cases run --model $m }
```

Each finished case prints one line, for example:

```
F7006 GPS_DEGRADED | rule WIND_OR_ENVIRONMENT | single UNKNOWN | panel UNKNOWN
```

There are 97 lines per model, 388 in total. It is finished when the prompt comes back after the fourth model.

**To check the GPU is being used:** open a second PowerShell window and run `ollama ps`. The PROCESSOR column should
say `100% GPU` (or mostly GPU). If it says CPU, see Troubleshooting.

**If it stops** (sleep, restart, closed window): open PowerShell, `cd` into the `aerofleet` folder, run
`.venv\Scripts\Activate.ps1`, then the two run lines again. It skips the cases already done.

## 5. Send back

1. These four files from the folder `aerofleet\research\results\panel_eval\` (97 lines each):
   - `real_gemma3_4b.jsonl`
   - `real_phi4-mini.jsonl`
   - `real_qwen2.5_3b.jsonl`
   - `real_qwen3_4b.jsonl`
2. The text output of these two commands (copy and paste, or a screenshot):
   ```powershell
   ollama list
   nvidia-smi
   ```

## Troubleshooting

- **`Activate.ps1 cannot be loaded because running scripts is disabled`**: run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer `Y`, then run `.venv\Scripts\Activate.ps1` again.
- **`python` is not recognized / opens the Microsoft Store**: reinstall Python with "Add python.exe to PATH" ticked,
  then reopen PowerShell. Or use `py` instead of `python` in every command.
- **`ollama` is not recognized**: reopen PowerShell after installing Ollama, or start the Ollama app from the Start
  menu.
- **`connection refused` / `11434` errors**: Ollama is not running. Start the Ollama app from the Start menu and run
  the command again.
- **`ModuleNotFoundError: No module named 'research'`**: you are not in the `aerofleet` folder, or the
  `$env:PYTHONPATH = "."` line was not run in this window.
- **`ollama ps` shows CPU**: update the NVIDIA driver, restart the laptop, and make sure the laptop is plugged in
  (some laptops switch off the GPU on battery). It still works on CPU, just slower.

macOS or Linux instead of Windows: use `source .venv/bin/activate` to activate, and run
`for m in gemma3:4b phi4-mini qwen2.5:3b qwen3:4b; do PYTHONPATH=. python -m research.panel_eval.real_cases run --model $m; done`.

Declared in `research/panel_eval/real_cases.py` (amendment 1).
