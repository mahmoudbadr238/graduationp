# 🚀 Release Readiness Checklist

**Version**: 1.0.0  
**Date**: November 11, 2025  
**Target**: November 12-13, 2025  

---

## Pre-Release Fixes

### 🔴 P0 Critical (45 minutes)
- [ ] **GPU Package Validation**
  - [ ] Open `app/utils/gpu_manager.py`
  - [ ] Add `APPROVED_PACKAGES` dict at module level
  - [ ] Add validation in `auto_install_package()`
  - [ ] Wrap with timeout handling
  - [ ] Create unit test in `app/tests/test_gpu_manager.py`
  - [ ] Run: `pytest app/tests/test_gpu_manager.py -v`
  - [ ] **Estimated**: 30 min coding + 15 min testing
  - [ ] **Reviewer**: [Assign]
  - [ ] **Status**: 🔴 Not started

---

### 🔴 P1-1: Pip Install Timeout (10 minutes)
- [ ] Open `app/utils/gpu_manager.py` line 82
- [ ] Add `timeout=60` parameter to `subprocess.check_call()`
- [ ] Add `except subprocess.TimeoutExpired` handler
- [ ] Test: `pytest app/tests/test_gpu_manager.py::test_pip_timeout`
- [ ] **Reviewer**: [Assign]
- [ ] **Status**: 🔴 Not started

### 🔴 P1-2: Path API Consistency (20 minutes)
- [ ] Open `app/application.py`
- [ ] Replace all `os.path.dirname/join` with `Path()` API
- [ ] Use `.as_posix()` for cross-platform paths
- [ ] Test Windows: `python main.py` (verify no errors)
- [ ] Test Linux/WSL: Same
- [ ] Verify QML loads: Check console output
- [ ] **Reviewer**: [Assign]
- [ ] **Status**: 🔴 Not started

### 🔴 P1-3: CSV Newline Handling (15 minutes)
- [ ] Search `app/ui/backend_bridge.py` for `csv.writer`
- [ ] Find all `open()` calls for CSV export
- [ ] Add `newline=''` parameter to `open()`
- [ ] Test: Export scan history, verify no blank lines
- [ ] Verify on Windows and Linux
- [ ] **Reviewer**: [Assign]
- [ ] **Status**: 🔴 Not started

### 🔴 P1-4: Admin Features Documentation (20 minutes)
- [ ] Open `SECURITY.md`
- [ ] Add "Features Requiring Admin" table
- [ ] Add "Features Working Without Admin" list
- [ ] Add "Running Without Admin" instructions
- [ ] Update UI with error messages for unavailable features
- [ ] Test: Run without admin, verify error messages
- [ ] **Reviewer**: [Assign]
- [ ] **Status**: 🔴 Not started

### 🔴 P1-5: AppImage Recipe (45 minutes) - *Can defer to v1.0.1 for Windows-only release*
- [ ] Create `scripts/build_appimage.sh`
- [ ] Create `scripts/build_appimage_docker.sh`
- [ ] Update `CONTRIBUTING.md` with Linux build instructions
- [ ] Test build on Ubuntu 22.04 (or use Docker)
- [ ] Verify AppImage runs: `./Sentinel-*.AppImage --diagnose`
- [ ] Test: `--export-diagnostics` flag works
- [ ] **Decision**: [Ship as part of v1.0.0 or defer to v1.0.1?]
- [ ] **Reviewer**: [Assign]
- [ ] **Status**: 🔴 Not started

---

## Testing Phase (30 minutes)

### Smoke Tests
- [ ] Run `pytest app/tests/test_smoke.py -v`
  ```bash
  pytest app/tests/test_smoke.py -v --tb=short
  ```
  - [ ] test_import_app PASSED
  - [ ] test_diagnose_command PASSED
  - [ ] test_export_diagnostics PASSED
  - [ ] test_reset_settings PASSED

### Core Tests
- [ ] Run `pytest app/tests/test_core.py -v`
  ```bash
  pytest app/tests/test_core.py -v --tb=short
  ```
  - [ ] test_config_* PASSED
  - [ ] test_privileges_* PASSED

### Manual Testing (Windows)
- [ ] **Startup**
  - [ ] `python main.py` - app starts without errors
  - [ ] Verify window opens
  - [ ] Check console for no Python warnings
  - [ ] Note startup time (target: <3 seconds)
  
- [ ] **Navigation**
  - [ ] Click through all 7 pages
  - [ ] Verify no crashes
  - [ ] Verify smooth animations
  - [ ] Test Ctrl+1-7 keyboard shortcuts

- [ ] **Features**
  - [ ] System Snapshot - all metrics populated
  - [ ] Event Viewer - loads (if admin)
  - [ ] GPU Monitoring - detects GPU or shows N/A
  - [ ] Network - shows adapters
  - [ ] Settings - can save and restore

