"""
refactor_project.py — One-shot migration script for Sentinel project restructuring.

Restructures the flat app/ package into a modular, enterprise-grade layout:

    backend/              ← app/  (Python backend)
        core/             ← app/core/
        config/           ← app/config/
        utils/            ← app/utils/
        infra/            ← app/infra/
        api/              ← app/ui/          (QML bridge layer)
        engines/          ← NEW grouping
            ai/           ← app/ai/
            scanning/     ← app/scanning/
            sandbox/      ← app/sandbox/
            sandbox_vmware/ ← app/sandbox_vmware/
            scancenter/   ← app/scancenter/
            intel/        ← app/intel/
            gpu/          ← app/gpu/
            filefunction/ ← app/filefunction/
        tests/            ← app/tests/
    frontend/
        qml/              ← qml/            (QML UI)
    payload/
        sandbox_agent/    ← tools/sandbox_agent/
        url_detonator/    ← tools/url_detonator/

Also rewrites:
  - All `from app.xxx` absolute imports  → `from backend.xxx` (with mapping)
  - All `from ..xxx` cross-package relative imports → absolute `from backend.xxx`
  - Relative imports in application.py  → updated for new sub-package paths
  - QML path references in application.py → frontend/qml/
  - `from tools.xxx` imports → `from payload.xxx`

Usage:
    python refactor_project.py              # dry-run (shows plan, changes nothing)
    python refactor_project.py --execute    # actually perform the migration
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ─── Package mapping ───────────────────────────────────────────────────────
# old sub-package path (relative to app/) → new path (relative to backend/)
SUBPACKAGE_MAP = {
    "core":           "core",
    "config":         "config",
    "utils":          "utils",
    "infra":          "infra",
    "ui":             "api",
    "ai":             "engines/ai",
    "scanning":       "engines/scanning",
    "sandbox":        "engines/sandbox",
    "sandbox_vmware": "engines/sandbox_vmware",
    "scancenter":     "engines/scancenter",
    "intel":          "engines/intel",
    "gpu":            "engines/gpu",
    "filefunction":   "engines/filefunction",
    "tests":          "tests",
}

# Root-level files in app/ that move to backend/
ROOT_MODULE_FILES = [
    "__main__.py",
    "__version__.py",
    "application.py",
]

# ─── Absolute-import rewrite map ──────────────────────────────────────────
# Built so that the most specific prefix is tried first.

def _build_abs_import_map():
    """Build ordered list of (old_prefix, new_prefix) for absolute imports."""
    pairs = []
    for old_sub, new_sub in SUBPACKAGE_MAP.items():
        old_pkg = f"app.{old_sub}"
        new_pkg = "backend." + new_sub.replace("/", ".")
        pairs.append((old_pkg, new_pkg))
    # Root-level modules (e.g. app.__version__, app.application)
    for fname in ROOT_MODULE_FILES:
        if fname.endswith(".py") and fname != "__init__.py":
            mod = fname[:-3]
            pairs.append((f"app.{mod}", f"backend.{mod}"))
    # Catch-all: bare `app` → `backend`
    pairs.append(("app", "backend"))
    # Sort longest first so `app.scanning` is tried before `app`
    pairs.sort(key=lambda p: -len(p[0]))
    return pairs

ABS_IMPORT_MAP = _build_abs_import_map()

# tools → payload mapping
TOOLS_IMPORT_MAP = [
    ("tools.url_detonator", "payload.url_detonator"),
    ("tools.sandbox_agent", "payload.sandbox_agent"),
    ("tools", "payload"),
]

# ─── Reverse map: new dotted package → old dotted package ─────────────────

def _build_reverse_map():
    m = {}
    for old_sub, new_sub in SUBPACKAGE_MAP.items():
        new_pkg = "backend." + new_sub.replace("/", ".")
        old_pkg = f"app.{old_sub}"
        m[new_pkg] = old_pkg
    m["backend"] = "app"
    return m

REVERSE_MAP = _build_reverse_map()

# ─── Helpers ──────────────────────────────────────────────────────────────

def _old_abs_to_new_abs(old_dotted: str) -> str:
    """Convert an old absolute import path (e.g. 'app.scanning.url_scanner')
    to the new path (e.g. 'backend.engines.scanning.url_scanner')."""
    for old_prefix, new_prefix in ABS_IMPORT_MAP:
        if old_dotted == old_prefix:
            return new_prefix
        if old_dotted.startswith(old_prefix + "."):
            return new_prefix + old_dotted[len(old_prefix):]
    return old_dotted

def _tools_to_payload(dotted: str) -> str:
    """Convert tools.xxx import to payload.xxx."""
    for old, new in TOOLS_IMPORT_MAP:
        if dotted == old:
            return new
        if dotted.startswith(old + "."):
            return new + dotted[len(old):]
    return dotted

def _get_old_package(new_file: Path) -> str:
    """Given a file's NEW path under backend/, return its OLD dotted package."""
    try:
        rel = new_file.relative_to(ROOT / "backend")
    except ValueError:
        return ""
    parent_parts = rel.parent.parts
    if not parent_parts:
        return "app"
    new_pkg = "backend." + ".".join(parent_parts)
    # Find longest matching prefix in REVERSE_MAP
    parts_list = list(parent_parts)
    for length in range(len(parts_list), 0, -1):
        candidate = "backend." + ".".join(parts_list[:length])
        if candidate in REVERSE_MAP:
            old_base = REVERSE_MAP[candidate]
            suffix_parts = parts_list[length:]
            if suffix_parts:
                return old_base + "." + ".".join(suffix_parts)
            return old_base
    return "app"

