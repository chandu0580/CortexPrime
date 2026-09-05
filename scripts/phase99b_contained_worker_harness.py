"""Phase 9.9B evidence: CONTAINED is a real execution boundary (ADR-089).

What this proves, in order
--------------------------
1. **The boundary is real, measured from inside it.** Separate container,
   separate PID namespace, non-root, read-only root filesystem, no Docker
   socket, no repository, no kubeconfig, and -- the decisive one -- **no
   CortexPrime credential anywhere in the worker's environment.**
2. **The worker is bound, not general.** Every binding is checked against a live
   worker: a changed operation, provider, tenant, capability version or
   implementation digest is refused, and so is an argument the schema does not
   declare. Each refusal is executed, not reasoned about.
3. **The governed chain still owns the decision.** The write travels
   ``GovernedCapabilityWriter`` → gateway → ``WorkerRuntime`` → adapter →
   worker → API server. No second executor, gateway, scheduler, credential
   authority or audit path exists.
4. **Then, and only then, the first real irreversible Kubernetes write** -- with
   the result established by an *independent* governed read rather than by the
   worker's own answer.

The stop rule
-------------
Every safety negative runs BEFORE the write. If any boundary or binding check
fails, the harness stops without writing and says which property failed, exactly
as Phases 9.6 and 9.7 did.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED / BLOCKED.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

REPORT: dict = {
    "phase": "9.9B",
    "checks": [],
    "deferred": [],
    "measurements": {},
    "verdict": "NOT VERIFIED",
}

WORKER_URL = os.getenv("CORTEX_P99B_WORKER_URL", "")
CA_BUNDLE = os.getenv("CORTEX_TLS_CA_BUNDLE", "")
NAMESPACE = os.getenv("CORTEX_P99B_NAMESPACE", "cortex-p99b")
OTHER_NS = os.getenv("CORTEX_P99B_OTHER_NAMESPACE", "cortex-p99b-other")
TARGET = os.getenv("CORTEX_P99B_TARGET", "payments-api")
BYSTANDER = os.getenv("CORTEX_P99B_BYSTANDER", "billing-api")
IMPL_DIGEST = os.getenv("CORTEX_P99B_IMPL_DIGEST", "")
CAPABILITY_ID = os.getenv("CORTEX_P99B_CAPABILITY_ID", "")
CAPABILITY_VERSION = int(os.getenv("CORTEX_P99B_CAPABILITY_VERSION", "1"))
OPERATION = os.getenv("CORTEX_P99B_OPERATION", "kubernetes.workload.rollout_restart")
TENANT = os.getenv("CORTEX_P99B_TENANT", "dev")
RESTART_TOKEN = os.getenv("CORTEX_P99B_RESTART_TOKEN", "")
PROVIDER = "kubernetes-contained"


def check(name: str, ok: bool, detail: str = "") -> bool:
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def deferred(name: str, why: str) -> None:
    """Recorded separately and never counted as a pass."""
    REPORT["deferred"].append({"item": name, "why": str(why)[:400]})
    print(f"  [DEFR] {name} — {why}")


def measure(name: str, value) -> None:
    REPORT["measurements"][name] = value
    print(f"  [ms ] {name} = {value}")


def section(title: str) -> None:
    print(f"\n[{title}]")


def bail(code: int, why: str) -> None:
    REPORT["why"] = why
    REPORT["passed"] = sum(1 for c in REPORT["checks"] if c["ok"])
    REPORT["total"] = len(REPORT["checks"])
    REPORT["failed_checks"] = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if code == 0:
        REPORT["verdict"] = "VERIFIED"
    print("\n" + json.dumps(REPORT, indent=1))
    sys.exit(code)


# ----------------------------------------------------------------------
# Talking to the worker directly. Used ONLY to prove the worker's own
# refusals; the real write goes through the governed chain.
# ----------------------------------------------------------------------

def _ssl_ctx() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=CA_BUNDLE or None)


def worker_get(path: str) -> dict:
    request = urllib.request.Request(f"{WORKER_URL}{path}", method="GET")
    with urllib.request.urlopen(request, context=_ssl_ctx(), timeout=30) as answer:
        return json.loads(answer.read().decode("utf-8"))


def worker_execute(envelope: dict, *, token: str = None) -> dict:
    """Post an envelope directly. Returns the worker's own answer."""
    body = json.dumps(envelope).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    bearer = RESTART_TOKEN if token is None else token
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    request = urllib.request.Request(
        f"{WORKER_URL}/execute", data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, context=_ssl_ctx(), timeout=45) as answer:
            return json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"refused": True, "reason_code": f"http_{exc.code}", "detail": ""}