- [ ] **CLI Flags**
  - [ ] `python -m app --diagnose` - shows diagnostics
  - [ ] `python -m app --export-diagnostics /tmp/test.json` - creates file
  - [ ] `python -m app --reset-settings` - resets config

- [ ] **Admin Mode**
  - [ ] Run with admin - all features available
  - [ ] Run without admin - degraded features show error messages

### Manual Testing (Linux - WSL if available)
- [ ] Same as Windows above, but in WSL
- [ ] Verify paths work on Linux
- [ ] Verify no Windows-specific crashes

---

## Code Review Phase (30 minutes)

### Security Review
- [ ] No eval/exec remaining: `grep -r "eval\|exec" app/`
- [ ] All subprocess calls have timeouts
- [ ] No shell=True in subprocess calls
- [ ] No secrets in code (only env vars)
- [ ] GPU package whitelist implemented

### Code Quality
- [ ] Ruff passes: `python -m ruff check .`
- [ ] Bandit passes: `python -m bandit -r app/ -ll`
- [ ] No new warnings in imports
- [ ] Path APIs standardized
- [ ] Exception handling specific

### Test Coverage
- [ ] Run coverage report: `pytest --cov=app --cov-report=html`
- [ ] Check `htmlcov/index.html` - verify target modules covered
- [ ] Minimum 40% coverage (current), target 60%

---

## Packaging Phase (30 minutes)

### PyInstaller Windows Build
- [ ] Run: `pyinstaller sentinel.spec`
- [ ] Verify `dist/Sentinel.exe` created (~45-50 MB)
- [ ] Test exe: `dist\Sentinel.exe --diagnose`
- [ ] Verify exe size reasonable
- [ ] Verify QML assets packaged

### AppImage Linux Build (if included)
- [ ] Run: `bash scripts/build_appimage.sh x86_64`
- [ ] Verify `dist/Sentinel-*.AppImage` created
- [ ] Test: `chmod +x Sentinel-*.AppImage && ./Sentinel-*.AppImage --diagnose`

### Artifacts Preparation
- [ ] Create release folder: `release/v1.0.0/`
- [ ] Copy Windows exe: `release/v1.0.0/Sentinel-1.0.0-x86_64.exe`
- [ ] Copy AppImage (if ready): `release/v1.0.0/Sentinel-1.0.0-x86_64.AppImage`
- [ ] Copy source zip
- [ ] Create checksums: `sha256sum *`

---

## Documentation Phase (15 minutes)

### Update Files
- [ ] Update `CHANGELOG.md` with all P0/P1 fixes in v1.0.0 section
- [ ] Update `README.md` version badge (1.0.0, not beta)
- [ ] Update `SECURITY.md` with admin features table
- [ ] Create `RELEASE_NOTES.md` for this version
  ```markdown
  # v1.0.0 Release Notes
  
  ## 🎉 Initial Release - Production Hardening Complete
  
  ### Security Fixes
  - GPU manager package validation (prevent dependency confusion)
  - Pip install timeout (prevent hangs)
  
  ### Bug Fixes
  - Path API consistency (Windows/Linux parity)
  - CSV export newline handling (Windows blank rows)
  - Admin features documentation
  
  ### Known Limitations
  - Linux users: Use WSL2 for GUI testing; native AppImage in v1.0.1
  - Event Viewer: Windows only (requires admin)
  - GPU monitoring: NVIDIA, AMD, Intel supported; others gracefully degrade
  
  ### Installation
  [See README.md](README.md)
  
  ### Thank You
  Special thanks to all contributors and testers.
  ```

### Version Update
- [ ] Verify `app/__version__.py` has `__version__ = "1.0.0"`
- [ ] Verify `sentinel.spec` doesn't have version override
- [ ] Verify `qml/main.qml` title shows v1.0.0

---

## Release Phase (30 minutes)

### Git Preparation
- [ ] Stage all changes: `git add .`
- [ ] Review diff: `git diff --cached --stat`
- [ ] Verify only intended files changed
- [ ] Create commit message:
  ```
  chore: v1.0.0 production hardening & release
  
  🔒 Security
  - Add GPU package installation whitelist (CWE-427 prevention)
  - Add pip install timeout (network hang prevention)
  
  🐛 Bug Fixes
  - Standardize path API (os.path → Path)
  - Fix CSV export newlines (Windows)
  - Document admin privilege requirements
  
  📦 Packaging
  - Add AppImage build recipe
  - Update PyInstaller spec verification
  
  📚 Documentation
  - Clarify admin-gated features
  - Update SECURITY.md and CONTRIBUTING.md
  - Create RELEASE_NOTES.md
  
  Tests
  - All smoke tests passing
  - Security audit complete
  - Cross-platform verification done
  ```
- [ ] Commit: `git commit -m "..."`

