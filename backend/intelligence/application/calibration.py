"""Empirical calibration & reliability — Phase 8.7 (ADR-078).

Derives reliability from REAL historical prediction outcomes in the durable ledgers,
never from model-stated confidence. Because CortexPrime emits no model probability,
there is no probability-vs-frequency curve to fit; the honest quantity is the
empirical reliability of a prediction CLASS — the fraction of decided outcomes that
held, with an interval around that estimate, stratified so incompatible runtime
versions never merge, temporally safe so future outcomes never leak backward, and
returning INSUFFICIENT_DATA (never fake precision) when the sample is too small.

The reader ports (composition supplies the SQL repositories) keep this module fenced:
it imports no World storage, no connector, no provider, and never the World grounded
constructors — so it can read a verification's verdict but never mint one. It
produces advisory evidence only; it cannot authorize, execute, or change World truth
(BND-INTELLIGENCE-CANNOT-EXECUTE / -CREATE-FACT / -BYPASS-WORLD).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import NormalDist
from typing import Any, Optional, Protocol

from backend.contracts.tenant import TenantRef
from backend.contracts.world import CalibrationState, ClaimConfidence
from backend.platform.hashing import compute_digest
from backend.contracts.intelligence.calibration import (
    AssuranceTier,
    CalibrationDataset,
    CalibrationEligibility,
    CalibrationPolicy,
    CalibrationSample,
    CalibrationStatus,
    DriftStatus,
    OutcomeLabel,
    PredictionClass,
    ReliabilityEstimate,
    ReliabilityInterval,
)

__all__ = [
    "VerdictView",
    "PredictionRecordPort",
    "VerificationRecordPort",
    "HumanAdjudicationPort",
    "wilson_interval",
    "CalibrationDatasetBuilder",
    "ReliabilityEstimator",
    "DriftDetector",
]

_DIMENSIONS = ("subject_type", "predicate", "environment", "model_identity", "harness_version")


# -- deterministic digests (computed here; the contracts stay hash-free) --------

def hash_policy(policy: CalibrationPolicy) -> str:
    return compute_digest(policy.to_dict()).value[:16]


def hash_dataset(dataset: CalibrationDataset) -> str:
    return compute_digest(dataset.digest_payload()).value


def hash_result(estimate: ReliabilityEstimate) -> str:
    return compute_digest(estimate.to_dict()).value


@dataclass(frozen=True)
class VerdictView:
    """The minimal independent-verification view the calibrator consumes — the
    verdict value and when it was decided. Composition maps a WorldVerification to
    this so the intelligence plane never imports/mints a WorldVerification."""

    verdict: str                 # "supported" / "unsupported" / "insufficient_evidence"
    verified_at: datetime
    verification_ref: str


class PredictionRecordPort(Protocol):
    """Reads reasoning records by kind, with an optional as-known cut (composition
    backs it with the SQL reasoning repository). Returns record-like objects with
    ``.record`` (dict), ``.refs`` (dict), ``.recorded_at``, ``.predicate``."""

    def list_by_kind(self, *, tenant_id: str, kind: str,
                     known_at: Optional[datetime] = None) -> tuple:
        ...


class VerificationRecordPort(Protocol):
    def list_for_subject(self, *, tenant_id: str, subject_ref: str, predicate: str,
                         known_at: Optional[datetime] = None) -> tuple[VerdictView, ...]:
        ...


class HumanAdjudicationPort(Protocol):
    """Optional: whether a prediction's investigation carried a human adjudication —
    a DISTINCT signal, never a rewrite of World truth (Part P)."""

    def adjudicated_refs(self, *, tenant_id: str) -> frozenset:
        ...


def wilson_interval(successes: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """The Wilson score interval for a binomial proportion — a documented, standard
    method for binary outcomes with small samples (no dependency, deterministic).
    Rounded to 6 dp so repeated runs produce identical digests (reproducibility)."""
    if n <= 0:
        return (0.0, 1.0)
    z = NormalDist().inv_cdf(1.0 - (1.0 - level) / 2.0)
    phat = successes / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    margin = (z * ((phat * (1.0 - phat) / n + z * z / (4.0 * n * n)) ** 0.5)) / denom
    return (round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6))


def _class_matches(sample_class: PredictionClass, query: PredictionClass) -> bool:
    """A sample belongs to ``query`` if every query dimension is either the wildcard
    ``*`` or equals the sample's. model/harness are never wildcarded by ``broaden``,
    so versions never silently merge."""
    return all(getattr(query, d) == "*" or getattr(query, d) == getattr(sample_class, d)
               for d in _DIMENSIONS)


class CalibrationDatasetBuilder:
    """Builds a reproducible calibration dataset by joining predictions, evaluations,
    and independent verifications from the ledgers — deterministic, temporally safe,
    tenant-scoped. It NEVER reads model-stated confidence."""

    def __init__(self, *, prediction_port: PredictionRecordPort,
                 verification_port: VerificationRecordPort,
                 human_port: Optional[HumanAdjudicationPort] = None,
                 environment: str = "unknown") -> None:
        self._pred = prediction_port
        self._verif = verification_port
        self._human = human_port
        self._env = environment

    def build(
        self, *, tenant: TenantRef, policy: CalibrationPolicy, now: datetime,
        known_at: Optional[datetime] = None, time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None, provider_label: str = "scripted",
        experience_prediction_refs: frozenset = frozenset(),
    ) -> CalibrationDataset:
        if not isinstance(tenant, TenantRef):
            raise TypeError("tenant must be an explicit TenantRef (fail closed)")
        preds = self._pred.list_by_kind(tenant_id=tenant.tenant_id, kind="prediction", known_at=known_at)
        evals = self._pred.list_by_kind(tenant_id=tenant.tenant_id, kind="prediction_evaluation",
                                        known_at=known_at)
        eval_by_pred: dict = {}
        for e in evals:
            pref = (e.refs or {}).get("prediction_ref") or (e.record or {}).get("prediction_ref")
            if pref and pref not in eval_by_pred:   # first (oldest) evaluation wins; dedupe
                eval_by_pred[pref] = e
        adjudicated = (self._human.adjudicated_refs(tenant_id=tenant.tenant_id)
                       if self._human else frozenset())

        samples: list[CalibrationSample] = []
        seen: set = set()
        model_ids, harness_vers = set(), set()
        for p in preds:
            rec = p.record or {}
            pred_ref = rec.get("record_id")
            if not pred_ref or pred_ref in seen:    # duplicate predictions never inflate the count (Part T#4)
                continue
            if time_from and p.recorded_at < time_from:
                continue
            if time_to and p.recorded_at > time_to:
                continue
            seen.add(pred_ref)
            sample = self._sample_for(
                tenant=tenant, prediction=p, evaluation=eval_by_pred.get(pred_ref),
                policy=policy, known_at=known_at, uses_experience=pred_ref in experience_prediction_refs,
                human=(pred_ref in adjudicated))
            samples.append(sample)
            model_ids.add(sample.model_identity)
            harness_vers.add(sample.harness_version)
        return CalibrationDataset(
            tenant_id=tenant.tenant_id, policy_digest=hash_policy(policy), generated_at=now,
            samples=tuple(samples), time_from=time_from, time_to=time_to, known_at=known_at,
            model_identities=tuple(sorted(model_ids)), harness_versions=tuple(sorted(harness_vers)),
            algorithm_version=policy.algorithm_version, provider_label=provider_label)

    def _sample_for(self, *, tenant, prediction, evaluation, policy, known_at,
                    uses_experience, human) -> CalibrationSample:
        rec = prediction.record or {}
        refs = prediction.refs or {}
        pred_ref = rec.get("record_id")
        subject = rec.get("subject_ref") or ""
        predicate = rec.get("predicate") or prediction.predicate or ""
        model_id = rec.get("model_ref") or "unknown"
        harness_v = refs.get("harness_version") or "unknown"
        subject_type = subject.split("/", 1)[0] if "/" in subject else (subject or "unknown")
        pclass = PredictionClass(subject_type=subject_type or "unknown", predicate=predicate or "unknown",
                                 environment=self._env, model_identity=model_id, harness_version=harness_v)

        def mk(eligibility, outcome, tier, matched=None, within=None, verif_ref=None):
            return CalibrationSample(
                prediction_ref=pred_ref, prediction_class=pclass, eligibility=eligibility,
                outcome_label=outcome, assurance_tier=tier, matched=matched, within_horizon=within,
                subject_ref=subject, predicate=predicate or "unknown", model_identity=model_id,
                harness_version=harness_v, recorded_at=prediction.recorded_at,
                execution_ref=(evaluation.refs or {}).get("execution_ref") if evaluation else None,
                verification_ref=verif_ref, uses_experience=uses_experience, human_adjudicated=human)

        if evaluation is None:
            # no observed outcome yet — censored, preserved (Part D), never a failure.
            return mk(CalibrationEligibility.PENDING_OUTCOME, OutcomeLabel.PENDING,
                      AssuranceTier.INSUFFICIENT_OUTCOME)
        erec = evaluation.record or {}
        matched = erec.get("matched")
        within = erec.get("within_horizon")
        if policy.require_within_horizon and within is False:
            # a late outcome is censored, NOT a failure (STALE != FALSE).
            return mk(CalibrationEligibility.INSUFFICIENT_EVIDENCE, OutcomeLabel.INSUFFICIENT_EVIDENCE,
                      AssuranceTier.INSUFFICIENT_OUTCOME, matched, within)
        verif = self._pick_verification(tenant, subject, predicate, rec, known_at)
        if verif is None:
            # decided by the deterministic evaluation only — UNASSURED population.
            if matched:
                return mk(CalibrationEligibility.ELIGIBLE, OutcomeLabel.SUPPORTED,
                          AssuranceTier.SUPPORTED_OUTCOME, matched, within)
            return mk(CalibrationEligibility.ELIGIBLE, OutcomeLabel.UNSUPPORTED,
                      AssuranceTier.UNASSURED_OUTCOME, matched, within)
        v = verif.verdict
        if v == "supported":
            return mk(CalibrationEligibility.ELIGIBLE, OutcomeLabel.SUPPORTED,
                      AssuranceTier.ASSURED_OUTCOME, matched, within, verif.verification_ref)
        if v == "unsupported":
            return mk(CalibrationEligibility.ELIGIBLE, OutcomeLabel.UNSUPPORTED,
                      AssuranceTier.ASSURED_OUTCOME, matched, within, verif.verification_ref)
        # insufficient_evidence / conflicted -> censored (UNKNOWN/CONFLICTED != FALSE, Part E/K).
        return mk(CalibrationEligibility.INSUFFICIENT_EVIDENCE, OutcomeLabel.INSUFFICIENT_EVIDENCE,
                  AssuranceTier.INSUFFICIENT_OUTCOME, matched, within, verif.verification_ref)

    def _pick_verification(self, tenant, subject, predicate, pred_record, known_at):
        """Join a verification to this prediction by (subject, predicate) within the
        prediction's window (verification has no execution_ref column, so the link is
        the subject/predicate pair — the latest decisive verdict inside the horizon)."""
        verifs = self._verif.list_for_subject(
            tenant_id=tenant.tenant_id, subject_ref=subject, predicate=predicate, known_at=known_at)
        if not verifs:
            return None
        predicted_at = _parse(pred_record.get("predicted_at"))
        deadline = _parse(pred_record.get("deadline"))
        in_window = [v for v in verifs
                     if (predicted_at is None or v.verified_at >= predicted_at)
                     and (deadline is None or v.verified_at <= deadline)]
        pool = in_window or list(verifs)
        return sorted(pool, key=lambda v: v.verified_at)[-1]


def _parse(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


class ReliabilityEstimator:
    """Computes the empirical reliability of a prediction class from a dataset —
    counts, a Wilson interval, and a calibrated ClaimConfidence ONLY when the sample
    supports it. INSUFFICIENT_DATA is a valid, preferred outcome (Part I/J)."""

    def estimate(
        self, *, dataset: CalibrationDataset, prediction_class: PredictionClass,
        policy: CalibrationPolicy, now: datetime, allow_fallback: bool = True,
    ) -> ReliabilityEstimate:
        samples = tuple(s for s in dataset.samples
                        if _class_matches(s.prediction_class, prediction_class))
        decided = [s for s in samples if s.is_decided]
        supported = [s for s in decided if s.outcome_label is OutcomeLabel.SUPPORTED]
        unsupported = [s for s in decided if s.outcome_label is OutcomeLabel.UNSUPPORTED]
        insufficient = [s for s in samples if s.outcome_label is OutcomeLabel.INSUFFICIENT_EVIDENCE]
        conflicted = [s for s in samples if s.outcome_label is OutcomeLabel.CONFLICTED]
        pending = [s for s in samples if s.outcome_label is OutcomeLabel.PENDING]
        assured = [s for s in decided if s.assurance_tier is AssuranceTier.ASSURED_OUTCOME]

        def build(status, *, rate=None, interval=None, coverage=None, confidence=None,
                  fallback=False, fallback_from=None, note=""):
            return ReliabilityEstimate(
                prediction_class=prediction_class, status=status, sample_count=len(samples),
                decided_count=len(decided), supported_count=len(supported),
                unsupported_count=len(unsupported), insufficient_count=len(insufficient),
                conflicted_count=len(conflicted), pending_count=len(pending),
                assured_count=len(assured), dataset_digest=hash_dataset(dataset),
                policy_digest=hash_policy(policy), confidence=confidence or ClaimConfidence.uncalibrated(),
                generated_at=now, support_rate=rate, interval=interval, assurance_coverage=coverage,
                fallback_applied=fallback, fallback_from=fallback_from, reliability_note=note)

        if len(decided) < policy.min_decided_samples:
            broader = prediction_class.broaden()
            if allow_fallback and broader is not None:
                est = self.estimate(dataset=dataset, prediction_class=broader, policy=policy,
                                    now=now, allow_fallback=True)
                if est.status is not CalibrationStatus.INSUFFICIENT_DATA:
                    # re-badge as an explicit fallback from the requested class.
                    return ReliabilityEstimate(
                        prediction_class=est.prediction_class, status=est.status,
                        sample_count=est.sample_count, decided_count=est.decided_count,
                        supported_count=est.supported_count, unsupported_count=est.unsupported_count,
                        insufficient_count=est.insufficient_count, conflicted_count=est.conflicted_count,
                        pending_count=est.pending_count, assured_count=est.assured_count,
                        dataset_digest=est.dataset_digest, policy_digest=est.policy_digest,
                        confidence=est.confidence, generated_at=now, support_rate=est.support_rate,
                        interval=est.interval, assurance_coverage=est.assurance_coverage,
                        fallback_applied=True, fallback_from=prediction_class.to_dict(),
                        reliability_note=("insufficient data for the requested class; broadened to "
                                          f"{est.prediction_class.to_dict()}"))
            return build(CalibrationStatus.INSUFFICIENT_DATA,
                         note=f"only {len(decided)} decided outcomes (< {policy.min_decided_samples}); "
                              "INSUFFICIENT_DATA — no fake precision")

        rate = round(len(supported) / len(decided), 6)
        lo, hi = wilson_interval(len(supported), len(decided), policy.interval_level)
        interval = ReliabilityInterval(method=policy.interval_method, level=policy.interval_level,
                                       lower=lo, upper=hi)
        coverage = round(len(assured) / len(decided), 6)
        status = (CalibrationStatus.CALIBRATED if coverage >= policy.min_assurance_coverage
                  else CalibrationStatus.CALIBRATED_WITH_LIMITATIONS)
        note = (f"{len(supported)}/{len(decided)} decided outcomes supported; assurance coverage "
                f"{coverage:.2f}" + ("" if status is CalibrationStatus.CALIBRATED
                                     else " (below policy — limitations)"))
        return build(status, rate=rate, interval=interval, coverage=coverage,
                     confidence=ClaimConfidence.calibrated(rate), note=note)

    def compare_experience(
        self, *, dataset: CalibrationDataset, prediction_class: PredictionClass,
        policy: CalibrationPolicy, now: datetime,
    ) -> dict:
        """Measure WITH_EXPERIENCE vs WITHOUT_EXPERIENCE reliability (Part M). Returns
        both estimates; the platform never claims experience helped without evidence."""
        with_ds = _subset(dataset, lambda s: s.uses_experience)
        without_ds = _subset(dataset, lambda s: not s.uses_experience)
        return {
            "with_experience": self.estimate(dataset=with_ds, prediction_class=prediction_class,
                                             policy=policy, now=now, allow_fallback=False),
            "without_experience": self.estimate(dataset=without_ds, prediction_class=prediction_class,
                                                policy=policy, now=now, allow_fallback=False),
        }


def _subset(dataset: CalibrationDataset, predicate) -> CalibrationDataset:
    return CalibrationDataset(
        tenant_id=dataset.tenant_id, policy_digest=dataset.policy_digest,
        generated_at=dataset.generated_at, samples=tuple(s for s in dataset.samples if predicate(s)),
        time_from=dataset.time_from, time_to=dataset.time_to, known_at=dataset.known_at,
        model_identities=dataset.model_identities, harness_versions=dataset.harness_versions,
        algorithm_version=dataset.algorithm_version, provider_label=dataset.provider_label)


class DriftDetector:
    """Deterministic drift detection between two datasets of the same class: the
    documented policy is non-overlapping Wilson intervals (no magic threshold). When
    either side is INSUFFICIENT_DATA, the answer is UNKNOWN_DRIFT_STATUS — never a
    fabricated verdict (Part L/V)."""

    def __init__(self, *, estimator: Optional[ReliabilityEstimator] = None) -> None:
        self._estimator = estimator or ReliabilityEstimator()

    def compare(
        self, *, before: CalibrationDataset, after: CalibrationDataset,
        prediction_class: PredictionClass, policy: CalibrationPolicy, now: datetime,
    ) -> DriftStatus:
        a = self._estimator.estimate(dataset=before, prediction_class=prediction_class,
                                     policy=policy, now=now, allow_fallback=False)
        b = self._estimator.estimate(dataset=after, prediction_class=prediction_class,
                                     policy=policy, now=now, allow_fallback=False)
        if (a.status is CalibrationStatus.INSUFFICIENT_DATA
                or b.status is CalibrationStatus.INSUFFICIENT_DATA
                or a.interval is None or b.interval is None):
            return DriftStatus.UNKNOWN_DRIFT_STATUS
        if a.interval.upper < b.interval.lower or b.interval.upper < a.interval.lower:
            return DriftStatus.DRIFT_DETECTED
        return DriftStatus.NO_DRIFT