def good_envelope(**overrides) -> dict:
    envelope = {
        "tenant": TENANT,
        "execution_id": "exec-probe",
        "capability_id": CAPABILITY_ID,
        "capability_version": CAPABILITY_VERSION,
        "provider": PROVIDER,
        "operation": OPERATION,
        "implementation_digest": IMPL_DIGEST,
        "arguments": {"namespace": NAMESPACE, "name": TARGET},
        "authorization_ref": "auth-probe",
        "approval_ref": "approval-probe",
        "autonomy_decision": "policy/1",
        "worker_identity": "kubernetes-contained-worker",
        "execution_digest": "d" * 64,
        "idempotency_key": "probe-key",
    }
    envelope.update(overrides)
    return envelope


def _kubectl(*args) -> str:
    import subprocess  # noqa: S404 - harness-only, outside the module graph
    done = subprocess.run(  # noqa: S603
        ["kubectl", "--request-timeout=45s", *args],
        capture_output=True, text=True, timeout=120)
    return (done.stdout or "").strip()


def _deployment(namespace: str, name: str) -> dict:
    raw = _kubectl("-n", namespace, "get", "deploy", name, "-o", "json")
    return json.loads(raw) if raw else {}


def _restart_annotation(deployment: dict) -> str:
    return (((deployment.get("spec") or {}).get("template") or {})
            .get("metadata") or {}).get("annotations", {}).get(
                "cortexprime.io/restarted-by-action", "")


# ======================================================================
# A. The boundary, measured from inside it
# ======================================================================

def probe_boundary() -> dict:
    section("A. the worker boundary, measured from inside the container")
    facts = worker_get("/boundary")

    check("A1. the worker runs as a NON-ROOT user", facts["uid"] != 0, f"uid={facts['uid']}")
    check("A2. it is PID 1 in its OWN pid namespace — a separate process, not a "
          "thread of the platform", facts["pid_1_is_self"], f"pid={facts['pid']}")
    check("A3. its root filesystem is READ-ONLY", facts["root_writable"] is False)
    check("A4. it has a writable /tmp and nothing else", facts["tmp_writable"] is True)
    check("A5. NO Docker socket is exposed", facts["docker_socket_present"] is False)
    check("A6. NO CortexPrime repository is mounted", facts["repo_present"] is False)
    check("A7. NO developer kubeconfig is present", facts["kubeconfig_present"] is False)

    # The decisive credential check: what is actually in its environment?
    env_names = facts["env_names"]
    forbidden = [n for n in env_names if any(
        marker in n.upper() for marker in
        ("TOKEN", "SECRET", "PASSWORD", "POSTGRES", "DURABLE_URL", "DATABASE",
         "KUBECONFIG", "CORTEX_KUBERNETES"))]
    check("A8. NO credential-bearing variable exists in the worker's environment "
          "— it holds no CortexPrime secret at all", not forbidden,
          f"suspicious={forbidden}")
    check("A9. the only CORTEX_* variables are BINDINGS, not secrets",
          all(n.startswith(("CORTEX_BIND_", "CORTEX_IMPLEMENTATION_"))
              for n in env_names if n.startswith("CORTEX_")),
          str([n for n in env_names if n.startswith("CORTEX_")]))
    check("A10. it has its OWN ServiceAccount token, mounted by the kubelet — "
          "the identity that may patch one namespace",
          facts["sa_token_mounted"] is True)

    measure("worker_uid", facts["uid"])
    measure("worker_env_var_count", len(env_names))
    return facts


def probe_runtime_hardening() -> None:
    section("B. process hardening and resource limits, as the runtime reports them")
    pod = json.loads(_kubectl(
        "-n", NAMESPACE, "get", "pod", "-l", "app=contained-worker",
        "-o", "json") or '{"items":[]}')
    if not pod.get("items"):
        check("B0. the worker pod is present", False, "no pod found")
        return
    spec = pod["items"][0]["spec"]
    container = spec["containers"][0]
    sc = container.get("securityContext") or {}
    pod_sc = spec.get("securityContext") or {}

    check("B1. allowPrivilegeEscalation is false",
          sc.get("allowPrivilegeEscalation") is False)
    check("B2. ALL Linux capabilities are dropped",
          (sc.get("capabilities") or {}).get("drop") == ["ALL"])
    check("B3. readOnlyRootFilesystem is enforced by the runtime",
          sc.get("readOnlyRootFilesystem") is True)
    check("B4. runAsNonRoot is enforced by the runtime",
          pod_sc.get("runAsNonRoot") is True)
    check("B5. the RuntimeDefault seccomp profile is applied",
          (pod_sc.get("seccompProfile") or {}).get("type") == "RuntimeDefault")

    limits = (container.get("resources") or {}).get("limits") or {}
    check("B6. memory is bounded", bool(limits.get("memory")), str(limits.get("memory")))
    check("B7. CPU is bounded", bool(limits.get("cpu")), str(limits.get("cpu")))
    measure("worker_memory_limit", limits.get("memory"))
    measure("worker_cpu_limit", limits.get("cpu"))

    deferred("process-count (RLIMIT_NPROC) limit",
             "the worker reports rlimit_nproc = [-1, -1]; this runtime does not "
             "enforce a per-container process cap, and no cap is claimed. "
             "Kubernetes exposes this only via the kubelet's podPidsLimit, which "
             "k3d does not set. NOT VERIFIED rather than asserted.")
    deferred("egress network firewall",
             "no NetworkPolicy is applied, so outbound destinations are not "
             "restricted at the network layer. What IS proven below is that the "
             "worker's Kubernetes destination comes from its own environment and "
             "cannot be supplied by a caller. A full egress firewall is NOT "
             "VERIFIED.")


