"""
Privacy-preserving data redaction for AI payloads.

Ensures no sensitive data is sent to online AI providers.
"""

from __future__ import annotations

import hashlib
import re
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RedactionStats:
    """Statistics about what was redacted."""
    usernames_redacted: int = 0
    ips_redacted: int = 0
    paths_redacted: int = 0
    emails_redacted: int = 0
    domains_redacted: int = 0
    
    @property
    def total_redacted(self) -> int:
        return (
            self.usernames_redacted + 
            self.ips_redacted + 
            self.paths_redacted +
            self.emails_redacted +
            self.domains_redacted
        )


class RedactionEngine:
    """
    Redacts sensitive information from text before sending to online AI.
    
    Patterns redacted:
    - Usernames (Windows format: DOMAIN\\user, user@domain)
    - IP addresses (IPv4 and IPv6)
    - File paths (Windows and Unix)
    - Email addresses
    - Internal domain names
    
    Redaction uses consistent hashing so the same value
    always maps to the same placeholder (e.g., USER_A7F3).
    """
    
    # Common patterns
    WINDOWS_USER = re.compile(
        r'(?:(?:[A-Z][A-Z0-9\-]*\\)?[a-zA-Z][a-zA-Z0-9_\-\.]{2,30})'
        r'(?=\s|$|[,;:\)])',
        re.IGNORECASE
    )
    
    IPV4 = re.compile(
        r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    )
    
    IPV6 = re.compile(
        r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|'
        r'\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b|'
        r'\b::(?:[0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}\b'
    )
    
    WINDOWS_PATH = re.compile(
        r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*',
        re.IGNORECASE
    )
    
    UNIX_PATH = re.compile(
        r'(?:/[a-zA-Z0-9_\-\.]+)+/?'
    )
    
    EMAIL = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )
    
    # Known safe system accounts (don't redact)
    SAFE_ACCOUNTS = {
        "system", "local service", "network service",
        "nt authority", "builtin", "everyone", "administrators",
        "users", "guests", "authenticated users", "interactive",
    }
    
    # Known safe paths (don't redact)
    SAFE_PATHS = {
        "c:\\windows", "c:\\program files", "c:\\program files (x86)",
        "/usr", "/bin", "/sbin", "/etc", "/var", "/tmp",
    }
    
    def __init__(
        self,
        redact_usernames: bool = True,
        redact_ips: bool = True,
        redact_paths: bool = True,
        redact_emails: bool = True,
    ):
        self.redact_usernames = redact_usernames
        self.redact_ips = redact_ips
        self.redact_paths = redact_paths
        self.redact_emails = redact_emails
        
        # Mapping of original values to placeholders
        self._mapping: dict[str, str] = {}
        self._stats = RedactionStats()
    
    def _make_placeholder(self, value: str, prefix: str) -> str:
        """Create a consistent placeholder for a value."""
        if value in self._mapping:
            return self._mapping[value]
        
        # Use first 4 chars of MD5 for uniqueness
        hash_suffix = hashlib.md5(value.lower().encode()).hexdigest()[:4].upper()
        placeholder = f"{prefix}_{hash_suffix}"
        self._mapping[value] = placeholder
        return placeholder
    
    def _is_safe_account(self, account: str) -> bool:
        """Check if account is a known safe system account."""
        return account.lower() in self.SAFE_ACCOUNTS
    
    def _is_safe_path(self, path: str) -> bool:
        """Check if path is a known safe system path."""
        path_lower = path.lower()
        for safe in self.SAFE_PATHS:
            if path_lower.startswith(safe):
                return True
        return False
    
    def redact(self, text: str) -> tuple[str, RedactionStats]:
        """
        Redact sensitive information from text.
        
        Args:
            text: The text to redact
        
        Returns:
            Tuple of (redacted_text, stats)
        """
        if not text:
            return text, RedactionStats()
        
        self._stats = RedactionStats()
        result = text
        
        # Redact IPs first (most specific)
        if self.redact_ips:
            # IPv4
            for match in self.IPV4.finditer(result):
                ip = match.group()
                if not ip.startswith("127.") and not ip.startswith("0."):
                    placeholder = self._make_placeholder(ip, "IP")
                    result = result.replace(ip, placeholder)
                    self._stats.ips_redacted += 1
            
            # IPv6
            for match in self.IPV6.finditer(result):
                ip = match.group()
                if ip != "::1":  # Keep localhost
                    placeholder = self._make_placeholder(ip, "IP")
                    result = result.replace(ip, placeholder)
                    self._stats.ips_redacted += 1
        
        # Redact emails
        if self.redact_emails:
            for match in self.EMAIL.finditer(result):
                email = match.group()
                placeholder = self._make_placeholder(email, "EMAIL")
                result = result.replace(email, placeholder)
                self._stats.emails_redacted += 1
        
        # Redact paths
        if self.redact_paths:
            # Windows paths
            for match in self.WINDOWS_PATH.finditer(result):
                path = match.group()
                if not self._is_safe_path(path):
                    placeholder = self._make_placeholder(path, "PATH")
                    result = result.replace(path, placeholder)
                    self._stats.paths_redacted += 1
            
            # Unix paths (be more selective - many false positives)
            for match in self.UNIX_PATH.finditer(result):
                path = match.group()
                if not self._is_safe_path(path) and len(path) > 10:
                    placeholder = self._make_placeholder(path, "PATH")
                    result = result.replace(path, placeholder)
                    self._stats.paths_redacted += 1
        
        return result, self._stats
    
    def get_mapping(self) -> dict[str, str]:
        """Get the value-to-placeholder mapping (for debugging)."""
        return dict(self._mapping)
    
    def clear(self) -> None:
        """Clear the mapping and stats."""
        self._mapping.clear()
        self._stats = RedactionStats()


def redact_sensitive(
    data: dict[str, Any],
    redact_usernames: bool = True,
    redact_ips: bool = True,
    redact_paths: bool = True,
) -> tuple[dict[str, Any], RedactionStats]:
    """
    Redact sensitive information from a data dict.
    
    Recursively processes all string values.
    
    Args:
        data: The data to redact
        redact_*: Which types to redact
    
    Returns:
        Tuple of (redacted_data, stats)
    """
    engine = RedactionEngine(
        redact_usernames=redact_usernames,
        redact_ips=redact_ips,
        redact_paths=redact_paths,
    )
    
    total_stats = RedactionStats()
    
    def process(obj: Any) -> Any:
        nonlocal total_stats
        
        if isinstance(obj, str):
            redacted, stats = engine.redact(obj)
            total_stats.ips_redacted += stats.ips_redacted
            total_stats.paths_redacted += stats.paths_redacted
            total_stats.emails_redacted += stats.emails_redacted
            return redacted
        
        elif isinstance(obj, dict):
            return {k: process(v) for k, v in obj.items()}
        
        elif isinstance(obj, list):
            return [process(item) for item in obj]
        
        return obj
    
    return process(data), total_stats
