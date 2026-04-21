# Linux Support

This document describes the current Linux behavior of Sentinel and the places
where Linux support is intentionally different from Windows.

## What Is First-Class on Linux

- System Snapshot
- Storage classification and filtering
- Security posture collection
- GPU device detection and normalized telemetry states
- File scanning and quarantine flows
- Network scan UI and diagnostics
- Cross-platform runtime paths, logging, and crash capture

## Storage Behavior

The Linux storage view is normalized before it reaches QML.

Default view:

- shows primary, internal, external, boot, and network mounts
- hides pseudo filesystems and system-managed mounts
- hides loop devices and Snap `squashfs` images
- hides container overlays and similar non-actionable mounts

Debug view:

- the System Snapshot storage section exposes `Show debug mounts`
- hidden mounts remain available for advanced inspection

## GPU Telemetry

Linux GPU telemetry uses a provider-based architecture with per-metric
availability tracking.

### Detection priority

| Priority | Provider | Vendor |
|----------|----------|--------|
| 1 | NVML / `pynvml` | NVIDIA |
| 2 | `nvidia-smi` (fallback) | NVIDIA |
| 3 | **amdgpu sysfs** (native Linux kernel interface) | AMD |
| 4 | `rocm-smi` (if ROCm is installed) | AMD |
| 5 | pyadl (Windows ADL SDK — WSL only) | AMD |
| 6 | hardware identification via `lspci` | all vendors |

The amdgpu sysfs provider reads directly from the kernel's DRM and hwmon
interfaces.  It requires only the standard `amdgpu` kernel module that ships
with Ubuntu; no ROCm installation or proprietary tools are needed.

### AMD GPU support on Linux

Ubuntu with `amdgpu`-backed hardware (discrete or integrated) will show:

- **GPU name** — resolved from `lspci` using the card's PCI address
- **GPU utilisation** — from `gpu_busy_percent` sysfs node
- **Temperature** — from `hwmon/hwmon*/temp1_input` (if exposed)
- **Power draw** — from `hwmon/hwmon*/power1_average` (if exposed)
- **Fan speed** — from `hwmon/hwmon*/pwm1` and `fan1_input` (if exposed)
- **VRAM** — from `mem_info_vram_total` / `mem_info_vram_used` (discrete GPUs)
- **Driver** — amdgpu kernel module version from `/sys/module/amdgpu/version`

### AMD integrated GPU / APU memory

AMD APUs and integrated Radeon graphics use shared system memory rather than
dedicated VRAM.  Sentinel detects this condition and labels the memory tiles
**"Shared memory"** instead of showing `0 B` or `Unavailable`.

The underlying GTT (shared pool) size is read from sysfs and recorded
internally, but is not shown as a dedicated VRAM figure to avoid confusion.

Some sensors (temperature, power, fan) may not be exposed by the hwmon driver
on certain APU generations; those tiles show **"Not exposed"** rather than a
fabricated value.

### Metric availability states

Sentinel does not invent missing Linux sensor values.  Each metric is
normalised with an explicit availability state:

| State | UI label | Meaning |
|-------|----------|---------|
| `ok` | Live | Metric is actively collected |
| `unsupported` | Unsupported | Hardware or driver does not support this metric |
| `unavailable` | Unavailable | Metric should exist but could not be read |
| `permission_denied` | Permission required | Elevated privileges needed |
| `not_exposed` | Not exposed | Sensor exists but driver does not surface it |
| `backend_error` | Backend error | Metric query failed with an error |
| `shared_memory` | Shared memory | iGPU uses shared system RAM; no dedicated figure |

This prevents unsupported sensors from showing fake `0%` or `0 C` readings.

### Windows GPU path

The Windows GPU implementation (`backend/engines/gpu/telemetry_worker.py`) is
unchanged.  All Linux AMD work lives in:

- `backend/platform/linux/drm_enumeration.py`
- `backend/platform/linux/amd_sysfs_provider.py`
- `backend/platform/linux/telemetry_worker.py`
- `backend/platform/linux/gpu_normalization.py`

## Security Posture

On Linux, Sentinel evaluates platform-native signals where possible:

- firewall status
- antivirus presence and daemon activity
- package update state
- Secure Boot state
- disk encryption for root/home backing devices
- remote administration exposure
- AppArmor / SELinux enforcement

The UI uses a posture summary and provider diagnostics instead of Windows-only
labels.

## Runtime Paths

Linux uses XDG-style paths by default:

- config: `$XDG_CONFIG_HOME/sentinel`
- data: `$XDG_DATA_HOME/sentinel`
- cache: `$XDG_CACHE_HOME/sentinel`
- state: `$XDG_STATE_HOME/sentinel`
- logs: `$XDG_STATE_HOME/sentinel/logs`
- crashes: `$XDG_STATE_HOME/sentinel/crashes`

Legacy compatibility reads still check older locations such as
`~/.config/Sentinel`, `~/.local/share/Sentinel`, and `~/.sentinel`.

## Optional Linux Tools

These are optional but improve fidelity:

- `nvidia-smi`
- `pynvml`
- `rocm-smi`
- `ufw`
- `firewalld`
- `nftables`
- `iptables`
- `clamscan`
- `clamd`
- `mokutil`
- `aa-status`

If a tool is missing, Sentinel should surface the missing provider as degraded
or unavailable rather than silently treating the machine as healthy.

## Current Linux Gaps

These areas remain Windows-only or intentionally limited on Linux:

- Event Viewer collection
- Windows Defender / UAC / TPM flows
- VMware sandbox execution from a Linux host

The product should report those boundaries honestly in the UI and diagnostics.
