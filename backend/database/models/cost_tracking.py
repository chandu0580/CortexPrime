"""
ORM model: cost_tracking

Stores per-call LLM/API cost records for the Mission Cost Engine.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy                     import Date, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm                 import Mapped, mapped_column

from backend.database.base          import Base
from backend.database.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class CostRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One row per billable API call (LLM, search, voice, etc.).

    Designed for cheap INSERT-only writes; aggregation happens at query time
    or via the summary views in cost_engine.py.
    """

    __tablename__ = "cost_tracking"

    # ── Identity ─────────────────────────────────────────────────────────────
    mission_id:  Mapped[Optional[str]] = mapped_column(String(36),  nullable=True, index=True)
    user_id:     Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    session_id:  Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # ── Provider / service ────────────────────────────────────────────────────
    provider:    Mapped[str]           = mapped_column(String(64),  nullable=False, index=True)
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
    cost_usd:          Mapped[float] = mapped_column(Float,   nullable=False, default=0.0, index=True)

    # ── Reporting date (for easy date-bucketed aggregation) ───────────────────
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # ── Extended payload ─────────────────────────────────────────────────────
    extra: Mapped[Optional[dict]] = mapped_column("extra_data", JSONB, nullable=True)

    __table_args__ = (
        Index("idx_cost_mission_date",  "mission_id",  "report_date"),
        Index("idx_cost_user_date",     "user_id",     "report_date"),
        Index("idx_cost_provider_date", "provider",    "report_date"),
    )
