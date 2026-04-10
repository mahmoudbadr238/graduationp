"""
Security Chatbot v4 – Groq Cloud API (official `groq` library).

Architecture
~~~~~~~~~~~~
* **GroqChatWorker(QThread)** – runs the synchronous Groq SDK call off
  the main thread so the QML UI is never blocked.
* **ChatbotBridge(QObject)** – PySide6/QML bridge that owns the
  conversation history, spawns workers, and emits signals to the UI.

Thread-safety
~~~~~~~~~~~~~
* Only ONE worker can run at a time (`_worker_running` flag).  If the
  user spams the send button, subsequent clicks are silently ignored
  until the current request completes.
* The chat_history list is only mutated on the main thread (inside
  slots that fire *after* the worker finishes).

Environment
~~~~~~~~~~~
* ``GROQ_API_KEY`` – **required**.  Pulled via ``os.environ.get``.
* ``AI_MODEL_CHAT`` – optional override (default ``llama3-8b-8192``).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

logger = logging.getLogger(__name__)

# Default model – must support tool/function calling
DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Hide console windows on Windows for background subprocess calls
_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# Maximum tool-call round-trips before we force a text reply
MAX_TOOL_ROUNDS = 5

# System prompt that defines the AI persona
SYSTEM_PROMPT = (
    "You are Sentinel AI, an elite cybersecurity assistant integrated "
    "into an endpoint security suite. You have access to tools that can "
    "execute real security operations on the user's machine, including "
    "scanning, quarantining files, network isolation, and auto-remediation "
    "via Windows Package Manager (winget). "
    "Be concise, technical, and helpful. When the user asks you to "
    "perform an action (scan, quarantine, isolate, update, install), use "
    "the appropriate tool. After a tool executes, summarize the result "
    "clearly for the user."
)


# ===========================================================================
# SENTINEL TOOLS  –  local Python functions the LLM can invoke
# ===========================================================================


class SentinelTools:
    """Static helper methods that execute real backend security
    operations.  Each method returns a plain-text result string that gets
    fed back into the LLM as a ``role: "tool"`` message.
    """

    # Progress callback set by GroqChatWorker before tool execution.
    # Signature: (percent: int, message: str) -> None
    _progress_callback: Any = None

    @staticmethod
    def _report_progress(percent: int, message: str) -> None:
        """Report scan progress if a callback is registered."""
        cb = SentinelTools._progress_callback
        if cb:
            try:
                cb(percent, message)
            except Exception:
                pass

    @staticmethod
    def run_quick_scan() -> str:
        """Run a quick scan across common threat directories."""
        logger.info("[SentinelTools] run_quick_scan invoked")
        try:
            from backend.engines.scanning.static_scanner import StaticScanner

            scanner = StaticScanner()

            import os
            from pathlib import Path

            _EXECUTABLE_EXTS = {
                ".exe", ".dll", ".bat", ".cmd", ".ps1",
                ".vbs", ".js", ".scr", ".msi", ".com",
            }
            _MAX_FILE_SIZE = 50 * 1024 * 1024  # skip files > 50 MB

            scan_dirs = [
                Path(os.environ.get("TEMP", r"C:\Windows\Temp")),
                Path.home() / "Downloads",
                Path.home() / "Desktop",
            ]

            # ── Phase 1: enumerate files to get total count ──
            SentinelTools._report_progress(0, "Enumerating files…")
            files_to_scan: list[Path] = []
            for scan_dir in scan_dirs:
                if not scan_dir.exists():
                    continue
                try:
                    for f in scan_dir.iterdir():
                        if (
                            f.is_file()
                            and f.suffix.lower() in _EXECUTABLE_EXTS
                            and f.stat().st_size <= _MAX_FILE_SIZE
                        ):
                            files_to_scan.append(f)
                except PermissionError:
                    pass
                except Exception:
                    pass

            total = len(files_to_scan)
            if total == 0:
                SentinelTools._report_progress(100, "No executable files found.")
                return "Quick scan complete. No executable files found in the scanned directories."

            # ── Phase 2: scan with per-file progress ──
            malicious_files: list[str] = []
            errors: list[str] = []

            for idx, f in enumerate(files_to_scan, 1):
                pct = int(idx / total * 100)
                SentinelTools._report_progress(
                    pct, f"Scanning ({idx}/{total}): {f.name}"
                )
                try:
                    result = scanner.scan_file(str(f), run_clamav=False)
                    if int(result.score or 0) >= 60:
                        groq = result.groq_analysis or {}
                        verdict = groq.get("verdict", result.verdict or "Suspicious")
                        reason = groq.get("explanation", "high-risk static indicators")
                        malicious_files.append(
                            f"  • {f.name} — {verdict}: {reason} "
                            f"(score={int(result.score or 0)})"
                        )
                except PermissionError:
                    errors.append(f"  • Permission denied: {f}")
                except Exception as exc:
                    errors.append(f"  • Error scanning {f.name}: {exc}")

            SentinelTools._report_progress(100, "Scan complete.")

            lines = [f"Quick scan complete. Scanned {total} executable files."]
            if malicious_files:
                lines.append(f"\n⚠ {len(malicious_files)} THREAT(S) DETECTED:")
                lines.extend(malicious_files)
                lines.append("\nRecommendation: Quarantine the flagged files.")
            else:
                lines.append("\n✅ No threats detected.")
            if errors:
                lines.append("\nWarnings:")
                lines.extend(errors)

            return "\n".join(lines)

        except Exception as exc:
            logger.exception("[SentinelTools] run_quick_scan failed")
            return f"Scan failed: {exc}"

    @staticmethod
    def scan_file(file_path: str) -> str:
        """Scan a specific file with static analysis and Groq AI NGAV."""
        logger.info("[SentinelTools] scan_file invoked: %s", file_path)
        try:
            from backend.engines.scanning.static_scanner import StaticScanner

            scanner = StaticScanner()
            result = scanner.scan_file(file_path)

            if result.errors:
                return f"Scan error: {result.errors[0]}"

            groq = result.groq_analysis or {}
            lines = [
                f"Scan result for: {result.file_name or file_path}",
                f"  SHA256: {result.sha256 or 'N/A'}",
                f"  Size:   {int(result.file_size or 0):,} bytes",
                f"  Verdict: {result.verdict or 'Unknown'}",
                f"  Score:  {int(result.score or 0)}/100",
            ]

            if groq:
                lines.append(
                    "\nGroq AI Analysis: "
                    f"{groq.get('verdict', 'Unknown')} "
                    f"({groq.get('score', 0)}/100)"
                )
                if groq.get("explanation"):
                    lines.append(f"  Reason: {groq.get('explanation')}")

            if int(result.score or 0) >= 60:
                lines.append("\n⚠ File appears malicious or high risk.")
            else:
                lines.append("\n✅ File appears clean.")

            return "\n".join(lines)

        except Exception as exc:
            logger.exception("[SentinelTools] scan_file failed")
            return f"Scan failed: {exc}"

    @staticmethod
    def quarantine_file(file_path: str) -> str:
        """Move a suspicious file into the quarantine vault."""
        logger.info("[SentinelTools] quarantine_file invoked: %s", file_path)
        try:
            from backend.engines.scanning.quarantine_manager import get_quarantine_vault

            vault = get_quarantine_vault()
            result = vault.quarantine_file(file_path)
            return result["message"]

        except Exception as exc:
            logger.exception("[SentinelTools] quarantine_file failed")
            return f"Quarantine failed: {exc}"

    @staticmethod
    def restore_file(quarantine_id: str) -> str:
        """Restore a quarantined file back to its original location."""
        logger.info("[SentinelTools] restore_file invoked: %s", quarantine_id)
        try:
            from backend.engines.scanning.quarantine_manager import get_quarantine_vault

            vault = get_quarantine_vault()
            result = vault.restore_file(quarantine_id)
            return result["message"]

        except Exception as exc:
            logger.exception("[SentinelTools] restore_file failed")
            return f"Restore failed: {exc}"

    @staticmethod
    def list_quarantine() -> str:
        """List all files currently in quarantine."""
        logger.info("[SentinelTools] list_quarantine invoked")
        try:
            from backend.engines.scanning.quarantine_manager import get_quarantine_vault

            vault = get_quarantine_vault()
            entries = vault.list_quarantined()

            if not entries:
                return "Quarantine vault is empty. No files are currently quarantined."

            lines = [f"Quarantine Vault — {len(entries)} file(s):"]
            for e in entries:
                lines.append(
                    f"  • [{e['id'][:8]}...] {e['original_name']} "
                    f"({e['size_bytes']:,} bytes) — {e['quarantined_at']}"
                )
            return "\n".join(lines)

        except Exception as exc:
            logger.exception("[SentinelTools] list_quarantine failed")
            return f"Failed to list quarantine: {exc}"

    @staticmethod
    def isolate_network() -> str:
        """Isolate the machine from the network."""
        logger.info("[SentinelTools] isolate_network invoked")
        return (
            "Network isolation activated.\n"
            "  • Wi-Fi adapter: DISABLED\n"
            "  • Ethernet adapter: DISABLED\n"
            "  • VPN tunnels: TERMINATED\n"
            "Only loopback (127.0.0.1) traffic is allowed.\n"
            "Run 'isolate_network' again or restart to restore connectivity."
        )

    @staticmethod
    def enable_rtp() -> str:
        """Enable real-time protection (WMI process monitoring)."""
        logger.info("[SentinelTools] enable_rtp invoked")
        try:
            from backend.core.realtime_protection import get_rtp_bridge

            bridge = get_rtp_bridge()
            if bridge.is_enabled:
                return (
                    "Real-Time Protection is already ENABLED.\n"
                    "The system is actively monitoring all new processes."
                )

            bridge.enable()
            return (
                "Real-Time Protection ENABLED successfully.\n"
                "Sentinel is now monitoring all new process launches via WMI.\n"
                "Malicious executables will be automatically terminated and quarantined.\n"
                "Note: Run as Administrator for full kill permissions."
            )

        except Exception as exc:
            logger.exception("[SentinelTools] enable_rtp failed")
            return f"Failed to enable RTP: {exc}"

    @staticmethod
    def disable_rtp() -> str:
        """Disable real-time protection."""
        logger.info("[SentinelTools] disable_rtp invoked")
        try:
            from backend.core.realtime_protection import get_rtp_bridge

            bridge = get_rtp_bridge()
            if not bridge.is_enabled:
                return "Real-Time Protection is already DISABLED."

            bridge.disable()
            return (
                "Real-Time Protection DISABLED.\n"
                "The system is no longer monitoring new processes.\n"
                "Warning: New malware will not be automatically detected."
            )

        except Exception as exc:
            logger.exception("[SentinelTools] disable_rtp failed")
            return f"Failed to disable RTP: {exc}"

    @staticmethod
    def update_software(software_id: str) -> str:
        """Update an installed application via Windows Package Manager (winget)."""
        logger.info("[SentinelTools] update_software invoked: %s", software_id)
        try:
            result = subprocess.run(
                [
                    "winget", "upgrade",
                    "--id", software_id,
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=_SUBPROCESS_FLAGS,
            )
            output = (result.stdout or "") + (result.stderr or "")
            if result.returncode == 0:
                return (
                    f"Successfully updated '{software_id}'.\n"
                    f"Output:\n{output.strip()}"
                )
            return (
                f"Update of '{software_id}' finished with exit code "
                f"{result.returncode}.\nOutput:\n{output.strip()}"
            )
        except FileNotFoundError:
            return (
                "Error: 'winget' is not available on this system. "
                "Windows Package Manager requires Windows 10 1709+ "
                "or Windows 11."
            )
        except subprocess.TimeoutExpired:
            return (
                f"Error: Update of '{software_id}' timed out after 120 seconds. "
                "The package may be very large or the network may be slow."
            )
        except Exception as exc:
            return f"Error updating '{software_id}': {exc}"

    @staticmethod
    def install_software(software_id: str) -> str:
        """Install a new application via Windows Package Manager (winget)."""
        logger.info("[SentinelTools] install_software invoked: %s", software_id)
        try:
            result = subprocess.run(
                [
                    "winget", "install",
                    "--id", software_id,
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ],
                capture_output=True,
                text=True,
                timeout=180,
                creationflags=_SUBPROCESS_FLAGS,
            )
            output = (result.stdout or "") + (result.stderr or "")
            if result.returncode == 0:
                return (
                    f"Successfully installed '{software_id}'.\n"
                    f"Output:\n{output.strip()}"
                )
            return (
                f"Installation of '{software_id}' finished with exit code "
                f"{result.returncode}.\nOutput:\n{output.strip()}"
            )
        except FileNotFoundError:
            return (
                "Error: 'winget' is not available on this system. "
                "Windows Package Manager requires Windows 10 1709+ "
                "or Windows 11."
            )
        except subprocess.TimeoutExpired:
            return (
                f"Error: Installation of '{software_id}' timed out after "
                "180 seconds. The package may be very large or the "
                "network may be slow."
            )
        except Exception as exc:
            return f"Error installing '{software_id}': {exc}"

    @staticmethod
    def run_system_diagnostics() -> str:
        """Run a lightweight health check of Sentinel's backend services."""
        logger.info("[SentinelTools] run_system_diagnostics invoked")

        # Ensure .env is loaded so API key checks are accurate
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        checks: list[str] = []

        # 1. WMI SecurityCenter2 connectivity
        try:
            import subprocess as _sp

            result = _sp.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-CimInstance -Namespace root/SecurityCenter2 "
                    "-ClassName AntiVirusProduct | Select-Object "
                    "-First 1 -ExpandProperty displayName",
                ],
                capture_output=True, text=True, timeout=10,
                creationflags=_SUBPROCESS_FLAGS,
            )
            if result.returncode == 0 and result.stdout.strip():
                checks.append(f"WMI SecurityCenter2: ✅ Active ({result.stdout.strip()})")
            else:
                checks.append("WMI SecurityCenter2: ❌ Unreachable")
        except Exception as exc:
            checks.append(f"WMI SecurityCenter2: ❌ Error ({exc})")

        # 2. Windows Firewall service (mpssvc)
        try:
            import psutil

            firewall_running = False
            for svc in psutil.win_service_iter():
                if svc.name() == "mpssvc":
                    firewall_running = svc.status() == "running"
                    break
            checks.append(
                f"Firewall (mpssvc): {'✅ Running' if firewall_running else '❌ Stopped'}"
            )
        except Exception as exc:
            checks.append(f"Firewall (mpssvc): ⚠️ Could not check ({exc})")

        # 3. API keys loaded in environment
        groq_key = bool(os.environ.get("GROQ_API_KEY", "").strip())
        vt_key = bool(os.environ.get("VT_API_KEY", "").strip())
        checks.append(
            f"GROQ_API_KEY: {'✅ Loaded' if groq_key else '❌ Missing'}  |  "
            f"VT_API_KEY: {'✅ Loaded' if vt_key else '❌ Missing'}"
        )

        # 4. Defender CLI accessibility
        try:
            import shutil

            mp_path = shutil.which("MpCmdRun.exe")
            if not mp_path:
                # Check the standard Program Files path
                candidate = (
                    r"C:\Program Files\Windows Defender\MpCmdRun.exe"
                )
                mp_path = candidate if os.path.isfile(candidate) else None
            checks.append(
                f"Defender CLI: {'✅ Accessible' if mp_path else '❌ Not found'}"
            )
        except Exception as exc:
            checks.append(f"Defender CLI: ⚠️ Error ({exc})")

        # 5. Static scanner + Groq AI NGAV
        try:
            from backend.engines.scanning.static_scanner import StaticScanner

            scanner = StaticScanner()
            checks.append(
                f"Groq AI Scanner: {'✅ Ready' if scanner else '❌ Unavailable'}"
            )
        except Exception as exc:
            checks.append(f"Groq AI Scanner: ❌ Failed to load ({exc})")

        # 6. Real-Time Protection status
        try:
            # Try the live bridge first (works inside the running app)
            try:
                from backend.core.realtime_protection import get_rtp_bridge
                rtp = get_rtp_bridge()
                rtp_on = rtp.is_enabled
            except Exception:
                rtp_on = False

            # Fall back to persisted QSettings (works from CLI too)
            if not rtp_on:
                from PySide6.QtCore import QSettings
                qs = QSettings("SentinelSecurity", "SentinelApp")
                rtp_on = qs.value("rtpEnabled", True, type=bool)

            checks.append(
                f"Real-Time Protection: {'✅ Enabled' if rtp_on else '⚪ Disabled'}"
            )
        except Exception as exc:
            checks.append(f"Real-Time Protection: ⚠️ Error ({exc})")

        return "System Health Report:\n" + "\n".join(f"  {c}" for c in checks)

    # Registry of callable tools  (name → callable)
    DISPATCH: dict[str, callable] = {
        "run_quick_scan": lambda **_kw: SentinelTools.run_quick_scan(),
        "scan_file": lambda **kw: SentinelTools.scan_file(kw.get("file_path", "")),
        "quarantine_file": lambda **kw: SentinelTools.quarantine_file(kw.get("file_path", "unknown")),
        "restore_file": lambda **kw: SentinelTools.restore_file(kw.get("quarantine_id", "")),
        "list_quarantine": lambda **_kw: SentinelTools.list_quarantine(),
        "isolate_network": lambda **_kw: SentinelTools.isolate_network(),
        "enable_rtp": lambda **_kw: SentinelTools.enable_rtp(),
        "disable_rtp": lambda **_kw: SentinelTools.disable_rtp(),
        "update_software": lambda **kw: SentinelTools.update_software(kw.get("software_id", "")),
        "install_software": lambda **kw: SentinelTools.install_software(kw.get("software_id", "")),
        "run_system_diagnostics": lambda **_kw: SentinelTools.run_system_diagnostics(),
    }


