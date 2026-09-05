"""The CONTAINED worker: one capability, one operation, one document.

What this is
------------
CortexPrime's first genuinely out-of-process worker (ADR-089). It exists so that
``IsolationTier.CONTAINED`` has an occupant that earns the name: a separate
process, in a separate container, with its own filesystem and no ambient
credential -- rather than an in-process adapter that merely declares the tier.

What it deliberately is not
---------------------------
Not a Kubernetes client. Not an HTTP proxy. Not a plugin host. Not a shell. It
accepts no source, no path, no URL, no module name, no provider name, and no
operation other than the single one compiled into it at image build time.

**Python standard library only.** No pip, no third-party package, not even a
Kubernetes SDK. That is not minimalism for its own sake: ``CodeTrust.FIXED`` is
a claim that this worker cannot be made to do anything nobody declared, and a
dependency tree is precisely where undeclared behaviour hides. A reviewer can
read every line that runs here.

The envelope is checked before the credential is touched
--------------------------------------------------------
Binding verification happens first, in full, and refuses on the first mismatch.
A worker that authenticated and then discovered the request was for another
tenant would already have spent the credential. So: identity, then secrets.

Authority
---------
This worker has none. It receives an execution that the platform's gateway,
authorization, approval and autonomy policy already agreed to, and it performs
the one action or refuses. It cannot approve, cannot escalate, cannot choose a
provider, cannot choose a destination, and cannot decide what its own result
means -- ``succeeded`` here reports what the API server said, and the platform's
World and Assurance planes decide what actually happened.
"""

from __future__ import annotations

import json
import os
import resource
import ssl
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Compile-time binding. Supplied by the platform-controlled Deployment manifest
# and NEVER by a request. Anything a request could change is not a binding.
# ---------------------------------------------------------------------------
BIND_TENANT = os.environ.get("CORTEX_BIND_TENANT", "")
BIND_CAPABILITY_ID = os.environ.get("CORTEX_BIND_CAPABILITY_ID", "")
BIND_CAPABILITY_VERSION = os.environ.get("CORTEX_BIND_CAPABILITY_VERSION", "")
BIND_PROVIDER = os.environ.get("CORTEX_BIND_PROVIDER", "")
BIND_OPERATION = os.environ.get("CORTEX_BIND_OPERATION", "")
BIND_NAMESPACE = os.environ.get("CORTEX_BIND_NAMESPACE", "")
IMPLEMENTATION_DIGEST = os.environ.get("CORTEX_IMPLEMENTATION_DIGEST", "")
IMPLEMENTATION_VERSION = os.environ.get("CORTEX_IMPLEMENTATION_VERSION", "")

#: The one annotation this worker may write. CortexPrime's own key, not
#: kubectl's: an operator reading the cluster must be able to tell which system
#: touched the workload.
RESTART_ANNOTATION = "cortexprime.io/restarted-by-action"

#: The Kubernetes API server, from the container's own environment. This is
#: deployment configuration injected by the kubelet. It is not in the envelope
#: and there is deliberately no way for a caller to supply it.
K8S_HOST = os.environ.get("KUBERNETES_SERVICE_HOST", "")
K8S_PORT = os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS", "443")
K8S_CA = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

#: Exactly the envelope fields this worker understands. An envelope carrying
#: anything else is refused rather than trimmed -- an unexpected field is either
#: a caller this worker does not understand or an attempt to smuggle one in, and
#: both are refusals.
ENVELOPE_FIELDS = frozenset({
    "tenant", "execution_id", "capability_id", "capability_version",
    "provider", "operation", "implementation_digest", "arguments",
    "authorization_ref", "approval_ref", "autonomy_decision",
    "worker_identity", "execution_digest", "idempotency_key",
})
#: NOT an envelope field: ``credential``. The secret arrives as the transport
#: Authorization header, applied by the platform's single ``reveal()`` call site
#: (``httpx_adapter.py``). Keeping it out of the body means it is never part of
#: anything the platform digests, logs or persists as a request body -- and an
#: envelope that carries one anyway is refused by the unknown-field rule above,
#: because a caller putting a secret in the body is a caller doing something
#: this protocol does not do.

#: Exactly the arguments the declared operation takes. Same rule.
ARGUMENT_FIELDS = frozenset({"namespace", "name"})


