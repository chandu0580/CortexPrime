# Decision Explainability

## Overview

Phase 10 of the Engineering Decision Engine. Every engineering decision includes a complete explanation of WHY it was made, including all factors, evidence chain, confidence level, and alternatives considered.

## Explanation Structure

```
WHY: "Change involves 2 category(ies): backend, secrets. 
      Risk assessed at 72/100 (high). 
      Approval required from: engineering, security. 
      Deploying via canary (60% confidence). 
      Pipeline: High risk — full pipeline with all safeguards."

Factors:
├── backend (35/100) — Backend code changes
├── secrets (85/100) — Secret/credential changes
├── keyword:payment (90/100) — Payment processing
└── keyword:secret (85/100) — Secret or sensitive value

Evidence Chain:
├── Step 1: change_detection — 2 files changed → [backend, secrets]
├── Step 2: impact_analysis — 5 entities affected → [payment-service]
├── Step 3: risk_assessment — Risk score 72/100 → high
├── Step 4: execution_planning — Full pipeline with safeguards → []
├── Step 5: approval_determination — Approval required → [engineering, security]
└── Step 6: deployment_strategy — canary → 60%

Confidence: 60%
Alternatives:
├── Full pipeline (rolling)
└── blue_green deployment
```

## Evidence Chain

The evidence chain traces the complete reasoning path:

1. **Change Detection** — What files changed and their categories
2. **Impact Analysis** — What entities are affected and which services
3. **Risk Assessment** — Risk score, level, and contributing factors
4. **Execution Planning** — Which stages run, which are skipped
5. **Approval Determination** — Whether approval is needed and from whom
6. **Deployment Strategy** — Selected strategy and confidence level

## Confidence

Overall confidence reflects the deployment strategy confidence. Sources of uncertainty:
- Code Intelligence unavailability (falls back to basic classification)
- Learning Engine unavailability (no past failure data)
- Incomplete repository scan

## DecisionExplanation Structure

```
DecisionExplanation
├── why: str — human-readable explanation
├── factors: List[Dict] — each factor has name, contribution, reason
├── evidence_chain: List[Dict] — step-by-step reasoning trace
├── confidence: float — overall confidence score
└── alternatives: List[str] — alternative strategies considered
```

## Tracing

Every decision is also traced through:
- **EventHub** — `engineering.decision_made` event emitted
- **MissionReplayStore** — Full decision report recorded as replay event
- **Knowledge Graph** — Decision and risk entities with relationships
- **RuntimeStore** — Decision report persisted as an execution record