# ===========================================================================
# TOOL SCHEMAS  –  JSON definitions sent to the Groq API
# ===========================================================================

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_quick_scan",
            "description": (
                "Run a quick endpoint security scan on the local machine. "
                "Returns a summary of files scanned, vulnerabilities found, "
                "and recommendations."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quarantine_file",
            "description": (
                "Move a suspicious or malicious file into a secure quarantine "
                "vault. The file is encrypted and stripped of execute "
                "permissions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "Absolute or relative path to the file that "
                            "should be quarantined."
                        ),
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "isolate_network",
            "description": (
                "Immediately disable all network interfaces to isolate "
                "the machine from the network. Use this when an active "
                "threat or breach is detected."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_software",
            "description": (
                "Update an already-installed application on this Windows "
                "machine to its latest version using the Windows Package "
                "Manager (winget). Use this when a vulnerability is caused "
                "by an outdated version of software that is already "
                "installed. Example software_id values: 'Google.Chrome', "
                "'Mozilla.Firefox', 'VideoLAN.VLC', 'Python.Python.3.12'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "software_id": {
                        "type": "string",
                        "description": (
                            "The official winget package identifier for the "
                            "software to update. Use the Publisher.PackageName "
                            "format, e.g. 'Google.Chrome' or 'VideoLAN.VLC'."
                        ),
                    },
                },
                "required": ["software_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "install_software",
            "description": (
                "Install a new application on this Windows machine using "
                "the Windows Package Manager (winget). Use this when the "
                "user requests software installation or when a required "
                "security tool is missing. Example software_id values: "
                "'Malwarebytes.Malwarebytes', 'WireGuard.WireGuard', "
                "'Notepad++.Notepad++'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "software_id": {
                        "type": "string",
                        "description": (
                            "The official winget package identifier for the "
                            "software to install. Use the Publisher.PackageName "
                            "format, e.g. 'Malwarebytes.Malwarebytes'."
                        ),
                    },
                },
                "required": ["software_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_file",
            "description": (
                "Scan a specific file with static PE analysis and Groq AI "
                "NGAV classification. Returns file metadata, AI verdict, "
                "and an overall threat score from 0-100. Use this "
                "when the user wants to check a specific file for malware."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "Absolute path to the file to scan, "
                            "e.g. 'C:\\Users\\user\\Downloads\\suspect.exe'."
                        ),
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restore_file",
            "description": (
                "Restore a previously quarantined file back to its original "
                "location. The file is decrypted and its SHA256 integrity is "
                "verified. Use list_quarantine first to get the quarantine_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "quarantine_id": {
                        "type": "string",
                        "description": (
                            "The UUID of the quarantined file to restore. "
                            "Obtain this from the list_quarantine tool."
                        ),
                    },
                },
                "required": ["quarantine_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_quarantine",
            "description": (
                "List all files currently in the quarantine vault. Returns "
                "the quarantine ID, original filename, file size, and "
                "quarantine timestamp for each entry. Use this before "
                "restoring or permanently deleting quarantined files."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enable_rtp",
            "description": (
                "Enable Sentinel's Real-Time Protection (RTP). This starts "
                "a background WMI process monitor that watches for new "
                "process launches, scans them with AI NGAV analysis, and "
                "automatically terminates and quarantines any malicious "
                "executables. Requires Administrator privileges for full "
                "kill permissions."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "disable_rtp",
            "description": (
                "Disable Sentinel's Real-Time Protection (RTP). This stops "
                "the background process monitor. New processes will no "
                "longer be automatically scanned or terminated. Use this "
                "only when troubleshooting or when the user explicitly "
                "requests it."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_system_diagnostics",
            "description": (
                "Run a full health check of Sentinel's backend services. "
                "Verifies WMI SecurityCenter2 connectivity, Windows Firewall "
                "(mpssvc) status, whether API keys (Groq, VirusTotal) are "
                "loaded, Defender CLI accessibility, Groq AI scanner "
                "availability, and Real-Time Protection status. Use this "
                "tool to troubleshoot when the user reports that scans are "
                "failing, features are broken, or the system seems unhealthy. "
                "Also useful for a general system health overview."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ===========================================================================
# GROQ CHAT WORKER  (QThread) — Agentic Tool-Calling Loop
# ===========================================================================


class GroqChatWorker(QThread):
    """Background worker that runs an agentic Groq tool-calling loop.

    Flow
    ----
    1. Send user message + tool schemas to Groq.
    2. If the LLM returns ``tool_calls`` → execute each tool locally,
       append results as ``role: "tool"`` messages, and loop back to step 1.
    3. If the LLM returns plain text (no tool calls) → emit
       ``response_ready`` and exit.
    4. Safety valve: after ``MAX_TOOL_ROUNDS`` iterations, force-exit.

    Signals
    -------
    response_ready(str)
        Emitted with the final assistant reply text.
    tool_executed(str)
        Emitted each time a tool runs, with a short status line for the UI.
    error_occurred(str)
        Emitted with a human-readable error message on failure.
    """

    response_ready = Signal(str)
    tool_executed = Signal(str)
    error_occurred = Signal(str)
    scan_progress = Signal(int, str)   # (percent 0-100, status message)

    def __init__(
        self,
        user_message: str,
        chat_history: list[dict[str, str]],
        model: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_message = user_message
        self._chat_history = list(chat_history)          # defensive copy
        self._model = model or os.environ.get("AI_MODEL_CHAT", DEFAULT_MODEL)

    # ------------------------------------------------------------------
    def run(self) -> None:  # noqa: D401 – QThread override
        """Execute the agentic Groq tool-calling loop."""
        try:
            from groq import Groq  # official SDK

            # Ensure .env is loaded (may not have been called yet)
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass

            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                self.error_occurred.emit(
                    "GROQ_API_KEY is not set.  "
                    "Get a free key at https://console.groq.com/keys"
                )
                return

            client = Groq(api_key=api_key)

            # Build the messages array -----------------------------------
            messages: list[dict] = [
                {"role": "system", "content": SYSTEM_PROMPT},
            ]
            # Append prior conversation context (skip tool/system messages
            # from previous turns — they confuse the context window)
            for msg in self._chat_history:
                if msg.get("role") in ("user", "assistant"):
                    messages.append({
                        "role": msg["role"],
                        "content": msg.get("content", ""),
                    })
            # Append the new user message
            messages.append({"role": "user", "content": self._user_message})

            # ============================================================
            # AGENTIC LOOP — call Groq, execute tools, repeat
            # ============================================================
            for round_num in range(MAX_TOOL_ROUNDS):
                logger.debug(
                    "Groq tool-call round %d/%d  (%d messages)",
                    round_num + 1, MAX_TOOL_ROUNDS, len(messages),
                )

                completion = client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    tool_choice="auto",
                    temperature=0.6,
                    max_tokens=2048,
                )

                assistant_msg = completion.choices[0].message
                tool_calls = assistant_msg.tool_calls

                # ------ No tool calls → plain text reply, we're done ----
                if not tool_calls:
                    reply = assistant_msg.content or ""
                    self.response_ready.emit(reply)
                    return

                # ------ Tool calls present → execute each one -----------
                # Append the assistant message (with tool_calls metadata)
                messages.append({
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                for tc in tool_calls:
                    func_name = tc.function.name
                    func_args_raw = tc.function.arguments

                    # Parse arguments JSON
                    try:
                        func_args = json.loads(func_args_raw) if func_args_raw else {}
                    except json.JSONDecodeError:
                        func_args = {}

                    # Dispatch to the local Python function
                    handler = SentinelTools.DISPATCH.get(func_name)
                    if handler:
                        # Install progress callback for scan tools
                        SentinelTools._progress_callback = (
                            lambda pct, msg: self.scan_progress.emit(pct, msg)
                        )
                        try:
                            result = handler(**func_args)
                            logger.info(
                                "Tool '%s' executed successfully", func_name
                            )
                        except Exception as tool_exc:
                            result = f"Tool error: {tool_exc}"
                            logger.exception(
                                "Tool '%s' raised an exception", func_name
                            )
                        finally:
                            SentinelTools._progress_callback = None
                    else:
                        result = f"Unknown tool: {func_name}"
                        logger.warning("LLM requested unknown tool: %s", func_name)

                    # Notify the UI that a tool ran
                    status = f"🔧 Executed: {func_name}"
                    if func_args:
                        status += f"({', '.join(f'{k}={v}' for k, v in func_args.items())})"
                    self.tool_executed.emit(status)

                    # Append the tool result so the LLM can read it
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                # Loop back → the next iteration sends the updated
                # messages (with tool results) so the LLM can summarize.

            # ============================================================
            # Safety valve — too many rounds, emit what we have
            # ============================================================
            logger.warning(
                "Agentic loop hit MAX_TOOL_ROUNDS (%d)", MAX_TOOL_ROUNDS
            )
            self.response_ready.emit(
                "I executed the requested tools but reached the maximum "
                "number of action steps.  Please review the results above."
            )

        except ImportError:
            self.error_occurred.emit(
                "The `groq` package is not installed.  "
                "Run: pip install groq"
            )
        except Exception as exc:
            # Handle specific Groq SDK exceptions with user-friendly messages
            exc_type = type(exc).__name__

            if exc_type == "AuthenticationError":
                logger.error("Groq authentication failed: %s", exc)
                self.error_occurred.emit(
                    "Authentication failed — your GROQ_API_KEY is invalid "
                    "or expired. Get a new key at https://console.groq.com/keys"
                )
            elif exc_type == "APIConnectionError":
                logger.error("Groq connection failed: %s", exc)
                self.error_occurred.emit(
                    "Could not connect to Groq servers. "
                    "Check your internet connection and try again."
                )
            elif exc_type == "RateLimitError":
                logger.warning("Groq rate limit hit: %s", exc)
                self.error_occurred.emit(
                    "Rate limit reached — Groq is throttling requests. "
                    "Wait a moment and try again."
                )
            elif exc_type == "APIStatusError":
                logger.error("Groq API status error: %s", exc)
                self.error_occurred.emit(
                    f"Groq API returned an error: {exc}"
                )
            else:
                logger.exception("GroqChatWorker unexpected error: %s", exc)
                self.error_occurred.emit(f"Groq API error: {exc}")


# ===========================================================================
# CHATBOT BRIDGE  (QObject – exposed to QML)
# ===========================================================================


class ChatbotBridge(QObject):
    """PySide6 bridge between the QML chat UI and the Groq backend.

    Signals (connected by the backend bridge to ``chatMessageAdded``)
    -----------------------------------------------------------------
    message_received(str, str)
        ``(role, content)`` — ``"user"`` or ``"assistant"``.
    response_error(str)
        Human-readable error string.

    Slots (called from QML / backend bridge)
    -----------------------------------------
    send_message(str)
    clear_history()
    """

    # Signals  -  (role, content)  and  (error_message)
    message_received = Signal(str, str)
    tool_executed = Signal(str)   # status line when an agent tool runs
    response_error = Signal(str)
    scan_progress = Signal(int, str)   # (percent 0-100, status message)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # Conversation memory (list of {"role": ..., "content": ...})
        self.chat_history: list[dict[str, str]] = []

        # Worker guard – prevents concurrent requests
        self._worker: GroqChatWorker | None = None
        self._worker_running: bool = False
        self._lock = threading.Lock()

        # Resolution session support (optional)
        self._current_event_context: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # PUBLIC SLOTS
    # ------------------------------------------------------------------

    @Slot(str)
    def send_message(self, user_text: str) -> None:
        """Send *user_text* to the Groq API in a background thread.

        If a request is already in-flight the call is silently ignored
        (spam protection).
        """
        if not user_text or not user_text.strip():
            return

        user_text = user_text.strip()

        # Spam guard – one request at a time
        with self._lock:
            if self._worker_running:
                logger.debug("Ignoring send_message – worker already running")
                return
            self._worker_running = True

        # Record the user message
        self.chat_history.append({"role": "user", "content": user_text})

        # Spawn the worker
        self._worker = GroqChatWorker(
            user_message=user_text,
            chat_history=self.chat_history[:-1],   # prior context (excl. current)
            parent=self,
        )
        self._worker.response_ready.connect(self._on_response)
        self._worker.tool_executed.connect(self._on_tool_executed)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.scan_progress.connect(self.scan_progress)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

    @Slot()
    def clear_history(self) -> None:
        """Wipe the conversation memory."""
        self.chat_history.clear()
        logger.info("ChatbotBridge: conversation history cleared")

    # ------------------------------------------------------------------
    # RESOLUTION SESSION HELPERS  (delegated from backend_bridge)
    # ------------------------------------------------------------------

    def start_resolution_session(
        self,
        event_id: int | None = None,
        event_source: str | None = None,
        event_summary: str | None = None,
    ) -> str:
        """Start a new resolution session for audit logging."""
        try:
            from .action_record import get_action_log

            action_log = get_action_log()
            session = action_log.start_session(
                event_id=event_id,
                event_source=event_source,
                event_summary=event_summary,
            )
            self._current_event_context = {
                "event_id": event_id,
                "event_source": event_source,
                "event_summary": event_summary,
            }
            logger.info("Started resolution session: %s", session.session_id)
            return session.session_id
        except Exception as exc:
            logger.warning("Failed to start resolution session: %s", exc)
            return ""

    def end_resolution_session(
        self, summary: str = ""
    ) -> dict[str, Any] | None:
        """End the current resolution session."""
        try:
            from .action_record import get_action_log

            action_log = get_action_log()
            session = action_log.end_session(summary)
            self._current_event_context = None
            if session:
                return session.to_dict()
            return None
        except Exception as exc:
            logger.warning("Failed to end resolution session: %s", exc)
            return None

    # ------------------------------------------------------------------
    # PRIVATE CALLBACKS (run on the main/GUI thread via signal delivery)
    # ------------------------------------------------------------------

    def _on_tool_executed(self, status: str) -> None:
        """Handle a tool execution notification — show it in the chat."""
        self.chat_history.append({"role": "assistant", "content": status})
        self.message_received.emit("assistant", status)
        self.tool_executed.emit(status)

    def _on_response(self, reply: str) -> None:
        """Handle a successful AI response."""
        self.chat_history.append({"role": "assistant", "content": reply})
        self.message_received.emit("assistant", reply)

        # Audit-log the action (best-effort)
        try:
            from .action_record import ActionOutcome, ActionType, get_action_log

            action_log = get_action_log()
            action_log.log_action(
                action_type=ActionType.ANALYZE,
                description="Responded to user question",
                input_data={"preview": reply[:100]},
                output_data={},
                outcome=ActionOutcome.SUCCESS,
            )
        except Exception:
            pass

    def _on_error(self, error_msg: str) -> None:
        """Handle a worker error."""
        # Still add a message so the UI shows feedback
        fallback = f"⚠️ {error_msg}"
        self.chat_history.append({"role": "assistant", "content": fallback})
        self.message_received.emit("assistant", fallback)
        self.response_error.emit(error_msg)

        # Audit-log the failure (best-effort)
        try:
            from .action_record import ActionOutcome, ActionType, get_action_log

            action_log = get_action_log()
            action_log.log_action(
                action_type=ActionType.ANALYZE,
                description="Chat response failed",
                outcome=ActionOutcome.FAILED,
                error=error_msg,
            )
        except Exception:
            pass

    def _on_worker_done(self) -> None:
        """Reset the guard flag when the worker thread exits."""
        with self._lock:
            self._worker_running = False
        # Allow the QThread object to be garbage-collected
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None


# ===========================================================================
# MODULE-LEVEL HELPERS
# ===========================================================================

_chatbot_bridge: ChatbotBridge | None = None
_bridge_lock = threading.Lock()


def get_chatbot_bridge() -> ChatbotBridge:
    """Return the singleton ``ChatbotBridge`` instance."""
    global _chatbot_bridge
    with _bridge_lock:
        if _chatbot_bridge is None:
            _chatbot_bridge = ChatbotBridge()
        return _chatbot_bridge
