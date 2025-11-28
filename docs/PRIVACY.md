# Privacy Policy

Sentinel respects your privacy. This document describes what data we collect and how it's used.

## Data Collection

### Data We DO NOT Collect

- **No cloud uploads** – All analysis runs locally on your machine
- **No user tracking** – No analytics or tracking cookies
- **No browsing history** – We don't monitor or store your activity
- **No file scanning by default** – VirusTotal is disabled unless explicitly configured

### Data We Collect Locally

**Stored on your computer** (`~/.sentinel/` and `%APPDATA%/Sentinel/`):
- System metrics (CPU, memory, disk, network)
- Windows security event logs
- Network adapter information
- GPU status and temperature
- Application settings and preferences
- Diagnostic logs

### Optional Data Sharing

**Only enabled if explicitly configured:**

#### Sentry (Crash Reporting)
- **When**: Unhandled application crashes
- **What**: Stack trace, system info, environment details
- **How to enable**: Set `SENTRY_DSN` environment variable
- **Opt-out**: Do not set `SENTRY_DSN`

#### VirusTotal (File Scanning)
- **When**: You manually scan a file/URL (optional feature, disabled by default)
- **What**: File hash, file content, scan results
- **How to enable**: Set `VT_API_KEY` environment variable
- **Opt-out**: Do not set `VT_API_KEY`

#### Nmap (Network Scanning)
- **When**: You manually scan a network (optional feature, disabled by default)
- **What**: Network topology, open ports, services
- **How to enable**: Install Nmap on your system
- **Opt-out**: Do not install Nmap

## Local Storage

### Configuration Files

**Location**: `%APPDATA%/Sentinel/settings.json` (Windows) or `~/.local/share/sentinel/settings.json` (Linux)

**Contains**:
```json
{
  "sampling_rates": {
    "cpu_interval_ms": 1000,
    "gpu_interval_ms": 2000
  },
  "feature_toggles": {
    "enable_gpu_monitoring": true,
    "enable_network_scanner": false,
    "enable_virustotal": false,
    "enable_crash_reporting": false
  },
  "ui": {
    "theme": "dark"
  }
}
```

### Log Files

**Location**: `%APPDATA%/Sentinel/logs/sentinel.log`

**Retention**: 10 rotating files, 1 MB each

**Contains**: Application lifecycle events, errors, debug info

**Samples**:
```
2025-01-15 10:30:45 [INFO] app.application: Application started
2025-01-15 10:30:46 [DEBUG] app.core.logging_setup: Global exception hooks installed
```

### Database

**Location**: `~/.sentinel/` (SQLite)

**Contains**: Scan results, event history

## Data Retention

- **Settings**: Indefinite (until user resets)
- **Logs**: 10 MB rolling buffer (oldest files deleted when exceeded)
- **Crash reports** (Sentry): 30 days (depends on Sentry's retention policy)
- **File scans** (VirusTotal): None stored locally; VirusTotal's privacy policy applies

## Security

- **File permissions**: 0600 (readable only by you) on Unix-like systems
- **Encryption**: Not encrypted at rest (recommend full-disk encryption for sensitive systems)
- **In-transit**: HTTPS for VirusTotal and Sentry (if enabled)

## Your Rights

- **Access**: All data is human-readable JSON/logs on your computer
- **Deletion**: Delete `%APPDATA%/Sentinel/` or `~/.local/share/sentinel/` to remove all data
- **Control**: Use `--reset-settings` CLI flag or delete `settings.json` manually
- **Portability**: Settings are standard JSON; logs are text; easily exported

## Third-Party Services

### VirusTotal

- **Website**: https://www.virustotal.com
- **Privacy**: https://www.virustotal.com/gui/privacy
- **Data**: File hashes and content when you manually scan

### Sentry

- **Website**: https://sentry.io
- **Privacy**: https://sentry.io/privacy/
- **Data**: Crash stack traces and system info

### Nmap

- **Website**: https://nmap.org
- **Data**: Network topology (runs locally, no external upload)

## Changes to This Policy

We may update this policy. Changes will be reflected in CHANGELOG.md and tagged releases.

**Last updated**: November 2025

## Questions?

For privacy inquiries, please open a [GitHub Issue](https://github.com/mahmoudbadr238/graduationp/issues) or contact security@example.com.
