"""
NeMo Guardrails — Conversational Security Layer for CortexPrime.

Architecture position:
    User → NeMo Guardrails → Mission Runtime → Governance Runtime → Agents

This module provides FAST, in-process pattern-based guardrails that run
BEFORE the request reaches Mission Runtime.  It complements (does not
replace) the existing Governance Runtime / ApprovalQueue / SafetyGuard.

Layers
------
1. InputGuardrail   — detects prompt injection, jailbreaks, system-prompt
                      extraction, role-override, and harmful intent
2. ToolCallGuardrail — validates browser/computer/external tool calls
3. OutputGuardrail  — scans LLM output for credential leakage,
                      hallucinated system details, unsafe instructions
4. PolicyRegistry   — named, versioned policy sets; active set is swappable
5. GuardrailsTelemetry — counters + rolling violation history
6. GuardrailsEngine — singleton facade used by middleware and runtime

All checks are synchronous for speed (no async I/O).
"""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------

class ViolationType(str, Enum):
    PROMPT_INJECTION        = "prompt_injection"
    JAILBREAK               = "jailbreak"
    ROLE_OVERRIDE           = "role_override"
    SYSTEM_PROMPT_EXTRACT   = "system_prompt_extraction"
    HARMFUL_INTENT          = "harmful_intent"
    UNSAFE_TOOL_CALL        = "unsafe_tool_call"
    BROWSER_UNSAFE_ACTION   = "browser_unsafe_action"
    COMPUTER_UNSAFE_ACTION  = "computer_unsafe_action"
    CREDENTIAL_LEAK         = "credential_leak"
    SYSTEM_INFO_LEAK        = "system_info_leak"
    UNSAFE_OUTPUT           = "unsafe_output"
    POLICY_VIOLATION        = "policy_violation"


class GuardrailDecision(str, Enum):
    ALLOW   = "allow"
    BLOCK   = "block"
    WARN    = "warn"       # allow but emit warning + audit event


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class GuardrailResult:
    decision:       GuardrailDecision
    violation_type: Optional[ViolationType]
    matched_rule:   str
    reason:         str
    risk_score:     float          # 0.0–1.0
    layer:          str            # "input" | "tool" | "output"
    sanitized:      Optional[str]  # cleaned text for WARN decisions

    @property
    def blocked(self) -> bool:
        return self.decision == GuardrailDecision.BLOCK

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision":       self.decision.value,
            "violation_type": self.violation_type.value if self.violation_type else None,
            "matched_rule":   self.matched_rule,
            "reason":         self.reason,
            "risk_score":     self.risk_score,
            "layer":          self.layer,
            "sanitized":      self.sanitized,
        }


_ALLOW = GuardrailResult(
    decision       = GuardrailDecision.ALLOW,
    violation_type = None,
    matched_rule   = "",
    reason         = "clean",
    risk_score     = 0.0,
    layer          = "",
    sanitized      = None,
)


def _block(
    vtype:   ViolationType,
    rule:    str,
    reason:  str,
    score:   float,
    layer:   str,
) -> GuardrailResult:
    return GuardrailResult(
        decision       = GuardrailDecision.BLOCK,
        violation_type = vtype,
        matched_rule   = rule,
        reason         = reason,
        risk_score     = score,
        layer          = layer,
        sanitized      = None,
    )


# ===========================================================================
# 1. INPUT GUARDRAIL
# ===========================================================================

