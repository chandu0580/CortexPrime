"""CortexPrime contracts -- the shared language of the platform.

This package defines the vocabulary every bounded context uses to speak to every
other bounded context. It is the only package in the codebase that every other
package is permitted to depend on, which is only safe because it depends on
nothing itself.

What contracts are
------------------
Immutable, versioned, transport-neutral value types with validation. Nothing
more.

What contracts are forbidden from doing
---------------------------------------
No business logic. No persistence. No I/O. No infrastructure. No framework
types. No imports outside the Python standard library. A contract that reaches
out to do something is no longer a contract -- it is a service wearing one as a
disguise, and the dependency rule that makes this package safe collapses.

The single permitted exception to "no logic" is *validation of the value's own
invariants* in ``__post_init__``, plus small derived properties over the value's
own fields (``is_terminal``, ``can_approve``). These stay because putting them
anywhere else guarantees the rule gets restated inconsistently in several places.

Usage
-----
    from backend.contracts import ExecutionContract, SideEffectClass

    contract = ExecutionContract(
        execution_key="restart-web-01",
        action=ActionRef("docker.restart", {"container": "web-01"}),
        scope=ExecutionScope("docker", ("web-01",), "production"),
        side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
        inverse=ActionRef("docker.restart", {"container": "web-01"}),
        verification_criteria=("container is running", "no restart within 5m"),
    )
    wire = contract.to_dict()
    restored = ExecutionContract.from_dict(wire)

See ``docs/contracts/README.md`` for versioning rules and ``docs/adr/ADR-010``
for why this package exists in this form.
"""

from __future__ import annotations

from backend.contracts._contract import (
    ENVELOPE_CONTRACT_KEY,
    ENVELOPE_VERSION_KEY,
    Contract,
    contract_registry,
    decode_envelope,
    freeze_mapping,
)
from backend.contracts.approval import (
    ApprovalArtifact,
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    HashAlgorithm,
    PayloadDigest,
)
from backend.contracts.audit import (
    GENESIS_PREVIOUS_DIGEST,
    AuditEvent,
    AuditEventKind,
)
from backend.contracts.configuration import (
    ConfigurationSource,
    DeclarationSet,
    EnvironmentDeclaration,
    ResourceDeclaration,
)
from backend.contracts.connector import (
    ConnectorCapabilities,
    ConnectorHealth,
    ConnectorRef,
    IsolationTier,
    ToolDescriptor,
)
from backend.contracts.errors import ContractViolation, ContractVersionError
from backend.contracts.evidence import (
    Citation,
    EvidenceItem,
    EvidenceKind,
    EvidenceSet,
    SourceOutcome,
    SourceStatus,
)
from backend.contracts.credential import (
    CredentialRef,
    CredentialScope,
    CredentialState,
    CredentialType,
)
from backend.contracts.transport import (
    ConnectionRef,
    ConnectionState,
    TransportFailure,
    TransportKind,
)
from backend.contracts.provider import (
    ADAPTER_METRICS,
    AdapterRef,
    ProviderDelivery,
    ProviderFailure,
    ProviderRef,
)
from backend.contracts.execution import (
    ActionRef,
    ExecutionContract,
    ExecutionEnvironment,
    ExecutionResult,
    ExecutionScope,
    ExecutionStatus,
    SideEffectClass,
)
from backend.contracts.identity import PrincipalKind, PrincipalRef, SecurityContext
from backend.contracts.knowledge import (
    AssembledContext,
    KnowledgeAuthority,
    KnowledgeItem,
    KnowledgeKind,
)
from backend.contracts.mission import (
    LEGAL_TRANSITIONS,
    MissionIntent,
    MissionRef,
    MissionState,
    MissionTransition,
    TaskRef,
    TaskState,
    is_legal_transition,
)
from backend.contracts.policy import (
    Obligation,
    ObligationKind,
    PolicyDecision,
    PolicyEffect,
    RiskClassification,
    RiskFactors,
    RiskLevel,
)
from backend.contracts.storage import (
    StorageAccess,
    StorageBinding,
    StorageOperation,
)
from backend.contracts.tenant import (
    OrganizationRef,
    ProjectRef,
    TenantRef,
    TenantScope,
)
from backend.contracts.verification import (
    Verdict,
    VerificationResult,
    VerificationTarget,
    VerifierIdentity,
)

#: Version of the contracts package as a whole. Individual contracts carry their
#: own ``CONTRACT_VERSION``; this identifies the vocabulary release.
CONTRACTS_PACKAGE_VERSION = "1.0.0"

__all__ = [
    "CONTRACTS_PACKAGE_VERSION",
    # base
    "Contract",
    "ENVELOPE_CONTRACT_KEY",
    "ENVELOPE_VERSION_KEY",
    "contract_registry",
    "decode_envelope",
    "freeze_mapping",
    # errors
    "ContractViolation",
    "ContractVersionError",
    # tenant
    "TenantRef",
    "OrganizationRef",
    "ProjectRef",
    "TenantScope",
    # storage boundary
    "StorageOperation",
    "StorageBinding",
    "StorageAccess",
    # identity
    "PrincipalKind",
    "PrincipalRef",
    "SecurityContext",
    # mission
    "MissionState",
    "MissionRef",
    "MissionIntent",
    "MissionTransition",
    "TaskState",
    "TaskRef",
    "LEGAL_TRANSITIONS",
    "is_legal_transition",
    # execution
    "SideEffectClass",
    "ExecutionStatus",
    "ExecutionScope",
    "ExecutionEnvironment",
    "CredentialRef",
    "CredentialScope",
    "CredentialState",
    "CredentialType",
    "TransportKind",
    "ConnectionState",
    "TransportFailure",
    "ConnectionRef",
    "ProviderRef",
    "AdapterRef",
    "ProviderFailure",
    "ProviderDelivery",
    "ADAPTER_METRICS",
    "ActionRef",
    "ExecutionContract",
    "ExecutionResult",
    # approval
    "HashAlgorithm",
    "ApprovalOutcome",
    "PayloadDigest",
    "ApprovalArtifact",
    "ApprovalRequest",
    "ApprovalDecision",
    # policy
    "RiskLevel",
    "PolicyEffect",
    "ObligationKind",
    "Obligation",
    "RiskFactors",
    "RiskClassification",
    "PolicyDecision",
    # configuration
    "ConfigurationSource",
    "ResourceDeclaration",
    "EnvironmentDeclaration",
    "DeclarationSet",
    # evidence
    "EvidenceKind",
    "SourceStatus",
    "Citation",
    "EvidenceItem",
    "SourceOutcome",
    "EvidenceSet",
    # knowledge
    "KnowledgeKind",
    "KnowledgeAuthority",
    "KnowledgeItem",
    "AssembledContext",
    # verification
    "Verdict",
    "VerificationTarget",
    "VerifierIdentity",
    "VerificationResult",
    # audit
    "AuditEventKind",
    "AuditEvent",
    "GENESIS_PREVIOUS_DIGEST",
    # connector
    "ConnectorHealth",
    "IsolationTier",
    "ConnectorRef",
    "ToolDescriptor",
    "ConnectorCapabilities",
]
