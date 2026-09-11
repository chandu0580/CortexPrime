"""The governed evidence-acquisition path — Phase 9.5 (ADR-085).

The port this closes
----------------------
``EvidenceAcquisitionPort`` (``intelligence/application/proposal.py``) has carried
the strongest claim in the codebase since Phase 8:

    "the governed READ path: governed read -> Observation -> Fact -> Belief,
     returning references. **This is the ONLY way the Intelligence Plane obtains
     new world evidence; it never touches a connector itself.**"

Until now nothing in ``backend/`` implemented it. Every phase from 8.2 to 8.8
satisfied it with a stub inside its own harness script, which meant the claim was
true of the design and untested in production code. This is the third time that
pattern has appeared — after the observation mapping (closed in 9.3) and the
world read port (closed in 9.4) — and this is the last of the three.

How a tool becomes a governed read
------------------------------------
The model names a **tool key** from a frozen allowlist. It never names a
capability, a provider, an endpoint, a query or a path; it does not know they
exist. This module holds the only mapping from key to capability, and that
mapping is data — a frozen tuple of :class:`InvestigationTool` — supplied at
composition.

    model: "use k8s.pod_termination on kubernetes:pod:ns/payments-api-x"
              |
              v  (this module, deterministically)
    capability platform.kubernetes.pod.get   payload {namespace, name}
              |
              v  the whole governed chain: authorize -> resolve -> lease ->
                 gateway -> transport -> provider
              v
    Observation -> Fact -> references + the OBSERVED value

Read-only, structurally
-------------------------
Every tool is checked **at construction** against the capability catalog: a tool
whose operation is not ``SideEffectClass.READ`` makes the registry refuse to
assemble. There is no runtime branch to forget and no flag to set wrongly — a
write capability cannot be reached because a tool naming one cannot exist.

``EvidenceRequest`` reinforces it from the other side: it has ``tool``,
``subject_ref``, ``predicate`` and a ``read_only`` field that is only ever True.
There is no field through which a write could be described.

What this module will not do
------------------------------
It does not interpret. It maps a tool to a capability, runs the governed read,
projects the declared evidence onto the declared proposition, records the
Observation and derives the Fact. The *value* it returns is what the instrument
reported. Whether that value supports or contradicts a hypothesis is decided by
the engine, deterministically, against the test's own declared expectation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "InvestigationTool",
    "ToolRegistry",
    "GovernedEvidenceAcquisition",
]


@dataclass(frozen=True)
class InvestigationTool:
    """One read-only tool the model may name, bound to one governed capability.

    ``key`` is the entire vocabulary the model has. ``operation`` is the governed
    capability it resolves to. ``subject_kind`` states what the tool observes, so
    a subject reference of the wrong shape is refused before any provider is
    contacted rather than producing a confidently wrong read.

    ``project`` turns the operation's declared bounded evidence into the value the
    proposition is expressed in. It is a pure function supplied at composition; it
    may select and reshape declared fields and may not invent one.
    """

    key: str
    operation: str
    subject_kind: str
    predicate: str
    describes: str
    project: Callable[[Mapping[str, Any]], Any]
    source_ref: str
    payload_from_subject: Callable[[str], Mapping[str, Any]]
    # Phase 11.3 (ADR-123 D-19): a compiled pattern over a FAILED read's reason
    # that means the provider answered "this evidence does not exist" (for a
    # container log: the instance is gone). Such a read is absence, not a
    # platform failure: the port answers ``absent`` and the investigation goes
    # on. Declared per tool, never inferred; every other failure still blocks.
    absent_when: Optional[Any] = None

    def __post_init__(self) -> None:
        for name in ("key", "operation", "subject_kind", "predicate",
                     "describes", "source_ref"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"an investigation tool needs a {name}")
        if not callable(self.project) or not callable(self.payload_from_subject):
            raise ContractViolation("project and payload_from_subject must be callable")
        if self.absent_when is not None and not callable(getattr(self.absent_when, "search", None)):
            raise ContractViolation("absent_when must be a compiled pattern")


class ToolRegistry:
    """The frozen read-only tool allowlist, checked against the real catalogs.

    Construction is where read-only stops being a promise. Every tool's operation
    is looked up in the composed provider catalogs and must declare
    ``SideEffectClass.READ``; anything else — or an operation no catalog declares
    — refuses the whole registry. A deployment cannot start with a tool that could
    write, so no investigation can select one.
    """

    __slots__ = ("_tools",)

    def __init__(self, *, tools: Sequence[InvestigationTool], catalogs: Mapping[str, Any]) -> None:
        from backend.contracts.execution import SideEffectClass

        if not tools:
            raise ContractViolation(
                "an investigation with no tools can observe nothing; an empty "
                "registry would make every investigation INSUFFICIENT_EVIDENCE "
                "for a reason that has nothing to do with the world"
            )
        seen: dict = {}
        for tool in tools:
            if not isinstance(tool, InvestigationTool):
                raise ContractViolation("tools must be InvestigationTool instances")
            if tool.key in seen:
                raise ContractViolation(f"tool key {tool.key!r} is declared twice")
            spec = None
            for catalog in catalogs.values():
                spec = catalog.get(tool.operation)
                if spec is not None:
                    break
            if spec is None:
                raise ContractViolation(
                    f"tool {tool.key!r} names operation {tool.operation!r}, which no "
                    "composed catalog declares; a tool the platform cannot resolve "
                    "would fail at the worst possible moment"
                )
            if spec.side_effect_class is not SideEffectClass.READ:
                raise ContractViolation(
                    f"tool {tool.key!r} names {tool.operation!r}, whose declared "
                    f"side effect is {spec.side_effect_class.value}. An investigation "
                    "observes; it does not act. This is refused at construction so "
                    "no investigation can ever select it."
                )
            seen[tool.key] = tool
        self._tools = dict(seen)

    @property
    def keys(self) -> tuple:
        """The exact allowlist handed to the engine as ``available_tools``."""
        return tuple(sorted(self._tools))

    def get(self, key: str) -> Optional[InvestigationTool]:
        return self._tools.get(key)

    def describe(self) -> tuple:
        return tuple({"tool": t.key, "observes": t.describes,
                      "subject_kind": t.subject_kind, "predicate": t.predicate}
                     for t in (self._tools[k] for k in sorted(self._tools)))


class GovernedEvidenceAcquisition:
    """Implements ``EvidenceAcquisitionPort`` over the real governed read path.

    Holds a governed capability reader, an observer, a fact derivation and a tool
    registry — and no provider, no connector, no credential, no endpoint and no
    HTTP client. There is no route from here to a provider except the governed
    capability chain, and no route from the Intelligence Plane to here except the
    port.
    """

    __slots__ = ("_reader", "_observer", "_derivation", "_registry", "_context",
                 "_clock")

    def __init__(
        self, *, reader: Any, observer: Any, derivation: Any, registry: ToolRegistry,
        context: Any, clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        if not isinstance(registry, ToolRegistry):
            raise ContractViolation("a frozen ToolRegistry is required")
        self._reader = reader
        self._observer = observer
        self._derivation = derivation
        self._registry = registry
        self._context = context
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def available_tools(self) -> tuple:
        return self._registry.keys

    def acquire(self, *, tenant: Any, request: Any, now: datetime) -> Any:
        """Perform one governed read for one validated evidence request.

        Every refusal below returns an explicit ``ok=False`` with a reason. The
        engine turns that into ``BLOCKED`` — an honest "the platform could not
        obtain this evidence", never a hypothesis quietly left unsupported as
        though the world had answered.
        """
        from backend.intelligence.application.proposal import EvidenceResult

        def _refused(reason: str) -> Any:
            return EvidenceResult(
                ok=False, subject_ref=getattr(request, "subject_ref", ""),
                predicate=getattr(request, "predicate", ""), reason=reason)

        if not getattr(request, "read_only", False):
            # Belt and braces against a request shape that could not exist: the
            # contract has no write field. If one ever appears, it stops here.
            return _refused("a non-read evidence request is refused; an "
                            "investigation observes and does not act")

        tool = self._registry.get(getattr(request, "tool", ""))
        if tool is None:
            return _refused(
                f"tool {getattr(request, 'tool', None)!r} is not in the frozen "
                "read-only allowlist")

        subject = getattr(request, "subject_ref", "")
        if not subject.startswith(tool.subject_kind):
            return _refused(
                f"tool {tool.key!r} observes {tool.subject_kind!r} subjects; "
                f"{subject!r} is not one, so the read would answer about "
                "something other than what was asked")

        try:
            payload = dict(tool.payload_from_subject(subject))
        except Exception as problem:  # noqa: BLE001 — a malformed reference
            return _refused(f"the subject reference could not be resolved to a "
                            f"governed payload: {type(problem).__name__}")

        outcome = self._reader.read(self._context, operation=tool.operation,
                                    payload=payload)
        if not outcome.succeeded:
            failure = str(outcome.failure_reason or "")
            if tool.absent_when is not None and tool.absent_when.search(failure):
                # Phase 11.3 (ADR-123 D-19): measured on the live cluster, the API
                # server answered a request for a container's previous log with an
                # error ("previous terminated container ... not found") where in
                # other runs the kubelet answered 200 with the same text. Both mean
                # the log does not exist. Not observed is not a value, and it is
                # not a blocked investigation either (D-15).
                return EvidenceResult(
                    ok=False, absent=True, subject_ref=subject, predicate=tool.predicate,
                    reason=(f"{tool.key!r}: the provider reports this evidence does not exist: "
                            f"{failure[:200]}"))
            return _refused(f"the governed read failed: {outcome.failure_reason}")

        try:
            value = tool.project(outcome.evidence)
        except Exception as problem:  # noqa: BLE001
            return _refused(f"the declared evidence did not carry what "
                            f"{tool.key!r} observes: {type(problem).__name__}")
        if value is None:
            # The read succeeded and the instrument did not report this field.
            # That is "not observed", which is not the same as any value, so no
            # observation is recorded and the hypothesis stays where it was.
            # Phase 11.3 (ADR-123 D-15): said explicitly (``absent=True``) so the
            # engine continues instead of concluding BLOCKED -- a container that
            # dies within a second has no cAdvisor series, and that absence must
            # not end an investigation that still has the kubelet's termination
            # and log to read.
            return EvidenceResult(
                ok=False, absent=True, subject_ref=subject, predicate=tool.predicate,
                reason=(f"{tool.key!r} succeeded but the provider reported no "
                        f"{tool.predicate!r} for {subject!r}; not observed is not a value"))

        from backend.api.governed_read_observer import GovernedReadObserver, ObservationLeg

        moment = now or self._clock()
        observer = (self._observer if isinstance(self._observer, GovernedReadObserver)
                    else GovernedReadObserver(ingestion=self._observer,
                                              source_ref=tool.source_ref,
                                              produced_by=tool.source_ref))
        recorded = observer.observe(
            tenant=tenant, outcome=outcome, now=moment,
            legs=(ObservationLeg(subject_ref=subject, predicate=tool.predicate,
                                 value=value, observed_at=moment),))
        if not recorded:
            return _refused("the observation boundary recorded nothing")
        observation, _newly = recorded[0]

        fact_ref = None
        if self._derivation is not None:
            derived = self._derivation.derive(tenant=tenant, observation=observation,
                                              recorded_at=moment)
            fact = getattr(derived, "fact", None)
            fact_ref = getattr(fact, "record_id", None) if fact is not None else None

        return EvidenceResult(
            ok=True, subject_ref=subject, predicate=tool.predicate,
            observation_ref=observation.record_id, fact_ref=fact_ref,
            observed_value=observation.value, source_ref=tool.source_ref,
            execution_ref=outcome.execution_id)
