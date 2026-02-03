"""
ChatContextBuilder: Build compact context for the security chatbot.

Gathers relevant information from:
    - System metrics (CPU, memory, disk)
    - Recent events (warnings, errors)
    - Scan history
    - Security status

This grounded context helps the chatbot give accurate, specific answers
instead of generic responses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class SystemMonitor(Protocol):
    """Protocol for system monitoring services."""
    
    def get_cpu_percent(self) -> float: ...
    def get_memory_percent(self) -> float: ...
    def get_disk_percent(self) -> float: ...


@runtime_checkable
class EventRepository(Protocol):
    """Protocol for event repository."""
    
    def get_recent(self, limit: int) -> list[dict[str, Any]]: ...


@dataclass
class ChatContext:
    """
    Compact context for chatbot grounding.
    
    Contains summarized information about current system state
    and recent activities.
    """
    
    # System metrics
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    system_health: str = "unknown"  # good, warning, critical
    
    # Security status
    is_admin: bool = False
    firewall_enabled: bool | None = None
    realtime_protection: bool | None = None
    last_scan_time: str | None = None
    
    # Recent events summary
    recent_error_count: int = 0
    recent_warning_count: int = 0
    critical_events: list[dict[str, Any]] = field(default_factory=list)
    
    # Top issues
    top_issues: list[str] = field(default_factory=list)
    
    # Timestamps
    context_time: str = ""
    
    def to_prompt_string(self) -> str:
        """Convert to a compact string for LLM context."""
        lines = [
            "CURRENT SYSTEM STATUS:",
            f"- CPU: {self.cpu_percent:.0f}%",
            f"- Memory: {self.memory_percent:.0f}%",
            f"- Disk: {self.disk_percent:.0f}%",
            f"- Overall Health: {self.system_health}",
            f"- Running as Admin: {'Yes' if self.is_admin else 'No'}",
        ]
        
        # Add security status if available
        if self.firewall_enabled is not None:
            lines.append(f"- Firewall: {'Enabled' if self.firewall_enabled else 'DISABLED'}")
        if self.realtime_protection is not None:
            lines.append(f"- Real-time Protection: {'Active' if self.realtime_protection else 'INACTIVE'}")
        if self.last_scan_time:
            lines.append(f"- Last Scan: {self.last_scan_time}")
        
        # Add event summary
        lines.append("\nRECENT ACTIVITY:")
        lines.append(f"- Errors (24h): {self.recent_error_count}")
        lines.append(f"- Warnings (24h): {self.recent_warning_count}")
        
        # Add critical events
        if self.critical_events:
            lines.append("\nCRITICAL EVENTS:")
            for ev in self.critical_events[:3]:
                lines.append(f"  • {ev.get('title', ev.get('event_id', 'Unknown'))}")
        
        # Add top issues
        if self.top_issues:
            lines.append("\nTOP ISSUES:")
            for issue in self.top_issues[:3]:
                lines.append(f"  • {issue}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_percent": self.disk_percent,
            "system_health": self.system_health,
            "is_admin": self.is_admin,
            "firewall_enabled": self.firewall_enabled,
            "realtime_protection": self.realtime_protection,
            "last_scan_time": self.last_scan_time,
            "recent_error_count": self.recent_error_count,
            "recent_warning_count": self.recent_warning_count,
            "critical_events": self.critical_events,
            "top_issues": self.top_issues,
            "context_time": self.context_time,
        }


class ChatContextBuilder:
    """
    Builds grounded context for the security chatbot.
    
    Gathers information from various services and summarizes
    it into a compact context for LLM grounding.
    """
    
    # Thresholds for health assessment
    THRESHOLDS = {
        "cpu": {"good": 50, "warning": 80, "critical": 95},
        "memory": {"good": 70, "warning": 85, "critical": 95},
        "disk": {"good": 75, "warning": 90, "critical": 95},
    }
    
    def __init__(
        self,
        snapshot_service: Any = None,
        event_repo: Any = None,
        scan_repo: Any = None,
    ):
        """
        Initialize the context builder.
        
        Args:
            snapshot_service: System snapshot service for metrics
            event_repo: Event repository for recent events
            scan_repo: Scan repository for scan history
        """
        self._snapshot = snapshot_service
        self._event_repo = event_repo
        self._scan_repo = scan_repo
        self._cached_context: ChatContext | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl = timedelta(seconds=30)  # Refresh every 30s
    
    def build_context(self, force_refresh: bool = False) -> ChatContext:
        """
        Build the current context.
        
        Args:
            force_refresh: Force refresh even if cache is valid
        
        Returns:
            ChatContext with current system information
        """
        # Check cache
        now = datetime.now()
        if (
            not force_refresh
            and self._cached_context is not None
            and self._cache_time is not None
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._cached_context
        
        ctx = ChatContext(context_time=now.isoformat())
        
        # Get system metrics
        self._populate_metrics(ctx)
        
        # Get security status
        self._populate_security_status(ctx)
        
        # Get recent events
        self._populate_events(ctx)
        
        # Assess health
        ctx.system_health = self._assess_health(ctx)
        
        # Identify top issues
        ctx.top_issues = self._identify_issues(ctx)
        
        # Cache the result
        self._cached_context = ctx
        self._cache_time = now
        
        return ctx
    
    def _populate_metrics(self, ctx: ChatContext) -> None:
        """Populate system metrics."""
        if self._snapshot is None:
            return
        
        try:
            # Try different attribute patterns
            if hasattr(self._snapshot, "cpuPercent"):
                ctx.cpu_percent = self._snapshot.cpuPercent or 0
            elif hasattr(self._snapshot, "get_cpu_percent"):
                ctx.cpu_percent = self._snapshot.get_cpu_percent() or 0
            
            if hasattr(self._snapshot, "memoryPercent"):
                ctx.memory_percent = self._snapshot.memoryPercent or 0
            elif hasattr(self._snapshot, "get_memory_percent"):
                ctx.memory_percent = self._snapshot.get_memory_percent() or 0
            
            if hasattr(self._snapshot, "diskPercent"):
                ctx.disk_percent = self._snapshot.diskPercent or 0
            elif hasattr(self._snapshot, "get_disk_percent"):
                ctx.disk_percent = self._snapshot.get_disk_percent() or 0
            
            # Check admin status
            if hasattr(self._snapshot, "isAdmin"):
                ctx.is_admin = bool(self._snapshot.isAdmin)
            
        except Exception as e:
            logger.warning(f"Failed to get system metrics: {e}")
    
    def _populate_security_status(self, ctx: ChatContext) -> None:
        """Populate security status."""
        if self._snapshot is None:
            return
        
        try:
            # Firewall status
            if hasattr(self._snapshot, "firewallDomain"):
                ctx.firewall_enabled = bool(self._snapshot.firewallDomain)
            elif hasattr(self._snapshot, "firewall_enabled"):
                ctx.firewall_enabled = bool(self._snapshot.firewall_enabled)
            
            # Real-time protection
            if hasattr(self._snapshot, "defenderRealtimeProtection"):
                ctx.realtime_protection = bool(self._snapshot.defenderRealtimeProtection)
            
        except Exception as e:
            logger.warning(f"Failed to get security status: {e}")
    
    def _populate_events(self, ctx: ChatContext) -> None:
        """Populate recent events summary."""
        if self._event_repo is None:
            return
        
        try:
            # Get recent events
            events = []
            if hasattr(self._event_repo, "get_recent"):
                events = self._event_repo.get_recent(100)
            elif hasattr(self._event_repo, "getRecent"):
                events = self._event_repo.getRecent(100)
            
            # Count by level
            for event in events:
                level = (event.get("level") or "").lower()
                if level in ("critical", "error"):
                    ctx.recent_error_count += 1
                    if level == "critical":
                        ctx.critical_events.append({
                            "event_id": event.get("event_id"),
                            "title": event.get("message", "")[:80],
                            "provider": event.get("provider", event.get("source")),
                        })
                elif level == "warning":
                    ctx.recent_warning_count += 1
            
            # Limit critical events
            ctx.critical_events = ctx.critical_events[:5]
            
        except Exception as e:
            logger.warning(f"Failed to get events: {e}")
    
    def _assess_health(self, ctx: ChatContext) -> str:
        """Assess overall system health."""
        # Check for critical conditions
        if ctx.cpu_percent >= self.THRESHOLDS["cpu"]["critical"]:
            return "critical"
        if ctx.memory_percent >= self.THRESHOLDS["memory"]["critical"]:
            return "critical"
        if ctx.disk_percent >= self.THRESHOLDS["disk"]["critical"]:
            return "critical"
        if ctx.critical_events:
            return "critical"
        
        # Check for warnings
        if ctx.cpu_percent >= self.THRESHOLDS["cpu"]["warning"]:
            return "warning"
        if ctx.memory_percent >= self.THRESHOLDS["memory"]["warning"]:
            return "warning"
        if ctx.disk_percent >= self.THRESHOLDS["disk"]["warning"]:
            return "warning"
        if ctx.recent_error_count > 5:
            return "warning"
        if ctx.firewall_enabled is False:
            return "warning"
        if ctx.realtime_protection is False:
            return "warning"
        
        return "good"
    
    def _identify_issues(self, ctx: ChatContext) -> list[str]:
        """Identify top issues based on context."""
        issues = []
        
        # Resource issues
        if ctx.cpu_percent >= self.THRESHOLDS["cpu"]["warning"]:
            issues.append(f"High CPU usage ({ctx.cpu_percent:.0f}%)")
        if ctx.memory_percent >= self.THRESHOLDS["memory"]["warning"]:
            issues.append(f"High memory usage ({ctx.memory_percent:.0f}%)")
        if ctx.disk_percent >= self.THRESHOLDS["disk"]["warning"]:
            issues.append(f"Low disk space ({100 - ctx.disk_percent:.0f}% free)")
        
        # Security issues
        if ctx.firewall_enabled is False:
            issues.append("Firewall is DISABLED")
        if ctx.realtime_protection is False:
            issues.append("Real-time protection is INACTIVE")
        
        # Event issues
        if ctx.recent_error_count > 10:
            issues.append(f"High error rate ({ctx.recent_error_count} errors)")
        elif ctx.recent_error_count > 5:
            issues.append(f"Elevated errors ({ctx.recent_error_count} errors)")
        
        if ctx.critical_events:
            issues.append(f"{len(ctx.critical_events)} critical events need attention")
        
        return issues[:5]  # Limit to top 5
    
    def get_quick_summary(self) -> str:
        """Get a one-line summary of system status."""
        ctx = self.build_context()
        
        if ctx.system_health == "critical":
            if ctx.top_issues:
                return f"⚠️ Critical: {ctx.top_issues[0]}"
            return "⚠️ System requires attention"
        elif ctx.system_health == "warning":
            if ctx.top_issues:
                return f"⚡ Warning: {ctx.top_issues[0]}"
            return "⚡ System has minor issues"
        else:
            return "✅ System is healthy"
    
    def invalidate_cache(self) -> None:
        """Invalidate the cached context."""
        self._cached_context = None
        self._cache_time = None


# Singleton instance
_builder_instance: ChatContextBuilder | None = None


def get_context_builder(
    snapshot_service: Any = None,
    event_repo: Any = None,
    scan_repo: Any = None,
) -> ChatContextBuilder:
    """Get the singleton ChatContextBuilder instance."""
    global _builder_instance
    if _builder_instance is None:
        _builder_instance = ChatContextBuilder(
            snapshot_service=snapshot_service,
            event_repo=event_repo,
            scan_repo=scan_repo,
        )
    elif snapshot_service is not None:
        # Update services if provided
        _builder_instance._snapshot = snapshot_service
    
    return _builder_instance