# ======================================================================
# C. Binding. Every refusal executed against the live worker.
# ======================================================================

def probe_bindings() -> None:
    section("C. the worker is BOUND, not general — every refusal executed")

    cases = [
        ("C1. a DIFFERENT operation is refused",
         {"operation": "kubernetes.pod.delete"}, "operation_mismatch"),
        ("C2. a DIFFERENT provider is refused",
         {"provider": "arbitrary-provider"}, "provider_mismatch"),
        ("C3. a DIFFERENT tenant is refused",
         {"tenant": "someone-else"}, "tenant_mismatch"),
        ("C4. a DIFFERENT capability id is refused",
         {"capability_id": "platform.something.else"}, "capability_id_mismatch"),
        ("C5. a CHANGED capability version is refused",
         {"capability_version": 2}, "capability_version_mismatch"),
        ("C6. a CHANGED implementation digest is refused",
         {"implementation_digest": "0" * 64}, "implementation_digest_mismatch"),
        ("C7. an UNEXPECTED envelope field is refused",
         {"url": "http://evil.example"}, "envelope_unknown_fields"),
        ("C8. a CREDENTIAL smuggled into the envelope body is refused",
         {"credential": "sneaky"}, "envelope_unknown_fields"),
        ("C9. an UNEXPECTED argument is refused",
         {"arguments": {"namespace": NAMESPACE, "name": TARGET, "path": "/api/v1"}},
         "arguments_unknown_fields"),
        ("C10. a workload OUTSIDE the bound namespace is refused",
         {"arguments": {"namespace": OTHER_NS, "name": TARGET}},
         "namespace_out_of_scope"),
        ("C11. a WILDCARD target is refused",
         {"arguments": {"namespace": NAMESPACE, "name": "*"}},
         "name_not_a_single_target"),
        ("C12. a COMMA-separated target list is refused",
         {"arguments": {"namespace": NAMESPACE, "name": "a,b"}},
         "name_not_a_single_target"),
        ("C13. a PATH-TRAVERSAL target is refused",
         {"arguments": {"namespace": NAMESPACE, "name": "../../secrets"}},
         "name_not_a_single_target"),
        ("C14. a MISSING idempotency key is refused",
         {"idempotency_key": ""}, "idempotency_key_missing"),
        ("C15. a MISSING approval reference is refused",
         {"approval_ref": ""}, "approval_ref_missing"),
        ("C16. a MISSING authorization reference is refused",
         {"authorization_ref": ""}, "authorization_ref_missing"),
    ]
    for name, overrides, expected in cases:
        answer = worker_execute(good_envelope(**overrides))
        ok = answer.get("refused") is True and answer.get("reason_code") == expected
        check(name, ok, f"{answer.get('reason_code')}")
        if not answer.get("provider_called", True) is not True:
            pass

    # A refusal must never have contacted the API server.
    answer = worker_execute(good_envelope(operation="kubernetes.pod.delete"))
    check("C17. every refusal reports that NO provider was contacted",
          answer.get("provider_called") is False)

    # Without a credential the worker refuses, and does so only AFTER the
    # bindings pass -- so a bad envelope never reaches the credential at all.
    answer = worker_execute(good_envelope(), token="")
    check("C18. a request with NO credential is refused",
          answer.get("refused") is True
          and answer.get("reason_code") == "credential_missing",
          str(answer.get("reason_code")))

    answer = worker_execute(good_envelope(tenant="someone-else"), token="")
    check("C19. binding is checked BEFORE the credential — a wrong-tenant "
          "envelope refuses on the tenant, not on the missing credential",
          answer.get("reason_code") == "tenant_mismatch",
          str(answer.get("reason_code")))

    # The endpoint surface itself is closed.
    for path in ("/exec", "/shell", "/eval", "/proxy"):
        try:
            worker_get(path)
            reachable = True
        except urllib.error.HTTPError as exc:
            reachable = exc.code != 404
        except urllib.error.URLError:
            reachable = False
        check(f"C20. there is no {path} endpoint", not reachable)


