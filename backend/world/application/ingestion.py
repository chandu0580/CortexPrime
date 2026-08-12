"""Observation ingestion — the World Plane's deterministic write boundary.

The one narrow path by which an external read becomes durable world state:

    governed READ result + governed context
            ↓  (deterministic mapping — no model)
    Observation (contract, tenant-scoped, provenanced, temporally honest)
            ↓  (secret firewall + validation)
    ObservationRepository.record  →  cw_observation

The hard invariants (ADR-064):
  * Tenant comes from the governed context, NEVER from the payload, the source
    name, model output, a URL, or connector metadata. A missing/ambiguous
    tenant fails closed.
  * Provenance is mandatory and reference-only; a value carrying credential
    material is refused before it is recorded (field-aware secret firewall).
  * Model output cannot become an Observation. There is no ``from_model`` /
    ``from_text`` path; the source kind has no MODEL member; the ingestion
    service accepts a ``ReadObservation`` produced by a governed read, never a
    model proposal.
  * Observation identity is deterministic (a digest over tenant, source,
    subject, predicate, observed_at, value) so a duplicate delivery dedupes
    rather than creating duplicate world state. At-least-once, not exactly-once.

This module imports only the epistemic contracts, the platform hashing and
secret-detection primitives, and stdlib. It does not touch a database, a
connector, the gateway, the harness, or the execution plane (composition
supplies the repository; the caller supplies the already-read result).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol

from backend.contracts.errors import ContractViolation
from backend.contracts.evidence import SourceStatus
from backend.contracts.tenant import TenantRef
from backend.contracts.world import (
    Observation,
    ObservationInstant,
    ObservationSource,
    ObservationSourceKind,
    ProvenanceRef,
)
from backend.platform.credentials.inspection import find_secrets
from backend.platform.hashing import compute_digest
from backend.platform.identity.generators import prefixed_id

__all__ = [
    "ObservationRepository",
    "ObservationIngestion",
    "ObservationRejected",
    "ReadObservation",
    "observation_identity",
]


class ObservationRejected(ContractViolation):
    """An observation was refused at the ingestion boundary. The refusal reason
    is the message; nothing was recorded and no provider was contacted by the
    boundary (the boundary never contacts a provider)."""


def observation_identity(observation: Observation) -> str:
    """The deterministic identity for idempotency (Part J).

    A digest over the fields that make two deliveries "the same observation":
    tenant, source, subject, predicate, the moment observed, and the observed
    value. NOT a blind hash of an arbitrary payload — the value is canonicalized
    through the platform's canonical digest, and the fields are named. Two
    identical external observations produce the same identity and collide on the
    unique constraint; a genuinely new observation (different value, or a later
    ``observed_at``) is a new identity and a new row.
    """
    return compute_digest(
        {
            "tenant": observation.tenant.tenant_id,
            "source_kind": observation.source.kind.value,
            "source_ref": observation.source.source_ref,
            "subject_ref": observation.subject_ref,
            "predicate": observation.predicate,
            "observed_at": observation.instant.observed_at.isoformat(),
            "value": observation.value,
        }
    ).value


class ObservationRepository(Protocol):
    """The durable sink. Composition supplies a SQL implementation; the World
    Plane depends only on this abstraction (Part B).

    Append-only by contract: ``record`` inserts (deduping on identity), and
    there is deliberately no ``update`` or ``delete`` method — an observation
    is immutable evidence (Part K)."""

    def record(self, observation: Observation, *, identity_digest: str) -> bool:
        """Persist the observation. Returns True if newly recorded, False if a
        prior observation with the same identity already existed (idempotent
        dedupe). Never raises on a duplicate — a duplicate is expected under
        at-least-once delivery."""
        ...


@dataclass(frozen=True)
class ReadObservation:
    """What a governed READ hands the ingestion boundary — the mapping input.

    This is a plain value object, produced by the composition layer *after* a
    governed provider read, carrying the facts needed to build an Observation.
    It is NOT a provider handle, a connector, or a credential — the boundary
    never reads a provider itself. ``source_kind`` names an instrument and can
    never be a model. ``observed_at`` is the instrument's report of when the
    world was in this state; for a plain read that reflects "now", the caller
    sets it equal to ``retrieved_at`` and says so.
    """

    source_kind: ObservationSourceKind
    source_ref: str
    subject_ref: str
    predicate: str
    value: Any
    status: SourceStatus
    observed_at: datetime
    retrieved_at: datetime
    produced_by: str
    execution_ref: Optional[str] = None
    trace_ref: Optional[str] = None


class ObservationIngestion:
    """Turns a governed read into a durable Observation, or refuses (Parts B–J).

    Constructed with a repository and the *governed tenant* — the tenant is
    fixed by the boundary's construction/context, never taken from the read
    result. ``ingest`` maps, validates (tenant, provenance, temporal, secrets),
    and records.
    """

    def __init__(self, *, repository: ObservationRepository) -> None:
        self._repository = repository

    def ingest(
        self,
        *,
        tenant: TenantRef,
        read: ReadObservation,
        recorded_at: datetime,
    ) -> tuple[Observation, bool]:
        """Record one observation from a governed read.

        ``tenant`` is supplied by the governed context, not the read. Returns
        ``(observation, newly_recorded)``. Raises :class:`ObservationRejected`
        for any refusal (invalid tenant, missing provenance, bad timestamps,
        secret-bearing value, malformed observation) — before touching the
        repository.
        """
        if not isinstance(tenant, TenantRef):
            raise ObservationRejected(
                "tenant must be an explicit TenantRef from the governed context; "
                "the World Plane never infers tenant from a payload or a source")
        if not isinstance(read, ReadObservation):
            raise ObservationRejected("ingest requires a ReadObservation")

        # Secret firewall (Part Q): a value carrying credential material is
        # refused before it is recorded, field-aware and nested-structure aware.
        findings = find_secrets(read.value)
        if findings:
            where = ", ".join(f"{f.path} ({f.why})" for f in findings[:6])
            raise ObservationRejected(
                f"observation value carries secret-shaped material ({where}); "
                "the World Plane records references, never credentials")
        # Provenance references must also be secret-free (defence in depth); the
        # ProvenanceRef contract raises SecretInProvenance on construction below.

        # Build the immutable Observation. Contract validation enforces the
        # non-MODEL source kind, tz-aware distinct times, and the SourceStatus
        # value/absence rule.
        try:
            source = ObservationSource(kind=read.source_kind, source_ref=read.source_ref)
            instant = ObservationInstant(
                observed_at=read.observed_at, retrieved_at=read.retrieved_at)
            provenance = ProvenanceRef(
                produced_by=read.produced_by,
                source_ref=read.source_ref,
                execution_ref=read.execution_ref,
                trace_ref=read.trace_ref,
            )
            observation = Observation(
                record_id=prefixed_id("wobs"),
                tenant=tenant,
                recorded_at=recorded_at,
                provenance=provenance,
                source=source,
                subject_ref=read.subject_ref,
                predicate=read.predicate,
                value=read.value,
                status=read.status,
                instant=instant,
            )
        except ContractViolation as exc:
            raise ObservationRejected(f"malformed observation: {exc}") from exc

        identity = observation_identity(observation)
        newly = self._repository.record(observation, identity_digest=identity)
        return observation, newly