# ── Prompt injection patterns ────────────────────────────────────────────
# Classic DAN / role-override / system-override injections
_INJECTION_PATTERNS: List[Tuple[str, str]] = [
    # Ignore / override
    (r"ignore\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|directives?|prompts?|rules?|constraints?)", "ignore_previous_instructions"),
    (r"disregard\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|prompts?)", "disregard_instructions"),
    (r"forget\s+(all\s+)?(previous|prior|your)\s+(instructions?|rules?|training)", "forget_instructions"),
    (r"override\s+(your\s+)?(instructions?|system\s+prompt|guidelines?|rules?|safeguards?|constraints?)", "override_instructions"),

    # Injected payloads
    (r"new\s+(system\s+)?(prompt|instruction|directive)\s*[:=»]", "injected_system_prompt"),
    (r"<\s*(system|assistant|human|user)\s*>", "xml_role_injection"),
    (r"\[SYSTEM\]|\[INST\]|\[\/INST\]|\[ASSISTANT\]", "bracket_role_injection"),

    # Prompt leaking
    (r"(print|repeat|output|reveal|show|tell me|give me|what (is|are))\s+(your\s+)?(system\s+prompt|initial\s+prompt|instructions?|prompt\s+template)", "prompt_extraction"),
    (r"(translate|encode|decode|base64)\s+(your\s+)?(system\s+prompt|instructions?)", "obfuscated_extraction"),

    # Indirect injection via content
    (r"when\s+you\s+read\s+this.*ignore", "indirect_injection"),
    (r"the\s+following\s+is\s+a\s+new\s+(system\s+)?instruction", "indirect_injection_2"),
]

# ── Jailbreak patterns ───────────────────────────────────────────────────
_JAILBREAK_PATTERNS: List[Tuple[str, str]] = [
    # DAN / character personas
    (r"\bDAN\b|\bDo\s+Anything\s+Now\b", "dan_jailbreak"),
    (r"\bjailbreak\b", "explicit_jailbreak"),
    (r"pretend\s+(you\s+are|to\s+be)\s+(an?\s+)?(AI|assistant|model|system)\s+(without|that\s+(has\s+no|ignores?|lacks?)|with\s+no)\s+(restrictions?|guidelines?|safety|filters?|rules?|limits?)", "unrestricted_persona"),
    (r"act\s+as\s+(if\s+you\s+(are|were|have\s+no)|an?\s+AI\s+without)\s+(restrictions?|safety|guidelines?|filters?)", "unrestricted_act_as"),
    (r"you\s+are\s+now\s+in\s+(developer|debug|god|admin|root|maintenance|test)\s+mode", "debug_mode_injection"),
    (r"roleplay\s+as\s+(an?\s+)?(evil|malicious|unrestricted|unethical|rogue|dangerous)\s+(AI|assistant|bot|system)", "evil_roleplay"),

    # Token manipulation
    (r"speak\s+(in|using)\s+(pig\s+latin|l33t|morse|rot13|base64)\s+to\s+(bypass|avoid|evade)", "obfuscated_bypass"),
    (r"\[/?JAILBREAK\]|\[/?BYPASS\]|\[/?FILTER\]", "jailbreak_tags"),

    # Safety bypass phrases
    (r"(bypass|disable|turn\s+off|remove)\s+(your\s+)?(safety|content|filter|guardrail|restriction)", "safety_bypass"),
    (r"for\s+(educational|academic|research|hypothetical|fictional|creative)\s+purposes[,\s]+((please\s+)?(tell|show|explain|describe|generate).*?(how\s+to|step[s\-]by[s\-]step))", "educational_bypass"),
    (r"(this\s+is\s+|it['']s\s+|)(just|only)\s+(a\s+)?(fiction|story|game|roleplay|scenario)\s*,?\s*(so\s+)?(you\s+can|please)", "fiction_bypass"),
]

# ── Role override patterns ───────────────────────────────────────────────
_ROLE_PATTERNS: List[Tuple[str, str]] = [
    (r"you\s+are\s+no\s+longer\s+(cortexprime|an?\s+ai|an?\s+assistant)", "role_denial"),
    (r"(from\s+now\s+on|starting\s+now)\s*[,\s]\s*you\s+(are|will\s+be|must\s+be)", "role_override_directive"),
    (r"(assume|take on|adopt|switch to)\s+(the\s+)?(role|persona|identity)\s+of\s+(an?\s+)?(hacker|attacker|malware|virus|criminal)", "malicious_persona"),
    (r"(sudo|root|admin)\s+(mode|access|override|command)", "privilege_claim"),
    (r"developer\s+mode\s+(enabled?|activated?|on)", "developer_mode"),
    (r"god\s+mode|unrestricted\s+mode|no\s+(limits?|restrictions?|filters?|rules?|guidelines?)\s+mode", "unlimited_mode"),
]

