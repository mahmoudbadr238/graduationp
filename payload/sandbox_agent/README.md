# Sentinel Sandbox Agent

This folder contains the agent scripts that run **inside** the sandbox VM to perform behavioral analysis of samples.

## Files

- `agent.py` - Main monitoring agent that tracks processes, files, registry, and network activity
- `agent_payload.py` - **Visual Agent** — human-like GUI automation with floating HUD overlay (compiled to `agent.exe`)

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

## Visual Agent (`agent_payload.py`) — Build & Deploy

### What it does

A "Computer-Use Agent" that runs inside the guest VM with:
1. **Floating HUD** — borderless, semi-transparent, always-on-top overlay pinned to top-center showing real-time status
2. **Human-like mouse & keyboard** — all movements use `pyautogui.easeInOutQuad` with ~1.4 s travel so it looks natural on screen
3. **Full interaction sequence** — opens Explorer → finds & double-clicks the sample → dismisses UAC → clicks through installer prompts → scrolls & explores the UI → monitors for the configured timeout

### Prerequisites (on your HOST machine)

```bash
pip install pyautogui pyinstaller pillow opencv-python
```

> `pillow` and `opencv-python` are required by `pyautogui.locateOnScreen()` for image-matching confidence.

### Build to standalone EXE

Run from the repo root (or from `tools/sandbox_agent/`):

```bash
pyinstaller --onefile --noconsole --name agent ^
    --hidden-import tkinter ^
    --hidden-import pyautogui ^
    tools/sandbox_agent/agent_payload.py
```

The output will be at `dist/agent.exe` (~15-25 MB standalone).

> **`--noconsole`** hides the black console window so only the HUD is visible.
> If you need debug output during development, remove `--noconsole`.

### Deploy to the Guest VM

Your `VMwareRunner` already has `copy_to_guest()` and `run_in_guest()`. Typical flow:

```python
runner.copy_to_guest("dist/agent.exe", r"C:\Sentinel\Jobs\<job_id>\agent.exe")
runner.copy_to_guest(sample_path, rf"C:\Sentinel\Jobs\<job_id>\{sample_name}")

# Run in no-wait mode so the VM keeps executing while host monitors
runner.run_in_guest(
    rf"C:\Sentinel\Jobs\<job_id>\agent.exe",
    [rf"C:\Sentinel\Jobs\<job_id>\{sample_name}", "--timeout", "120"],
    wait=False,
)
```

### CLI usage (inside the VM)

```
agent.exe C:\Sentinel\Jobs\abc123\rufus.exe
agent.exe C:\Sentinel\Jobs\abc123\rufus.exe --timeout 90
agent.exe C:\Sentinel\Jobs\abc123\rufus.exe --no-hud
```
