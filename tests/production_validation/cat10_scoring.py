"""
Category 10 — Production Scoring Engine
=========================================
Consumes all CategoryResult objects and produces:

  Reliability Score    — session stability, memory, telemetry, recovery
  Security Score       — guardrails, governance, audit completeness
  Performance Score    — latency SLA, concurrent agent success, mission throughput
  Production Readiness — weighted composite of all categories

Each score is 0–100.  The Production Readiness Score gate is:
  ≥ 90  → Production Ready
  75–89 → Needs Minor Hardening
  60–74 → Significant Gaps — Do Not Deploy
  < 60  → Not Production Ready
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tests.production_validation import CategoryResult, CheckStatus


# ---------------------------------------------------------------------------
# Score categories and their weights in the composite score
# ---------------------------------------------------------------------------

# category_name_prefix → (reliability_weight, security_weight, performance_weight)
# Each row: how much this category contributes to each pillar
_CATEGORY_WEIGHTS = {
    "01 — Long Session":          (0.30, 0.00, 0.20),
    "02 — Multi-Agent Stress":    (0.20, 0.00, 0.40),
    "03 — Voice End-to-End":      (0.10, 0.00, 0.10),
    "04 — Browser Agent":         (0.10, 0.10, 0.10),
    "05 — Computer Agent":        (0.10, 0.10, 0.10),
    "06 — Governance":            (0.10, 0.30, 0.00),
    "07 — Security":              (0.00, 0.50, 0.00),
    "08 — Research":              (0.10, 0.00, 0.10),
    "09 — Recovery":              (0.10, 0.00, 0.00),
}

# Final composite weights
_PILLAR_WEIGHTS = {
    "reliability":   0.35,
    "security":      0.35,
    "performance":   0.30,
}


@dataclass
class ProductionScore:
    reliability:   float
    security:      float
    performance:   float
    composite:     float
    grade:         str
    verdict:       str
    category_scores: Dict[str, float] = field(default_factory=dict)
    weaknesses:      List[str]        = field(default_factory=list)
    strengths:       List[str]        = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "reliability":     self.reliability,
            "security":        self.security,
            "performance":     self.performance,
            "composite":       self.composite,
            "grade":           self.grade,
            "verdict":         self.verdict,
            "category_scores": self.category_scores,
            "weaknesses":      self.weaknesses,
            "strengths":       self.strengths,
        }


def _weighted_average(category_results: List[CategoryResult], col: int) -> float:
    """
    Compute weighted average for one pillar (col index into _CATEGORY_WEIGHTS).
    Only categories that are present in results are included.
    """
    total_weight = 0.0
    total_score  = 0.0
    for cat in category_results:
        # Match by prefix
        weights = _CATEGORY_WEIGHTS.get(cat.name)
        if weights is None:
            continue
        w = weights[col]
        if w == 0.0:
            continue
        total_weight += w
        total_score  += cat.score * w
    if total_weight == 0.0:
        return 0.0
    return round(total_score / total_weight, 1)


def _find_weaknesses(category_results: List[CategoryResult]) -> List[str]:
    weaknesses = []
    for cat in category_results:
        for c in cat.checks:
            if c.status == CheckStatus.FAIL:
                weaknesses.append(f"[{cat.name}] {c.name}: {c.message}")
    return weaknesses


def _find_strengths(category_results: List[CategoryResult]) -> List[str]:
    strengths = []
    for cat in category_results:
        if cat.score >= 90.0 and cat.total > 0:
            strengths.append(f"[{cat.name}] Score {cat.score:.0f}% — {cat.passed}/{cat.total} checks passed")
    return strengths


def compute(category_results: List[CategoryResult]) -> ProductionScore:
    """Compute production scores from all category results."""
    reliability = _weighted_average(category_results, 0)
    security    = _weighted_average(category_results, 1)
    performance = _weighted_average(category_results, 2)

    composite   = round(
        reliability * _PILLAR_WEIGHTS["reliability"]
        + security  * _PILLAR_WEIGHTS["security"]
        + performance * _PILLAR_WEIGHTS["performance"],
        1,
    )

    # Grade
    if composite >= 90:
        grade   = "A"
        verdict = "Production Ready"
    elif composite >= 75:
        grade   = "B"
        verdict = "Needs Minor Hardening"
    elif composite >= 60:
        grade   = "C"
        verdict = "Significant Gaps — Do Not Deploy"
    else:
        grade   = "D"
        verdict = "Not Production Ready"

    category_scores = {cat.name: cat.score for cat in category_results}
    weaknesses      = _find_weaknesses(category_results)
    strengths       = _find_strengths(category_results)

    return ProductionScore(
        reliability     = reliability,
        security        = security,
        performance     = performance,
        composite       = composite,
        grade           = grade,
        verdict         = verdict,
        category_scores = category_scores,
        weaknesses      = weaknesses,
        strengths       = strengths,
    )
