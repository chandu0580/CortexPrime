"""
Safety Guard Engine  (CortexPrime)
====================================
Validates every agent action against URL allowlists / blocklists,
domain rules, dangerous-operation patterns, and action classifications.

Risk levels
-----------
CRITICAL  — must never run without explicit human approval
HIGH      — requires human approval before execution
MEDIUM    — advisory warning; logged; can be auto-approved per policy
LOW       — routine action; no gate needed
NONE      — completely safe; informational only
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# =========================================================
# RISK LEVELS
# =========================================================

class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    NONE     = "none"


RISK_RANK = {
    RiskLevel.CRITICAL: 4,
    RiskLevel.HIGH:     3,
    RiskLevel.MEDIUM:   2,
    RiskLevel.LOW:      1,
    RiskLevel.NONE:     0,
}


# =========================================================
# ASSESSMENT RESULT
# =========================================================

@dataclass
class SafetyAssessment:
    risk_level:         RiskLevel
    requires_approval:  bool
    reason:             str
    matched_patterns:   List[str]    = field(default_factory=list)
    blocked:            bool         = False
    action:             str          = ""
    target:             str          = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "risk_level":        self.risk_level.value,
            "requires_approval": self.requires_approval,
            "reason":            self.reason,
            "matched_patterns":  self.matched_patterns,
            "blocked":           self.blocked,
            "action":            self.action,
            "target":            self.target,
        }


# =========================================================
# PATTERN TABLES
# =========================================================

# Patterns that raise to CRITICAL (blocked by default)
_CRITICAL_PATTERNS: List[str] = [
    r"\bformat\s+disk\b",
    r"\brm\s+-rf\b",
    r"\brmdir\s+/s\b",
    r"\bdrop\s+(database|table|schema)\b",
    r"\bdelete\s+all\b",
    r"\bwipe\s+(drive|disk|all)\b",
    r"\boverwrite\s+(system|os|boot)\b",
    r"\bkill\s+(all|processes)\b",
    r"\bshutdown\s+system\b",
    r"\breboot\s+server\b",
    r"\bexfiltrate\b",
    r"\bransomware\b",
    r"\bmalware\b",
    r"\bbypass\s+(auth|authentication|security)\b",
    r"\b(steal|harvest)\s+(credential|password|token)\b",
]

# Patterns that raise to HIGH (require approval)
_HIGH_PATTERNS: List[str] = [
    r"\bdelete\b",
    r"\bremove\b",
    r"\bpurge\b",
    r"\buninstall\b",
    r"\bdrop\b",
    r"\btruncate\b",
    r"\berase\b",
    r"\binstall\s+(application|software|package|app)\b",
    r"\bmodify\s+(system|os|registry|config)\b",
    r"\bform\s+submit\b",
    r"\bsubmit\s+form\b",
    r"\bsign\s+in\b",
    r"\blog\s+in\b",
    r"\bpurchase\b",
    r"\bbuy\b",
    r"\bpayment\b",
    r"\bcheckout\b",
    r"\bcredit\s+card\b",
    r"\benter\s+(password|credential|token|secret)\b",
    r"\btype\s+(password|credential)\b",
    r"\bexternal\s+api\b",
    r"\bwrite\s+file\b",
    r"\boverwrite\s+file\b",
    r"\baccess\s+credential\b",
    r"\badmin\s+access\b",
    r"\broot\s+access\b",
    r"\bsudo\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bregistry\s+(edit|write|delete)\b",
]

# Patterns that raise to MEDIUM (advisory)
_MEDIUM_PATTERNS: List[str] = [
    r"\bdownload\b",
    r"\bupload\b",
    r"\bsend\s+(email|message)\b",
    r"\bpost\s+to\b",
    r"\bshare\b",
    r"\bexport\b",
    r"\bimport\b",
    r"\bclipboard\b",
    r"\bscreenshot\b",
    r"\brecord\b",
    r"\bmicrophone\b",
    r"\bcamera\b",
]

# Fully blocked URL patterns (regardless of risk level)
_URL_BLOCKLIST_PATTERNS: List[str] = [
    r"\.onion$",
    r"pastebin\.com",
    r"temp-mail\.",
    r"10minutemail\.",
    r"guerrillamail\.",
    r"darkweb\.",
    r"tor2web\.",
]

# Trusted domain allowlist — only these domains are LOW risk for navigation
_TRUSTED_DOMAINS: List[str] = [
    "github.com",
    "google.com",
    "wikipedia.org",
    "stackoverflow.com",
    "docs.python.org",
    "pypi.org",
    "npmjs.com",
    "microsoft.com",
    "developer.mozilla.org",
    "arxiv.org",
    "openai.com",
    "anthropic.com",
    "huggingface.co",
    "youtube.com",
    "linkedin.com",
    "reddit.com",
    "news.ycombinator.com",
    "duckduckgo.com",
    "bing.com",
    "yahoo.com",
    "medium.com",
    "dev.to",
    "fastapi.tiangolo.com",
    "reactjs.org",
    "nextjs.org",
    "tailwindcss.com",
]


# =========================================================
# SAFETY GUARD ENGINE
# =========================================================

class SafetyGuard:
    """
    Assess risk of any agent action and decide whether approval is needed.

    Usage
    -----
    assessment = safety_guard.assess_action("delete all files in Downloads")
    if assessment.requires_approval:
        # hold for human approval
    """

    def __init__(self) -> None:
        self._critical_re = [re.compile(p, re.IGNORECASE) for p in _CRITICAL_PATTERNS]
        self._high_re     = [re.compile(p, re.IGNORECASE) for p in _HIGH_PATTERNS]
        self._medium_re   = [re.compile(p, re.IGNORECASE) for p in _MEDIUM_PATTERNS]
        self._block_url   = [re.compile(p, re.IGNORECASE) for p in _URL_BLOCKLIST_PATTERNS]

    # ----------------------------------------------------------
    # MAIN ENTRY POINT
    # ----------------------------------------------------------

    def assess_action(
        self,
        action:      str,
        target:      str = "",
        agent:       str = "",
        context:     str = "",
    ) -> SafetyAssessment:
        """
        Evaluate an action text (and optional target/context) for risk.
        Returns a SafetyAssessment with risk_level and requires_approval.
        """
        full_text = f"{action} {target} {context}".strip()

        # 1. Check URL blocklist
        if target and _looks_like_url(target):
            block_check = self._check_url_blocked(target)
            if block_check:
                return SafetyAssessment(
                    risk_level        = RiskLevel.CRITICAL,
                    requires_approval = True,
                    blocked           = True,
                    reason            = f"URL is in the blocklist: {block_check}",
                    matched_patterns  = [block_check],
                    action            = action,
                    target            = target,
                )

        # 2. Scan for critical patterns
        critical_matches = self._scan(full_text, self._critical_re)
        if critical_matches:
            return SafetyAssessment(
                risk_level        = RiskLevel.CRITICAL,
                requires_approval = True,
                reason            = f"Critical operation detected: {critical_matches[0]}",
                matched_patterns  = critical_matches,
                action            = action,
                target            = target,
            )

        # 3. Scan for high-risk patterns
        high_matches = self._scan(full_text, self._high_re)
        if high_matches:
            return SafetyAssessment(
                risk_level        = RiskLevel.HIGH,
                requires_approval = True,
                reason            = f"High-risk operation detected: {high_matches[0]}",
                matched_patterns  = high_matches,
                action            = action,
                target            = target,
            )

        # 4. Scan for medium-risk patterns
        medium_matches = self._scan(full_text, self._medium_re)
        if medium_matches:
            return SafetyAssessment(
                risk_level        = RiskLevel.MEDIUM,
                requires_approval = False,
                reason            = f"Advisory: {medium_matches[0]}",
                matched_patterns  = medium_matches,
                action            = action,
                target            = target,
            )

        # 5. Check URL trust for navigation actions
        if target and _looks_like_url(target):
            domain = _extract_domain(target)
            if not self._is_trusted_domain(domain):
                return SafetyAssessment(
                    risk_level        = RiskLevel.MEDIUM,
                    requires_approval = False,
                    reason            = f"Navigating to untrusted domain: {domain}",
                    matched_patterns  = [f"untrusted_domain:{domain}"],
                    action            = action,
                    target            = target,
                )

        return SafetyAssessment(
            risk_level        = RiskLevel.LOW,
            requires_approval = False,
            reason            = "Action classified as low-risk.",
            action            = action,
            target            = target,
        )

    # ----------------------------------------------------------
    # URL VALIDATION
    # ----------------------------------------------------------

    def validate_url(self, url: str) -> SafetyAssessment:
        """Validate a URL against blocklist and domain trust rules."""
        blocked_pattern = self._check_url_blocked(url)
        if blocked_pattern:
            return SafetyAssessment(
                risk_level        = RiskLevel.CRITICAL,
                requires_approval = True,
                blocked           = True,
                reason            = f"Blocked URL pattern: {blocked_pattern}",
                matched_patterns  = [blocked_pattern],
                action            = "navigate",
                target            = url,
            )
        domain = _extract_domain(url)
        if self._is_trusted_domain(domain):
            return SafetyAssessment(
                risk_level        = RiskLevel.LOW,
                requires_approval = False,
                reason            = f"Trusted domain: {domain}",
                action            = "navigate",
                target            = url,
            )
        return SafetyAssessment(
            risk_level        = RiskLevel.MEDIUM,
            requires_approval = False,
            reason            = f"Untrusted domain: {domain}",
            matched_patterns  = [f"untrusted:{domain}"],
            action            = "navigate",
            target            = url,
        )

    def is_domain_trusted(self, url: str) -> bool:
        return self._is_trusted_domain(_extract_domain(url))

    # ----------------------------------------------------------
    # INTERNAL HELPERS
    # ----------------------------------------------------------

    def _check_url_blocked(self, url: str) -> Optional[str]:
        for pattern in self._block_url:
            if pattern.search(url):
                return pattern.pattern
        return None

    def _is_trusted_domain(self, domain: str) -> bool:
        domain = domain.lstrip("www.").lower()
        return any(domain == td or domain.endswith("." + td) for td in _TRUSTED_DOMAINS)

    @staticmethod
    def _scan(text: str, patterns: List[re.Pattern]) -> List[str]:
        matches: List[str] = []
        for p in patterns:
            m = p.search(text)
            if m:
                matches.append(m.group(0))
        return matches


# =========================================================
# UTILITY FUNCTIONS
# =========================================================

def _looks_like_url(text: str) -> bool:
    return text.startswith(("http://", "https://", "www."))


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return url


# =========================================================
# SINGLETON
# =========================================================

safety_guard = SafetyGuard()
