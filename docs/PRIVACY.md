# Privacy Policy

Sentinel respects your privacy. This document describes what data we collect and how it's used.

## Data Collection

### Data We DO NOT Collect

- **No background cloud uploads by default** – Core monitoring, scanning, and event collection run locally unless you explicitly enable optional cloud-backed AI or crash reporting
- **No user tracking** – No analytics or tracking cookies
- **No browsing history** – We don't monitor or store your activity
- **No automatic file uploads** – All scanning is local unless explicitly configured

### Data We Collect Locally

**Stored on your computer** in Sentinel's platform-native local data paths:
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

#### AI Services (Groq)
- **When**: You request AI-powered security explanations
- **What**: Event descriptions and context
- **How to enable**: Set `GROQ_API_KEY` environment variable
- **Opt-out**: Do not set `GROQ_API_KEY`

#### Nmap (Network Scanning)
- **When**: You manually scan a network (optional feature, disabled by default)
- **What**: Network topology, open ports, services
- **How to enable**: Install Nmap on your system
- **Opt-out**: Do not install Nmap

## Local Storage

### Configuration Files

**Location**: Sentinel stores settings in the platform-native settings store used by Qt `QSettings`:
- Windows: user registry hive under the Sentinel application keys
- Linux: local Qt settings files under the user's home/config directories

**Contains**:
- Theme and font preferences
- Startup and tray behavior preferences
- Monitoring intervals and feature toggles

### Log Files

**Location**:
- Windows: `%APPDATA%\Sentinel\logs\sentinel.log`
- Linux: `$XDG_STATE_HOME/sentinel/logs/sentinel.log`

**Retention**: 10 rotating files, 1 MB each

**Contains**: Application lifecycle events, errors, debug info

**Samples**:
```
2025-01-15 10:30:45 [INFO] app.application: Application started
2025-01-15 10:30:46 [DEBUG] app.core.logging_setup: Global exception hooks installed
```

### Database

**Location**:
- Windows: `%APPDATA%\Sentinel\sentinel.db`
- Linux: `$XDG_DATA_HOME/sentinel/sentinel.db`

Legacy compatibility lookups for older locations such as `~/.sentinel` remain
readable so upgrades do not silently lose local data.

**Contains**: Scan results, event history

## Data Retention

- **Settings**: Indefinite (until user resets)
- **Logs**: 10 MB rolling buffer (oldest files deleted when exceeded)
- **Crash reports** (Sentry): 30 days (depends on Sentry's retention policy)
- **Scan results**: Stored locally in SQLite database

## Security

- **File permissions**: 0600 (readable only by you) on Unix-like systems
- **Encryption**: Not encrypted at rest (recommend full-disk encryption for sensitive systems)
- **In-transit**: HTTPS for AI APIs and Sentry (if enabled)

## Your Rights

- **Access**: All data is human-readable JSON/logs on your computer
- **Deletion**: Delete the Sentinel config/data/state directories for your platform to remove local data
- **Control**: Use `--reset-settings` CLI flag or delete `settings.json` manually
- **Portability**: Settings are standard JSON; logs are text; easily exported

## Third-Party Services

### Groq

- **Website**: https://groq.com
- **Privacy**: https://groq.com/privacy-policy/
- **Data**: Redacted event or scan context when you request AI explanations

### Sentry

- **Website**: https://sentry.io
- **Privacy**: https://sentry.io/privacy/
- **Data**: Crash stack traces and system info

### Nmap

- **Website**: https://nmap.org
- **Data**: Network topology (runs locally, no external upload)

## Changes to This Policy

We may update this policy. Changes will be reflected in CHANGELOG.md and tagged releases.

**Last updated**: April 22, 2026

## Questions?

For privacy inquiries, please open a [GitHub Issue](https://github.com/mahmoudbadr238/graduationp/issues) or contact security@example.com.
