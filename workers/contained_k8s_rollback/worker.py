"""The CONTAINED rollback worker: one capability, one operation, one document.

What this is
------------
The second genuinely out-of-process worker (ADR-124, after ADR-089's restart
worker). It performs exactly one typed action: roll ONE Deployment back to ONE
known revision that the platform named, bound to the Deployment's UID, its
generation, its current revision and the digest of the pod template it is
currently running. It is a sibling of the restart worker, not an extension of
it: a different ServiceAccount, a different binding, a different image digest.
A worker that could restart AND roll back would hold the union of both
authorities, and neither action would be contained by the other's review.

What it deliberately is not
---------------------------
Not a Kubernetes client. Not ``kubectl rollout undo``. It accepts no pod
template, no patch document, no path, no URL, no selector, no image and no
command. The template it writes is the one Kubernetes already holds in the
ReplicaSet the Deployment itself owns for the named revision -- read here, by
this worker, with its own credential -- and it is written only if that
template's digest is exactly the digest the platform approved. So the thing
approved and the thing written are one object, and nobody upstream (least of
all a model) can hand this worker a pod spec to run.

**Python standard library only.** Same reason as the restart worker:
``CodeTrust.FIXED`` is a claim that this worker cannot be made to do anything
nobody declared, and a dependency tree is where undeclared behaviour hides.

Order of operations (every step refuses before the next)
--------------------------------------------------------
1. Binding (identity, then arguments) -- before the credential is touched.
2. The authority window: an envelope whose authority has lapsed is refused
   before any provider call and again immediately before the write, so a
   worker holding an expired lease cannot write (fencing by time).
3. Preconditions from a fresh read of the Deployment: UID, generation,
   revision, not paused, current template digest.
4. The target: exactly one ReplicaSet controlled by that UID carries the target
   revision, and its template digest is the approved one; the pre-action
   revision's ReplicaSet is retained (the action stays compensable).
5. A server-side dry run (``dryRun=All``) of the exact patch.
6. The write: a JSON patch whose first two operations TEST the UID and the
   resourceVersion just read, so the API server applies it atomically only
   against the object that was checked. A concurrent writer makes it fail
   rather than interleave.

Authority
---------
None. ``succeeded`` reports what the API server said. The platform's World and
Assurance planes decide what actually happened, from an independent read made
with a different ServiceAccount.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Mapping, Optional

# ---------------------------------------------------------------------------
# Compile-time binding. Supplied by the platform-controlled Deployment manifest
# and NEVER by a request.
# ---------------------------------------------------------------------------
BIND_TENANT = os.environ.get("CORTEX_BIND_TENANT", "")
BIND_CAPABILITY_ID = os.environ.get("CORTEX_BIND_CAPABILITY_ID", "")
BIND_CAPABILITY_VERSION = os.environ.get("CORTEX_BIND_CAPABILITY_VERSION", "")
BIND_PROVIDER = os.environ.get("CORTEX_BIND_PROVIDER", "")
BIND_OPERATION = os.environ.get("CORTEX_BIND_OPERATION", "")
BIND_NAMESPACE = os.environ.get("CORTEX_BIND_NAMESPACE", "")
IMPLEMENTATION_DIGEST = os.environ.get("CORTEX_IMPLEMENTATION_DIGEST", "")
IMPLEMENTATION_VERSION = os.environ.get("CORTEX_IMPLEMENTATION_VERSION", "")

#: The one annotation this worker writes, on the Deployment's OWN metadata --
#: never on the pod template. A template annotation would change the template
#: hash, create a new ReplicaSet and make the "rollback" a new revision nobody
#: approved. On the Deployment metadata it changes no revision.
ROLLBACK_ANNOTATION = "cortexprime.io/rolled-back-by-action"
REVISION_ANNOTATION = "deployment.kubernetes.io/revision"
POD_TEMPLATE_HASH_LABEL = "pod-template-hash"

K8S_HOST = os.environ.get("KUBERNETES_SERVICE_HOST", "")
K8S_PORT = os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS", "443")
K8S_CA = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

ENVELOPE_FIELDS = frozenset({
    "tenant", "execution_id", "capability_id", "capability_version",
    "provider", "operation", "implementation_digest", "arguments",
    "authorization_ref", "approval_ref", "autonomy_decision",
    "worker_identity", "execution_digest", "idempotency_key",
    # The one field the restart envelope does not carry: when the authority
    # this execution was admitted under stops being valid.
    "authority_expires_at",
})

ARGUMENT_FIELDS = frozenset({
    "namespace", "name", "uid", "expected_generation", "expected_revision",
    "expected_template_digest", "target_revision", "target_template_digest",
    "plan_id", "policy_version",
})

_UID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_PLAN_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_POLICY_VERSION = re.compile(r"^[A-Za-z0-9_.:/()>=,+-]{1,80}$")
_SEGMENT_BAD = ("*", ",", " ", "/", "=", "\n", "\r", "\t", "..", "%", "?", "&")


class Refused(Exception):
    """A refusal before any provider call. Carries no credential material."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail


class Ambiguous(Exception):
    """The transport did not complete; the request may have landed."""


def pod_template_digest(template: Any) -> str:
    """The digest of a pod template, as the platform computes it.

    ``sha256`` over canonical JSON (sorted keys, no whitespace) of the template
    with the controller's ``pod-template-hash`` label and the serializer's
    ``metadata.creationTimestamp`` removed. Those are the only two ways a
    Deployment's template and the ReplicaSet created from it differ, so the
    same declared template gives the same digest on both. The platform-side
    copy is ``pod_template_digest`` in the Kubernetes connector; a unit test
    holds the two to identical answers.
    """
    if not isinstance(template, Mapping):
        raise ValueError("a pod template must be an object")
    body = copy.deepcopy(dict(template))
    meta = body.get("metadata")
    if isinstance(meta, Mapping):
        meta = dict(meta)
        labels = meta.get("labels")
        if isinstance(labels, Mapping):
            labels = {k: v for k, v in labels.items() if k != POD_TEMPLATE_HASH_LABEL}
            meta["labels"] = labels
        meta.pop("creationTimestamp", None)
        body["metadata"] = meta
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _int_arg(arguments: Mapping[str, Any], label: str) -> int:
    value = arguments.get(label)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise Refused(f"{label}_malformed", f"{label} must be a positive integer")
    return value


