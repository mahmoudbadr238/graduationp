# Build, Validation & Quality Assurance

Sentinel handles sensitive system APIs, process manipulation, and real-time scanning, so release validation must be explicit and repeatable. This document describes the current commands that exist in the repository and separates passing release checks from configured cleanup baselines.

---

## 1. Static Analysis & Linting

`pyproject.toml` contains Ruff, mypy, Bandit, and pytest configuration. The full-repo Ruff and mypy baselines are currently not clean, so they are **not** documented as passing release gates until those findings are paid down.

Use these commands to inspect the current static-analysis baseline:

```bash
python -m ruff check backend main.py scripts
python -m ruff format backend main.py scripts --check
python -m mypy backend main.py --config-file pyproject.toml
python -m bandit -s B101 -r backend main.py
```

For release readiness, record the results honestly. Do not claim Ruff or mypy pass unless the commands above complete successfully on the release branch.

---

## 2. Automated Testing

The repository contains over 30 dedicated backend tests. Because hardware telemetry (like GPUs) and security postures (like AppArmor) differ vastly between developer machines, Sentinel employs heavy dependency injection and hardware mocking to ensure code paths are verified regardless of the host machine.

**Run Tests (Windows):**
```powershell
.venv\Scripts\python -m pytest backend/tests -q
```

**Run Tests (Linux):**
```bash
.venv/bin/python -m pytest backend/tests -q
```

### Key Test Coverages:
- **Regression Guards:** `test_windows_ui_regression_guards.py` and `test_modal_dialog_regressions.py` ensure that QML structure modifications do not break data bindings.
- **Hardware Mocking:** `test_linux_amd_gpu.py` uses simulated `sysfs` directories to test how the AMD telemetry parser reacts to missing sensors, shared-memory iGPUs, and permission errors.
- **Enforcement Safety:** `test_rtp_enforcement_safety.py` ensures that the Real-Time Protection process terminator accurately maps "allow" vs "block" verdicts.
- **State Normalization:** `test_degraded_states.py` verifies that missing dependencies (e.g., ClamAV not in PATH) result in `Unavailable` states rather than crashing the scanner orchestrator.

---

## 3. Diagnostics Toolkit

Sentinel ships with a built-in diagnostics CLI designed to preemptively catch environmental issues before launching the PySide6 UI. This is critical for users deploying Sentinel on custom Linux distributions or heavily hardened Windows machines.

```bash
python -m backend --diagnose
```

The diagnostics tool verifies:
- Read/write access to OS-specific configuration and logging paths (`%APPDATA%` or `$XDG_DATA_HOME`).
- The presence of optional binaries (`nmap`, `clamscan`, `nvidia-smi`).
- Database schema integrity for the SQLite WAL repositories.
- Resolution of required `GROQ_API_KEY` environment variables.

---

## 4. Build & Packaging

Sentinel is packaged into a standalone, portable desktop application using **PyInstaller**. Subprocesses and `multiprocessing` spawn logic are carefully adapted to survive PyInstaller's frozen environment (e.g., using `multiprocessing.freeze_support()`).

### Packaging on Windows
Due to WMI and `pywin32` dependencies, the Windows build must be executed on a Windows host.
```powershell
# Build the GUI bundle, helper executables, sandbox agent, and ZIP artifact.
.\scripts\build\build.ps1
```

The Windows build script produces `dist\Sentinel\Sentinel.exe` and `dist\Sentinel-Windows-x64.zip`. It also validates `Sentinel.exe --diagnose`, the URL detonator helper, and the GPU worker startup stream.

### Packaging on Linux
A helper script is provided to automate the virtual environment, install dependencies, and build a localized `dist` folder.
```bash
chmod +x scripts/run_linux.sh scripts/build/build_linux.sh
./scripts/run_linux.sh
./scripts/build/build_linux.sh

# Optional release archive after a successful packaged smoke test:
tar -czf Sentinel-Linux-x64.tar.gz -C dist Sentinel
```
*Note: Due to Qt/PySide6 dynamic linking (`.so` files), the Linux build is most compatible when packaged on older distributions (like Ubuntu 20.04/22.04) to ensure glibc backward compatibility on the target machine.*
