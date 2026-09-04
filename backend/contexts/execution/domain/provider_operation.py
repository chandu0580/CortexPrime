"""The operation model: named operations, not a URL somebody passed in.

The thing this module exists to prevent
-----------------------------------------
    connector.request(url, method, body)

An execution API shaped like that is an authenticated HTTP proxy with a
capability check bolted to the front. Every operation it can perform is
"whatever the caller typed", so the capability that authorized it describes
nothing, the approval that covered it covered nothing, and the audit record says
a caller was allowed to make requests.

So operations are **declared**. ``repository.create_issue`` names a method, a
path shape, a parameter list, an effect class and what a valid answer looks like.
An adapter can perform the operations in its catalog and there is no code path
that performs anything else — not because a check refuses it, but because there
is no field for it.

Determinism is the second property
------------------------------------
Same binding, same operation, same validated input, same environment produces
the same provider request. No attempt number in the path, no clock, no random
routing, no host selection. That is what makes a replayed decision comparable to
the original one, and what makes "was this request the one we authorized" a
question with an answer.

Where the authority actually lives
------------------------------------
The catalog says what the *provider* accepts. ``CapabilityBinding`` says what
CortexPrime *authorized*. Where they disagree the binding wins and the operation
is refused — see ``ProviderOperationSpec.contract_refusals``. A catalog entry can
never widen a binding, and a provider's runtime schema is never consulted at all:
a provider that changed its required fields since the capability was approved is
drift, and drift is refused rather than accommodated.

Validation happens before a credential is acquired
----------------------------------------------------
Every check here is a pure function of the declared spec and the payload. None
of it touches the network, so malformed input is refused without a provider ever
being contacted and without a secret ever being minted for it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Tuple

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.platform.hashing import compute_digest

__all__ = [
    "ParameterKind",
    "ParameterLocation",
    "ParameterSpec",
    "RecordEvidenceSpec",
    "ProviderOperationSpec",
    "OperationCatalog",
    "ProviderRequestPlan",
    "UnknownOperation",
]

#: Path segments a resource identifier may never produce. ``..`` walks out of the
#: path the operation declared, ``/`` invents a segment nobody declared, and the
#: rest are the characters that turn one request into two somewhere downstream.
_FORBIDDEN_IN_SEGMENT = ("/", "\\", "..", "?", "#", "%", " ", "\t", "\r", "\n")

_MAX_STRING_LENGTH = 4096
_MAX_TEXT_LENGTH = 65536
_MAX_LIST_ITEMS = 100


class UnknownOperation(ContractViolation):
    """An operation was requested that this provider's catalog does not declare.

    Not "not found yet" and not a prompt to go and look one up. A catalog is the
    complete list of what an adapter can do; an operation outside it is one
    nobody wrote, and resolving it at invocation time would be the adapter
    choosing a capability.
    """


class ParameterKind(str, Enum):
    """What shape a parameter has. Checked structurally, never semantically."""

    STRING = "string"
    TEXT = "text"
    """Free-form and long — an issue body, a commit message. Bounded generously
    rather than not at all: an unbounded field is an unbounded allocation in
    every parser between here and the provider."""

    INTEGER = "integer"
    BOOLEAN = "boolean"
    ENUM = "enum"
    STRING_LIST = "string_list"

    RESOURCE_SEGMENT = "resource_segment"
    """An identifier that becomes part of a URL path — an owner, a repository, a
    number. **The security-relevant kind.** Checked against
    ``_FORBIDDEN_IN_SEGMENT`` so a parameter cannot add a segment, escape the
    declared path, or smuggle a query string into it."""


class ParameterLocation(str, Enum):
    """Where a validated parameter goes in the provider request.

    Explicit because it is the difference between a value the provider treats as
    an identifier and one it treats as content, and because a parameter whose
    destination was inferred would eventually be inferred into the path.
    """

    PATH = "path"
    QUERY = "query"
    BODY = "body"


@dataclass(frozen=True)
class ParameterSpec:
    """One declared input to one operation."""

    name: str
    kind: ParameterKind
    location: ParameterLocation
    required: bool = True

    max_length: Optional[int] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    allowed_values: Tuple[str, ...] = ()
    """For ``ENUM``. Non-empty is required for that kind: an enum with no values
    is a string wearing a stricter name."""

    body_key: Optional[str] = None
    """The provider's own name for this field, when it differs from ours. A
    rename table with one entry per parameter, rather than a transformation
    function — a function here would be a place provider behaviour could be
    changed without changing the declared contract."""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ContractViolation("a parameter must be named")
        if not isinstance(self.kind, ParameterKind):
            raise ContractViolation("kind must be a ParameterKind")
        if not isinstance(self.location, ParameterLocation):
            raise ContractViolation("location must be a ParameterLocation")
        if self.kind is ParameterKind.ENUM and not self.allowed_values:
            raise ContractViolation(
                f"parameter {self.name!r} is an enum with no permitted values; "
                "that is a string with a stricter name and no stricter behaviour"
            )
        if (
            self.location is ParameterLocation.PATH
            and self.kind is not ParameterKind.RESOURCE_SEGMENT
        ):
            # Everything reaching a URL path goes through the segment checks.
            # A STRING in a path is how ``../`` gets into one.
            raise ContractViolation(
                f"parameter {self.name!r} is placed in the path but is not a "
                "resource_segment; only that kind is checked for the characters "
                "that let a value escape the path an operation declared"
            )
        if self.location is ParameterLocation.PATH and not self.required:
            raise ContractViolation(
                f"path parameter {self.name!r} is optional; an absent path "
                "segment leaves a hole in the URL, which is a different endpoint"
            )

    @property
    def wire_name(self) -> str:
        return self.body_key or self.name

    def problems(self, value: Any) -> Tuple[str, ...]:
        """Everything wrong with this value. Every reason, not the first."""
        found: list = []
        kind = self.kind

        if kind in (ParameterKind.STRING, ParameterKind.TEXT, ParameterKind.RESOURCE_SEGMENT, ParameterKind.ENUM):
            if not isinstance(value, str):
                return (f"{self.name}: expected text, got {type(value).__name__}",)
            ceiling = self.max_length or (
                _MAX_TEXT_LENGTH if kind is ParameterKind.TEXT else _MAX_STRING_LENGTH
            )
            if len(value) > ceiling:
                found.append(f"{self.name}: longer than {ceiling} characters")
            for character in value:
                code = ord(character)
                if (code < 0x20 and character not in "\t\n\r") or code == 0x7F:
                    found.append(
                        f"{self.name}: contains a control character, which is how "
                        "one field becomes two in whatever writes it out"
                    )
                    break
            if kind is ParameterKind.ENUM and value not in self.allowed_values:
                # The values are listed: an operator seeing this needs to know
                # what was permitted, and none of them is sensitive.
                found.append(
                    f"{self.name}: {value!r} is not one of "
                    f"{', '.join(self.allowed_values)}"
                )
            if kind is ParameterKind.RESOURCE_SEGMENT:
                if not value.strip():
                    found.append(f"{self.name}: a resource identifier cannot be blank")
                for fragment in _FORBIDDEN_IN_SEGMENT:
                    if fragment in value:
                        found.append(
                            f"{self.name}: contains {fragment!r}; a path parameter "
                            "that can add or leave a segment reaches an endpoint "
                            "the operation did not declare"
                        )
                        break
            return tuple(found)

        if kind is ParameterKind.INTEGER:
            # bool is an int in Python and is *not* an integer parameter here:
            # accepting True for an issue number is a type confusion that
            # reaches the provider as ``/issues/1``.
            if isinstance(value, bool) or not isinstance(value, int):
                return (f"{self.name}: expected an integer, got {type(value).__name__}",)
            if self.min_value is not None and value < self.min_value:
                found.append(f"{self.name}: below the minimum of {self.min_value}")
            if self.max_value is not None and value > self.max_value:
                found.append(f"{self.name}: above the maximum of {self.max_value}")
            return tuple(found)

        if kind is ParameterKind.BOOLEAN:
            if not isinstance(value, bool):
                return (f"{self.name}: expected a boolean, got {type(value).__name__}",)
            return ()

        if kind is ParameterKind.STRING_LIST:
            if not isinstance(value, (list, tuple)):
                return (f"{self.name}: expected a list, got {type(value).__name__}",)
            if len(value) > _MAX_LIST_ITEMS:
                found.append(f"{self.name}: more than {_MAX_LIST_ITEMS} entries")
            for index, entry in enumerate(value):
                if not isinstance(entry, str) or not entry.strip():
                    found.append(f"{self.name}[{index}]: entries must be non-blank text")
                elif len(entry) > (self.max_length or _MAX_STRING_LENGTH):
                    found.append(f"{self.name}[{index}]: entry is too long")
            return tuple(found)

        return (f"{self.name}: no validation rule exists for {kind.value}",)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "location": self.location.value,
            "required": self.required,
            "max_length": self.max_length,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "allowed_values": list(self.allowed_values),
            "wire_name": self.wire_name,
        }


@dataclass(frozen=True)
class ProviderRequestPlan:
    """A fully-determined provider exchange. Built, never assembled ad hoc.

    Deliberately holds no credential and no ``Authorization`` header: transport
    owns credential injection (ADR-042 §57), and a plan that could carry one
    would be a plan that gets logged with one.
    """

    method: str
    path: str
    query: Mapping[str, str] = field(default_factory=dict)
    body: Optional[Mapping[str, Any]] = None
    headers: Mapping[str, str] = field(default_factory=dict)
    """Non-secret, declared provider headers only — ``Accept``, an API version.
    Validated against the transport's forbidden-name list before it is sent."""

    def to_dict(self) -> dict:
        """Safe for audit. **Method and path only** — a query string routinely
        carries an identifier and a body routinely carries customer data."""
        return {"method": self.method, "path": self.path, "query_keys": sorted(self.query)}


