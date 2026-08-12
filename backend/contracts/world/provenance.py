"""World Plane provenance — reference-only — Phase 7.1 (Part L).

Every epistemic record must be able to answer "where did this come from?"
without embedding what it came from. Provenance here is **references only**:
ids and hashes that point at immutable anchors the platform already keeps —
observations, executions, traces (``correlation_id``), the harness version,
a parent claim — never the payloads and never secrets.

Two hard rules (ADR-062):
  * No credential material. Not a token, not an ``Authorization`` header, not
    a raw secret. Enforced at construction: a value that looks like a secret
    raises :class:`SecretInProvenance`. The check is dependency-free (contracts
    may not import the platform firewall); it is a coarse tripwire, and the
    real defence is that provenance carries references, not payloads.
  * No large evidence payloads copied in. Provenance is a pointer, not a store.

This contract deliberately has no ``source_system`` *credential* and no
endpoint — only an opaque ``source_ref`` (e.g. a connector-config reference or
an instrument id) that a later phase resolves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = ["ProvenanceRef", "SecretInProvenance"]


class SecretInProvenance(ContractViolation):
    """A provenance value looked like credential material. Refused."""


#: Coarse secret markers, checked as case-insensitive substrings. Deliberately
#: dependency-free (the contracts layer imports nothing but stdlib basics and
#: other contracts — no ``re``): the platform firewall is richer and lives
#: above this layer. This is a tripwire, not the defence — provenance carries
#: references, so a secret here is already a bug this only surfaces loudly.
_SECRET_MARKERS = (
    "authorization:", "authorization =", "authorization=",
    "bearer ", "ghp_", "gho_", "ghs_", "xoxb-", "xoxp-", "xoxa-", "xoxr-",
    "sk-", "akia", "private key-----", "token=", "token =", "token:",
    "password=", "password =", "password:", "secret=", "secret:",
)


def _looks_secret(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)

#: Fields that hold references. Each is checked for secret shapes.
_REF_FIELDS = (
    "produced_by",
    "source_ref",
    "observation_ref",
    "execution_ref",
    "trace_ref",
    "parent_claim_ref",
)


@dataclass(frozen=True)
class ProvenanceRef(Contract):
    """Reference-only lineage for an epistemic record (Part L, Part F).

    ``produced_by`` names the agent/instrument that produced the record (e.g.
    ``"connector:grafana"``, ``"derivation:infra-facts/1"``) — required, so
    every record answers "who/what produced this". The ``*_ref`` fields are
    optional pointers at immutable anchors; at least one must be present besides
    ``produced_by`` so provenance is never a bare label (``BND-PROVENANCE-
    REQUIRED`` at the type level for records that demand grounding).

    None of these fields may contain a credential. That is the contract.
    """

    CONTRACT_NAME = "cortexprime.world.provenance_ref"

    produced_by: str
    source_ref: Optional[str] = None
    observation_ref: Optional[str] = None
    execution_ref: Optional[str] = None
    trace_ref: Optional[str] = None
    parent_claim_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.produced_by, str) or not self.produced_by.strip():
            raise ContractViolation(
                "produced_by is required; every record names what produced it"
            )
        for field in _REF_FIELDS:
            value = getattr(self, field)
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{field} must be a non-empty reference string or None"
                )
            if _looks_secret(value):
                raise SecretInProvenance(
                    f"provenance field {field!r} looks like credential material; "
                    "provenance carries references and hashes, never secrets"
                )

    @property
    def anchors(self) -> tuple[str, ...]:
        """The reference anchors present (excluding the producer label)."""
        return tuple(
            getattr(self, f)
            for f in _REF_FIELDS[1:]
            if getattr(self, f) is not None
        )

    @property
    def grounds_a_claim(self) -> bool:
        """Whether this provenance carries at least one anchor beyond the
        producer label — the minimum for grounding a Fact/Belief/Outcome."""
        return len(self.anchors) >= 1

    def with_observation(self, observation_ref: str) -> "ProvenanceRef":
        """A copy naming an observation anchor. Used by the (future) ingestion
        boundary when it derives a fact from an observation."""
        from dataclasses import replace

        return replace(self, observation_ref=observation_ref)
