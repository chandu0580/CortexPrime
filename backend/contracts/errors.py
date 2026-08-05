"""Contract-layer errors.

The contracts package raises exactly two error types. Both are defined here so
that no contract module needs to import any other contract module for error
handling.

Contracts never raise framework exceptions (HTTPException, ValidationError from
a third-party library, etc.). Translating a ContractViolation into a transport
error is the responsibility of the interface layer.
"""

from __future__ import annotations

__all__ = ["ContractViolation", "ContractVersionError"]


class ContractViolation(ValueError):
    """A contract was constructed or decoded with invalid content.

    Raised during ``__post_init__`` validation and during ``from_dict``
    decoding. Callers should treat this as a programming error or a malformed
    message, never as an expected control-flow outcome.
    """


class ContractVersionError(ContractViolation):
    """A serialized payload declares a contract version that cannot be decoded.

    Distinct from ContractViolation so that transport layers can distinguish
    "this message is malformed" from "this message came from a newer peer".
    """
