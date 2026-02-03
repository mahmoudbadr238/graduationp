# Sentinel Sandbox Agent

This folder contains the agent scripts that run **inside** the sandbox VM to perform behavioral analysis of samples.

## Files

- `agent.py` - Main monitoring agent that tracks processes, files, registry, and network activity

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
