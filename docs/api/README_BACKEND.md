# Sentinel Backend Architecture

## Overview

Sentinel uses a Python backend with PySide6/QML integration, modular services,
and optional external tooling for specific workflows such as network scanning
and sandbox execution.

The current repository structure is centered on `backend/` and `frontend/qml/`.

---

## Backend Structure

### `backend/api/`

QML-facing services and bridge objects.

Examples:
- `backend_bridge.py`
- settings and notification services
- GPU and snapshot services

### `backend/core/`

Core runtime concerns:

- startup orchestration
- dependency injection
- logging and crash handling
- resource monitoring
- configuration helpers

### `backend/engines/`

Feature-specific engines, including:

- AI-related services
- scan and report pipelines
- sandbox and VMware integration
- file and recovery workflows
- threat-intelligence and supporting utilities

### `backend/infra/`

Infrastructure helpers and external tool detection, such as Nmap availability.

### `backend/tests/`

Automated tests for core backend behavior.

### `backend/utils/`

Diagnostics, privilege helpers, and support utilities.

---

## Application Flow

1. `main.py` starts the desktop application
2. `backend.application` configures services and QML context properties
3. `BackendBridge` exposes slots and signals to QML
4. QML pages in `frontend/qml/` call into the backend services

---

## Main User-Facing Services

| Area | Backend Role |
|------|--------------|
| System monitoring | Live CPU, memory, disk, network, and GPU data |
| Event workflows | Windows event loading and explanation paths |
| Scan Center | File, URL, report, and history orchestration |
| Network scan | Nmap-backed scanning when available |
| Sandbox Lab | VMware-backed detonation and preview workflows |
| Notifications | In-app notification center and tray support |

---

## Configuration Surface

Sentinel primarily uses environment variables and local config files.

Common environment variables:

```env
GROQ_API_KEY=
SENTRY_DSN=
NMAP_PATH=
OFFLINE_ONLY=false

SANDBOX_VMRUN=
SANDBOX_VMX=
SANDBOX_SNAPSHOT=
SANDBOX_GUEST_USER=
SANDBOX_GUEST_PASS=
```

Use `.env.example` as the template for local setup.

---

## Diagnostics

The current user-facing diagnostics entrypoint is:

```bash
python -m backend --diagnose
```

Additional supported commands:

```bash
python -m backend --export-diagnostics diagnostics.json
python -m backend --reset-settings
```

These are the preferred first steps when validating a new machine or debugging a
local setup issue.

---

## Optional Integrations

### Groq

Used for AI-backed assistant and report interpretation flows when configured.

### Nmap

Used for network scanning when installed or provided through `NMAP_PATH`.

### VMware Workstation

Used for Sandbox Lab and sandbox-assisted scan flows when configured correctly.

### Sentry

Optional crash reporting when `SENTRY_DSN` is set.

---

## Testing and Validation

Typical backend validation commands:

```bash
python -m backend --diagnose
python -m pytest backend/tests -q
python -m ruff check backend main.py scripts
python -m ruff format backend main.py scripts --check
python -m mypy backend main.py --config-file=pyproject.toml
python -m bandit -s B101 -r backend main.py
```

---

## Notes for Contributors

- Keep QML-facing changes aligned with `BackendBridge`
- Prefer targeted service changes over broad refactors
- Update docs when setup or runtime behavior changes
- Treat optional integrations as optional, not baseline requirements
