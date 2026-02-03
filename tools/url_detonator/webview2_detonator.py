"""
WebView2-based URL detonation sandbox for Windows.

Uses Microsoft Edge WebView2 control in headless mode to safely visit
URLs and monitor for malicious behavior.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class DetonationConfig:
    """Configuration for URL detonation."""
    
    timeout_seconds: int = 30
    block_downloads: bool = True
    block_popups: bool = True
    block_navigation_away: bool = False
    capture_screenshot: bool = True
    capture_network: bool = True
    capture_console: bool = True
    user_agent: Optional[str] = None


@dataclass
class NetworkRequest:
    """Captured network request during detonation."""
    
    url: str
    method: str
    resource_type: str
    timestamp: float
    status_code: Optional[int] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    blocked: bool = False


@dataclass
class ConsoleMessage:
    """Captured console message during detonation."""
    
    level: str  # log, warn, error
    message: str
    timestamp: float
    source: str = ""


@dataclass 
class DetonationResult:
    """Result of URL detonation in sandbox."""
    
    url: str
    final_url: str
    success: bool
    error: Optional[str] = None
    
    # Page info
    page_title: str = ""
    load_time_ms: int = 0
    
    # Captured data
    network_requests: List[NetworkRequest] = field(default_factory=list)
    console_messages: List[ConsoleMessage] = field(default_factory=list)
    screenshot_path: Optional[str] = None
    
    # Behavioral signals
    download_attempts: List[str] = field(default_factory=list)
    popup_attempts: int = 0
    navigation_blocked: int = 0
    external_domains: List[str] = field(default_factory=list)
    
    # JavaScript findings
    eval_calls: int = 0
    document_writes: int = 0
    obfuscated_code: bool = False
    
    # Timing
    start_time: float = 0
    end_time: float = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "final_url": self.final_url,
            "success": self.success,
            "error": self.error,
            "page_title": self.page_title,
            "load_time_ms": self.load_time_ms,
            "network_requests": [
                {
                    "url": r.url,
                    "method": r.method,
                    "resource_type": r.resource_type,
                    "status_code": r.status_code,
                    "blocked": r.blocked,
                }
                for r in self.network_requests
            ],
            "console_messages": [
                {
                    "level": m.level,
                    "message": m.message,
                    "source": m.source,
                }
                for m in self.console_messages
            ],
            "screenshot_path": self.screenshot_path,
            "download_attempts": self.download_attempts,
            "popup_attempts": self.popup_attempts,
            "navigation_blocked": self.navigation_blocked,
            "external_domains": self.external_domains,
            "eval_calls": self.eval_calls,
            "document_writes": self.document_writes,
            "obfuscated_code": self.obfuscated_code,
            "duration_seconds": self.end_time - self.start_time if self.end_time else 0,
        }


class WebView2Detonator:
    """
    WebView2-based URL sandbox detonator.
    
    Uses Edge WebView2 to visit URLs in a controlled environment and
    capture behavior for analysis.
    """
    
    # Known external CDNs to ignore
    KNOWN_CDNS = {
        "cdnjs.cloudflare.com",
        "cdn.jsdelivr.net",
        "unpkg.com",
        "ajax.googleapis.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "maxcdn.bootstrapcdn.com",
        "stackpath.bootstrapcdn.com",
        "code.jquery.com",
    }
    
    def __init__(self, config: Optional[DetonationConfig] = None):
        """
        Initialize the detonator.
        
        Args:
            config: Detonation configuration options
        """
        self.config = config or DetonationConfig()
        self._webview_available = None
        self._temp_dir = None
    
    def is_available(self) -> bool:
        """Check if WebView2 runtime is available."""
        if self._webview_available is not None:
            return self._webview_available
        
        if sys.platform != "win32":
            self._webview_available = False
            return False
        
        try:
            # Check for WebView2 runtime via registry or file
            import winreg
            
            # Try to find WebView2 installation
            keys_to_check = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
            ]
            
            for root, subkey in keys_to_check:
                try:
                    with winreg.OpenKey(root, subkey) as key:
                        version = winreg.QueryValueEx(key, "pv")[0]
                        if version:
                            logger.info(f"WebView2 runtime found: {version}")
                            self._webview_available = True
                            return True
                except (OSError, FileNotFoundError):
                    continue
            
            # Fallback: Check if Edge is installed
            edge_path = Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if edge_path.exists():
                logger.info("Edge browser found, WebView2 likely available")
                self._webview_available = True
                return True
            
            self._webview_available = False
            return False
            
        except Exception as e:
            logger.warning(f"Error checking WebView2 availability: {e}")
            self._webview_available = False
            return False
    
    def detonate(self, url: str) -> DetonationResult:
        """
        Detonate (safely visit) a URL in the sandbox.
        
        Args:
            url: The URL to visit
            
        Returns:
            DetonationResult with captured behavior
        """
        result = DetonationResult(
            url=url,
            final_url=url,
            success=False,
            start_time=time.time()
        )
        
        if not self.is_available():
            result.error = "WebView2 runtime not available"
            result.end_time = time.time()
            return result
        
        try:
            # Try to use webview2 Python bindings if available
            return self._detonate_with_pywebview(url, result)
        except ImportError:
            logger.info("pywebview not available, using Edge DevTools Protocol")
            return self._detonate_with_edge_cdp(url, result)
        except Exception as e:
            logger.warning(f"pywebview failed, trying Edge CDP: {e}")
            return self._detonate_with_edge_cdp(url, result)
    
    def _detonate_with_pywebview(self, url: str, result: DetonationResult) -> DetonationResult:
        """Detonate using pywebview library."""
        import webview
        
        # Create temp dir for output
        self._temp_dir = tempfile.mkdtemp(prefix="sentinel_detonate_")
        
        # Track state
        state = {
            "loaded": False,
            "network_requests": [],
            "console_messages": [],
            "download_attempts": [],
            "popup_attempts": 0,
            "final_url": url,
            "page_title": "",
        }
        
        def on_loaded():
            """Called when page is loaded."""
            state["loaded"] = True
            try:
                state["final_url"] = window.get_current_url()
                state["page_title"] = window.evaluate_js("document.title") or ""
                
                # Inject monitoring script
                self._inject_monitor_script(window)
                
            except Exception as e:
                logger.warning(f"Error in on_loaded: {e}")
        
        def on_closing():
            """Called when window is closing."""
            pass
        
        # Create window with restrictions
        window = webview.create_window(
            title="Sentinel URL Sandbox",
            url=url,
            width=1280,
            height=720,
            resizable=False,
            fullscreen=False,
            hidden=True,  # Headless
            frameless=True,
        )
        
        # Set up event handlers
        window.events.loaded += on_loaded
        window.events.closing += on_closing
        
        # Run with timeout
        def run_webview():
            webview.start(debug=False)
        
        thread = threading.Thread(target=run_webview)
        thread.start()
        thread.join(timeout=self.config.timeout_seconds)
        
        # If still running, force close
        if thread.is_alive():
            try:
                window.destroy()
            except Exception:
                pass
        
        # Collect results
        result.success = state["loaded"]
        result.final_url = state["final_url"]
        result.page_title = state["page_title"]
        result.network_requests = [
            NetworkRequest(**r) for r in state["network_requests"]
        ]
        result.console_messages = [
            ConsoleMessage(**m) for m in state["console_messages"]
        ]
        result.download_attempts = state["download_attempts"]
        result.popup_attempts = state["popup_attempts"]
        result.end_time = time.time()
        result.load_time_ms = int((result.end_time - result.start_time) * 1000)
        
        return result
    
    def _detonate_with_edge_cdp(self, url: str, result: DetonationResult) -> DetonationResult:
        """
        Detonate using Edge with Chrome DevTools Protocol.
        
        Falls back to basic headless Edge if CDP isn't available.
        """
        try:
            # Find Edge executable
            edge_paths = [
                Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            ]
            
            edge_exe = None
            for path in edge_paths:
                if path.exists():
                    edge_exe = path
                    break
            
            if not edge_exe:
                result.error = "Microsoft Edge not found"
                result.end_time = time.time()
                return result
            
            # Create temp user data dir for isolation
            temp_profile = tempfile.mkdtemp(prefix="sentinel_edge_")
            
            # Build command
            cmd = [
                str(edge_exe),
                "--headless",
                "--disable-gpu",
                f"--user-data-dir={temp_profile}",
                "--no-first-run",
                "--disable-extensions",
                "--disable-popup-blocking" if not self.config.block_popups else "--block-new-web-contents",
                "--disable-translate",
                "--disable-sync",
                "--disable-background-networking",
                "--safebrowsing-disable-download-protection",
                f"--timeout={self.config.timeout_seconds * 1000}",
            ]
            
            if self.config.block_downloads:
                cmd.append("--disable-download-notification")
            
            if self.config.user_agent:
                cmd.append(f"--user-agent={self.config.user_agent}")
            
            cmd.append(url)
            
            # Run Edge with timeout
            try:
                start = time.time()
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=self.config.timeout_seconds + 5,
                    text=True,
                )
                
                result.success = True
                result.load_time_ms = int((time.time() - start) * 1000)
                result.final_url = url  # Can't easily get final URL in headless mode
                
                # Parse any output for errors/warnings
                if process.stderr:
                    for line in process.stderr.split("\n"):
                        if line.strip():
                            result.console_messages.append(
                                ConsoleMessage(
                                    level="error" if "error" in line.lower() else "log",
                                    message=line.strip(),
                                    timestamp=time.time(),
                                    source="edge"
                                )
                            )
                
            except subprocess.TimeoutExpired:
                result.error = "Timeout waiting for page to load"
                result.success = False
            except Exception as e:
                result.error = f"Edge execution failed: {e}"
                result.success = False
            
            finally:
                # Cleanup temp profile
                try:
                    import shutil
                    shutil.rmtree(temp_profile, ignore_errors=True)
                except Exception:
                    pass
            
            result.end_time = time.time()
            return result
            
        except Exception as e:
            result.error = f"Edge CDP detonation failed: {e}"
            result.end_time = time.time()
            return result
    
    def _inject_monitor_script(self, window) -> None:
        """Inject JavaScript to monitor page behavior."""
        script = """
        (function() {
            // Track eval calls
            var originalEval = window.eval;
            window.__evalCount = 0;
            window.eval = function(code) {
                window.__evalCount++;
                return originalEval.call(this, code);
            };
            
            // Track document.write
            var originalWrite = document.write;
            window.__documentWriteCount = 0;
            document.write = function(html) {
                window.__documentWriteCount++;
                return originalWrite.call(this, html);
            };
            
            // Track popups
            window.__popupCount = 0;
            window.open = function() {
                window.__popupCount++;
                return null;
            };
            
            // Track downloads (anchor clicks with download attribute)
            document.addEventListener('click', function(e) {
                if (e.target.tagName === 'A' && e.target.hasAttribute('download')) {
                    window.__downloadAttempts = window.__downloadAttempts || [];
                    window.__downloadAttempts.push(e.target.href);
                }
            }, true);
        })();
        """
        
        try:
            window.evaluate_js(script)
        except Exception as e:
            logger.warning(f"Failed to inject monitor script: {e}")
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc
        except Exception:
            return ""


def detonate_url(url: str, config: Optional[DetonationConfig] = None) -> DetonationResult:
    """
    Convenience function to detonate a URL.
    
    Args:
        url: URL to detonate
        config: Optional detonation configuration
        
    Returns:
        DetonationResult with captured behavior
    """
    detonator = WebView2Detonator(config)
    return detonator.detonate(url)


def check_webview2_available() -> bool:
    """Check if WebView2 is available on this system."""
    return WebView2Detonator().is_available()


def detonation_result_to_evidence(result: DetonationResult) -> List[dict]:
    """
    Convert detonation result to evidence list for scoring.
    
    Args:
        result: DetonationResult from detonation
        
    Returns:
        List of evidence dicts compatible with scoring
    """
    evidence = []
    
    if result.download_attempts:
        evidence.append({
            "title": "Download Attempt",
            "severity": "high",
            "detail": f"Page attempted to download {len(result.download_attempts)} file(s): {', '.join(result.download_attempts[:3])}",
            "category": "sandbox"
        })
    
    if result.popup_attempts > 0:
        evidence.append({
            "title": "Popup Blocked",
            "severity": "medium",
            "detail": f"Page attempted to open {result.popup_attempts} popup window(s)",
            "category": "sandbox"
        })
    
    if result.eval_calls > 5:
        evidence.append({
            "title": "Excessive Eval Usage",
            "severity": "medium",
            "detail": f"Page called eval() {result.eval_calls} times, indicating possible obfuscation",
            "category": "sandbox"
        })
    
    if result.document_writes > 3:
        evidence.append({
            "title": "Document Write Usage",
            "severity": "low",
            "detail": f"Page used document.write() {result.document_writes} times",
            "category": "sandbox"
        })
    
    if result.obfuscated_code:
        evidence.append({
            "title": "Obfuscated JavaScript",
            "severity": "high",
            "detail": "Page contains heavily obfuscated JavaScript code",
            "category": "sandbox"
        })
    
    # Check for suspicious external domains
    suspicious_externals = [
        d for d in result.external_domains
        if d not in WebView2Detonator.KNOWN_CDNS
    ]
    if len(suspicious_externals) > 5:
        evidence.append({
            "title": "Many External Domains",
            "severity": "medium",
            "detail": f"Page connects to {len(suspicious_externals)} external domains: {', '.join(suspicious_externals[:5])}...",
            "category": "sandbox"
        })
    
    # Check console errors
    errors = [m for m in result.console_messages if m.level == "error"]
    if len(errors) > 10:
        evidence.append({
            "title": "Many Console Errors",
            "severity": "low",
            "detail": f"Page generated {len(errors)} JavaScript errors",
            "category": "sandbox"
        })
    
    return evidence
