"""Nmap CLI wrapper for network scanning."""
import os
import subprocess
from typing import Dict, Any
from ..core.interfaces import INetworkScanner
from ..core.errors import ExternalToolMissing, IntegrationDisabled
from ..config.settings import get_settings


class NmapCli(INetworkScanner):
    """Network scanner using local Nmap CLI."""
    
    def __init__(self):
        settings = get_settings()
        
        # Check if offline mode
        if settings.offline_only:
            raise IntegrationDisabled("Network scanning disabled in offline mode")
        
        # Find nmap executable
        self.nmap_path = settings.nmap_path or self._find_nmap()
        if not self.nmap_path:
            raise ExternalToolMissing("Nmap not found. Install from https://nmap.org/")
    
    def scan(self, target: str, fast: bool = True) -> Dict[str, Any]:
        """
        Run nmap scan on target.
        
        Args:
            target: IP address, hostname, or CIDR range
            fast: If True, use quick scan (-F). If False, use comprehensive scan.
        
        Returns:
            Dict with scan results including hosts, ports, and services
        """
        # Build nmap command
        cmd = [self.nmap_path]
        
        if fast:
            # Fast scan: top 100 ports
            cmd.extend(["-F", "-T4"])
        else:
            # Comprehensive scan: service detection
            cmd.extend(["-sV", "-T3"])
        
        # Always get XML output for parsing
        cmd.extend(["-oX", "-", target])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=True
            )
            
            # Parse XML output (simplified - in production use python-nmap)
            return self._parse_output(result.stdout, target)
        
        except subprocess.TimeoutExpired:
            return {
                "target": target,
                "status": "timeout",
                "error": "Scan timed out after 5 minutes",
                "hosts": []
            }
        except subprocess.CalledProcessError as e:
            return {
                "target": target,
                "status": "error",
                "error": f"Nmap failed: {e.stderr}",
                "hosts": []
            }
        except Exception as e:
            return {
                "target": target,
                "status": "error",
                "error": str(e),
                "hosts": []
            }
    
    def _find_nmap(self) -> str:
        """Try to find nmap in common locations."""
        # Check PATH
        try:
            result = subprocess.run(
                ["nmap", "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return "nmap"
        except:
            pass
        
        # Check common Windows install locations
        common_paths = [
            r"C:\Program Files (x86)\Nmap\nmap.exe",
            r"C:\Program Files\Nmap\nmap.exe",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        return ""
    
    def _parse_output(self, xml_output: str, target: str) -> Dict[str, Any]:
        """Parse nmap XML output (simplified version)."""
        # In production, use python-nmap or xml.etree for proper parsing
        # This is a simplified version that just checks if scan completed
        
        hosts = []
        
        # Simple check for host up
        if "Host is up" in xml_output or "<status state=\"up\"" in xml_output:
            # Extract basic info (this is very simplified)
            ports_found = xml_output.count("<port ")
            
            hosts.append({
                "address": target,
                "status": "up",
                "ports_found": ports_found,
            })
        
        return {
            "target": target,
            "status": "completed",
            "hosts": hosts,
            "raw_output": xml_output[:1000],  # First 1000 chars
        }
