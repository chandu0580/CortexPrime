"""The CONTAINED GitHub worker: one capability, one operation, one comment.

What this is
------------
The second occupant of ``IsolationTier.CONTAINED`` (ADR-089), and the first for
a software-development provider. A separate process, in a separate container,
with its own read-only filesystem and no standing credential, which can post
exactly one kind of thing to exactly the repositories it was deployed against.

What it deliberately is not
---------------------------
Not a GitHub client. Not an HTTP proxy. Not a plugin host. Not a shell. It
accepts no URL, no host, no path, no method, no repository outside its binding
and no operation other than the single one compiled into it at image build
time. **Python standard library only** -- no pip, no SDK: ``CodeTrust.FIXED``
claims this worker cannot be made to do anything nobody declared, and a
dependency tree is where undeclared behaviour hides.

The envelope is checked before the credential is touched
--------------------------------------------------------
Binding verification happens first, in full, and refuses on the first mismatch,
so a refusal never spends a credential it was not entitled to use.

Attribution, since GitHub has no annotation
--------------------------------------------
The Kubernetes workers stamp the object with the action digest. A GitHub comment
has no such field, so this worker appends one attribution line naming the
CortexPrime action to the body it posts. That line is how a human reading the
thread knows what produced the comment, and how independent verification
recognises the comment as the one this action created rather than a similar one
somebody else wrote. The caller's text is never otherwise altered.

Authority
---------
None. It performs an execution the platform's gateway, authorization, approval
and autonomy policy already agreed to, and reports what GitHub said. It cannot
approve, escalate, choose a provider or a destination, or decide what its own
result means.
"""

from __future__ import annotations

import hashlib
import json
import os
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
#: Comma-separated "owner/repo" entries. GitHub treats repository names
#: case-insensitively, so the comparison below does too -- a case-shifted name
#: is the same repository and must not read as a different one.
BIND_REPOSITORIES = tuple(
    entry.strip().casefold()
    for entry in os.environ.get("CORTEX_BIND_REPOSITORIES", "").split(",")
    if entry.strip()
)
IMPLEMENTATION_DIGEST = os.environ.get("CORTEX_IMPLEMENTATION_DIGEST", "")
IMPLEMENTATION_VERSION = os.environ.get("CORTEX_IMPLEMENTATION_VERSION", "")

#: The GitHub API host, from the container's own environment: deployment
#: configuration (GitHub Enterprise Server names its own). Never from a caller.
GITHUB_API_HOST = os.environ.get("CORTEX_GITHUB_API_HOST", "api.github.com")
#: An enterprise deployment behind a private CA supplies its bundle here.
GITHUB_CA = os.environ.get("CORTEX_GITHUB_CA_BUNDLE") or None

ENVELOPE_FIELDS = frozenset({
    "tenant", "execution_id", "capability_id", "capability_version",
    "provider", "operation", "implementation_digest", "arguments",
    "authorization_ref", "approval_ref", "autonomy_decision",
    "worker_identity", "execution_digest", "idempotency_key",
})
#: NOT an envelope field: ``credential``. The secret arrives as the transport
#: Authorization header, applied by the platform's single ``reveal()`` call
#: site, so it is never part of anything the platform digests, logs or persists
#: as a request body -- and an envelope carrying one anyway is refused by the
#: unknown-field rule above.
ARGUMENT_FIELDS = frozenset({"owner", "repo", "issue_number", "body"})

#: GitHub's own limit for a comment body.
MAX_BODY = 65536
#: Room for the attribution line the worker appends.
MAX_CALLER_BODY = MAX_BODY - 256


class Refused(Exception):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail


def _verify_binding(envelope: Mapping[str, Any]) -> dict:
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
    if set(arguments) != ARGUMENT_FIELDS:
        raise Refused("arguments_incomplete",
                      f"arguments must be exactly {sorted(ARGUMENT_FIELDS)}")

    owner, repo = arguments["owner"], arguments["repo"]
    for label, value in (("owner", owner), ("repo", repo)):
        if not isinstance(value, str) or not value:
            raise Refused(f"{label}_malformed", f"{label} must be non-empty text")
        # A separator is how one target becomes many; a traversal is how one
        # path becomes another. Neither belongs in a repository identifier.
        for bad in ("*", ",", " ", "/", "=", "\n", "\r", "\t", "..", "%", "?", "&", "@", ":"):
            if bad in value:
                raise Refused(f"{label}_not_a_single_target",
                              f"{label} contains {bad!r}; this worker addresses exactly "
                              "one repository")
    repository = f"{owner}/{repo}"
    if not BIND_REPOSITORIES:
        raise Refused("worker_unbound",
                      "this worker was deployed without a repository binding")
    if repository.casefold() not in BIND_REPOSITORIES:
        raise Refused("repository_out_of_scope",
                      f"this worker is bound to {len(BIND_REPOSITORIES)} repository/ies "
                      f"and was asked for {repository!r}")

    issue_number = arguments["issue_number"]
    if isinstance(issue_number, bool) or not isinstance(issue_number, int) or issue_number <= 0:
        raise Refused("issue_number_malformed",
                      "issue_number must be a positive integer; a path fragment is not one")

    body = arguments["body"]
    if not isinstance(body, str) or not body.strip():
        raise Refused("body_malformed", "body must be non-empty text")
    if len(body) > MAX_CALLER_BODY:
        raise Refused("body_too_long",
                      f"body exceeds {MAX_CALLER_BODY} characters")

    key = envelope["execution_digest"]
    if not isinstance(key, str) or not key:
        raise Refused("execution_digest_missing",
                      "an unattributable write is not one this worker performs")
    for label in ("authorization_ref", "approval_ref", "autonomy_decision"):
        if not envelope[label]:
            raise Refused(f"{label}_missing",
                          f"the envelope carries no {label}; this worker performs only "
                          "executions the platform already authorized")
    return {"owner": owner, "repo": repo, "issue_number": issue_number,
            "body": body, "action_ref": key}


def _attributed_body(target: Mapping[str, Any]) -> str:
    """The caller's text, plus exactly one attribution line. Never a rewrite."""
    action = str(target["action_ref"])[:16]
    return (f"{target['body']}\n\n"
            f"<sub>Posted by CortexPrime — governed action {action}</sub>")


