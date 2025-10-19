"""Custom exceptions for Sentinel."""


class SentinelError(Exception):
    """Base exception for all Sentinel errors."""
    pass


class IntegrationDisabled(SentinelError):
    """Raised when a required integration is disabled."""
    pass


class ExternalToolMissing(SentinelError):
    """Raised when an external tool (like nmap) is not found."""
    pass
