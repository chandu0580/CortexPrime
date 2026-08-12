"""Assurance infrastructure — the durable verification repository.

The one place in the Assurance Plane that touches the durable store. It
implements the ``VerificationRepository`` port over ``cw_verification``
(migration 0017), append-only. It imports the durable store and the epistemic
contracts, and nothing that executes.
"""

from backend.assurance.infrastructure.sql_verification import SqlVerificationRepository

__all__ = ["SqlVerificationRepository"]
