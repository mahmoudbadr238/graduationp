# Contributing to Sentinel

Thank you for considering contributing to Sentinel. This guide keeps the older
document style, but the content below is aligned to the current repository
layout and tooling.

## 🤝 Code of Conduct

- Be respectful and direct.
- Keep feedback technical and constructive.
- Focus on reproducibility and clarity.
- Do not publicly disclose security vulnerabilities.

## 🐛 Reporting Bugs

Before opening a bug report, check existing issues and run local diagnostics.

Please include:

- **Clear title** describing the issue
- **Steps to reproduce**
- **Expected behavior** and **actual behavior**
- **Screenshots or logs** if relevant
- **Environment details**
  - Windows version
  - Python version
  - whether the app was elevated
  - whether `GROQ_API_KEY`, Nmap, or VMware were configured

For security issues, follow [../SECURITY.md](../SECURITY.md) instead.

## 💡 Suggesting Enhancements

Enhancement proposals should explain:

- the user problem
- the current limitation
- the proposed behavior
- any expected impact on setup, permissions, or optional integrations

## 🔧 Development Setup

1. **Clone the repository**

```bash
git clone https://github.com/mahmoudbadr238/graduationp.git
cd graduationp
```

2. **Create and activate a virtual environment**

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. **Install dependencies**

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

4. **Create local configuration**

```powershell
Copy-Item .env.example .env
```

5. **Run diagnostics**

```bash
python -m backend --diagnose
```

6. **Run the application**

```bash
python main.py
```

If you need a limited-access development session, you can skip UAC elevation:

```powershell
$env:SKIP_UAC = "1"
python main.py
```

## 📝 Pull Request Process

1. **Branch from `main`**

```bash
git checkout -b feature/amazing-feature
```

2. **Make a focused change**

- Keep unrelated cleanup out of the same PR
- Update docs when setup or behavior changes
- Keep secrets and local config out of commits

3. **Validate your change**

```bash
python -m backend --diagnose
python -m pytest backend/tests -q
python -m ruff check backend main.py scripts
python -m ruff format backend main.py scripts --check
python -m mypy backend main.py --config-file=pyproject.toml
```

If you changed security-sensitive behavior, also run:

```bash
python -m bandit -s B101 -r backend main.py
```

4. **Commit clearly**

```bash
git add <files>
git commit -m "Docs: Update current README and contributing guide"
```

5. **Push your branch**

```bash
git push origin feature/amazing-feature
```

6. **Open a Pull Request**

Include:

- what changed
- why it changed
- how it was validated
- screenshots for UI changes if helpful

## 🎯 Code Quality Standards

Sentinel has local Ruff, mypy, Bandit, and pytest tooling configured. The full-repo Ruff and mypy baselines are not currently clean, so record those results honestly and treat touched-code cleanup separately unless CI is updated to require a clean baseline.

### Pre-commit Hooks

Install hooks if you plan to contribute regularly:

```bash
pip install pre-commit
pre-commit install
```

Run them manually:

```bash
pre-commit run --all-files
```

### Linting with Ruff

```bash
python -m ruff check backend main.py scripts
python -m ruff format backend main.py scripts --check
```

### Type Checking with MyPy

```bash
python -m mypy backend main.py --config-file=pyproject.toml
```

### Test Suite

```bash
python -m pytest backend/tests -q
```

### CI Workflows

The repository currently includes GitHub Actions workflows for:

- quality checks
- build / import verification
- Bandit security scans
- dependency auditing

See `.github/workflows/`.

## 🎨 Code Style Guidelines

### Python

- Follow the existing repository patterns.
- Keep functions and services reasonably scoped.
- Use type hints when practical.
- Prefer targeted changes over broad rewrites.

### QML

- Work inside `frontend/qml/`.
- Reuse existing components where possible.
- Keep pages consistent with `ThemeManager` and current route handling.
- Preserve the current sidebar-driven navigation model in `frontend/qml/main.qml`.

### Current Project Structure

- `backend/api/` - QML-facing services and bridge objects
- `backend/core/` - startup, config, logging, monitoring, notifications
- `backend/engines/` - scanning, AI, sandbox, and file/security engines
- `backend/tests/` - test suite
- `frontend/qml/components/` - reusable UI components
- `frontend/qml/pages/` - application pages
- `frontend/qml/theme/` and `frontend/qml/ui/` - theme and UI helpers

### Adding a New QML Page

1. Create the page in `frontend/qml/pages/`
2. Add it to the appropriate `qmldir` if needed
3. Wire it into `frontend/qml/main.qml`
4. Add or update navigation entry points
5. Validate the route manually in the running app

## ✅ Testing Checklist

Before submitting a PR:

- [ ] The change is scoped and understandable
- [ ] Relevant diagnostics were run
- [ ] Relevant tests were run
- [ ] Ruff was checked for touched Python code, or remaining findings were documented
- [ ] MyPy was run if types or interfaces changed
- [ ] Documentation was updated if behavior changed
- [ ] No secrets or local machine paths were committed unintentionally

## 📚 Resources

- [../README.md](../README.md)
- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)
- [QUICKSTART.md](QUICKSTART.md)
- [api/README_BACKEND.md](api/README_BACKEND.md)
- [sandbox_vmware.md](sandbox_vmware.md)

## 💬 Questions?

Open a GitHub issue for general questions or contributor discussion.

---

Thank you for contributing to Sentinel.
