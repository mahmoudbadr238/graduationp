# Integration Guide - Sentinel Security Suite

## Overview

Sentinel supports a small set of optional integrations and external tools. The
desktop application can still run without them, but certain workflows become
limited or unavailable.

This guide focuses on the integrations that are part of the current project
setup:

- Groq for AI-assisted analysis
- Nmap for network scanning
- VMware Workstation for sandbox-backed workflows
- Sentry for optional crash reporting

---

## Groq Integration

### What it is

Groq is the primary AI provider used by the current Sentinel setup for assistant
responses and AI-generated summaries.

### Configuration

Add your key to `.env`:

```env
GROQ_API_KEY=gsk_your_key_here
```

You can also set it for the current PowerShell session:

```powershell
$env:GROQ_API_KEY = "gsk_your_key_here"
python main.py
```

### Verification

1. Launch Sentinel
2. Open the Security Assistant or AI-backed scan/report flow
3. Confirm AI responses are available

### Troubleshooting

**Missing key**
- Confirm `.env` exists in the repo root
- Confirm `GROQ_API_KEY` is non-empty
- Restart Sentinel after editing `.env`

**Network or auth errors**
- Re-run `python -m backend --diagnose`
- Check your network/proxy settings
- Verify the key in the Groq console

---

## Nmap Integration

### What it is

Nmap powers Sentinel's optional network scanning workflows.

### Setup Instructions

1. Download Nmap from https://nmap.org/download.html
2. Install it and add it to `PATH`
3. If needed, set a custom path in `.env`:

```env
NMAP_PATH=C:\Program Files (x86)\Nmap\nmap.exe
```

### Verification

```powershell
nmap --version
python -m backend --diagnose
```

Then launch Sentinel and open the Network Scan page.

### Safety Note

Only scan systems and networks you own or are authorized to assess.

---

## VMware Workstation Integration

### What it is

VMware Workstation is used for Sandbox Lab and sandbox-backed analysis flows in
the current project.

### Required Environment Variables

```env
SANDBOX_VMRUN=C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe
SANDBOX_VMX=D:\vm\windows10\Windows 10 x64.vmx
SANDBOX_SNAPSHOT=Clean Base
SANDBOX_GUEST_USER=
SANDBOX_GUEST_PASS=
SANDBOX_HOST_RESULTS_DIR=C:\SentinelSandbox\results
SANDBOX_HOST_FRAMES_DIR=C:\SentinelSandbox\frames
```

### Verification

1. Confirm VMware Workstation is installed
2. Confirm the VMX path and snapshot name are correct
3. Launch Sentinel
4. Use Sandbox Lab diagnostics or a sandbox-backed scan flow

### Troubleshooting

**VMware not detected**
- Verify `SANDBOX_VMRUN`
- Check that `vmrun.exe` exists at that path

**Guest actions fail**
- Recheck `SANDBOX_GUEST_USER` and `SANDBOX_GUEST_PASS`
- Confirm VMware Tools is installed in the guest
- Confirm the snapshot exists

---

## Sentry Crash Reporting

### What it is

Sentry is optional and used only when you explicitly configure crash reporting.

### Configuration

```env
SENTRY_DSN=
```

If it is left empty, crash reporting remains disabled.

---

## Environment Variables Reference

| Variable | Type | Purpose |
|----------|------|---------|
| `GROQ_API_KEY` | String | Enables AI-backed features |
| `SENTRY_DSN` | String | Enables optional crash reporting |
| `NMAP_PATH` | Path | Custom path to `nmap.exe` |
| `OFFLINE_ONLY` | Boolean | Disable external API calls |
| `SANDBOX_VMRUN` | Path | Path to `vmrun.exe` |
| `SANDBOX_VMX` | Path | Path to the sandbox VMX |
| `SANDBOX_SNAPSHOT` | String | Snapshot name used for sandbox reset |
| `SANDBOX_GUEST_USER` | String | Guest username |
| `SANDBOX_GUEST_PASS` | String | Guest password |

### Example `.env`

```env
GROQ_API_KEY=
SENTRY_DSN=
NMAP_PATH=
OFFLINE_ONLY=false

SANDBOX_VMRUN=C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe
SANDBOX_VMX=D:\vm\windows10\Windows 10 x64.vmx
SANDBOX_SNAPSHOT=Clean Base
SANDBOX_GUEST_USER=
SANDBOX_GUEST_PASS=
```

---

## Offline Mode

Set:

```env
OFFLINE_ONLY=true
```

This disables external API usage while still allowing the local desktop
application to run in a reduced mode.

---

## Help

- Main project docs: [../README.md](../README.md)
- Quick start: [../QUICKSTART.md](../QUICKSTART.md)
- Backend overview: [README_BACKEND.md](README_BACKEND.md)
- VMware guide: [../sandbox_vmware.md](../sandbox_vmware.md)
