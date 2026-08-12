"""World Plane infrastructure — the durable observation repository.

The one place in the World Plane that touches the durable store. It implements
the ``ObservationRepository`` port over ``cw_observation`` (migration 0015),
append-only. It imports the durable store and the epistemic contracts, and
nothing that executes.
"""

from backend.world.infrastructure.sql_observation import SqlObservationRepository

__all__ = ["SqlObservationRepository"]
