"""The Capability Registry application service.

Orchestrates: domain decision → persistence → event. Events are returned, never
published; this context owns no bus, the same arrangement as every other context
here.

What this service answers
---------------------------
    What capabilities exist?
    What does this one claim?
    May it run?

What it deliberately does **not** answer
------------------------------------------
    Which capability should serve this request?

That is resolution, and it needs a request to resolve against. Building it here
would make the registry decide what to use rather than record what exists, and
the two want different inputs and different tests. Phase 3.2.4.

Registration is a privileged operation
----------------------------------------
Registering a capability is how something becomes runnable at all, so it is at
least as sensitive as approving a workflow. The authorization *decision* belongs
to Phase 3.2.3; what exists here is the seam it will occupy --
``registration_guard``, which every write goes through and which by default
refuses nothing. That default is stated rather than hidden, because an
unguarded registry is a real exposure and pretending otherwise would be worse
than leaving it open on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable

from backend.contracts.connector import CodeTrust, IsolationTier
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.contexts.connectivity.application.commands import (
    DeprecateCapability,
    DisableCapability,
    EnableCapability,
    GetCapability,
    InspectContract,
    ListCapabilities,
    ListVersions,
    RegisterCapability,
    RevokeCapability,
    SetCapabilityTrust,
    ValidateCapability,
)
from backend.contexts.connectivity.domain.contract import (
    CapabilityContract,
    CapabilityEnvironment,
    CapabilityInterface,
    ExecutionMode,
    SchemaRef,
)
from backend.contexts.connectivity.domain.definition import (
    CapabilityDefinition,
    CapabilitySource,
    CapabilityTenancy,
)
from backend.contexts.connectivity.domain.errors import (
    CapabilityNotFound,
    CapabilityVersionNotFound,
)
from backend.contexts.connectivity.domain.events import (
    AGGREGATE_TYPE,
    CapabilityDeprecated,
    CapabilityDisabled,
    CapabilityEnabled,
    CapabilityRegistered,
    CapabilityRevoked,
    CapabilityTrustChanged,
    CapabilityValidated,
)
from backend.contexts.connectivity.domain.identifiers import (
    CapabilityId,
    CapabilityRef,
    CapabilityVersion,
)
from backend.contexts.connectivity.domain.lifecycle import CapabilityStatus, TrustState
from backend.platform.events import EventMetadata

__all__ = ["CapabilityService", "CommandResult", "RegistrationGuard", "OpenRegistration"]


@dataclass(frozen=True)
class CommandResult:
    capability: CapabilityDefinition
    events: tuple = ()

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


@runtime_checkable
class RegistrationGuard(Protocol):
    """The seam Phase 3.2.3's authorization will occupy.

    Narrow on purpose: it is asked whether a principal may register or move a
    capability, and it holds nothing the registry can reach. A policy engine
    implements this; nothing else in this module changes when it does.
    """

    def assert_may_register(self, context: Any, definition: CapabilityDefinition) -> None: ...

    def assert_may_change(
        self, context: Any, definition: CapabilityDefinition, operation: str
    ) -> None: ...


class OpenRegistration:
    """Refuses nothing. The honest default until 3.2.3 exists.

    Named so that "this registry has no authorization" is visible at the
    composition root rather than being an absence somebody has to notice.
    """

    def assert_may_register(self, context: Any, definition: CapabilityDefinition) -> None:
        return None

    def assert_may_change(
        self, context: Any, definition: CapabilityDefinition, operation: str
    ) -> None:
        return None


class CapabilityService:
    def __init__(
        self,
        repository: Any,
        *,
        guard: Optional[RegistrationGuard] = None,
    ) -> None:
        self._repository = repository
        self._guard = guard or OpenRegistration()

    @property
    def guard(self) -> RegistrationGuard:
        return self._guard

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    @staticmethod
    def _metadata(context: Any, definition: CapabilityDefinition) -> EventMetadata:
        from backend.contracts.tenant import TenantRef, TenantScope

        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=definition.reference.value,
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
        )

    def _facts(self, definition: CapabilityDefinition) -> dict:
        return {
            "capability_id": definition.capability_id.value,
            "version": definition.version.number,
            "digest": definition.digest or "",
            "tenancy": definition.tenancy.value,
            "owner": definition.owner.principal_id,
        }

    def _reference(self, capability_id: str, version: int) -> CapabilityRef:
        return CapabilityRef(
            capability_id=CapabilityId.parse(capability_id),
            version=CapabilityVersion(version),
        )

    def _load(self, context: Any, capability_id: str, version: int) -> CapabilityDefinition:
        reference = self._reference(capability_id, version)
        found = self._repository.find(context, reference)
        if found is None:
            known = [
                d.version.number
                for d in self._repository.versions_of(context, reference.capability_id)
            ]
            if not known:
                raise CapabilityNotFound(reference.capability_id.value)
            raise CapabilityVersionNotFound(
                reference.capability_id.value, version, known
            )
        return found

    def _saved(
        self, context: Any, definition: CapabilityDefinition, events: tuple
    ) -> CommandResult:
        self._repository.replace(context, definition)
        return CommandResult(capability=definition, events=events)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, context: Any, command: RegisterCapability) -> CommandResult:
        """Declare a capability version.

        Arrives REGISTERED and UNVERIFIED, never enabled and never trusted.
        Something that describes itself and is immediately usable is a
        self-signed certificate.
        """
        contract = CapabilityContract(
            interface=CapabilityInterface(command.interface),
            side_effect_class=SideEffectClass(command.side_effect_class),
            effect_semantics=EffectSemantics(command.effect_semantics),
            isolation_tier=IsolationTier(command.isolation_tier),
            code_trust=CodeTrust(command.code_trust),
            execution_mode=ExecutionMode(command.execution_mode),
            input_schema=(
                SchemaRef.from_dict(command.input_schema) if command.input_schema else None
            ),
            output_schema=(
                SchemaRef.from_dict(command.output_schema)
                if command.output_schema
                else None
            ),
            required_permissions=tuple(command.required_permissions),
            supported_environments=tuple(
                CapabilityEnvironment(e) for e in command.supported_environments
            ),
            idempotency_supported=command.idempotency_supported,
            retryable=command.retryable,
            cancellable=command.cancellable,
            compensation_capability=command.compensation_capability,
            timeout_seconds=command.timeout_seconds,
                provider_operation=command.provider_operation,
        )

        definition = CapabilityDefinition.register(
            capability_id=CapabilityId.parse(command.capability_id),
            version=CapabilityVersion(command.version),
            name=command.name,
            description=command.description,
            provider=command.provider,
            contract=contract,
            owner=PrincipalRef(
                principal_id=command.owner_id,
                kind=PrincipalKind(command.owner_kind),
                display_name=command.owner_display_name,
            ),
            tenancy=CapabilityTenancy(command.tenancy),
            source=CapabilitySource(command.source),
            tenant_id=command.tenant_id,
            shared_with=tuple(command.shared_with),
            category=command.category,
            supersedes=command.supersedes,
            metadata=command.metadata,
        )

        self._guard.assert_may_register(context, definition)

        # The repository refuses a different contract for a version that already
        # exists, and accepts an identical one idempotently. Detected here so the
        # event can say which of the two happened.
        already = self._repository.find(context, definition.reference)
        self._repository.register(context, definition)
        stored = self._repository.find(context, definition.reference) or definition

        return CommandResult(
            capability=stored,
            events=(
                CapabilityRegistered(
                    metadata=self._metadata(context, stored),
                    **self._facts(stored),
                    provider=stored.provider,
                    interface=stored.contract.interface.value,
                    side_effect_class=stored.contract.side_effect_class.value,
                    effect_semantics=stored.contract.effect_semantics.value,
                    source=stored.source.value,
                    idempotent_registration=already is not None,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def validate(self, context: Any, command: ValidateCapability) -> CommandResult:
        definition = self._load(context, command.capability_id, command.version)
        self._guard.assert_may_change(context, definition, "validate")
        # The stored definition must still be the one that was registered.
        definition.verify_digest()
        moved = definition.validated(command.note)
        return self._saved(
            context,
            moved,
            (
                CapabilityValidated(
                    metadata=self._metadata(context, moved),
                    **self._facts(moved),
                    note=command.note,
                ),
            ),
        )

    def enable(self, context: Any, command: EnableCapability) -> CommandResult:
        definition = self._load(context, command.capability_id, command.version)
        self._guard.assert_may_change(context, definition, "enable")
        definition.verify_digest()
        moved = definition.enabled(command.note)
        return self._saved(
            context,
            moved,
            (
                CapabilityEnabled(
                    metadata=self._metadata(context, moved),
                    **self._facts(moved),
                    trust=moved.trust.value,
                    executable=moved.is_executable,
                ),
            ),
        )

    def disable(self, context: Any, command: DisableCapability) -> CommandResult:
        definition = self._load(context, command.capability_id, command.version)
        self._guard.assert_may_change(context, definition, "disable")
        moved = definition.disabled(command.reason)
        return self._saved(
            context,
            moved,
            (
                CapabilityDisabled(
                    metadata=self._metadata(context, moved),
                    **self._facts(moved),
                    reason=command.reason,
                ),
            ),
        )

    def deprecate(self, context: Any, command: DeprecateCapability) -> CommandResult:
        definition = self._load(context, command.capability_id, command.version)
        self._guard.assert_may_change(context, definition, "deprecate")
        moved = definition.deprecated(command.reason)
        return self._saved(
            context,
            moved,
            (
                CapabilityDeprecated(
                    metadata=self._metadata(context, moved),
                    **self._facts(moved),
                    reason=command.reason,
                    successor_version=command.successor_version or 0,
                ),
            ),
        )

    def revoke(self, context: Any, command: RevokeCapability) -> CommandResult:
        definition = self._load(context, command.capability_id, command.version)
        self._guard.assert_may_change(context, definition, "revoke")
        moved = definition.revoked(command.reason)
        return self._saved(
            context,
            moved,
            (
                CapabilityRevoked(
                    metadata=self._metadata(context, moved),
                    **self._facts(moved),
                    reason=command.reason,
                ),
            ),
        )

    def set_trust(self, context: Any, command: SetCapabilityTrust) -> CommandResult:
        definition = self._load(context, command.capability_id, command.version)
        self._guard.assert_may_change(context, definition, "set_trust")
        target = TrustState(command.trust)
        previous = definition.trust.value

        if target is TrustState.VERIFIED:
            moved = definition.verified(command.reason)
        elif target is TrustState.TRUSTED:
            moved = definition.trusted(command.reason)
        elif target is TrustState.QUARANTINED:
            moved = definition.quarantined(command.reason)
        elif target is TrustState.UNTRUSTED:
            moved = definition.distrusted(command.reason)
        else:
            moved = definition.released_from_quarantine(command.reason)

        return self._saved(
            context,
            moved,
            (
                CapabilityTrustChanged(
                    metadata=self._metadata(context, moved),
                    **self._facts(moved),
                    previous_trust=previous,
                    trust=moved.trust.value,
                    reason=command.reason,
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetCapability) -> CapabilityDefinition:
        return self._load(context, query.capability_id, query.version)

    def inspect_contract(self, context: Any, query: InspectContract) -> dict:
        definition = self._load(context, query.capability_id, query.version)
        return {
            "reference": definition.reference.value,
            "digest": definition.digest,
            "contract": definition.contract.to_dict(),
            "effect_declared": definition.effect_is_declared,
            "executable": definition.is_executable,
        }

    def versions(self, context: Any, query: ListVersions) -> tuple:
        found = self._repository.versions_of(
            context, CapabilityId.parse(query.capability_id)
        )
        if not found:
            raise CapabilityNotFound(query.capability_id)
        return tuple(found)

    def list(self, context: Any, query: ListCapabilities) -> tuple:
        found = list(self._repository.all(context))

        if not query.include_undiscoverable:
            found = [d for d in found if d.is_discoverable]
        if query.provider:
            found = [d for d in found if d.provider == query.provider]
        if query.interface:
            found = [d for d in found if d.contract.interface.value == query.interface]
        if query.status:
            found = [d for d in found if d.status is CapabilityStatus(query.status)]
        if query.trust:
            found = [d for d in found if d.trust is TrustState(query.trust)]
        if query.environment:
            environment = CapabilityEnvironment(query.environment)
            found = [d for d in found if d.permits_environment(environment)]
        if query.executable_only:
            found = [d for d in found if d.is_executable]
        return tuple(found)

    def executable(
        self, context: Any, reference: str
    ) -> CapabilityDefinition:
        """Fetch a capability and assert it may actually run.

        The query a future resolver calls. It exists here, rather than being
        left to the caller, so that "found it" and "may run it" cannot drift
        apart in whoever writes the resolver.
        """
        parsed = CapabilityRef.parse(reference)
        definition = self._load(
            context, parsed.capability_id.value, parsed.version.number
        )
        definition.verify_digest()
        definition.assert_executable()
        return definition
