"""World Plane application layer — ports and the ingestion service.

Depends on the epistemic contracts and the platform secret detector only. It
does not import a database, a connector, the gateway, the harness, or the
execution plane — composition supplies the repository, and the caller supplies
an already-read external result plus its governed context.
"""

from backend.world.application.ingestion import (
    ObservationIngestion,
    ObservationRejected,
    ObservationRepository,
    ReadObservation,
    observation_identity,
)

__all__ = [
    "ObservationRepository",
    "ObservationIngestion",
    "ObservationRejected",
    "ReadObservation",
    "observation_identity",
]
