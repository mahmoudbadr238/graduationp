"""VirusTotal API client."""

from typing import Any

import requests

from ..config.settings import get_settings
from ..core.errors import IntegrationDisabled


class VirusTotalClient:
    """Client for VirusTotal REST API v3."""

    BASE_URL = "https://www.virustotal.com/api/v3"

    def __init__(self):
        settings = get_settings()

        # Check if offline mode or no API key
        if settings.offline_only:
            raise IntegrationDisabled("VirusTotal disabled in offline mode")

        self.api_key = settings.vt_api_key
        if not self.api_key:
            raise IntegrationDisabled("VirusTotal API key not configured")

        self.session = requests.Session()
        self.session.headers.update(
            {"x-apikey": self.api_key, "Accept": "application/json"}
        )

    def scan_file_hash(self, sha256: str) -> dict[str, Any]:
        """
        Check file reputation by SHA256 hash.

        Returns:
            Dict with analysis results including detection stats
        """
        try:
            url = f"{self.BASE_URL}/files/{sha256}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 404:
                return {
                    "found": False,
                    "sha256": sha256,
                    "message": "File not found in VirusTotal database",
                }

            response.raise_for_status()
            data = response.json()

            # Extract key information
            attributes = data.get("data", {}).get("attributes", {})
            stats = attributes.get("last_analysis_stats", {})

            return {
                "found": True,
                "sha256": sha256,
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "undetected": stats.get("undetected", 0),
                "harmless": stats.get("harmless", 0),
                "reputation": attributes.get("reputation", 0),
                "popular_threat_name": attributes.get(
                    "popular_threat_classification", {}
                ).get("suggested_threat_label", ""),
            }

        except requests.RequestException as e:
            return {"error": f"VirusTotal API error: {e!s}", "sha256": sha256}

    def scan_url(self, url: str) -> dict[str, Any]:
        """
        Submit URL for scanning.

        Returns:
            Dict with scan submission status
        """
        try:
            endpoint = f"{self.BASE_URL}/urls"
            response = self.session.post(endpoint, data={"url": url}, timeout=10)
            response.raise_for_status()

            data = response.json()
            analysis_id = data.get("data", {}).get("id", "")

            return {
                "submitted": True,
                "url": url,
                "analysis_id": analysis_id,
                "message": "URL submitted for analysis",
            }

        except requests.RequestException as e:
            return {"error": f"VirusTotal API error: {e!s}", "url": url}

    def get_url_report(self, url: str) -> dict[str, Any]:
        """
        Get existing URL analysis report.

        Returns:
            Dict with analysis results
        """
        try:
            # URL needs to be base64 encoded (without padding)
            import base64

            url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")

            endpoint = f"{self.BASE_URL}/urls/{url_id}"
            response = self.session.get(endpoint, timeout=10)

            if response.status_code == 404:
                return {
                    "found": False,
                    "url": url,
                    "message": "URL not found in VirusTotal database",
                }

            response.raise_for_status()
            data = response.json()

            # Extract key information
            attributes = data.get("data", {}).get("attributes", {})
            stats = attributes.get("last_analysis_stats", {})

            return {
                "found": True,
                "url": url,
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "undetected": stats.get("undetected", 0),
                "harmless": stats.get("harmless", 0),
            }

        except requests.RequestException as e:
            return {"error": f"VirusTotal API error: {e!s}", "url": url}
