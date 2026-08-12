"""Assurance application layer — the independent verifier and its policies.

Depends on the World read layer and the epistemic/verification contracts only.
It imports no connector, gateway, transport, credential, scheduler, or execution
plane — assurance evaluates claims against independently obtained evidence; it
never acts. Composition supplies the durable verification repository.
"""

from backend.assurance.application.procedures import (
    PROCEDURE_VERSION,
    VerificationProcedure,
    VerificationProcedureKind,
)
from backend.assurance.application.policy import AssurancePolicy
from backend.assurance.application.verifier import (
    DEFAULT_VERIFIER_IDENTITY,
    AssuranceRefused,
    AssuranceResult,
    AssuranceVerifier,
    VerificationRepository,
)

__all__ = [
    "VerificationProcedure",
    "VerificationProcedureKind",
    "PROCEDURE_VERSION",
    "AssurancePolicy",
    "AssuranceVerifier",
    "AssuranceResult",
    "AssuranceRefused",
    "VerificationRepository",
    "DEFAULT_VERIFIER_IDENTITY",
]