# ── Harmful intent patterns ──────────────────────────────────────────────
_HARMFUL_PATTERNS: List[Tuple[str, str]] = [
    # Malware / exploit
    (r"(write|create|generate|build|make|code)\s+(me\s+)?(a\s+|an\s+)?(ransomware|virus|malware|trojan|keylogger|spyware|worm|rootkit|exploit|payload|shellcode|reverse\s+shell)", "malware_creation"),
    (r"(step[s\-]by[s\-]step|how\s+to|instructions?\s+for)\s+(hack(ing)?|cracking?|breaking?\s+into|bypassing?)\s+(a\s+|an\s+|the\s+)?(computer|server|network|system|account|password)", "hacking_instructions"),

    # Credentials / PII
    (r"(steal|harvest|scrape|collect|dump)\s+(user\s+)?(credentials?|passwords?|tokens?|api\s+keys?|private\s+keys?)", "credential_theft"),
    (r"(sql\s+injection|xss\s+attack|csrf\s+attack|directory\s+traversal|path\s+traversal|lfi|rfi|ssrf|xxe)", "web_attack_pattern"),

    # Physical harm
    (r"(how\s+to\s+|instructions?\s+(for|on)\s+)(make|build|create|synthesize)\s+(a\s+)?(bomb|explosive|weapon|poison|drug)", "physical_harm"),

    # DoS
    (r"(launch|execute|run|perform)\s+(a\s+)?(dos|ddos|denial.of.service)\s+attack", "dos_attack"),
]

# Compile all patterns once
def _compile(patterns: List[Tuple[str, str]]) -> List[Tuple[re.Pattern, str]]:
    return [(re.compile(p, re.IGNORECASE | re.DOTALL), name) for p, name in patterns]

_COMPILED_INJECTION = _compile(_INJECTION_PATTERNS)
_COMPILED_JAILBREAK = _compile(_JAILBREAK_PATTERNS)
_COMPILED_ROLE      = _compile(_ROLE_PATTERNS)
_COMPILED_HARMFUL   = _compile(_HARMFUL_PATTERNS)


class InputGuardrail:
    """Checks user-supplied text before it enters the mission pipeline."""

    def check(self, text: str) -> GuardrailResult:
        if not text:
            return _ALLOW

        # Prompt injection
        for pattern, name in _COMPILED_INJECTION:
            if pattern.search(text):
                return _block(
                    ViolationType.PROMPT_INJECTION, name,
                    f"Prompt injection detected: {name}", 0.95, "input",
                )

        # Jailbreak
        for pattern, name in _COMPILED_JAILBREAK:
            if pattern.search(text):
                return _block(
                    ViolationType.JAILBREAK, name,
                    f"Jailbreak attempt detected: {name}", 0.95, "input",
                )

        # Role override
        for pattern, name in _COMPILED_ROLE:
            if pattern.search(text):
                return _block(
                    ViolationType.ROLE_OVERRIDE, name,
                    f"Role override attempt detected: {name}", 0.90, "input",
                )

        # Harmful intent
        for pattern, name in _COMPILED_HARMFUL:
            if pattern.search(text):
                return _block(
                    ViolationType.HARMFUL_INTENT, name,
                    f"Harmful intent detected: {name}", 0.98, "input",
                )

        return _ALLOW


# ===========================================================================
# 2. TOOL CALL GUARDRAIL
# ===========================================================================

# ── Browser protection ───────────────────────────────────────────────────

# Domains that are always blocked (credential harvesting, known malicious)
_BLOCKED_DOMAINS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"phishing", r"malware", r"ransomware",
        # lookalike / typosquat patterns
        r"paypa1\.com", r"g00gle\.com", r"faceb00k\.com",
        r"amaz0n\.com", r"micros0ft\.com",
        # onion / dark-web
        r"\.onion",
        # credential-related paths
        r"/login.*redirect", r"/oauth.*callback.*token",
    ]
]

