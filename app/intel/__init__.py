"""
Intel Module - External Threat Intelligence Integration
========================================================

This module provides secure, privacy-respecting integration with external
threat intelligence services:

- VirusTotal (file hash + URL lookups)
- AbuseIPDB (IP reputation)
- urlscan.io (URL analysis)

CRITICAL PRIVACY RULES:
1. Only HASHES are sent for files - NEVER file content
2. API keys are never logged
3. User consent required for any network call
4. All results cached to minimize external calls
5. Offline mode works without any of this

Usage:
    from app.intel import get_virustotal_client, ThreatVerdict
    
    client = get_virustotal_client()
    result = await client.check_file_hash(sha256_hash)
    print(result.verdict)  # CLEAN, SUSPICIOUS, MALICIOUS, UNKNOWN
"""

from .providers import (
    ThreatVerdict,
    IntelProvider,
    VirusTotalClient,
    get_virustotal_client,
)

from .cache import IntelCache, get_intel_cache

__all__ = [
    "ThreatVerdict",
    "IntelProvider", 
    "VirusTotalClient",
    "get_virustotal_client",
    "IntelCache",
    "get_intel_cache",
]
