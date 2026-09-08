"""
ORM model: cost_tracking

Stores per-call LLM/API cost records for the Mission Cost Engine.

Source of truth
---------------
Migrations ``0004_add_cost_tracking`` -> ``0005_cost_tracking_updated_at`` ->
``0006_fix_cost_tracking_id_type``, reproduced here column for column. Alembic
owns the application schema (ADR-109); this model describes the table the
lineage builds, it does not define one of its own.

What was wrong before Phase 10.20 (ADR-114)
-------------------------------------------
This model was never imported by ``backend/database/models/__init__``, so it
was never on ``Base.metadata`` -- and it disagreed with the table in four ways:

* it mapped the payload attribute to a column named ``extra_data``, while
  ``0004`` created ``extra``. ``cost_engine.record()`` -- the only writer --
  therefore issued ``INSERT ... (extra_data, ...)`` against a table with no
  such column, asyncpg raised ``UndefinedColumnError``, the transaction rolled
  back, and ``record()`` caught it and logged a warning. Every cost record
  written on every migrated database was silently lost, and the caller was
  told nothing.
* ``mission_id`` was ``String(36)`` and ``user_id`` ``String(128)``; ``0004``
  created both as ``String(255)``.
* the payload type was ``JSONB``; ``0004`` created ``sa.JSON``.
* six ``index=True`` markers and three ``idx_cost_*`` composite indexes
  described indexes no migration ever created, while the four
  ``ix_cost_tracking_*`` indexes the migration did create were undeclared.

``extra`` and ``extra_data`` were the same concept -- the free-form per-call
metadata dict every caller passes as ``extra=`` -- so this is a model
correction, not a rename: no reader projects the column, no contract names it,
and no database has ever had an ``extra_data`` column or a row in this table.

The mixins are kept deliberately: ``0006`` changed ``id`` to uuid "to match
UUIDPrimaryKeyMixin" and ``0005`` added ``updated_at`` "(TimestampMixin)".
The lineage was aligned to them on purpose.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import JSON, Date, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base
from backend.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CostRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per billable API call (LLM, search, voice, etc.).

    Designed for cheap INSERT-only writes; aggregation happens at query time
    via the summary methods in cost_engine.py, none of which reads ``extra``.
    """

    __tablename__ = "cost_tracking"

    # ── Identity ─────────────────────────────────────────────────────────────
    mission_id:  Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_id:     Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    session_id:  Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Provider / service ────────────────────────────────────────────────────
    provider:    Mapped[str]           = mapped_column(String(64),  nullable=False)
    # e.g. openai | anthropic | azure_openai | google | search | voice | custom
    service:     Mapped[str]           = mapped_column(String(64),  nullable=False)
    # e.g. chat_completion | embedding | tts | stt | web_search
    model:       Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # ── Usage ─────────────────────────────────────────────────────────────────
    prompt_tokens:     Mapped[int]   = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int]   = mapped_column(Integer, nullable=False, default=0)
    total_tokens:      Mapped[int]   = mapped_column(Integer, nullable=False, default=0)
    units:             Mapped[float] = mapped_column(Float,   nullable=False, default=0.0)
    # units = tokens for LLM, characters for TTS, seconds for audio, queries for search

    # ── Cost ──────────────────────────────────────────────────────────────────
    cost_usd:          Mapped[float] = mapped_column(Float,   nullable=False, default=0.0)

    # ── Reporting date (for easy date-bucketed aggregation) ───────────────────
    report_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Extended payload ─────────────────────────────────────────────────────
    # Column ``extra``, type JSON, exactly as 0004 created it. Free-form
    # per-call metadata; never read by any aggregate.
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # The four indexes 0004 created, by their migrated names.
    __table_args__ = (
        Index("ix_cost_tracking_mission_date",  "mission_id", "report_date"),
        Index("ix_cost_tracking_user_date",     "user_id",    "report_date"),
        Index("ix_cost_tracking_provider_date", "provider",   "report_date"),
        Index("ix_cost_tracking_report_date",   "report_date"),
    )