@dataclass(frozen=True)
class RecordEvidenceSpec:
    """Declared, bounded, *repeating* evidence — Phase 9.3 (ADR-083).

    Why this exists at all
    ------------------------
    ``response_evidence_fields`` keeps top-level scalars, and for every operation
    up to Phase 9.2 that was the whole answer: a read returns one thing and the
    facts worth keeping about it are a handful of scalars.

    A Kubernetes WATCH window is the first operation whose *answer is a sequence*.
    One window carries N events, and each event's type, resource identity and own
    ``resourceVersion`` are exactly the facts the World Plane must record — not a
    summary of them. A flat scalar map cannot express that, so without this the
    events could not reach an Observation at all.

    What it is NOT
    ----------------
    It is **not** a door for raw payloads. ADR-042 §56 is unchanged: a provider
    body is unbounded, can carry the caller's own data back, and does not belong
    in an execution event. Every property that made scalar evidence safe is kept,
    one level down:

    * **Declared before the invocation existed.** The list field and every
      per-record field are named in the catalog. An undeclared field is dropped,
      exactly as at the top level.
    * **Scalars only.** ``int``/``float``/``bool`` kept; ``str`` truncated. A
      nested object or list inside a record is dropped, never flattened.
    * **Hard-bounded.** ``max_records`` is a cap the *operation* declares, and an
      answer that exceeds it is refused rather than trimmed — a silently
      truncated event sequence is a gap in world state that looks like continuity.
    * **In the digest.** This spec enters ``identity_payload``, so widening it is
      contract drift and a running binding refuses rather than accommodates it.

    The bound is therefore bigger than it was, and still a bound.
    """

    field_name: str
    """The top-level list field on the normalized body, e.g. ``"events"``."""

    fields: Tuple[str, ...]
    """The per-record scalar fields to keep. Everything else is dropped."""

    max_records: int = 64
    """The most records this operation will ever accept in one answer. An answer
    with more is ``MALFORMED_RESPONSE``: refusing a too-large window costs a
    re-read from the same position, while trimming it would lose events the
    stream position then claims were seen."""

    max_string_length: int = 256
    """Same truncation as top-level scalar evidence."""

    def __post_init__(self) -> None:
        if not isinstance(self.field_name, str) or not self.field_name.strip():
            raise ContractViolation("record evidence must name a field")
        if not isinstance(self.fields, tuple) or not self.fields:
            raise ContractViolation(
                f"record evidence for {self.field_name!r} declares no fields; "
                "undeclared record evidence would be an unbounded payload with "
                "a cap on it, which is the thing this is not"
            )
        for name in self.fields:
            if not isinstance(name, str) or not name.strip():
                raise ContractViolation("record evidence field names must be text")
        if len(set(self.fields)) != len(self.fields):
            raise ContractViolation(
                f"record evidence for {self.field_name!r} declares a field twice"
            )
        if not isinstance(self.max_records, int) or not 1 <= self.max_records <= 1024:
            raise ContractViolation(
                "max_records must be between 1 and 1024; an unbounded record "
                "count is an unbounded payload"
            )
        if (
            not isinstance(self.max_string_length, int)
            or not 1 <= self.max_string_length <= _MAX_STRING_LENGTH
        ):
            raise ContractViolation("max_string_length is out of range")

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "fields": sorted(self.fields),
            "max_records": self.max_records,
            "max_string_length": self.max_string_length,
        }

    def problems(self, body: Any) -> Tuple[str, ...]:
        """Whether the answer's record sequence is one this operation accepts.

        Absent is fine — an operation may legitimately answer with no records
        (an empty watch window). Present but not a list, or longer than the
        declared cap, is a refusal.
        """
        if not isinstance(body, Mapping) or self.field_name not in body:
            return ()
        records = body[self.field_name]
        if not isinstance(records, list):
            return (
                f"{self.field_name!r} must be a list of records, got "
                f"{type(records).__name__}",
            )
        if len(records) > self.max_records:
            return (
                f"{self.field_name!r} carries {len(records)} records and this "
                f"operation declares at most {self.max_records}; the answer is "
                "refused rather than trimmed",
            )
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                return (
                    f"{self.field_name}[{index}] is a "
                    f"{type(record).__name__}, not a record",
                )
        return ()

    def extract(self, body: Any) -> Tuple[dict, ...]:
        """The declared scalar fields of each record. Pure; assumes ``problems``
        already passed, and drops rather than raises on anything unexpected."""
        if not isinstance(body, Mapping):
            return ()
        records = body.get(self.field_name)
        if not isinstance(records, list):
            return ()
        picked: list = []
        for record in records[: self.max_records]:
            if not isinstance(record, Mapping):
                continue
            kept: dict = {}
            for name in self.fields:
                if name not in record:
                    continue
                value = record[name]
                if isinstance(value, bool) or isinstance(value, (int, float)):
                    kept[name] = value
                elif isinstance(value, str):
                    kept[name] = value[: self.max_string_length]
                # Anything else — a nested object, a list — is dropped. Evidence
                # is scalars; a structure here would be the payload coming back.
            picked.append(kept)
        return tuple(picked)


