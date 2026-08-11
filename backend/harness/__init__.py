"""The Phase 6.1 harness spine — the deterministic substrate around cognition.

The model proposes; the harness validates, budgets, records, and hands the
proposal to governance. Nothing in this package touches a provider, mints a
credential, or grants authority: the governed invocation gateway remains the
sole side-effect authority (L1), and this package's whole job is to make sure
untrusted model output arrives there schema-valid, budgeted, and traceable
(L13, L14) — or not at all.

Modules
---------
``version``       — immutable harness version identity (L15 groundwork; the
                    running harness cannot mutate its own version).
``trace``         — attribution-grade span records, redacted at construction.
``llm_boundary``  — the single model chokepoint: deterministic schema
                    validation, prompt scrubbing, normalized token usage.
``loop``          — the mission loop: budgets, typed stop reasons, and the
                    rule that the model can never declare its own success.
"""

from backend.harness.version import CURRENT_HARNESS_VERSION, HarnessVersion
from backend.harness.trace import (
    HarnessSpan,
    InMemoryTraceRecorder,
    build_model_span,
    build_action_span,
)
from backend.harness.llm_boundary import (
    GovernedModelBoundary,
    InvalidModelOutput,
    ModelInvocation,
    TokenUsage,
)
from backend.harness.loop import (
    ActionOutcome,
    HarnessLoop,
    LoopBudget,
    LoopResult,
    Observation,
    StopReason,
)
from backend.harness.llm_boundary import TraceEvidenceMissing, schema_identity
from backend.harness.firewall import (
    SecretFinding,
    assert_no_secrets,
    find_secrets,
)
from backend.harness.tool_exposure import (
    ArgKind,
    ArgSpec,
    ExposedTool,
    ResolvedTool,
    ToolExposurePolicy,
    ToolProposal,
    ToolRefusalReason,
    ToolRefused,
)

__all__ = [
    "CURRENT_HARNESS_VERSION",
    "HarnessVersion",
    "HarnessSpan",
    "InMemoryTraceRecorder",
    "build_model_span",
    "build_action_span",
    "GovernedModelBoundary",
    "InvalidModelOutput",
    "TraceEvidenceMissing",
    "schema_identity",
    "ModelInvocation",
    "TokenUsage",
    "ActionOutcome",
    "HarnessLoop",
    "LoopBudget",
    "LoopResult",
    "Observation",
    "StopReason",
    "SecretFinding",
    "find_secrets",
    "assert_no_secrets",
    "ArgKind",
    "ArgSpec",
    "ExposedTool",
    "ResolvedTool",
    "ToolExposurePolicy",
    "ToolRefusalReason",
    "ToolRefused",
    "ToolProposal",
]
