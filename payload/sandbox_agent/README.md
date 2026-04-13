# Sentinel Sandbox Agent

This folder contains the agent scripts that run **inside** the sandbox VM to perform behavioral analysis of samples.

## Files

- `sentinel_agent.py` - **Primary unified agent** (observe -> classify -> decide -> resolve -> execute -> verify -> record)
- `agent_payload.py` - Legacy build entrypoint shim that forwards to `sentinel_agent.py`
- `agent_main.py` - Legacy import/CLI shim that forwards to `sentinel_agent.py`
- `agent.py` - Legacy process/file/network monitor-only script

## Installation (Inside VM)

1. Install Python 3.8+
2. Install dependencies:
   ```
   pip install psutil wmi
   ```
3. Copy this folder to `C:\Sandbox\` in the VM

## Usage

The agent is invoked automatically by the Sandbox Controller, but can be run manually:

```bash
python agent.py --sample C:\Sandbox\malware.exe --timeout 60 --output C:\Sandbox\report.json
```

## Output

Generates a JSON report with:
- Spawned processes
- Created/modified/deleted files
- Registry modifications
- Network connections

## Security Note

This agent is designed to run **inside an isolated VM only**. Never run it on your host system!

---

## Unified Agent Build & Deploy

### What it does

Unified state-aware agent with:
1. **Observe -> classify -> decide -> resolve -> execute -> verify loop**
2. **Strict control matching with confidence thresholds**
3. **Behavioral monitor + JSON report output compatible with host pipeline**
4. **Optional HUD and anti-evasion environment seeding**

### Prerequisites (on your HOST machine)

```bash
pip install pyautogui pyinstaller psutil wmi pywinauto
```

This project builds from `agent_payload.py`, which is now a compatibility shim
that forwards to the primary implementation in `sentinel_agent.py`.

### Build to standalone EXE

Run from the repo root:

```bash
pyinstaller --onefile --noconsole --name sentinel_agent ^
    --hidden-import tkinter ^
    --hidden-import pyautogui ^
    --hidden-import psutil ^
    --hidden-import wmi ^
    --hidden-import pywinauto ^
    payload/sandbox_agent/agent_payload.py
```

The output will be at `dist/sentinel_agent.exe`.

> **`--noconsole`** hides the black console window so only the HUD is visible.
> If you need debug output during development, remove `--noconsole`.

### Deploy to the Guest VM

Your `VMwareRunner` already has `copy_to_guest()` and `run_in_guest()`. Typical flow:

```python
runner.copy_to_guest("dist/sentinel_agent.exe", r"C:\Sentinel\Jobs\<job_id>\sentinel_agent.exe")
runner.copy_to_guest(sample_path, rf"C:\Sentinel\Jobs\<job_id>\{sample_name}")

# Run in no-wait mode so the VM keeps executing while host monitors
runner.run_in_guest(
    rf"C:\Sentinel\Jobs\<job_id>\sentinel_agent.exe",
    [rf"C:\Sentinel\Jobs\<job_id>\{sample_name}", "--timeout", "120"],
    wait=False,
)
```

### CLI usage (inside the VM)

```
sentinel_agent.exe C:\Sentinel\Jobs\abc123\rufus.exe
agent.exe C:\Sentinel\Jobs\abc123\rufus.exe --timeout 90
agent.exe C:\Sentinel\Jobs\abc123\rufus.exe --no-hud
```