def _verify_binding(envelope: Mapping[str, Any], *, now: Optional[datetime] = None) -> dict:
    """Check every binding before the credential is read. Refuse on the first."""
    unknown = set(envelope) - ENVELOPE_FIELDS
    if unknown:
        raise Refused("envelope_unknown_fields",
                      f"envelope carries undeclared fields: {sorted(unknown)}")
    missing = ENVELOPE_FIELDS - set(envelope)
    if missing:
        raise Refused("envelope_incomplete", f"envelope is missing: {sorted(missing)}")

    for label, got, expected in (
        ("tenant", envelope["tenant"], BIND_TENANT),
        ("capability_id", envelope["capability_id"], BIND_CAPABILITY_ID),
        ("capability_version", str(envelope["capability_version"]), BIND_CAPABILITY_VERSION),
        ("provider", envelope["provider"], BIND_PROVIDER),
        ("operation", envelope["operation"], BIND_OPERATION),
        ("implementation_digest", envelope["implementation_digest"], IMPLEMENTATION_DIGEST),
    ):
        if not expected:
            raise Refused("worker_unbound",
                          f"this worker was deployed without a {label} binding; "
                          "an unbound worker would accept anything")
        if got != expected:
            raise Refused(f"{label}_mismatch",
                          f"envelope {label}={got!r} but this worker is bound to {expected!r}")

    arguments = envelope["arguments"]
    if not isinstance(arguments, dict):
        raise Refused("arguments_malformed", "arguments must be an object")
    unknown_args = set(arguments) - ARGUMENT_FIELDS
    if unknown_args:
        raise Refused("arguments_unknown_fields",
                      f"arguments carry undeclared fields: {sorted(unknown_args)}")
    if set(arguments) != ARGUMENT_FIELDS:
        raise Refused("arguments_incomplete",
                      f"arguments must be exactly {sorted(ARGUMENT_FIELDS)}")

    namespace, name = arguments["namespace"], arguments["name"]
    for label, value in (("namespace", namespace), ("name", name)):
        if not isinstance(value, str) or not value:
            raise Refused(f"{label}_malformed", f"{label} must be non-empty text")
        for bad in _SEGMENT_BAD:
            if bad in value:
                raise Refused(f"{label}_not_a_single_target",
                              f"{label} contains {bad!r}; this worker addresses exactly one workload")
    if namespace != BIND_NAMESPACE:
        raise Refused("namespace_out_of_scope",
                      f"this worker is bound to namespace {BIND_NAMESPACE!r} and was asked for {namespace!r}")

    uid = arguments["uid"]
    if not isinstance(uid, str) or not _UID.match(uid):
        raise Refused("uid_malformed", "uid must be a Kubernetes object UID")
    expected_generation = _int_arg(arguments, "expected_generation")
    expected_revision = _int_arg(arguments, "expected_revision")
    target_revision = _int_arg(arguments, "target_revision")
    if target_revision == expected_revision:
        raise Refused("target_is_current", "the target revision is the current revision; nothing to roll back")
    digests = {}
    for label in ("expected_template_digest", "target_template_digest"):
        value = arguments[label]
        if not isinstance(value, str) or not _DIGEST.match(value):
            raise Refused(f"{label}_malformed", f"{label} must be a sha256 hex digest")
        digests[label] = value
    if digests["expected_template_digest"] == digests["target_template_digest"]:
        raise Refused("target_template_is_current",
                      "the target template is the running template; nothing to roll back")
    plan_id = arguments["plan_id"]
    if not isinstance(plan_id, str) or not _PLAN_ID.match(plan_id):
        raise Refused("plan_id_malformed", "plan_id must be a platform plan reference")
    policy_version = arguments["policy_version"]
    if not isinstance(policy_version, str) or not _POLICY_VERSION.match(policy_version):
        raise Refused("policy_version_malformed", "policy_version must name the policy the plan was approved under")

    action_ref = envelope["execution_digest"]
    if not isinstance(action_ref, str) or not action_ref:
        raise Refused("execution_digest_missing", "an unattributable write is not one this worker performs")
    for label in ("authorization_ref", "approval_ref", "autonomy_decision"):
        if not envelope[label]:
            raise Refused(f"{label}_missing",
                          f"the envelope carries no {label}; this worker performs only executions "
                          "the platform already authorized")

    expires_at = _parse_expiry(envelope["authority_expires_at"])
    _check_authority_window(expires_at, now=now)
    return {
        "namespace": namespace, "name": name, "uid": uid,
        "expected_generation": expected_generation, "expected_revision": expected_revision,
        "expected_template_digest": digests["expected_template_digest"],
        "target_revision": target_revision,
        "target_template_digest": digests["target_template_digest"],
        "plan_id": plan_id, "policy_version": policy_version,
        "action_ref": action_ref, "authority_expires_at": expires_at,
    }


