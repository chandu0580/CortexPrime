"""The Assurance verifier — independent adjudication that mints WorldVerification.

The evaluator never accepts a model's assertion as evidence. Given a typed
procedure naming a claim, it obtains evidence *independently* from the World Plane
(via ``WorldQuery``), applies deterministic failure semantics, and produces a
``WorldVerification`` carrying a ``Verdict`` (SUPPORTED / UNSUPPORTED /
INSUFFICIENT_EVIDENCE), an explicit ``VerifierIdentity``, the procedure, and the
independent evidence it cited.

Structural firewalls (Constitution P5; ADR-062/069):
  * The verifier's reasoning path must differ from the claim's producer — a
    verifier that shares the producer's path is self-verification and is refused.
  * The platform verifier is DETERMINISTIC (``model_identifier=None``): a criteria
    check against world state needs no model and is stronger for it.
  * Evidence comes from the World ledgers, never from the claim. UNKNOWN world
    state, CONFLICTED evidence, and (under policy) STALE or unknown-lineage
    evidence can never return SUPPORTED — verifier failure is never success.

Imports the World read layer and the epistemic contracts only. No connector,
gateway, transport, credential, scheduler, or execution: assurance evaluates, it
never acts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol

from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef
from backend.contracts.verification import Verdict, VerifierIdentity
from backend.contracts.world import (
    EpistemicStatus,
    ProvenanceRef,
    SourceAuthority,
    WorldVerification,
)
from backend.platform.hashing import compute_digest
from backend.platform.identity.generators import prefixed_id
from backend.world.application import (
    FreshnessState,
    LineagePolicy,
    ObservationEvidence,
    WorldQuery,
)
from backend.assurance.application.policy import AssurancePolicy
from backend.assurance.application.procedures import (
    VerificationProcedure,
    VerificationProcedureKind,
)

__all__ = [
    "AssuranceRefused",
    "AssuranceResult",
    "VerificationRepository",
    "AssuranceVerifier",
    "DEFAULT_VERIFIER_IDENTITY",
]

#: The platform's deterministic verifier. No model — a criteria check against
#: world state is stronger for having none. Its reasoning path is fixed and
#: distinct from any model reasoning path, so it is independent by construction.
DEFAULT_VERIFIER_IDENTITY = VerifierIdentity(
    verifier_id="assurance:world-verifier/1",
    reasoning_path_id="assurance:deterministic-world-check/1",
    model_identifier=None,
)


class AssuranceRefused(ContractViolation):
    """A verification could not even be attempted (bad tenant, self-verification,
    unknown procedure). Distinct from a verdict — nothing was adjudicated."""


class VerificationRepository(Protocol):
    """The durable, append-only sink for minted verifications. Tenant-scoped,
    fail-closed. There is no update or delete — a verification is an immutable
    historical decision."""

    def record(
        self,
        verification: WorldVerification,
        *,
        identity_digest: str,
        predicate: str,
        producer_reasoning_path: str,
        verified_at: datetime,
    ) -> bool:
        """Persist the verification; return True if newly recorded, False if a
        verification with the same identity already existed (idempotent)."""
        ...


@dataclass(frozen=True)
class AssuranceResult:
    """A verification decision and the independent evidence behind it."""

    tenant_id: str
    subject_ref: str
    predicate: str
    expected: Any
    observed: Any
    verdict: Verdict
    verification: WorldVerification
    evidence: tuple[ObservationEvidence, ...]
    procedure_ref: str
    policy_ref: str
    rationale: str
    verified_at: datetime
    newly_recorded: bool = False

    @property
    def is_supported(self) -> bool:
        return self.verdict is Verdict.SUPPORTED

    def to_dict(self) -> dict:
        return {
            "what": {"subject_ref": self.subject_ref, "predicate": self.predicate,
                     "expected": self.expected, "observed": self.observed},
            "verdict": self.verdict.value,
            "verifier": {"verifier_id": self.verification.verifier.verifier_id,
                         "reasoning_path_id": self.verification.verifier.reasoning_path_id,
                         "model_identifier": self.verification.verifier.model_identifier},
            "procedure_ref": self.procedure_ref,
            "policy_ref": self.policy_ref,
            "evidence_refs": list(self.verification.evidence_refs),
            "evidence": [e.to_dict() for e in self.evidence],
            "rationale": self.rationale,
            "verified_at": self.verified_at.isoformat(),
            "tenant": self.tenant_id,
        }


def _verification_identity(
    *, tenant_id: str, procedure: VerificationProcedure,
    producer_reasoning_path: str, verified_at: datetime,
) -> str:
    return compute_digest({
        "tenant": tenant_id, "kind": procedure.kind.value,
        "subject_ref": procedure.subject_ref, "predicate": procedure.predicate,
        "expected": procedure.expected, "producer": producer_reasoning_path,
        "verified_at": verified_at.isoformat(),
    }).value


class AssuranceVerifier:
    """Independently verifies a claim and (optionally) records the decision.

    Constructed with a ``WorldQuery`` for independent evidence, an optional
    ``LineagePolicy`` (to reason about independence honestly), an ``AssurancePolicy``
    (the SUPPORTED bar), and an optional durable ``VerificationRepository``."""

    def __init__(
        self,
        *,
        query: WorldQuery,
        repository: Optional[VerificationRepository] = None,
        policy: Optional[AssurancePolicy] = None,
        lineage_policy: Optional[LineagePolicy] = None,
        produced_by: str = "assurance:world-verifier/1",
    ) -> None:
        self._query = query
        self._repository = repository
        self._policy = policy or AssurancePolicy.default()
        self._lineage = lineage_policy or LineagePolicy.none()
        self._produced_by = produced_by

    def verify(
        self,
        *,
        tenant: TenantRef,
        procedure: VerificationProcedure,
        producer_reasoning_path: str,
        verified_at: datetime,
        verifier: VerifierIdentity = DEFAULT_VERIFIER_IDENTITY,
        known_at: Optional[datetime] = None,
    ) -> AssuranceResult:
        """Adjudicate ``procedure``'s claim against independent world evidence.

        ``producer_reasoning_path`` is the reasoning path that produced the claim
        (a model's). ``verified_at`` is the knowledge time of the verification;
        for a world-state/prediction procedure it is also the valid time the
        evidence is obtained at (unless ``procedure.at_valid`` overrides)."""
        if not isinstance(tenant, TenantRef):
            raise AssuranceRefused("tenant must be an explicit TenantRef (fail closed)")
        if not isinstance(procedure, VerificationProcedure):
            raise AssuranceRefused("a typed VerificationProcedure is required")
        if not isinstance(procedure.kind, VerificationProcedureKind):
            raise AssuranceRefused("unknown verification procedure")
        # Independence firewall: the verifier may not share the producer's path.
        if not verifier.is_independent_of(producer_reasoning_path):
            raise AssuranceRefused(
                "the verifier shares the producer's reasoning path; "
                "self-verification is refused (Constitution P5)")

        at_valid = procedure.at_valid or verified_at
        # Independent evidence — obtained from the World ledger, never the claim.
        wqr = self._query.as_of_valid(
            tenant=tenant, subject_ref=procedure.subject_ref,
            predicate=procedure.predicate, at_valid=at_valid, now=verified_at,
            known_at=known_at)

        verdict, rationale = self._adjudicate(procedure, wqr)
        observed = wqr.effective_value
        evidence = wqr.evidence
        # SUPPORTED must cite evidence; if there is none, it cannot be SUPPORTED.
        evidence_refs = tuple(e.observation_id for e in evidence)
        if verdict is Verdict.SUPPORTED and not evidence_refs:
            verdict = Verdict.INSUFFICIENT_EVIDENCE
            rationale = "no citable evidence for a supported verdict"

        verification = WorldVerification(
            record_id=prefixed_id("wverif"), tenant=tenant, recorded_at=verified_at,
            provenance=ProvenanceRef(
                produced_by=self._produced_by,
                observation_ref=evidence_refs[0] if evidence_refs else None,
                execution_ref=procedure.execution_ref),
            subject_ref=procedure.subject_ref, procedure_ref=procedure.procedure_ref,
            verifier=verifier, verdict=verdict,
            evidence_refs=evidence_refs if verdict is Verdict.SUPPORTED else ())

        newly = False
        if self._repository is not None:
            identity = _verification_identity(
                tenant_id=tenant.tenant_id, procedure=procedure,
                producer_reasoning_path=producer_reasoning_path, verified_at=verified_at)
            newly = self._repository.record(
                verification, identity_digest=identity, predicate=procedure.predicate,
                producer_reasoning_path=producer_reasoning_path, verified_at=verified_at)

        return AssuranceResult(
            tenant_id=tenant.tenant_id, subject_ref=procedure.subject_ref,
            predicate=procedure.predicate, expected=procedure.expected,
            observed=observed, verdict=verdict, verification=verification,
            evidence=evidence, procedure_ref=procedure.procedure_ref,
            policy_ref=self._policy.policy_ref, rationale=rationale,
            verified_at=verified_at, newly_recorded=newly)

    # -- deterministic adjudication (failure semantics first) ---------------

    def _adjudicate(self, procedure, wqr) -> tuple[Verdict, str]:
        status = wqr.effective_status
        # Hard failure semantics — never convertible to SUPPORTED.
        if status is EpistemicStatus.UNKNOWN:
            return Verdict.INSUFFICIENT_EVIDENCE, "world state is UNKNOWN; nothing to verify against"
        if status is EpistemicStatus.CONFLICTED:
            return Verdict.INSUFFICIENT_EVIDENCE, "evidence is CONFLICTED; cannot adjudicate"
        if self._policy.require_fresh and wqr.freshness.state is FreshnessState.STALE:
            return Verdict.INSUFFICIENT_EVIDENCE, "evidence is STALE; policy requires fresh evidence"
        # Independence honesty: if the policy requires it, the evidence source
        # must have KNOWN lineage — unknown lineage cannot be claimed independent.
        if self._policy.require_known_lineage:
            if not wqr.evidence:
                return Verdict.INSUFFICIENT_EVIDENCE, "no evidence to establish lineage independence"
            lg = self._lineage.lineage_of(source_kind=wqr.evidence[0].source_kind,
                                          source_ref=wqr.evidence[0].source_ref)
            if not lg.is_known:
                return (Verdict.INSUFFICIENT_EVIDENCE,
                        "evidence lineage is UNKNOWN; independence cannot be proven")
        if self._policy.min_authority is not None:
            tier = wqr.evidence[0].tier if wqr.evidence else SourceAuthority.UNVERIFIED
            if not tier.at_least(self._policy.min_authority):
                return (Verdict.INSUFFICIENT_EVIDENCE,
                        f"evidence authority {tier.value} below required "
                        f"{self._policy.min_authority.value}")

        # Adequate, fresh, non-conflicted evidence: compare to the claim.
        observed_digest = compute_digest(wqr.effective_value).value
        expected_digest = compute_digest(procedure.expected).value
        if observed_digest == expected_digest:
            return Verdict.SUPPORTED, "independent world evidence matches the claimed value"
        return Verdict.UNSUPPORTED, "independent world evidence contradicts the claimed value"