def _post_comment(target: Mapping[str, Any], credential: str) -> dict:
    """The one provider call this worker can make. Host, path and method are
    fixed; only the repository, issue number and body vary, all validated."""
    url = (f"https://{GITHUB_API_HOST}/repos/{target['owner']}/{target['repo']}"
           f"/issues/{target['issue_number']}/comments")
    body_text = _attributed_body(target)
    payload = json.dumps({"body": body_text}).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CortexPrime-ContainedWorker/1.0",
            "Authorization": f"Bearer {credential}",
        },
    )
    context = ssl.create_default_context(cafile=GITHUB_CA)
    try:
        with urllib.request.urlopen(request, context=context, timeout=30) as answer:
            document = json.loads(answer.read().decode("utf-8") or "{}")
            status, headers = answer.status, dict(answer.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")[:400]
        headers = dict(exc.headers or {})
        try:
            document = json.loads(raw)
        except ValueError:
            document = {"message": raw}
        return {
            "succeeded": False, "ambiguous": False, "status": exc.code,
            "provider_message": str(document.get("message", ""))[:300],
            "rate_limit": _rate_facts(headers),
            "evidence": {},
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # The request may well have landed: GitHub has no idempotency key, so a
        # repeat could post a second comment. Never SUCCESS, never FAILURE.
        return {
            "succeeded": False, "ambiguous": True, "status": None,
            "provider_message": f"{type(exc).__name__}: transport did not complete",
            "rate_limit": {}, "evidence": {},
        }

    user = document.get("user") if isinstance(document.get("user"), dict) else {}
    return {
        "succeeded": 200 <= status < 300,
        "ambiguous": False,
        "status": status,
        "provider_message": None,
        "rate_limit": _rate_facts(headers),
        "evidence": {
            "comment_id": document.get("id"),
            "html_url": document.get("html_url"),
            "issue_url": document.get("issue_url"),
            "created_at": document.get("created_at"),
            "author_login": user.get("login"),
            # The content, as a digest: enough for the platform to verify that
            # the comment GitHub holds is the one this action composed, without
            # echoing the text back through another system.
            "body_sha256": hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
            "action_marker": str(target["action_ref"])[:16],
        },
    }


def _rate_facts(headers: Mapping[str, str]) -> dict:
    """GitHub's rate-limit state, as facts. Never a decision taken here."""
    lower = {str(k).lower(): v for k, v in (headers or {}).items()}
    facts = {}
    for name in ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-used",
                 "x-ratelimit-reset", "x-ratelimit-resource", "retry-after"):
        if name in lower:
            facts[name.replace("x-ratelimit-", "").replace("-", "_")] = str(lower[name])[:32]
    return facts


def _boundary_facts() -> dict:
    """Fixed measurements of this worker's own boundary, for the harness.

    Not a command endpoint: it takes no input, and every value is read from a
    fixed location. Environment variable NAMES are reported and values never
    are -- the harness proves no unrelated credential is present, which the
    names answer and the values would leak.
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
        # POSIX only, and imported here rather than at module scope so the
        # worker's own logic can be exercised anywhere its tests run.
        import resource

        nproc = resource.getrlimit(resource.RLIMIT_NPROC)
    except (ImportError, ValueError, OSError):
        nproc = None

    return {
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "gid": os.getgid() if hasattr(os, "getgid") else None,
        "pid": os.getpid(),
        "root_writable": _writable("/"), "tmp_writable": _writable("/tmp"),
        "docker_socket_present": os.path.exists("/var/run/docker.sock"),
        "host_proc_present": os.path.exists("/host/proc"),
        "repo_present": os.path.exists("/app/backend") or os.path.exists("/backend"),
        "kubeconfig_present": (os.path.exists("/root/.kube/config")
                               or os.path.exists(os.path.expanduser("~/.kube/config"))),
        "sa_token_mounted": os.path.exists(
            "/var/run/secrets/kubernetes.io/serviceaccount/token"),
        "env_names": sorted(os.environ.keys()),
        "rlimit_nproc": nproc,
        "pid_1_is_self": os.getpid() == 1,
        "implementation_version": IMPLEMENTATION_VERSION,
        "implementation_digest": IMPLEMENTATION_DIGEST,
        "api_host": GITHUB_API_HOST,
        "bound_to": {
            "tenant": BIND_TENANT,
            "capability_id": BIND_CAPABILITY_ID,
            "capability_version": BIND_CAPABILITY_VERSION,
            "provider": BIND_PROVIDER,
            "operation": BIND_OPERATION,
            "repositories": list(BIND_REPOSITORIES),
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "cortexprime-contained-github-worker"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        """Method and path only: the request carries a credential and a body."""
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
        credential = None
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > 128 * 1024:
                raise Refused("envelope_size", "envelope must be 1..131072 bytes")
            envelope = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(envelope, dict):
                raise Refused("envelope_malformed", "envelope must be an object")

            target = _verify_binding(envelope)          # identity first...

            # ...then the secret, from the transport header and never the body.
            header = self.headers.get("Authorization") or ""
            if not header.startswith("Bearer ") or len(header) <= 7:
                raise Refused("credential_missing",
                              "this worker holds no standing credential for the action "
                              "and was given none")
            credential = header[7:]
            outcome = _post_comment(target, credential)
            self._respond(200, {"refused": False, **outcome})
        except Refused as refusal:
            # A refusal is not a provider call. Nothing was dialled.
            self._respond(200, {
                "refused": True, "reason_code": refusal.reason_code,
                "detail": refusal.detail, "succeeded": False,
                "ambiguous": False, "provider_called": False,
            })
        except Exception as exc:  # noqa: BLE001 - never leak, never claim
            self._respond(200, {
                "refused": True, "reason_code": "worker_internal",
                "detail": type(exc).__name__, "succeeded": False,
                "ambiguous": True, "provider_called": False,
            })
        finally:
            del credential


def main() -> None:
    missing = [name for name, value in (
        ("CORTEX_BIND_TENANT", BIND_TENANT),
        ("CORTEX_BIND_CAPABILITY_ID", BIND_CAPABILITY_ID),
        ("CORTEX_BIND_CAPABILITY_VERSION", BIND_CAPABILITY_VERSION),
        ("CORTEX_BIND_PROVIDER", BIND_PROVIDER),
        ("CORTEX_BIND_OPERATION", BIND_OPERATION),
        ("CORTEX_BIND_REPOSITORIES", ",".join(BIND_REPOSITORIES)),
        ("CORTEX_IMPLEMENTATION_DIGEST", IMPLEMENTATION_DIGEST),
    ) if not value]
    if missing:
        # Refuse to start rather than start unbound: an unbound worker would
        # accept whatever the first caller claimed.
        sys.stderr.write(f"worker refuses to start; unbound: {', '.join(missing)}\n")
        raise SystemExit(2)

    sys.stderr.write(
        f"contained github worker: tenant={BIND_TENANT} operation={BIND_OPERATION} "
        f"repositories={len(BIND_REPOSITORIES)} api={GITHUB_API_HOST}\n")

    certificate = os.environ.get("CORTEX_WORKER_TLS_CERT", "/tls/tls.crt")
    key = os.environ.get("CORTEX_WORKER_TLS_KEY", "/tls/tls.key")
    port = int(os.environ.get("CORTEX_WORKER_PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certificate, keyfile=key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
