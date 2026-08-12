"""Intelligence application layer — the investigation service and its ports.

Depends on the intelligence/world/epistemic contracts and the platform secret
detector only. It does not import a database, a connector, a provider SDK, the
gateway, or the execution plane — composition supplies the repository, and the
model boundary/world-read are ports.
"""

from backend.intelligence.application.investigation_service import (
    AutonomyRefused,
    InvestigationConcurrencyError,
    InvestigationNotFound,
    InvestigationRejected,
    InvestigationRepository,
    InvestigationService,
    InvestigationTransitionRefused,
)
from backend.intelligence.application.context import (
    AssembledContext,
    ContextAssembler,
    ContextBudget,
    ContextSection,
    SECTION_ORDER,
)
from backend.intelligence.application.proposal import (
    EvidenceAcquisitionPort,
    EvidenceRequest,
    EvidenceResult,
    EvidenceSelectionPolicy,
    InvestigationProposal,
    ModelProposalFailed,
    ModelProposalPort,
    ModelProviderUnavailable,
    ModelSchemaRejected,
    ModelTraceUnavailable,
    ProposedHypothesis,
    ProposedTest,
    TestRejected,
    ValidatedTest,
    WorldReadPort,
    test_identity,
)
from backend.intelligence.application.model_boundary import (
    GovernedModelProposalPort,
    INVESTIGATION_SYSTEM_PROMPT,
    InvestigationProposalSchema,
    ScriptedModelPort,
)
from backend.intelligence.application.engine import (
    InvestigationBudget,
    InvestigationEngine,
    StepOutcome,
    StepResult,
)

__all__ = [
    # 8.1 state machine
    "InvestigationService",
    "InvestigationRepository",
    "InvestigationRejected",
    "InvestigationTransitionRefused",
    "AutonomyRefused",
    "InvestigationNotFound",
    "InvestigationConcurrencyError",
    # 8.2 context assembly
    "ContextAssembler",
    "AssembledContext",
    "ContextSection",
    "ContextBudget",
    "SECTION_ORDER",
    # 8.2 proposals / ports / policy
    "InvestigationProposal",
    "ProposedHypothesis",
    "ProposedTest",
    "EvidenceRequest",
    "EvidenceResult",
    "ValidatedTest",
    "TestRejected",
    "EvidenceSelectionPolicy",
    "ModelProposalPort",
    "WorldReadPort",
    "EvidenceAcquisitionPort",
    "test_identity",
    # 8.3 model boundary
    "GovernedModelProposalPort",
    "ScriptedModelPort",
    "InvestigationProposalSchema",
    "INVESTIGATION_SYSTEM_PROMPT",
    "ModelProposalFailed",
    "ModelSchemaRejected",
    "ModelTraceUnavailable",
    "ModelProviderUnavailable",
    # 8.2 engine
    "InvestigationEngine",
    "InvestigationBudget",
    "StepOutcome",
    "StepResult",
]