def _resolve_relative(file_old_pkg: str, dots: int, module_path: str) -> str:
    """Resolve a relative import to an absolute old-style path.

    file_old_pkg: e.g. 'app.ai'
    dots: number of leading dots (1 = current pkg, 2 = parent, etc.)
    module_path: e.g. 'scanning.scanner_engine'
    Returns: e.g. 'app.scanning.scanner_engine'
    """
    parts = file_old_pkg.split(".")
    levels_up = dots - 1
    if levels_up > len(parts):
        return ""  # invalid
    base_parts = parts[:len(parts) - levels_up]
    base = ".".join(base_parts)
    if module_path:
        return f"{base}.{module_path}"
    return base

# Regex for Python import lines
_RE_ABS_IMPORT_FROM = re.compile(
    r'^(\s*)(from\s+)(app(?:\.\w+)*)((?:\s+import\s+.*))'
)
_RE_ABS_IMPORT_BARE = re.compile(
    r'^(\s*)(import\s+)(app(?:\.\w+)*)(.*)'
)
_RE_TOOLS_IMPORT_FROM = re.compile(
    r'^(\s*)(from\s+)(tools(?:\.\w+)*)((?:\s+import\s+.*))'
)
_RE_TOOLS_IMPORT_BARE = re.compile(
    r'^(\s*)(import\s+)(tools(?:\.\w+)*)(.*)'
)
_RE_REL_IMPORT = re.compile(
    r'^(\s*)(from\s+)(\.{2,})(\w[\w.]*)?(\s+import\s+.*)'
)