class Refused(Exception):
    """A refusal. Carries no credential material and no stack detail."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail


def _verify_binding(envelope: Mapping[str, Any]) -> dict:
    """Check every binding before the credential is read. Refuse on the first.

    Order matters. Identity is established before anything secret is touched,
    so a refusal never spends a credential it was not entitled to use.
    """
    unknown = set(envelope) - ENVELOPE_FIELDS
    if unknown:
        raise Refused("envelope_unknown_fields",
                      f"envelope carries undeclared fields: {sorted(unknown)}")
    missing = ENVELOPE_FIELDS - set(envelope)
    if missing:
        raise Refused("envelope_incomplete",
                      f"envelope is missing: {sorted(missing)}")

    for label, got, expected in (
        ("tenant", envelope["tenant"], BIND_TENANT),
        ("capability_id", envelope["capability_id"], BIND_CAPABILITY_ID),
        ("capability_version", str(envelope["capability_version"]),
         BIND_CAPABILITY_VERSION),
        ("provider", envelope["provider"], BIND_PROVIDER),
        ("operation", envelope["operation"], BIND_OPERATION),
        ("implementation_digest", envelope["implementation_digest"],
         IMPLEMENTATION_DIGEST),
    ):
        if not expected:
            raise Refused("worker_unbound",
                          f"this worker was deployed without a {label} binding; "
                          "an unbound worker would accept anything")
        if got != expected:
            raise Refused(f"{label}_mismatch",
                          f"envelope {label}={got!r} but this worker is bound to "
                          f"{expected!r}")

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
        # Blast radius lives in the type, here as much as on the platform side.
        # A separator is how one target becomes many, and a traversal is how one
        # path becomes another.
        for bad in ("*", ",", " ", "/", "=", "\n", "\r", "\t", "..", "%", "?", "&"):
            if bad in value:
                raise Refused(f"{label}_not_a_single_target",
                              f"{label} contains {bad!r}; this worker addresses "
                              "exactly one workload")
    if namespace != BIND_NAMESPACE:
        raise Refused("namespace_out_of_scope",
                      f"this worker is bound to namespace {BIND_NAMESPACE!r} and "
                      f"was asked for {namespace!r}")

    key = envelope["idempotency_key"]
    if not isinstance(key, str) or not key:
        raise Refused("idempotency_key_missing",
                      "an unattributable write is not one this worker performs")
    for label in ("authorization_ref", "approval_ref", "autonomy_decision"):
        if not envelope[label]:
            raise Refused(f"{label}_missing",
                          f"the envelope carries no {label}; this worker performs "
                          "only executions the platform already authorized")
    return {"namespace": namespace, "name": name, "idempotency_key": key}


def _patch_deployment(target: Mapping[str, str], credential: str) -> dict:
    """The one provider call this worker can make. Nothing here is variable
    except the workload name, which was validated above."""
    if not K8S_HOST:
        raise Refused("no_api_server",
                      "the Kubernetes API address is not in this container's "
                      "environment; it is deployment configuration and this "
                      "worker will not accept one from a caller")

    url = (f"https://{K8S_HOST}:{K8S_PORT}/apis/apps/v1/namespaces/"
           f"{target['namespace']}/deployments/{target['name']}")
    body = json.dumps({
        "spec": {"template": {"metadata": {"annotations": {
            RESTART_ANNOTATION: target["idempotency_key"][:63]}}}}
    }).encode("utf-8")

    request = urllib.request.Request(
        url, data=body, method="PATCH",
        headers={
            "Content-Type": "application/strategic-merge-patch+json",
            "Accept": "application/json",
            "Authorization": f"Bearer {credential}",
        },
    )
    ctx = ssl.create_default_context(cafile=K8S_CA)
    try:
        with urllib.request.urlopen(request, context=ctx, timeout=30) as answer:
            payload = json.loads(answer.read().decode("utf-8") or "{}")
            status = answer.status
    except urllib.error.HTTPError as exc:
        # The cluster's own sentence, not ours. Never a success.
        raw = exc.read().decode("utf-8", "replace")[:400]
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {"message": raw}
        return {
            "succeeded": False, "ambiguous": False, "status": exc.code,
            "provider_message": str(payload.get("message", ""))[:300],
            "evidence": {},
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # The request may well have landed. Never SUCCESS, never FAILURE.
        return {
            "succeeded": False, "ambiguous": True, "status": None,
            "provider_message": f"{type(exc).__name__}: transport did not complete",
            "evidence": {},
        }

    metadata = payload.get("metadata") or {}
    spec_meta = (((payload.get("spec") or {}).get("template") or {})
                 .get("metadata") or {})
    return {
        "succeeded": 200 <= status < 300,
        "ambiguous": False,
        "status": status,
        "provider_message": None,
        "evidence": {
            "kind": payload.get("kind"),
            "name": metadata.get("name"),
            "namespace": metadata.get("namespace"),
            "resourceVersion": metadata.get("resourceVersion"),
            "generation": metadata.get("generation"),
            "restartAnnotation": (spec_meta.get("annotations") or {}).get(
                RESTART_ANNOTATION),
        },
    }


def _boundary_facts() -> dict:
    """Fixed measurements of this worker's own boundary, for the harness.

    Deliberately not a command endpoint: it takes no input and every value below
    is read from a fixed location. Environment variable **names** are reported
    and values never are -- the harness needs to prove no unrelated credential is
    present, which the names answer and the values would leak.
    """
    def _writable(path: str) -> bool:
        try:
            probe = os.path.join(path, ".cortex-write-probe")
            with open(probe, "w", encoding="utf-8") as handle:
                handle.write("x")
            os.unlink(probe)
            return True
        except OSError:
            return False

    try:
        nproc = resource.getrlimit(resource.RLIMIT_NPROC)
    except (ValueError, OSError):
        nproc = None

    return {
        "uid": os.getuid(),
        "gid": os.getgid(),
        "pid": os.getpid(),
        "root_writable": _writable("/"),
        "tmp_writable": _writable("/tmp"),
        "docker_socket_present": os.path.exists("/var/run/docker.sock"),
        "host_proc_present": os.path.exists("/host/proc"),
        "repo_present": os.path.exists("/app/backend") or os.path.exists("/backend"),
        "kubeconfig_present": (
            os.path.exists("/root/.kube/config")
            or os.path.exists(os.path.expanduser("~/.kube/config"))
        ),
        "sa_token_mounted": os.path.exists(
            "/var/run/secrets/kubernetes.io/serviceaccount/token"),
        "env_names": sorted(os.environ.keys()),
        "rlimit_nproc": nproc,
        "pid_1_is_self": os.getpid() == 1,
        "implementation_version": IMPLEMENTATION_VERSION,
        "implementation_digest": IMPLEMENTATION_DIGEST,
        "bound_to": {
            "tenant": BIND_TENANT,
            "capability_id": BIND_CAPABILITY_ID,
            "capability_version": BIND_CAPABILITY_VERSION,
            "provider": BIND_PROVIDER,
            "operation": BIND_OPERATION,
            "namespace": BIND_NAMESPACE,
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "cortexprime-contained-worker"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        """Log the method and path only.

        The envelope carries a credential, so a request body must never reach a
        log. This is the whole of the worker's logging.
        """
        sys.stderr.write(f"worker {self.command} {self.path}\n")

    def _respond(self, code: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's contract
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
                raise Refused("envelope_size", "envelope must be 1..65536 bytes")
            envelope = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(envelope, dict):
                raise Refused("envelope_malformed", "envelope must be an object")

            target = _verify_binding(envelope)          # identity first...

            # ...then the secret, from the transport header and never the body.
            header = self.headers.get("Authorization") or ""
            if not header.startswith("Bearer ") or len(header) <= 7:
                raise Refused("credential_missing",
                              "this worker holds no standing credential for the "
                              "action and was given none")
            credential = header[7:]

            outcome = _patch_deployment(target, credential)
            del credential
            self._respond(200, {"refused": False, **outcome})
        except Refused as refusal:
            # A refusal is not a provider call. Nothing was dialled.
            self._respond(200, {
                "refused": True,
                "reason_code": refusal.reason_code,
                "detail": refusal.detail,
                "succeeded": False,
                "ambiguous": False,
                "provider_called": False,
            })
        except Exception as exc:  # noqa: BLE001 - never leak, never claim
            self._respond(200, {
                "refused": True,
                "reason_code": "worker_internal",
                "detail": type(exc).__name__,
                "succeeded": False,
                "ambiguous": True,
                "provider_called": False,
            })


def main() -> None:
    missing = [name for name, value in (
        ("CORTEX_BIND_TENANT", BIND_TENANT),
        ("CORTEX_BIND_CAPABILITY_ID", BIND_CAPABILITY_ID),
        ("CORTEX_BIND_CAPABILITY_VERSION", BIND_CAPABILITY_VERSION),
        ("CORTEX_BIND_PROVIDER", BIND_PROVIDER),
        ("CORTEX_BIND_OPERATION", BIND_OPERATION),
        ("CORTEX_BIND_NAMESPACE", BIND_NAMESPACE),
        ("CORTEX_IMPLEMENTATION_DIGEST", IMPLEMENTATION_DIGEST),
    ) if not value]
    if missing:
        # Refuse to start rather than start unbound. An unbound worker would
        # accept whatever the first caller claimed.
        sys.stderr.write(
            f"worker refuses to start; unbound: {', '.join(missing)}\n")
        raise SystemExit(2)

    sys.stderr.write(
        f"worker bound to {BIND_OPERATION} for {BIND_CAPABILITY_ID}"
        f"@{BIND_CAPABILITY_VERSION} in {BIND_NAMESPACE}\n")

    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)

    # TLS is required, not optional. The platform sends the credential as this
    # connection's authorization header, and a worker that would serve it in the
    # clear is one misconfiguration away from doing so.
    cert, key = "/tls/tls.crt", "/tls/tls.key"
    if not (os.path.exists(cert) and os.path.exists(key)):
        sys.stderr.write(
            "worker refuses to start: no TLS material at /tls. The credential "
            "arrives as an authorization header and will not be served in the "
            "clear\n")
        raise SystemExit(2)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    sys.stderr.write("worker serving HTTPS on :8080\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