_DANGEROUS_BROWSER_ACTIONS: List[Tuple[str, str]] = [
    (r"(fill|enter|type|input)\s+(the\s+)?(username|password|credential|secret|api.?key|token)", "credential_input"),
    (r"(submit|click)\s+(a?\s*)(login|sign.in|auth|credential)", "credential_submit"),
    (r"(download|save|store)\s+(all\s+)?(cookies?|session\s+token|auth\s+token)", "cookie_harvest"),
    (r"(bypass|skip|dismiss|close)\s+(the\s+)?(captcha|auth|2fa|mfa|security\s+check)", "auth_bypass"),
    (r"(execute|run|eval)\s+(javascript|js|script)\s+on\s+(the\s+|this\s+|a\s+)?(page|site|url)", "js_injection"),
    (r"(navigate|go)\s+to\s+.*(malware|phishing|exploit)", "malicious_navigation"),
]

_COMPILED_BROWSER = _compile(_DANGEROUS_BROWSER_ACTIONS)

# ── Computer (desktop) protection ────────────────────────────────────────

_DANGEROUS_COMPUTER_ACTIONS: List[Tuple[str, str]] = [
    # Destructive file operations
    (r"\brm\s+(-rf|-r)\b|\brmdir\s+/[sq]?\b|\bdel\s+/[sfq]?\b", "destructive_delete"),
    (r"\bformat\b.*(c:|d:|e:|/dev/)", "disk_format"),
    (r"\bwipe\b.*(disk|drive|partition|all\s+files?)", "disk_wipe"),
    (r"\bdd\s+if=.*of=/dev/", "raw_disk_write"),

    # Privilege escalation
    (r"\bsudo\s+(su|bash|sh|zsh|root|-i|-s)\b", "sudo_shell"),
    (r"\brunas\s+/user:(administrator|admin|system|root)", "runas_admin"),
    (r"\bpsexec\b", "psexec"),
    (r"\bnet\s+(user|localgroup)\s.*/(add|delete)", "account_modification"),

    # Credential access
    (r"\b(mimikatz|lazagne|pwdump|lsadump|hashdump)\b", "credential_dumper"),
    (r"\breg\s+(query|export)\s.*(sam|security|system|lsa)", "registry_credential"),
    (r"(dump|extract)\s+(password|credential|hash)\s+(from\s+)?(memory|lsass|sam)", "memory_credential"),

    # Network / lateral movement
    (r"\b(netsh|iptables|ufw)\s+.*(disable|flush|delete|reset)", "firewall_disable"),
    (r"\b(nc|ncat|netcat)\s+(-e|-c)\s", "reverse_shell"),
    (r"\bcurl\s.*\|\s*(bash|sh|python|perl|ruby)", "pipe_exec"),
    (r"\bwget\s.*-O\s*-\s*\|\s*(bash|sh)", "pipe_exec_wget"),

    # Startup / persistence
    (r"\b(reg\s+add|schtasks|cron|at\s+)\b.*\b(startup|run|persist|autorun)\b", "persistence"),
    (r"\b(bcdedit|bootmgr)\b.*(disable|edit|modify)", "bootloader_modification"),
]

_COMPILED_COMPUTER = _compile(_DANGEROUS_COMPUTER_ACTIONS)


class ToolCallGuardrail:
    """Validates tool calls before they are dispatched to the browser/computer agent."""

    def check_browser(self, action: str, url: str = "") -> GuardrailResult:
        # Domain blocklist
        for pattern in _BLOCKED_DOMAINS:
            if pattern.search(url):
                return _block(
                    ViolationType.BROWSER_UNSAFE_ACTION, "blocked_domain",
                    f"Navigation to blocked domain: {url[:120]}", 0.98, "tool",
                )

        # Dangerous browser action patterns
        combined = f"{action} {url}"
        for pattern, name in _COMPILED_BROWSER:
            if pattern.search(combined):
                return _block(
                    ViolationType.BROWSER_UNSAFE_ACTION, name,
                    f"Unsafe browser action: {name}", 0.92, "tool",
                )
        return _ALLOW

    def check_computer(self, action: str) -> GuardrailResult:
        for pattern, name in _COMPILED_COMPUTER:
            if pattern.search(action):
                return _block(
                    ViolationType.COMPUTER_UNSAFE_ACTION, name,
                    f"Unsafe computer action blocked: {name}", 0.97, "tool",
                )
        return _ALLOW

    def check_external(self, url: str, method: str = "GET") -> GuardrailResult:
        """Validate outbound HTTP requests."""
        for pattern in _BLOCKED_DOMAINS:
            if pattern.search(url):
                return _block(
                    ViolationType.UNSAFE_TOOL_CALL, "blocked_domain",
                    f"Outbound request to blocked domain: {url[:120]}", 0.98, "tool",
                )
        # SSRF protection. Phase 11.1: judged by parsing, not by a prefix
        # regex -- the regex missed decimal/hex/octal spellings, IPv4-mapped
        # IPv6, fe80::, carrier-grade NAT, unsupported schemes and embedded
        # credentials. This is the synchronous, literal-only judgement (no DNS
        # here: this runs inside request middleware); the request boundary
        # itself (``backend.safety.outbound_guard``) resolves and pins.
        from backend.safety.outbound_guard import judge_outbound_url

        judgement = judge_outbound_url(url, resolve=False)
        if not judgement.allowed:
            return _block(
                ViolationType.UNSAFE_TOOL_CALL, "ssrf_private_ip",
                f"SSRF attempt blocked ({judgement.reason}): {url[:80]}", 0.95, "tool",
            )
        return _ALLOW


