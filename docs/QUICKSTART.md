# Sentinel Quick Start Guide

This guide covers the shortest path to a working Sentinel development and execution environment on Windows or Linux. 

## 1. Clone the Repository

```bash
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp
```

## 2. Environment Setup

It is highly recommended to run Sentinel in an isolated Python Virtual Environment to prevent conflicts with your system packages (especially for PySide6 and `psutil`).

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**Linux (Bash):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install Dependencies

Install the core application requirements.

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Linux users must also install:**
```bash
pip install -r linux_requirements.txt
```

## 4. Configuration (.env)

Sentinel uses a `.env` file located in the root of the repository for API keys and sandbox configurations. While Sentinel will run perfectly fine without this file (gracefully degrading features), you will need it to unlock AI capabilities and the Sandbox Lab.

Create a `.env` file in the root directory:

```env
# Required for AI Assistant, Threat Summaries, and AI NGAV
GROQ_API_KEY=your_groq_key_here

# (Optional) Windows VMware Sandbox Setup
VMRUN_PATH=C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe
VMX_PATH=D:\vm\windows10\Windows 10 x64.vmx
VM_SNAPSHOT=Clean Base
VM_GUEST_USER=IEUser
VM_GUEST_PASS=Passw0rd!
```

## 5. Verify & Run

Before launching the QML UI, use the built-in backend diagnostics tool. This checks your host machine for required tools, optional scanners, Python paths, and database writable directories.

```bash
# 1. Run Diagnostics
python -m backend --diagnose

# 2. Start the Sentinel Desktop Application
python main.py
```

---

## Expanding Platform Capabilities

Sentinel is designed to use external tools if they are available in your system `PATH`. 

**Useful Optional Tools (Linux):**
- **Nmap:** Required for the Network Scanning module.
- **ClamAV:** Install `clamscan` and `clamd` for local signature-based scanning.
- **GPU Tools:** While Sentinel reads AMD metrics directly from `sysfs`, NVIDIA cards require `nvidia-smi` or `pynvml`.
- **Security Posture Checks:** Ensure `ufw`/`firewalld`, `mokutil` (for Secure Boot), and `aa-status` (AppArmor) are installed for full Security Snapshot coverage.

**Useful Optional Tools (Windows):**
- **Nmap for Windows:** Requires `npcap`.
- **VMware Workstation:** Required for the Sandbox Detonation lab.

---

## Where to go next?
- Want to package Sentinel as an `.exe`? See [BUILD_AND_VALIDATION.md](BUILD_AND_VALIDATION.md).
- Want to understand how Sentinel safely handles external processes? See [ARCHITECTURE.md](ARCHITECTURE.md).
- Want to see how the 11-stage Scan pipeline works? See [FEATURES_AND_WORKFLOWS.md](FEATURES_AND_WORKFLOWS.md).
