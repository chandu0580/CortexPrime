"""Detection → investigation, in production — Phase 11.3 (ADR-123).

This module is the composition layer that closes the seam Phases 8–11.2 left
open: nothing in ``backend/`` opened or advanced an investigation. Now:

    signal fabric candidates  ──▶  InvestigationHandoff.offer
                                     │  detect (deterministic, sustained)
                                     │  record the detection (cw_reasoning, idempotent)
                                     │  open ONE investigation per incident (cw_investigation)
                                     ▼
                              InvestigationRunner (one supervised thread)
                                     │  compose tools for THIS incident (frozen read-only allowlist)
                                     │  seed the differential, collect baseline evidence
                                     │  engine.step … (model proposes / plan proposes; platform decides)
                                     │  corroboration, assessment (categorical confidence), cost
                                     ▼
                              cw_investigation + cw_reasoning(assessment) + cp_harness_trace

Everything the runner composes already exists: ``GovernedCapabilityReader``,
``GovernedEvidenceAcquisition``, ``ToolRegistry``, ``InvestigationService``,
``InvestigationEngine``, ``GovernedModelBoundary``, ``WorldQuery``,
``BeliefFormation``. It composes NO dispatcher, NO write capability, NO
credential of its own. It runs inside the process that holds the runtime's
roles (ADR-122 F-1) — beside the signal worker in ``backend.main``.

Hard boundary: the runner OBSERVES, DETECTS, INVESTIGATES, EXPLAINS and
RECOMMENDS. Its tool registry refuses any operation whose declared side effect
is not READ at construction; there is no code path from here to
``GovernedCapabilityWriter``.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Optional

from backend.platform.hashing import compute_digest
from backend.signal.correlation import IncidentCandidate
from backend.signal.detection import DetectionEvent, DetectionPolicy, detect

log = logging.getLogger("cortexprime.investigation.runtime")

__all__ = [
    "InvestigationRuntimeConfig", "InvestigationHandoff", "InvestigationRunner",
    "InvestigationOutcome", "build_investigation_runtime", "start_embedded_investigator",
    "EmbeddedInvestigator", "incident_ref_for", "model_port_from_config",
]

POLICY_REF = "phase113-detection-investigation/1"
HARNESS_VERSION_LABEL = "phase113"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvestigationRuntimeConfig:
    tenant_id: str
    namespace: str
    model_provider: str = ""          # "" → deterministic plan only
    model_name: str = ""
    model_timeout_seconds: float = 180.0
    # A CrashLoop plan is twelve tests over seven distinct reads (the rest reuse
    # World evidence); a step is spent on a reuse too. Sixteen steps cover the
    # plan with room for a model's additions; twelve reads bound the world contact.
    max_steps: int = 16
    max_reads: int = 12
    # The context assembler's deterministic size budget (chars/4 estimate) for
    # each model proposal. Unchanged by default. A slow provider -- a small
    # local model on a contended CPU -- may be given a smaller one: the
    # assembler already drops lower-priority sections with a stated reason, and
    # the plan port learns what has run from the ledger, not the prompt (D-16).
    context_tokens: int = 4000
    # Answer tokens per model proposal. A reasoning model spends part of this
    # budget thinking before it writes JSON, so a hosted reasoning provider needs
    # more than the default (measured: glm-5.2 used 481 of 1024 tokens on a
    # two-field answer). Unchanged by default.
    model_max_output_tokens: int = 900
    max_seconds: float = 900.0
    max_tokens: int = 24000
    max_queue: int = 64
    resume_active: bool = True
    detection_policy: DetectionPolicy = DetectionPolicy()
    lookback_seconds: float = 1800.0

    @classmethod
    def from_env(cls, *, tenant_id: str, namespace: str) -> "InvestigationRuntimeConfig":
        def _f(name: str, default: float) -> float:
            raw = (os.getenv(name) or "").strip()
            return float(raw) if raw else default

        def _i(name: str, default: int) -> int:
            raw = (os.getenv(name) or "").strip()
            return int(raw) if raw else default

        return cls(
            tenant_id=tenant_id, namespace=namespace,
            model_provider=(os.getenv("CORTEX_INVESTIGATION_MODEL_PROVIDER") or "").strip(),
            model_name=(os.getenv("CORTEX_INVESTIGATION_MODEL") or "").strip(),
            model_timeout_seconds=_f("CORTEX_INVESTIGATION_MODEL_TIMEOUT_SECONDS", 180.0),
            max_steps=_i("CORTEX_INVESTIGATION_MAX_STEPS", 16),
            context_tokens=_i("CORTEX_INVESTIGATION_CONTEXT_TOKENS", 4000),
            model_max_output_tokens=_i("CORTEX_INVESTIGATION_MODEL_MAX_OUTPUT_TOKENS", 900),
            max_reads=_i("CORTEX_INVESTIGATION_MAX_READS", 12),
            max_seconds=_f("CORTEX_INVESTIGATION_MAX_SECONDS", 900.0),
            max_tokens=_i("CORTEX_INVESTIGATION_MAX_TOKENS", 24000),
            resume_active=(os.getenv("CORTEX_INVESTIGATION_RESUME") or "1").strip() != "0",
        )


def _parse_when(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def incident_ref_for(event: DetectionEvent) -> str:
    """The incident reference an investigation is opened for. The subject
    itself for a Kubernetes subject (the grammar the remediation service and
    the product API already parse); for an alert, the workload its labels name
    when they name one in this namespace, else the alert subject."""
    if event.subject_ref.startswith("kubernetes:"):
        return event.subject_ref
    labels = event.correlation or {}
    namespace = labels.get("namespace")
    pod = labels.get("pod")
    deployment = labels.get("deployment") or labels.get("service") or labels.get("job")
    if namespace and pod:
        return f"kubernetes:pod:{namespace}/{pod}"
    if namespace and deployment:
        return f"kubernetes:deployment:{namespace}/{deployment}"
    return event.subject_ref


# ---------------------------------------------------------------------------
# The handoff: candidates → detections → investigations
# ---------------------------------------------------------------------------

class InvestigationHandoff:
    """Implements ``backend.signal.worker.DetectionHandoff``. Decides nothing
    about causes; decides only whether a sustained condition has an
    investigation yet, and opens one if not."""

    def __init__(self, *, config: InvestigationRuntimeConfig, observations: Any, reasoning: Any,
                 service: Any, repository: Any, runner: "InvestigationRunner", tenant: Any,
                 metrics: Any = None, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> None:
        self._config = config
        self._observations = observations
        self._reasoning = reasoning
        self._service = service
        self._repository = repository
        self._runner = runner
        self._tenant = tenant
        self._metrics = metrics
        self._clock = clock
        self.detections: list = []
        self.opened: list = []
        self._recorded: set = set()

    def offer(self, candidates: tuple, *, tenant_id: str, now: datetime) -> None:
        if tenant_id != self._config.tenant_id or not candidates:
            return
        since = now - timedelta(seconds=self._config.lookback_seconds)
        try:
            history = self._observations.list_recent(tenant_id=tenant_id, since=since, limit=1000)
        except Exception as exc:  # noqa: BLE001 - the ledger being unreadable is not a detection
            log.warning("detection skipped: observation history unavailable: %s", exc)
            return
        events = detect(candidates=candidates, observations=history, tenant_id=tenant_id,
                        now=now, policy=self._config.detection_policy)
        for event in events:
            self._handle(event, now)

    def _handle(self, event: DetectionEvent, now: datetime) -> None:
        if event.detection_id not in self._recorded:
            newly = self._record_detection(event, now)
            self._recorded.add(event.detection_id)
            if newly:
                self.detections.append(event)
                self._count("detections", event.condition)
        incident_ref = incident_ref_for(event)
        if self._runner.knows(incident_ref) or self._active_investigation(incident_ref) is not None:
            return
        if self._recently_concluded(incident_ref, now):
            return
        try:
            from backend.contracts.intelligence import AutonomyLevel

            investigation = self._service.create(
                tenant=self._tenant, incident_ref=incident_ref, policy_ref=POLICY_REF,
                harness_version=HARNESS_VERSION_LABEL, now=now,
                autonomy_level=AutonomyLevel.A1_INVESTIGATE)
        except Exception as exc:  # noqa: BLE001
            log.exception("could not open an investigation for %s: %s", incident_ref, exc)
            return
        self.opened.append((investigation.investigation_ref, incident_ref))
        log.info("investigation %s opened for %s (%s)", investigation.investigation_ref,
                 incident_ref, event.condition)
        self._runner.submit(investigation.investigation_ref, incident_ref, event)

    def _record_detection(self, event: DetectionEvent, now: datetime) -> bool:
        if self._reasoning is None:
            return True
        from backend.platform.identity.generators import prefixed_id

        identity = compute_digest({"detection": event.detection_id, "tenant": event.tenant_id}).value
        try:
            return bool(self._reasoning.record(
                reasoning_id=prefixed_id("wreason"), identity_digest=identity,
                tenant_id=event.tenant_id, kind="detection", subject_ref=event.subject_ref,
                predicate="detection", record=event.to_dict(),
                refs={"observations": list(event.evidence), "candidate_id": event.candidate_id},
                recorded_at=now))
        except Exception as exc:  # noqa: BLE001 - recording failure must not stop detection
            log.warning("detection %s was not recorded durably: %s", event.detection_id, exc)
            return True

    def _recently_concluded(self, incident_ref: str, now: datetime) -> bool:
        """An incident that concluded inside the detection lookback is not
        reopened by the next detection of the same subject. A CrashLoop keeps
        being a CrashLoop until somebody changes something; every detection
        window it sustains is the same incident, and the conclusion already on
        the ledger (root cause, insufficient evidence, or blocked) is the answer
        until the lookback has passed. Read from the durable ledger, not
        remembered, so a restarted process applies the same rule."""
        try:
            for state in self._repository.list_terminal(tenant_id=self._config.tenant_id, limit=200):
                if not isinstance(state, dict) or state.get("incident_ref") != incident_ref:
                    continue
                when = _parse_when(state.get("updated_at") or state.get("created_at"))
                if when is not None and (now - when).total_seconds() < self._config.lookback_seconds:
                    return True
        except Exception as exc:  # noqa: BLE001 - an unreadable ledger does not stop detection
            log.warning("terminal investigations unreadable: %s", exc)
        return False

    def _active_investigation(self, incident_ref: str) -> Optional[str]:
        try:
            for state in self._repository.list_active(tenant_id=self._config.tenant_id, limit=200):
                if state.get("incident_ref") == incident_ref:
                    return state.get("investigation_ref")
        except Exception as exc:  # noqa: BLE001
            log.warning("active investigations unreadable: %s", exc)
        return None

    def _count(self, name: str, *labels: str) -> None:
        if self._metrics is None:
            return
        try:
            getattr(self._metrics, name).labels(*labels).inc()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

@dataclass
class InvestigationOutcome:
    investigation_ref: str
    incident_ref: str
    incident_class: str
    conclusion: Optional[str]
    outcome: Optional[str]
    confidence: Optional[str]
    steps: int
    reads: int
    model_calls: int
    model_failures: tuple
    tokens: int
    seconds: float
    provider: str
    assessment: Optional[Mapping[str, Any]] = None
    error: Optional[str] = None
    report: Optional[Mapping[str, Any]] = None
    step_outcomes: tuple = ()

    def to_dict(self) -> dict:
        return {k: (dict(v) if isinstance(v, Mapping) else (list(v) if isinstance(v, tuple) else v))
                for k, v in self.__dict__.items()}


class InvestigationRunner:
    """One supervised thread that runs investigations to a conclusion.

    Bounded: one investigation at a time, a bounded queue, and per-investigation
    budgets (steps, reads, seconds, tokens). On start it resumes the tenant's
    active investigations with this policy from the durable ledger, so a
    process restart neither loses nor duplicates work.
    """

    def __init__(self, *, config: InvestigationRuntimeConfig, composer: Callable[..., Any],
                 service: Any, repository: Any, tenant: Any, metrics: Any = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 on_outcome: Optional[Callable[[InvestigationOutcome], None]] = None) -> None:
        self._config = config
        self._composer = composer
        self._service = service
        self._repository = repository
        self._tenant = tenant
        self._metrics = metrics
        self._clock = clock
        self._on_outcome = on_outcome
        self._queue: "queue.Queue" = queue.Queue(maxsize=config.max_queue)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="cortexprime-investigator", daemon=True)
        self._known: set = set()
        self._lock = threading.Lock()
        self.outcomes: list = []
        self.current: Optional[str] = None

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> "InvestigationRunner":
        if self._config.resume_active:
            self._resume()
        self._thread.start()
        return self

    def stop(self, timeout: float = 30.0) -> None:
        self._stop.set()
        self._thread.join(timeout=timeout)

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def knows(self, incident_ref: str) -> bool:
        with self._lock:
            return incident_ref in self._known

    def submit(self, investigation_ref: str, incident_ref: str, event: Optional[DetectionEvent]) -> bool:
        with self._lock:
            if incident_ref in self._known:
                return False
            self._known.add(incident_ref)
        try:
            self._queue.put_nowait((investigation_ref, incident_ref, event))
            return True
        except queue.Full:
            with self._lock:
                self._known.discard(incident_ref)
            log.warning("investigation queue full; %s deferred", incident_ref)
            return False

    def _resume(self) -> None:
        try:
            states = self._repository.list_active(tenant_id=self._config.tenant_id, limit=200)
        except Exception as exc:  # noqa: BLE001
            log.warning("resume skipped: %s", exc)
            return
        for state in states:
            if state.get("policy_ref") != POLICY_REF:
                continue
            ref, incident = state.get("investigation_ref"), state.get("incident_ref")
            if ref and incident and self.submit(ref, incident, None):
                log.info("resuming investigation %s for %s", ref, incident)

    # -- the loop -----------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            investigation_ref, incident_ref, event = item
            self.current = investigation_ref
            self._gauge("investigations_active", 1.0)
            try:
                outcome = self.run_one(investigation_ref, incident_ref, event)
            except Exception as exc:  # noqa: BLE001 - never silent
                log.exception("investigation %s crashed", investigation_ref)
                self._fail_durably(investigation_ref, exc)
                outcome = InvestigationOutcome(
                    investigation_ref=investigation_ref, incident_ref=incident_ref,
                    incident_class="unknown", conclusion=None, outcome="BLOCKED", confidence="none",
                    steps=0, reads=0, model_calls=0, model_failures=(), tokens=0, seconds=0.0,
                    provider="n/a", error=f"{type(exc).__name__}: {exc}"[:300])
            finally:
                self.current = None
                self._gauge("investigations_active", 0.0)
                with self._lock:
                    self._known.discard(incident_ref)
            self.outcomes.append(outcome)
            if self._on_outcome is not None:
                try:
                    self._on_outcome(outcome)
                except Exception:  # noqa: BLE001
                    log.exception("outcome hook raised")

    def _fail_durably(self, investigation_ref: str, exc: BaseException) -> None:
        """Phase 11.3 (ADR-123 D-20): a crash is recorded in the ledger, not only
        in memory. Measured: a crashed investigation stayed ``investigating``
        forever, so the product reported it running and the handoff treated its
        incident as still under investigation. Best effort: if the state itself
        cannot be read or the transition is not legal, that is logged."""
        from backend.contracts.intelligence import InvestigationConclusion, InvestigationStatus
        from backend.contracts.intelligence.investigation import is_terminal_status

        cause = f"investigation crashed: {type(exc).__name__}: {exc}"[:300]
        try:
            investigation = self._service.reconstruct(tenant=self._tenant, investigation_ref=investigation_ref)
            if is_terminal_status(investigation.status):
                return
            if investigation.status is InvestigationStatus.CREATED:
                # Nothing was investigated; the contract allows only ABANDONED here.
                self._service.transition(investigation=investigation, to_status=InvestigationStatus.ABANDONED,
                                         cause=cause, now=self._clock())
            else:
                self._service.conclude(investigation=investigation, conclusion=InvestigationConclusion.FAILED,
                                       cause=cause, now=self._clock())
        except Exception:  # noqa: BLE001 - the crash is already logged; this must not raise
            log.exception("could not record the failure of investigation %s", investigation_ref)

    def run_one(self, investigation_ref: str, incident_ref: str,
                event: Optional[DetectionEvent]) -> InvestigationOutcome:
        """Run ONE investigation to a terminal conclusion within its budget."""
        from backend.api.investigation_catalog import (
            classify_incident, hypotheses_compatible, seed_hypotheses, window_for,
        )
        from backend.contracts.intelligence import InvestigationConclusion, InvestigationStatus
        from backend.contracts.intelligence.investigation import is_terminal_status
        from backend.intelligence.application.engine import (
            InvestigationBudget, InvestigationEngine, StepOutcome,
        )

        started = time.perf_counter()
        now = self._clock()
        investigation = self._service.reconstruct(tenant=self._tenant, investigation_ref=investigation_ref)
        detection_kind = event.condition if event is not None else "kubernetes.pod.crashloop"
        incident_class = classify_incident(detection_kind=detection_kind, subject_ref=incident_ref)
        first_seen = event.window_start if event is not None else investigation.created_at
        window = window_for(first_observed_at=first_seen, now=now)
        restart_count = 0
        if event is not None:
            rc = (event.correlation or {}).get("restartCount")
            restart_count = rc if isinstance(rc, int) else 0
        stack = self._composer(incident_class=incident_class, subject_ref=incident_ref,
                               window=window, restart_count=restart_count)
        self._count("investigations_opened", incident_class)

        if investigation.status is InvestigationStatus.CREATED:
            investigation = self._service.transition(
                investigation=investigation, to_status=InvestigationStatus.INVESTIGATING,
                cause=f"detection {detection_kind}: {event.reason if event else 'resumed'}", now=now)
        if not investigation.differential:
            for hypothesis in seed_hypotheses(incident_class=incident_class, subject_ref=incident_ref):
                investigation = self._service.upsert_hypothesis(
                    investigation=investigation, hypothesis=hypothesis, now=now)

        # Baseline evidence: what the platform reads about every incident before
        # a single hypothesis is tested. Linked, never interpreted here.
        investigation = self._collect_baseline(investigation, stack, now)

        engine = InvestigationEngine(
            service=self._service, assembler=stack["assembler"], model_port=stack["proposal_port"],
            evidence_port=stack["evidence_port"], world_read_port=stack["world_port"],
            policy=stack["policy"], harness_version=HARNESS_VERSION_LABEL,
            available_tools=stack["registry"].keys, compatible=hypotheses_compatible)
        from backend.intelligence.application.context import ContextBudget

        budget = InvestigationBudget(max_steps=self._config.max_steps, max_reads=self._config.max_reads,
                                     context=ContextBudget(max_context_tokens=self._config.context_tokens),
                                     max_seconds=self._config.max_seconds, max_tokens=self._config.max_tokens)
        step_outcomes = []
        while not is_terminal_status(investigation.status) and not self._stop.is_set():
            elapsed = time.perf_counter() - started
            if budget.max_seconds is not None and elapsed >= budget.max_seconds:
                from backend.intelligence.application.differential import settle

                summary = settle(investigation, compatible=hypotheses_compatible)
                investigation = self._service.conclude(
                    investigation=investigation, conclusion=InvestigationConclusion(summary.conclusion),
                    cause=f"time budget exhausted after {elapsed:.0f}s; {summary.residual_uncertainty}",
                    now=self._clock())
                break
            plan = stack.get("plan")
            if plan is not None and hasattr(plan, "note_prior_tests"):
                plan.note_prior_tests(investigation.test_refs)
            result = engine.step(investigation=investigation, budget=budget, now=self._clock())
            investigation = result.investigation
            step_outcomes.append(result.outcome.value)
            self._count("investigation_steps", result.outcome.value)
            log.info("investigation %s step %d: %s (%s)", investigation_ref, investigation.steps_taken,
                     result.outcome.value, (result.reason or "")[:120])
            if result.outcome is StepOutcome.TERMINATED:
                break
        if not is_terminal_status(investigation.status):
            investigation = self._service.conclude(
                investigation=investigation, conclusion=InvestigationConclusion.UNRESOLVED,
                cause="runner stopped before a conclusion", now=self._clock())

        seconds = time.perf_counter() - started
        assessment = self._assess(investigation, stack, window, seconds)
        provider = stack["provider_label"]
        proposal_port = stack.get("hybrid_port")
        model_calls = getattr(proposal_port, "model_calls", 0)
        model_failures = tuple(getattr(proposal_port, "model_failures", ()))
        tokens = getattr(proposal_port, "tokens_used", 0)
        outcome = InvestigationOutcome(
            investigation_ref=investigation_ref, incident_ref=incident_ref,
            incident_class=incident_class,
            conclusion=investigation.conclusion.value if investigation.conclusion else None,
            outcome=assessment.get("outcome") if assessment else None,
            confidence=assessment.get("confidence") if assessment else None,
            steps=investigation.steps_taken, reads=investigation.reads_taken,
            model_calls=model_calls, model_failures=model_failures, tokens=tokens,
            seconds=round(seconds, 2), provider=provider, assessment=assessment,
            report=self._report(investigation, stack), step_outcomes=tuple(step_outcomes))
        self._count("investigations_concluded", outcome.outcome or "none", outcome.confidence or "none")
        self._observe("investigation_seconds", seconds, outcome.outcome or "none")
        log.info("investigation %s concluded: %s / %s in %.1fs (%d steps, %d reads, %d model calls)",
                 investigation_ref, outcome.outcome, outcome.confidence, seconds, outcome.steps,
                 outcome.reads, model_calls)
        return outcome

    # -- pieces -------------------------------------------------------------

    def _collect_baseline(self, investigation: Any, stack: Mapping[str, Any], now: datetime) -> Any:
        from backend.intelligence.application.proposal import EvidenceRequest

        registry = stack["registry"]
        subject = investigation.incident_ref
        wanted = []
        if subject.startswith("kubernetes:pod:"):
            wanted = [("k8s.pod_state", "pod_state", subject), ("k8s.pod_events", "events", subject)]
        elif subject.startswith("kubernetes:deployment:"):
            wanted = [("k8s.deployment_state", "deployment_state", subject)]
        for tool, predicate, target in wanted:
            if registry.get(tool) is None:
                continue
            t0 = time.perf_counter()
            result = stack["evidence_port"].acquire(
                tenant=self._tenant, now=now,
                request=EvidenceRequest(tool=tool, subject_ref=target, predicate=predicate, read_only=True))
            self._observe("investigation_evidence_seconds", time.perf_counter() - t0, tool)
            self._count("investigation_reads", tool, "ok" if result.ok else "refused")
            if result.ok:
                refs = tuple(r for r in (result.observation_ref, result.fact_ref) if r)
                investigation = self._service.link_evidence(investigation=investigation,
                                                            evidence_refs=refs, now=now)
            else:
                log.info("baseline read %s refused: %s", tool, result.reason)
        return investigation

    def _evidence_view(self, investigation: Any, stack: Mapping[str, Any]) -> dict:
        observations = stack["observations"]
        query = stack["query"]
        view: dict = {}
        for ref in investigation.evidence_refs:
            if not ref.startswith("wobs"):
                continue
            try:
                observation = observations.get_observation(tenant_id=self._tenant.tenant_id,
                                                           observation_id=ref)
            except Exception:  # noqa: BLE001
                observation = None
            if observation is None:
                continue
            freshness = "unknown"
            try:
                answer = query.current(tenant=self._tenant, subject_ref=observation.subject_ref,
                                       predicate=observation.predicate, now=self._clock()).to_dict()
                freshness = answer.get("fresh", {}).get("state", "unknown")
            except Exception:  # noqa: BLE001
                pass
            view[ref] = {
                "source_kind": observation.source.kind.value, "source_ref": observation.source.source_ref,
                "subject_ref": observation.subject_ref, "predicate": observation.predicate,
                "value": observation.value, "freshness": freshness,
                "observed_at": observation.instant.observed_at.isoformat(),
            }
        return view

    def _assess(self, investigation: Any, stack: Mapping[str, Any], window: Any, seconds: float) -> Optional[dict]:
        from backend.intelligence.application.confidence import assess

        try:
            view = self._evidence_view(investigation, stack)
            timeline = self._timeline(investigation, view, window)
            assessment = assess(investigation=investigation, evidence_view=view,
                                lineage_of=stack["lineage"].lineage_of, window=window.to_dict(),
                                timeline=timeline, now=self._clock())
            document = assessment.to_dict()
            document["cost"] = self._cost(investigation, stack, seconds)
            self._record_assessment(investigation, document)
            return document
        except Exception as exc:  # noqa: BLE001 - an assessment failure is reported, never hidden
            log.exception("assessment of %s failed", investigation.investigation_ref)
            return {"outcome": "BLOCKED", "confidence": "none",
                    "error": f"assessment failed: {type(exc).__name__}"}

    def _timeline(self, investigation: Any, view: Mapping[str, Mapping[str, Any]], window: Any) -> tuple:
        entries = [{"at": window.incident_start.isoformat(), "event": "incident start",
                    "source": "signal fabric"}]
        for ref, item in view.items():
            value = item.get("value") if isinstance(item.get("value"), Mapping) else {}
            if item.get("predicate") == "rollout_history" and value.get("latestRolloutAt"):
                entries.append({"at": value["latestRolloutAt"], "event": f"rollout to revision "
                                f"{value.get('currentRevision')} ({value.get('currentImage')})",
                                "source": item.get("source_ref"), "observation": ref})
            if item.get("predicate") == "events":
                if value.get("firstWarningAt"):
                    entries.append({"at": value["firstWarningAt"], "event": "first Warning event",
                                    "source": item.get("source_ref"), "observation": ref})
            entries.append({"at": item.get("observed_at"), "event": f"observed {item.get('predicate')}",
                            "source": item.get("source_ref"), "observation": ref})
        try:
            events = self._repository.list_events(tenant_id=self._tenant.tenant_id,
                                                  investigation_id=investigation.investigation_ref, limit=200)
        except Exception:  # noqa: BLE001
            events = ()
        for ev in events:
            kind = ev.get("event_kind") if isinstance(ev, Mapping) else getattr(ev, "event_kind", None)
            at = ev.get("recorded_at") if isinstance(ev, Mapping) else getattr(ev, "recorded_at", None)
            if kind in ("created", "status_changed", "concluded", "transitioned"):
                entries.append({"at": str(at), "event": f"investigation {kind}", "source": "ledger"})
        entries.sort(key=lambda e: str(e.get("at") or ""))
        return tuple(entries)

    def _cost(self, investigation: Any, stack: Mapping[str, Any], seconds: float) -> dict:
        traces = stack.get("traces")
        spans = ()
        if traces is not None:
            try:
                spans = traces.spans_for_mission(investigation.investigation_ref)
            except Exception:  # noqa: BLE001
                spans = ()
        prompt_tokens = completion_tokens = 0
        model_calls = 0
        providers: dict = {}
        latency = 0.0
        for raw in spans:
            span = raw if isinstance(raw, Mapping) else (raw.to_dict() if hasattr(raw, "to_dict") else {})
            usage = span.get("token_usage")
            provider = span.get("model_provider")
            if provider:
                providers[provider] = providers.get(provider, 0) + 1
            model_calls += 1
            if isinstance(usage, Mapping):
                prompt_tokens += int(usage.get("prompt_tokens") or 0)
                completion_tokens += int(usage.get("completion_tokens") or 0)
            if isinstance(span.get("latency_ms"), (int, float)):
                latency += float(span["latency_ms"])
        # Phase 11.4 (ADR-124, mandate §59): no provider price is configured in
        # this platform, and the old estimate returned 0.0 for every provider --
        # a fabricated price of zero. Tokens are measured; money is not, and says
        # so. A pass that spent no tokens honestly costs nothing.
        total_tokens = prompt_tokens + completion_tokens
        usd: Optional[float] = 0.0 if total_tokens == 0 else None
        if usd is None:
            estimate = 0.0
            for provider, calls in providers.items():
                estimate += _estimate_usd(provider, stack.get("model_name") or "", prompt_tokens, completion_tokens)
            usd = round(estimate, 6) if estimate else None
        if usd:
            self._count_value("investigation_cost_usd", usd, stack["provider_label"])
        return {
            "model_calls": model_calls, "providers": providers,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model_latency_ms": round(latency, 1), "estimated_usd": usd,
            "monetary_cost": ("none (no tokens spent)" if total_tokens == 0 else
                              "unknown: no provider pricing is configured" if usd is None else "estimated"),
            "governed_reads": investigation.reads_taken, "steps": investigation.steps_taken,
            "wall_seconds": round(seconds, 2),
        }

    def _record_assessment(self, investigation: Any, document: Mapping[str, Any]) -> None:
        reasoning = getattr(self, "reasoning", None)
        if reasoning is None:
            return
        from backend.platform.identity.generators import prefixed_id

        identity = compute_digest({"assessment": investigation.investigation_ref,
                                   "seq": investigation.seq}).value
        try:
            reasoning.record(
                reasoning_id=prefixed_id("wreason"), identity_digest=identity,
                tenant_id=self._tenant.tenant_id, kind="assessment",
                subject_ref=investigation.investigation_ref, predicate="assessment",
                record=dict(document),
                refs={"incident_ref": investigation.incident_ref,
                      "evidence": list(investigation.evidence_refs)},
                recorded_at=self._clock())
        except Exception as exc:  # noqa: BLE001
            log.warning("assessment of %s not recorded durably: %s", investigation.investigation_ref, exc)

    def _report(self, investigation: Any, stack: Mapping[str, Any]) -> Optional[dict]:
        try:
            from backend.api.incident_investigation import assemble_report

            return assemble_report(investigation=investigation).to_dict()
        except Exception:  # noqa: BLE001
            return None

    # -- metrics ------------------------------------------------------------

    def _count(self, name: str, *labels: str) -> None:
        if self._metrics is None:
            return
        try:
            getattr(self._metrics, name).labels(*labels).inc()
        except Exception:  # noqa: BLE001
            pass

    def _count_value(self, name: str, value: float, *labels: str) -> None:
        if self._metrics is None:
            return
        try:
            getattr(self._metrics, name).labels(*labels).inc(value)
        except Exception:  # noqa: BLE001
            pass

    def _observe(self, name: str, value: float, *labels: str) -> None:
        if self._metrics is None:
            return
        try:
            getattr(self._metrics, name).labels(*labels).observe(value)
        except Exception:  # noqa: BLE001
            pass

    def _gauge(self, name: str, value: float) -> None:
        if self._metrics is None:
            return
        try:
            getattr(self._metrics, name).set(value)
        except Exception:  # noqa: BLE001
            pass


def _estimate_usd(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """The existing static cost table (backend/analytics/cost_engine.py). A
    local provider prices at zero; an unknown one estimates zero and says so
    through ``providers`` in the cost document rather than inventing a price."""
    try:
        from backend.analytics.cost_engine import CostEngine

        estimate = getattr(CostEngine, "estimate_cost", None)
        if estimate is None:
            return 0.0
        engine = CostEngine()
        return float(engine.estimate_cost(provider=provider, model=model,
                                          prompt_tokens=prompt_tokens, completion_tokens=completion_tokens))
    except Exception:  # noqa: BLE001
        return 0.0


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

def model_port_from_config(config: InvestigationRuntimeConfig) -> Optional[Any]:
    """The REAL model port, or None. Only the existing ``LLMService`` stack is
    used (``LLMServiceModelPort``); no SDK is added and no key is read here."""
    if not config.model_provider:
        return None
    from backend.harness.llm_boundary import LLMServiceModelPort

    return LLMServiceModelPort(config.model_name or None, provider=config.model_provider,
                               timeout_seconds=config.model_timeout_seconds,
                               max_tokens=config.model_max_output_tokens)


def build_investigation_runtime(runtime: Any, *, config: InvestigationRuntimeConfig,
                                metrics: Any = None, on_outcome: Optional[Callable[..., None]] = None
                                ) -> tuple:
    """Compose (handoff, runner) over the running governed runtime.

    Refuses when the read capabilities an investigation needs are not
    commissioned: an investigator that cannot read observes nothing, and saying
    so at start is better than concluding BLOCKED on every incident.
    """
    from backend.api.capability_execution_composition import GovernedCapabilityReader
    from backend.api.governed_evidence_acquisition import GovernedEvidenceAcquisition, ToolRegistry
    from backend.api.investigation_catalog import (
        PlanAugmentedModelPort, PlanModelPort, ToolComposition, investigation_tools,
    )
    from backend.api.observability_evidence import (
        WorldQueryEvidencePort, observability_authority_policy, observability_freshness_policy,
        observability_lineage_policy,
    )
    from backend.contexts.connectivity.application.commands import GetCapability
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.contracts.tenant import TenantRef
    from backend.harness.llm_boundary import GovernedModelBoundary
    from backend.harness.trace_sql import SqlTraceRecorder
    from backend.harness.version import CURRENT_HARNESS_VERSION
    from backend.intelligence.application.context import ContextAssembler
    from backend.intelligence.application.investigation_service import InvestigationService
    from backend.intelligence.application.model_boundary import GovernedModelProposalPort
    from backend.intelligence.application.proposal import EvidenceSelectionPolicy
    from backend.intelligence.infrastructure import SqlInvestigationRepository
    from backend.platform.context import ExecutionContext
    from backend.platform.context.identity import IdentityContext
    from backend.world.application import BeliefFormation, FactDerivation, ObservationIngestion, WorldQuery
    from backend.world.infrastructure import SqlFactRepository, SqlObservationRepository
    from backend.world.infrastructure.sql_reasoning import SqlReasoningRepository

    store = runtime.persistence.store
    tenant = TenantRef(tenant_id=config.tenant_id)
    observations = SqlObservationRepository(store)
    facts = SqlFactRepository(store)
    reasoning = SqlReasoningRepository(store)
    repository = SqlInvestigationRepository(store)
    service = InvestigationService(repository=repository)
    ingestion = ObservationIngestion(repository=observations)
    derivation = FactDerivation(repository=facts)
    lineage = observability_lineage_policy()
    authority = observability_authority_policy()
    freshness = observability_freshness_policy()
    query = WorldQuery(facts=facts, observations=observations, authority_policy=authority,
                       freshness_policy=freshness)
    beliefs = BeliefFormation(query=query, observations=observations, authority_policy=authority,
                              lineage_policy=lineage)
    traces = SqlTraceRecorder(store)

    platform_ctx = ExecutionContext.platform_internal(
        reason="investigation runtime: governed read capability lookup",
        component="cortexprime.investigator", source="lifecycle")
    tenant_ctx = ExecutionContext.for_tenant(
        tenant_id=config.tenant_id,
        identity=IdentityContext(principal=PrincipalRef(principal_id="investigator", kind=PrincipalKind.PLATFORM),
                                 capabilities=("capability:invoke",)),
        source="investigator")

    # The read capabilities an investigation may use, as commissioned. Missing
    # ones are simply not exposed as tools (the registry refuses unknown ops).
    wanted = ("kubernetes.pod.get", "kubernetes.pod.logs", "kubernetes.events.list",
              "kubernetes.deployment.get", "kubernetes.replicasets.list", "kubernetes.pods.list",
              "prometheus.pod_memory_ratio", "prometheus.pod_restarts", "prometheus.pod_restarts_range",
              "prometheus.deployment_unavailable")
    definitions: dict = {}
    for operation in wanted:
        try:
            definitions[operation] = runtime.capabilities.get(
                platform_ctx, GetCapability(capability_id=f"platform.{operation}", version=1))
        except Exception:  # noqa: BLE001 - not commissioned → not a tool
            continue
    if not any(op.startswith("kubernetes.") for op in definitions):
        raise RuntimeError("the investigation runtime refuses to start: no Kubernetes read "
                           "capability is commissioned (platform.kubernetes.pod.get and friends)")
    # The worker directory is process-local (ADR-122 F-1): every connector this
    # process will dispatch to must be admitted HERE. The signal worker admits
    # the Kubernetes connector for itself; the investigator also reads through
    # Prometheus when it is composed, so it admits that connector too. Without
    # this the memory read stays leased and the investigation concludes
    # BLOCKED -- which is how it was found.
    from backend.signal.worker import _commission_connector_worker

    for provider_id in sorted(getattr(runtime.connectivity, "catalogs", {})):
        try:
            _commission_connector_worker(runtime, platform_ctx, worker_id=f"{provider_id}-connector")
        except Exception as exc:  # noqa: BLE001 - an unknown worker id is not fatal; its reads will refuse
            log.info("connector worker %s-connector not admitted: %s", provider_id, exc)
    reader = GovernedCapabilityReader(runtime=runtime, capability_definitions=definitions,
                                      principal=PrincipalRef(principal_id="investigator",
                                                             kind=PrincipalKind.PLATFORM))
    prometheus = "prometheus" in getattr(runtime.connectivity, "catalogs", {}) and any(
        op.startswith("prometheus.") for op in definitions)
    catalogs = runtime.connectivity.catalogs
    model_port = model_port_from_config(config)
    provider_label = f"{config.model_provider}:{config.model_name}" if model_port else "deterministic"

    def compose(*, incident_class: str, subject_ref: str, window: Any, restart_count: int) -> dict:
        tools = tuple(t for t in investigation_tools(ToolComposition(
            subject_ref=subject_ref, window=window, restart_count=restart_count, prometheus=prometheus))
            if t.operation in definitions)
        registry = ToolRegistry(tools=tools, catalogs=catalogs)
        # The INGESTION is handed over, not a fixed observer: the acquisition
        # port builds one observer per tool so each observation carries the
        # tool's own source_ref (kubelet logs, cAdvisor, kube-state-metrics,
        # the API server) -- which is what lets lineage tell them apart.
        evidence_port = GovernedEvidenceAcquisition(
            reader=reader, observer=ingestion, derivation=derivation, registry=registry,
            context=tenant_ctx)
        plan = PlanModelPort(incident_class=incident_class, subject_ref=subject_ref,
                             available_tools=registry.keys)
        hybrid = None
        if model_port is not None:
            hybrid = PlanAugmentedModelPort(model_port=model_port, plan=plan,
                                            timeout_seconds=config.model_timeout_seconds,
                                            max_tokens=config.max_tokens)
        boundary = GovernedModelBoundary(model_port=hybrid or plan, recorder=traces,
                                         harness_version=CURRENT_HARNESS_VERSION)
        return {
            "registry": registry, "evidence_port": evidence_port, "observations": observations,
            "query": query, "beliefs": beliefs, "lineage": lineage, "assembler": ContextAssembler(),
            "policy": EvidenceSelectionPolicy(), "world_port": WorldQueryEvidencePort(query=query),
            "proposal_port": GovernedModelProposalPort(boundary=boundary, provider_label=provider_label),
            "plan": plan,
            "hybrid_port": hybrid, "provider_label": provider_label, "model_name": config.model_name,
            "traces": traces, "reasoning": reasoning,
        }

    runner = InvestigationRunner(config=config, composer=compose, service=service, repository=repository,
                                 tenant=tenant, metrics=metrics, on_outcome=on_outcome)
    runner.reasoning = reasoning
    handoff = InvestigationHandoff(config=config, observations=observations, reasoning=reasoning,
                                   service=service, repository=repository, runner=runner, tenant=tenant,
                                   metrics=metrics)
    return handoff, runner


class EmbeddedInvestigator:
    def __init__(self, handoff: InvestigationHandoff, runner: InvestigationRunner) -> None:
        self.handoff = handoff
        self.runner = runner

    def stop(self, timeout: float = 30.0) -> None:
        self.runner.stop(timeout=timeout)


def start_embedded_investigator(runtime: Any, *, metrics: Any = None,
                                on_outcome: Optional[Callable[..., Any]] = None) -> Optional[EmbeddedInvestigator]:
    """Compose and start the investigator beside the signal worker when the
    signal loop is configured. Unconfigured: nothing happens (pre-11.3).

    ``on_outcome`` (Phase 11.4) receives each concluded investigation -- the
    remediation runtime's hook. The investigator still composes no write."""
    tenant_id = (os.getenv("CORTEX_SIGNAL_TENANT_ID") or "").strip()
    namespace = (os.getenv("CORTEX_SIGNAL_NAMESPACE") or "").strip()
    if not (tenant_id and namespace):
        return None
    if (os.getenv("CORTEX_INVESTIGATION_ENABLED") or "1").strip() == "0":
        return None
    try:
        config = InvestigationRuntimeConfig.from_env(tenant_id=tenant_id, namespace=namespace)
        if metrics is None:
            try:
                from backend.observability.prometheus_metrics import metrics as _metrics
                metrics = _metrics
            except Exception:  # noqa: BLE001
                metrics = None
        handoff, runner = build_investigation_runtime(runtime, config=config, metrics=metrics,
                                                      on_outcome=on_outcome)
    except Exception as exc:  # noqa: BLE001 - the API keeps booting; investigation does not run half-composed
        log.error("embedded investigator refused to start: %s", exc)
        return None
    runner.start()
    log.info("embedded investigator started: tenant=%s namespace=%s model=%s",
             tenant_id, namespace, config.model_provider or "deterministic")
    return EmbeddedInvestigator(handoff, runner)