def rewrite_line(line: str, file_old_pkg: str, is_in_engines: bool) -> str:
    """Rewrite a single line's imports if needed."""
    # 1. Cross-package relative imports (.. or more dots)
    m = _RE_REL_IMPORT.match(line)
    if m:
        indent, from_kw, dots_str, module_path, import_tail = m.groups()
        dots = len(dots_str)
        module_path = module_path or ""
        old_abs = _resolve_relative(file_old_pkg, dots, module_path)
        if old_abs:
            new_abs = _old_abs_to_new_abs(old_abs)
            return f"{indent}{from_kw}{new_abs}{import_tail}\n"

    # 2. Absolute `from app.xxx import yyy`
    m = _RE_ABS_IMPORT_FROM.match(line)
    if m:
        indent, from_kw, pkg, tail = m.groups()
        new_pkg = _old_abs_to_new_abs(pkg)
        return f"{indent}{from_kw}{new_pkg}{tail}\n"

    # 3. Absolute `import app.xxx`
    m = _RE_ABS_IMPORT_BARE.match(line)
    if m:
        indent, import_kw, pkg, tail = m.groups()
        new_pkg = _old_abs_to_new_abs(pkg)
        return f"{indent}{import_kw}{new_pkg}{tail}\n"

    # 4. `from tools.xxx import yyy`
    m = _RE_TOOLS_IMPORT_FROM.match(line)
    if m:
        indent, from_kw, pkg, tail = m.groups()
        new_pkg = _tools_to_payload(pkg)
        return f"{indent}{from_kw}{new_pkg}{tail}\n"

    # 5. `import tools.xxx`
    m = _RE_TOOLS_IMPORT_BARE.match(line)
    if m:
        indent, import_kw, pkg, tail = m.groups()
        new_pkg = _tools_to_payload(pkg)
        return f"{indent}{import_kw}{new_pkg}{tail}\n"

    # 6. String-literal references: "-m", "app" in subprocess calls
    if '"-m", "app"' in line:
        line = line.replace('"-m", "app"', '"-m", "backend"')
    if "'-m', 'app'" in line:
        line = line.replace("'-m', 'app'", "'-m', 'backend'")

    return line

def rewrite_application_py_relative(line: str) -> str:
    """Special handler for application.py single-dot relative imports.

    application.py sits directly in backend/, so `.xxx` means `backend.xxx`.
    We need to update paths for sub-packages that moved:
        .ui.xxx           → .api.xxx
        .sandbox_vmware   → .engines.sandbox_vmware
        .filefunction.xxx → .engines.filefunction.xxx
    """
    # Single-dot relative imports: from .xxx import yyy
    m = re.match(r'^(\s*)(from\s+)(\.)(\w[\w.]*)?(\s+import\s+.*)', line)
    if not m:
        return line
    indent, from_kw, dot, module_path, import_tail = m.groups()
    if not module_path:
        return line

    # Mapping for single-dot relative imports in application.py
    app_rel_map = [
        ("ui.",             "api."),
        ("sandbox_vmware",  "engines.sandbox_vmware"),
        ("filefunction.",   "engines.filefunction."),
        ("ai.",             "engines.ai."),
        ("scanning.",       "engines.scanning."),
        ("sandbox.",        "engines.sandbox."),
        ("scancenter.",     "engines.scancenter."),
        ("intel.",          "engines.intel."),
        ("gpu.",            "engines.gpu."),
    ]
    for old_prefix, new_prefix in app_rel_map:
        bare_old = old_prefix.rstrip(".")
        if module_path == bare_old:
            # Exact match: e.g. from .sandbox_vmware import X
            new_module = new_prefix.rstrip(".")
            return f"{indent}{from_kw}.{new_module}{import_tail}\n"
        if module_path.startswith(old_prefix):
            # Prefix match: e.g. from .ui.backend_bridge import X
            new_module = new_prefix + module_path[len(old_prefix):]
            return f"{indent}{from_kw}.{new_module}{import_tail}\n"
    return line


# ─── File / directory operations ──────────────────────────────────────────

