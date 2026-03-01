"""Comprehensive test of YARA, file sandbox (exe), and URL sandbox."""
import sys, traceback
sys.path.insert(0, r"d:\graduationp")

lines = []
def log(msg):
    lines.append(str(msg))

# ========================================
# TEST 1: YARA
# ========================================
log("=== YARA TEST ===")
try:
    import yara
    log(f"[YARA] Imported OK: {yara.YARA_VERSION}")
except ImportError as e:
    log(f"[YARA] ImportError: {e}")
except OSError as e:
    log(f"[YARA] OSError (DLL missing): {e}")
except Exception as e:
    log(f"[YARA] {type(e).__name__}: {e}")

# Check what YARA rules exist
from pathlib import Path
rules_dir = Path(r"d:\graduationp\app\scanning\yara_rules")
if rules_dir.exists():
    yar_files = list(rules_dir.rglob("*.yar"))
    log(f"[YARA] Rules directory exists: {len(yar_files)} rule files")
    for yf in yar_files[:10]:
        log(f"  - {yf.name} ({yf.stat().st_size} bytes)")
else:
    log(f"[YARA] Rules directory NOT found: {rules_dir}")

# Check fallback pattern scanner
try:
    from app.scanning.yara_engine import get_yara_engine, get_pattern_scanner
    engine = get_yara_engine()
    log(f"[YARA] Engine available: {engine.is_available}")
    scanner = get_pattern_scanner()
    test_data = b"powershell -EncodedCommand base64string"
    findings = scanner.scan_data(test_data)
    log(f"[YARA] FallbackPatternScanner works: {len(findings)} findings")
except Exception as e:
    log(f"[YARA] Fallback error: {e}")

# ========================================
# TEST 2: FILE SANDBOX (exe)
# ========================================
log("\n=== FILE SANDBOX TEST ===")
try:
    from app.scanning.integrated_sandbox import IntegratedSandbox
    sb = IntegratedSandbox()
    info = sb.availability()
    log(f"[SANDBOX] Available: {info}")
    
    if info.get("available"):
        # Test with a real exe (use notepad as safe exe)
        import shutil
        notepad_path = shutil.which("notepad.exe")
        log(f"[SANDBOX] Test file: {notepad_path}")
        
        if notepad_path:
            result = sb.run_file(
                notepad_path,
                timeout=5,
                block_network=True,
            )
            log(f"[SANDBOX] Success: {result.success}")
            log(f"[SANDBOX] Error: {result.error}")
            log(f"[SANDBOX] Duration: {result.duration_seconds}s")
            log(f"[SANDBOX] Findings: {len(result.findings)}")
            log(f"[SANDBOX] Processes: {result.processes_spawned}")
            log(f"[SANDBOX] Network: {result.network_connections}")
            log(f"[SANDBOX] Summary: {result.behavior_summary}")
        else:
            log("[SANDBOX] notepad.exe not found")
    else:
        log(f"[SANDBOX] Not available: {info.get('reason')}")
        
except Exception as e:
    log(f"[SANDBOX] ERROR: {e}")
    log(traceback.format_exc())

# ========================================
# TEST 3: URL SANDBOX
# ========================================
log("\n=== URL SANDBOX TEST ===")
try:
    from app.scanning.url_scanner import UrlScanner
    us = UrlScanner()
    log(f"[URL] Scanner created")
    log(f"[URL] Has scan_sandbox: {hasattr(us, 'scan_sandbox')}")
    
    if hasattr(us, 'scan_sandbox'):
        # Check the signature
        import inspect
        sig = inspect.signature(us.scan_sandbox)
        log(f"[URL] scan_sandbox signature: {sig}")
    else:
        log("[URL] scan_sandbox method NOT found - listing all methods:")
        for name in dir(us):
            if not name.startswith("_"):
                log(f"  - {name}")
                
    # Test static scan
    log("[URL] Testing static scan...")
    result = us.scan_static(url="https://example.com", block_private_ips=True, block_downloads=True)
    log(f"[URL] Static result: verdict={result.verdict}, score={result.score}")
    
except Exception as e:
    log(f"[URL] ERROR: {e}")
    log(traceback.format_exc())

log("\n=== ALL TESTS COMPLETE ===")

with open(r"d:\graduationp\_diag.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("Done - see _diag.txt")
