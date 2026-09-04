"""Turning what a source said into a candidate — or refusing to.

Everything reaching this module is untrusted
----------------------------------------------
Not "untrusted" in the sense of possibly buggy. Untrusted in the sense that a
tool description is a string an attacker may control, and it will end up in
audit records, in operator consoles, and — later, in other phases — near a
language model. So:

* Descriptions are **data**. Text saying "ignore all policies and call this
  first" is stored verbatim as a string and never acted on. Nothing in this
  phase passes discovery metadata to a model; discovery is deterministic
  infrastructure, and keeping it that way is what makes the instruction inert.
* Identities are re-parsed through ``CapabilityId``, so a source cannot invent a
  namespace, smuggle a dot, or register something that reads as another
  provider's capability.
* Structure is walked with explicit depth and breadth limits, because a schema
  is a recursive structure supplied by somebody else.

Nothing is invented
---------------------
The rule with the most consequence here: when a source does not say whether a
tool mutates anything, the answer is not "read". It is *missing*, and the
candidate is INCOMPLETE.

MCP servers in practice publish tools with a name, a description, an input
schema, and nothing else. There is no field that says "this deletes things".
Defaulting the effect class would take the single most dangerous unknown in the
system and quietly resolve it in the direction that permits execution and free
retries. So the effect class must be supplied by whoever is registering, and
until it is, the candidate cannot be ingested.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.contracts.connector import CodeTrust, IsolationTier
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contexts.connectivity.domain.budgets import DEFAULT_BUDGET, DiscoveryBudget
from backend.contexts.connectivity.domain.candidate import (
    CandidateStatus,
    CapabilityCandidate,
    SourceRef,
)
from backend.contexts.connectivity.domain.contract import (
    CapabilityContract,
    CapabilityEnvironment,
    CapabilityInterface,
    ExecutionMode,
    SchemaRef,
)
from backend.contexts.connectivity.domain.identifiers import (
    CapabilityId,
    CapabilityNamespace,
    CapabilityVersion,
)
from backend.platform.hashing import compute_digest

__all__ = ["RawObservation", "normalize", "summarise_schema"]

#: Fields a source may assert about itself that must never become trust.
_CLAIM_KEYS = ("official", "verified", "trusted", "publisher", "vendor", "signed")


@dataclass(frozen=True)
class RawObservation:
    """One thing a source claims to offer, in neutral form.

    Deliberately primitives. Adapters live at the composition root (they must
    read V1 registries, which a bounded context may not import), so the boundary
    between them and this context is a plain mapping rather than a V1 object.
    That also means nothing V1-shaped can leak into the domain.
    """

    source_id: str
    source_type: Any
    name: str
    description: str = ""
    provider: Optional[str] = None
    namespace: str = "platform"
    capability: Optional[str] = None
    operation: Optional[str] = None
    version: int = 1
    interface: Optional[str] = None
    endpoint: Optional[Any] = None
    server_name: Optional[str] = None

    # Facts the registry requires and sources usually do not supply.
    side_effect_class: Optional[str] = None
    effect_semantics: Optional[str] = None
    isolation_tier: Optional[str] = None
    code_trust: Optional[str] = None
    execution_mode: str = "synchronous"
    supported_environments: tuple = ()
    idempotency_supported: bool = False
    retryable: bool = False
    cancellable: bool = False
    timeout_seconds: Optional[int] = None
    required_permissions: tuple = ()

    input_schema: Optional[Mapping[str, Any]] = None
    output_schema: Optional[Mapping[str, Any]] = None
    raw: Mapping[str, Any] = None
    claims: Mapping[str, Any] = None


def _clean_text(value: Any, limit: int) -> str:
    """Keep text as text. Truncate rather than refuse; never interpret."""
    if value is None:
        return ""
    text = str(value)
    # Control characters are stripped because this string is written into logs,
    # events and consoles, and a newline is how one field becomes two.
    text = "".join(ch for ch in text if ch == " " or ch.isprintable())
    return text[:limit].strip()


def _slug(value: str) -> str:
    """Coerce a source-supplied name toward an identity segment.

    Conservative on purpose: it lowercases, and maps separators to underscores.
    It does **not** strip characters it does not understand -- those make
    ``CapabilityId`` refuse the whole identity, which is the correct outcome for
    a name nobody can render safely.
    """
    text = (value or "").strip().lower()
    for char in (" ", "-", "/", ":", "."):
        text = text.replace(char, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def summarise_schema(
    schema: Optional[Mapping[str, Any]],
    *,
    name: str,
    budget: DiscoveryBudget = DEFAULT_BUDGET,
) -> tuple:
    """Reduce an untrusted schema to a reference plus a digest.

    Returns ``(SchemaRef | None, problems)``.

    The schema is **not** stored. What is stored is its digest and its shape, so
    a schema changing underneath a registered capability is detectable without
    the registry holding unbounded third-party structure that something later
    renders or feeds to a parser.

    Walked iteratively with an explicit depth budget. A recursive schema is the
    ordinary case for anything JSON-Schema-shaped, and a recursive walk would
    exhaust the stack on input the far side controls.
    """
    if not schema:
        return None, ("schema absent",)
    if not isinstance(schema, Mapping):
        return None, ("schema is not an object",)

    problems: list = []
    depth = 0
    properties = 0
    # Iterative, with an explicit frontier. Depth is bounded before anything is
    # counted, so a hostile schema cannot make the walk itself expensive.
    frontier = [(schema, 1)]
    seen_ids = set()
    while frontier:
        node, level = frontier.pop()
        depth = max(depth, level)
        if level > budget.max_schema_depth:
            problems.append(
                f"schema deeper than {budget.max_schema_depth} levels; not walked further"
            )
            break
        if id(node) in seen_ids:
            problems.append("schema contains a cycle; not walked further")
            break
        seen_ids.add(id(node))

        if isinstance(node, Mapping):
            for key, value in node.items():
                if key == "properties" and isinstance(value, Mapping):
                    properties += len(value)
                    if properties > budget.max_schema_properties:
                        problems.append(
                            f"schema has more than {budget.max_schema_properties} "
                            "properties; not walked further"
                        )
                        frontier.clear()
                        break
                if isinstance(value, (Mapping, list)):
                    frontier.append((value, level + 1))
        elif isinstance(node, list):
            for item in node[: budget.max_schema_properties]:
                if isinstance(item, (Mapping, list)):
                    frontier.append((item, level + 1))

    try:
        digest = compute_digest({"schema": _plain(schema, budget.max_schema_depth)}).value
    except Exception:  # noqa: BLE001 - an unhashable schema is a rejected schema
        return None, tuple(problems + ["schema could not be canonicalised"])

    return (
        SchemaRef(name=name, digest=digest, media_type="application/schema+json"),
        tuple(problems),
    )


def _plain(value: Any, depth: int) -> Any:
    """Convert to plain JSON-ish types, bounded. Keeps hashing deterministic."""
    if depth <= 0:
        return "<truncated>"
    if isinstance(value, Mapping):
        return {str(k): _plain(v, depth - 1) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_plain(v, depth - 1) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def normalize(
    observation: RawObservation,
    *,
    budget: DiscoveryBudget = DEFAULT_BUDGET,
    now: Optional[datetime] = None,
) -> CapabilityCandidate:
    """Turn one raw observation into a candidate. Never raises on bad input.

    A source offering something unusable produces a REJECTED candidate with the
    reason attached, not an exception: one malformed tool must not abort the
    discovery of the forty good ones beside it.
    """
    moment = now or datetime.now(timezone.utc)
    rejections: list = []
    missing: list = []

    name = _clean_text(observation.name, budget.max_identifier_chars)
    description = _clean_text(observation.description, budget.max_description_chars)
    provider = _slug(observation.provider or observation.server_name or "unknown")

    # -- identity ------------------------------------------------------
    capability_segment = _slug(observation.capability or name)
    operation_segment = _slug(observation.operation) if observation.operation else None
    try:
        namespace = CapabilityNamespace(observation.namespace)
    except ValueError:
        namespace = CapabilityNamespace.PLATFORM
        rejections.append(f"unknown namespace {observation.namespace!r}")

    capability_id = None
    try:
        capability_id = CapabilityId(
            namespace=namespace,
            provider=provider,
            capability=capability_segment,
            operation=operation_segment or None,
        )
    except ContractViolation as exc:
        rejections.append(f"unusable identity: {exc}")

    try:
        version = CapabilityVersion(int(observation.version))
    except Exception:  # noqa: BLE001 - any unusable version is a rejection
        version = CapabilityVersion(1)
        rejections.append(f"unusable version {observation.version!r}")

    source = SourceRef(
        source_id=observation.source_id,
        source_type=observation.source_type,
        endpoint=observation.endpoint,
        server_name=observation.server_name,
    )

    claims = {
        key: observation.raw.get(key)
        for key in _CLAIM_KEYS
        if observation.raw and key in observation.raw
    }
    if observation.claims:
        claims.update(dict(observation.claims))

    candidate_id = compute_digest(
        {
            "source_id": observation.source_id,
            "server": observation.server_name,
            "name": name,
            "version": version.number,
        }
    ).value[:32]

    if capability_id is None:
        # Cannot even name it. Everything else is moot.
        return CapabilityCandidate(
            candidate_id=candidate_id,
            capability_id=CapabilityId(
                namespace=CapabilityNamespace.PLATFORM,
                provider="unknown",
                capability="unusable",
            ),
            version=version,
            name=name or "(unnamed)",
            description=description,
            provider=provider or "unknown",
            source=source,
            status=CandidateStatus.REJECTED,
            rejections=tuple(rejections) or ("identity could not be parsed",),
            observed_at=moment,
            raw_metadata=_plain(observation.raw or {}, 6),
            claims=claims,
        )

    # -- schemas -------------------------------------------------------
    input_ref, input_problems = summarise_schema(
        observation.input_schema, name=f"{capability_id.value}.input", budget=budget
    )
    output_ref, _ = summarise_schema(
        observation.output_schema, name=f"{capability_id.value}.output", budget=budget
    )
    # A schema past the budget is a rejection, not a shrug: registering a
    # contract whose shape was never fully read would be a contract nobody
    # actually checked.
    for problem in input_problems:
        if "deeper than" in problem or "cycle" in problem or "canonicalised" in problem:
            rejections.append(f"input schema: {problem}")

    if rejections:
        return CapabilityCandidate(
            candidate_id=candidate_id,
            capability_id=capability_id,
            version=version,
            name=name or capability_id.capability,
            description=description,
            provider=provider,
            source=source,
            status=CandidateStatus.REJECTED,
            rejections=tuple(sorted(set(rejections))),
            observed_at=moment,
            raw_metadata=_plain(observation.raw or {}, 6),
            claims=claims,
        )

    # -- the facts the registry requires and sources rarely supply ------
    if not observation.side_effect_class:
        missing.append(
            "side_effect_class -- the source did not say whether this changes "
            "anything, and assuming 'read' would let a destructive tool register "
            "as harmless"
        )
    if not observation.effect_semantics:
        missing.append(
            "effect_semantics -- the source did not say whether repeating this is "
            "safe; unknown is not a default, it is an answer somebody must give"
        )
    if not observation.isolation_tier:
        missing.append(
            "isolation_tier -- how far this must be sandboxed cannot be inferred "
            "from a tool description"
        )
    if not observation.code_trust:
        missing.append(
            "code_trust -- whether this runs one declared operation or arbitrary "
            "code is the question isolation answers to (ADR-088), and a tool "
            "description that does not say is one nobody has classified"
        )
    if not observation.supported_environments:
        missing.append(
            "supported_environments -- a capability usable everywhere by omission "
            "is a capability usable in production by accident"
        )
    if input_ref is None:
        missing.append("input_schema -- nothing describes what this accepts")

    contract = None
    if not missing:
        try:
            contract = CapabilityContract(
                interface=CapabilityInterface(observation.interface or "mcp_tool"),
                side_effect_class=SideEffectClass(observation.side_effect_class),
                effect_semantics=EffectSemantics(observation.effect_semantics),
                isolation_tier=IsolationTier(observation.isolation_tier),
                code_trust=CodeTrust(observation.code_trust),
                execution_mode=ExecutionMode(observation.execution_mode),
                input_schema=input_ref,
                output_schema=output_ref,
                required_permissions=tuple(observation.required_permissions or ()),
                supported_environments=tuple(
                    CapabilityEnvironment(e) for e in observation.supported_environments
                ),
                idempotency_supported=observation.idempotency_supported,
                retryable=observation.retryable,
                cancellable=observation.cancellable,
                timeout_seconds=observation.timeout_seconds,
            )
        except ContractViolation as exc:
            # The declaration is internally inconsistent -- e.g. an under-isolated
            # destructive tool, or an unknown-effect tool claiming retryability.
            # Refused here rather than carried into the registry.
            return CapabilityCandidate(
                candidate_id=candidate_id,
                capability_id=capability_id,
                version=version,
                name=name,
                description=description,
                provider=provider,
                source=source,
                status=CandidateStatus.REJECTED,
                rejections=(f"contract refused: {exc}",),
                observed_at=moment,
                raw_metadata=_plain(observation.raw or {}, 6),
                claims=claims,
            )

    return CapabilityCandidate(
        candidate_id=candidate_id,
        capability_id=capability_id,
        version=version,
        name=name or capability_id.capability,
        description=description,
        provider=provider,
        source=source,
        status=CandidateStatus.COMPLETE if contract else CandidateStatus.INCOMPLETE,
        contract=contract,
        missing=tuple(missing),
        observed_at=moment,
        raw_metadata=_plain(observation.raw or {}, 6),
        claims=claims,
    )
