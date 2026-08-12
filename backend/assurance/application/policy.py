"""Assurance policy — deterministic, versioned, inspectable. No numbers.

The policy states what evidence a verification requires before it may return
SUPPORTED. It is explicit configuration a model cannot modify: required source
authority, whether fresh evidence is required, whether independence must be
lineage-proven, and how conflict is handled. There are no numeric trust scores —
requirements are tiers and booleans, the same discipline as Phases 7.4/7.6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts.world import SourceAuthority

__all__ = ["AssurancePolicy"]


@dataclass(frozen=True)
class AssurancePolicy:
    """The bar a verification must clear to return SUPPORTED.

    ``require_fresh`` — stale evidence cannot support (STALE != VERIFIED).
    ``require_known_lineage`` — evidence whose lineage is UNKNOWN cannot be
    claimed independent, so it cannot support (no false independence).
    ``min_authority`` — the evidence source must have at least this standing.
    Conflict and unknown world state can never support, regardless of policy —
    those are hard failure semantics, not tunable."""

    name: str = "assurance-policy"
    version: int = 1
    require_fresh: bool = True
    require_known_lineage: bool = False
    min_authority: Optional[SourceAuthority] = None

    @classmethod
    def default(cls) -> "AssurancePolicy":
        """Fresh evidence required; lineage independence not required; no
        authority floor. The honest baseline."""
        return cls()

    @property
    def policy_ref(self) -> str:
        return f"assurance-policy:{self.name}/{self.version}"
