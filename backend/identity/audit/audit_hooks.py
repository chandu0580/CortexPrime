from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger(__name__)


class IdentityAuditHooks:
    def __init__(self):
        self._enabled = True

    async def publish(
        self,
        action: str,
        user_id: str,
        outcome: str,
        metadata: Optional[dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> None:
        if not self._enabled:
            return
        try:
            from backend.events.event_bus import event_bus
            from backend.events.event_models import CognitionEvent, EventTypes

            await event_bus.publish(
                CognitionEvent(
                    agent="identity_runtime",
                    event_type=EventTypes.AUTH_EVENT
                    if hasattr(EventTypes, "AUTH_EVENT")
                    else "auth_event",
                    status=outcome,
                    message=f"Auth {action}: user={user_id[:32]} outcome={outcome}",
                    execution_id=f"auth_{user_id[:16]}",
                    payload={
                        "action": action,
                        "user_id": user_id,
                        "outcome": outcome,
                        "tenant_id": tenant_id,
                        **(metadata or {}),
                    },
                )
            )
        except Exception as exc:
            log.debug("Audit hook non-fatal error: %s", exc)

    async def login(self, user_id: str, outcome: str, tenant_id: Optional[str] = None, **kwargs: Any) -> None:
        await self.publish("login", user_id, outcome, kwargs, tenant_id)

    async def logout(self, user_id: str, outcome: str, tenant_id: Optional[str] = None, **kwargs: Any) -> None:
        await self.publish("logout", user_id, outcome, kwargs, tenant_id)

    async def token_refresh(self, user_id: str, outcome: str, tenant_id: Optional[str] = None, **kwargs: Any) -> None:
        await self.publish("token_refresh", user_id, outcome, kwargs, tenant_id)

    async def session_created(self, user_id: str, outcome: str, tenant_id: Optional[str] = None, **kwargs: Any) -> None:
        await self.publish("session_created", user_id, outcome, kwargs, tenant_id)

    async def session_revoked(self, user_id: str, outcome: str, tenant_id: Optional[str] = None, **kwargs: Any) -> None:
        await self.publish("session_revoked", user_id, outcome, kwargs, tenant_id)

    async def token_revoked(self, user_id: str, outcome: str, tenant_id: Optional[str] = None, **kwargs: Any) -> None:
        await self.publish("token_revoked", user_id, outcome, kwargs, tenant_id)

    async def permission_denied(self, user_id: str, resource: str, action: str, tenant_id: Optional[str] = None, **kwargs: Any) -> None:
        await self.publish("permission_denied", user_id, "denied", {**kwargs, "resource": resource, "action": action}, tenant_id)
