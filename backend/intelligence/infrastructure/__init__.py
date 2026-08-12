"""Intelligence infrastructure — the durable investigation repository.

The one place in the Intelligence Plane that touches the durable store. It
implements the ``InvestigationRepository`` port over ``cw_investigation``
(migration 0019), append-only, event-sourced. It imports the durable store and
the contracts, and nothing that executes.
"""

from backend.intelligence.infrastructure.sql_investigation import (
    SqlInvestigationRepository,
)

__all__ = ["SqlInvestigationRepository"]
