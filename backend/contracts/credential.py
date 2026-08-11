"""Credential vocabulary.

Owner: the credential fabric (Phase 4.1). Consumed by BC-5 Execution and by the
composition root, which is why it lives in ``contracts/`` — the two may not
import each other, and a reference that crosses that boundary has to be published
vocabulary rather than one side's private type.

The distinction this module exists to make unbreakable
--------------------------------------------------------
**A credential reference is not a credential.** ``CredentialRef`` names one; it
never carries one. It is safe to put in an execution record, a checkpoint, an
event, an audit entry and a replay frame, because there is nothing in it to leak
— every field is an identifier, and the type has no field that could hold secret
material even if somebody tried.

The secret itself is ``CredentialMaterial`` (``platform.credentials``), which is
deliberately *not* here: it is runtime-only, unserialisable by construction, and
must never reach a module whose job is to describe things that get written down.

Possession is not authority
-----------------------------
Holding a credential proves you can authenticate to a provider. It does not mean
CortexPrime authorized the action. Those are two separate questions answered by
two separate subsystems, and the whole security value of this phase rests on them
staying separate: a stolen token must still fail at the invocation gateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = [
    "CredentialType",
    "CredentialState",
    "CredentialRef",
    "CredentialScope",
    "is_valid_scope_token",
]

#: Characters a scope token may contain after its first. Deliberately permissive
#: about *content* and strict about *shape*: provider scopes are the provider's
#: vocabulary and this must not pretend to enumerate them, but a scope carrying
#: whitespace or a control character is one that will be mangled by whatever
#: transport carries it.
#:
#: Checked with plain string operations rather than a regex because ``contracts/``
#: is a leaf package whose permitted standard-library imports are a short,
#: reviewed list (``DEP-CONTRACTS-LEAF``). Widening that list to fit one
#: validator would be the wrong trade: the list is small on purpose.
_SCOPE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/-"
)
_SCOPE_MAX_LENGTH = 128


def is_valid_scope_token(token: object) -> bool:
    """Whether a scope token is usable. Shape only -- never meaning."""
    if not isinstance(token, str) or not token or len(token) > _SCOPE_MAX_LENGTH:
        return False
    if not token[0].isalnum() or not token[0].isascii():
        return False
    return all(character in _SCOPE_CHARS for character in token)


class CredentialType(str, Enum):
    """What kind of thing the credential is, as a *contract* rather than a value.

    Describes how a transport must present it, never what it contains. Extensible
    on purpose and branched on nowhere in the domain — a fabric with a
    provider-specific branch stops being provider-neutral the moment the second
    provider arrives.
    """

    API_KEY = "api_key"
    BEARER = "bearer"
    OAUTH_ACCESS_TOKEN = "oauth_access_token"
    MTLS_REFERENCE = "mtls_reference"
    """A pointer to a client certificate held elsewhere. The private key never
    enters this process, which is why it is a *reference* type."""

    CLOUD_TEMPORARY = "cloud_temporary"
    """Short-lived credentials minted by a cloud identity system."""

    SIGNED_ASSERTION = "signed_assertion"

    @property
    def is_inherently_short_lived(self) -> bool:
        """Whether this kind normally expires on its own.

        Advisory. An ``API_KEY`` that never expires is not made short-lived by a
        caller asking for a short lifetime, and this is what lets the fabric say
        so instead of pretending otherwise.
        """
        return self in {
            CredentialType.OAUTH_ACCESS_TOKEN,
            CredentialType.CLOUD_TEMPORARY,
            CredentialType.SIGNED_ASSERTION,
        }


class CredentialState(str, Enum):
    """Whether a credential may be used. Four states, and only one says yes.

    Deliberately **not** the capability lifecycle. A credential being revoked and
    a capability being revoked are different events with different causes and
    different remedies; merging them would make "rotate the token" and "withdraw
    the ability" the same operation.
    """

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

    UNKNOWN = "unknown"
    """The fabric could not establish the state. **Fails closed.** "Not known to
    be invalid" is not "known valid", and treating it as such is how a revoked
    token keeps working during the exact incident it was revoked for."""

    @property
    def permits_use(self) -> bool:
        return self is CredentialState.ACTIVE


@dataclass(frozen=True)
class CredentialRef(Contract):
    """An opaque handle to a credential. Safe to persist, log, and audit.

    Carries no secret and has nowhere to put one. Rendered
    ``cred://<tenant>/<opaque-id>`` so that anything printing it shows a
    reference, and so a grep for a leaked token never matches one of these.

    Tenant-qualified in the identity itself rather than alongside it: a
    reference that could be moved between tenants by changing a neighbouring
    field is a reference that will be.
    """

    CONTRACT_NAME = "cortexprime.credential.ref"

    tenant_id: str
    credential_id: str
    """Opaque. Assigned by the fabric, meaningful to the provider adapter, and
    never derived from the secret — a reference derived from what it points at
    would leak by construction."""

    def __post_init__(self) -> None:
        for label in ("tenant_id", "credential_id"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
            if "/" in value or value != value.strip():
                raise ContractViolation(
                    f"{label} must not contain a separator or surrounding "
                    "whitespace; a reference that does not round-trip is a "
                    "reference that eventually names something else"
                )
        # Cheap structural guard against the mistake this type exists to prevent.
        if len(self.credential_id) > 128:
            raise ContractViolation(
                "credential_id is implausibly long for an identifier; a secret "
                "was probably passed where a reference belongs"
            )

    @property
    def value(self) -> str:
        return f"cred://{self.tenant_id}/{self.credential_id}"

    def __str__(self) -> str:
        return self.value

    def belongs_to(self, tenant_id: str) -> bool:
        return self.tenant_id == tenant_id

    @classmethod
    def parse(cls, text: str) -> "CredentialRef":
        if not isinstance(text, str) or not text.startswith("cred://"):
            raise ContractViolation(
                f"{text!r} is not a credential reference; expected "
                "cred://<tenant>/<id>"
            )
        remainder = text[len("cred://") :]
        tenant, separator, credential = remainder.partition("/")
        if not separator:
            raise ContractViolation("a credential reference must name its tenant")
        return cls(tenant_id=tenant, credential_id=credential)

    def to_dict(self) -> dict:
        return {
            "ref": self.value,
            "tenant_id": self.tenant_id,
            "credential_id": self.credential_id,
        }


@dataclass(frozen=True)
class CredentialScope(Contract):
    """What a credential is allowed to do at the provider. Explicit, always.

    Scope tokens are the *provider's* vocabulary — ``repo:read``,
    ``issues.write``, an ARN, a Vault path. This deliberately does not enumerate
    them: a fabric that knew every provider's scopes would need changing for
    every new provider, and would be wrong about the first one it guessed.

    What it does enforce is the relationship that matters: a granted scope must
    be a **subset** of what was requested. Never a superset, and never silently
    narrower either — see ``missing_from``.
    """

    CONTRACT_NAME = "cortexprime.credential.scope"

    tokens: frozenset = field(default_factory=frozenset)
    resource: Optional[str] = None
    """The specific resource, when the provider scopes by resource rather than by
    verb. This is the field that stops *authorized repository A* becoming
    *credential for repository B*."""

    def __post_init__(self) -> None:
        cleaned = set()
        for token in self.tokens:
            if not is_valid_scope_token(token):
                raise ContractViolation(
                    f"{token!r} is not a usable scope token; scopes must be "
                    "printable, separator-free identifiers"
                )
            cleaned.add(token)
        if not cleaned:
            raise ContractViolation(
                "a credential scope must name at least one token; an empty scope "
                "is either 'everything' or 'nothing' and nobody can tell which"
            )
        object.__setattr__(self, "tokens", frozenset(cleaned))
        if self.resource is not None and (
            not isinstance(self.resource, str) or not self.resource.strip()
        ):
            raise ContractViolation("resource must be non-blank text when present")

    # -- comparison ------------------------------------------------------

    def covers(self, other: "CredentialScope") -> bool:
        """Whether this scope is at least as broad as ``other``.

        Resource-aware: a scope for one resource never covers another, however
        many verbs it holds. That single rule is what makes the confused-deputy
        case structural rather than a matter of care.
        """
        if not isinstance(other, CredentialScope):
            raise ContractViolation("can only compare against another CredentialScope")
        if self.resource != other.resource:
            return False
        return other.tokens <= self.tokens

    def missing_from(self, granted: "CredentialScope") -> frozenset:
        """Tokens that were asked for and not granted.

        Non-empty means the provider issued something narrower than requested.
        The fabric refuses rather than proceeding: silently accepting a narrower
        credential turns "create an issue" into "read an issue" and fails at the
        provider, halfway through an operation somebody approved.
        """
        if granted.resource != self.resource:
            return frozenset(self.tokens)
        return frozenset(self.tokens - granted.tokens)

    def to_dict(self) -> dict:
        return {"tokens": sorted(self.tokens), "resource": self.resource}

    @classmethod
    def of(cls, *tokens: str, resource: Optional[str] = None) -> "CredentialScope":
        return cls(tokens=frozenset(tokens), resource=resource)
