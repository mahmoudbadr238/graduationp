"""URL scanner using VirusTotal."""
from typing import Dict, Any
from ..core.interfaces import IUrlScanner
from ..core.errors import IntegrationDisabled


class UrlScanner(IUrlScanner):
    """Scan URLs using VirusTotal API."""
    
    def __init__(self, vt_client):
        """
        Initialize scanner.
        
        Args:
            vt_client: VirusTotalClient instance
        """
        if not vt_client:
            raise IntegrationDisabled("URL scanning requires VirusTotal integration")
        
        self.vt_client = vt_client
    
    def scan_url(self, url: str) -> Dict[str, Any]:
        """
        Scan a URL and return results.
        
        Returns:
            Dict with URL analysis results
        """
        if not url:
            return {
                "error": "URL cannot be empty",
                "url": url
            }
        
        try:
            # First try to get existing report
            report = self.vt_client.get_url_report(url)
            
            if report.get("found"):
                return report
            
            # If not found, submit for analysis
            submission = self.vt_client.scan_url(url)
            
            if submission.get("submitted"):
                return {
                    "url": url,
                    "status": "submitted",
                    "message": "URL submitted for analysis. Check back later for results.",
                    "analysis_id": submission.get("analysis_id", "")
                }
            
            return submission
        
        except IntegrationDisabled as e:
            return {
                "error": str(e),
                "url": url
            }
        except Exception as e:
            return {
                "error": f"Scan failed: {str(e)}",
                "url": url
            }
