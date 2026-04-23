# Sentinel

**An Advanced, Cross-Platform Endpoint Security & Telemetry Suite**

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![Platform: Windows | Linux](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey.svg)
![Framework: PySide6](https://img.shields.io/badge/Framework-PySide6-brightgreen.svg)

**Sentinel** is a desktop endpoint security application built with Python and PySide6/QML. Designed to bridge the gap between deep system administration and modern threat analysis, Sentinel provides an integrated environment for system telemetry, security posture assessment, network scanning, malware detonation, and AI-assisted event analysis.

> [!NOTE]
> **Academic & Professional Context**  
> Sentinel was developed as an extensive engineering project. It demonstrates complex systems integration—including multi-processing, inter-process communication (IPC), raw Linux `sysfs` parsing, Windows WMI integration, and graceful dependency degradation—all behind a unified, declarative UI.

---

## The Problem & The Solution

**The Problem:** Typical endpoint security tools are either commercial black-boxes that obscure their telemetry, or fragmented CLI utilities (Nmap, ClamAV, `nvidia-smi`) that lack a unified investigative interface. Furthermore, cross-platform tools often rely on lazy OS wrappers rather than deep, platform-native integrations.

**The Solution:** Sentinel consolidates discrete security operations into a single pane of glass without hiding the underlying truth. It features natively implemented OS probes (e.g., direct `sysfs`/DRM reads on Linux, WMI on Windows), isolates heavy scanning operations in subprocesses to guarantee UI fluidity, and strictly reports missing capabilities (graceful degradation) instead of crashing or faking data.

---

## Core Engineering Highlights

Sentinel is engineered to professional standards, heavily focusing on resilience, thread safety, and platform integrity.

- **Process Isolation & IPC:** Heavy workloads like GPU telemetry, URL detonation, and the VMware Sandbox run in isolated subprocesses. A custom QML-to-Python `BackendBridge` manages asynchronous IPC, ensuring the UI remains highly responsive even during 100% CPU scanning events.
- **Graceful Degradation:** The application implements "truthful platform boundaries." If `nmap`, `clamav`, `vmrun`, or an API key is missing, Sentinel dynamically adjusts the UI to report `Unavailable` or `Permission Required` rather than failing.
- **Native Telemetry (No Wrappers):** Instead of relying on generic wrappers, Sentinel natively parses the Linux systemd journal, enumerates PCI buses for hybrid GPU detection, and queries Windows Event Logs via `pywin32`.
- **Quality Assurance:** The repository enforces strict `mypy` typing, extensive `ruff` and `bandit` linting, and relies on an automated suite of over 30 backend tests specifically targeting regression guards and hardware mocking.

For a deep dive into the system design, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Key Capabilities & Modules

Sentinel integrates over a dozen discrete modules into a unified workflow. Below is a high-level summary. For complete technical details, see [FEATURES_AND_WORKFLOWS.md](docs/FEATURES_AND_WORKFLOWS.md).

### 🛡️ Real-Time Protection (RTP)
Continuous process monitoring utilizing WMI on Windows and process polling on Linux. It intercepts newly spawned processes, runs them through static analysis and AI heuristics, and can actively terminate malicious executions based on configured policies.

### 🔬 Multi-Engine Scan Center
An 11-stage file analysis pipeline. Submissions undergo PE extraction (`pefile`), embedded IOC string extraction, local ClamAV signature checks, and **Groq AI Next-Gen AV** behavioral analysis, culminating in a deterministic verdict.

### 🧪 Dynamic Sandbox Lab
*(Windows Only)* Live malware detonation using VMware Workstation. Sentinel reverts the VM to a clean snapshot, injects the sample, executes it, and captures high-resolution video streams alongside process/file/network delta reports.

### 📊 Advanced Hardware Telemetry
A real-time metrics dashboard capable of handling multi-GPU and hybrid laptop setups. It aggregates NVML, AMD ADL SDK, and direct DRM `sysfs` reads to report utilization, VRAM, power draw, and temperatures without requiring heavy vendor suites like ROCm.

### 🧠 AI Security Assistant
Integrated with Groq (`llama-3.3-70b-versatile` and `llama-3.1-8b-instant`), Sentinel can translate raw Windows Event Logs, systemd journal entries, and dense scan reports into plain-English threat summaries and actionable remediation steps.

### 🧰 Forensics & Network
Features secure 3-pass file shredding, forensic file carving (recovering JPEGs/PDFs from raw disk sectors), and an Nmap-powered network scanner for host discovery and vulnerability probing.

---

## Platform Support & Integrity

Sentinel respects platform realities. It does not attempt to simulate Windows features on Linux or vice versa.

| Capability | Windows | Linux |
| :--- | :---: | :---: |
| **System Snapshot & Posture** | Yes (Defender, UAC) | Yes (UFW, AppArmor, ClamAV) |
| **GPU Telemetry** | Yes (NVML, AMD ADL) | Yes (sysfs, DRM, NVML) |
| **Real-Time Protection** | Yes (WMI Watcher) | Yes (Process Polling) |
| **Event Viewer** | Yes (Windows Event Log) | Yes (`journalctl`) |
| **Sandbox Detonation** | Yes (VMware) | ❌ *Not Supported* |
| **XDG Runtime Paths** | ❌ AppData | Yes |

---

## Tech Stack Overview

- **Frontend:** PySide6 (Qt 6.6.0+), QML
- **Backend Core:** Python 3.11+, `psutil`, SQLite3 (WAL mode)
- **Windows Integrations:** `pywin32`, `wmi`, `pefile`, VMware `vmrun`
- **Linux Integrations:** `journalctl`, `sysfs`/DRM parsing, `ufw`/`aa-status` wrappers
- **AI/LLM:** Groq API SDK
- **Testing & Tooling:** `pytest`, `mypy` (strict), `ruff`, `bandit`, PyInstaller

---

## Getting Started

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Installation
```bash
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (Linux)
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
# Linux users also run: pip install -r linux_requirements.txt
```

### 3. Verification & Launch
Before launching the UI, it is highly recommended to run the built-in diagnostic tool. This will verify runtime paths, check optional dependencies (like Nmap, ClamAV), and validate API keys.

```bash
python -m backend --diagnose
python main.py
```

For advanced configuration (including API keys and Sandbox setup), see the [QUICKSTART.md](docs/QUICKSTART.md).

---

## Project Structure

```text
graduationp/
├── backend/
│   ├── api/              # QML-to-Python bridge and QProcess workers
│   ├── core/             # Dependency injection, logging, startup orchestration
│   ├── engines/          # Security modules (AI, Sandbox, Scanners, GPU, Forensics)
│   ├── infra/            # External integrations (Nmap CLI, SQLite, psutil)
│   ├── platform/         # OS-specific implementations (e.g., Linux sysfs parsing)
│   └── tests/            # Pytest regression suite
├── frontend/
│   └── qml/
│       ├── components/   # Reusable UI cards, dialogs, charts
│       ├── pages/        # Main application views (ScanCenter, SystemSnapshot, etc.)
│       └── ui/           # Global theme manager
├── docs/                 # Detailed architectural and workflow documentation
└── main.py               # Application entrypoint
```

---

## Documentation Index

To explore the engineering depth of Sentinel, refer to the following specific documents:

1. [**ARCHITECTURE.md**](docs/ARCHITECTURE.md): Deep dive into IPC, subprocess isolation, and the UI-to-Backend bridge.
2. [**FEATURES_AND_WORKFLOWS.md**](docs/FEATURES_AND_WORKFLOWS.md): Detailed breakdowns of the 11-stage scan pipeline, dynamic sandbox, and AI integration.
3. [**BUILD_AND_VALIDATION.md**](docs/BUILD_AND_VALIDATION.md): Overview of the strict typing, testing rigor, and packaging strategies.
4. [**QUICKSTART.md**](docs/QUICKSTART.md): Complete setup guide, including environment variables and optional tools.

---

## Limitations & Truthfulness Notes

In the interest of full engineering transparency:
- **Production Readiness:** Sentinel is a sophisticated graduation/research project. While it employs production-grade patterns (strict typing, IPC), it is not a commercially certified EDR replacement.
- **AI Hallucinations:** The Groq-powered AI Assistant and NGAV components are assistive. LLMs can hallucinate; therefore, the core enforcement engine relies on deterministic scoring.
- **Sandbox Extensibility:** The Sandbox Lab requires a locally installed, licensed copy of VMware Workstation. It is not currently designed for cloud hypervisor scaling.
- **Linux Evasion:** The Linux Real-Time Protection relies on user-space process polling (`psutil`). Advanced rootkits can bypass user-space polling by hiding PIDs in the kernel.

---

## License

This project is licensed under the [MIT License](LICENSE).
