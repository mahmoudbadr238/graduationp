"""
Tool Wrappers for the Smart Security Assistant.

These are the interfaces that agents use to interact with the system.
Implementations connect to the actual Sentinel backend.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# EVENT STRUCTURES
# =============================================================================

@dataclass
class Event:
    """Windows Event structure."""
    record_id: int
    log_name: str  # "System", "Security", "Application"
    provider: str  # "Service Control Manager", "Microsoft-Windows-Security-Auditing"
    event_id: int
    level: str  # "Information", "Warning", "Error", "Critical"
    time_created: str  # ISO format
    message: str
    fields: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "log_name": self.log_name,
            "provider": self.provider,
            "event_id": self.event_id,
            "level": self.level,
            "time_created": self.time_created,
            "message": self.message,
            "fields": self.fields,
        }


# =============================================================================
# SECURITY STATUS STRUCTURES
# =============================================================================

@dataclass
class FirewallStatus:
    """Windows Firewall status."""
    domain: bool = True
    private: bool = True
    public: bool = True
    
    @property
    def all_enabled(self) -> bool:
        return self.domain and self.private and self.public
    
    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "private": self.private,
            "public": self.public,
            "all_enabled": self.all_enabled,
        }


@dataclass
class DefenderStatus:
    """Windows Defender status."""
    realtime_protection: bool = True
    tamper_protection: bool = True
    last_scan: str = ""
    antivirus_enabled: bool = True
    antispyware_enabled: bool = True
    
    @property
    def is_healthy(self) -> bool:
        return self.realtime_protection and self.antivirus_enabled
    
    def to_dict(self) -> dict:
        return {
            "realtime_protection": self.realtime_protection,
            "tamper_protection": self.tamper_protection,
            "last_scan": self.last_scan,
            "antivirus_enabled": self.antivirus_enabled,
            "antispyware_enabled": self.antispyware_enabled,
            "is_healthy": self.is_healthy,
        }


@dataclass
class UpdateStatus:
    """Windows Update status."""
    pending_reboot: bool = False
    last_update: str = ""
    pending_updates: int = 0
    
    def to_dict(self) -> dict:
        return {
            "pending_reboot": self.pending_reboot,
            "last_update": self.last_update,
            "pending_updates": self.pending_updates,
        }


# =============================================================================
# SCAN RESULT STRUCTURES
# =============================================================================

@dataclass
class FileScanResult:
    """Result from file scan."""
    verdict: str  # "clean", "suspicious", "malicious", "unknown"
    score: int  # 0-100
    signals: list[str] = field(default_factory=list)
    hashes: dict = field(default_factory=dict)  # md5, sha256
    static: dict = field(default_factory=dict)  # imports, strings, sections
    dynamic: dict = field(default_factory=dict)  # processes, files, registry, network
    errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "signals": self.signals,
            "hashes": self.hashes,
            "static": self.static,
            "dynamic": self.dynamic,
            "errors": self.errors,
        }


@dataclass
class UrlScanResult:
    """Result from URL scan."""
    verdict: str  # "clean", "suspicious", "malicious", "unknown"
    score: int  # 0-100
    signals: list[str] = field(default_factory=list)
    whois: dict = field(default_factory=dict)  # domain_age_days, registrar, country
    dns: dict = field(default_factory=dict)  # a, aaaa, mx
    http: dict = field(default_factory=dict)  # final_url, status_code, content_type
    errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "signals": self.signals,
            "whois": self.whois,
            "dns": self.dns,
            "http": self.http,
            "errors": self.errors,
        }


# =============================================================================
# TOOL INTERFACE (Protocol for dependency injection)
# =============================================================================

class SecurityToolsProtocol(Protocol):
    """Protocol defining all required security tools."""
    
    def get_recent_events(self, limit: int = 20, log_name: Optional[str] = None) -> list[Event]: ...
    def get_event_details(self, record_id: int, log_name: Optional[str] = None) -> Optional[Event]: ...
    def search_events(self, query: str, limit: int = 20) -> list[Event]: ...
    def get_firewall_status(self) -> FirewallStatus: ...
    def get_defender_status(self) -> DefenderStatus: ...
    def get_update_status(self) -> UpdateStatus: ...
    def scan_file(self, path: str) -> FileScanResult: ...
    def analyze_url_offline(self, url: str) -> UrlScanResult: ...
    def analyze_url_online(self, url: str) -> UrlScanResult: ...


# =============================================================================
# TOOL REGISTRY (Actual implementation wrapper)
# =============================================================================

class ToolRegistry:
    """
    Registry of available tools with implementations.
    
    Wraps actual Sentinel backend functions into a consistent interface.
    """
    
    def __init__(
        self,
        get_recent_events: Optional[Callable] = None,
        get_event_details: Optional[Callable] = None,
        search_events: Optional[Callable] = None,
        get_firewall_status: Optional[Callable] = None,
        get_defender_status: Optional[Callable] = None,
        get_update_status: Optional[Callable] = None,
        scan_file: Optional[Callable] = None,
        analyze_url_offline: Optional[Callable] = None,
        analyze_url_online: Optional[Callable] = None,
        kb_lookup: Optional[Callable] = None,
        get_app_help: Optional[Callable] = None,
    ):
        """
        Initialize with backend function references.
        
        All functions are optional - tool calls return errors if not provided.
        """
        self._get_recent_events = get_recent_events
        self._get_event_details = get_event_details
        self._search_events = search_events
        self._get_firewall_status = get_firewall_status
        self._get_defender_status = get_defender_status
        self._get_update_status = get_update_status
        self._scan_file = scan_file
        self._analyze_url_offline = analyze_url_offline
        self._analyze_url_online = analyze_url_online
        self._kb_lookup = kb_lookup
        self._get_app_help = get_app_help
        
        logger.info("ToolRegistry initialized")
    
    def register_callback(self, tool_name, callback: Callable) -> None:
        """
        Register a callback for a specific tool.
        
        This allows dynamic registration of tool implementations,
        useful for integrating with the Sentinel backend.
        
        Args:
            tool_name: ToolName enum or string name
            callback: Function to call for this tool
        """
        # Import ToolName from schema
        from .schema import ToolName
        
        # Handle string tool names
        if isinstance(tool_name, str):
            try:
                tool_name = ToolName(tool_name)
            except ValueError:
                logger.warning(f"Unknown tool name: {tool_name}")
                return
        
        # Map tool names to internal attributes
        tool_map = {
            ToolName.GET_RECENT_EVENTS: "_get_recent_events",
            ToolName.GET_EVENT_DETAILS: "_get_event_details",
            ToolName.SEARCH_EVENTS: "_search_events",
            ToolName.GET_FIREWALL_STATUS: "_get_firewall_status",
            ToolName.GET_DEFENDER_STATUS: "_get_defender_status",
            ToolName.GET_UPDATE_STATUS: "_get_update_status",
            ToolName.SCAN_FILE: "_scan_file",
            ToolName.ANALYZE_URL_OFFLINE: "_analyze_url_offline",
            ToolName.ANALYZE_URL_ONLINE: "_analyze_url_online",
            ToolName.LOOKUP_KB_RULES: "_kb_lookup",
            ToolName.GET_APP_HELP: "_get_app_help",
        }
        
        attr_name = tool_map.get(tool_name)
        if attr_name:
            setattr(self, attr_name, callback)
            logger.debug(f"Registered callback for {tool_name.value}")
    
    def get_recent_events(
        self,
        limit: int = 20,
        log_name: Optional[str] = None,
        severity_filter: Optional[str] = None,
        hours_back: int = 24,
    ) -> tuple[list[Event], Optional[str]]:
        """
        Get recent Windows events.
        
        Returns:
            (list of Events, error message or None)
        """
        if not self._get_recent_events:
            return [], "Event retrieval not available"
        
        try:
            raw_events = self._get_recent_events(limit=limit, log_name=log_name)
            
            events = []
            for e in raw_events:
                if isinstance(e, dict):
                    event = Event(
                        record_id=e.get("record_id", 0),
                        log_name=e.get("log_name", "System"),
                        provider=e.get("provider", e.get("source", "Unknown")),
                        event_id=e.get("event_id", 0),
                        level=e.get("level", "Information"),
                        time_created=e.get("time_created", e.get("timestamp", "")),
                        message=e.get("message", ""),
                        fields=e.get("fields", {}),
                    )
                else:
                    event = e
                
                # Apply severity filter
                if severity_filter:
                    level_lower = event.level.lower()
                    if severity_filter == "errors" and level_lower not in ("error", "critical"):
                        continue
                    elif severity_filter == "warnings" and level_lower not in ("warning", "error", "critical"):
                        continue
                
                events.append(event)
            
            return events, None
            
        except Exception as e:
            logger.exception(f"Error getting recent events: {e}")
            return [], str(e)
    
    def get_event_details(
        self,
        record_id: Optional[int] = None,
        event_id: Optional[int] = None,
        log_name: Optional[str] = None,
    ) -> tuple[Optional[Event], Optional[str]]:
        """
        Get details for a specific event.
        
        Can lookup by record_id (exact) or event_id (find in recent events).
        
        Returns:
            (Event or None, error message or None)
        """
        # If we have record_id, try direct lookup
        if record_id and self._get_event_details:
            try:
                result = self._get_event_details(record_id, log_name)
                if result:
                    if isinstance(result, dict):
                        return Event(**result), None
                    return result, None
            except Exception as e:
                logger.warning(f"Direct event lookup failed: {e}")
        
        # Fallback: search recent events for event_id
        if event_id:
            events, err = self.get_recent_events(limit=50, log_name=log_name)
            if not err:
                for event in events:
                    if event.event_id == event_id:
                        return event, None
                return None, f"Event ID {event_id} not found in recent events"
        
        return None, "Could not find the requested event"
    
    def search_events(
        self,
        query: str,
        limit: int = 20,
    ) -> tuple[list[Event], Optional[str]]:
        """
        Search events by query string.
        
        Returns:
            (list of Events, error message or None)
        """
        if not self._search_events:
            # Fallback: search in recent events
            events, err = self.get_recent_events(limit=100)
            if err:
                return [], err
            
            query_lower = query.lower()
            matches = []
            for event in events:
                if (query_lower in event.message.lower() or
                    query_lower in event.provider.lower() or
                    query_lower in str(event.event_id)):
                    matches.append(event)
                    if len(matches) >= limit:
                        break
            
            return matches, None
        
        try:
            raw_events = self._search_events(query, limit)
            events = []
            for e in raw_events:
                if isinstance(e, dict):
                    events.append(Event(**e))
                else:
                    events.append(e)
            return events, None
        except Exception as e:
            logger.exception(f"Error searching events: {e}")
            return [], str(e)
    
    def get_firewall_status(self) -> tuple[FirewallStatus, Optional[str]]:
        """Get Windows Firewall status."""
        if not self._get_firewall_status:
            return FirewallStatus(), "Firewall status not available"
        
        try:
            result = self._get_firewall_status()
            if isinstance(result, dict):
                return FirewallStatus(
                    domain=result.get("domain", result.get("Domain", True)),
                    private=result.get("private", result.get("Private", True)),
                    public=result.get("public", result.get("Public", True)),
                ), None
            return result, None
        except Exception as e:
            logger.exception(f"Error getting firewall status: {e}")
            return FirewallStatus(), str(e)
    
    def get_defender_status(self) -> tuple[DefenderStatus, Optional[str]]:
        """Get Windows Defender status."""
        if not self._get_defender_status:
            return DefenderStatus(), "Defender status not available"
        
        try:
            result = self._get_defender_status()
            if isinstance(result, dict):
                return DefenderStatus(
                    realtime_protection=result.get("realtime_protection", 
                                                   result.get("real_time_protection", True)),
                    tamper_protection=result.get("tamper_protection", True),
                    last_scan=result.get("last_scan", ""),
                    antivirus_enabled=result.get("antivirus_enabled", 
                                                 result.get("enabled", True)),
                    antispyware_enabled=result.get("antispyware_enabled", True),
                ), None
            return result, None
        except Exception as e:
            logger.exception(f"Error getting defender status: {e}")
            return DefenderStatus(), str(e)
    
    def get_update_status(self) -> tuple[UpdateStatus, Optional[str]]:
        """Get Windows Update status."""
        if not self._get_update_status:
            return UpdateStatus(), "Update status not available"
        
        try:
            result = self._get_update_status()
            if isinstance(result, dict):
                return UpdateStatus(
                    pending_reboot=result.get("pending_reboot", False),
                    last_update=result.get("last_update", ""),
                    pending_updates=result.get("pending_updates", 0),
                ), None
            return result, None
        except Exception as e:
            logger.exception(f"Error getting update status: {e}")
            return UpdateStatus(), str(e)
    
    def scan_file(self, path: str) -> tuple[FileScanResult, Optional[str]]:
        """Scan a file for malware."""
        if not self._scan_file:
            return FileScanResult(verdict="unknown", score=0), "File scanning not available"
        
        try:
            result = self._scan_file(path)
            if isinstance(result, dict):
                return FileScanResult(
                    verdict=result.get("verdict", "unknown"),
                    score=result.get("score", 0),
                    signals=result.get("signals", []),
                    hashes=result.get("hashes", {}),
                    static=result.get("static", {}),
                    dynamic=result.get("dynamic", {}),
                    errors=result.get("errors", []),
                ), None
            return result, None
        except Exception as e:
            logger.exception(f"Error scanning file: {e}")
            return FileScanResult(verdict="unknown", score=0, errors=[str(e)]), str(e)
    
    def analyze_url_offline(self, url: str) -> tuple[UrlScanResult, Optional[str]]:
        """Analyze URL using offline rules only."""
        if not self._analyze_url_offline:
            # Basic offline analysis fallback
            return self._basic_url_analysis(url), None
        
        try:
            result = self._analyze_url_offline(url)
            if isinstance(result, dict):
                return UrlScanResult(**result), None
            return result, None
        except Exception as e:
            logger.exception(f"Error analyzing URL offline: {e}")
            return UrlScanResult(verdict="unknown", score=0, errors=[str(e)]), str(e)
    
    def analyze_url_online(self, url: str) -> tuple[UrlScanResult, Optional[str]]:
        """Analyze URL using online services (if available)."""
        if not self._analyze_url_online:
            return self.analyze_url_offline(url)
        
        try:
            result = self._analyze_url_online(url)
            if isinstance(result, dict):
                return UrlScanResult(**result), None
            return result, None
        except Exception as e:
            logger.exception(f"Error analyzing URL online: {e}")
            # Fallback to offline
            return self.analyze_url_offline(url)
    
    def lookup_kb_rules(
        self,
        provider: str,
        event_id: int,
    ) -> tuple[Optional[dict], Optional[str]]:
        """
        Look up event in the deterministic knowledge base.
        
        Returns:
            (KB entry dict or None, error message or None)
        """
        if not self._kb_lookup:
            return None, "KB lookup not available"
        
        try:
            result = self._kb_lookup(provider, event_id)
            return result, None
        except Exception as e:
            logger.exception(f"Error looking up KB: {e}")
            return None, str(e)
    
    def get_app_help(self, feature_name: str) -> tuple[Optional[str], Optional[str]]:
        """Get help text for an app feature."""
        if not self._get_app_help:
            # Fallback help texts
            return self._default_app_help(feature_name), None
        
        try:
            result = self._get_app_help(feature_name)
            return result, None
        except Exception as e:
            logger.exception(f"Error getting app help: {e}")
            return self._default_app_help(feature_name), None
    
    def _basic_url_analysis(self, url: str) -> UrlScanResult:
        """Basic offline URL analysis."""
        import re
        
        signals = []
        score = 0
        
        # Check for IP-based URL
        if re.match(r'https?://\d+\.\d+\.\d+\.\d+', url):
            signals.append("ip_url")
            score += 30
        
        # Check for suspicious TLDs
        suspicious_tlds = ['.xyz', '.top', '.work', '.click', '.link', '.gq', '.ml', '.tk']
        for tld in suspicious_tlds:
            if url.lower().endswith(tld) or f"{tld}/" in url.lower():
                signals.append("suspicious_tld")
                score += 20
                break
        
        # Check for excessive subdomains
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.netloc.count('.') > 3:
                signals.append("excessive_subdomains")
                score += 15
        except:
            pass
        
        # Check for URL shorteners
        shorteners = ['bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly']
        for shortener in shorteners:
            if shortener in url.lower():
                signals.append("url_shortener")
                score += 10
                break
        
        # Determine verdict
        if score >= 50:
            verdict = "suspicious"
        elif score >= 30:
            verdict = "suspicious"
        else:
            verdict = "unknown"  # Not "clean" without more analysis
        
        return UrlScanResult(
            verdict=verdict,
            score=min(score, 100),
            signals=signals,
        )
    
    def _default_app_help(self, feature_name: str) -> str:
        """Default help texts for app features."""
        help_texts = {
            "event_viewer": (
                "The Event Viewer shows Windows security and system events. "
                "Navigate to it from the sidebar, then:\n"
                "• Events are color-coded by severity\n"
                "• Click any event to see details\n"
                "• Use 'Explain with AI' for plain-English explanations\n"
                "• Filter by log type (System, Security, Application)"
            ),
            "scanner": (
                "The Scanner analyzes files for malware using local rules. "
                "To scan a file:\n"
                "• Go to Scanner page from sidebar\n"
                "• Click 'Select File' or drag-and-drop\n"
                "• Click 'Scan' to analyze\n"
                "All scanning is done locally - files are never uploaded."
            ),
            "security_status": (
                "Security Status shows your system's protection level:\n"
                "• Windows Defender real-time protection\n"
                "• Firewall status for all network profiles\n"
                "• Windows Update status\n"
                "• TPM and BitLocker status"
            ),
            "network_monitor": (
                "Network Monitor shows active connections:\n"
                "• View all network connections\n"
                "• Scan for open ports\n"
                "• Identify processes using network\n"
                "• Detect suspicious connections"
            ),
        }
        
        feature_lower = feature_name.lower()
        for key, text in help_texts.items():
            if key in feature_lower or feature_lower in key:
                return text
        
        return (
            f"Sentinel has many security features. "
            f"Use the sidebar to navigate to different pages. "
            f"Ask me about specific features like Event Viewer, Scanner, or Security Status."
        )