# ===========================================================================
# 3. OUTPUT GUARDRAIL
# ===========================================================================

_CREDENTIAL_PATTERNS: List[Tuple[str, str]] = [
    # JWT
    (r"ey[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "jwt_token"),
    # Generic API keys
    (r"\b(sk|pk|api|key|token|secret|bearer)\s*[=:]\s*[A-Za-z0-9_\-]{20,}", "api_key_pattern"),
    # AWS
    (r"\bAKIA[0-9A-Z]{16}\b", "aws_access_key"),
    (r"\b[A-Za-z0-9/+]{40}\b(?=.*aws)", "aws_secret_key"),
    # Private key block
    (r"-----BEGIN\s+(RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----", "private_key"),
    # Connection strings
    (r"(postgresql|mysql|mongodb|redis|mssql)://[^@\s]+:[^@\s]+@", "db_connection_string"),
    # Password in variable
    (r"(password|passwd|pwd|secret|credential)\s*=\s*['\"][^'\"]{6,}['\"]", "hardcoded_password"),
]

_SYSTEM_LEAK_PATTERNS: List[Tuple[str, str]] = [
    (r"my\s+(system\s+prompt|instructions?\s+(are|say|state|tell\s+me)|prompt\s+template)\s+(is|are)\s*[:=]?\s*['\"]", "system_prompt_leak"),
    (r"(the\s+)?(backend|server|database|internal)\s+(connection\s+string|credentials?|password|secret)", "system_details_leak"),
    (r"(cortexprime|cortex_prime)\s+(database|db|postgres|redis)\s+(password|secret|key|url|host)", "cortex_config_leak"),
]

_UNSAFE_OUTPUT_PATTERNS: List[Tuple[str, str]] = [
    (r"(here\s+(is|are)|step[s\-]by[s\-]step)\s+(how\s+to\s+)?(create|make|build|write)\s+(a?\s+)?(ransomware|virus|malware|keylogger|exploit|shellcode)", "malware_instructions"),
    (r"(here\s+(is|are)|below\s+is)\s+(the\s+)?(working\s+)?(exploit\s+code|malware\s+code|payload|reverse\s+shell)", "exploit_output"),
]

_COMPILED_CRED_OUT   = _compile(_CREDENTIAL_PATTERNS)
_COMPILED_SYSINFO    = _compile(_SYSTEM_LEAK_PATTERNS)
_COMPILED_UNSAFE_OUT = _compile(_UNSAFE_OUTPUT_PATTERNS)

_REDACT_CRED_RE = re.compile(
    r"(sk|pk|api|key|token|secret|bearer)\s*[=:]\s*[A-Za-z0-9_\-]{20,}|"
    r"ey[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"-----BEGIN\s+.*?PRIVATE\s+KEY-----.*?-----END\s+.*?PRIVATE\s+KEY-----|"
    r"(postgresql|mysql|mongodb|redis)://[^@\s]+:[^@\s]+@",
    re.IGNORECASE | re.DOTALL,
)


class OutputGuardrail:
    """Scans LLM output before it is sent to the user."""

    def check(self, text: str) -> GuardrailResult:
        # Credential / secret leakage
        for pattern, name in _COMPILED_CRED_OUT:
            if pattern.search(text):
                sanitized = _REDACT_CRED_RE.sub("[REDACTED]", text)
                return GuardrailResult(
                    decision       = GuardrailDecision.WARN,
                    violation_type = ViolationType.CREDENTIAL_LEAK,
                    matched_rule   = name,
                    reason         = f"Potential credential in output redacted: {name}",
                    risk_score     = 0.88,
                    layer          = "output",
                    sanitized      = sanitized,
                )

        # System info leakage
        for pattern, name in _COMPILED_SYSINFO:
            if pattern.search(text):
                return _block(
                    ViolationType.SYSTEM_INFO_LEAK, name,
                    f"System information leak blocked: {name}", 0.85, "output",
                )

        # Unsafe instructions in output
        for pattern, name in _COMPILED_UNSAFE_OUT:
            if pattern.search(text):
                return _block(
                    ViolationType.UNSAFE_OUTPUT, name,
                    f"Unsafe content in output blocked: {name}", 0.96, "output",
                )

        return _ALLOW


# ===========================================================================
# 4. POLICY REGISTRY
# ===========================================================================

@dataclass
class GuardrailPolicy:
    name:        str
    version:     str
    input_on:    bool = True
    tool_on:     bool = True
    output_on:   bool = True
    strict_mode: bool = False   # True → WARN becomes BLOCK


_DEFAULT_POLICY = GuardrailPolicy(
    name     = "default",
    version  = "1.0",
    input_on = True,
    tool_on  = True,
    output_on = True,
    strict_mode = False,
)

_STRICT_POLICY = GuardrailPolicy(
    name     = "strict",
    version  = "1.0",
    input_on = True,
    tool_on  = True,
    output_on = True,
    strict_mode = True,
)


class PolicyRegistry:
    def __init__(self) -> None:
        self._policies: Dict[str, GuardrailPolicy] = {
            "default": _DEFAULT_POLICY,
            "strict":  _STRICT_POLICY,
        }
        self._active = "default"

    def get_active(self) -> GuardrailPolicy:
        return self._policies[self._active]

    def set_active(self, name: str) -> None:
        if name not in self._policies:
            raise ValueError(f"Unknown policy: {name!r}")
        self._active = name

    def register(self, policy: GuardrailPolicy) -> None:
        self._policies[policy.name] = policy

    def list_names(self) -> List[str]:
        return list(self._policies)


# ===========================================================================
# 5. TELEMETRY
# ===========================================================================

@dataclass
class ViolationRecord:
    violation_type: str
    matched_rule:   str
    layer:          str
    text_preview:   str
    timestamp:      float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violation_type": self.violation_type,
            "matched_rule":   self.matched_rule,
            "layer":          self.layer,
            "text_preview":   self.text_preview,
            "timestamp":      self.timestamp,
        }