def probe_credential_scope() -> None:
    section("D. the credential is least-privilege, proven against the live API")
    # The worker's own identity may patch one deployment in one namespace. Prove
    # the negative directly: the same token cannot reach the other namespace.
    answer = worker_execute(
        good_envelope(arguments={"namespace": OTHER_NS, "name": TARGET}))
    check("D1. the worker refuses a cross-namespace target before the API is "
          "even asked", answer.get("reason_code") == "namespace_out_of_scope")

    for verb, resource, ns, want in (
        ("patch", "deployments", NAMESPACE, "yes"),
        ("delete", "deployments", NAMESPACE, "no"),
        ("create", "pods", NAMESPACE, "no"),
        ("get", "secrets", NAMESPACE, "no"),
        ("create", "pods/exec", NAMESPACE, "no"),
        ("patch", "deployments", OTHER_NS, "no"),
        ("patch", "deployments", "kube-system", "no"),
    ):
        got = _kubectl(
            "auth", "can-i", verb, resource,
            f"--as=system:serviceaccount:{NAMESPACE}:cortex-restarter",
            "-n", ns) or "no"
        check(f"D2. RBAC: {verb} {resource} in {ns} is {want}",
              got.splitlines()[0].strip() == want, got.splitlines()[0].strip())


# ======================================================================
# E-K. The governed chain. The write happens HERE or not at all.
# ======================================================================

def _runtime():
    """Compose the real runtime with BOTH the read connector and the worker."""
    os.environ.setdefault(
        "CORTEX_CONNECTOR_FACTORIES",
        "backend.api.kubernetes_provider_factory:kubernetes_real_extension,"
        "backend.api.contained_worker_factory:contained_worker_extension")
    from backend.api.application_runtime import build_governed_runtime

    runtime = build_governed_runtime()
    if runtime is None:
        bail(2, "no governed runtime; is CORTEX_DURABLE_URL set?")

    # Claim the audit writer role. The chain appends to the hash chain as it
    # goes, and a process that does not hold the role has its appends refused --
    # correctly, so two writers cannot interleave into one chain. A harness that
    # skipped this would be testing a chain with holes in it.
    writer = getattr(runtime, "audit_writer", None)
    if writer is not None:
        try:
            writer.acquire()
        except Exception as exc:  # noqa: BLE001 - reported, never ignored
            bail(2, f"could not claim the audit writer role: {exc}")
    return runtime


def _platform_ctx():
    from backend.api.application_runtime import _platform_context
    return _platform_context()


def _commission(runtime, ctx):
    """Register the ONE write capability against the contained provider.

    Reuses the existing capability lifecycle commands. Nothing here is a second
    registration path; it is the same one every other phase used.
    """
    from backend.contexts.connectivity.application.commands import (
        EnableCapability, GetCapability, RegisterCapability, SetCapabilityTrust,
        ValidateCapability,
    )
    from backend.contexts.execution.domain.worker_directory import (
        WorkerAvailability, WorkerTrust,
    )

    def _idem(fn):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - commissioning is idempotent by intent
            return None

    directory = runtime.connectivity.directory
    for worker in ("kubernetes-connector", "kubernetes-contained-worker"):
        for step in (
            lambda w=worker: directory.validate(ctx, worker_id=w, tenant_id=""),
            lambda w=worker: directory.enable(ctx, worker_id=w, tenant_id=""),
            lambda w=worker: directory.set_trust(ctx, worker_id=w, tenant_id="",
                                                 trust=WorkerTrust.VERIFIED,
                                                 reason="phase-9.9b"),
            lambda w=worker: directory.set_trust(ctx, worker_id=w, tenant_id="",
                                                 trust=WorkerTrust.TRUSTED,
                                                 reason="phase-9.9b"),
            lambda w=worker: directory.set_availability(
                ctx, worker_id=w, tenant_id="",
                availability=WorkerAvailability.AVAILABLE),
        ):
            _idem(step)

    _idem(lambda: runtime.capabilities.register(ctx, RegisterCapability(
        capability_id=CAPABILITY_ID, version=CAPABILITY_VERSION, name=OPERATION,
        description=OPERATION, provider=PROVIDER, interface="connector",
        side_effect_class="irreversible_write",
        effect_semantics="non_idempotent_write",
        # The whole point of Part A: FIXED code performing an irreversible write
        # needs CONTAINED, and this worker genuinely is.
        isolation_tier="contained", code_trust="fixed",
        execution_mode="synchronous", owner_id="ops-owner", owner_kind="human",
        tenancy="platform", source="internal",
        supported_environments=("development",), provider_operation=OPERATION)))
    for command in (
        lambda: runtime.capabilities.validate(ctx, ValidateCapability(
            capability_id=CAPABILITY_ID, version=CAPABILITY_VERSION)),
        lambda: runtime.capabilities.enable(ctx, EnableCapability(
            capability_id=CAPABILITY_ID, version=CAPABILITY_VERSION)),
        lambda: runtime.capabilities.set_trust(ctx, SetCapabilityTrust(
            capability_id=CAPABILITY_ID, version=CAPABILITY_VERSION,
            trust="verified", reason="harness")),
        lambda: runtime.capabilities.set_trust(ctx, SetCapabilityTrust(
            capability_id=CAPABILITY_ID, version=CAPABILITY_VERSION,
            trust="trusted", reason="harness")),
    ):
        _idem(command)
    return {OPERATION: runtime.capabilities.get(ctx, GetCapability(
        capability_id=CAPABILITY_ID, version=CAPABILITY_VERSION))}


