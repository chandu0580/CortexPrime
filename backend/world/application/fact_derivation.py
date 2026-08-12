"""Deterministic Observation -> Fact derivation — the World Plane fact boundary.

The one narrow, deterministic path by which a grounded observation becomes a
bitemporal world fact:

    Observation (real, instrument-grounded, never a model)
            |  (deterministic reconciliation — no LLM, no provider, no clock read here)
    Fact (contract: subject/predicate/value, valid-time, authority, status)
            |
    FactRepository.record  ->  cw_fact  (append-only version)

The hard invariants (ADR-065; L1-L16):
  * A Fact is derived ONLY from a real ``Observation`` object — which itself can
    never come from a model (no MODEL observation source). Model output cannot
    create a Fact. There is no text/proposal path here.
  * Tenant comes from the governed context and must match the observation's
    tenant; a mismatch fails closed.
  * valid time (``valid_from`` = the instrument's ``observed_at``) is independent
    of knowledge time (``recorded_at``, supplied by the caller). Neither is
    inferred from the other.
  * Reconciliation is deterministic and policy-free: valid-time succession for a
    later/earlier world change, CONFLICTED for two values at the SAME valid
    instant (no authority to choose — never latest-wins), idempotent no-op when
    the value at that instant is already what we hold.
  * A non-informative observation (empty / unavailable / not-configured) derives
    NO fact — the identity simply stays UNKNOWN. Absence is not FALSE.
  * No freshness policy is invented: STALE is never emitted here (deferred until
    an explicit policy exists). No confidence is invented: a Fact carries no
    ``ClaimConfidence`` at all, and a model-stated confidence can never become
    one (separate, unconvertible types).

This module imports the epistemic contracts, the platform digest, and the
bitemporal projection only. It touches no database, connector, gateway, harness,
credential, scheduler, or execution — composition supplies the repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol

from backend.contracts.errors import ContractViolation
from backend.contracts.evidence import SourceStatus
from backend.contracts.knowledge import KnowledgeAuthority
from backend.contracts.tenant import TenantRef
from backend.contracts.world import (
    EpistemicStatus,
    Fact,
    Observation,
    ProvenanceRef,
    ValidityInterval,
)
from backend.platform.hashing import compute_digest
from backend.platform.identity.generators import prefixed_id
from backend.world.application.bitemporal import (
    FactVersion,
    project_valid_at,
)

__all__ = [
    "FactRepository",
    "FactDerivation",
    "FactDerivationRejected",
    "DerivationOutcome",
    "DerivationResult",
    "fact_semantic_identity",
    "fact_version_identity",
]


class FactDerivationRejected(ContractViolation):
    """A derivation was refused at the fact boundary (invalid tenant, malformed
    fact). Nothing was recorded; no provider was contacted (the boundary never
    contacts one)."""


def fact_semantic_identity(
    tenant: TenantRef, subject_ref: str, predicate: str
) -> str:
    """The semantic identity of a real-world proposition (Part 3).

    A digest over (tenant, subject_ref, predicate) — NOT the value and NOT a
    random UUID. Every version/state of "deployment/payments spec.replicas"
    shares this identity, so repeated and changing observations of the same
    proposition resolve to one identity with many versions. Tenant is part of
    the identity, so the same subject/predicate in two tenants is two
    propositions."""
    return compute_digest(
        {
            "tenant": tenant.tenant_id,
            "subject_ref": subject_ref,
            "predicate": predicate,
        }
    ).value


def fact_version_identity(
    semantic_identity: str, value: Any, valid_from: datetime
) -> str:
    """The deterministic identity of one fact VERSION (Part 15, idempotency).

    A digest over (semantic_identity, value, valid_from). The same observation
    derived twice yields the same version identity and dedupes on the unique
    constraint; a changed value or a different valid_from is a new version. The
    value is canonicalized (key-order independent), like the observation digest.
    At-least-once with deterministic identity — not exactly-once."""
    return compute_digest(
        {
            "semantic_identity": semantic_identity,
            "value": value,
            "valid_from": valid_from.isoformat(),
        }
    ).value


class DerivationOutcome(str, Enum):
    """What the deterministic reconciliation decided."""

    ASSERTED = "asserted"
    """A new AFFIRMED fact version (first assertion or valid-time succession)."""
    CONFLICTED = "conflicted"
    """A new CONFLICTED fact version: a different value at a valid instant that
    already holds another value, with no authority to choose. Both retained."""
    DEDUPED = "deduped"
    """The value at that valid instant is already what we hold — idempotent
    no-op, nothing recorded."""
    SKIPPED_NON_INFORMATIVE = "skipped_non_informative"
    """The observation carried no value (empty / unavailable / not-configured);
    no fact is derived. The identity stays UNKNOWN — absence is not FALSE."""


@dataclass(frozen=True)
class DerivationResult:
    """The outcome of one derivation. ``fact`` is present only when a version was
    recorded (ASSERTED / CONFLICTED); ``newly`` is False when the durable insert
    deduped on the version identity."""

    outcome: DerivationOutcome
    fact: Optional[Fact]
    newly: bool
    reason: str
    parent_claim_ref: Optional[str] = None


class FactRepository(Protocol):
    """The durable fact ledger. Composition supplies a SQL implementation; the
    World Plane depends only on this abstraction.

    Append-only by contract: ``record`` inserts a version (deduping on the
    version identity), ``versions_for`` reads a semantic identity's history
    tenant-scoped, and there is deliberately no ``update`` or ``delete`` — a
    correction or a world change is a new version, never an overwrite (Part 7)."""

    def record(
        self,
        fact: Fact,
        *,
        version_digest: str,
        semantic_identity: str,
        value_digest: str,
    ) -> bool:
        """Persist one fact version. Returns True if newly recorded, False if a
        version with the same identity already existed (idempotent dedupe)."""
        ...

    def versions_for(
        self, *, tenant_id: str, semantic_identity: str
    ) -> tuple[FactVersion, ...]:
        """Every version for a semantic identity, tenant-scoped. A cross-tenant
        identity returns nothing (fail closed)."""
        ...


class FactDerivation:
    """Turns a grounded observation into a durable bitemporal fact, or decides a
    no-op — deterministically (Part 2, 14).

    Constructed with a repository. ``derive`` validates, reconciles against the
    existing versions, constructs a grounded ``Fact``, and records it. No model,
    no provider, no clock read of its own (the caller supplies knowledge time).
    """

    def __init__(
        self,
        *,
        repository: FactRepository,
        produced_by: str = "derivation:world-facts/1",
        authority: KnowledgeAuthority = KnowledgeAuthority.ADVISORY,
    ) -> None:
        self._repository = repository
        self._produced_by = produced_by
        # A single uncorroborated instrument grounds an ADVISORY fact — authority
        # is provenance-derived, never a number a model invents. Corroboration /
        # authoritative-source promotion is a later phase.
        self._authority = authority

    def derive(
        self,
        *,
        tenant: TenantRef,
        observation: Observation,
        recorded_at: datetime,
    ) -> DerivationResult:
        """Derive at most one fact version from one observation.

        ``tenant`` is the governed context's tenant and must match the
        observation's tenant (fail closed). ``recorded_at`` is the knowledge
        time — supplied by the caller, independent of the observation's valid
        time. Returns a :class:`DerivationResult`; raises
        :class:`FactDerivationRejected` only for a structural refusal."""
        if not isinstance(tenant, TenantRef):
            raise FactDerivationRejected(
                "tenant must be an explicit TenantRef from the governed context")
        if not isinstance(observation, Observation):
            raise FactDerivationRejected(
                "a fact is derived only from a real Observation object; model "
                "output cannot create a fact (there is no text/proposal path)")
        if observation.tenant.tenant_id != tenant.tenant_id:
            raise FactDerivationRejected(
                "the observation belongs to a different tenant than the governed "
                "context; a fact is never derived across tenants (fail closed)")

        # A non-informative observation carries no value to assert. No fact is
        # derived; the identity stays UNKNOWN. (Absence is not FALSE.)
        if observation.status is not SourceStatus.RETURNED_DATA or observation.value is None:
            return DerivationResult(
                outcome=DerivationOutcome.SKIPPED_NON_INFORMATIVE,
                fact=None, newly=False,
                reason=(f"observation status {observation.status.value} carries no "
                        "value; no fact derived (UNKNOWN, not FALSE)"))

        subject_ref = observation.subject_ref
        predicate = observation.predicate
        value = observation.value
        valid_from = observation.instant.observed_at
        semantic_identity = fact_semantic_identity(tenant, subject_ref, predicate)
        value_digest = compute_digest(value).value

        current = self._repository.versions_for(
            tenant_id=tenant.tenant_id, semantic_identity=semantic_identity)

        # Deterministic reconciliation against the value effective at this valid
        # instant under current knowledge.
        effective = project_valid_at(current, valid_from)
        status = EpistemicStatus.AFFIRMED
        parent_claim_ref: Optional[str] = None
        outcome = DerivationOutcome.ASSERTED

        if effective.status is EpistemicStatus.UNKNOWN:
            # Nothing covers this valid instant yet — first assertion (or a new
            # earliest/interleaving world state). AFFIRMED, no parent.
            pass
        elif effective.status is EpistemicStatus.AFFIRMED:
            if effective.value_digest == value_digest:
                # The value effective here is already what we hold — idempotent.
                return DerivationResult(
                    outcome=DerivationOutcome.DEDUPED, fact=None, newly=False,
                    reason="value already effective at this valid instant")
            parent_claim_ref = effective.fact_ids[0] if effective.fact_ids else None
            if effective.valid_from == valid_from:
                # Same valid instant, different value, no authority: CONFLICTED.
                status = EpistemicStatus.CONFLICTED
                outcome = DerivationOutcome.CONFLICTED
            # else: strictly later/earlier valid_from -> valid-time succession,
            # AFFIRMED (the prior version's interval is bounded at query time).
        else:  # already CONFLICTED at this instant
            parent_claim_ref = effective.fact_ids[0] if effective.fact_ids else None
            # A value equal to one already present at this instant dedupes; a
            # further different value stays CONFLICTED. Either way this is not a
            # clean affirmation.
            if any(v.value_digest == value_digest and v.valid_from == valid_from
                   for v in current):
                return DerivationResult(
                    outcome=DerivationOutcome.DEDUPED, fact=None, newly=False,
                    reason="value already present at this conflicted instant")
            status = EpistemicStatus.CONFLICTED
            outcome = DerivationOutcome.CONFLICTED

        # Build the grounded, immutable Fact. Provenance carries the full chain:
        # the observation it derives from, and the observation's own execution /
        # trace anchors, so Fact -> Observation -> execution -> audit is
        # traceable. parent_claim_ref names the prior version it succeeds/conflicts
        # with (references, never deletion).
        try:
            provenance = ProvenanceRef(
                produced_by=self._produced_by,
                observation_ref=observation.record_id,
                execution_ref=observation.provenance.execution_ref,
                trace_ref=observation.provenance.trace_ref,
                parent_claim_ref=parent_claim_ref,
            )
            fact = Fact(
                record_id=prefixed_id("wfact"),
                tenant=tenant,
                recorded_at=recorded_at,
                provenance=provenance,
                subject_ref=subject_ref,
                predicate=predicate,
                value=value,
                validity=ValidityInterval(valid_from=valid_from),  # open, as asserted
                authority=self._authority,
                status=status,
            )
        except ContractViolation as exc:
            raise FactDerivationRejected(f"malformed fact: {exc}") from exc

        version_digest = fact_version_identity(semantic_identity, value, valid_from)
        newly = self._repository.record(
            fact, version_digest=version_digest,
            semantic_identity=semantic_identity, value_digest=value_digest)
        return DerivationResult(
            outcome=outcome, fact=fact, newly=newly,
            reason=status.value, parent_claim_ref=parent_claim_ref)
