"""Provider and adapter vocabulary: who is being addressed, and how we speak to it.

Owner: the provider adapter fabric (Phase 4.3). Published here because Execution
names a provider, Connectivity describes one, audit records both, and none of
those may import the others.

Six identities that must not collapse
---------------------------------------
    CapabilityRef   WHAT may be done            (BC-8, ADR-032)
    WorkerRef       WHICH implementation runs   (ADR-036)
    ProviderRef     WHO is being addressed      (here)
    AdapterRef      HOW we translate for them   (here)
    ConnectionRef   HOW bytes move              (ADR-041)
    CredentialRef   WHAT authenticates          (ADR-040)

They are six because each answers a question the others cannot, and because
every pair that gets merged takes a security decision with it. ``provider ==
capability`` makes trusting GitHub authorize every GitHub operation.
``adapter == worker`` makes a worker's trust decision cover code that was
written later. ``provider == connection`` makes reachability into permission.

An adapter is a translator, and nothing else
----------------------------------------------
It is not an authorization mechanism, not a capability registry, not a
credential store and not a transport. It receives authority that four other
components already established and turns it into one provider protocol
exchange. Everything in this module is shaped to keep it unable to do more:
there is no field here that could carry a grant, a secret, or a URL.

A provider's own answer is a fact, never an authority
-------------------------------------------------------
``ProviderFailure`` includes ``AUTHENTICATION_FAILURE`` and
``AUTHORIZATION_FAILURE`` because providers refuse things. Those are recorded as
what the provider said. They never feed back into whether CortexPrime authorized
the action — that was decided before the adapter existed, and a provider saying
yes does not revisit it either.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = [
    "ProviderRef",
    "AdapterRef",
    "ProviderFailure",
    "ProviderDelivery",
    "ADAPTER_METRICS",
]

#: Metric names the adapter fabric emits. Every one is a count with tenant,
#: provider, adapter and environment labels -- never an operation payload, never
#: a credential reference, never a URL. Listed here so the observable surface is
#: reviewable in one place rather than discovered in a dashboard.
ADAPTER_METRICS = (
    "adapter.invocation",
    "adapter.success",
    "adapter.failure",
    "adapter.refused",
    "adapter.provider_timeout",
    "adapter.provider_rate_limit",
    "adapter.provider_auth_failure",
    "adapter.protocol_failure",
    "adapter.malformed_response",
    "adapter.unknown_outcome",
    "adapter.contract_mismatch",
    "adapter.effect_anomaly",
)

_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)
_MAX_ID_LENGTH = 128


def _clean_identifier(label: str, value: object) -> str:
    """Validate an identifier's *shape*. Never its meaning.

    Deliberately strict about separators and permissive about vocabulary: a
    provider id is somebody else's name for themselves and this must not pretend
    to enumerate them, but one carrying a slash or a space is one that will not
    round-trip through the reference forms below.
    """
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")
    text = value.strip()
    if len(text) > _MAX_ID_LENGTH:
        raise ContractViolation(
            f"{label} is implausibly long for an identifier; something that is "
            "not an identifier was probably passed"
        )
    for character in text:
        if character not in _ID_CHARS:
            raise ContractViolation(
                f"{label} contains {character!r}; identifiers are printable, "
                "separator-free tokens so that a reference built from them "
                "always parses back to the same parts"
            )
    return text


@dataclass(frozen=True)
class ProviderRef(Contract):
    """The external system an authorized operation addresses.

    Rendered ``provider://<id>``. Carries no endpoint, no credential, no
    account and no tenant — where the provider is, how one authenticates to it
    and whose data lives there are three separate questions owned by three
    separate components, and answering any of them here would make this the
    object an operator has to keep secret.

    **Deliberately not tenant-qualified**, and this is the one identity in the
    chain that is not. ``github`` is the same external system for every tenant;
    what differs is which credential reaches it and which resources that
    credential may touch, and both of those are carried elsewhere. Qualifying
    the provider by tenant would quietly suggest that provider account and
    tenant are the same thing, which is exactly the assumption that lets tenant
    A's repository become tenant B's.
    """

    CONTRACT_NAME = "cortexprime.provider.ref"

    provider_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "provider_id", _clean_identifier("provider_id", self.provider_id)
        )

    @property
    def value(self) -> str:
        return f"provider://{self.provider_id}"

    def __str__(self) -> str:
        return self.value

    def matches(self, provider_id: str) -> bool:
        """Exact, case-sensitive. There is no fuzzy provider match anywhere."""
        return self.provider_id == provider_id

    @classmethod
    def parse(cls, text: str) -> "ProviderRef":
        if not isinstance(text, str) or not text.startswith("provider://"):
            raise ContractViolation(
                f"{text!r} is not a provider reference; expected provider://<id>"
            )
        return cls(provider_id=text[len("provider://") :])

    def to_dict(self) -> dict:
        return {"ref": self.value, "provider_id": self.provider_id}


@dataclass(frozen=True)
class AdapterRef(Contract):
    """The translation code that turns an authorized operation into a protocol.

    Rendered ``adapter://<provider>/<id>@<version>``. Version is pinned and
    ``latest`` is refused for the same reason ``WorkerImplementation`` refuses
    it: an adapter identity that resolves at invocation time names a decision
    nobody made, and it is the field an audit record uses to answer "which
    translation produced this request".

    **Not a ``WorkerRef``.** A worker is the implementation selected to perform
    a binding; an adapter is how that implementation speaks to one provider.
    They are usually one object today and they are two identities on purpose:
    adapter trust and worker trust are separate judgements (ADR-042 §36), and a
    single id would make "we vouch for this adapter" and "we vouch for this
    worker" the same sentence.
    """

    CONTRACT_NAME = "cortexprime.provider.adapter_ref"

    adapter_id: str
    provider_id: str
    version: str

    def __post_init__(self) -> None:
        for label in ("adapter_id", "provider_id", "version"):
            object.__setattr__(
                self, label, _clean_identifier(label, getattr(self, label))
            )
        if self.version.lower() in {"latest", "current", "head"}:
            raise ContractViolation(
                f"adapter {self.adapter_id!r} declares version {self.version!r}; "
                "a moving version resolves at invocation time, so an audit "
                "record would name a translation nobody chose. Pin it"
            )

    @property
    def value(self) -> str:
        return f"adapter://{self.provider_id}/{self.adapter_id}@{self.version}"

    def __str__(self) -> str:
        return self.value

    def serves(self, provider: ProviderRef) -> bool:
        return isinstance(provider, ProviderRef) and provider.matches(self.provider_id)

    def to_dict(self) -> dict:
        return {
            "ref": self.value,
            "adapter_id": self.adapter_id,
            "provider_id": self.provider_id,
            "version": self.version,
        }


class ProviderDelivery(str, Enum):
    """Whether the provider received the operation. The field retry reads.

    Parallel to ``transport.DeliveryState`` and deliberately restated at this
    layer: transport answers "did the bytes arrive", this answers "did the
    *operation* reach the provider". They usually agree; where they do not — a
    provider that answered 200 to a request it did not apply, a stream that
    ended mid-result — the adapter is the only place that can tell, and
    collapsing the two would lose exactly that.
    """

    NOT_ATTEMPTED = "not_attempted"
    """Refused before anything left. The only state that is provably safe to
    repeat, and even then Execution decides."""

    DELIVERED = "delivered"
    """The provider received it and answered. Says nothing about whether it
    liked the request, and nothing about whether it applied it."""

    UNKNOWN = "unknown"
    """Nobody can say. The default whenever the fabric is not certain, because
    certainty is the thing being claimed."""

    @property
    def is_settled(self) -> bool:
        return self is not ProviderDelivery.UNKNOWN


class ProviderFailure(str, Enum):
    """What went wrong, in provider-neutral terms.

    Distinguishable on purpose. Flattening these into ``provider_failed`` takes
    away exactly what Execution's recovery reads: a validation failure and a
    rate limit call for opposite responses, and neither is a timeout.

    **Nothing here is a retry instruction.** ``is_ambiguous`` says whether the
    operation may have been applied; whether to try again is Execution's
    decision under the effect semantics the binding declared (ADR-031).
    """

    # -- authentication and authorization at the provider ------------------
    AUTHENTICATION_FAILURE = "authentication_failure"
    """The credential was rejected. A fact about the credential, never a
    CortexPrime authorization outcome — those were settled at the gateway."""

    AUTHORIZATION_FAILURE = "authorization_failure"
    """The provider refused on permission grounds. Returned as the provider's
    answer, never silently transformed into success and never re-decided."""

    # -- the request ---------------------------------------------------------
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    VALIDATION_FAILURE = "validation_failure"
    PRECONDITION_FAILED = "precondition_failed"

    # -- the provider's condition ---------------------------------------------
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    QUOTA_EXCEEDED = "quota_exceeded"

    # -- the exchange ------------------------------------------------------------
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PROTOCOL_ERROR = "protocol_error"
    MALFORMED_RESPONSE = "malformed_response"
    """The provider answered with something that is not a valid answer. **Never
    a success**: a response the fabric cannot parse is one it cannot check, and
    an unchecked response recorded as success is a half-applied change marked
    done."""

    RESPONSE_TOO_LARGE = "response_too_large"

    # -- CortexPrime-side refusals, before anything was sent ----------------------
    TRANSPORT_REFUSED = "transport_refused"
    CREDENTIAL_REFUSED = "credential_refused"
    OPERATION_NOT_SUPPORTED = "operation_not_supported"
    PROVIDER_MISMATCH = "provider_mismatch"
    ADAPTER_UNAVAILABLE = "adapter_unavailable"
    CONTRACT_MISMATCH = "contract_mismatch"
    """The provider's shape is not the one the capability contract was bound
    against. Refused rather than accommodated: silently adapting to drift means
    executing a contract nobody approved."""

    EFFECT_EXCEEDED = "effect_exceeded"
    """The operation did more than the binding authorized. Always ambiguous —
    the change may well have landed, and calling it a failure would assert
    otherwise."""

    UNKNOWN_OUTCOME = "unknown_outcome"
    """The honest answer when nobody can say. Never ``SUCCESS`` and never
    ``FAILURE``; both of those are claims."""

    @property
    def is_ambiguous(self) -> bool:
        """Whether the operation may have been applied despite the failure.

        The question Execution's retry rules actually ask. Deliberately
        conservative — anything that could have been transmitted is listed,
        because the cost of being wrong in that direction is a duplicated
        production change.
        """
        return self in {
            ProviderFailure.TIMEOUT,
            ProviderFailure.CANCELLED,
            ProviderFailure.MALFORMED_RESPONSE,
            ProviderFailure.RESPONSE_TOO_LARGE,
            ProviderFailure.PROTOCOL_ERROR,
            ProviderFailure.EFFECT_EXCEEDED,
            ProviderFailure.UNKNOWN_OUTCOME,
        }

    @property
    def is_definitely_not_applied(self) -> bool:
        """Whether the provider can be shown not to have acted.

        Only refusals raised before transmission, plus provider answers that are
        a refusal by definition. A 404 is here because a provider that could not
        find the resource did not change it; a 409 is *not*, because a conflict
        can follow a partially applied change.
        """
        return self in {
            ProviderFailure.TRANSPORT_REFUSED,
            ProviderFailure.CREDENTIAL_REFUSED,
            ProviderFailure.OPERATION_NOT_SUPPORTED,
            ProviderFailure.PROVIDER_MISMATCH,
            ProviderFailure.ADAPTER_UNAVAILABLE,
            ProviderFailure.CONTRACT_MISMATCH,
            ProviderFailure.AUTHENTICATION_FAILURE,
            ProviderFailure.AUTHORIZATION_FAILURE,
            ProviderFailure.VALIDATION_FAILURE,
            ProviderFailure.NOT_FOUND,
            ProviderFailure.RATE_LIMITED,
        }

    @property
    def is_security_relevant(self) -> bool:
        return self in {
            ProviderFailure.AUTHENTICATION_FAILURE,
            ProviderFailure.AUTHORIZATION_FAILURE,
            ProviderFailure.PROVIDER_MISMATCH,
            ProviderFailure.CONTRACT_MISMATCH,
            ProviderFailure.EFFECT_EXCEEDED,
            ProviderFailure.CREDENTIAL_REFUSED,
        }

    @property
    def metric(self) -> Optional[str]:
        """The ``ADAPTER_METRICS`` name this failure counts against, if any."""
        return {
            ProviderFailure.TIMEOUT: "adapter.provider_timeout",
            ProviderFailure.RATE_LIMITED: "adapter.provider_rate_limit",
            ProviderFailure.AUTHENTICATION_FAILURE: "adapter.provider_auth_failure",
            ProviderFailure.PROTOCOL_ERROR: "adapter.protocol_failure",
            ProviderFailure.MALFORMED_RESPONSE: "adapter.malformed_response",
            ProviderFailure.UNKNOWN_OUTCOME: "adapter.unknown_outcome",
            ProviderFailure.CONTRACT_MISMATCH: "adapter.contract_mismatch",
            ProviderFailure.EFFECT_EXCEEDED: "adapter.effect_anomaly",
        }.get(self)