def plan_moves():
    """Return list of (src, dst) Path pairs for all moves."""
    moves = []
    app_dir = ROOT / "app"

    # 1. Sub-packages
    for old_sub, new_sub in SUBPACKAGE_MAP.items():
        src = app_dir / old_sub
        dst = ROOT / "backend" / new_sub.replace("/", os.sep)
        if src.exists():
            moves.append((src, dst))

    # 2. Root-level files in app/
    for fname in ROOT_MODULE_FILES:
        src = app_dir / fname
        dst = ROOT / "backend" / fname
        if src.exists():
            moves.append((src, dst))

    # 3. qml/ → frontend/qml/
    qml_dir = ROOT / "qml"
    if qml_dir.exists():
        moves.append((qml_dir, ROOT / "frontend" / "qml"))

    # 4. tools/ sub-dirs → payload/
    for sub in ("sandbox_agent", "url_detonator"):
        src = ROOT / "tools" / sub
        dst = ROOT / "payload" / sub
        if src.exists():
            moves.append((src, dst))

    return moves


def create_init_files(execute: bool):
    """Create __init__.py files for new intermediate packages."""
    new_inits = [
        (ROOT / "backend" / "__init__.py",
         '"""Sentinel endpoint security backend."""\n'),
        (ROOT / "backend" / "engines" / "__init__.py",
         '"""Sentinel engine sub-packages (AI, scanning, sandbox, etc.)."""\n'),
        (ROOT / "frontend" / "__init__.py",
         '"""Sentinel frontend package."""\n'),
        (ROOT / "payload" / "__init__.py",
         '"""Sentinel standalone payload / agent package."""\n'),
    ]
    for path, content in new_inits:
        if path.exists():
            continue
        if execute:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"  [CREATE] {path.relative_to(ROOT)}")
        else:
            print(f"  [CREATE] {path.relative_to(ROOT)}  (new __init__.py)")


def execute_moves(moves, execute: bool):
    """Move files/directories according to the plan."""
    for src, dst in moves:
        rel_src = src.relative_to(ROOT)
        rel_dst = dst.relative_to(ROOT)
        if execute:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"  [MOVE] {rel_src}  →  {rel_dst}")
        else:
            print(f"  [MOVE] {rel_src}  →  {rel_dst}")


def rewrite_imports_in_tree(execute: bool):
    """Walk all .py files and rewrite imports."""
    changed_files = []
    search_dirs = [
        ROOT / "backend",
        ROOT / "frontend",
        ROOT / "payload",
    ]
    # In dry-run mode, also scan app/ to show what would change
    if not execute:
        search_dirs.append(ROOT / "app")

    # Also rewrite root-level scripts
    extra_files = [
        ROOT / "main.py",
        ROOT / "_diag.py",
    ]
    # Scripts that reference app.*
    scripts_dir = ROOT / "scripts"

    py_files = list(extra_files)
    for d in search_dirs:
        if d.exists():
            py_files.extend(d.rglob("*.py"))
    if scripts_dir.exists():
        py_files.extend(scripts_dir.rglob("*.py"))

    for py_file in py_files:
        if not py_file.exists():
            continue
        # Skip archive/build dirs
        rel_str = str(py_file.relative_to(ROOT))
        if any(skip in rel_str for skip in ("_cleanup_archive", "archive",
                                             "build", ".venv", "__pycache__",
                                             "refactor_project")):
            continue
        try:
            original = py_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        lines = original.splitlines(keepends=True)
        new_lines = []

        # For dry-run on app/ files, simulate the old package
        try:
            rel = py_file.relative_to(ROOT / "app")
            file_old_pkg = "app." + ".".join(rel.parent.parts) if rel.parent.parts else "app"
            is_application_py = py_file.name == "application.py" and not rel.parent.parts
        except ValueError:
            try:
                file_old_pkg = _get_old_package(py_file)
            except Exception:
                file_old_pkg = ""
            is_application_py = (py_file.name == "application.py"
                                 and py_file.parent == ROOT / "backend")

        is_in_engines = False
        try:
            py_file.relative_to(ROOT / "backend" / "engines")
            is_in_engines = True
        except ValueError:
            # In dry-run, engines subpackages are still under app/
            if not execute and file_old_pkg:
                engine_pkgs = ("app.ai", "app.scanning", "app.sandbox",
                               "app.sandbox_vmware", "app.scancenter",
                               "app.intel", "app.gpu", "app.filefunction")
                is_in_engines = any(file_old_pkg == ep or file_old_pkg.startswith(ep + ".")
                                    for ep in engine_pkgs)

        for line in lines:
            new_line = rewrite_line(line, file_old_pkg, is_in_engines)
            # Extra pass for application.py single-dot relative imports
            if is_application_py:
                new_line = rewrite_application_py_relative(new_line)
            new_lines.append(new_line)

        new_text = "".join(new_lines)
        if new_text != original:
            rel = py_file.relative_to(ROOT)
            if execute:
                py_file.write_text(new_text, encoding="utf-8")
                print(f"  [REWRITE] {rel}")
            else:
                print(f"  [REWRITE] {rel}")
            changed_files.append(py_file)

    return changed_files


