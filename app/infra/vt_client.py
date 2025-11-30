"""VirusTotal API client with file upload, rate limiting, and retry logic."""

import base64
import logging
import time
from typing import Any, Optional

import requests

from ..config.settings import get_settings
from ..core.errors import IntegrationDisabled

logger = logging.getLogger(__name__)

# Rate limiting configuration
REQUEST_RATE_LIMIT = 4  # 4 requests per minute (free tier limit)
RATE_LIMIT_WINDOW = 60  # seconds
REQUEST_TIMEOUT = 30  # seconds per request
MAX_FILE_SIZE = 650 * 1024 * 1024  # 650 MB max for file upload
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 1.5  # Exponential backoff multiplier


class VirusTotalClient:
    """Client for VirusTotal REST API v3 with rate limiting and error recovery."""

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

        # Rate limiting state
        self._request_times: list[float] = []
        self._last_error: Optional[str] = None
        logger.info("VirusTotal client initialized")

    def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting to stay within API quota."""
        now = time.time()
        # Remove old requests outside the window
        self._request_times = [
            t for t in self._request_times if now - t < RATE_LIMIT_WINDOW
        ]

        # If we've hit the limit, wait
        if len(self._request_times) >= REQUEST_RATE_LIMIT:
            sleep_time = RATE_LIMIT_WINDOW - (now - self._request_times[0])
            if sleep_time > 0:
                logger.debug(f"Rate limit reached, sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
                # Recalculate after sleep
                self._enforce_rate_limit()
                return

        self._request_times.append(now)

    def _request_with_retry(
        self, method: str, url: str, **kwargs
    ) -> Optional[requests.Response]:
        """Make HTTP request with retry logic and timeout."""
        for attempt in range(RETRY_ATTEMPTS):
            try:
                self._enforce_rate_limit()

                if method.upper() == "GET":
                    response = self.session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
                elif method.upper() == "POST":
                    response = self.session.post(url, timeout=REQUEST_TIMEOUT, **kwargs)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                response.raise_for_status()
                return response

            except requests.Timeout:
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{RETRY_ATTEMPTS} for {url}"
                )
                if attempt < RETRY_ATTEMPTS - 1:
                    wait_time = RETRY_BACKOFF**attempt
                    time.sleep(wait_time)
                continue

            except requests.HTTPError as e:
                # 429 = rate limited, 503 = service unavailable
                if e.response.status_code in (429, 503):
                    logger.warning(
                        f"Service throttling (HTTP {e.response.status_code}), retrying..."
                    )
                    if attempt < RETRY_ATTEMPTS - 1:
                        wait_time = RETRY_BACKOFF**attempt
                        time.sleep(wait_time)
                    continue
                # Other HTTP errors - don't retry
                logger.error(f"HTTP error {e.response.status_code}: {e}")
                self._last_error = str(e)
                return None

            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                self._last_error = str(e)
                if attempt < RETRY_ATTEMPTS - 1:
                    wait_time = RETRY_BACKOFF**attempt
                    time.sleep(wait_time)
                    continue
                return None

        logger.error(f"Request failed after {RETRY_ATTEMPTS} attempts")
        return None

    def scan_file_hash(self, sha256: str) -> dict[str, Any]:
        """
        Check file reputation by SHA256 hash with retry logic.

        Args:
            sha256: File SHA256 hash

        Returns:
            Dict with analysis results including detection stats
        """
        try:
            url = f"{self.BASE_URL}/files/{sha256}"
            response = self._request_with_retry("GET", url)

            if not response:
                return {"error": self._last_error or "Request failed", "sha256": sha256}

            if response.status_code == 404:
                return {
                    "found": False,
                    "sha256": sha256,
                    "message": "File not found in VirusTotal database",
                }

            data = response.json()

            # Extract key information
            attributes = data.get("data", {}).get("attributes", {})
            stats = attributes.get("last_analysis_stats", {})

            logger.debug(f"Hash analysis for {sha256}: {stats}")
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

        except Exception as e:
            logger.error(f"Error scanning hash {sha256}: {e}")
            return {"error": f"VirusTotal error: {e!s}", "sha256": sha256}

    def scan_file_upload(self, file_path: str) -> dict[str, Any]:
        """
        Upload file to VirusTotal for scanning.

        Args:
            file_path: Path to file to scan

        Returns:
            Dict with submission status and analysis ID
        """
        try:
            import os

            # Validate file
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return {"error": "File not found", "file": file_path}

            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                logger.error(f"File too large: {file_size} > {MAX_FILE_SIZE}")
                return {
                    "error": f"File too large (max {MAX_FILE_SIZE/1024/1024}MB)",
                    "file": file_path,
                }

            logger.info(f"Uploading file {file_path} ({file_size} bytes)")

            # Upload file
            url = f"{self.BASE_URL}/files"
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = self._request_with_retry("POST", url, files=files)

            if not response:
                return {"error": self._last_error or "Upload failed", "file": file_path}

            data = response.json()
            analysis_id = data.get("data", {}).get("id", "")

            logger.info(f"File uploaded successfully: {analysis_id}")
            return {
                "submitted": True,
                "file": file_path,
                "file_size": file_size,
                "analysis_id": analysis_id,
                "message": "File submitted for analysis",
            }

        except Exception as e:
            logger.error(f"Error uploading file {file_path}: {e}")
            return {"error": f"Upload error: {e!s}", "file": file_path}

    def scan_url(self, url: str) -> dict[str, Any]:
        """
        Submit URL for scanning with rate limiting.

        Returns:
            Dict with scan submission status
        """
        try:
            endpoint = f"{self.BASE_URL}/urls"
            response = self._request_with_retry("POST", endpoint, data={"url": url})

            if not response:
                return {"error": self._last_error or "Request failed", "url": url}

            data = response.json()
            analysis_id = data.get("data", {}).get("id", "")

            logger.debug(f"URL submitted: {url} -> {analysis_id}")
            return {
                "submitted": True,
                "url": url,
                "analysis_id": analysis_id,
                "message": "URL submitted for analysis",
            }

        except Exception as e:
            logger.error(f"Error submitting URL {url}: {e}")
            return {"error": f"VirusTotal error: {e!s}", "url": url}

    def get_url_report(self, url: str) -> dict[str, Any]:
        """
        Get existing URL analysis report with retry logic.

        Returns:
            Dict with analysis results
        """
        try:
            # URL needs to be base64 encoded (without padding)
            url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")

            endpoint = f"{self.BASE_URL}/urls/{url_id}"
            response = self._request_with_retry("GET", endpoint)

            if not response:
                return {"error": self._last_error or "Request failed", "url": url}

            if response.status_code == 404:
                logger.debug(f"URL report not found: {url}")
                return {
                    "found": False,
                    "url": url,
                    "message": "URL not found in VirusTotal database",
                }

            data = response.json()

            # Extract key information
            attributes = data.get("data", {}).get("attributes", {})
            stats = attributes.get("last_analysis_stats", {})

            logger.debug(f"URL analysis for {url}: {stats}")
            return {
                "found": True,
                "url": url,
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "undetected": stats.get("undetected", 0),
                "harmless": stats.get("harmless", 0),
            }

        except Exception as e:
            logger.error(f"Error getting URL report {url}: {e}")
            return {"error": f"VirusTotal error: {e!s}", "url": url}

    def get_analysis_result(self, analysis_id: str) -> dict[str, Any]:
        """
        Get analysis result by ID (for uploaded files or URLs).

        Args:
            analysis_id: Analysis ID returned from submission

        Returns:
            Dict with analysis status and results
        """
        try:
            endpoint = f"{self.BASE_URL}/analyses/{analysis_id}"
            response = self._request_with_retry("GET", endpoint)

            if not response:
                return {
                    "error": self._last_error or "Request failed",
                    "analysis_id": analysis_id,
                }

            data = response.json()
            attributes = data.get("data", {}).get("attributes", {})
            status = attributes.get("status", "unknown")
            stats = attributes.get("stats", {})

            return {
                "analysis_id": analysis_id,
                "status": status,
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "undetected": stats.get("undetected", 0),
                "harmless": stats.get("harmless", 0),
            }

        except Exception as e:
            logger.error(f"Error getting analysis result {analysis_id}: {e}")
            return {"error": f"VirusTotal error: {e!s}", "analysis_id": analysis_id}
