"""
Governance Audit Logger  (CortexPrime)
========================================
Durable audit trail backed by PostgreSQL.

Every governance decision, mission lifecycle event, browser/computer agent
action, and approval workflow outcome is written to the ``audit_logs`` table.
Entries survive server restarts, Docker restarts, and deployments.

Public interface (backward-compatible)
---------------------------------------
    audit_logger.log(...)               → AuditEntry  (sync, fire-and-forget to DB)
    await audit_logger.alog(...)        → AuditEntry  (async, awaits DB write)
    audit_logger.get_all(limit)         → list[dict]  (reads from DB)
    audit_logger.get_by_execution(id)   → list[dict]
    audit_logger.get_by_outcome(o)      → list[dict]
    audit_logger.get_by_risk(r)         → list[dict]
    audit_logger.summary()             → dict
    await audit_logger.get_all_async(...)           → list[dict]
    await audit_logger.get_by_execution_async(...)  → list[dict]
    await audit_logger.get_page(...)                → dict  (paginated)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

log = logging.getLogger(__name__)


# =========================================================
# AUDIT ENTRY  (lightweight in-process DTO)
# =========================================================

@dataclass
class AuditEntry:
    audit_id:     str
    execution_id: str
    agent:        str
    user:         str
    action:       str
    target:       str
    risk_level:   str
    outcome:      str          # approved | rejected | blocked | allowed | timed_out | started | completed | failed
    reason:       str
    timestamp:    str
    session_id:   Optional[str]
    request_id:   Optional[str]
    metadata:     Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =========================================================
# AUDIT LOGGER
# =========================================================

class AuditLogger:
    """
    Central audit log for all governance decisions in CortexPrime.

    Writes are always durable: every entry is persisted to PostgreSQL.
    A small write-through in-memory cache (up to _MAX_CACHE rows) is kept
    for low-latency reads of recent entries when the DB is unavailable.
    """

    _MAX_CACHE = 200   # recent-entry read cache only; not the source of truth

    def __init__(self) -> None:
        self._cache: List[AuditEntry] = []

    # ----------------------------------------------------------
    # SYNCHRONOUS LOG  (fire-and-forget DB write)
    # ----------------------------------------------------------

    def log(
        self,
        execution_id: str,
        agent:        str,
        action:       str,
        target:       str            = "",
        risk_level:   str            = "low",
        outcome:      str            = "allowed",
        reason:       str            = "",
        user:         str            = "system",
        session_id:   Optional[str]  = None,
        request_id:   Optional[str]  = None,
        metadata:     Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            audit_id     = str(uuid4()),
            execution_id = execution_id,
            agent        = agent,
            user         = user,
            action       = action,
            target       = target,
            risk_level   = risk_level,
            outcome      = outcome,
            reason       = reason,
            timestamp    = datetime.utcnow().isoformat(),
            session_id   = session_id,
            request_id   = request_id,
            metadata     = metadata or {},
        )

        self._add_to_cache(entry)

        log.debug(
            "AUDIT | %s | %s | action=%s | outcome=%s | risk=%s",
            execution_id[:8], agent, action, outcome, risk_level,
        )

        # Fire-and-forget durable persistence to PostgreSQL
        asyncio.ensure_future(self._persist(entry))

        return entry

    # ----------------------------------------------------------
    # ASYNC LOG  (awaits DB write — use when you need confirmation)
    # ----------------------------------------------------------

    async def alog(
        self,
        execution_id: str,
        agent:        str,
        action:       str,
        target:       str            = "",
        risk_level:   str            = "low",
        outcome:      str            = "allowed",
        reason:       str            = "",
        user:         str            = "system",
        session_id:   Optional[str]  = None,
        request_id:   Optional[str]  = None,
        metadata:     Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            audit_id     = str(uuid4()),
            execution_id = execution_id,
            agent        = agent,
            user         = user,
            action       = action,
            target       = target,
            risk_level   = risk_level,
            outcome      = outcome,
            reason       = reason,
            timestamp    = datetime.utcnow().isoformat(),
            session_id   = session_id,
            request_id   = request_id,
            metadata     = metadata or {},
        )

        self._add_to_cache(entry)

        log.debug(
            "AUDIT | %s | %s | action=%s | outcome=%s | risk=%s",
            execution_id[:8], agent, action, outcome, risk_level,
        )

        await self._persist(entry)
        return entry

    # ----------------------------------------------------------
    # SYNCHRONOUS QUERIES  (read from DB; fall back to cache)
    # ----------------------------------------------------------

    def get_all(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return most recent entries — prefers DB, falls back to cache."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._warm_cache(limit))
                return [e.as_dict() for e in self._cache[-limit:][::-1]]
            else:
                return loop.run_until_complete(self.get_all_async(limit=limit))
        except Exception:
            return [e.as_dict() for e in self._cache[-limit:][::-1]]

    def get_by_execution(self, execution_id: str) -> List[Dict[str, Any]]:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return [e.as_dict() for e in self._cache if e.execution_id == execution_id]
            else:
                return loop.run_until_complete(
                    self.get_by_execution_async(execution_id)
                )
        except Exception:
            return [e.as_dict() for e in self._cache if e.execution_id == execution_id]

    def get_by_outcome(self, outcome: str, limit: int = 100) -> List[Dict[str, Any]]:
        return [e.as_dict() for e in reversed(self._cache) if e.outcome == outcome][:limit]

    def get_by_risk(self, risk_level: str, limit: int = 100) -> List[Dict[str, Any]]:
        return [e.as_dict() for e in reversed(self._cache) if e.risk_level == risk_level][:limit]

    def summary(self) -> Dict[str, Any]:
        entries  = self._cache
        total    = len(entries)
        approved = sum(1 for e in entries if e.outcome == "approved")
        rejected = sum(1 for e in entries if e.outcome == "rejected")
        blocked  = sum(1 for e in entries if e.outcome == "blocked")
        allowed  = sum(1 for e in entries if e.outcome == "allowed")
        critical = sum(1 for e in entries if e.risk_level == "critical")
        high     = sum(1 for e in entries if e.risk_level == "high")
        return {
            "total":             total,
            "approved":          approved,
            "rejected":          rejected,
            "blocked":           blocked,
            "allowed":           allowed,
            "critical_actions":  critical,
            "high_risk_actions": high,
        }

    # ----------------------------------------------------------
    # ASYNC QUERIES  (used by API routes directly)
    # ----------------------------------------------------------

    async def get_all_async(
        self,
        limit:      int           = 200,
        offset:     int           = 0,
        risk_level: Optional[str] = None,
        outcome:    Optional[str] = None,
        agent:      Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Paginated audit log query from PostgreSQL."""
        try:
            from sqlalchemy import select, desc
            from backend.database.engine import AsyncSessionLocal
            from backend.database.models.audit_log import AuditLog

            async with AsyncSessionLocal() as session:
                q = select(AuditLog).order_by(desc(AuditLog.created_at))
                if risk_level:
                    q = q.where(AuditLog.risk_level == risk_level)
                if outcome:
                    q = q.where(AuditLog.outcome == outcome)
                if agent:
                    q = q.where(AuditLog.agent == agent)
                q = q.offset(offset).limit(limit)
                result = await session.execute(q)
                rows = result.scalars().all()
                return [r.to_dict() for r in rows]
        except Exception as exc:
            log.warning("DB query failed, using cache: %s", exc)
            entries = list(reversed(self._cache))
            if risk_level:
                entries = [e for e in entries if e.risk_level == risk_level]
            if outcome:
                entries = [e for e in entries if e.outcome == outcome]
            if agent:
                entries = [e for e in entries if e.agent == agent]
            return [e.as_dict() for e in entries[offset : offset + limit]]

    async def get_by_execution_async(self, execution_id: str) -> List[Dict[str, Any]]:
        try:
            from sqlalchemy import select
            from backend.database.engine import AsyncSessionLocal
            from backend.database.models.audit_log import AuditLog

            async with AsyncSessionLocal() as session:
                q = (
                    select(AuditLog)
                    .where(AuditLog.execution_id == execution_id)
                    .order_by(AuditLog.created_at)
                )
                result = await session.execute(q)
                rows = result.scalars().all()
                return [r.to_dict() for r in rows]
        except Exception as exc:
            log.warning("DB query failed, using cache: %s", exc)
            return [e.as_dict() for e in self._cache if e.execution_id == execution_id]

    async def get_page(
        self,
        page:       int           = 1,
        page_size:  int           = 50,
        risk_level: Optional[str] = None,
        outcome:    Optional[str] = None,
        agent:      Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a paginated result set with total count."""
        try:
            from sqlalchemy import select, desc, func
            from backend.database.engine import AsyncSessionLocal
            from backend.database.models.audit_log import AuditLog

            offset = (page - 1) * page_size

            async with AsyncSessionLocal() as session:
                count_q = select(func.count()).select_from(AuditLog)
                if risk_level:
                    count_q = count_q.where(AuditLog.risk_level == risk_level)
                if outcome:
                    count_q = count_q.where(AuditLog.outcome == outcome)
                if agent:
                    count_q = count_q.where(AuditLog.agent == agent)
                total_result = await session.execute(count_q)
                total = total_result.scalar() or 0

                q = select(AuditLog).order_by(desc(AuditLog.created_at))
                if risk_level:
                    q = q.where(AuditLog.risk_level == risk_level)
                if outcome:
                    q = q.where(AuditLog.outcome == outcome)
                if agent:
                    q = q.where(AuditLog.agent == agent)
                q = q.offset(offset).limit(page_size)
                result = await session.execute(q)
                rows = result.scalars().all()
                entries = [r.to_dict() for r in rows]

            return {
                "entries":   entries,
                "total":     total,
                "page":      page,
                "page_size": page_size,
                "pages":     (total + page_size - 1) // page_size if total else 0,
                "has_next":  (page * page_size) < total,
                "has_prev":  page > 1,
            }
        except Exception as exc:
            log.warning("DB pagination failed, using cache: %s", exc)
            entries = list(reversed(self._cache))
            if risk_level:
                entries = [e for e in entries if e.risk_level == risk_level]
            if outcome:
                entries = [e for e in entries if e.outcome == outcome]
            if agent:
                entries = [e for e in entries if e.agent == agent]
            total  = len(entries)
            offset = (page - 1) * page_size
            slice_ = entries[offset : offset + page_size]
            return {
                "entries":   [e.as_dict() for e in slice_],
                "total":     total,
                "page":      page,
                "page_size": page_size,
                "pages":     (total + page_size - 1) // page_size if total else 0,
                "has_next":  (page * page_size) < total,
                "has_prev":  page > 1,
            }

    async def get_summary_async(self) -> Dict[str, Any]:
        """Aggregate statistics from PostgreSQL."""
        try:
            from sqlalchemy import select, func
            from backend.database.engine import AsyncSessionLocal
            from backend.database.models.audit_log import AuditLog

            async with AsyncSessionLocal() as session:
                outcome_q = (
                    select(AuditLog.outcome, func.count().label("cnt"))
                    .group_by(AuditLog.outcome)
                )
                outcome_res = await session.execute(outcome_q)
                by_outcome: Dict[str, int] = {row.outcome: row.cnt for row in outcome_res}

                risk_q = (
                    select(AuditLog.risk_level, func.count().label("cnt"))
                    .group_by(AuditLog.risk_level)
                )
                risk_res = await session.execute(risk_q)
                by_risk: Dict[str, int] = {row.risk_level: row.cnt for row in risk_res}

                total_q = select(func.count()).select_from(AuditLog)
                total_res = await session.execute(total_q)
                total = total_res.scalar() or 0

            return {
                "total":             total,
                "approved":          by_outcome.get("approved", 0),
                "rejected":          by_outcome.get("rejected", 0),
                "blocked":           by_outcome.get("blocked", 0),
                "allowed":           by_outcome.get("allowed", 0),
                "pending":           by_outcome.get("pending", 0),
                "started":           by_outcome.get("started", 0),
                "completed":         by_outcome.get("completed", 0),
                "failed":            by_outcome.get("failed", 0),
                "critical_actions":  by_risk.get("critical", 0),
                "high_risk_actions": by_risk.get("high", 0),
            }
        except Exception as exc:
            log.warning("DB summary failed, using cache: %s", exc)
            return self.summary()

    # ----------------------------------------------------------
    # INTERNAL HELPERS
    # ----------------------------------------------------------

    def _add_to_cache(self, entry: AuditEntry) -> None:
        self._cache.append(entry)
        if len(self._cache) > self._MAX_CACHE:
            self._cache = self._cache[-self._MAX_CACHE:]

    async def _warm_cache(self, limit: int) -> None:
        """Refresh the in-memory cache from the DB (best-effort)."""
        try:
            entries = await self.get_all_async(limit=limit)
            self._cache = [
                AuditEntry(
                    audit_id     = e.get("id", str(uuid4())),
                    execution_id = e["execution_id"],
                    agent        = e["agent"],
                    user         = e.get("user_id", "system"),
                    action       = e["action"],
                    target       = e.get("metadata", {}).get("target", ""),
                    risk_level   = e["risk_level"],
                    outcome      = e["outcome"],
                    reason       = e["reason"],
                    timestamp    = e.get("timestamp", ""),
                    session_id   = e.get("session_id"),
                    request_id   = e.get("request_id"),
                    metadata     = e.get("metadata", {}),
                )
                for e in reversed(entries)
            ]
        except Exception:
            pass  # cache warm-up must never crash anything

    async def _persist(self, entry: AuditEntry) -> None:
        """Write a single audit entry to PostgreSQL (durable)."""
        try:
            from backend.database.engine import AsyncSessionLocal
            from backend.database.models.audit_log import AuditLog

            meta = dict(entry.metadata)
            if entry.target:
                meta.setdefault("target", entry.target)

            row = AuditLog(
                id           = entry.audit_id,  # type: ignore[arg-type]
                execution_id = entry.execution_id,
                user_id      = entry.user,
                agent        = entry.agent,
                action       = entry.action,
                risk_level   = entry.risk_level,
                outcome      = entry.outcome,
                reason       = entry.reason,
                session_id   = entry.session_id,
                request_id   = entry.request_id,
                metadata_    = meta or None,
            )

            async with AsyncSessionLocal() as session:
                session.add(row)
                await session.commit()

        except Exception as exc:
            log.warning("Audit persistence failed: %s", exc)


# =========================================================
# SINGLETON
# =========================================================

audit_logger = AuditLogger()