@dataclass(frozen=True)
class ProviderOperationSpec:
    """One named operation a provider adapter can perform, completely declared."""

    operation: str
    """The capability's operation, exactly as the binding names it. Matched by
    equality and never by prefix, suffix or similarity."""

    method: str
    path_template: str
    """``/repos/{owner}/{repo}/issues``. Placeholders name declared ``PATH``
    parameters and nothing else — an unknown placeholder is a construction-time
    refusal, not a runtime substitution of empty text."""

    side_effect_class: SideEffectClass
    effect_semantics: EffectSemantics
    """What the *provider* does. Compared against the binding rather than
    trusted: a catalog claiming a weaker effect than the binding declares is a
    catalog trying to make a write look repeatable."""

    parameters: Tuple[ParameterSpec, ...] = ()
    success_statuses: Tuple[int, ...] = (200,)
    response_required_fields: Tuple[str, ...] = ()
    """Fields a valid answer must contain. A response missing one is
    ``MALFORMED_RESPONSE`` and never a success — the provider answered, but not
    with the thing this operation is defined to return."""

    response_evidence_fields: Tuple[str, ...] = ()
    """The small, non-sensitive fields worth keeping as evidence — an id, a
    number, a URL. Everything else is digested and dropped."""

    response_evidence_records: Optional[RecordEvidenceSpec] = None
    """Declared, bounded, repeating evidence — for the operations whose answer is
    a *sequence* rather than one thing (Phase 9.3: a WATCH window). ``None``, the
    default, is the ordinary case and keeps evidence flat. See
    :class:`RecordEvidenceSpec` for why this is an extension of the bound rather
    than a hole in it."""

    supports_idempotency_key: bool = False
    idempotency_header: Optional[str] = None
    """The header the provider reads a key from, when it has one. Absent means
    the provider has none, and the fabric says so rather than pretending: a key
    sent to a provider that ignores it is a key that did nothing."""

    static_headers: Mapping[str, str] = field(default_factory=dict)

    static_query: Mapping[str, str] = field(default_factory=dict)
    """Query parameters that are part of *what this operation is*, not input to
    it — Phase 9.3 (ADR-083). ``watch=true`` is the motivating case: a watch is a
    different operation from a list, and expressing that as a caller-supplied
    parameter would mean the caller decides whether the authorized read is a
    one-shot or an open stream. Declared here it enters the digest, cannot be
    varied per invocation, and cannot be overridden by a parameter of the same
    name (``plan`` refuses that at construction).

    Mirrors ``static_headers`` deliberately: same shape, same reasoning."""

    provider_timeout_seconds: Optional[float] = None
    max_response_bytes: Optional[int] = None

    pinned_capability_digests: Tuple[str, ...] = ()
    """The exact capability contract digests this operation was written against.

    Non-empty turns contract drift into a refusal: a capability whose contract
    was republished no longer matches, and the adapter was written for a shape
    that has changed. Empty means this axis is not pinned — the binding's own
    effect comparison still runs, and that is the check that cannot be skipped.
    """

    def __post_init__(self) -> None:
        for label in ("operation", "method", "path_template"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        if not self.method.isalpha() or self.method != self.method.upper():
            raise ContractViolation(
                f"method {self.method!r} must be upper-case alphabetic text"
            )
        if not self.path_template.startswith("/"):
            raise ContractViolation(
                f"path template {self.path_template!r} must be absolute; a "
                "relative path resolves against a base somebody else chose"
            )
        if not isinstance(self.side_effect_class, SideEffectClass):
            raise ContractViolation("side_effect_class must be a SideEffectClass")
        if not isinstance(self.effect_semantics, EffectSemantics):
            raise ContractViolation("effect_semantics must be an EffectSemantics")
        if not self.success_statuses:
            raise ContractViolation(
                f"operation {self.operation!r} declares no success status; without "
                "one every answer is a success, including the ones that are not"
            )
        if self.idempotency_header is not None and not self.supports_idempotency_key:
            raise ContractViolation(
                "an idempotency header is declared but the operation does not "
                "support idempotency keys; one of the two is not what its "
                "author intended"
            )

        declared = {p.name for p in self.parameters}
        if len(declared) != len(self.parameters):
            raise ContractViolation(
                f"operation {self.operation!r} declares a parameter twice"
            )
        for placeholder in _placeholders(self.path_template):
            spec = next((p for p in self.parameters if p.name == placeholder), None)
            if spec is None:
                raise ContractViolation(
                    f"path template names {{{placeholder}}} but operation "
                    f"{self.operation!r} declares no such parameter; a "
                    "placeholder with nothing behind it would be substituted "
                    "with nothing and reach a different endpoint"
                )
            if spec.location is not ParameterLocation.PATH:
                raise ContractViolation(
                    f"parameter {placeholder!r} appears in the path template but "
                    f"is declared as {spec.location.value}"
                )
        for spec in self.parameters:
            if spec.location is ParameterLocation.PATH and (
                "{" + spec.name + "}" not in self.path_template
            ):
                raise ContractViolation(
                    f"parameter {spec.name!r} is a path parameter that the path "
                    "template never uses; it would be validated and discarded"
                )

        for name, value in self.static_query.items():
            if not isinstance(name, str) or not name.strip():
                raise ContractViolation("static query names must be text")
            if not isinstance(value, str):
                raise ContractViolation(
                    f"static query {name!r} must be text; a value the operation "
                    "declares is a constant, not something to be formatted"
                )
        collisions = sorted(
            {p.wire_name for p in self.parameters if p.location is ParameterLocation.QUERY}
            & set(self.static_query)
        )
        if collisions:
            raise ContractViolation(
                f"operation {self.operation!r} declares {', '.join(collisions)} both "
                "as static query and as a caller parameter; the point of a static "
                "query value is that the caller cannot choose it"
            )
        if self.response_evidence_records is not None and not isinstance(
            self.response_evidence_records, RecordEvidenceSpec
        ):
            raise ContractViolation(
                "response_evidence_records must be a RecordEvidenceSpec"
            )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def identity_payload(self) -> dict:
        return {
            "operation": self.operation,
            "method": self.method,
            "path_template": self.path_template,
            "side_effect_class": self.side_effect_class.value,
            "effect_semantics": self.effect_semantics.value,
            "parameters": [p.to_dict() for p in self.parameters],
            "success_statuses": sorted(self.success_statuses),
            "response_required_fields": sorted(self.response_required_fields),
            "supports_idempotency_key": self.supports_idempotency_key,
            "idempotency_header": self.idempotency_header,
            "static_headers": dict(sorted(self.static_headers.items())),
            "static_query": dict(sorted(self.static_query.items())),
            "response_evidence_records": (
                self.response_evidence_records.to_dict()
                if self.response_evidence_records is not None
                else None
            ),
            "pinned_capability_digests": sorted(self.pinned_capability_digests),
        }

    @property
    def digest(self) -> str:
        """What this operation *is*. Recorded so an audit can answer which
        declaration produced a request, across a catalog change."""
        return compute_digest(self.identity_payload()).value

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def contract_refusals(self, binding: Any) -> Tuple[str, ...]:
        """Whether this declaration still agrees with what was authorized.

        Three ways it can disagree, and all three refuse rather than adapt:

        the operation is not the bound one (an adapter about to do something
        else); the contract digest moved (the capability was republished and
        this code was written for the previous shape); or the provider's effect
        exceeds the binding's (the catalog is claiming authority the binding did
        not give).

        The reverse — a catalog declaring a *weaker* effect than the binding —
        is permitted. A read operation performed under a write authorization is
        within what was allowed; refusing it would make the binding a floor as
        well as a ceiling, which is not what an authorization is.
        """
        problems: list = []
        if binding.operation != self.operation:
            problems.append(
                f"the binding authorizes {binding.operation!r} but this "
                f"operation is {self.operation!r}"
            )
        if (
            self.pinned_capability_digests
            and binding.capability_digest not in self.pinned_capability_digests
        ):
            problems.append(
                "the capability contract digest is not one this operation was "
                "written against; the contract changed and the adapter did not"
            )
        order = {
            SideEffectClass.READ: 0,
            SideEffectClass.REVERSIBLE_WRITE: 1,
            SideEffectClass.IRREVERSIBLE_WRITE: 2,
            SideEffectClass.DESTRUCTIVE: 3,
        }
        if order[self.side_effect_class] > order[binding.side_effect_class]:
            problems.append(
                f"this operation performs a {self.side_effect_class.value} but "
                f"the binding authorizes {binding.side_effect_class.value}"
            )
        if (
            binding.effect_semantics.is_repeatable
            and not self.effect_semantics.is_repeatable
        ):
            # The binding says repeating is safe and the provider says it is
            # not. The provider is right about its own behaviour, and the retry
            # rules read the binding -- so this must not proceed quietly.
            problems.append(
                f"the binding declares {binding.effect_semantics.value} but this "
                f"operation is {self.effect_semantics.value}; retry safety would "
                "be decided from a claim the provider does not support"
            )
        return tuple(problems)

    def input_problems(self, payload: Mapping[str, Any]) -> Tuple[str, ...]:
        """Everything wrong with this input. Pure, and no provider is contacted.

        Unknown keys are refused rather than dropped. Silently discarding a
        field means a caller believes it was sent, and the operation performed
        is not the one they described — which is also the one the action digest
        covered.
        """
        if not isinstance(payload, Mapping):
            return ("the operation input must be a mapping",)
        problems: list = []
        declared = {spec.name: spec for spec in self.parameters}

        for name in payload:
            if name not in declared:
                problems.append(
                    f"{name}: not an input to {self.operation!r}; unknown fields "
                    "are refused rather than dropped, because a dropped field is "
                    "an operation the caller did not perform and believes they did"
                )
        for spec in self.parameters:
            if spec.name not in payload:
                if spec.required:
                    problems.append(f"{spec.name}: required")
                continue
            value = payload[spec.name]
            if value is None:
                if spec.required:
                    problems.append(f"{spec.name}: required and was null")
                continue
            problems.extend(spec.problems(value))
        return tuple(problems)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def plan(
        self,
        payload: Mapping[str, Any],
        *,
        idempotency_key: Optional[str] = None,
    ) -> ProviderRequestPlan:
        """Build the provider request. Deterministic, and validated first.

        Same spec plus same validated input produces the same plan, every time.
        Nothing here reads a clock, a counter, an attempt number or a random
        source: two runs of one authorized action must be distinguishable by
        their idempotency key, not by their shape.
        """
        problems = self.input_problems(payload)
        if problems:
            # Not a caller convenience -- constructing a request from input that
            # failed validation is the one path that must not exist.
            raise ContractViolation(
                f"cannot build a request for {self.operation!r}: "
                + "; ".join(problems)[:400]
            )

        path = self.path_template
        # The operation's own constants first. A caller parameter cannot
        # overwrite one: __post_init__ refuses a spec where the two names
        # collide, so this seeding is unconditional rather than defensive.
        query: dict = dict(self.static_query)
        body: dict = {}
        for spec in self.parameters:
            if spec.name not in payload or payload[spec.name] is None:
                continue
            value = payload[spec.name]
            if spec.location is ParameterLocation.PATH:
                path = path.replace("{" + spec.name + "}", str(value))
            elif spec.location is ParameterLocation.QUERY:
                query[spec.wire_name] = _as_query_value(value)
            else:
                body[spec.wire_name] = value

        if "{" in path or "}" in path:
            # Belt and braces: __post_init__ proves every placeholder has a
            # required path parameter, so reaching here means one was not
            # substituted and the URL would name a literal brace.
            raise ContractViolation(
                f"the path for {self.operation!r} still contains a placeholder "
                "after substitution"
            )

        headers = dict(self.static_headers)
        if idempotency_key and self.supports_idempotency_key and self.idempotency_header:
            headers[self.idempotency_header] = idempotency_key

        return ProviderRequestPlan(
            method=self.method,
            path=path,
            query=query,
            body=body if (body or self.method in {"POST", "PUT", "PATCH"}) else None,
            headers=headers,
        )

    def response_problems(self, body: Any) -> Tuple[str, ...]:
        """Whether the provider's answer is one this operation can accept.

        A provider that answered the wrong shape has not succeeded. The caller
        turns a non-empty result into ``MALFORMED_RESPONSE``, which is ambiguous
        rather than failed: the operation may well have been applied, and only
        the account of it is untrustworthy.
        """
        records = self.response_evidence_records
        if not self.response_required_fields:
            return records.problems(body) if records is not None else ()
        if not isinstance(body, Mapping):
            return (
                f"expected a {self.operation!r} object, got "
                f"{type(body).__name__}",
            )
        missing = [f for f in self.response_required_fields if f not in body]
        if missing:
            return (f"the response is missing {', '.join(sorted(missing))}",)
        return records.problems(body) if records is not None else ()

    def evidence(self, body: Any) -> dict:
        """The bounded, non-sensitive facts worth keeping from a response.

        Bounded on purpose (ADR-042 §56). A raw provider payload is unbounded,
        can contain the caller's own data coming back, and belongs in an
        evidence store with its own governance rather than in an execution
        event.
        """
        if not isinstance(body, Mapping):
            return {}
        picked: dict = {}
        for name in self.response_evidence_fields:
            if name not in body:
                continue
            value = body[name]
            if isinstance(value, (int, float, bool)):
                picked[name] = value
            elif isinstance(value, str):
                picked[name] = value[:256]
        # Declared repeating evidence, under the same discipline one level down
        # (Phase 9.3). Absent unless the operation declares it, so every
        # operation written before this one keeps exactly the evidence it had.
        if self.response_evidence_records is not None:
            records = self.response_evidence_records.extract(body)
            if records:
                picked[self.response_evidence_records.field_name] = list(records)
        return picked


class OperationCatalog:
    """Every operation one provider adapter can perform. Immutable, and complete.

    **Not a registry.** It is constructed whole, owned by the composition root,
    and cannot be added to afterwards — there is no ``register`` and no module
    singleton. A mutable catalog would be a place an operation could appear
    without anybody registering a capability for it, which is the second half of
    the arbitrary-URL problem this module exists to close.
    """

    __slots__ = ("_provider", "_operations")

    def __init__(self, provider_id: str, operations: Iterable[ProviderOperationSpec]) -> None:
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ContractViolation("a catalog must name the provider it describes")
        entries: dict = {}
        for spec in operations:
            if not isinstance(spec, ProviderOperationSpec):
                raise ContractViolation(
                    "a catalog holds ProviderOperationSpec entries"
                )
            if spec.operation in entries:
                raise ContractViolation(
                    f"{provider_id}: operation {spec.operation!r} is declared "
                    "twice; two declarations for one operation is one of them "
                    "silently not applying"
                )
            entries[spec.operation] = spec
        if not entries:
            raise ContractViolation(
                f"the catalog for {provider_id!r} declares no operation; an "
                "adapter that can do nothing should not be registered as one "
                "that can do something"
            )
        self._provider = provider_id.strip()
        self._operations = entries

    @property
    def provider_id(self) -> str:
        return self._provider

    @property
    def operations(self) -> Tuple[str, ...]:
        return tuple(sorted(self._operations))

    def get(self, operation: str) -> Optional[ProviderOperationSpec]:
        """Exact match only. No prefix, no suffix, no closest match."""
        return self._operations.get(operation)

    def require(self, operation: str) -> ProviderOperationSpec:
        spec = self.get(operation)
        if spec is None:
            raise UnknownOperation(
                f"{self._provider} declares no operation {operation!r}; the "
                f"catalog holds {', '.join(self.operations)}. An operation "
                "outside it is one nobody wrote a contract for"
            )
        return spec

    def __contains__(self, operation: object) -> bool:
        return operation in self._operations

    def __len__(self) -> int:
        return len(self._operations)

    @property
    def digest(self) -> str:
        """What this catalog *is*, for audit and for detecting a swapped one."""
        return compute_digest(
            {
                "provider_id": self._provider,
                "operations": [
                    self._operations[name].identity_payload()
                    for name in sorted(self._operations)
                ],
            }
        ).value

    def to_dict(self) -> dict:
        return {
            "provider_id": self._provider,
            "operations": list(self.operations),
            "digest": self.digest,
        }

    def __repr__(self) -> str:
        return (
            f"<OperationCatalog {self._provider} "
            f"operations={len(self._operations)}>"
        )


def _placeholders(template: str) -> Tuple[str, ...]:
    """Names between braces in a path template. Unbalanced braces refuse."""
    found: list = []
    rest = template
    while "{" in rest:
        _, _, after = rest.partition("{")
        name, closed, rest = after.partition("}")
        if not closed:
            raise ContractViolation(
                f"path template {template!r} has an unclosed placeholder"
            )
        if not name or "{" in name:
            raise ContractViolation(
                f"path template {template!r} has a malformed placeholder"
            )
        found.append(name)
    return tuple(found)


def _as_query_value(value: Any) -> str:
    """Render a validated value for a query string. Total, and never guessing.

    Booleans become ``true``/``false`` rather than ``True``/``False``: Python's
    repr is not what any provider's query parser reads, and the one that accepts
    it does so by accident.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(entry) for entry in value)
    return str(value)
