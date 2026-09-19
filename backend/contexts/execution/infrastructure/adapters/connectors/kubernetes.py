"""The governed Kubernetes READ capability — Phase 9.1/9.2/9.3 (ADR-081/082/083).

Kubernetes becomes a *governed capability of CortexPrime*, not a connector: a
declared, read-only ``OperationCatalog`` of `ProviderOperationSpec`s modelling the
Kubernetes HTTP API (the API server is plain HTTPS), so a Kubernetes read runs
through the ONE governed execution path — capability → authorization → lease →
gateway → transport → provider — exactly like GitHub/Grafana. There is NO second
gateway, executor, scheduler, credential system, or HTTP client here: this module
declares the *contract* only; provider I/O happens solely when the governed
execution transport invokes the composed adapter.

This module imports no `kubernetes` SDK, no `httpx`, no `backend.connectors`, no
credential carrier (structurally fenced by BND-PROVIDER-SDK / BND-DIRECT-HTTP), and
declares only READ operations (Part D) — a write would require a new, explicit
capability declaration with a `RiskClassification` + verification requirement.

resourceVersion (Part F): the governed ``evidence()`` extraction is deliberately
bounded to top-level scalars (ADR-042: raw payloads belong in an evidence store,
not the execution event). So the provider adapter NORMALIZES a Kubernetes response
— lifting ``metadata.resourceVersion`` to a top-level ``resourceVersion`` evidence
field — and every LIST/GET spec keeps ``resourceVersion`` in its
``response_evidence_fields``. A governed read's resourceVersion therefore survives
into the Observation, establishing the data contract LIST→WATCH continuity needs.
resourceVersion is never fabricated: if the provider omits it, it is simply absent
(Part F).

WATCH (Phase 9.3, ADR-083)
----------------------------
``kubernetes.pods.watch`` is declared here as another READ, and it reaches the API
server through the same one governed path — the same adapter, channel, broker and
transport. Three things make that possible without a second transport:

* **The window is bounded.** ``timeoutSeconds`` makes each watch an ordinary
  one-shot request whose body is that window's events. The governed transport
  refuses server-sent events by design, and this is the shape that does not need
  them. Continuity across windows is exact: the next window starts from the
  resourceVersion the last event carried, copied verbatim.
* **``watch=true`` is declared, not passed.** It lives in ``static_query``, so a
  watch is a *different operation* from a list rather than a list a caller asked
  to keep open, and the difference is in the operation's digest.
* **The answer is NDJSON**, decoded by ``KubernetesWatchDecoder`` and normalized
  into declared, bounded per-event records (``RecordEvidenceSpec``) — the same
  scalars-only, declared-in-advance discipline as flat evidence, one level down.

Fail-closed throughout: an unknown event type, an event with no resourceVersion,
a mutation identifying no resource, an unparseable line, a truncated window and a
window over the declared event cap are each a refusal. A refused window leaves the
stream position untouched and Kubernetes re-delivers — at-least-once, never a
silently accepted gap. A 410 (as an HTTP status or as an in-stream ``Status``) is
surfaced, never converted into success.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Optional, Tuple

from backend.contracts.execution import (
    EffectSemantics, ExecutionEnvironment, SideEffectClass,
)
from backend.contracts.policy import RiskClassification, RiskFactors, RiskLevel
from backend.contracts.provider import ProviderRef
from backend.contracts.transport import TransportKind
from backend.contracts.intelligence.investigation import AutonomyLevel
from backend.contracts.intelligence.capability_profile import (
    CapabilityProfile, VerificationRequirement,
)
from backend.contexts.execution.domain.provider_operation import (
    OperationCatalog, ParameterKind, ParameterLocation, ParameterSpec, ProviderOperationSpec,
    RecordEvidenceSpec,
)
from backend.contexts.execution.infrastructure.adapters.channel import ProviderChannel
from backend.contexts.execution.infrastructure.adapters.connector import (
    HttpStatusTranslator,
)
from backend.platform.transport import ConnectionPolicy, TransportBroker, TransportEndpoint

__all__ = [
    "KUBERNETES_PROVIDER_ID",
    "KUBERNETES_PROVIDER",
    "KUBERNETES_READ_OPERATIONS",
    "KUBERNETES_REAL_READ_OPERATIONS",
    "KubernetesReadNormalizer",
    "KubernetesResponseTranslator",
    "KubernetesWatchDecoder",
    "KubernetesRestartBodyBuilder",
    "ROLLOUT_RESTART_OPERATION",
    "RESTART_ANNOTATION",
    "DEPLOYMENT_ROLLBACK_OPERATION",
    "ROLLBACK_ANNOTATION",
    "pod_template_digest",
    "kubernetes_write_profiles",
    "KUBERNETES_WATCH_OPERATION",
    "KUBERNETES_WATCH_EVENT_TYPES",
    "KUBERNETES_WATCH_MUTATION_TYPES",
    "WATCH_WINDOW_SECONDS",
    "WATCH_MAX_EVENTS",
    "kubernetes_read_catalog",
    "kubernetes_real_read_catalog",
    "kubernetes_read_profiles",
    "build_kubernetes_channel",
]

KUBERNETES_PROVIDER_ID = "kubernetes"
KUBERNETES_PROVIDER = ProviderRef(provider_id=KUBERNETES_PROVIDER_ID)
_POLICY_VERSION = "k8s-read-policy/1"

#: The smallest read-only set for the first incident-investigation vertical
#: (Phase 9.0 §8: CrashLoopBackOff / deployment-failure). Deriving cause from pods,
#: their events, their logs, and the owning deployment.
KUBERNETES_REPLICASETS_OPERATION = "kubernetes.replicasets.list"

KUBERNETES_READ_OPERATIONS = (
    "kubernetes.pods.list",
    "kubernetes.pod.get",
    "kubernetes.pod.logs",
    "kubernetes.deployments.list",
    "kubernetes.deployment.get",
    "kubernetes.events.list",
    "kubernetes.pods.watch",
    # Phase 11.3: the ReplicaSet lineage of a namespace -- every revision a
    # Deployment ever rolled, each with its own image and creation time. This
    # is the observable a "what changed, and when" question is answered from.
    KUBERNETES_REPLICASETS_OPERATION,
)

#: The Phase 9.3 WATCH operation (ADR-083). A READ: it observes and cannot act.
KUBERNETES_WATCH_OPERATION = "kubernetes.pods.watch"

#: The Phase 9.6 WRITE (ADR-086). The FIRST and ONLY Kubernetes mutation this
#: platform can perform, and it is deliberately the smallest useful one.
ROLLOUT_RESTART_OPERATION = "kubernetes.workload.rollout_restart"

#: The annotation a restart stamps on the pod template.
#:
#: A CortexPrime-owned key, not ``kubectl.kubernetes.io/restartedAt``. Writing
#: kubectl's annotation would make a platform action indistinguishable from a
#: human running kubectl, and "who restarted this workload, and why" is the first
#: question asked afterwards. The value is the platform's own action identity, so
#: the annotation answers it.
RESTART_ANNOTATION = "cortexprime.io/restarted-by-action"

#: Phase 11.4 (ADR-124): the second governed Kubernetes write -- roll ONE
#: Deployment back to ONE known revision. Performed only by the CONTAINED
#: rollback worker (its own provider id, its own ServiceAccount); it is not in
#: this in-process connector's catalog and never will be.
DEPLOYMENT_ROLLBACK_OPERATION = "kubernetes.deployment.rollback"

#: The annotation the rollback worker writes on the Deployment's OWN metadata
#: (never the pod template, which would create a revision nobody approved).
ROLLBACK_ANNOTATION = "cortexprime.io/rolled-back-by-action"

#: The label the Deployment controller adds to a ReplicaSet's template; the only
#: label by which a ReplicaSet's template differs from the Deployment's.
POD_TEMPLATE_HASH_LABEL = "pod-template-hash"


def pod_template_digest(template: Any) -> str:
    """The digest of a full pod template, identical to the rollback worker's.

    ``sha256`` over canonical JSON (sorted keys, no whitespace) of the template
    minus the controller's ``pod-template-hash`` label and the serializer's
    ``metadata.creationTimestamp``. The same declared template therefore has the
    same digest on a Deployment and on the ReplicaSet created from it. The copy
    in ``workers/contained_k8s_rollback/worker.py`` must answer identically; a
    unit test holds them to it. Unlike ``_template_digest`` (what the containers
    RUN, for the regression hypothesis), this covers the whole template, because
    a rollback writes the whole template.
    """
    import copy
    import hashlib
    import json

    if not isinstance(template, Mapping):
        raise ValueError("a pod template must be an object")
    body = copy.deepcopy(dict(template))
    meta = body.get("metadata")
    if isinstance(meta, Mapping):
        meta = dict(meta)
        labels = meta.get("labels")
        if isinstance(labels, Mapping):
            meta["labels"] = {k: v for k, v in labels.items() if k != POD_TEMPLATE_HASH_LABEL}
        meta.pop("creationTimestamp", None)
        body["metadata"] = meta
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


#: Phase 9.2 exposed exactly ONE real operation (Part E): the smallest read that
#: proves the whole governed chain against a live API server. Phase 9.3 adds
#: exactly one more (ADR-083) — the WATCH that continues that LIST. The pair is
#: deliberate and minimal: a watch is only meaningful from a resourceVersion a
#: governed list produced, so exposing one without the other would expose a
#: stream with no honest way to start it. The remaining four stay declared
#: contract, real-exposed only when a later phase decides to.
KUBERNETES_REAL_READ_OPERATIONS = (
    "kubernetes.pods.list", KUBERNETES_WATCH_OPERATION,
    # Phase 9.5 (ADR-085): the two reads a CrashLoopBackOff differential actually
    # discriminates on. A pod's last termination (exit code + reason) separates an
    # OOM kill from an application failure; a deployment's revision and image
    # separate a regression from a long-standing fault. Both were declared in 9.1
    # and are only now exposed, which is the point of declaring a contract ahead
    # of exposing it.
    "kubernetes.pod.get", "kubernetes.deployment.get",
    # Phase 11.3 (ADR-123): the three reads an evidence-first investigation
    # needs beyond pod and deployment state -- what the container SAID before
    # it died (its logs, from the kubelet), what the CONTROL PLANE recorded
    # about the object (its events), and what CHANGED (the ReplicaSet lineage
    # that carries every revision's image). All three are READ and were
    # declared in 9.1/11.3; none carries a write field.
    "kubernetes.pod.logs", "kubernetes.events.list", KUBERNETES_REPLICASETS_OPERATION,
    # Phase 9.6's write is deliberately ABSENT. It is declared (see
    # ``kubernetes_write_catalog``) but not exposed: an IRREVERSIBLE_WRITE may
    # not be performed by a CONTAINED in-process worker, so putting it in the
    # real read exposure would offer an operation this worker must refuse
    # (ADR-086). It joins a real exposure when a SEALED tier exists.
)

#: The event types Kubernetes sends on a watch stream. A closed set on purpose —
#: an event type outside it is a protocol this normalizer does not understand, and
#: an event nobody understands must not become world state (fail closed).
KUBERNETES_WATCH_EVENT_TYPES = ("ADDED", "MODIFIED", "DELETED", "BOOKMARK", "ERROR")

#: The mutation types. ``BOOKMARK`` is deliberately absent: it advances the stream
#: position and asserts nothing about a resource. ``ERROR`` is absent because it is
#: the stream failing, not a resource changing.
KUBERNETES_WATCH_MUTATION_TYPES = ("ADDED", "MODIFIED", "DELETED")

#: How long one governed watch window stays open, in seconds.
#:
#: Bounded, and bounded *below the transport's read timeout* (``TimeoutPolicy.
#: read_seconds`` = 30.0). A quiet cluster sends no bytes at all, so a window
#: longer than that read timeout would be killed by httpx as a ReadTimeout — an
#: ambiguous outcome — every time nothing happened, which is most of the time.
#: At 20 seconds the API server closes the window first and a quiet window is an
#: ordinary, successful, empty answer.
WATCH_WINDOW_SECONDS = 20

#: The most events one window may carry. A window with more is REFUSED, not
#: trimmed: the driver then re-watches from the same position and Kubernetes
#: redelivers, whereas a trimmed window would advance the stream position past
#: events nobody recorded — a hole in world state that looks like continuity.
WATCH_MAX_EVENTS = 64

# Shared parameter shapes — all references, never a URL or shell fragment.
_NS = ParameterSpec(name="namespace", kind=ParameterKind.RESOURCE_SEGMENT,
                    location=ParameterLocation.PATH, max_length=253)
_NAME = ParameterSpec(name="name", kind=ParameterKind.RESOURCE_SEGMENT,
                      location=ParameterLocation.PATH, max_length=253)
_LABEL = ParameterSpec(name="labelSelector", kind=ParameterKind.STRING,
                       location=ParameterLocation.QUERY, max_length=512, required=False)
_LIMIT = ParameterSpec(name="limit", kind=ParameterKind.INTEGER,
                       location=ParameterLocation.QUERY, required=False)
# Phase 11.3 -- log and event reads are BOUNDED by declaration. A log read
# without a tail bound is an unbounded allocation in every parser between the
# kubelet and the World Plane; the caps below are the most any caller can ask.
_TAIL = ParameterSpec(name="tailLines", kind=ParameterKind.INTEGER,
                      location=ParameterLocation.QUERY, required=False,
                      min_value=1, max_value=500)
_SINCE = ParameterSpec(name="sinceSeconds", kind=ParameterKind.INTEGER,
                       location=ParameterLocation.QUERY, required=False,
                       min_value=1, max_value=86400)
#: ``previous=true`` asks the kubelet for the PREVIOUS container instance's log
#: -- for a crash-looping container that is the log of the run that died,
#: which is the one an investigation wants.
_PREVIOUS = ParameterSpec(name="previous", kind=ParameterKind.BOOLEAN,
                          location=ParameterLocation.QUERY, required=False)
_FIELD = ParameterSpec(name="fieldSelector", kind=ParameterKind.STRING,
                       location=ParameterLocation.QUERY, max_length=512, required=False)

#: Log evidence is never the log. It is the bounded, declared, scrubbed SHAPE
#: of the log: each distinct message pattern once, with how often it recurred
#: and at what level. The raw text stays on the kubelet.
LOG_MAX_PATTERNS = 32
_LOG_PATTERN_RECORDS = RecordEvidenceSpec(
    field_name="patterns",
    fields=("pattern", "count", "level", "firstLine"),
    max_records=LOG_MAX_PATTERNS,
    max_string_length=200,
)
EVENTS_MAX_RECORDS = 64
_EVENT_RECORDS = RecordEvidenceSpec(
    field_name="events",
    fields=("reason", "type", "message", "count", "firstTimestamp", "lastTimestamp",
            "involvedKind", "involvedName"),
    max_records=EVENTS_MAX_RECORDS,
    max_string_length=240,
)
REPLICASETS_MAX_RECORDS = 64
_REPLICASET_RECORDS = RecordEvidenceSpec(
    field_name="replicaSets",
    fields=("name", "revision", "image", "replicas", "readyReplicas",
            "creationTimestamp", "ownerName", "templateDigest",
            # Phase 11.4 (ADR-124): which Deployment OBJECT owns it (a name can
            # be reused by a recreated Deployment; a UID cannot) and the digest
            # of its full template, which is what a rollback would write.
            "ownerUid", "podTemplateDigest"),
    max_records=REPLICASETS_MAX_RECORDS,
)

#: The watch continuation point. REQUIRED, and required for a reason: a watch
#: without a resourceVersion means "start from now, and also send me the current
#: state of everything", which is a different operation with a different cost and
#: no continuity with what was already observed. The value is opaque text the
#: driver read from a durable Observation — never minted, never incremented,
#: never interpreted as a number here or anywhere.
_WATCH_RV = ParameterSpec(name="resourceVersion", kind=ParameterKind.STRING,
                          location=ParameterLocation.QUERY, max_length=128)
#: The window length. Bounded by declaration so no caller can ask for a window
#: that outlives the transport's read timeout (see ``WATCH_WINDOW_SECONDS``).
_WATCH_TIMEOUT = ParameterSpec(name="timeoutSeconds", kind=ParameterKind.INTEGER,
                               location=ParameterLocation.QUERY,
                               min_value=1, max_value=WATCH_WINDOW_SECONDS)

# resourceVersion (lifted to top-level by the adapter) is kept in the bounded
# scalar evidence of every read (Part F). Evidence fields are top-level scalars —
# the governed evidence extractor keeps only int/float/bool/str, by design.
_RV = "resourceVersion"
_TIMEOUT = 20.0

_K8S_HEADERS = {
    "accept": "application/json",
    "user-agent": "CortexPrime-ConnectorAdapter/1.0",
}


def _read(operation: str, path_template: str, *, parameters, evidence,
          required=(_RV,), records=None) -> ProviderOperationSpec:
    return ProviderOperationSpec(
        operation=operation, method="GET", path_template=path_template,
        side_effect_class=SideEffectClass.READ, effect_semantics=EffectSemantics.READ_ONLY,
        parameters=parameters, success_statuses=(200,),
        response_required_fields=required, response_evidence_fields=evidence,
        response_evidence_records=records,
        static_headers=_K8S_HEADERS,
        provider_timeout_seconds=_TIMEOUT, max_response_bytes=4 * 1024 * 1024)


#: Per-pod evidence on a list (Phase 9.4, ADR-084). Until now a pods.list kept
#: only counts, which is enough to notice something is wrong and not enough to
#: say anything about a *particular* pod — so it could not corroborate a metric
#: that names one. Declared, bounded and scalars-only, exactly like every other
#: record evidence; the cap is the same one the watch window uses.
_POD_RECORDS = RecordEvidenceSpec(
    field_name="pods",
    fields=("name", "namespace", "uid", "phase", "restartCount", "waitingReason",
            # Phase 11.4 (ADR-124): readiness and the owning ReplicaSet, so an
            # independent verifier can say which revision's pods are ready.
            "ready", "ownerName"),
    max_records=WATCH_MAX_EVENTS,
)


def kubernetes_read_catalog() -> OperationCatalog:
    """The declared, READ-only Kubernetes operation catalog (real capability
    contract). Provider I/O only happens when the governed transport invokes the
    composed adapter — this is the contract, not the client. Evidence fields are the
    normalized top-level scalars a real adapter lifts from the K8s response."""
    return OperationCatalog(
        KUBERNETES_PROVIDER_ID,
        (
            _read("kubernetes.pods.list", "/api/v1/namespaces/{namespace}/pods",
                  parameters=(_NS, _LABEL, _LIMIT),
                  evidence=(_RV, "kind", "apiVersion", "podCount", "crashLoopCount"),
                  records=_POD_RECORDS),
            _read("kubernetes.pod.get", "/api/v1/namespaces/{namespace}/pods/{name}",
                  parameters=(_NS, _NAME),
                  evidence=(_RV, "kind", "name", "namespace", "phase", "restartCount",
                            "waitingReason",
                            # Phase 9.5: how the container LAST DIED. exitCode 137
                            # with reason OOMKilled is a resource failure; exit 1
                            # with reason Error is not. Nothing else in a pod's
                            # status separates those two as cleanly.
                            "lastExitCode", "lastTerminationReason")),
            _read("kubernetes.pod.logs", "/api/v1/namespaces/{namespace}/pods/{name}/log",
                  parameters=(_NS, _NAME, _TAIL, _SINCE, _PREVIOUS),
                  # Phase 11.3: the declared SHAPE of a log, never its text.
                  evidence=("lineCount", "errorLineCount", "truncated", "logUnavailable",
                            "patternCount", "patternsTruncated"),
                  required=("lineCount",), records=_LOG_PATTERN_RECORDS),
            _read("kubernetes.deployments.list",
                  "/apis/apps/v1/namespaces/{namespace}/deployments",
                  parameters=(_NS, _LABEL, _LIMIT),
                  evidence=(_RV, "kind", "apiVersion", "deploymentCount")),
            _read("kubernetes.deployment.get",
                  "/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
                  parameters=(_NS, _NAME),
                  evidence=(_RV, "kind", "name", "namespace", "replicas", "readyReplicas",
                            "availableReplicas",
                            # Phase 9.5: what is actually deployed. A revision
                            # change is the observable a regression hypothesis
                            # stands or falls on.
                            "revision", "image",
                            # Phase 11.4 (ADR-124): what a rollback plan binds to
                            # and what an independent verifier checks -- the
                            # object's identity (uid, generation), the digest of
                            # the template it runs, whether the controller has
                            # caught up (observedGeneration, updated/unavailable)
                            # and the controller's own conditions.
                            "uid", "generation", "observedGeneration", "updatedReplicas",
                            "unavailableReplicas", "paused", "templateDigest",
                            "revisionHistoryLimit", "availableCondition", "progressingReason",
                            "rolledBackByAction", "persistentVolumeClaims")),
            _read("kubernetes.events.list", "/api/v1/namespaces/{namespace}/events",
                  parameters=(_NS, _LIMIT, _FIELD),
                  # Phase 11.3: the control plane's own account of an object --
                  # BackOff, Unhealthy, Failed, ScalingReplicaSet -- with the
                  # timestamps that place them. Bounded and truncation-declared.
                  evidence=(_RV, "kind", "apiVersion", "eventCount", "eventsTruncated"),
                  records=_EVENT_RECORDS),
            _read(KUBERNETES_REPLICASETS_OPERATION,
                  "/apis/apps/v1/namespaces/{namespace}/replicasets",
                  parameters=(_NS, _LABEL, _LIMIT),
                  evidence=(_RV, "kind", "apiVersion", "replicaSetCount",
                            "replicaSetsTruncated"),
                  records=_REPLICASET_RECORDS),
            _watch(),
        ),
    )


def kubernetes_write_catalog() -> OperationCatalog:
    """The read catalog PLUS the one declared write (Phase 9.6).

    Kept separate from :func:`kubernetes_read_catalog` deliberately. A write does
    not belong in a function named "read": every existing caller — the read
    harnesses, the investigator's tool registry, the provider factory — asks for
    the read catalog and must keep getting exactly reads, so that a write can
    never reach them by having been quietly added to a set they already trust.
    A caller that wants the write has to name it here.

    Composing this catalog is NOT the same as being able to run the write. The
    operation it adds is an ``IRREVERSIBLE_WRITE``, which no CONTAINED worker may
    perform and which cannot be registered as a capability against one; see
    ADR-086.
    """
    reads = kubernetes_read_catalog()
    return OperationCatalog(
        KUBERNETES_PROVIDER_ID,
        tuple(reads.require(op) for op in reads.operations) + (_rollout_restart(),),
    )


def _rollout_restart() -> ProviderOperationSpec:
    """One workload rollout restart — the first governed Kubernetes write.

    Honest classification, and why it is not what it is usually called
    ------------------------------------------------------------------
    This is an ``IRREVERSIBLE_WRITE``. It is commonly described as safe or
    reversible, and by the definition this codebase uses — *"a declared inverse
    fully restores the prior state"* — it is neither. Stamping the pod template
    changes the template hash, which creates a new ReplicaSet and a new entry in
    the rollout history. Nothing removes that. ``kubectl rollout undo`` does not
    undo it; it appends another revision.

    What IS true, and is the narrower claim made instead: the **declared workload
    configuration is preserved**. Image, command, environment, replicas,
    resources, probes and volumes are untouched; the only field this operation
    writes is one platform-owned annotation on the pod template. That is a real
    safety property and it is not reversibility.

    Classifying it honestly costs nothing and buys the right behaviour: the
    autonomy policy's reversibility gate then forces HUMAN_APPROVAL_REQUIRED at
    A3 with no delegated autonomy, so A4 is unreachable for this operation by
    construction rather than by a rule somebody remembered to write.

    Blast radius is a property of the declaration
    ----------------------------------------------
    Two required path parameters — one namespace, one name — and nothing else.
    There is no label selector, no list, no wildcard, no ``--all``, and no field
    through which a second workload could be named. One call restarts one
    workload, because the operation cannot express anything larger.

    Non-idempotent, stated
    ------------------------
    Repeating it with a *different* action identity stamps a different annotation
    and triggers a second rollout. Repeating it with the SAME identity is a no-op
    at the API server, because the annotation already holds that value — which is
    why the value is the platform's idempotency key rather than a clock.
    """
    return ProviderOperationSpec(
        operation=ROLLOUT_RESTART_OPERATION,
        method="PATCH",
        path_template="/apis/apps/v1/namespaces/{namespace}/deployments/{name}",
        side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
        # Honest: the same authorized action repeated is safe (the annotation
        # already holds that value), but a *retry with a new identity* is a second
        # rollout. Execution must not blind-retry this, and NON_IDEMPOTENT is what
        # tells it so.
        effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
        parameters=(_NS, _NAME),
        static_headers={
            **_K8S_HEADERS,
            # A strategic merge patch: the API server merges this document into
            # the existing object rather than replacing it, so the rest of the pod
            # template is preserved by the SERVER, not by our hoping the body was
            # complete. Set here so the channel's JSON default cannot win.
            "content-type": "application/strategic-merge-patch+json",
        },
        success_statuses=(200,),
        response_required_fields=(_RV, "kind"),
        response_evidence_fields=(_RV, "kind", "name", "namespace", "revision",
                                  "image", "restartedByAction"),
        provider_timeout_seconds=_TIMEOUT,
        max_response_bytes=1024 * 1024,
    )


class KubernetesRestartBodyBuilder:
    """Builds the one request body this platform may send to Kubernetes.

    The whole document is a constant except for a single leaf, and that leaf is
    the platform's own action identity — never caller input, never a model's
    output, never a clock. There is no code path here that can produce any other
    shape: the dictionary below is written literally.

    Why the idempotency key and not a timestamp: ``plan()`` is documented as
    deterministic — *"Nothing here reads a clock, a counter, an attempt number or
    a random source"* — because "same authority, same request" is what makes an
    approval binding and a replay inert. A timestamp would break that on every
    call. The action identity keeps it, and additionally makes a re-run of the
    SAME authorized action a no-op at the API server rather than a second rollout.
    """

    def build(self, spec: Any, payload: Any, *, idempotency_key: Optional[str]) -> Any:
        if spec.operation != ROLLOUT_RESTART_OPERATION:
            # The builder is attached to the whole adapter; every other operation
            # keeps the flat body the spec declares.
            return None
        if not idempotency_key or not str(idempotency_key).strip():
            raise ValueError(
                "a rollout restart needs the platform's action identity to stamp; "
                "without one the request would either be non-deterministic or "
                "indistinguishable from a previous restart"
            )
        return {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            RESTART_ANNOTATION: str(idempotency_key)[:63],
                        }
                    }
                }
            }
        }


def _watch() -> ProviderOperationSpec:
    """One governed WATCH window over the pods of a namespace — Phase 9.3 (ADR-083).

    Same path as ``pods.list``; ``watch=true`` is what makes it a different
    operation, and it is declared here rather than passed in. That distinction is
    load-bearing: if ``watch`` were a caller parameter, the caller — not the
    capability — would decide whether an authorized read is one request or an open
    stream, and the approval would have covered neither specifically.

    ``allowWatchBookmarks=true`` is likewise part of what this operation is. A
    bookmark lets the API server advance our stream position during a quiet
    period without inventing a resource change, which is the difference between
    holding a position honestly and letting it go stale until it expires.

    The answer is newline-delimited JSON, decoded by ``KubernetesWatchDecoder``
    and normalized into declared, bounded per-event records. It is still a READ:
    a watch observes, and there is no field on this spec through which it could
    do anything else.
    """
    return ProviderOperationSpec(
        operation=KUBERNETES_WATCH_OPERATION,
        method="GET",
        path_template="/api/v1/namespaces/{namespace}/pods",
        side_effect_class=SideEffectClass.READ,
        effect_semantics=EffectSemantics.READ_ONLY,
        parameters=(_NS, _WATCH_RV, _WATCH_TIMEOUT, _LABEL),
        static_query={"watch": "true", "allowWatchBookmarks": "true"},
        success_statuses=(200,),
        # An empty window is a legitimate, successful answer (nothing happened),
        # so the only field a valid answer must always carry is the count.
        response_required_fields=("eventCount",),
        response_evidence_fields=(
            "eventCount", "lastResourceVersion", "bookmarkCount",
            "streamErrorCode", "streamErrorReason",
        ),
        response_evidence_records=RecordEvidenceSpec(
            field_name="events",
            fields=("type", "kind", "namespace", "name", "uid", _RV),
            max_records=WATCH_MAX_EVENTS,
        ),
        static_headers=_K8S_HEADERS,
        # Must outlive the window the server is holding open, and stays under the
        # transport's own read timeout regime; the channel takes the minimum of
        # this, the policy, and the remaining authority window regardless.
        provider_timeout_seconds=float(WATCH_WINDOW_SECONDS) + 8.0,
        # Narrower than a list: a window is a handful of events, and a window
        # that overran this budget is refused rather than half-read.
        max_response_bytes=1024 * 1024,
    )


def kubernetes_real_read_catalog() -> OperationCatalog:
    """The Phase 9.2 REAL exposure: exactly one operation (Part E). A deployment
    that composes the real adapter exposes this subset; the full read catalog
    remains the declared contract for later phases to expose deliberately."""
    full = kubernetes_read_catalog()
    return OperationCatalog(
        KUBERNETES_PROVIDER_ID,
        tuple(full.require(op) for op in KUBERNETES_REAL_READ_OPERATIONS),
    )


class KubernetesResponseTranslator(HttpStatusTranslator):
    """Kubernetes answers failures with a ``Status`` object carrying a bounded
    ``message`` ("pods is forbidden: User ... cannot list resource ..."). The
    default status mapping already classifies 401/403/404/410 correctly; this
    translator only extracts that message so an operator sees the cluster's own
    sentence instead of a bare status code. It cannot reclassify a failure into
    a success: ``classify`` is inherited unchanged."""

    def describe(self, exchange: Any, body: Any) -> Tuple[Optional[str], Optional[str]]:
        code, reason = super().describe(exchange, body)
        if isinstance(body, Mapping) and body.get("kind") == "Status":
            message = body.get("message")
            if isinstance(message, str) and message.strip():
                return code, message.strip()[:200]
        return code, reason


class KubernetesWatchDecoder:
    """Decodes what Kubernetes actually puts on the wire for a watch.

    A watch response is **newline-delimited JSON**: HTTP 200, then one complete
    JSON object per line, for as long as the window stays open. It is not a JSON
    document, so ``ProviderExchange.json()`` — which is right for every other
    operation — would refuse it.

    Dispatch is by declaration, not by name: this decoder switches on
    ``spec.static_query["watch"]``, so an operation is decoded as a stream
    because its contract says it is one.

    Everything it will not do:

    * **No partial windows.** A truncated body is refused before parsing, exactly
      as ``json()`` refuses one. NDJSON is the shape where half an answer parses
      perfectly — every complete line is a complete event — and a window that
      silently lost its tail would advance the stream position past events that
      were never recorded.
    * **No skipping.** One unparseable line refuses the whole window. Dropping it
      and continuing would leave a gap the position then claims was covered.
    * **No invention.** An empty body is an empty window (a quiet cluster), which
      is a true and ordinary answer — not an error, and not a fabricated event.
    """

    def decode(self, spec: Any, exchange: Any) -> Tuple[Any, Optional[str]]:
        if spec.operation == "kubernetes.pod.logs":
            return self._decode_log(spec, exchange)
        if str(spec.static_query.get("watch", "")).lower() != "true":
            return exchange.json()
        if exchange.status_code not in spec.success_statuses:
            # A *failed* watch is not a stream. Kubernetes answers a refused
            # watch with an ordinary ``Status`` JSON document, and decoding that
            # as NDJSON would wrap it in an events envelope the translator can no
            # longer recognise — so the operator would get "status 410" instead
            # of the cluster's own "too old resource version: 4 (99)".
            #
            # Same rule the normalizer already follows: a failure body keeps the
            # provider's own dialect for the translator to describe.
            return exchange.json()
        if exchange.truncated:
            return None, (
                "the watch window hit the transport budget and was truncated; "
                "every complete line of a partial NDJSON window still parses, "
                "which is exactly why a partial window must not be accepted"
            )
        raw = exchange.body
        if raw is None:
            return None, "no watch response body was returned"
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None, "the watch response is not valid UTF-8"
        events = []
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                return None, (
                    f"watch line {number} is not valid JSON; the window is "
                    "refused rather than partially accepted"
                )
            if not isinstance(event, Mapping):
                return None, (
                    f"watch line {number} is a {type(event).__name__}, not a "
                    "watch event object"
                )
            events.append(event)
        return {"events": events}, None

    @staticmethod
    def _decode_log(spec: Any, exchange: Any) -> Tuple[Any, Optional[str]]:
        """Phase 11.3: a pod log is ``text/plain``, not a JSON document.

        A failed log read (403, 404, 400 for a container that never ran) is an
        ordinary ``Status`` JSON document and keeps the provider's dialect for
        the translator. A successful one is wrapped as ``{"log": text}`` for the
        normalizer, which turns it into declared, bounded pattern evidence. A
        truncated body is ACCEPTED and marked: unlike a watch window, a partial
        log is still true evidence of what the container said -- the bound is
        declared (``tailLines``), and the mark says the bound was hit.
        """
        if exchange.status_code not in spec.success_statuses:
            return exchange.json()
        raw = exchange.body
        if raw is None:
            return {"log": "", "truncated": False}, None
        text = raw.decode("utf-8", errors="replace")
        return {"log": text, "truncated": bool(exchange.truncated)}, None


_LOG_ERROR_WORDS = ("fatal", "panic", "error", "exception", "traceback", "critical",
                    "failed", "cannot", "unable", "refused", "denied")
_LOG_WARN_WORDS = ("warn",)
_LOG_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")
_LOG_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_LOG_HEX = re.compile(r"\b(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])[0-9a-f]{8,}\b")
_LOG_IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
_LOG_NUM = re.compile(r"\b\d+(?:\.\d+)?\b")
_LOG_WS = re.compile(r"\s+")
_LOG_UNAVAILABLE = re.compile(r"unable to retrieve container logs|previous terminated container .* not found|"
                              r"container .* is waiting to start", re.IGNORECASE)


def _template_digest(containers: Any) -> str:
    from backend.platform.hashing import compute_digest

    shape = []
    for container in containers:
        if not isinstance(container, Mapping):
            continue
        env = container.get("env")
        env_names = sorted(str(e.get("name")) for e in env if isinstance(e, Mapping)) if isinstance(env, list) else []
        env_from = container.get("envFrom")
        shape.append({
            "image": container.get("image"), "command": container.get("command"),
            "args": container.get("args"), "env": env_names,
            "envFrom": len(env_from) if isinstance(env_from, list) else 0,
            "resources": container.get("resources"),
        })
    return compute_digest(shape).value[:16]


def _log_level(line: str) -> str:
    lowered = line.lower()
    if any(word in lowered for word in _LOG_ERROR_WORDS):
        return "error"
    if any(word in lowered for word in _LOG_WARN_WORDS):
        return "warning"
    return "info"


def _log_pattern(line: str) -> str:
    """Deterministic message shape: identifiers and numbers become placeholders,
    whitespace collapses, secrets are scrubbed, length is bounded."""
    shaped = _LOG_TS.sub("<ts>", line)
    shaped = _LOG_UUID.sub("<uuid>", shaped)
    shaped = _LOG_IP.sub("<ip>", shaped)
    shaped = _LOG_HEX.sub("<hex>", shaped)
    shaped = _LOG_NUM.sub("#", shaped)
    shaped = _LOG_WS.sub(" ", shaped).strip()
    return _scrub(shaped)[:200]


def _scrub(text: str) -> str:
    from backend.platform.credentials.redaction import scrub_text

    return scrub_text(text, max_length=1024)


class KubernetesReadNormalizer:
    """Lifts the declared evidence scalars out of the Kubernetes envelope
    (Part G). This is the code the 9.1 docstring promised and 9.2 makes real.

    - ``metadata.resourceVersion`` → top-level ``resourceVersion``, **exactly as
      returned**: an opaque string, never coerced to an integer, never hashed,
      never substituted, never fabricated. If the cluster omitted it, it stays
      absent — the operation's required-field check then refuses the answer as
      malformed (Part N: reject, never synthesize).
    - list envelopes gain their declared counts (``podCount``/``crashLoopCount``/
      ``deploymentCount``/``eventCount``) computed from ``items``.
    - single-resource reads lift the declared identity/status scalars.

    Pure and deterministic; understands the envelope of every operation in the
    declared catalog; raises on a non-mapping body (the adapter then refuses the
    answer as malformed — a refusal, not an invention).
    """

    def normalize(self, spec: ProviderOperationSpec, body: Any) -> Any:
        if not isinstance(body, Mapping):
            raise ValueError(
                f"{spec.operation}: expected a JSON object envelope, "
                f"got {type(body).__name__}"
            )
        if spec.operation == KUBERNETES_WATCH_OPERATION:
            return self._normalize_watch(body)
        out = dict(body)
        meta = body.get("metadata")
        if isinstance(meta, Mapping):
            version = meta.get("resourceVersion")
            if isinstance(version, str) and version:
                out[_RV] = version
        items = body.get("items")
        op = spec.operation
        if op == "kubernetes.pods.list" and isinstance(items, list):
            out["podCount"] = len(items)
            out["crashLoopCount"] = sum(1 for pod in items if self._is_crashloop(pod))
            out["pods"] = [self._pod_record(pod) for pod in items
                           if isinstance(pod, Mapping)]
        elif op == "kubernetes.deployments.list" and isinstance(items, list):
            out["deploymentCount"] = len(items)
        elif op == "kubernetes.events.list" and isinstance(items, list):
            out["eventCount"] = len(items)
            records = [self._event_record(item) for item in items if isinstance(item, Mapping)]
            # Newest last-seen first, then deterministic. The cap is declared;
            # exceeding it is declared too ("eventsTruncated"), never silent.
            records.sort(key=lambda r: (r.get("lastTimestamp") or "", r.get("reason") or ""),
                         reverse=True)
            out["eventsTruncated"] = len(records) > EVENTS_MAX_RECORDS
            out["events"] = records[:EVENTS_MAX_RECORDS]
        elif op == KUBERNETES_REPLICASETS_OPERATION and isinstance(items, list):
            out["replicaSetCount"] = len(items)
            records = [self._replicaset_record(item) for item in items
                       if isinstance(item, Mapping)]
            records.sort(key=lambda r: (r.get("creationTimestamp") or "", r.get("name") or ""),
                         reverse=True)
            out["replicaSetsTruncated"] = len(records) > REPLICASETS_MAX_RECORDS
            out["replicaSets"] = records[:REPLICASETS_MAX_RECORDS]
        elif op == "kubernetes.pod.logs":
            out = self._normalize_log(body)
        elif op == "kubernetes.pod.get":
            self._lift_identity(out, meta)
            status = body.get("status")
            if isinstance(status, Mapping):
                phase = status.get("phase")
                if isinstance(phase, str):
                    out["phase"] = phase
                restarts, waiting = self._container_signal(status)
                if restarts is not None:
                    out["restartCount"] = restarts
                if waiting is not None:
                    out["waitingReason"] = waiting
                code, reason = self._last_termination(status)
                if code is not None:
                    out["lastExitCode"] = code
                if reason is not None:
                    out["lastTerminationReason"] = reason
        elif op in ("kubernetes.deployment.get", ROLLOUT_RESTART_OPERATION):
            self._lift_identity(out, meta)
            if isinstance(meta, Mapping):
                annotations = meta.get("annotations")
                if isinstance(annotations, Mapping):
                    revision = annotations.get("deployment.kubernetes.io/revision")
                    if isinstance(revision, str) and revision:
                        # Kept as the opaque string Kubernetes wrote. It is an
                        # identifier, not a quantity to compare arithmetically.
                        out["revision"] = revision
            image = self._first_container_image(body)
            if image is not None:
                out["image"] = image
            stamped = self._restart_annotation(body)
            if stamped is not None:
                out["restartedByAction"] = stamped
            wanted = body.get("spec")
            if isinstance(wanted, Mapping) and isinstance(wanted.get("replicas"), int):
                out["replicas"] = wanted["replicas"]
            status = body.get("status")
            if isinstance(status, Mapping):
                for field in ("readyReplicas", "availableReplicas"):
                    if isinstance(status.get(field), int):
                        out[field] = status[field]
                # Phase 11.4 (ADR-124): whether the controller has caught up with
                # the spec, and its own account of availability and progress.
                for field in ("updatedReplicas", "unavailableReplicas", "observedGeneration"):
                    value = status.get(field)
                    if isinstance(value, int) and not isinstance(value, bool):
                        out[field] = value
                for condition in status.get("conditions") or ():
                    if not isinstance(condition, Mapping):
                        continue
                    if condition.get("type") == "Available" and isinstance(condition.get("status"), str):
                        out["availableCondition"] = condition["status"]
                    if condition.get("type") == "Progressing" and isinstance(condition.get("reason"), str):
                        out["progressingReason"] = condition["reason"]
            # Phase 11.4 (ADR-124): the identity and template a rollback plan binds
            # to. Copied or digested, never inferred: a missing field stays absent.
            if isinstance(meta, Mapping):
                uid = meta.get("uid")
                if isinstance(uid, str) and uid:
                    out["uid"] = uid
                generation = meta.get("generation")
                if isinstance(generation, int) and not isinstance(generation, bool):
                    out["generation"] = generation
                annotations = meta.get("annotations")
                if isinstance(annotations, Mapping):
                    stamped_rollback = annotations.get(ROLLBACK_ANNOTATION)
                    if isinstance(stamped_rollback, str) and stamped_rollback:
                        out["rolledBackByAction"] = stamped_rollback
            if isinstance(wanted, Mapping):
                if isinstance(wanted.get("paused"), bool):
                    out["paused"] = wanted["paused"]
                limit = wanted.get("revisionHistoryLimit")
                if isinstance(limit, int) and not isinstance(limit, bool):
                    out["revisionHistoryLimit"] = limit
                template = wanted.get("template")
                if isinstance(template, Mapping):
                    out["templateDigest"] = pod_template_digest(template)
                    # Whether the workload mounts persistent data: a count of the
                    # template's persistentVolumeClaim volumes, never a guess.
                    pod_spec = template.get("spec")
                    volumes = pod_spec.get("volumes") if isinstance(pod_spec, Mapping) else None
                    out["persistentVolumeClaims"] = sum(
                        1 for v in (volumes or ()) if isinstance(v, Mapping) and v.get("persistentVolumeClaim"))
        return out

    # -- Phase 11.3 lifts ----------------------------------------------------

    @staticmethod
    def _event_record(item: Mapping) -> dict:
        """One Kubernetes Event as declared scalars. Copied, never computed;
        the message is bounded and secret-scrubbed because an event message is
        free text the control plane copied from a component."""
        record: dict = {}
        for field_name in ("reason", "type", "firstTimestamp", "lastTimestamp"):
            value = item.get(field_name)
            if isinstance(value, str) and value:
                record[field_name] = value
        if "lastTimestamp" not in record:
            value = item.get("eventTime")
            if isinstance(value, str) and value:
                record["lastTimestamp"] = value
        message = item.get("message")
        if isinstance(message, str) and message:
            record["message"] = _scrub(message)[:240]
        count = item.get("count")
        if isinstance(count, int) and not isinstance(count, bool):
            record["count"] = count
        involved = item.get("involvedObject")
        if isinstance(involved, Mapping):
            kind = involved.get("kind")
            name = involved.get("name")
            if isinstance(kind, str) and kind:
                record["involvedKind"] = kind
            if isinstance(name, str) and name:
                record["involvedName"] = name
        return record

    @staticmethod
    def _replicaset_record(item: Mapping) -> dict:
        record: dict = {}
        meta = item.get("metadata")
        if isinstance(meta, Mapping):
            name = meta.get("name")
            if isinstance(name, str) and name:
                record["name"] = name
            created = meta.get("creationTimestamp")
            if isinstance(created, str) and created:
                record["creationTimestamp"] = created
            annotations = meta.get("annotations")
            if isinstance(annotations, Mapping):
                revision = annotations.get("deployment.kubernetes.io/revision")
                if isinstance(revision, str) and revision:
                    record["revision"] = revision
            owners = meta.get("ownerReferences")
            if isinstance(owners, list):
                for owner in owners:
                    if isinstance(owner, Mapping) and isinstance(owner.get("name"), str):
                        record["ownerName"] = owner["name"]
                        if isinstance(owner.get("uid"), str) and owner["uid"]:
                            record["ownerUid"] = owner["uid"]
                        break
        spec = item.get("spec")
        if isinstance(spec, Mapping):
            replicas = spec.get("replicas")
            if isinstance(replicas, int) and not isinstance(replicas, bool):
                record["replicas"] = replicas
            template = spec.get("template")
            if isinstance(template, Mapping):
                record["podTemplateDigest"] = pod_template_digest(template)
                inner = template.get("spec")
                if isinstance(inner, Mapping):
                    containers = inner.get("containers")
                    if isinstance(containers, list) and containers:
                        first = containers[0]
                        if isinstance(first, Mapping) and isinstance(first.get("image"), str):
                            record["image"] = first["image"]
                        # A digest of what the containers RUN: image, command,
                        # args, env names, resources. Two revisions with the
                        # same digest differ only in metadata -- a rollout that
                        # changed nothing the process could feel.
                        record["templateDigest"] = _template_digest(containers)
        status = item.get("status")
        if isinstance(status, Mapping):
            ready = status.get("readyReplicas")
            if isinstance(ready, int) and not isinstance(ready, bool):
                record["readyReplicas"] = ready
        return record

    @staticmethod
    def _normalize_log(body: Mapping) -> dict:
        """The declared shape of a log: distinct message patterns, counted.

        Deterministic: timestamps, identifiers, addresses and numbers are
        replaced by placeholders so the SAME message recurring with different
        ids is one pattern with a count -- ten copies of one error are one
        piece of evidence that happened ten times, not ten pieces. Every
        pattern is secret-scrubbed before it can become an Observation, and
        capped in length. The raw text never leaves this function.
        """
        text = body.get("log")
        if not isinstance(text, str):
            text = ""
        lines = [line for line in text.splitlines() if line.strip()]
        # The kubelet answers 200 with its OWN error text when the requested
        # container log is gone ("unable to retrieve container logs for
        # containerd://..."). That is not the application saying anything; it is
        # the instrument saying it has nothing. Declared as such, and kept out
        # of the patterns, so an absent log can never refute a hypothesis.
        unavailable = [line for line in lines if _LOG_UNAVAILABLE.search(line)]
        lines = [line for line in lines if not _LOG_UNAVAILABLE.search(line)]
        patterns: dict = {}
        error_lines = 0
        for number, line in enumerate(lines, start=1):
            level = _log_level(line)
            if level == "error":
                error_lines += 1
            key = _log_pattern(line)
            entry = patterns.get(key)
            if entry is None:
                patterns[key] = {"pattern": key, "count": 1, "level": level,
                                 "firstLine": number}
            else:
                entry["count"] += 1
                if level == "error" and entry["level"] != "error":
                    entry["level"] = "error"
        records = sorted(patterns.values(), key=lambda r: (-r["count"], r["firstLine"]))
        return {
            "lineCount": len(lines),
            "errorLineCount": error_lines,
            "truncated": bool(body.get("truncated", False)),
            "logUnavailable": bool(unavailable) and not lines,
            "patternCount": len(records),
            "patternsTruncated": len(records) > LOG_MAX_PATTERNS,
            "patterns": records[:LOG_MAX_PATTERNS],
        }

    @classmethod
    def _pod_record(cls, pod: Mapping) -> dict:
        """The declared per-pod scalars of one list item (Phase 9.4).

        Every field is copied, never computed. ``restartCount`` in particular is
        the container statuses' total exactly as the API server reports it — the
        same number kube-state-metrics re-exports, which is what makes the two
        comparable at all. A pod with no container statuses yet contributes no
        restart count rather than a zero: not-observed and observed-zero are
        different claims.
        """
        record: dict = {}
        meta = pod.get("metadata")
        if isinstance(meta, Mapping):
            for field_name in ("name", "namespace", "uid"):
                value = meta.get(field_name)
                if isinstance(value, str) and value:
                    record[field_name] = value
            owners = meta.get("ownerReferences")
            if isinstance(owners, list):
                for owner in owners:
                    if isinstance(owner, Mapping) and owner.get("controller") is True \
                            and isinstance(owner.get("name"), str):
                        record["ownerName"] = owner["name"]
                        break
        status = pod.get("status")
        if isinstance(status, Mapping):
            phase = status.get("phase")
            if isinstance(phase, str) and phase:
                record["phase"] = phase
            restarts, waiting = cls._container_signal(status)
            if restarts is not None:
                record["restartCount"] = restarts
            if waiting is not None:
                record["waitingReason"] = waiting
            for condition in status.get("conditions") or ():
                if isinstance(condition, Mapping) and condition.get("type") == "Ready" \
                        and isinstance(condition.get("status"), str):
                    record["ready"] = condition["status"] == "True"
        return record

    @classmethod
    def _normalize_watch(cls, body: Mapping) -> dict:
        """One decoded watch window → declared, bounded per-event records.

        Fail-closed everywhere it matters. Every refusal below raises, and the
        adapter turns that into ``MALFORMED_RESPONSE`` — the window is rejected,
        the stream position does not move, and the driver re-watches from where
        it was. That is always safer than accepting an event nobody understood.

        * An **unknown event type** is refused (Part K). The set is closed.
        * A mutation event with **no resourceVersion** is refused. That value is
          the whole continuity mechanism; a mutation without one cannot be
          resumed from and must never be silently given someone else's.
        * A mutation event with **no name and no uid** is refused: an observation
          about an unidentifiable resource asserts nothing and can never be
          corroborated or superseded.
        * A **BOOKMARK** is kept, and kept distinct. It advances position and is
          not a mutation — no Observation about a resource may be built from one.
        * An **ERROR** terminates the window. Events before it are real and are
          kept; the error is surfaced as scalars (``streamErrorCode`` — 410 is
          the one that matters) and never as an event record. Nothing after it is
          read, because after an ERROR the server has stopped talking about this
          stream position.

        ``lastResourceVersion`` is the resourceVersion of the last event actually
        kept — copied exactly, opaque, never the largest, never computed. If no
        event carried one it stays absent, and the driver keeps the position it
        already had.
        """
        raw = body.get("events")
        if not isinstance(raw, list):
            raise ValueError("a decoded watch window must carry an events list")

        records: list = []
        bookmarks = 0
        last_version: Optional[str] = None
        error_code: Optional[int] = None
        error_reason: Optional[str] = None

        for index, event in enumerate(raw):
            if not isinstance(event, Mapping):
                raise ValueError(f"watch event {index} is not an object")
            kind = event.get("type")
            if not isinstance(kind, str) or kind not in KUBERNETES_WATCH_EVENT_TYPES:
                raise ValueError(
                    f"watch event {index} has type {kind!r}, which this "
                    f"normalizer does not understand; the understood set is "
                    f"{', '.join(KUBERNETES_WATCH_EVENT_TYPES)}"
                )
            obj = event.get("object")
            if not isinstance(obj, Mapping):
                raise ValueError(f"watch event {index} ({kind}) carries no object")

            if kind == "ERROR":
                error_code, error_reason = cls._stream_error(obj)
                break

            version = cls._event_version(obj)
            if version is None:
                raise ValueError(
                    f"watch event {index} ({kind}) has no "
                    "metadata.resourceVersion; continuity cannot be resumed "
                    "from an event that does not say where it sits"
                )

            if kind == "BOOKMARK":
                bookmarks += 1
                records.append({"type": kind, _RV: version})
                last_version = version
                continue

            record = {"type": kind, _RV: version}
            obj_kind = obj.get("kind")
            if isinstance(obj_kind, str) and obj_kind:
                record["kind"] = obj_kind
            meta = obj.get("metadata")
            if isinstance(meta, Mapping):
                for field_name in ("name", "namespace", "uid"):
                    value = meta.get(field_name)
                    if isinstance(value, str) and value:
                        record[field_name] = value
            if not record.get("name") and not record.get("uid"):
                raise ValueError(
                    f"watch event {index} ({kind}) identifies no resource "
                    "(neither metadata.name nor metadata.uid); an observation "
                    "about nothing in particular is not an observation"
                )
            records.append(record)
            last_version = version

        out: dict = {"events": records, "eventCount": len(records),
                     "bookmarkCount": bookmarks}
        if last_version is not None:
            out["lastResourceVersion"] = last_version
        if error_code is not None:
            out["streamErrorCode"] = error_code
        if error_reason:
            out["streamErrorReason"] = error_reason
        return out

    @staticmethod
    def _event_version(obj: Mapping) -> Optional[str]:
        """``metadata.resourceVersion``, exactly as returned. Opaque text: not
        parsed, not compared, not ordered, not converted."""
        meta = obj.get("metadata")
        if not isinstance(meta, Mapping):
            return None
        version = meta.get("resourceVersion")
        return version if isinstance(version, str) and version else None

    @staticmethod
    def _stream_error(obj: Mapping) -> Tuple[Optional[int], Optional[str]]:
        """The cluster's own account of why the stream stopped.

        ``code`` 410 is the load-bearing one — the watch resourceVersion is no
        longer retained and continuity is genuinely lost. It arrives here, inside
        a 200 response, at least as often as it arrives as an HTTP 410.
        """
        code = obj.get("code")
        reason = obj.get("reason")
        message = obj.get("message")
        text = reason if isinstance(reason, str) and reason else None
        if isinstance(message, str) and message.strip():
            text = f"{text}: {message.strip()}" if text else message.strip()
        return (code if isinstance(code, int) else None,
                text[:200] if isinstance(text, str) else None)

    @staticmethod
    def _lift_identity(out: dict, meta: Any) -> None:
        if isinstance(meta, Mapping):
            for field in ("name", "namespace"):
                value = meta.get(field)
                if isinstance(value, str) and value:
                    out[field] = value

    @staticmethod
    def _last_termination(status: Mapping) -> Tuple[Optional[int], Optional[str]]:
        """How the container last died - ``lastState.terminated`` (Phase 9.5).

        The first container's last termination, copied exactly. A pod that has
        never terminated contributes nothing rather than a zero: exit code 0 means
        "exited cleanly", and inventing it for a container that never exited would
        assert something no instrument reported.
        """
        statuses = status.get("containerStatuses")
        if not isinstance(statuses, list) or not statuses:
            return None, None
        first = statuses[0]
        if not isinstance(first, Mapping):
            return None, None
        last = first.get("lastState")
        if not isinstance(last, Mapping):
            return None, None
        terminated = last.get("terminated")
        if not isinstance(terminated, Mapping):
            return None, None
        code = terminated.get("exitCode")
        reason = terminated.get("reason")
        return (code if isinstance(code, int) and not isinstance(code, bool) else None,
                reason if isinstance(reason, str) and reason else None)

    @staticmethod
    def _restart_annotation(body: Mapping) -> Optional[str]:
        """The action identity a governed restart stamped on the pod template.

        Lifted so a read-back can confirm that the action the platform authorized
        is the action the cluster actually carries — not merely that *a* restart
        happened. An annotation somebody else wrote answers a different question.
        """
        spec = body.get("spec")
        if not isinstance(spec, Mapping):
            return None
        template = spec.get("template")
        if not isinstance(template, Mapping):
            return None
        meta = template.get("metadata")
        if not isinstance(meta, Mapping):
            return None
        annotations = meta.get("annotations")
        if not isinstance(annotations, Mapping):
            return None
        value = annotations.get(RESTART_ANNOTATION)
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _first_container_image(body: Mapping) -> Optional[str]:
        """The image the deployment declares for its first container."""
        spec = body.get("spec")
        if not isinstance(spec, Mapping):
            return None
        template = spec.get("template")
        if not isinstance(template, Mapping):
            return None
        pod_spec = template.get("spec")
        if not isinstance(pod_spec, Mapping):
            return None
        containers = pod_spec.get("containers")
        if not isinstance(containers, list) or not containers:
            return None
        first = containers[0]
        image = first.get("image") if isinstance(first, Mapping) else None
        return image if isinstance(image, str) and image else None

    @staticmethod
    def _container_signal(status: Mapping) -> Tuple[Optional[int], Optional[str]]:
        """Total restart count and the first waiting reason, from the pod's
        container statuses. Absent statuses stay absent."""
        statuses = status.get("containerStatuses")
        if not isinstance(statuses, list) or not statuses:
            return None, None
        restarts, waiting = 0, None
        for entry in statuses:
            if not isinstance(entry, Mapping):
                return None, None
            count = entry.get("restartCount")
            restarts += count if isinstance(count, int) else 0
            state = entry.get("state")
            if waiting is None and isinstance(state, Mapping):
                block = state.get("waiting")
                if isinstance(block, Mapping) and isinstance(block.get("reason"), str):
                    waiting = block["reason"]
        return restarts, waiting

    @classmethod
    def _is_crashloop(cls, pod: Any) -> bool:
        if not isinstance(pod, Mapping):
            return False
        status = pod.get("status")
        if not isinstance(status, Mapping):
            return False
        _, waiting = cls._container_signal(status)
        return waiting == "CrashLoopBackOff"


def build_kubernetes_channel(
    *,
    broker: TransportBroker,
    policy: ConnectionPolicy,
    environment: ExecutionEnvironment,
    base_url: str,
) -> ProviderChannel:
    """The channel the Kubernetes API server is reached through. The endpoint is
    deployment configuration — there is deliberately NO default: no universal
    Kubernetes address exists, and a guessed one would be a fabricated
    destination. HTTPS only, refused here as well as by policy: a ServiceAccount
    bearer token on plaintext is exposed on every request (the GitHub channel's
    posture, not Grafana's stated dev exception)."""
    endpoint = TransportEndpoint.parse(
        base_url, transport=TransportKind.HTTPS, environment=environment
    )
    if endpoint.is_plaintext:
        raise ValueError(
            "the Kubernetes API endpoint must be HTTPS; a bearer token on "
            "plaintext is exposed on every request"
        )
    return ProviderChannel(
        provider=KUBERNETES_PROVIDER,
        broker=broker,
        base_endpoint=endpoint,
        policy=policy,
        transport=TransportKind.HTTPS,
    )


def _profile(operation: str, resource_scope: str) -> CapabilityProfile:
    """A READ profile: LOW blast radius, autonomy ceiling A1 (observe/investigate,
    never an action), no verification (nothing to verify), reversible by nature."""
    factors = RiskFactors(side_effect_class=SideEffectClass.READ, environment="development",
                          resource_count=1, reversible=True)
    return CapabilityProfile(
        capability_ref=f"platform.{operation}",
        provider=KUBERNETES_PROVIDER_ID, operation=operation,
        side_effect_class=SideEffectClass.READ, effect_semantics=EffectSemantics.READ_ONLY,
        risk=RiskClassification(level=RiskLevel.LOW, factors=factors,
                                rationale=f"{operation}: read-only cluster observation"),
        autonomy_ceiling=AutonomyLevel.A1_INVESTIGATE,
        verification_requirement=VerificationRequirement.NONE,
        resource_scope=resource_scope, reversible=True, timeout_seconds=_TIMEOUT,
        policy_version=_POLICY_VERSION)


def kubernetes_write_profiles() -> dict:
    """The capability-bridge profile for the one governed Kubernetes write.

    Every field here is a claim the platform has to live with:

    * ``reversible=False`` — there is no inverse (see ``_rollout_restart``). This
      is what makes the autonomy policy's gate 9 fire and force human approval.
    * ``verification_requirement=INDEPENDENT_READBACK`` — the contract refuses a
      mutating capability that requires no verification, and rightly: an action
      whose effect nobody checks is an action nobody can be held to.
    * ``autonomy_ceiling=A3`` — approved action. Never A4; the platform may not
      delegate this to itself.
    * ``resource_scope="deployment"`` and ``resource_count=1`` — one workload.
    * ``RiskLevel.HIGH`` — a production-shaped workload restart is not routine
      for a platform doing it on its own initiative, and HIGH is what routes it
      through ``REQUIRE_APPROVAL`` in the governed policy.
    """
    factors = RiskFactors(side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
                          environment="development", resource_count=1,
                          reversible=False)
    return {
        ROLLOUT_RESTART_OPERATION: CapabilityProfile(
            capability_ref=f"platform.{ROLLOUT_RESTART_OPERATION}",
            provider=KUBERNETES_PROVIDER_ID, operation=ROLLOUT_RESTART_OPERATION,
            side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
            effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
            risk=RiskClassification(
                level=RiskLevel.HIGH, factors=factors,
                rationale=(
                    "restarts one workload's pods; preserves the declared "
                    "configuration but stamps the pod template and creates a new "
                    "revision, which no inverse removes")),
            autonomy_ceiling=AutonomyLevel.A3_APPROVED_ACTION,
            verification_requirement=VerificationRequirement.INDEPENDENT_READBACK,
            resource_scope="deployment", reversible=False,
            timeout_seconds=_TIMEOUT, policy_version=_POLICY_VERSION),
        # Phase 11.4 (ADR-124): the second governed write, and the first whose
        # L10 class is COMPENSABLE. Still ``reversible=False`` -- pods are
        # replaced and revision numbers advance, so no inverse FULLY restores the
        # prior state -- but it declares its compensation: the same rollback
        # capability, targeting the pre-action revision, whose ReplicaSet the
        # controller retains. Capability-level risk stays HIGH, so every rollback
        # needs an approval artifact; whether that artifact may be delegated is
        # decided per action by the plan's risk and the autonomy policy.
        DEPLOYMENT_ROLLBACK_OPERATION: CapabilityProfile(
            capability_ref=f"platform.{DEPLOYMENT_ROLLBACK_OPERATION}",
            provider="kubernetes-contained-rollback", operation=DEPLOYMENT_ROLLBACK_OPERATION,
            side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
            effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
            risk=RiskClassification(
                level=RiskLevel.HIGH,
                factors=RiskFactors(side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
                                    environment="development", resource_count=1, reversible=False),
                rationale=(
                    "replaces one Deployment's pod template with the template of a revision it "
                    "already ran; its pods are replaced and revision numbers advance (no full "
                    "inverse), and the pre-action revision stays available as a compensation")),
            autonomy_ceiling=AutonomyLevel.A4_AUTONOMOUS,
            verification_requirement=VerificationRequirement.INDEPENDENT_READBACK,
            resource_scope="deployment", reversible=False,
            timeout_seconds=60.0, policy_version=_POLICY_VERSION,
            compensation=f"platform.{DEPLOYMENT_ROLLBACK_OPERATION}"),
    }


def kubernetes_read_profiles() -> dict:
    """The capability-bridge profiles for each Kubernetes read operation (Part B/C)."""
    scope = {"kubernetes.pods.list": "namespace", "kubernetes.pod.get": "pod",
             "kubernetes.pod.logs": "pod", "kubernetes.deployments.list": "namespace",
             "kubernetes.deployment.get": "deployment", "kubernetes.events.list": "namespace",
             KUBERNETES_WATCH_OPERATION: "namespace",
             KUBERNETES_REPLICASETS_OPERATION: "namespace"}
    return {op: _profile(op, scope[op]) for op in KUBERNETES_READ_OPERATIONS}
