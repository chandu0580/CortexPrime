"""Connection scope: a capability may only target what its tenant is connected to.

Phase 11.1-K. A connection binds one CortexPrime tenant to one provider target
(for Kubernetes: a cluster namespace). This module enforces the platform half of
that binding at the gateway's input stage -- before any credential is minted --
by wrapping the input validator the gateway already calls: a payload whose
target parameter names anything outside the invoking tenant's connection is an
input problem, and the gateway refuses it as ``INPUT_INVALID``.

Why the input stage: the binding the gateway validates carries the tenant the
authorization was decided for, and the payload the action digest will cover.
Refusing here means a cross-tenant target never reaches credential acquisition,
never reaches a worker and never reaches the provider. The provider-side half --
a credential minted for the tenant from a namespace-confined ServiceAccount -- is
independent, so either layer alone refuses a cross-tenant target.

Generic: a scope names providers and the input parameter(s) that identify the
target; nothing here knows what a namespace or a repository is.

Phase 11.2 added composite targets, because GitHub identifies one with two
parameters (``owner`` and ``repo``) where Kubernetes uses one. Two properties
are security-relevant and deliberate:

* **A partially named target is refused, never ignored.** A payload carrying
  ``repo`` but no ``owner`` does not fall through as "this operation has no
  target"; it is an input problem, because ``repo`` alone does not identify a
  repository and two owners may use the same name.
* **Comparison is case-insensitive.** GitHub treats ``Owner/Repo`` and
  ``owner/repo`` as the same repository, so a case-sensitive check would let
  ``ChanDu0580/CortexPrime`` walk past a connection naming
  ``chandu0580/cortexprime``. Kubernetes names are already lower-case, so this
  costs that connector nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Tuple

from backend.contracts.errors import ContractViolation

__all__ = ["ConnectionScope", "ConnectionScopes", "ConnectionScopeValidator"]


@dataclass(frozen=True)
class ConnectionScope:
    tenant_id: str
    providers: frozenset
    targets: frozenset
    target_parameter: str = "namespace"
    #: Several parameters that together identify one target, joined with "/"
    #: (GitHub: ``("owner", "repo")``). Empty means the single parameter above.
    target_parameters: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.providers or not self.targets:
            raise ContractViolation("a connection scope names a tenant, providers and targets")
        if self.target_parameters and len(set(self.target_parameters)) != len(self.target_parameters):
            raise ContractViolation("a composite target names each parameter once")

    @property
    def parameters(self) -> Tuple[str, ...]:
        return self.target_parameters or (self.target_parameter,)

    @property
    def label(self) -> str:
        return "/".join(self.parameters)

    def permits(self, target: str) -> bool:
        return target.casefold() in {t.casefold() for t in self.targets}


@dataclass
class ConnectionScopes:
    scopes: list = field(default_factory=list)

    def add(self, scope: ConnectionScope) -> None:
        self.scopes.append(scope)

    def extend(self, scopes: Iterable[ConnectionScope]) -> None:
        for scope in scopes:
            self.add(scope)

    @property
    def providers(self) -> frozenset:
        return frozenset(p for s in self.scopes for p in s.providers)

    def for_tenant(self, tenant_id: str, provider: str) -> Optional[ConnectionScope]:
        for scope in self.scopes:
            if scope.tenant_id == tenant_id and provider in scope.providers:
                return scope
        return None

    def to_dict(self) -> list:
        return [{"tenant_id": s.tenant_id, "providers": sorted(s.providers),
                 "targets": sorted(s.targets), "target_parameter": s.label}
                for s in self.scopes]


class ConnectionScopeValidator:
    """Wraps the gateway's input validator; adds the connection-scope problems."""

    def __init__(self, inner: Any, scopes: ConnectionScopes) -> None:
        self._inner = inner
        self._scopes = scopes

    def validate(self, binding: Any, payload: Mapping[str, Any]) -> Tuple[str, ...]:
        problems = list(self._inner.validate(binding, payload))
        provider = str(getattr(binding, "provider", "") or "")
        if provider not in self._scopes.providers:
            return tuple(problems)
        tenant = str(getattr(binding, "tenant_id", "") or "")
        scope = self._scopes.for_tenant(tenant, provider)
        if scope is None:
            problems.append(
                f"this tenant has no connection for {provider}; a capability of a connector "
                "the tenant is not connected to cannot target anything")
            return tuple(problems)
        values = [(payload or {}).get(name) for name in scope.parameters]
        if all(value is None for value in values):
            # This operation names no target at all (a whole-connection read).
            return tuple(problems)
        if any(value is None for value in values):
            missing = [n for n, v in zip(scope.parameters, values) if v is None]
            problems.append(
                f"{', '.join(missing)} must be given: part of a {scope.label} does not identify "
                f"a target, and an unscoped {provider} call cannot be authorized")
            return tuple(problems)
        target = "/".join(str(value) for value in values)
        if not scope.permits(target):
            problems.append(
                f"{scope.label} {target[:96]!r} is outside this tenant's "
                f"{provider} connection")
        return tuple(problems)

    # The gateway reads nothing else, but a caller inspecting the validator
    # (the capability-bridge, a test) sees the inner one's catalogs.
    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