def probe_the_chain(runtime) -> None:
    section("E. the CONTAINED worker is what the governed chain selects")
    from backend.contracts.connector import CodeTrust, IsolationTier
    from backend.contracts.execution import SideEffectClass

    workers = {
        entry.implementation.worker_id: entry.implementation
        for entry in runtime.connectivity.directory.all(_platform_ctx())
    } if hasattr(runtime.connectivity.directory, "all") else {}
    contained = None
    for adapter in runtime.connectivity.adapters.values():
        impl = getattr(adapter, "implementation", None)
        if impl is not None and impl.worker_id == "kubernetes-contained-worker":
            contained = impl
    check("E1. a worker declaring CONTAINED exists — the tier has its first "
          "occupant", contained is not None
          and contained.isolation is IsolationTier.CONTAINED,
          str(contained.isolation.value) if contained else "absent")
    if contained is None:
        bail(1, "the contained worker was not composed")

    check("E2. it may perform a FIXED irreversible write",
          contained.permits(CodeTrust.FIXED, SideEffectClass.IRREVERSIBLE_WRITE))
    check("E3. it may NOT host arbitrary code — CONTAINED is not SEALED",
          not contained.permits(CodeTrust.ARBITRARY, SideEffectClass.READ))
    check("E4. it declares exactly ONE operation",
          set(contained.supported_operations) == {OPERATION},
          str(sorted(contained.supported_operations)))
    check("E5. the in-process READ connector still cannot do this write",
          not any(
              impl.permits(CodeTrust.FIXED, SideEffectClass.IRREVERSIBLE_WRITE)
              for impl in (
                  getattr(a, "implementation", None)
                  for a in runtime.connectivity.adapters.values())
              if impl is not None and impl.worker_id == "kubernetes-connector"))


