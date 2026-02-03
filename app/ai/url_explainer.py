"""
AI-powered URL scan explanation generator.

Produces detailed but simple English explanations of URL scan results,
making security findings accessible to non-technical users.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.scanning.url_scanner import UrlScanResult, Evidence

logger = logging.getLogger(__name__)


@dataclass
class UrlExplanation:
    """Human-readable explanation of URL scan results."""
    
    what_it_is: str          # Brief description of the URL/site
    why_risky: str           # Why it may be dangerous (or safe)
    what_to_do: str          # Recommended action
    technical_summary: str   # Brief technical details
    confidence: str          # How confident we are (low/medium/high)


class UrlExplainer:
    """
    Generates AI-powered explanations for URL scan results.
    
    Uses local LLM when available, falls back to template-based
    explanations when model is unavailable.
    """
    
    def __init__(self, llm_engine=None):
        """
        Initialize the explainer.
        
        Args:
            llm_engine: Optional local LLM engine for AI explanations.
                       Falls back to templates if None.
        """
        self._llm = llm_engine
        self._use_ai = llm_engine is not None
    
    def explain(self, result: "UrlScanResult") -> UrlExplanation:
        """
        Generate explanation for URL scan result.
        
        Args:
            result: The UrlScanResult to explain
            
        Returns:
            UrlExplanation with human-readable analysis
        """
        if self._use_ai:
            try:
                return self._explain_with_ai(result)
            except Exception as e:
                logger.warning(f"AI explanation failed, using templates: {e}")
        
        return self._explain_with_templates(result)
    
    def _explain_with_ai(self, result: "UrlScanResult") -> UrlExplanation:
        """Generate explanation using local LLM."""
        prompt = self._build_prompt(result)
        
        try:
            response = self._llm.generate(prompt, max_tokens=500)
            return self._parse_ai_response(response, result)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
    
    def _build_prompt(self, result: "UrlScanResult") -> str:
        """Build prompt for LLM."""
        evidence_text = "\n".join(
            f"- {e.title}: {e.detail}" 
            for e in result.evidence
        )
        
        redirect_text = " -> ".join(result.redirects) if result.redirects else "None"
        
        ioc_text = ""
        if result.iocs:
            if result.iocs.get("domains"):
                ioc_text += f"Linked domains: {', '.join(result.iocs['domains'][:5])}\n"
            if result.iocs.get("ips"):
                ioc_text += f"IP addresses: {', '.join(result.iocs['ips'][:5])}\n"
        
        prompt = f"""Analyze this URL scan result and explain it in simple English.

URL: {result.normalized_url}
Final URL: {result.final_url}
Redirects: {redirect_text}
Score: {result.score}/100
Verdict: {result.verdict}

Evidence found:
{evidence_text}

{ioc_text}

Provide a brief explanation with:
1. WHAT IT IS: One sentence describing what this URL/website appears to be
2. WHY RISKY: 2-3 sentences explaining why it's safe or dangerous
3. WHAT TO DO: One clear action recommendation
4. CONFIDENCE: How confident is this assessment (low/medium/high)