def patch_qml_paths(execute: bool):
    """Update QML path references in application.py for frontend/qml/."""
    app_py = ROOT / "backend" / "application.py"
    if not app_py.exists():
        print("  [SKIP] backend/application.py not found")
        return

    text = app_py.read_text(encoding="utf-8")
    original = text

    # _setup_paths: qml_path = os.path.join(workspace_root, "qml")
    text = text.replace(
        'os.path.join(workspace_root, "qml")',
        'os.path.join(workspace_root, "frontend", "qml")',
    )

    # _create_qml_engine: os.path.join(os.getcwd(), "qml", "main.qml")
    text = text.replace(
        'os.path.join(os.getcwd(), "qml", "main.qml")',
        'os.path.join(os.getcwd(), "frontend", "qml", "main.qml")',
    )

    if text != original:
        if execute:
            app_py.write_text(text, encoding="utf-8")
            print("  [PATCH] backend/application.py  (QML paths → frontend/qml/)")
        else:
            print("  [PATCH] backend/application.py  (QML paths → frontend/qml/)")


def cleanup_empty_dirs(execute: bool):
    """Remove empty app/ and tools/ directories after migration."""
    for dirname in ("app", "tools"):
        d = ROOT / dirname
        if not d.exists():
            continue
        # Check if it still has meaningful content
        remaining = [p for p in d.rglob("*") if p.is_file()]
        if remaining:
            print(f"  [KEEP] {dirname}/  ({len(remaining)} files remaining)")
        else:
            if execute:
                shutil.rmtree(str(d), ignore_errors=True)
                print(f"  [REMOVE] {dirname}/  (empty after migration)")
            else:
                print(f"  [REMOVE] {dirname}/  (would be empty after migration)")


def update_pyproject_toml(execute: bool):
    """Update pyproject.toml if it references the old 'app' package."""
    for toml_path in [ROOT / "pyproject.toml", ROOT / "config" / "pyproject.toml"]:
        if not toml_path.exists():
            continue
        text = toml_path.read_text(encoding="utf-8")
        original = text
        # Common patterns in pyproject.toml
        text = text.replace('packages = ["app"]', 'packages = ["backend", "frontend", "payload"]')
        text = text.replace("packages = ['app']", "packages = ['backend', 'frontend', 'payload']")
        text = text.replace('where = ["app"]', 'where = ["."]')
        if text != original:
            rel = toml_path.relative_to(ROOT)
            if execute:
                toml_path.write_text(text, encoding="utf-8")
                print(f"  [PATCH] {rel}")
            else:
                print(f"  [PATCH] {rel}  (package references)")


def update_spec_files(execute: bool):
    """Update .spec / build files that reference old paths."""
    for spec in ROOT.glob("*.spec"):
        text = spec.read_text(encoding="utf-8")
        original = text
        text = text.replace("'app'", "'backend'")
        text = text.replace('"app"', '"backend"')
        text = text.replace("'qml'", "'frontend/qml'")
        text = text.replace('"qml"', '"frontend/qml"')
        if text != original:
            if execute:
                spec.write_text(text, encoding="utf-8")
                print(f"  [PATCH] {spec.name}")
            else:
                print(f"  [PATCH] {spec.name}  (build paths)")