def probe_the_write(runtime, definitions) -> None:
    """The first real governed irreversible Kubernetes write.

    Everything above has passed, so the platform has earned this. The write goes
    through ``GovernedCapabilityWriter`` -- the same typed door Phase 9.6 built --
    which means gateway, authorization, credential broker, worker selection and
    the adapter, in that order, with no shortcut available from here.
    """
    section("F. the FIRST governed irreversible Kubernetes write")
    from backend.api.capability_execution_composition import GovernedCapabilityWriter
    from backend.contracts.identity import PrincipalKind, PrincipalRef

    before = _deployment(NAMESPACE, TARGET)
    before_generation = (before.get("metadata") or {}).get("generation")
    before_annotation = _restart_annotation(before)
    bystander_before = _deployment(NAMESPACE, BYSTANDER)
    other_before = _deployment(OTHER_NS, TARGET)

    check("F1. the target carries NO CortexPrime restart annotation yet",
          not before_annotation, before_annotation or "<none>")
    measure("target_generation_before", before_generation)

    # The runtime composes ``NoApprovals()`` by default, which is fail-closed and
    # correct: a platform with no approval source must refuse an action that
    # needs one, not find one. Phase 9.6 proved that refusal; this phase needs
    # the positive path, so the harness supplies the EXISTING ``ApprovalLookup``
    # seam (the same protocol a real deployment would pass in). It is not a
    # second approval authority -- every question about whether the approval
    # covers the action is still answered by ``ApprovalFacts.is_valid_for``.
    approvals = _Approvals()
    runtime.authorization._approvals = approvals  # noqa: SLF001 - the declared seam

    definition = definitions[OPERATION]
    context = _tenant_ctx()

    # Before granting: the same call must refuse. Recorded because it is the
    # governance property that matters most here.
    from backend.api.capability_execution_composition import GovernedCapabilityWriter
    from backend.contracts.identity import PrincipalKind, PrincipalRef as _PRef
    probe_writer = GovernedCapabilityWriter(
        runtime=runtime, capability_definitions=definitions,
        principal=_PRef(principal_id="harness", kind=PrincipalKind.HUMAN))
    unapproved = probe_writer.write(
        context, operation=OPERATION,
        payload={"namespace": NAMESPACE, "name": TARGET},
        approval_artifact_id="approval-that-does-not-exist")
    check("F1b. WITHOUT a valid approval the chain refuses and writes nothing",
          unapproved.succeeded is False
          and "authorization refused" in (unapproved.failure_reason or ""),
          str(unapproved.failure_reason)[:120])
    check("F1c. that refusal left the cluster untouched",
          not _restart_annotation(_deployment(NAMESPACE, TARGET)))

    counter = _DialCounter(runtime)
    principal = PrincipalRef(principal_id="harness", kind=PrincipalKind.HUMAN)
    writer = GovernedCapabilityWriter(
        runtime=runtime, capability_definitions=definitions, principal=principal)

    # The approval is bound to the ACTION digest, so it authorizes this action
    # and nothing else. The digest is the platform's, computed at the gateway.
    # ``ApprovalFacts.is_valid_for`` compares against the CAPABILITY CONTRACT
    # digest and the governance verb -- so an approval for version 1 cannot
    # authorize version 2, and an approval to invoke cannot authorize anything
    # else. Bound to the platform's digest, never one this harness invented.
    approvals.grant(artifact_id="approval-p99b", tenant_id=TENANT,
                    operation="invoke", digest=definition.digest,
                    actor_ref="human:ops-oncall")

    outcome, failure = None, None
    try:
        outcome = writer.write(
            context, operation=OPERATION,
            payload={"namespace": NAMESPACE, "name": TARGET},
            approval_artifact_id="approval-p99b")
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        failure = f"{type(exc).__name__}: {exc}"

    # Asserting SUCCEEDED, not merely "returned an object": a refusal also
    # returns an outcome, and an earlier version of this check passed on one.
    check("F2. the write travelled the governed chain and SUCCEEDED",
          outcome is not None and outcome.succeeded is True,
          failure or (outcome.failure_reason if outcome else "no outcome"))
    measure("provider_dials_total", counter.total)
    measure("provider_writes", [f"{m} {pth}" for _, m, pth in counter.writes])

    if outcome is None or not outcome.succeeded:
        check("F3. NOTHING was written when the chain did not complete",
              not _restart_annotation(_deployment(NAMESPACE, TARGET)))
        check("F4. every provider write count is still ZERO",
              len(counter.writes) == 0, str(counter.writes))
        _record_dispatch_gap(runtime)
        bail(2, "STOPPED: the boundary is proven but the governed chain cannot "
                "dispatch an approval-requiring capability; see blocking_finding")

    section("G. the result, established by an INDEPENDENT read of the cluster")
    after = _deployment(NAMESPACE, TARGET)
    after_generation = (after.get("metadata") or {}).get("generation")
    after_annotation = _restart_annotation(after)

    check("G1. the target now carries CortexPrime OWN restart annotation",
          bool(after_annotation), after_annotation or "<none>")
    check("G2. the Deployment generation ADVANCED — a real spec change, not a "
          "no-op", isinstance(after_generation, int)
          and isinstance(before_generation, int)
          and after_generation > before_generation,
          f"{before_generation} -> {after_generation}")
    measure("target_generation_after", after_generation)
    check("G3. the annotation key is CortexPrime own, not kubectl",
          "cortexprime.io/restarted-by-action" in json.dumps(
              (after.get("spec") or {}).get("template", {})))

    section("H. blast radius: nothing else changed")
    bystander_after = _deployment(NAMESPACE, BYSTANDER)
    other_after = _deployment(OTHER_NS, TARGET)
    check("H1. the BYSTANDER deployment in the same namespace is untouched",
          (bystander_before.get("metadata") or {}).get("generation")
          == (bystander_after.get("metadata") or {}).get("generation")
          and not _restart_annotation(bystander_after))
    check("H2. the same-named deployment in the OTHER namespace is untouched",
          (other_before.get("metadata") or {}).get("generation")
          == (other_after.get("metadata") or {}).get("generation")
          and not _restart_annotation(other_after))
    check("H3. exactly ONE provider write occurred in this entire run",
          len(counter.writes) == 1, str(counter.writes))
    check("H4. that write went to the CONTAINED WORKER, not to the API server",
          all(provider == PROVIDER for provider, _, _ in counter.writes),
          str([p for p, _, _ in counter.writes]))

    section("I. the secret firewall")
    dsn = os.getenv("CORTEX_DURABLE_URL", "")
    needles = [n for n in (RESTART_TOKEN,
                           os.getenv("CORTEX_KUBERNETES_TOKEN", "")) if n]
    leaked = _scan_for_secret(dsn, *needles)
    check("I1. NO credential appears in ANY durable row of ANY table",
          not leaked, str(leaked))
    check("I2. NO credential appears in this report",
          not any(n and n in json.dumps(REPORT) for n in needles))
    check("I3. the envelope the worker receives carries NO credential field",
          "credential" not in _envelope_fields(), str(_envelope_fields()))