def _parse_expiry(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise Refused("authority_window_missing",
                      "the envelope does not say when its authority expires; an execution without a "
                      "window is one nothing could ever fence")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Refused("authority_window_malformed", "authority_expires_at is not an ISO-8601 instant") from None
    if parsed.tzinfo is None:
        raise Refused("authority_window_malformed", "authority_expires_at must carry a timezone")
    return parsed


def _check_authority_window(expires_at: datetime, *, now: Optional[datetime] = None) -> None:
    moment = now or _utcnow()
    if moment >= expires_at:
        raise Refused("authority_expired",
                      f"the authority this execution was admitted under expired at {expires_at.isoformat()}; "
                      "a worker whose lease has lapsed does not write")


# ---------------------------------------------------------------------------
# The Kubernetes calls. Fixed paths, fixed verbs; only the validated namespace
# and name vary. Injected for tests; production builds one per execution.
# ---------------------------------------------------------------------------

class KubeClient:
    def __init__(self, *, base_url: str, credential: str, context: ssl.SSLContext,
                 timeout: float = 30.0) -> None:
        self._base = base_url.rstrip("/")
        self._credential = credential
        self._context = context
        self._timeout = timeout

    def call(self, method: str, path: str, *, body: Any = None,
             content_type: Optional[str] = None) -> tuple:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self._credential}"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self._base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, context=self._context, timeout=self._timeout) as answer:
                raw = answer.read().decode("utf-8") or "{}"
                return answer.status, json.loads(raw)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")[:600]
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = {"message": raw}
            return exc.code, payload if isinstance(payload, dict) else {"message": str(payload)}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise Ambiguous(f"{type(exc).__name__}: transport did not complete") from None


def _deployment_path(target: Mapping[str, Any]) -> str:
    return (f"/apis/apps/v1/namespaces/{urllib.parse.quote(target['namespace'])}"
            f"/deployments/{urllib.parse.quote(target['name'])}")


def _replicasets_path(target: Mapping[str, Any]) -> str:
    return f"/apis/apps/v1/namespaces/{urllib.parse.quote(target['namespace'])}/replicasets"


def _failure(code: str, detail: str, *, status: Optional[int], evidence: Optional[dict] = None,
             provider_called: bool = True) -> dict:
    return {
        "refused": False, "succeeded": False, "ambiguous": False, "status": status,
        "provider_message": f"{code}: {detail}"[:300], "provider_called": provider_called,
        "evidence": {"preconditionFailed": True, "reasonCode": code, **(evidence or {})},
    }


def _message(payload: Mapping[str, Any]) -> str:
    return str(payload.get("message", ""))[:240]


def _owned_by(rs: Mapping[str, Any], uid: str) -> bool:
    owners = ((rs.get("metadata") or {}).get("ownerReferences")) or []
    return any(isinstance(o, Mapping) and o.get("uid") == uid and o.get("kind") == "Deployment"
               and o.get("controller") is True for o in owners)


def _revision_of(obj: Mapping[str, Any]) -> Optional[str]:
    annotations = ((obj.get("metadata") or {}).get("annotations")) or {}
    value = annotations.get(REVISION_ANNOTATION) if isinstance(annotations, Mapping) else None
    return value if isinstance(value, str) else None


