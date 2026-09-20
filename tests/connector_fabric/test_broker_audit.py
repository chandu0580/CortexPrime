"""Phase 11.1-K: the brokers' audit facts reach a REAL audit chain.

Found by the installed product: ``TransportBroker`` and ``CredentialBroker``
called ``AuditRuntime.record(kind, **fields)`` without the positional tenant
scope. Every call raised ``TypeError``, each broker's "audit failure never
turns a refusal into an allow" guard swallowed it, and the durable audit chain
of a deployed runtime stayed EMPTY. No test had wired either broker to a real
``AuditRuntime``; these do.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.contracts.audit import AuditEventKind
from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.platform.audit import AuditRuntime
from backend.platform.audit.store import InMemoryAuditStore
from backend.platform.transport.broker import TransportBroker
from backend.platform.transport.endpoint import TransportEndpoint, TransportKind
from backend.platform.transport.policy import ConnectionPolicy
from backend.platform.transport.request import TransportRefused, TransportRequest

PRINCIPAL = PrincipalRef(principal_id="connector-health", kind=PrincipalKind.PLATFORM)


def _chain():
    store = InMemoryAuditStore()
    return AuditRuntime(store), store


def test_a_refused_dial_is_recorded_in_the_tenants_scope():
    audit, store = _chain()
    broker = TransportBroker(audit=audit)
    endpoint = TransportEndpoint.parse("https://no-such-host.invalid/healthz", transport=TransportKind.HTTPS,
                                       environment=ExecutionEnvironment.PRODUCTION)
    with pytest.raises(TransportRefused):
        broker.dial(TransportRequest(
            endpoint=endpoint, policy=ConnectionPolicy(environment=ExecutionEnvironment.PRODUCTION),
            tenant_id="tenant-a", principal=PRINCIPAL, method="GET", authority_seconds_remaining=10.0))
    records = list(store.read_all())
    assert records, "the refusal left no audit fact"
    record = records[-1]
    assert record.kind is AuditEventKind.EXECUTION_REFUSED
    assert record.scope.tenant.tenant_id == "tenant-a"
    assert record.actor == PRINCIPAL


def test_a_credential_fact_is_recorded_in_the_tenants_scope():
    from backend.platform.credentials.broker import CredentialBroker

    audit, store = _chain()
    broker = CredentialBroker(audit=audit)
    request = SimpleNamespace(tenant_id="tenant-b", principal=PRINCIPAL)
    broker._safe_audit(AuditEventKind.EXECUTION_REFUSED, request, subject_reference="cap@1",
                       detail={"issued": False})
    (record,) = list(store.read_all())
    assert record.scope.tenant.tenant_id == "tenant-b"
    assert record.actor == PRINCIPAL


def test_audit_failure_still_never_raises(caplog):
    class Broken:
        def record(self, *args, **kwargs):
            raise RuntimeError("store unavailable")

    broker = TransportBroker(audit=Broken())
    broker._safe_audit(AuditEventKind.EXECUTION_REFUSED, SimpleNamespace(tenant_id="t", principal=PRINCIPAL))
    assert "RuntimeError: store unavailable" in caplog.text