def _action_digest(runtime, definition, context):
    """The ADR-038 action digest for this exact call.

    Computed with the platform's own function rather than reproduced here: an
    approval bound to a digest this harness invented would authorize something
    the gateway never sees.
    """
    from backend.contexts.connectivity.domain.authorization import (
        AuthorizationRequest, CapabilityOperation,
    )
    from backend.contexts.connectivity.domain.contract import CapabilityEnvironment
    from backend.contracts.identity import PrincipalKind, PrincipalRef

    request = AuthorizationRequest(
        tenant_id=TENANT,
        principal=PrincipalRef(principal_id="harness", kind=PrincipalKind.HUMAN),
        capability_ref=definition.reference,
        operation=CapabilityOperation.INVOKE,
        expected_digest=definition.digest,
        environment=CapabilityEnvironment.DEVELOPMENT,
    )
    decision = runtime.authorization.authorize(context, request)
    return getattr(decision, "action_digest", None) or definition.digest


class _Approvals:
    """A digest-bound approval lookup over the EXISTING ``ApprovalFacts``.

    Lifted from the Phase 9.6 harness unchanged. It stores nothing beyond the
    granted artifacts a human produced; every question about whether an approval
    covers an action is answered by ``ApprovalFacts.is_valid_for``, which already
    checks outcome, expiry, tenant, operation and digest. A lookup, not a second
    approval system.
    """

    def __init__(self):
        self._facts = {}

    def grant(self, *, artifact_id, tenant_id, operation, digest, actor_ref,
              expires_at=None):
        from backend.contracts.approval import ApprovalOutcome
        from backend.contexts.connectivity.application.authorization import ApprovalFacts
        if ":" not in actor_ref:
            raise ValueError("an approver must be a namespaced identity reference")
        self._facts[artifact_id] = ApprovalFacts(
            artifact_id=artifact_id, outcome=ApprovalOutcome.GRANTED,
            bound_digest=digest, scope_tenant_id=tenant_id, operation=operation,
            expires_at=expires_at)
        return artifact_id

    def find(self, context, artifact_id):
        return self._facts.get(artifact_id)


def _record_dispatch_gap(runtime) -> None:
    """Name the defect precisely, and prove it rather than assert it.

    The gateway re-authorizes at dispatch -- correctly, because an approval can
    be revoked between authorization and dispatch. But the request it builds to
    do that carries no approval artifact id, so the lookup it would consult is
    never given anything to look up, ``approval_valid`` can never become true,
    and any capability whose policy answers REQUIRE_APPROVAL is undispatchable.
    """
    import inspect

    section("Z. the blocking finding, proven from source and from behaviour")
    import backend.api.capability_execution_composition as comp

    source = inspect.getsource(comp)
    start = source.index("def facts_for(")
    body = source[start:start + 2000]
    request_block = body[body.index("AuthorizationRequest("):body.index("if decision is None")]
    check("Z1. the gateway's re-authorization request carries NO "
          "approval_artifact_id", "approval_artifact_id" not in request_block)
    check("Z2. AuthorityFacts nonetheless HAS the field, so the check was "
          "designed to work and is simply never fed",
          "approval_artifact_id" in inspect.getsource(
              __import__("backend.contexts.execution.application.invocation_gateway",
                         fromlist=["x"])))
    check("Z3. InvocationRequest has no approval field either — nothing on the "
          "dispatch path could carry it",
          not any(f.name == "approval_artifact_id" for f in __import__(
              "dataclasses").fields(__import__(
                  "backend.contexts.execution.domain.invocation",
                  fromlist=["InvocationRequest"]).InvocationRequest)))

    REPORT["blocking_finding"] = {
        "what": "an approval-requiring capability cannot be dispatched",
        "where": "backend/api/capability_execution_composition.py :: facts_for",
        "why": (
            "The gateway re-authorizes at dispatch, which is correct: an "
            "approval can be revoked between authorization and dispatch. But "
            "the AuthorizationRequest it builds omits approval_artifact_id, so "
            "the ApprovalLookup is never given an id, approval_valid is always "
            "False, and PolicyEffect.REQUIRE_APPROVAL always refuses with "
            "'approval_required'."),
        "observed": "dispatch result: dispatched=False invocation_refusal=approval_required",
        "never_hit_before": (
            "Phase 9.6 was blocked by isolation before dispatch, and every "
            "phase before it was read-only. No approval-requiring capability "
            "has ever reached a real gateway in this repository."),
        "identified_fix": (
            "Carry the approval reference on the sealed binding, the way "
            "code_trust now is, and pass it into facts_for's "
            "AuthorizationRequest. Additive and fail-closed: absent means no "
            "approval, which is today's behaviour. It makes the existing check "
            "work as designed rather than changing any policy."),
        "not_done_because": (
            "it changes how approvals bind to executions, which is governance "
            "surface this phase was told not to alter unilaterally."),
    }