def perform_rollback(target: Mapping[str, Any], client: Any, *,
                     clock: Callable[[], datetime] = _utcnow) -> dict:
    """Check, dry-run, write. Returns the worker's answer document."""
    # -- 3. the Deployment as it is now --------------------------------------
    status, deployment = client.call("GET", _deployment_path(target))
    if status == 404:
        return _failure("target_absent", "the Deployment no longer exists", status=status)
    if not 200 <= status < 300:
        return _failure("target_unreadable", _message(deployment), status=status)
    meta = deployment.get("metadata") or {}
    spec = deployment.get("spec") or {}
    observed = {
        "uid": meta.get("uid"), "generation": meta.get("generation"),
        "revision": _revision_of(deployment), "resourceVersion": meta.get("resourceVersion"),
    }
    if meta.get("uid") != target["uid"]:
        return _failure("uid_changed", "the Deployment was replaced; this plan was for a different object",
                        status=status, evidence={"observedUid": meta.get("uid")})
    current_template = spec.get("template")
    if not isinstance(current_template, Mapping):
        return _failure("target_malformed", "the Deployment has no pod template", status=status)
    current_digest = pod_template_digest(current_template)
    if current_digest == target["target_template_digest"]:
        # The world already holds the approved end state. Nothing is written; the
        # platform's independent verification decides what that means.
        return {"refused": False, "succeeded": True, "ambiguous": False, "status": status,
                "provider_message": None, "provider_called": True,
                "evidence": {"kind": deployment.get("kind"), "name": meta.get("name"),
                             "namespace": meta.get("namespace"), "resourceVersion": meta.get("resourceVersion"),
                             "generation": meta.get("generation"), "templateDigest": current_digest,
                             "noop": "already_at_target", "targetRevision": target["target_revision"],
                             "compensationRevision": target["expected_revision"]}}
    if spec.get("paused") is True:
        return _failure("deployment_paused", "a paused Deployment is not rolled back", status=status)
    if meta.get("generation") != target["expected_generation"]:
        return _failure("generation_changed",
                        f"generation is {meta.get('generation')}, the plan expected {target['expected_generation']}",
                        status=status, evidence={"observedGeneration": meta.get("generation")})
    if observed["revision"] != str(target["expected_revision"]):
        return _failure("revision_changed",
                        f"revision is {observed['revision']}, the plan expected {target['expected_revision']}",
                        status=status, evidence={"observedRevision": observed["revision"]})
    if current_digest != target["expected_template_digest"]:
        return _failure("template_changed", "the running pod template is not the one the plan was made against",
                        status=status)
    history_limit = spec.get("revisionHistoryLimit")
    if isinstance(history_limit, int) and history_limit < 1:
        return _failure("compensation_would_be_discarded",
                        "revisionHistoryLimit would discard the pre-action revision; the action would not be "
                        "compensable", status=status)

    # -- 4. the target revision, from the Deployment's OWN ReplicaSets --------
    status_rs, listing = client.call("GET", _replicasets_path(target))
    if not 200 <= status_rs < 300:
        return _failure("history_unreadable", _message(listing), status=status_rs)
    owned = [rs for rs in (listing.get("items") or []) if isinstance(rs, Mapping) and _owned_by(rs, target["uid"])]
    at_target = [rs for rs in owned if _revision_of(rs) == str(target["target_revision"])]
    if not at_target:
        # No fallback, no "previous revision instead". The approved target is
        # gone, so the approved action cannot be performed.
        return _failure("target_revision_unavailable",
                        f"no ReplicaSet of this Deployment carries revision {target['target_revision']}",
                        status=status_rs, evidence={"ownedReplicaSets": len(owned)})
    if len(at_target) > 1:
        return _failure("target_revision_ambiguous", "more than one ReplicaSet carries the target revision",
                        status=status_rs)
    target_rs = at_target[0]
    target_template = (target_rs.get("spec") or {}).get("template")
    if not isinstance(target_template, Mapping):
        return _failure("target_revision_malformed", "the target ReplicaSet has no pod template", status=status_rs)
    if pod_template_digest(target_template) != target["target_template_digest"]:
        return _failure("target_revision_drifted",
                        "the target revision's template is not the one that was approved", status=status_rs)
    if not any(_revision_of(rs) == str(target["expected_revision"]) for rs in owned):
        return _failure("compensation_unavailable",
                        "the pre-action revision's ReplicaSet is not retained; the action would not be compensable",
                        status=status_rs)

    # -- 5/6. the patch: tested against the object just read ------------------
    template = copy.deepcopy(dict(target_template))
    template_meta = dict(template.get("metadata") or {})
    labels = template_meta.get("labels")
    if isinstance(labels, Mapping):
        template_meta["labels"] = {k: v for k, v in labels.items() if k != POD_TEMPLATE_HASH_LABEL}
    template_meta.pop("creationTimestamp", None)
    template["metadata"] = template_meta
    annotation_value = target["action_ref"]
    operations = [
        {"op": "test", "path": "/metadata/uid", "value": target["uid"]},
        {"op": "test", "path": "/metadata/resourceVersion", "value": meta.get("resourceVersion")},
        {"op": "replace", "path": "/spec/template", "value": template},
    ]
    if isinstance(meta.get("annotations"), Mapping):
        operations.append({"op": "add", "path": "/metadata/annotations/"
                           + ROLLBACK_ANNOTATION.replace("~", "~0").replace("/", "~1"),
                           "value": annotation_value})
    else:
        operations.append({"op": "add", "path": "/metadata/annotations",
                           "value": {ROLLBACK_ANNOTATION: annotation_value}})

    _check_authority_window(target["authority_expires_at"], now=clock())
    status_dry, dry = client.call("PATCH", _deployment_path(target) + "?dryRun=All", body=operations,
                                  content_type="application/json-patch+json")
    if not 200 <= status_dry < 300:
        code = "dry_run_conflict" if status_dry in (409, 422) else "dry_run_refused"
        return _failure(code, _message(dry), status=status_dry)
    dry_template = ((dry.get("spec") or {}).get("template"))
    if not isinstance(dry_template, Mapping) or pod_template_digest(dry_template) != target["target_template_digest"]:
        return _failure("dry_run_unexpected_result",
                        "the server's dry-run result is not the approved template; nothing written", status=status_dry)

    # The second window check sits immediately before the only write.
    _check_authority_window(target["authority_expires_at"], now=clock())
    try:
        status_w, written = client.call("PATCH", _deployment_path(target), body=operations,
                                        content_type="application/json-patch+json")
    except Ambiguous as exc:
        return {"refused": False, "succeeded": False, "ambiguous": True, "status": None,
                "provider_message": str(exc), "provider_called": True,
                "evidence": {"dryRun": "passed"}}
    if not 200 <= status_w < 300:
        code = "precondition_changed_during_write" if status_w in (409, 422) else "write_refused"
        return _failure(code, _message(written), status=status_w, evidence={"dryRun": "passed"})
    wmeta = written.get("metadata") or {}
    wtemplate = ((written.get("spec") or {}).get("template")) or {}
    annotations = wmeta.get("annotations") if isinstance(wmeta.get("annotations"), Mapping) else {}
    return {
        "refused": False, "succeeded": True, "ambiguous": False, "status": status_w,
        "provider_message": None, "provider_called": True,
        "evidence": {
            "kind": written.get("kind"), "name": wmeta.get("name"), "namespace": wmeta.get("namespace"),
            "resourceVersion": wmeta.get("resourceVersion"), "generation": wmeta.get("generation"),
            "templateDigest": pod_template_digest(wtemplate) if isinstance(wtemplate, Mapping) else None,
            "rolledBackByAction": annotations.get(ROLLBACK_ANNOTATION),
            "targetRevision": target["target_revision"],
            "compensationRevision": target["expected_revision"], "dryRun": "passed",
        },
    }


