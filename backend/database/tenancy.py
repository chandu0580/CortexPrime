from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

_current_tenant_id: ContextVar[Optional[uuid.UUID]] = ContextVar("current_tenant_id", default=None)

PUBLIC_SCHEMA = "public"
TENANT_SCHEMA_PREFIX = "org_"


def set_current_tenant(tenant_id: Optional[uuid.UUID]) -> None:
    if tenant_id is None:
        _current_tenant_id.set(None)
    else:
        _current_tenant_id.set(tenant_id)


def get_current_tenant() -> Optional[uuid.UUID]:
    return _current_tenant_id.get()


def tenant_schema_name(tenant_id: uuid.UUID) -> str:
    return f"{TENANT_SCHEMA_PREFIX}{tenant_id.hex}"


async def ensure_tenant_schema(session: AsyncSession, tenant_id: uuid.UUID) -> str:
    schema = tenant_schema_name(tenant_id)
    result = await session.execute(
        text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    if result.scalar_one_or_none() is None:
        await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS \"{schema}\""))
        log.info("Created tenant schema: %s", schema)
    await session.execute(text(f"SET search_path TO \"{schema}\", public"))
    return schema


async def set_session_tenant(session: AsyncSession, tenant_id: Optional[uuid.UUID]) -> None:
    if tenant_id is None:
        await session.execute(text(f"SET search_path TO {PUBLIC_SCHEMA}"))
        _current_tenant_id.set(None)
    else:
        schema = tenant_schema_name(tenant_id)
        await session.execute(text(f"SET search_path TO \"{schema}\", {PUBLIC_SCHEMA}"))
        _current_tenant_id.set(tenant_id)


class TenantContextManager:
    def __init__(self, session: AsyncSession, tenant_id: Optional[uuid.UUID]):
        self._session = session
        self._tenant_id = tenant_id
        self._previous_tenant = get_current_tenant()

    async def __aenter__(self) -> AsyncSession:
        await set_session_tenant(self._session, self._tenant_id)
        return self._session

    async def __aexit__(self, *args) -> None:
        await set_session_tenant(self._session, self._previous_tenant)
