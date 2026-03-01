"""
Friendly Report Generator - User-friendly scan reports

Creates easy-to-understand reports for non-technical users.
Avoids jargon and explains findings in plain language.
"""

import logging
from datetime import datetime
from pathlib import Path
from dataclasses import asdict, is_dataclass

logger = logging.getLogger(__name__)


class FriendlyReportGenerator:
    """
    Generates user-friendly scan reports with plain language.
    
    Designed for normal users, not security professionals.
    """

    # Verdict explanations in plain language
    VERDICT_EXPLANATIONS = {
        "Safe": "This file appears to be safe. No threats were detected during our analysis.",
        "Suspicious": "This file has some characteristics that could indicate a problem. We recommend caution.",
        "Likely Malicious": "This file shows multiple warning signs and is likely harmful. We strongly recommend not using it.",
        "Malicious": "This file is dangerous! It shows clear signs of being malware. Do NOT run this file.",
    }

    # Severity explanations
    SEVERITY_LABELS = {
        "critical": "🔴 Critical Risk",
        "high": "🟠 High Risk",
        "medium": "🟡 Medium Risk",
        "low": "🟢 Low Risk",
        "info": "ℹ️ Information",
    }

    def generate_file_report(
        self,
        file_path: str | Path,
        static_result: dict | None = None,
        sandbox_result: dict | None = None,
        scoring_result = None,
    ) -> str:
        """
        Generate a user-friendly file scan report.
        
        Returns the report as a string (not saved to file).
        """
        def _to_dict(obj):
            if isinstance(obj, dict):
                return obj
            if hasattr(obj, "to_dict"):
                try:
                    return obj.to_dict()
                except Exception:
                    pass
            if is_dataclass(obj):
                try:
                    return asdict(obj)
                except Exception:
                    pass
            if hasattr(obj, "__dict__"):
                return vars(obj)
            return {}

        # Normalize result containers to dictionaries to avoid attribute errors
        if static_result is not None and not isinstance(static_result, dict):
            static_result = _to_dict(static_result)
        if sandbox_result is not None and not isinstance(sandbox_result, dict):
            sandbox_result = _to_dict(sandbox_result)

        file_path = Path(file_path)
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("📋 SECURITY SCAN REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"📅 Scanned on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        lines.append(f"📁 File: {file_path.name}")
        lines.append("")

        # Main Verdict - Big and Clear
        lines.append("-" * 60)
        if scoring_result:
            verdict = getattr(scoring_result, "verdict_label", "Unknown")
            score = getattr(scoring_result, "score", 0)

            # Verdict emoji and label
            if verdict == "Malicious" or score > 80:
                lines.append("⛔ VERDICT: DANGEROUS")
                lines.append("")
                lines.append("This file is NOT safe to use!")
            elif verdict == "Likely Malicious" or score > 50:
                lines.append("🚨 VERDICT: PROBABLY DANGEROUS")
                lines.append("")
                lines.append("This file shows many warning signs. Avoid using it.")
            elif verdict == "Suspicious" or score > 20:
                lines.append("⚠️ VERDICT: SUSPICIOUS")
                lines.append("")
                lines.append("This file has some concerning characteristics.")
                lines.append("Use with caution or get a second opinion.")
            else:
                lines.append("✅ VERDICT: SAFE")
                lines.append("")
                lines.append("No threats detected. This file appears safe to use.")

            lines.append("")
            lines.append(f"Risk Score: {score}/100 " + self._score_bar(score))
            lines.append("")

            # Simple explanation
            explanation = self.VERDICT_EXPLANATIONS.get(verdict, "")
            if explanation:
                lines.append(explanation)
        else:
            lines.append("❓ VERDICT: UNKNOWN")
            lines.append("")
            lines.append("We couldn't determine the safety of this file.")

        lines.append("-" * 60)
        lines.append("")

        # File Details (simplified)
        lines.append("📄 FILE DETAILS")
        lines.append("")
        lines.append(f"  Name: {file_path.name}")

        if static_result:
            file_size = static_result.get("file_size", 0)
            lines.append(f"  Size: {self._format_size(file_size)}")

            mime = static_result.get("mime_type", "")
            if mime:
                lines.append(f"  Type: {self._friendly_mime_type(mime)}")

            # Only show hash if user might need it
            sha256 = static_result.get("sha256", "")
            if sha256:
                lines.append(f"  Fingerprint: {sha256[:16]}...")

        lines.append("")

        # What We Checked
        lines.append("🔍 WHAT WE CHECKED")
        lines.append("")

        checks = []
        if static_result:
            checks.append("✓ File structure and code patterns")
            if static_result.get("pe_info"):
                checks.append("✓ Program header information")
            if static_result.get("yara_matches"):
                checks.append("✓ Known malware signatures")

        if sandbox_result and sandbox_result.get("success"):
            checks.append("✓ Behavior when running (sandbox test)")

        if not checks:
            checks.append("○ Basic file analysis")

        for check in checks:
            lines.append(f"  {check}")

        lines.append("")

        # Problems Found (if any)
        findings = []
        finding_keys = set()

        # Collect findings from static analysis
        if static_result:
            for finding in static_result.get("findings", []):
                finding = _to_dict(finding)
                item = {
                    "severity": finding.get("severity", "medium"),
                    "title": finding.get("title", "Unknown issue"),
                    "detail": finding.get("detail", ""),
                    "source": "file analysis"
                }
                key = (
                    str(item["severity"]).lower(),
                    str(item["title"]).strip().lower(),
                    str(item["detail"]).strip().lower(),
                )
                if key not in finding_keys:
                    findings.append(item)
                    finding_keys.add(key)

            # YARA matches
            for match in static_result.get("yara_matches", []):
                match = _to_dict(match)
                raw_rule = (
                    match.get("rule")
                    or match.get("rule_name")
                    or ""
                )
                if not raw_rule and isinstance(match.get("title"), str):
                    title_text = match.get("title", "")
                    raw_rule = title_text.replace("YARA:", "").strip() if title_text.lower().startswith("yara:") else title_text

                title = f"YARA: {raw_rule}" if raw_rule else "YARA: Signature Match"
                detail = (
                    match.get("description")
                    or match.get("detail")
                    or "Matched a known YARA signature pattern."
                )
                item = {
                    "severity": match.get("severity", "high"),
                    "title": title,
                    "detail": detail,
                    "source": "signature matching"
                }
                key = (
                    str(item["severity"]).lower(),
                    str(item["title"]).strip().lower(),
                    str(item["detail"]).strip().lower(),
                )
                if key not in finding_keys:
                    findings.append(item)
                    finding_keys.add(key)

        # Collect findings from sandbox
        if sandbox_result and sandbox_result.get("success"):
            if sandbox_result.get("timed_out"):
                findings.append({
                    "severity": "medium",
                    "title": "Program took too long to finish",
                    "detail": "The file ran longer than expected. Some malware does this to avoid detection.",
                    "source": "behavior test"
                })

            # Network attempts (bad sign)
            network = sandbox_result.get("network_connections", [])
            if network:
                findings.append({
                    "severity": "high",
                    "title": f"Tried to connect to the internet ({len(network)} attempts)",
                    "detail": "This file tried to reach external servers, which could be for malicious purposes.",
                    "source": "behavior test"
                })

            # File modifications
            files_created = sandbox_result.get("files_created", [])
            if len(files_created) > 5:
                findings.append({
                    "severity": "medium",
                    "title": f"Created many files ({len(files_created)})",
                    "detail": "Programs that create lots of files might be installing unwanted software.",
                    "source": "behavior test"
                })

            # Registry modifications
            registry = sandbox_result.get("registry_modifications", [])
            if registry:
                findings.append({
                    "severity": "high",
                    "title": f"Modified Windows settings ({len(registry)} changes)",
                    "detail": "This file tried to change system settings, which is often a sign of malware.",
                    "source": "behavior test"
                })

            # Child processes
            children = sandbox_result.get("child_processes", [])
            if len(children) > 2:
                findings.append({
                    "severity": "medium",
                    "title": f"Launched other programs ({len(children)})",
                    "detail": "Starting multiple programs can indicate spreading or installing additional malware.",
                    "source": "behavior test"
                })

        if findings:
            lines.append("⚠️ PROBLEMS FOUND")
            lines.append("")

            # Sort by severity
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            findings.sort(key=lambda x: severity_order.get(x["severity"], 5))

            for i, finding in enumerate(findings[:10], 1):  # Limit to 10
                severity_label = self.SEVERITY_LABELS.get(finding["severity"], "")
                lines.append(f"  {i}. {severity_label}")
                lines.append(f"     {finding['title']}")
                if finding["detail"]:
                    # Wrap long details
                    detail = finding["detail"][:100]
                    if len(finding["detail"]) > 100:
                        detail += "..."
                    lines.append(f"     → {detail}")
                lines.append("")

            if len(findings) > 10:
                lines.append(f"  ... and {len(findings) - 10} more issues")
                lines.append("")
        elif scoring_result and getattr(scoring_result, "score", 0) < 20:
            lines.append("✓ NO PROBLEMS FOUND")
            lines.append("")
            lines.append("  Our analysis didn't find any issues with this file.")
            lines.append("")

        # What Happened in Sandbox (detailed behavior analysis)
        if sandbox_result and sandbox_result.get("success"):
            session_summary = sandbox_result.get("session_summary")
            if session_summary:
                lines.extend(self._generate_sandbox_evidence_section(sandbox_result, session_summary))
            else:
                # Basic sandbox section without session data
                lines.extend(self._generate_basic_sandbox_section(sandbox_result))

        # Recommendations
        lines.append("-" * 60)
        lines.append("💡 WHAT SHOULD YOU DO?")
        lines.append("")

        if scoring_result:
            score = getattr(scoring_result, "score", 0)
            if score > 80:
                lines.append("  ❌ DELETE this file immediately")
                lines.append("  ❌ Do NOT open or run it")
                lines.append("  ❌ Run a full system antivirus scan")
                lines.append("  ❌ If you already ran it, check your system for issues")
            elif score > 50:
                lines.append("  ⚠️ Do NOT run this file unless you absolutely trust the source")
                lines.append("  ⚠️ Consider deleting it to be safe")
                lines.append("  ⚠️ If you must use it, scan with another antivirus first")
            elif score > 20:
                lines.append("  ⚠️ Be cautious - only run if you trust where it came from")
                lines.append("  ⚠️ Consider getting a second opinion from another scanner")
                lines.append("  ⚠️ Watch for unusual behavior if you run it")
            else:
                lines.append("  ✅ This file looks safe to use")
                lines.append("  ✅ You can run it normally")
                lines.append("  ℹ️ Always download files from trusted sources")
        else:
            lines.append("  ⚠️ Unable to fully analyze - use caution")

        lines.append("")
        lines.append("-" * 60)

        # Footer
        lines.append("")
        lines.append("This scan was performed 100% offline on your computer.")
        lines.append("No data was sent to any external servers.")
        lines.append("")
        lines.append("Powered by Sentinel Security Suite")
        lines.append("=" * 60)

        return "\n".join(lines)

    def generate_url_report(
        self,
        url: str,
        result: dict,
    ) -> str:
        """
        Generate a user-friendly URL scan report.
        
        Returns the report as a string.
        """
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("🌐 URL SAFETY REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"📅 Checked on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        lines.append(f"🔗 URL: {url}")
        lines.append("")

        # Verdict
        lines.append("-" * 60)
        verdict = result.get("verdict", "unknown").lower()
        score = result.get("score", 0)

        if verdict == "malicious" or score > 80:
            lines.append("⛔ VERDICT: DANGEROUS WEBSITE")
            lines.append("")
            lines.append("Do NOT visit this website! It may harm your computer.")
        elif verdict == "likely_malicious" or score > 50:
            lines.append("🚨 VERDICT: PROBABLY DANGEROUS")
            lines.append("")
            lines.append("This website shows many warning signs. Avoid visiting.")
        elif verdict == "suspicious" or score > 20:
            lines.append("⚠️ VERDICT: SUSPICIOUS")
            lines.append("")
            lines.append("This website has some concerning characteristics.")
        else:
            lines.append("✅ VERDICT: APPEARS SAFE")
            lines.append("")
            lines.append("No major threats detected for this URL.")

        lines.append("")
        lines.append(f"Risk Score: {score}/100 " + self._score_bar(score))
        lines.append("-" * 60)
        lines.append("")

        # Reasons (in plain language)
        reasons = result.get("reasons", [])
        if reasons:
            lines.append("🔍 WHAT WE FOUND")
            lines.append("")

            for reason in reasons[:8]:
                severity = reason.get("severity", "info")
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "ℹ️")
                lines.append(f"  {emoji} {reason.get('title', 'Unknown')}")
                if reason.get("detail"):
                    lines.append(f"     → {reason['detail'][:80]}")
                lines.append("")

        # Recommendations
        lines.append("-" * 60)
        lines.append("💡 WHAT SHOULD YOU DO?")
        lines.append("")

        if score > 50:
            lines.append("  ❌ Do NOT visit this website")
            lines.append("  ❌ Do NOT enter any personal information")
            lines.append("  ❌ If you visited, run an antivirus scan")
        elif score > 20:
            lines.append("  ⚠️ Be very careful if you visit")
            lines.append("  ⚠️ Don't download anything from this site")
            lines.append("  ⚠️ Don't enter passwords or personal info")
        else:
            lines.append("  ✅ This website appears safe to visit")
            lines.append("  ℹ️ Still be cautious with downloads and links")

        lines.append("")
        lines.append("-" * 60)
        lines.append("")
        lines.append("Powered by Sentinel Security Suite")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _generate_sandbox_evidence_section(self, sandbox_result: dict, session_summary: dict) -> list:
        """Generate detailed sandbox behavior evidence section with tables."""
        lines = []
        lines.append("")
        lines.append("🔬 WHAT HAPPENED DURING SANDBOX EXECUTION")
        lines.append("-" * 60)
        lines.append("")

        # Duration and outcome
        duration = sandbox_result.get("duration_seconds", 0)
        exit_code = sandbox_result.get("exit_code")
        timed_out = sandbox_result.get("timed_out", False)

        if timed_out:
            lines.append(f"  ⏱️ Ran for {duration:.1f} seconds before being stopped (timeout)")
        else:
            outcome = "successfully" if exit_code == 0 else f"with exit code {exit_code}"
            lines.append(f"  ⏱️ Finished {outcome} in {duration:.1f} seconds")

        lines.append("")

        # Statistics summary
        stats = session_summary.get("final_stats", session_summary.get("stats", {}))
        if stats:
            process_count = stats.get("processes_spawned", 0)
            file_count = stats.get("files_touched", 0)
            registry_count = stats.get("registry_changes", 0)
            network_count = stats.get("network_attempts", 0)
            suspicious_count = stats.get("suspicious_behaviors", 0)

            lines.append("  📊 Activity Summary:")
            if process_count > 0:
                lines.append(f"     • Processes started: {process_count}")
            if file_count > 0:
                lines.append(f"     • Files created/modified: {file_count}")
            if registry_count > 0:
                lines.append(f"     • Registry changes: {registry_count}")
            if network_count > 0:
                lines.append(f"     • Network connection attempts: {network_count}")
            if suspicious_count > 0:
                lines.append(f"     • ⚠️ Suspicious behaviors: {suspicious_count}")

            if process_count == 0 and file_count == 0 and registry_count == 0:
                lines.append("     • No significant activity detected")

            lines.append("")

        # Behavior narrative (if available)
        narrative = session_summary.get("narrative", "")
        if narrative:
            lines.append("  📖 Behavior Summary:")
            # Wrap narrative text
            for paragraph in narrative.split("\n"):
                if paragraph.strip():
                    lines.append(f"     {paragraph.strip()}")
            lines.append("")

        # ═══════════════════════════════════════════════════════════════
        # EXECUTION TIMELINE - Key events during run (what user watched)
        # ═══════════════════════════════════════════════════════════════

        all_events = session_summary.get("events", [])
        if all_events:
            lines.append("")
            lines.append("  ⏱️ EXECUTION TIMELINE (Key Events)")
            lines.append("  " + "─" * 55)

            # Select top 20 most important events
            # Priority: suspicious > process > network > registry > file
            def event_priority(evt):
                if evt.get("suspicious"):
                    return 0
                event_type = evt.get("event_type", "")
                if "suspicious" in event_type:
                    return 0
                if "process" in event_type:
                    return 1
                if "network" in event_type:
                    return 2
                if "registry" in event_type:
                    return 3
                return 4

            sorted_events = sorted(all_events, key=event_priority)
            timeline_events = sorted_events[:20]

            # Re-sort by timestamp for display
            timeline_events.sort(key=lambda e: e.get("timestamp", ""))

            for evt in timeline_events:
                timestamp = evt.get("timestamp", "")
                if timestamp:
                    # Extract just the time portion
                    try:
                        if "T" in timestamp:
                            time_part = timestamp.split("T")[1].split(".")[0]
                        else:
                            time_part = timestamp.split(" ")[-1].split(".")[0]
                    except Exception:
                        time_part = timestamp[:8]
                else:
                    time_part = "??:??:??"

                event_type = evt.get("event_type", "unknown")
                description = evt.get("description", "")

                # Format description based on event type
                if not description:
                    if "process" in event_type:
                        description = f"Process: {evt.get('process_name', 'unknown')}"
                    elif "file" in event_type:
                        path = evt.get("file_path", "")
                        op = event_type.replace("file_", "")
                        description = f"File {op}: {path.split(chr(92))[-1] if path else 'unknown'}"
                    elif "registry" in event_type:
                        description = f"Registry: {evt.get('registry_key', 'unknown key')}"
                    elif "network" in event_type:
                        addr = evt.get("remote_address", "?")
                        port = evt.get("remote_port", "?")
                        description = f"Network: {addr}:{port}"
                    else:
                        description = event_type.replace("_", " ").title()

                # Emoji based on type
                emoji = "  "
                if evt.get("suspicious") or "suspicious" in event_type:
                    emoji = "⚠️"
                elif "process" in event_type:
                    emoji = "⚙️"
                elif "file" in event_type:
                    emoji = "📄"
                elif "registry" in event_type:
                    emoji = "🗝️"
                elif "network" in event_type:
                    emoji = "🌐"

                # Truncate description
                if len(description) > 40:
                    description = description[:37] + "..."

                lines.append(f"  {time_part} {emoji} {description}")

            if len(all_events) > 20:
                lines.append(f"  ... and {len(all_events) - 20} more events")

            lines.append("")

        # ═══════════════════════════════════════════════════════════════
        # EVIDENCE TABLES
        # ═══════════════════════════════════════════════════════════════

        events_by_type = session_summary.get("events_by_type", {})

        # Process Evidence Table
        process_events = events_by_type.get("process_start", [])
        if process_events:
            lines.append("")
            lines.append("  ┌─────────────────────────────────────────────────────────┐")
            lines.append("  │ ⚙️  PROCESS EVIDENCE                                     │")
            lines.append("  ├───────┬───────────────────────┬─────────────────────────┤")
            lines.append("  │  PID  │ Process Name          │ Command Line            │")
            lines.append("  ├───────┼───────────────────────┼─────────────────────────┤")

            for proc in process_events[:10]:
                pid = str(proc.get("pid", "?"))[:5].ljust(5)
                name = str(proc.get("process_name", "Unknown"))[:21].ljust(21)
                cmd = str(proc.get("command_line", ""))[:23].ljust(23)
                lines.append(f"  │ {pid} │ {name} │ {cmd} │")

            if len(process_events) > 10:
                lines.append(f"  │  ...  │ ... and {len(process_events) - 10} more processes                │")

            lines.append("  └───────┴───────────────────────┴─────────────────────────┘")
            lines.append("")

        # File Evidence Table
        file_events = (events_by_type.get("file_create", []) +
                       events_by_type.get("file_modify", []) +
                       events_by_type.get("file_delete", []))
        if file_events:
            lines.append("")
            lines.append("  ┌─────────────────────────────────────────────────────────┐")
            lines.append("  │ 📄 FILE EVIDENCE                                        │")
            lines.append("  ├────────────┬────────────────────────────────────────────┤")
            lines.append("  │ Operation  │ File Path                                  │")
            lines.append("  ├────────────┼────────────────────────────────────────────┤")

            for evt in file_events[:10]:
                op = evt.get("event_type", "?").replace("file_", "").upper()[:10].ljust(10)
                path = str(evt.get("file_path", ""))
                # Truncate path intelligently
                if len(path) > 42:
                    path = "..." + path[-39:]
                path = path.ljust(42)
                lines.append(f"  │ {op} │ {path} │")

            if len(file_events) > 10:
                lines.append(f"  │    ...     │ ... and {len(file_events) - 10} more file operations           │")

            lines.append("  └────────────┴────────────────────────────────────────────┘")
            lines.append("")

        # Registry Evidence Table
        registry_events = (events_by_type.get("registry_create", []) +
                          events_by_type.get("registry_modify", []))
        if registry_events:
            lines.append("")
            lines.append("  ┌─────────────────────────────────────────────────────────┐")
            lines.append("  │ 🗝️  REGISTRY EVIDENCE                                   │")
            lines.append("  ├────────────┬────────────────────────────────────────────┤")
            lines.append("  │ Operation  │ Registry Key                               │")
            lines.append("  ├────────────┼────────────────────────────────────────────┤")

            for evt in registry_events[:8]:
                op = evt.get("event_type", "?").replace("registry_", "").upper()[:10].ljust(10)
                key = str(evt.get("registry_key", ""))
                if len(key) > 42:
                    key = "..." + key[-39:]
                key = key.ljust(42)
                lines.append(f"  │ {op} │ {key} │")

            if len(registry_events) > 8:
                lines.append(f"  │    ...     │ ... and {len(registry_events) - 8} more registry changes         │")

            lines.append("  └────────────┴────────────────────────────────────────────┘")
            lines.append("")

        # Network Evidence Table
        network_events = (events_by_type.get("network_connect", []) +
                         events_by_type.get("network_blocked", []))
        if network_events:
            lines.append("")
            lines.append("  ┌─────────────────────────────────────────────────────────┐")
            lines.append("  │ 🌐 NETWORK EVIDENCE                                     │")
            lines.append("  ├──────────┬─────────────────────────┬──────────┬─────────┤")
            lines.append("  │ Status   │ Remote Address          │ Port     │ Protocol│")
            lines.append("  ├──────────┼─────────────────────────┼──────────┼─────────┤")

            for evt in network_events[:8]:
                blocked = evt.get("blocked", False)
                status = ("BLOCKED" if blocked else "ALLOWED")[:8].ljust(8)
                addr = str(evt.get("remote_address", "?"))[:23].ljust(23)
                port = str(evt.get("remote_port", "?"))[:8].ljust(8)
                proto = str(evt.get("protocol", "TCP"))[:7].ljust(7)
                lines.append(f"  │ {status} │ {addr} │ {port} │ {proto} │")

            if len(network_events) > 8:
                lines.append(f"  │   ...    │ ... and {len(network_events) - 8} more connections                  │")

            lines.append("  └──────────┴─────────────────────────┴──────────┴─────────┘")
            lines.append("")

        # Suspicious Behaviors
        suspicious_events = session_summary.get("suspicious_behaviors", [])
        if suspicious_events:
            lines.append("")
            lines.append("  ┌─────────────────────────────────────────────────────────┐")
            lines.append("  │ ⚠️  SUSPICIOUS BEHAVIORS                                 │")
            lines.append("  ├─────────────────────────────────────────────────────────┤")

            for evt in suspicious_events[:5]:
                desc = str(evt.get("description", evt.get("behavior_category", "Unknown")))
                # Wrap description
                while len(desc) > 55:
                    lines.append(f"  │ {desc[:55]} │")
                    desc = desc[55:]
                lines.append(f"  │ {desc.ljust(55)} │")

                # Add reason if available
                indicators = evt.get("indicators", [])
                if indicators:
                    for ind in indicators[:2]:
                        ind_text = f"  → {ind}"[:55].ljust(55)
                        lines.append(f"  │ {ind_text} │")
                lines.append("  ├─────────────────────────────────────────────────────────┤")

            if len(suspicious_events) > 5:
                lines.append(f"  │ ... and {len(suspicious_events) - 5} more suspicious behaviors                    │")

            lines.append("  └─────────────────────────────────────────────────────────┘")
            lines.append("")

        # Files created list (legacy format for compatibility)
        files_created = sandbox_result.get("files_created", [])
        if files_created and not file_events:
            lines.append("  📁 Files Created:")
            for f in files_created[:5]:
                lines.append(f"     • {f}")
            if len(files_created) > 5:
                lines.append(f"     ... and {len(files_created) - 5} more")
            lines.append("")

        # Network blocked indicator
        if sandbox_result.get("network_blocked"):
            lines.append("  🔒 Network was BLOCKED during execution (safe mode)")
            lines.append("")

        # Session workspace reference
        workspace = session_summary.get("workspace", "")
        if workspace:
            lines.append(f"  📂 Full session data saved to: {workspace}")
            lines.append("")

        return lines

    def _generate_basic_sandbox_section(self, sandbox_result: dict) -> list:
        """Generate basic sandbox section without detailed session data."""
        lines = []
        lines.append("")
        lines.append("🔬 SANDBOX EXECUTION RESULTS")
        lines.append("-" * 60)
        lines.append("")

        duration = sandbox_result.get("duration_seconds", 0)
        exit_code = sandbox_result.get("exit_code")
        timed_out = sandbox_result.get("timed_out", False)

        if timed_out:
            lines.append(f"  ⏱️ Program ran until timeout ({duration:.1f}s)")
        else:
            lines.append(f"  ⏱️ Completed in {duration:.1f}s with exit code {exit_code}")

        # Files created
        files_created = sandbox_result.get("files_created", [])
        if files_created:
            lines.append(f"  📁 Created {len(files_created)} file(s)")
            for f in files_created[:3]:
                lines.append(f"     • {f}")
            if len(files_created) > 3:
                lines.append(f"     ... and {len(files_created) - 3} more")

        # Network status
        if sandbox_result.get("network_blocked"):
            lines.append("  🔒 Network access was blocked")

        lines.append("")
        return lines

    def _score_bar(self, score: int) -> str:
        """Create a visual score bar."""
        filled = score // 10
        empty = 10 - filled

        if score > 80:
            bar = "🔴" * filled + "⚪" * empty
        elif score > 50:
            bar = "🟠" * filled + "⚪" * empty
        elif score > 20:
            bar = "🟡" * filled + "⚪" * empty
        else:
            bar = "🟢" * filled + "⚪" * empty

        return f"[{bar}]"

    def _format_size(self, size: int) -> str:
        """Format file size in friendly way."""
        if size < 1024:
            return f"{size} bytes"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.1f} GB"

    def _friendly_mime_type(self, mime: str) -> str:
        """Convert MIME type to friendly name."""
        mapping = {
            "application/x-msdownload": "Windows Program",
            "application/x-dosexec": "Windows Program",
            "application/x-executable": "Program File",
            "application/pdf": "PDF Document",
            "application/zip": "ZIP Archive",
            "application/x-rar": "RAR Archive",
            "application/javascript": "JavaScript File",
            "text/html": "Web Page",
            "image/jpeg": "JPEG Image",
            "image/png": "PNG Image",
        }
        return mapping.get(mime, mime)


# Singleton instance
_generator = None


def get_friendly_report_generator() -> FriendlyReportGenerator:
    """Get the friendly report generator instance."""
    global _generator
    if _generator is None:
        _generator = FriendlyReportGenerator()
    return _generator