def _boundary_facts() -> dict:
    """Fixed measurements of this worker's own boundary; env NAMES only."""
    def _writable(path: str) -> bool:
        try:
            probe = os.path.join(path, ".cortex-write-probe")
            with open(probe, "w", encoding="utf-8") as handle:
                handle.write("x")
            os.unlink(probe)
            return True
        except OSError:
            return False

    return {
        "uid": os.getuid(), "gid": os.getgid(), "pid": os.getpid(),
        "root_writable": _writable("/"), "tmp_writable": _writable("/tmp"),
        "docker_socket_present": os.path.exists("/var/run/docker.sock"),
        "repo_present": os.path.exists("/app/backend") or os.path.exists("/backend"),
        "kubeconfig_present": os.path.exists(os.path.expanduser("~/.kube/config")),
        "sa_token_mounted": os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"),
        "env_names": sorted(os.environ.keys()),
        "pid_1_is_self": os.getpid() == 1,
        "implementation_version": IMPLEMENTATION_VERSION,
        "implementation_digest": IMPLEMENTATION_DIGEST,
        "bound_to": {"tenant": BIND_TENANT, "capability_id": BIND_CAPABILITY_ID,
                     "capability_version": BIND_CAPABILITY_VERSION, "provider": BIND_PROVIDER,
                     "operation": BIND_OPERATION, "namespace": BIND_NAMESPACE},
    }


