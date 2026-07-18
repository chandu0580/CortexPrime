from __future__ import annotations

import inspect
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

# Legacy — use base_connector.py for new connectors.
from backend.connectors.activity_service import ConnectorActivityService
from backend.connectors.base_connector import (
    CircuitBreaker,
    PaginatedResponse,
    TokenManager,
)
from backend.services.credential_service import CredentialService

log = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Abstract base connector with automatic activity recording.

    Subclasses define ``connector_name`` and ``connector_type`` as class
    attributes and implement domain methods that call ``self._execute()``
    to automatically record activity, audit logs, and event bus events.

    Every subclass automatically exposes its planner-visible capabilities
    via ``get_operations()``.  Private methods (starting with ``_``) and
    lifecycle methods (``initialize``, ``shutdown``, ``health``, ``configure``)
    are never exposed.  Connectors may set ``_operation_metadata`` to enrich
    the auto-discovered descriptions.
    """

    connector_name: str = ""
    connector_type: str = ""

    # Optional override — subclass can set this to provide richer descriptions.
    # Keyed by operation name, values are dicts with optional keys:
    #   "description"       — human-readable description
    #   "return_description" — description of the return value
    _operation_metadata: Dict[str, Dict[str, Any]] = {}

    @abstractmethod
    async def initialize(self) -> bool:
        ...

    @abstractmethod
    async def shutdown(self) -> bool:
        ...

    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        ...

    def configure(self, credentials: Dict[str, str]) -> None:
        """Configure this connector with credentials.

        Stores credentials via CredentialService (abstracted from env vars).
        Subclasses override to inject credentials before ``initialize()``.
        """
        CredentialService.store(self.connector_type, credentials)

    def _load_credentials(self) -> Dict[str, str]:
        """Load credentials from CredentialService instead of os.getenv."""
        return CredentialService.load(self.connector_type)

    # ------------------------------------------------------------------
    # Capability introspection — automatically discovers planner-visible
    # operations from the subclass's public async methods.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Infrastructure — circuit breaker, HTTP helpers, token management
    # ------------------------------------------------------------------

    @property
    def _circuit_breaker(self) -> CircuitBreaker:
        if not hasattr(self, "__cb"):
            object.__setattr__(self, "__cb", CircuitBreaker())
        return self.__cb

    @property
    def _token_mgr(self) -> Optional[TokenManager]:
        return getattr(self, "__tm", None)

    def set_auth(self, client_id: str, client_secret: str, token_url: str,
                 scopes: Optional[List[str]] = None):
        object.__setattr__(self, "__tm", TokenManager(client_id, client_secret, token_url, scopes))

    async def _get_auth_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        tm = self._token_mgr
        if tm and tm.valid_token:
            headers["Authorization"] = f"Bearer {tm.valid_token}"
        return headers

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an HTTP request with circuit breaker protection.

        Subclasses that have an ``_http_client`` attribute (httpx.AsyncClient)
        will use it; otherwise the method constructs a full URL from *path*.
        """
        headers = kwargs.pop("headers", {})
        headers.update(await self._get_auth_headers())

        client: Optional[httpx.AsyncClient] = getattr(self, "_client", None) or getattr(self, "_http_client", None)

        async def _do_request():
            if client is not None:
                return await client.request(method, path, headers=headers, **kwargs)
            raise RuntimeError(f"{self.connector_name}: no HTTP client configured")

        try:
            return self._circuit_breaker.call(_do_request)
        except Exception as exc:
            log.error("[%s] Request failed: %s %s - %s", self.connector_name, method, path, exc)
            raise

    async def get_paginated(self, path: str, page_size: int = 100,
                            page_param: str = "page",
                            next_token_param: str = "next_token",
                            **kwargs) -> PaginatedResponse[Dict]:
        """Helper for paginated GET requests."""
        params = kwargs.pop("params", {})
        params[page_param if page_param == "page" else next_token_param] = 1
        params["per_page"] = page_size
        resp = await self.request("GET", path, params=params, **kwargs)
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", data.get("items", []))
        next_token = data.get("next_page_token") if isinstance(data, dict) else None
        has_more = bool(next_token)
        total = data.get("total") if isinstance(data, dict) else None
        return PaginatedResponse(
            items=items, next_page_token=next_token,
            has_more=has_more, total=total,
        )

    async def close(self):
        client: Optional[httpx.AsyncClient] = getattr(self, "_client", None) or getattr(self, "_http_client", None)
        if client is not None:
            await client.aclose()

    @classmethod
    def get_operations(cls) -> Dict[str, Dict[str, Any]]:
        """Return metadata for every planner-visible operation.

        Auto-discovers public async methods that are not lifecycle methods.
        Connectors can enrich descriptions by setting ``_operation_metadata``.

        Returns a dict keyed by operation name, where each value contains::

            "description"        — human-readable description
            "required_params"    — list of required parameter names
            "optional_params"    — dict of optional param → default repr
            "return_description" — description of the return value
        """
        BASE_EXCLUDED = {"initialize", "shutdown", "health", "configure", "_execute"}
        overrides = cls._operation_metadata

        operations: Dict[str, Dict[str, Any]] = {}
        for name in dir(cls):
            if name.startswith("_"):
                continue
            if name in BASE_EXCLUDED:
                continue
            method = getattr(cls, name, None)
            if not inspect.iscoroutinefunction(method):
                continue

            try:
                sig = inspect.signature(method)
            except (ValueError, TypeError):
                continue

            required: List[str] = []
            optional: Dict[str, str] = {}
            for pname, param in sig.parameters.items():
                if pname == "self" or pname == "kwargs":
                    continue
                if param.default is inspect.Parameter.empty:
                    required.append(pname)
                else:
                    default = param.default
                    if default is None:
                        d_repr = "None"
                    elif isinstance(default, str):
                        d_repr = f'"{default}"'
                    else:
                        d_repr = str(default)
                    optional[pname] = d_repr

            return_desc = "Dict[str, Any]"
            ret = sig.return_annotation
            if ret is not inspect.Parameter.empty and ret is not None:
                origin = getattr(ret, "__origin__", None)
                if origin is list:
                    return_desc = "List[Dict[str, Any]]"
                elif isinstance(ret, str):
                    return_desc = ret

            meta = overrides.get(name, {})
            operations[name] = {
                "description": meta.get(
                    "description",
                    f"Execute the {name} operation on {cls.connector_name}.",
                ),
                "required_params": required,
                "optional_params": optional,
                "return_description": meta.get("return_description", return_desc),
            }

        return operations

    async def _execute(
        self,
        operation: str,
        resource: Optional[str] = None,
        func=None,
        *args,
        **kwargs,
    ):
        start = time.monotonic()
        status = "success"
        resource_id = None
        message = None
        result = None
        try:
            result = await func(*args, **kwargs)
            if hasattr(result, "id"):
                resource_id = str(result.id)
            elif isinstance(result, dict) and "id" in result:
                resource_id = str(result["id"])
            return result
        except Exception as e:
            status = "failed"
            message = str(e)
            raise
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            try:
                await ConnectorActivityService.record(
                    connector_name=self.connector_name,
                    connector_type=self.connector_type,
                    operation=operation,
                    resource=resource or operation,
                    resource_id=resource_id,
                    status=status,
                    duration_ms=duration_ms,
                    message=message,
                )
            except Exception:
                log.warning("Failed to record connector activity", exc_info=True)
