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

Generic: a scope names providers and a target parameter; nothing here knows what
a namespace is.
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

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.providers or not self.targets:
            raise ContractViolation("a connection scope names a tenant, providers and targets")


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
                 "targets": sorted(s.targets), "target_parameter": s.target_parameter}
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
        target = (payload or {}).get(scope.target_parameter)
        if target is not None and str(target) not in scope.targets:
            problems.append(
                f"{scope.target_parameter} {str(target)[:63]!r} is outside this tenant's "
                f"{provider} connection")
        return tuple(problems)

    # The gateway reads nothing else, but a caller inspecting the validator
    # (the capability-bridge, a test) sees the inner one's catalogs.
    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