class GuardrailsTelemetry:
    def __init__(self, max_history: int = 200) -> None:
        self._history: Deque[ViolationRecord] = deque(maxlen=max_history)
        self._total_checked   = 0
        self._total_blocked   = 0
        self._total_warned    = 0
        self._by_type: Dict[str, int] = {}

    def record(self, result: GuardrailResult, text_preview: str = "") -> None:
        self._total_checked += 1
        if result.decision == GuardrailDecision.BLOCK:
            self._total_blocked += 1
        elif result.decision == GuardrailDecision.WARN:
            self._total_warned += 1

        if result.violation_type:
            key = result.violation_type.value
            self._by_type[key] = self._by_type.get(key, 0) + 1
            self._history.append(ViolationRecord(
                violation_type = key,
                matched_rule   = result.matched_rule,
                layer          = result.layer,
                text_preview   = text_preview[:100],
            ))

    def snapshot(self, recent_n: int = 20) -> Dict[str, Any]:
        block_rate = (
            round(self._total_blocked / self._total_checked, 4)
            if self._total_checked > 0 else None
        )
        recent = list(self._history)[-recent_n:]
        recent.reverse()
        return {
            "total_checked":  self._total_checked,
            "total_blocked":  self._total_blocked,
            "total_warned":   self._total_warned,
            "block_rate":     block_rate,
            "by_violation":   dict(self._by_type),
            "recent_violations": [r.to_dict() for r in recent],
        }