# ─── Verification ─────────────────────────────────────────────────────────

def verify_no_old_imports():
    """Check that no Python files still reference the old import paths."""
    issues = []
    for py_file in ROOT.rglob("*.py"):
        # Skip _cleanup_archive, archive, build dirs
        rel = str(py_file.relative_to(ROOT))
        if any(skip in rel for skip in ("_cleanup_archive", "archive", "build",
                                         ".venv", "__pycache__", "refactor_project")):
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.match(r'from\s+app\.', stripped) or re.match(r'import\s+app\.', stripped):
                issues.append((py_file.relative_to(ROOT), i, stripped))
            if re.match(r'from\s+tools\.', stripped) or re.match(r'import\s+tools\.', stripped):
                issues.append((py_file.relative_to(ROOT), i, stripped))
    return issues


# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sentinel project restructuring migration script"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the migration (default is dry-run)",
    )
    args = parser.parse_args()
    execute = args.execute

    if execute:
        print("=" * 60)
        print("  EXECUTING MIGRATION (this will modify your project)")
        print("=" * 60)
    else:
        print("=" * 60)
        print("  DRY RUN — showing planned changes (nothing modified)")
        print("  Re-run with --execute to apply")
        print("=" * 60)

    # Pre-flight check
    if not (ROOT / "app").exists():
        print("\n[ERROR] app/ directory not found. Already migrated?")
        sys.exit(1)
    if (ROOT / "backend").exists():
        print("\n[ERROR] backend/ already exists. Remove it first or resolve manually.")
        sys.exit(1)

    # Phase 1: Plan moves
    moves = plan_moves()
    print(f"\n── Phase 1: Move {len(moves)} items ──")
    execute_moves(moves, execute)

    # Phase 2: Create __init__.py for new intermediate packages
    print("\n── Phase 2: Create __init__.py files ──")
    create_init_files(execute)

    # Phase 3: Rewrite Python imports
    print("\n── Phase 3: Rewrite Python imports ──")
    changed = rewrite_imports_in_tree(execute)
    print(f"  ({len(changed)} files with import changes)")

    # Phase 4: Patch QML path references
    print("\n── Phase 4: Patch QML paths in application.py ──")
    patch_qml_paths(execute)

    # Phase 5: Update build/config files
    print("\n── Phase 5: Update build & config references ──")
    update_pyproject_toml(execute)
    update_spec_files(execute)

    # Phase 6: Clean up empty old directories
    print("\n── Phase 6: Clean up old directories ──")
    cleanup_empty_dirs(execute)

    # Phase 7: Verify (only after execution)
    if execute:
        print("\n── Phase 7: Verification ──")
        issues = verify_no_old_imports()
        if issues:
            print(f"  [WARNING] {len(issues)} files still reference old imports:")
            for path, lineno, line in issues[:20]:
                print(f"    {path}:{lineno}  {line}")
            if len(issues) > 20:
                print(f"    ... and {len(issues) - 20} more")
        else:
            print("  [OK] No stale `from app.*` or `from tools.*` imports found")

    # Summary
    print("\n" + "=" * 60)
    if execute:
        print("  Migration complete!")
        print()
        print("  New structure:")
        print("    backend/         — Python backend (core, api, engines, ...)")
        print("    frontend/qml/    — QML UI files")
        print("    payload/         — Standalone agent payloads")
        print()
        print("  Next steps:")
        print("    1. Run: python main.py          (verify app launches)")
        print("    2. Run: python -m pytest backend/tests/  (verify tests)")
        print("    3. Delete app/ and tools/ if they still exist")
        print("    4. Update .github/copilot-instructions.md")
        print("    5. git add -A && git commit -m 'refactor: restructure to backend/frontend/payload'")
    else:
        print("  Dry run complete. Re-run with --execute to apply.")
    print("=" * 60)


if __name__ == "__main__":
    main()
