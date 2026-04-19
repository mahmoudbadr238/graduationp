# Security Policy

## Reporting Security Vulnerabilities

**DO NOT** open public GitHub issues for security vulnerabilities.

### Responsible Disclosure

If you discover a security vulnerability in Sentinel, please email:

**mahmoudbadr238@gmail.com**

**Subject**: `[SECURITY] Vulnerability in Sentinel`

Include:

1. Description of the issue
2. Steps to reproduce
3. Potential impact
4. Affected environment or feature
5. Suggested mitigation, if you have one

### Response Expectations

Sentinel follows a best-effort security response process:

- **Acknowledgement target**: within 5 business days
- **Triage**: as soon as the issue can be reproduced and scoped
- **Fix timing**: depends on severity, exploitability, and maintainer capacity

If the report is valid, the fix may land on `main` before it appears in a tagged
release.

## Supported Versions

| Version | Status |
|---------|--------|
| `main` | Supported |
| Latest tagged release | Best-effort support |
| Older releases / old commits | Not supported |

Only actively maintained code receives security fixes.

## Known Security Considerations

### Admin Privileges

Sentinel may request administrator privileges to access protected Windows data
and security-related features.

Examples include:

- Windows event sources that require elevation
- system-level security visibility
- privileged monitoring and system inspection paths

Without admin rights, the app can still run, but visibility is reduced.

### AI and External Providers

Sentinel can call optional external providers when configured:

- **Groq** via `GROQ_API_KEY`
- **Sentry** via `SENTRY_DSN`

Security implications:

- Cloud-connected features are optional
- Data handling depends on the providers you enable
- `OFFLINE_ONLY=true` should disable external API usage

### Network Scanning (Nmap)

- **Optional**: used only when Nmap is available
- **Locally initiated**: runs from the local machine
- **Separate tool dependency**: keep the Nmap installation updated

### VMware Sandbox Integration

- **Optional**: only active when VMware is configured
- **Sensitive configuration**: guest credentials and VM paths must be kept local
- **Operational risk**: sandbox usage requires careful VM hygiene and snapshot management

### Diagnostics and Local Artifacts

Do not publish or commit:

- `.env`
- API keys
- VMware guest credentials
- diagnostics exports with sensitive machine data
- code signing material

## Code Security Measures

### Dependency and Tooling Checks

- **Bandit** is available for Python security linting
- **pip-audit** is used in CI for dependency auditing
- **Ruff** and **MyPy** are used for general quality and static validation

### Current Validation Commands

```bash
python -m backend --diagnose
python -m pytest backend/tests -q
python -m bandit -s B101 -r backend main.py
python -m ruff check backend main.py scripts
python -m mypy backend main.py --config-file=pyproject.toml
```

### Operational Practices

- Keep optional integrations disabled unless needed
- Avoid logging secrets
- Review external-provider configuration carefully
- Treat sandbox credentials and diagnostic exports as sensitive

## Best Practices for Users

1. Keep the app and its dependencies updated
2. Store secrets in `.env`, not in source files
3. Review diagnostics before sharing them
4. Use least privilege where practical
5. Recheck Nmap and VMware setup after system changes

## Questions?

For security-sensitive issues, use email only.

For non-security bugs or feature requests, use the normal GitHub issue flow.