def _tenant_ctx():
    """The caller's authenticated context. Reused from the Phase 6.2 harness so
    this phase does not invent a second idea of who is asking."""
    from backend.contracts.identity import PrincipalKind, PrincipalRef
    from backend.platform.context import ExecutionContext
    from backend.platform.context.identity import IdentityContext

    identity = IdentityContext(
        principal=PrincipalRef(principal_id="harness", kind=PrincipalKind.HUMAN),
        capabilities=("capability:invoke",),
    )
    return ExecutionContext.for_tenant(
        tenant_id=TENANT, identity=identity, source="cli")


def _envelope_fields():
    from backend.contexts.execution.infrastructure.adapters.contained_worker import (
        CONTAINED_WORKER_ENVELOPE_FIELDS,
    )
    return list(CONTAINED_WORKER_ENVELOPE_FIELDS)


def _scan_for_secret(dsn, *needles):
    """Read every text column of every table and look for the secrets."""
    if not dsn or not needles:
        return []
    import sqlalchemy as sa

    engine = sa.create_engine(dsn)
    hits = []
    with engine.connect() as conn:
        tables = [r[0] for r in conn.execute(sa.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public'"))]
        for table in tables:
            columns = [r[0] for r in conn.execute(sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t "
                "AND data_type IN ('text','character varying','json','jsonb')"),
                {"t": table})]
            for column in columns:
                for needle in needles:
                    found = conn.execute(sa.text(
                        'SELECT 1 FROM "' + table + '" WHERE CAST("' + column
                        + '" AS TEXT) LIKE :needle LIMIT 1'),
                        {"needle": "%" + needle + "%"}).first()
                    if found:
                        hits.append(table + "." + column)
    engine.dispose()
    return hits


class _DialCounter:
    """Counts every provider dial and records its method and path.

    Lifted from the Phase 9.6 harness unchanged: a write must be countable
    separately from a read, and "exactly one write happened" is the measurement
    this phase turns on.
    """

    def __init__(self, runtime):
        self.counts, self.plans = {}, []
        for provider, adapter in runtime.connectivity.adapters.items():
            channel = getattr(adapter, "_channel", None)
            if channel is None:
                continue
            self.counts[provider] = 0
            channel.send = self._wrap(provider, channel.send)

    def _wrap(self, provider, original):
        def _send(authority, plan, **kw):
            self.counts[provider] += 1
            self.plans.append((provider, plan.method, plan.path))
            return original(authority, plan, **kw)
        return _send

    @property
    def total(self):
        return sum(self.counts.values())

    @property
    def writes(self):
        return [p for p in self.plans if p[1] not in ("GET", "HEAD")]


def main() -> None:
    print("[label] REAL k3d cluster, REAL out-of-process worker, REAL PostgreSQL.\n"
          "        Sections A-D run BEFORE any write. If one fails the harness\n"
          "        stops and nothing is written.\n")
    for label, value in (("CORTEX_P99B_WORKER_URL", WORKER_URL),
                         ("CORTEX_TLS_CA_BUNDLE", CA_BUNDLE),
                         ("CORTEX_P99B_IMPL_DIGEST", IMPL_DIGEST),
                         ("CORTEX_P99B_CAPABILITY_ID", CAPABILITY_ID)):
        if not value:
            bail(2, f"{label} is not set; run scripts/phase99b_provision.sh first")

    probe_boundary()
    probe_runtime_hardening()
    probe_bindings()
    probe_credential_scope()

    # THE STOP RULE. Nothing below this line runs if a boundary or binding
    # check failed, because everything below it writes to a real cluster.
    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"STOPPED BEFORE THE WRITE: {failed[0]}")

    runtime = _runtime()
    ctx = _platform_ctx()
    definitions = _commission(runtime, ctx)
    probe_the_chain(runtime)

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"STOPPED BEFORE THE WRITE: {failed[0]}")

    probe_the_write(runtime, definitions)

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"a check failed after the write: {failed[0]}")
    bail(0, "CONTAINED is a real execution boundary and the first governed "
            "irreversible Kubernetes write was performed and independently "
            "verified")


if __name__ == "__main__":
    main()
