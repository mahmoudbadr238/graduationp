# Build, Validation & Quality Assurance

Sentinel is developed under strict engineering standards. Because an Endpoint Security suite handles highly sensitive system APIs, process manipulation, and real-time scanning, the codebase is aggressively linted and tested.

---

## 1. Static Analysis & Linting

Sentinel utilizes modern Python tooling configured for strict enforcement. See `pyproject.toml` for the complete configuration rulesets.

### Mypy (Strict Mode)
All Python code runs through `mypy` with `strict = true` enabled. This enforces:
- `disallow_untyped_defs`
- `no_implicit_optional`
- `strict_equality`

This prevents a massive class of runtime `NoneType` and type-casting errors that plague complex cross-platform integrations.

### Ruff & Bandit
Code quality and formatting are governed by **Ruff**, utilizing over 30 extended rulesets (including `flake8-bugbear`, `flake8-simplify`, and `perflint`). 
Additionally, **Bandit** is run continuously to catch insecure patterns (e.g., hardcoded SQL, insecure subprocess calls without shell escaping).

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
# Create the standalone executable (hidden console)
pyinstaller sentinel_agent.spec
```

### Packaging on Linux
A helper script is provided to automate the virtual environment, install dependencies, and build a localized `dist` folder.
```bash
./build_linux.sh
```
*Note: Due to Qt/PySide6 dynamic linking (`.so` files), the Linux build is most compatible when packaged on older distributions (like Ubuntu 20.04/22.04) to ensure glibc backward compatibility on the target machine.*
