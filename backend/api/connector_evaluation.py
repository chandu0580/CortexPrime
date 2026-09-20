"""The connector evaluation suite -- the contract checks every connector passes.

Phase 11.1-K (ADR-125). A connector is admitted to the governed plane only when
its manifest and the operation catalogs its adapters compose agree on the rules
below. The suite is connector-agnostic: it takes a ``ConnectorManifest`` and the
composed catalogs (``provider_id -> OperationCatalog``) and returns every
violation, each naming the rule, the capability and what to change. Kubernetes
passes it (tests/connector_fabric/test_connector_evaluation.py); the next
connector runs the same function before its real-provider harness.

The rules are the ones a real install taught, not a style guide:

``EVAL-UNIQUE``      capability ids are unique
``EVAL-DESCRIBED``   the description tells a model and an operator what it does and when
``EVAL-COMPOSED``    the operation exists in the catalog of the provider that serves it
``EVAL-EFFECT``      manifest and catalog agree on read vs write
``EVAL-TARGET``      every tenant-scoped target parameter is an input of the operation
``EVAL-PERMISSION``  a provider read declares the provider permission it needs
``EVAL-FORBIDDEN``   no arbitrary-request, exec, shell, apply or delete capability
``EVAL-BUDGET``      the response budget admits a transport policy (>= the frame budget)
``EVAL-TIMEOUT``     a bounded timeout (<= 120 s)
``EVAL-WRITE-*``     a write: never retried, independently verified, not low risk,
                     served by a contained worker (not the read provider), not cluster-scoped
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

__all__ = ["EVALUATION_QUESTIONS", "EvaluationFinding", "EvaluationReport", "evaluate_connector",
           "evaluate_evidence"]

#: Verbs a governed capability may not perform: an arbitrary provider request,
#: code execution, or a deletion. Matched against the operation's VERB -- the
#: first word of its last segment -- and not as a substring: GitHub's
#: ``get_pull_request`` is a typed read whose noun merely contains "request",
#: while ``raw_request`` is the thing this rule exists to catch (Phase 11.2).
FORBIDDEN_VERBS = frozenset({"raw", "exec", "shell", "apply", "delete", "request",
                             "proxy", "command", "eval", "run"})
MAX_TIMEOUT_SECONDS = 120.0
MIN_DESCRIPTION = 60


@dataclass(frozen=True)
class EvaluationFinding:
    rule: str
    capability: str
    message: str


@dataclass(frozen=True)
class EvaluationReport:
    connector_id: str
    capabilities: int
    findings: Tuple[EvaluationFinding, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict:
        return {"connector": self.connector_id, "capabilities": self.capabilities, "passed": self.passed,
                "findings": [{"rule": f.rule, "capability": f.capability, "message": f.message}
                             for f in self.findings]}


def evaluate_connector(manifest: Any, catalogs: Mapping[str, Any], *,
                       read_provider: Optional[str] = None) -> EvaluationReport:
    """Every violation of the connector contract. Empty findings = admitted.

    ``read_provider`` is the provider that serves reads in-process (defaults to
    the connector id); a write served by it is refused -- writes run in a
    contained worker with their own identity.
    """
    from backend.platform.transport.policy import ResourceBudget

    frame = ResourceBudget().max_frame_bytes
    read_provider = read_provider or manifest.connector_id
    findings: list = []

    def add(rule: str, cap: str, message: str) -> None:
        findings.append(EvaluationFinding(rule, cap, message))

    seen: set = set()
    for cap in manifest.capabilities:
        cid = cap.capability_id
        if cid in seen:
            add("EVAL-UNIQUE", cid, "declared twice; one id, one contract")
        seen.add(cid)

        description = (cap.description or "").strip()
        if len(description) < MIN_DESCRIPTION or not any(w in description for w in ("Use", "Used", "Governed")):
            add("EVAL-DESCRIBED", cid, f"describe what it does and when to use it (>= {MIN_DESCRIPTION} chars, "
                                       "with 'Use ...' guidance or its governance)")

        segments = cap.operation.lower().split(".")
        last = segments[-1]
        verb = last.split("_")[0]
        hit = sorted({v for v in (verb, last) if v in FORBIDDEN_VERBS}
                     | (set(segments) & FORBIDDEN_VERBS))
        if hit:
            add("EVAL-FORBIDDEN", cid, f"operation names a forbidden kind of capability: {hit}")

        profile = cap.profile
        if float(profile.timeout_seconds) > MAX_TIMEOUT_SECONDS:
            add("EVAL-TIMEOUT", cid, f"timeout {profile.timeout_seconds}s exceeds {MAX_TIMEOUT_SECONDS}s")

        catalog = catalogs.get(cap.provider)
        spec = catalog.get(cap.operation) if catalog is not None else None
        if spec is None:
            add("EVAL-COMPOSED", cid, f"provider {cap.provider!r} composes no operation {cap.operation!r}")
        else:
            if bool(spec.side_effect_class.mutates) != bool(cap.mutates):
                add("EVAL-EFFECT", cid, "manifest and catalog disagree on whether this mutates")
            names = {p.name for p in spec.parameters}
            # A composite target (GitHub's owner/repo) is scoped only if EVERY
            # part of it is an input the platform validated.
            targets = tuple(getattr(cap, "target_parameters", ()) or ()) or (
                (cap.target_parameter,) if cap.target_parameter else ())
            absent = [t for t in targets if t not in names]
            if names and absent:
                add("EVAL-TARGET", cid, f"target parameter(s) {absent} are not inputs of "
                                        f"{cap.operation!r}; the connection scope could not "
                                        "confine it to the tenant's target")
            budget = getattr(spec, "max_response_bytes", None)
            if budget is not None and budget < frame:
                add("EVAL-BUDGET", cid, f"response budget {budget} < frame budget {frame}: the connection "
                                        "policy refuses to construct and every call fails")

        if cap.mutates:
            if cap.retry.value != "never":
                add("EVAL-WRITE-RETRY", cid, "a write is never retried")
            if profile.verification_requirement.value == "none":
                add("EVAL-WRITE-VERIFY", cid, "a write requires independent verification")
            if profile.risk.level.value == "low":
                add("EVAL-WRITE-RISK", cid, "a write is not low risk")
            if cap.provider == read_provider:
                add("EVAL-WRITE-CONTAINED", cid, "a write runs in a contained worker, not the read provider")
            if (profile.resource_scope or "").lower() == "cluster":
                add("EVAL-WRITE-SCOPE", cid, "a write is not cluster-scoped")
        elif cap.provider == read_provider and cap.category != "health" and not cap.required_permissions:
            add("EVAL-PERMISSION", cid, "declare the provider permission this read needs (health names it)")

    return EvaluationReport(connector_id=manifest.connector_id, capabilities=len(manifest.capabilities),
                            findings=tuple(findings))


# ---------------------------------------------------------------------------
# Behavioural evaluation: the questions every connector must answer with
# evidence from a REAL-provider run, never from a unit test's say-so.
# ---------------------------------------------------------------------------

#: (key, question). A connector's harness maps each key to the names of the
#: checks that prove it; the answer is computed, not asserted.
EVALUATION_QUESTIONS = (
    ("select", "Can CortexPrime correctly select the capability?"),
    ("arguments", "Can it produce valid arguments?"),
    ("governance", "Can governance reject unsafe operations?"),
    ("authorized_execution", "Can execution happen only after authorization?"),
    ("verification", "Can verification correctly distinguish success from failure?"),
    ("recovery", "Can the system recover from provider failures?"),
    ("explain", "Can the system explain the result to the user?"),
)


def evaluate_evidence(checks: Any, evidence: Mapping[str, Any]) -> dict:
    """Answer every question from a real run's checks.

    ``checks``: ``[{"name": ..., "ok": ...}]`` (a harness report).
    ``evidence``: question key -> check-name prefixes that prove it.
    PASS needs at least one matching check and no failing one; a question
    with no matching check is UNPROVEN, never PASS.
    """
    rows = [(str(c.get("name", "")), bool(c.get("ok"))) for c in checks or ()]
    answers = {}
    for key, question in EVALUATION_QUESTIONS:
        prefixes = tuple(evidence.get(key) or ())
        matched = [(n, ok) for n, ok in rows if prefixes and n.startswith(prefixes)]
        missing = [p for p in prefixes if not any(n.startswith(p) for n, _ in rows)]
        if not matched:
            verdict = "UNPROVEN"
        elif any(not ok for _, ok in matched):
            verdict = "FAIL"
        else:
            verdict = "PASS" if not missing else "PARTIAL"
        answers[key] = {"question": question, "verdict": verdict,
                        "evidence": [n for n, _ in matched], "missing_evidence": missing}
    return answers
