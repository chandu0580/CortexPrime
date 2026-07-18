# Deployment Strategy Intelligence

## Overview

Phase 6 of the Engineering Decision Engine. Automatically selects the optimal deployment strategy based on risk level, impact analysis, and infrastructure health.

## Strategy Decision Matrix

| Risk Level | Preferred Strategy | Confidence | Alternative |
|-----------|-------------------|------------|-------------|
| LOW | Rolling | 90% | No Deployment (5%) |
| MEDIUM | Rolling | 70% | Canary (20%) |
| HIGH | Canary | 60% | Blue/Green (20%) |
| CRITICAL | Blue/Green | 50% | Canary (30%) |

## Strategy Overrides

| Condition | Override | Confidence |
|-----------|---------|------------|
| No services affected | No Deployment | 95% |
| CRITICAL + Urgency | Hotfix | 10% |

## Deployment Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `rolling` | Gradual instance replacement | Low/Medium risk changes |
| `blue_green` | Full environment swap | Critical changes |
| `canary` | Percentage-based traffic shift | High risk, progressive exposure |
| `shadow` | Mirror traffic to new version | Observability without impact |
| `hotfix` | Bypass safeguards, fast deploy | Emergency production fixes |
| `rollback` | Revert to previous version | Failed deployments |
| `no_deployment` | Skip deployment entirely | Documentation, test-only changes |

## Implementation

Method: `EngineeringDecisionEngine._choose_deployment_strategy(risk, impact)`

Uses a ranked strategy list. Top candidate is selected based on risk level, with alternative strategies included for human decision support.

## Confidence Scoring

- Based on how well the strategy matches the risk profile
- Critical changes favor Blue/Green (highest isolation) at 50% confidence
- Low risk changes favor Rolling (fastest) at 90% confidence
- No-deployment override at 95% when no services affected

## DeploymentStrategyDecision Structure

```
DeploymentStrategyDecision
├── strategy: DeploymentStrategy
├── reasoning: str
├── confidence: float
└── evidence: List[str]
```
