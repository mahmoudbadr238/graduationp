# 🔴 P0 CRITICAL: GPU Manager Package Installation RCE Vulnerability

**Issue Type**: Security - Remote Code Execution (Potential)  
**Severity**: CRITICAL  
**Component**: `app/utils/gpu_manager.py`  
**Lines Affected**: 75-87  
**Status**: 🔴 OPEN - Requires immediate fix before release

---

## Problem Statement

The GPU manager's `auto_install_package()` method accepts a user-controllable package name and passes it directly to `pip install` without validation. This creates a **Dependency Confusion Attack** or **Package Hijacking** vector.

### Vulnerable Code
```python
# app/utils/gpu_manager.py, lines 75-87
@staticmethod
def auto_install_package(package: str) -> bool:
    """Auto-install a package using pip."""
    try:
        __import__(import_name)
        return True
    except ImportError:
        logger.warning(f"Package '{package}' not found")
        try:
            # Attempt auto-install
            logger.info(f"Auto-installing {package}...")
            subprocess.check_call(  # 🔴 VULNERABLE
                [sys.executable, "-m", "pip", "install", package, "--quiet"]
            )
            logger.info(f"✅ Successfully installed {package}")
            return True
        except subprocess.CalledProcessError as e:
            logger.exception(f"❌ Failed to install {package}: {e}")
            return False
```

### Attack Scenario

1. **Dependency Confusion**: Attacker publishes `pynvml-malicious` on PyPI
2. App receives user input or config with `package="pynvml-malicious"`
3. Pip prefers newer version from public PyPI
4. Malicious package executes arbitrary code on user's machine

### Current Call Sites

**File**: `app/utils/gpu_manager.py:94-97` (install_nvidia_stack)
```python
packages = [
    ("nvidia-ml-py", "pynvml"),
    ("py-wmi", "wmi"),
    ("clinfo", "clinfo"),
]
```

These are **hardcoded** ✅, but the method is public and could be called from:
- QML backend (if exposed)
- Config files (if ever made editable)
- Future HTTP APIs

---

## Root Cause

No validation that `package` parameter matches an approved list. The method assumes it's called with trusted package names only, but this is a security-by-obscurity approach.

---

## Impact Assessment

