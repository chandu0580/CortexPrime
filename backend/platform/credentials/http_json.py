"""One JSON request over the transport broker, for credential acquisition.

Phase 11.2. The Vault Kubernetes adapter (11.1-K) already made exactly this
call -- dial through the broker, refuse anything that is not a readable answer,
turn the body into a document -- and the GitHub App adapter needs the same
against a different provider. This is that call, with the provider's name and
headers as parameters instead of baked in.

Deliberately small. It does not retry, does not follow redirects, does not
interpret status codes beyond "the answer arrived", and does not know what a
token is: the caller judges the status, because what a 403 means is the
provider's semantics, not the transport's. Standard library only, like the rest
of ``backend/platform``.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping, Optional, Tuple

from backend.platform.credentials.material import CredentialMaterial
from backend.platform.credentials.request import CredentialRefusal, CredentialRefused
from backend.platform.credentials.redaction import safe_exception_text

__all__ = ["json_call"]

log = logging.getLogger(__name__)


def json_call(broker: Any, endpoint: Any, policy: Any, *, method: str, path: str,
              tenant_id: str, principal: Any, seconds: float,
              body: Optional[Mapping[str, Any]] = None,
              credential: Optional[CredentialMaterial] = None,
              headers: Optional[Mapping[str, str]] = None,
              correlation_id: Optional[str] = None,
              provider_label: str = "the provider") -> Tuple[Optional[int], Any]:
    """``(status, document)`` from one JSON request; raises ``CredentialRefused``
    when no answer arrived at all. ``document`` is ``{}`` when the body is absent,
    truncated or not JSON -- the status still tells the caller what happened."""
    from dataclasses import replace

    from backend.platform.transport.request import (
        DeliveryState,
        TransportRefused,
        TransportRequest,
    )

    request_headers = {"content-type": "application/json"}
    request_headers.update({str(k).lower(): str(v) for k, v in (headers or {}).items()})
    try:
        request = TransportRequest(
            endpoint=replace(endpoint, path=path, query=""), policy=policy,
            tenant_id=tenant_id, principal=principal, method=method,
            headers=request_headers,
            body=json.dumps(dict(body)).encode("utf-8") if body is not None else None,
            correlation_id=correlation_id, authority_seconds_remaining=max(1.0, seconds),
            credential=credential)
        outcome = broker.dial(request)
    except TransportRefused as refused:
        raise CredentialRefused(CredentialRefusal.PROVIDER_UNAVAILABLE,
                                f"{provider_label} could not be reached ({refused.reason_code})",
                                correlation_id=correlation_id) from refused
    except CredentialRefused:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("%s call failed: %s", provider_label, safe_exception_text(exc))
        raise CredentialRefused(CredentialRefusal.PROVIDER_UNAVAILABLE,
                                f"{provider_label} could not be reached ({type(exc).__name__})",
                                correlation_id=correlation_id) from exc
    if outcome.delivery is not DeliveryState.DELIVERED:
        raise CredentialRefused(CredentialRefusal.PROVIDER_UNAVAILABLE,
                                f"the request to {provider_label} did not complete",
                                correlation_id=correlation_id)
    document: Any = {}
    if outcome.body and not outcome.truncated:
        try:
            document = json.loads(outcome.body.decode("utf-8"))
        except Exception:  # noqa: BLE001 - judged by status by the caller
            document = {}
    return outcome.status_code, document
