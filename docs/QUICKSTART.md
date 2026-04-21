# Sentinel Quick Start

This guide covers the shortest path to a working Sentinel development setup on
Windows or Linux.

## 1. Clone the Repo

```bash
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp
```

## 2. Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install Dependencies

Base dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Linux also uses:

```bash
pip install -r linux_requirements.txt
```

## 4. Run Diagnostics Before the UI

```bash
python -m backend --diagnose
```

Use diagnostics to verify:

- runtime paths
- optional integrations
- platform-specific probes
- degraded dependencies before launch

## 5. Launch Sentinel

```bash
python main.py
```

## Linux-Specific Expectations

Sentinel runs on Linux without pretending to be a Windows app. The Linux build
uses:

- XDG config/data/cache/state directories
- filtered storage views by default
- a debug toggle for hidden mounts in System Snapshot
- platform-native firewall, package, encryption, Secure Boot, remote-access,
  and MAC checks
- explicit GPU sensor states such as `Unsupported`, `Unavailable`,
  `Permission required`, or `Not exposed`

Useful optional tools on Linux:

- `nvidia-smi` or `pynvml` for NVIDIA telemetry
- `rocm-smi` for AMD telemetry
- `ufw`, `firewalld`, `nftables`, or `iptables`
- `clamscan` / `clamd`
- `mokutil`
- `aa-status`
- `lsblk`

## Windows-Specific Expectations

Windows remains the only platform for:

- Event Viewer integration
- Windows-specific Defender and UAC flows
- VMware sandbox execution from the desktop host

## Build and Packaging

Linux helper scripts in the repo:

- [run_linux.sh](../run_linux.sh) provisions and runs the app on Linux
- [build_linux.sh](../build_linux.sh) builds a PyInstaller package on Linux

## Validation

Windows:

```powershell
.venv\Scripts\python -m pytest backend/tests -q
```

Linux:

```bash
.venv/bin/python -m pytest backend/tests -q
```

## Need More Detail?

- [README.md](../README.md)
- [docs/guides/LINUX_SUPPORT.md](guides/LINUX_SUPPORT.md)
- [docs/api/README_BACKEND.md](api/README_BACKEND.md)