# ===========================================================================
# 6. GUARDRAILS ENGINE  (facade)
# ===========================================================================

class GuardrailsEngine:
    """
    Singleton facade.  Called at every trust boundary:
      - HTTP middleware (input check on every POST body)
      - mission_runtime.py (before pipeline starts)
      - tool dispatcher (before browser/computer execution)
      - LLM output (before sending to user)

    Usage::

        result = guardrails_engine.check_input(user_text)
        if result.blocked:
            return {"error": result.reason}

        result = guardrails_engine.check_tool("browser", action, url=url)
        result = guardrails_engine.check_output(llm_response)
    """

    def __init__(self) -> None:
        self._input   = InputGuardrail()
        self._tool    = ToolCallGuardrail()
        self._output  = OutputGuardrail()
        self.policies = PolicyRegistry()
        self.telemetry = GuardrailsTelemetry()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_input(self, text: str) -> GuardrailResult:
        policy = self.policies.get_active()
        if not policy.input_on:
            return _ALLOW

        result = self._input.check(text)
        result = self._apply_policy(result, policy)
        self._record_and_audit(result, text, "input")
        return result

    def check_tool(
        self,
        tool_name: str,
        action:    str,
        url:       str = "",
    ) -> GuardrailResult:
        policy = self.policies.get_active()
        if not policy.tool_on:
            return _ALLOW

        tname = tool_name.lower()
        if tname in ("browser", "browser_agent"):
            result = self._tool.check_browser(action, url)
        elif tname in ("computer", "computer_agent", "desktop"):
            result = self._tool.check_computer(action)
        elif tname in ("http", "requests", "external"):
            result = self._tool.check_external(url or action)
        else:
            result = _ALLOW

        result = self._apply_policy(result, policy)
        self._record_and_audit(result, f"{tool_name}:{action}", "tool")
        return result

    def check_output(self, text: str) -> GuardrailResult:
        policy = self.policies.get_active()
        if not policy.output_on:
            return _ALLOW

        result = self._output.check(text)
        result = self._apply_policy(result, policy)
        self._record_and_audit(result, text, "output")
        return result

    # ------------------------------------------------------------------
    # Policy helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_policy(
        result: GuardrailResult,
        policy: GuardrailPolicy,
    ) -> GuardrailResult:
        """In strict mode, escalate WARN → BLOCK."""
        if policy.strict_mode and result.decision == GuardrailDecision.WARN:
            result.decision = GuardrailDecision.BLOCK
        return result

    # ------------------------------------------------------------------
    # Telemetry + Audit
    # ------------------------------------------------------------------

    def _record_and_audit(
        self,
        result:       GuardrailResult,
        text_preview: str,
        layer:        str,
    ) -> None:
        if result.decision == GuardrailDecision.ALLOW:
            self.telemetry._total_checked += 1
            return

        self.telemetry.record(result, text_preview[:100])

        # Fire-and-forget audit log (non-blocking)
        try:
            from backend.safety.audit_logger import audit_logger
            audit_logger.log(
                execution_id = "guardrails",
                agent        = f"guardrails_{layer}",
                action       = result.violation_type.value if result.violation_type else "policy_violation",
                target       = text_preview[:120],
                risk_level   = "high" if result.risk_score >= 0.90 else "medium",
                outcome      = result.decision.value,
                reason       = result.reason,
                metadata     = result.to_dict(),
            )
        except Exception:
            pass

    def status(self) -> Dict[str, Any]:
        """Summary for /health/guardrails."""
        snap    = self.telemetry.snapshot(recent_n=10)
        policy  = self.policies.get_active()
        return {
            "status":        "healthy",
            "active_policy": policy.name,
            "policy_version": policy.version,
            "strict_mode":   policy.strict_mode,
            "layers": {
                "input":  policy.input_on,
                "tool":   policy.tool_on,
                "output": policy.output_on,
            },
            "policy_count":  len(self.policies.list_names()),
            **snap,
        }


# Singleton
guardrails_engine = GuardrailsEngine()