### GitHub Release
- [ ] Go to https://github.com/mahmoudbadr238/graduationp/releases
- [ ] Click "Draft a new release"
- [ ] Tag: `v1.0.0`
- [ ] Release title: `Sentinel v1.0.0 - Production Ready 🎉`
- [ ] Copy content from `RELEASE_NOTES.md` into description
- [ ] Upload artifacts:
  - [ ] `Sentinel-1.0.0-x86_64.exe`
  - [ ] `Sentinel-1.0.0-x86_64.AppImage` (if ready)
  - [ ] `checksums.txt` (SHA256 sums)
  - [ ] `Source code (zip)`
- [ ] Click "Publish release"

### Announcement
- [ ] Update GitHub project status
- [ ] Add issue/PR to highlight fixes
- [ ] Send release notes to stakeholders

---

## Post-Release (15 minutes)

### Verification
- [ ] Visit GitHub releases page, verify v1.0.0 shows
- [ ] Download and test exe
- [ ] Verify checksums: `sha256sum -c checksums.txt`
- [ ] Test on clean Windows VM (optional, for peace of mind)

### Feedback Collection
- [ ] Create issues for v1.0.1 items (P2 medium priority)
- [ ] Add v1.0.1 milestone to GitHub
- [ ] Create v1.0.1 project board
- [ ] Document known issues in README

---

## Sign-Off Checklist

Before marking as RELEASED, verify:

### Security ✅
- [ ] P0 GPU manager fix verified
- [ ] Ruff audit passed (no new issues)
- [ ] Bandit audit passed
- [ ] No eval/exec in codebase
- [ ] All subprocess calls sandboxed

### Functionality ✅
- [ ] All smoke tests pass
- [ ] Windows manual testing complete
- [ ] Linux manual testing complete (WSL)
- [ ] CLI flags work (--diagnose, --export-diagnostics, --reset-settings)
- [ ] All 7 pages navigate correctly

### Packaging ✅
- [ ] PyInstaller exe builds and runs
- [ ] exe size reasonable (~45-50 MB)
- [ ] QML assets included
- [ ] AppImage builds (if included)

### Documentation ✅
- [ ] CHANGELOG updated
- [ ] README updated
- [ ] SECURITY.md updated
- [ ] RELEASE_NOTES.md created
- [ ] All links in docs working

### Release ✅
- [ ] Git commit created
- [ ] GitHub release created with artifacts
- [ ] Checksums verified
- [ ] No new issues found in download testing

---

## Role Assignments

| Role | Name | Checklist Item | Status |
|------|------|---|---|
| **P0 Fixer** | [Assign] | GPU package validation | 🔴 |
| **P1 Fixer** | [Assign] | P1-1 through P1-4 | 🔴 |
| **AppImage Dev** | [Assign] | P1-5 (optional) | 🔴 |
| **Tester (Windows)** | [Assign] | Manual testing | 🔴 |
| **Tester (Linux)** | [Assign] | WSL testing | 🔴 |
| **Code Reviewer** | [Assign] | Security/quality review | 🔴 |
| **Release Manager** | [Assign] | Git/GitHub release | 🔴 |

---

## Timeline Summary

```
Day 1 (Today):
├─ 08:00 - QA Review Complete ✅
├─ 09:00 - Assign P0/P1 fixes
├─ 09:15 - Parallel: P0, P1-1,2,3,4 fixes (1.5 hours)
├─ 10:45 - Code review (30 min)
├─ 11:15 - Testing phase (30 min)
└─ 11:45 - Packaging & PyInstaller build (30 min)

Day 2 (Tomorrow):
├─ 08:00 - Final verification (15 min)
├─ 08:15 - Git commit (10 min)
├─ 08:25 - GitHub release (10 min)
├─ 08:35 - Post-release verification (10 min)
└─ 09:00 - v1.0.0 RELEASED 🎉
```

**Total Time**: ~4 hours development + 2 hours testing/packaging = 6 hours  
**Recommendation**: Start immediately for same-day release

---

## Success Criteria

✅ Release is **SUCCESSFUL** if:
- [ ] All P0 issues fixed
- [ ] All P1 issues fixed
- [ ] All smoke tests passing
- [ ] GitHub release published
- [ ] exe downloads and runs
- [ ] No new security issues found
- [ ] Documentation updated

🔴 Release is **BLOCKED** if:
- [ ] Any P0 issue not fixed
- [ ] Security audit fails
- [ ] Smoke tests fail
- [ ] exe doesn't start
- [ ] More than 2 P1 issues remain (negotiate with stakeholders)

---

## Questions/Escalations

For blockers or questions:
1. Contact Principal Engineer (this review author)
2. Escalate to Product Lead
3. If security issue: Escalate immediately

---

**Prepared by**: Principal Engineer & QA Lead  
**Date**: November 11, 2025  
**Status**: Ready for team assignment  
**Target Release**: November 12-13, 2025

**Next Action**: Assign fixes to team members and begin P0 fix immediately.
