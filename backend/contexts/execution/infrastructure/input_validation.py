"""The concrete input validator: the Phase 3.3.3 seam, wired to real declarations.

What the seam was, and what it now has behind it
--------------------------------------------------
``InputValidator`` has existed since ADR-038 as a port with nothing implementing
it, and the gateway has refused every payload-carrying invocation ever since —
correctly, because unvalidated caller data reaching a real provider is precisely
what it exists to stop. Phase 4.3 gives it an implementation: the operation
catalogs the adapters were built from.

Why the catalog and not a schema engine
-----------------------------------------
Because the catalog is the same declaration the adapter builds its request from.
A separate validator with its own schema copy would be a second statement of
what an operation accepts, and the two would diverge on the first change — after
which one of them is wrong and nobody knows which. Here, "what may be sent" and
"what is checked" are the same object.

The platform's own schema validation is untouched and no second one is added.
This is a seam implementation, not an engine.

It fails closed in every direction
------------------------------------
No catalog for the provider, no entry for the operation, an operation whose
declaration no longer matches the bound contract, or input that does not satisfy
the declaration — all of them return problems, and the gateway turns any problem
into a refusal. There is no branch that returns "no problems found" because
something was missing.

It runs before the action is digested
--------------------------------------
The gateway validates, *then* digests, *then* acquires a credential. So input
that fails here never becomes an action digest, never causes a secret to be
minted, and never reaches a provider — which is the ordering ADR-042 §15 asks
for, and it is already the ordering the gateway had.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Tuple

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.domain.bound_capability import BoundCapability
from backend.contexts.execution.domain.provider_operation import OperationCatalog

__all__ = ["OperationInputValidator"]


class OperationInputValidator:
    """Validates a payload against the declared operation it will be sent as.

    Immutable after construction and owned by the composition root. There is no
    ``register``: a validator that could gain a provider at runtime would be a
    place an operation could become valid without anybody declaring it.
    """

    __slots__ = ("_catalogs", "_require_declaration")

    def __init__(
        self,
        catalogs: Iterable[OperationCatalog],
        *,
        require_declaration: bool = True,
    ) -> None:
        entries: dict = {}
        for catalog in catalogs:
            if not isinstance(catalog, OperationCatalog):
                raise ContractViolation(
                    "an input validator is built from OperationCatalog entries"
                )
            if catalog.provider_id in entries:
                raise ContractViolation(
                    f"two catalogs describe {catalog.provider_id!r}; one of them "
                    "would silently not apply, and nobody would know which"
                )
            entries[catalog.provider_id] = catalog
        self._catalogs = entries
        self._require_declaration = require_declaration
        """When true — the default — a provider with no catalog refuses.

        The alternative would be to pass unvalidated input through for providers
        nobody has declared yet, which is exactly the accident the seam exists to
        prevent. Turning it off is only defensible where another authoritative
        validator runs first, and there is deliberately no configuration path
        that sets it: a caller has to pass it.
        """

    @property
    def providers(self) -> Tuple[str, ...]:
        return tuple(sorted(self._catalogs))

    def catalog_for(self, provider_id: str) -> Optional[OperationCatalog]:
        return self._catalogs.get(provider_id)

    def validate(
        self, binding: BoundCapability, payload: Mapping[str, Any]
    ) -> Tuple[str, ...]:
        """Every problem with this input, or an empty tuple.

        Returns all of them rather than the first: an operator fixing one field
        and rediscovering the next has been told half the truth twice.
        """
        catalog = self._catalogs.get(binding.provider)
        if catalog is None:
            if not self._require_declaration:
                return ()
            return (
                f"no operation catalog declares provider {binding.provider!r}; "
                "input cannot be validated against a contract nobody wrote, and "
                "unvalidated input is not passed to a provider because the "
                "declaration happens to be missing",
            )

        spec = catalog.get(binding.operation)
        if spec is None:
            return (
                f"{binding.provider} declares no operation {binding.operation!r}; "
                f"it declares {', '.join(catalog.operations)}",
            )

        problems: list = []
        # Contract drift first. A payload that is valid against a declaration
        # which no longer matches the bound contract is still not a payload this
        # action was authorized to send.
        problems.extend(spec.contract_refusals(binding))
        problems.extend(spec.input_problems(payload or {}))
        return tuple(problems)

    def __repr__(self) -> str:
        return (
            f"<OperationInputValidator providers={self.providers} "
            f"require_declaration={self._require_declaration}>"
        )
