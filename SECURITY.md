# Security Policy

## Reporting Security Vulnerabilities

**DO NOT** open public GitHub issues for security vulnerabilities.

### Responsible Disclosure

If you discover a security vulnerability in Sentinel, please email:

**security@example.com**

**Subject**: `[SECURITY] Vulnerability in Sentinel`

Include:
1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact
4. Suggested fix (if available)

We will:
- Acknowledge receipt within 48 hours
- Investigate and confirm the issue
- Develop and test a fix
- Release a patched version
- Credit you in the release notes (unless you prefer to remain anonymous)

### Security Response Timeline

- **P1 (Critical)**: Patch released within 24-48 hours
- **P2 (High)**: Patch released within 1 week
- **P3 (Medium)**: Patch released within 2 weeks
- **P4 (Low)**: Fixed in next regular release

## Supported Versions

| Version | Status            | Release Date | End of Life |
|---------|------------------|--------------|-------------|
| 1.0.x   | Current (Stable) | Jan 2025     | Jan 2027    |
| 0.x.x   | Legacy           | Pre-release  | Ended       |

Only the latest version receives security patches.

## Known Security Considerations

### Admin Privileges

Sentinel requests administrator privileges to access:
- Windows Security Event logs
- Firewall status
- TPM and Secure Boot status
- Disk encryption (BitLocker)

**Why**: These features require elevated access on Windows. Without admin rights, security monitoring is degraded but the app still functions.

### GPU Monitoring

- NVIDIA GPU monitoring uses NVIDIA's official pynvml library
- Power management queries may fail on some hardware (gracefully degraded)
- No data is sent to NVIDIA (runs locally)

### Network Scanning (Nmap)

- **Optional**: Only runs if Nmap is installed and explicitly enabled
- **Local only**: Scans do not leave your network without explicit user action
- **Process isolation**: Nmap runs as a subprocess with timeout protection

### File Scanning (VirusTotal)

- **Requires API key**: Only works if `VT_API_KEY` environment variable is set
- **User initiated**: Never automatically scans files
- **Hash and content sent**: Both file hash and content sent to VirusTotal for analysis
- **Privacy**: Reviewed file hashes are uploaded; refer to VirusTotal's privacy policy

### Crash Reporting (Sentry)

- **Requires DSN**: Only enabled if `SENTRY_DSN` environment variable is set
- **Crash-only**: Stack traces sent only on unhandled exceptions
- **Opt-in**: User must explicitly configure for crash reporting

## Code Security Measures

### Dependency Management

- **pip-audit**: Scans dependencies for known vulnerabilities
- **Lockfile**: `requirements.lock` pins exact versions
- **Minimal deps**: Only essential libraries (PySide6, psutil, pynvml)

### Code Quality

- **Ruff linter**: Enforces PEP 8 and security-focused rules
- **Bandit**: Scans for common security anti-patterns
- **Type hints**: Python 3.11+ with mypy compatibility
- **No eval/exec**: Strict prohibition on dynamic code execution

### Process Isolation

- GPU telemetry runs in separate process (crashproof)
- Event reading runs in background worker threads
- UI thread never blocks on I/O or system calls

### Exception Handling

- Broad exception catching only in boundary code (Windows API, GPU queries)
- Specific exception types caught in hot paths
- No secrets logged (API keys, certificates filtered from logs)

## Best Practices for Users

1. **Keep updated**: Update to latest version promptly
2. **Audit settings**: Review `~/.sentinel/settings.json` or `%APPDATA%/Sentinel/settings.json`
3. **Manage API keys**: Store `VT_API_KEY` in `.env`, never in code or commit history
4. **Logs**: Periodically delete old logs to prevent accumulation
5. **Permissions**: Run with minimum required privileges (not always feasible on Windows)

## Security Tests

- **Unit tests**: `pytest -q app/tests/`
- **Security lint**: `bandit -q -r app main.py`
- **Dependency audit**: `pip-audit`
- **Style & types**: `ruff check . && mypy .`

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for security patches and fixes per release.

## Questions?

For security concerns or questions, please open a [GitHub Discussion](https://github.com/mahmoudbadr238/graduationp/discussions/categories/security) or email security@example.com.