def _client_for(credential: str) -> KubeClient:
    if not K8S_HOST:
        raise Refused("no_api_server",
                      "the Kubernetes API address is not in this container's environment; it is deployment "
                      "configuration and this worker will not accept one from a caller")
    return KubeClient(base_url=f"https://{K8S_HOST}:{K8S_PORT}", credential=credential,
                      context=ssl.create_default_context(cafile=K8S_CA))


def handle_envelope(envelope: Any, authorization_header: str, *,
                    client_factory: Callable[[str], Any] = _client_for) -> dict:
    """The whole request, as a pure function of its inputs (tests call this)."""
    try:
        if not isinstance(envelope, dict):
            raise Refused("envelope_malformed", "envelope must be an object")
        target = _verify_binding(envelope)                 # identity + window first...
        header = authorization_header or ""
        if not header.startswith("Bearer ") or len(header) <= 7:
            raise Refused("credential_missing",
                          "this worker holds no standing credential for the action and was given none")
        client = client_factory(header[7:])                # ...then the secret
        return perform_rollback(target, client)
    except Refused as refusal:
        return {"refused": True, "reason_code": refusal.reason_code, "detail": refusal.detail,
                "succeeded": False, "ambiguous": False, "provider_called": False}
    except Ambiguous as exc:
        return {"refused": False, "succeeded": False, "ambiguous": True, "status": None,
                "provider_message": str(exc), "provider_called": True, "evidence": {}}


class Handler(BaseHTTPRequestHandler):
    server_version = "cortexprime-contained-rollback-worker"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        # Method and path only; a body or header never reaches a log.
        sys.stderr.write(f"worker {self.command} {self.path}\n")

    def _respond(self, code: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._respond(200, {"ok": True})
        elif self.path == "/boundary":
            self._respond(200, _boundary_facts())
        else:
            self._respond(404, {"error": "no such endpoint"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/execute":
            self._respond(404, {"error": "no such endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 64 * 1024:
                self._respond(200, {"refused": True, "reason_code": "envelope_size",
                                    "detail": "envelope must be 1..65536 bytes", "succeeded": False,
                                    "ambiguous": False, "provider_called": False})
                return
            envelope = json.loads(self.rfile.read(length).decode("utf-8"))
            self._respond(200, handle_envelope(envelope, self.headers.get("Authorization") or ""))
        except Exception as exc:  # noqa: BLE001 - never leak, never claim
            self._respond(200, {"refused": True, "reason_code": "worker_internal", "detail": type(exc).__name__,
                                "succeeded": False, "ambiguous": True, "provider_called": False})


def main() -> None:
    missing = [name for name, value in (
        ("CORTEX_BIND_TENANT", BIND_TENANT), ("CORTEX_BIND_CAPABILITY_ID", BIND_CAPABILITY_ID),
        ("CORTEX_BIND_CAPABILITY_VERSION", BIND_CAPABILITY_VERSION), ("CORTEX_BIND_PROVIDER", BIND_PROVIDER),
        ("CORTEX_BIND_OPERATION", BIND_OPERATION), ("CORTEX_BIND_NAMESPACE", BIND_NAMESPACE),
        ("CORTEX_IMPLEMENTATION_DIGEST", IMPLEMENTATION_DIGEST),
    ) if not value]
    if missing:
        sys.stderr.write(f"worker refuses to start; unbound: {', '.join(missing)}\n")
        raise SystemExit(2)
    sys.stderr.write(f"worker bound to {BIND_OPERATION} for {BIND_CAPABILITY_ID}@{BIND_CAPABILITY_VERSION} "
                     f"in {BIND_NAMESPACE}\n")
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    cert, key = "/tls/tls.crt", "/tls/tls.key"
    if not (os.path.exists(cert) and os.path.exists(key)):
        sys.stderr.write("worker refuses to start: no TLS material at /tls\n")
        raise SystemExit(2)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    sys.stderr.write("worker serving HTTPS on :8080\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