### Likelihood
- **Current**: LOW (only internal callers with hardcoded packages)
- **Future**: MEDIUM (if API becomes public or config-driven)
- **Risk**: HIGH (if exploited, attacker gains user's privilege level)

### Severity Breakdown
| Aspect | Impact |
|--------|--------|
| **Confidentiality** | HIGH - Can read user files, install keylogger |
| **Integrity** | HIGH - Can modify app, inject malware |
| **Availability** | HIGH - Can corrupt system, delete files |
| **Privilege Escalation** | Possible if app runs as admin (would be HIGH) |

### Current Mitigation
- ✅ Only hardcoded packages used
- ✅ App doesn't run as admin by default
- ✅ Pip has signature verification (PyPI + HTTPS)
- ❌ No code-level validation

---

## Steps to Reproduce

### Proof of Concept (Non-destructive)
```python
import subprocess

# Simulate what a future API might do:
user_input = "malicious-package-name"  # From config, network, etc.

# This would execute:
# subprocess.check_call([sys.executable, "-m", "pip", "install", "malicious-package-name"])

# Pip would try to install from PyPI, potentially finding attacker package
```

### Actual Exploit (if exposed to user input)
1. User adds config: `"auto_install_packages": ["pip-exploit"]`
2. App calls `auto_install_package("pip-exploit")`
3. Attacker's PyPI package `pip-exploit` executes during install

---

## Fix: Add Package Whitelist

### Solution

Create an approved packages list and validate all requests:

```python
# app/utils/gpu_manager.py - Add at module level

# ✅ Approved packages for auto-installation
APPROVED_PACKAGES = {
    "pynvml": "nvidia-ml-py",      # NVIDIA GPU monitoring
    "wmi": "py-wmi",                # Windows WMI queries
    "clinfo": "clinfo",             # AMD GPU info (binary)
    "sentry_sdk": "sentry-sdk",    # Crash reporting
}

class GPUManager:
    # ... existing code ...
    
    @staticmethod
    def auto_install_package(package: str) -> bool:
        """
        Auto-install a package using pip.
        
        Args:
            package: Import name (must be in APPROVED_PACKAGES)
            
        Returns:
            bool: True if installed/available, False on error
            
        Raises:
            ValueError: If package not in approved list
        """
        # ✅ VALIDATION: Check against whitelist
        if package not in APPROVED_PACKAGES:
            logger.error(
                f"Package '{package}' not approved for auto-install. "
                f"Approved: {list(APPROVED_PACKAGES.keys())}"
            )
            raise ValueError(f"Unauthorized package: {package}")
        
        try:
            __import__(package)
            return True
        except ImportError:
            logger.warning(f"Package '{package}' not found")
            try:
                # Get the PyPI package name
                pypi_name = APPROVED_PACKAGES[package]
                
                # Attempt auto-install
                logger.info(f"Auto-installing {pypi_name}...")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pypi_name, "--quiet"],
                    timeout=60  # Add timeout (P1 issue fix)
                )
                logger.info(f"✅ Successfully installed {pypi_name}")
                return True
            except subprocess.CalledProcessError as e:
                logger.exception(f"❌ Failed to install {package}: {e}")
                return False
            except subprocess.TimeoutExpired:
                logger.exception(f"❌ Installation timeout for {package}")
                return False
```

### Implementation Checklist

- [ ] Add `APPROVED_PACKAGES` constant at top of `app/utils/gpu_manager.py`
- [ ] Add validation check in `auto_install_package()` method
- [ ] Add `timeout=60` parameter to `subprocess.check_call()` (also fixes P1)
- [ ] Update error message with approved package list
- [ ] Add unit test for validation
- [ ] Add docstring explaining security requirement

### Testing the Fix

```python
# app/tests/test_gpu_manager.py

import pytest
from app.utils.gpu_manager import GPUManager

def test_auto_install_package_validates_whitelist():
    """Verify only approved packages can be installed"""
    with pytest.raises(ValueError, match="Unauthorized package"):
        GPUManager.auto_install_package("malicious-package")
    
    with pytest.raises(ValueError, match="Unauthorized package"):
        GPUManager.auto_install_package("pip-exploit")

def test_auto_install_package_accepts_approved():
    """Verify approved packages pass validation"""
    # Note: Don't actually install in test, just check validation passes
    # Real integration test would be in CI
    from app.utils.gpu_manager import APPROVED_PACKAGES
    assert "pynvml" in APPROVED_PACKAGES
    assert "wmi" in APPROVED_PACKAGES

def test_auto_install_package_timeout():
    """Verify pip install has timeout"""
    # This would need mocking of subprocess.check_call
    # to verify timeout=60 is passed
    pass
```

---

## Alternative Solutions (Rejected)

### 1. Remove auto-install entirely
- ❌ Worse UX (users must manually install)
- ✅ Secure but impractical

### 2. Only allow installation from internal requirements.txt
- ✅ Very secure
- ❌ Less flexible for edge cases
- ❌ Requires vendoring binary packages

### 3. Use subprocess.run() instead of check_call()
- ❌ Doesn't address root cause
- ❌ Only changes error handling, not validation

---

## Validation After Fix

1. **Code Review**: Verify whitelist complete before deploy
2. **Unit Tests**: Run new validation tests
3. **Integration Test**: Verify existing auto-install still works
4. **Negative Test**: Confirm invalid package names are rejected
5. **Smoke Test**: Verify GPU monitoring still initializes

---

## References

- [CWE-427: Uncontrolled Search Path Element](https://cwe.mitre.org/data/definitions/427.html)
- [Dependency Confusion Attacks](https://www.praetorian.com/blog/dependency-confusion-package-manager-attacks/)
- [Python Pip Security Best Practices](https://pip.pypa.io/en/latest/security_model/)

---

## Timeline

- **Immediate**: Fix in next commit (before release)
- **Testing**: Included in release candidate test suite
- **Deployment**: Must be in v1.0.0 release
- **Post-Release**: No backport needed (v0.x not supported)

---

## Sign-Off

**Priority**: 🔴 CRITICAL  
**Fix Effort**: 30 minutes (including tests)  
**Review Effort**: 15 minutes  
**Total Before Release**: 45 minutes  
**Required**: YES - Blocking release  

**By**: Principal Engineer  
**Date**: November 11, 2025
