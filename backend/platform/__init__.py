"""CortexPrime platform infrastructure.

Cross-cutting technical capability with zero domain knowledge: identity,
hashing, persistence, messaging, configuration, telemetry.

Dependency rule (Constitution S10)::

    platform/  may import  contracts/
    platform/  may NOT import  contexts/  or  legacy/

Platform code knows *how* to do something. It never knows *why*. A module here
that can name a detector, a mission type, or a customer has drifted into a
bounded context and belongs elsewhere.
"""

from __future__ import annotations

__all__: list[str] = []