Keep explanations simple and avoid technical jargon. Be direct and helpful."""

        return prompt
    
    def _parse_ai_response(self, response: str, result: "UrlScanResult") -> UrlExplanation:
        """Parse LLM response into structured explanation."""
        # Simple parsing - look for sections
        what_it_is = self._extract_section(response, "WHAT IT IS", 
            default=self._generate_what_it_is(result))
        why_risky = self._extract_section(response, "WHY RISKY",
            default=self._generate_why_risky(result))
        what_to_do = self._extract_section(response, "WHAT TO DO",
            default=self._generate_what_to_do(result))
        confidence = self._extract_section(response, "CONFIDENCE",
            default=self._assess_confidence(result))
        
        technical = self._generate_technical_summary(result)
        
        return UrlExplanation(
            what_it_is=what_it_is,
            why_risky=why_risky,
            what_to_do=what_to_do,
            technical_summary=technical,
            confidence=confidence
        )
    
    def _extract_section(self, text: str, section: str, default: str) -> str:
        """Extract a section from LLM response."""
        import re
        
        # Try to find "SECTION: content" or "SECTION\ncontent"
        pattern = rf"{section}[:\s]*([^\n]+(?:\n(?![A-Z]+:)[^\n]+)*)"
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            content = match.group(1).strip()
            if content:
                return content
        
        return default
    
    def _explain_with_templates(self, result: "UrlScanResult") -> UrlExplanation:
        """Generate explanation using templates (fallback)."""
        return UrlExplanation(
            what_it_is=self._generate_what_it_is(result),
            why_risky=self._generate_why_risky(result),
            what_to_do=self._generate_what_to_do(result),
            technical_summary=self._generate_technical_summary(result),
            confidence=self._assess_confidence(result)
        )
    
    def _generate_what_it_is(self, result: "UrlScanResult") -> str:
        """Generate 'what it is' description."""
        from urllib.parse import urlparse
        
        parsed = urlparse(result.normalized_url)
        domain = parsed.netloc
        
        # Check for known patterns
        signals = result.signals
        
        if signals.get("is_phishing_url"):
            return f"This appears to be a phishing page hosted at {domain}, designed to steal your information."
        
        if signals.get("has_download_form"):
            return f"This is a file download page at {domain} that may attempt to install software on your computer."
        
        if signals.get("suspicious_tld"):
            tld = domain.split(".")[-1] if "." in domain else ""
            return f"This is a website at {domain} using a high-risk domain extension (.{tld}) often associated with malicious sites."
        
        if signals.get("punycode_domain"):
            return f"This website uses special characters in its domain name ({domain}) which may be an attempt to impersonate a legitimate site."
        
        if signals.get("ip_address_url"):
            return f"This URL points directly to an IP address ({domain}) rather than a normal website domain, which is unusual for legitimate sites."
        
        # Check content type if available
        http = result.http
        if http:
            content_type = http.get("content_type", "")
            if "html" in content_type:
                return f"This is a web page hosted at {domain}."
            elif "javascript" in content_type:
                return f"This URL serves JavaScript code from {domain}."
            elif "json" in content_type:
                return f"This URL serves data (JSON) from {domain}."
            elif any(x in content_type for x in ["pdf", "zip", "exe", "binary"]):
                return f"This URL serves a downloadable file from {domain}."
        
        # Default based on redirect count
        if len(result.redirects) > 2:
            return f"This URL at {domain} redirects through multiple sites before reaching its destination."
        
        return f"This is a web page hosted at {domain}."
    
    def _generate_why_risky(self, result: "UrlScanResult") -> str:
        """Generate 'why risky' explanation based on evidence."""
        if result.verdict == "safe":
            return self._generate_safe_explanation(result)
        
        # Collect risk factors by category
        risk_factors = []
        
        for evidence in result.evidence:
            if evidence.severity in ("high", "critical"):
                risk_factors.append(self._explain_evidence(evidence))
        
        if not risk_factors:
            # Use medium severity evidence
            for evidence in result.evidence:
                if evidence.severity == "medium":
                    risk_factors.append(self._explain_evidence(evidence))
        
        if not risk_factors:
            return "No specific risk factors were identified, but proceed with caution."
        
        # Combine top 3 risk factors
        unique_risks = list(dict.fromkeys(risk_factors))[:3]
        
        if len(unique_risks) == 1:
            return unique_risks[0]
        
        return " ".join(unique_risks)
    
    def _generate_safe_explanation(self, result: "UrlScanResult") -> str:
        """Generate explanation for safe URLs."""
        positive_points = []
        
        http = result.http
        if http:
            if http.get("status_code") == 200:
                positive_points.append("The site loaded normally")
            if result.normalized_url.startswith("https://"):
                positive_points.append("uses secure HTTPS encryption")
        
        if not result.redirects or len(result.redirects) <= 1:
            positive_points.append("doesn't use suspicious redirects")
        
        if not result.evidence:
            positive_points.append("no security concerns were found")
        
        if positive_points:
            return f"This URL appears safe. {', '.join(positive_points).capitalize()}."
        
        return "No concerning indicators were found during analysis."
    
    def _explain_evidence(self, evidence: "Evidence") -> str:
        """Convert technical evidence to plain English."""
        explanations = {
            # Domain/URL structure risks
            "punycode_domain": "The domain uses international characters that may be disguising its true identity.",
            "suspicious_tld": "The domain uses a risky extension commonly associated with spam and malware.",
            "ip_address_url": "Using an IP address instead of a domain name is often a sign of malicious activity.",
            "excessive_subdomains": "The URL has an unusually complex structure that may be trying to hide its true destination.",
            
            # Redirect risks
            "excessive_redirects": "The URL bounces through many sites before reaching its destination, which is suspicious.",
            "cross_domain_redirect": "The URL redirects to a completely different website than expected.",
            "redirect_to_suspicious_tld": "The URL redirects to a website with a risky domain extension.",
            
            # Content risks
            "password_field": "The page asks for passwords, which could be an attempt to steal your credentials.",
            "hidden_form": "The page contains hidden forms that may submit your data without your knowledge.",
            "credential_form": "The page has login forms that may be attempting to phish your credentials.",
            "obfuscated_javascript": "The page contains hidden code that may be doing something malicious.",
            "auto_download": "The page may try to automatically download files to your computer.",
            "external_script": "The page loads code from other websites, which could be malicious.",
            
            # Form/Input risks  
            "credit_card_form": "The page asks for credit card information.",
            "ssn_field": "The page asks for social security numbers.",
            
            # YARA/Pattern matches
            "yara_match": "The page content matches known malicious patterns.",
            "phishing_pattern": "The page shows signs of being a phishing attempt.",
            
            # Sandbox findings
            "sandbox_network_activity": "When visited in a safe environment, the page tried to contact suspicious servers.",
            "sandbox_file_write": "When visited in a safe environment, the page tried to create files on the computer.",
            "sandbox_registry_access": "When visited in a safe environment, the page tried to modify system settings.",
        }
        
        # Try to find matching explanation
        title_lower = evidence.title.lower().replace(" ", "_")
        for key, explanation in explanations.items():
            if key in title_lower:
                return explanation
        
        # Category-based fallback
        category_explanations = {
            "domain": "There are concerns about the website's domain or address.",
            "redirect": "The URL's redirect behavior is suspicious.",
            "content": "The page content contains concerning elements.",
            "form": "The page has forms that may be trying to collect sensitive information.",
            "network": "The page's network activity is suspicious.",
            "sandbox": "Testing in a safe environment revealed concerning behavior.",
        }
        
        for cat, explanation in category_explanations.items():
            if cat in evidence.category.lower():
                return explanation
        
        # Last resort - use the evidence detail
        return evidence.detail
    
    def _generate_what_to_do(self, result: "UrlScanResult") -> str:
        """Generate action recommendation."""
        verdict = result.verdict
        score = result.score
        
        if verdict == "malicious" or score >= 80:
            return "Do NOT visit this URL. It shows strong signs of being malicious. If you've already visited it, run a full security scan on your device."
        
        if verdict == "likely_malicious" or score >= 50:
            return "Avoid visiting this URL. If you must visit it, use a sandboxed browser and don't enter any personal information."
        
        if verdict == "suspicious" or score >= 20:
            return "Be cautious with this URL. Don't enter any passwords or personal information. Consider using a sandbox if you need to visit it."
        
        # Safe
        if result.normalized_url.startswith("http://"):
            return "The URL appears safe, but note it doesn't use HTTPS encryption. Avoid entering sensitive information."
        
        return "This URL appears safe to visit. As always, be cautious about entering sensitive information."
    
    def _generate_technical_summary(self, result: "UrlScanResult") -> str:
        """Generate brief technical summary."""
        parts = []
        
        # HTTP info
        http = result.http
        if http:
            status = http.get("status_code", "unknown")
            parts.append(f"HTTP {status}")
            
            ct = http.get("content_type", "")
            if ct:
                # Simplify content type
                ct = ct.split(";")[0].strip()
                parts.append(ct)
        
        # Redirect chain
        if result.redirects:
            parts.append(f"{len(result.redirects)} redirect(s)")
        
        # Evidence count by severity
        high_count = sum(1 for e in result.evidence if e.severity in ("high", "critical"))
        med_count = sum(1 for e in result.evidence if e.severity == "medium")
        
        if high_count:
            parts.append(f"{high_count} critical finding(s)")
        if med_count:
            parts.append(f"{med_count} warning(s)")
        
        # IOCs
        if result.iocs:
            domain_count = len(result.iocs.get("domains", []))
            ip_count = len(result.iocs.get("ips", []))
            if domain_count or ip_count:
                parts.append(f"{domain_count} linked domains, {ip_count} IPs")
        
        # YARA
        if result.yara_matches:
            parts.append(f"{len(result.yara_matches)} YARA match(es)")
        
        # Sandbox
        if result.sandbox_result:
            parts.append("sandbox tested")
        
        return " | ".join(parts) if parts else "Basic scan completed"
    
    def _assess_confidence(self, result: "UrlScanResult") -> str:
        """Assess confidence level of the analysis."""
        confidence_score = 0
        
        # HTTP response available
        if result.http and result.http.get("status_code"):
            confidence_score += 20
        
        # Content was analyzed
        if result.http and result.http.get("content_length", 0) > 0:
            confidence_score += 20
        
        # Evidence was collected
        if result.evidence:
            confidence_score += 20
            if len(result.evidence) >= 3:
                confidence_score += 10
        
        # Sandbox was run
        if result.sandbox_result:
            confidence_score += 30
        
        # YARA was run
        if result.yara_matches is not None:  # Even empty list means it ran
            confidence_score += 10
        
        if confidence_score >= 70:
            return "high"
        elif confidence_score >= 40:
            return "medium"
        else:
            return "low"


def explain_url_scan(result: "UrlScanResult", llm_engine=None) -> UrlExplanation:
    """
    Convenience function to explain a URL scan result.
    
    Args:
        result: UrlScanResult to explain
        llm_engine: Optional local LLM engine
        
    Returns:
        UrlExplanation with human-readable analysis
    """
    explainer = UrlExplainer(llm_engine)
    return explainer.explain(result)


def explanation_to_dict(explanation: UrlExplanation) -> dict:
    """Convert UrlExplanation to dictionary for QML."""
    return {
        "what_it_is": explanation.what_it_is,
        "why_risky": explanation.why_risky,
        "what_to_do": explanation.what_to_do,
        "technical_summary": explanation.technical_summary,
        "confidence": explanation.confidence,
    }
