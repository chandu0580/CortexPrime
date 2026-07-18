from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class LearningSessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class PatternCategory(str, Enum):
    MISSION = "mission"
    EXECUTION = "execution"
    CONNECTOR = "connector"
    GOVERNANCE = "governance"
    KNOWLEDGE = "knowledge"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"


class RecommendationCategory(str, Enum):
    CONNECTOR = "connector"
    TIMEOUT = "timeout"
    APPROVAL = "approval"
    RETRY = "retry"
    DEPLOYMENT = "deployment"
    RISK = "risk"
    PERFORMANCE = "performance"
    GOVERNANCE = "governance"


@dataclass
class Pattern:
    id: str = ""
    name: str = ""
    description: str = ""
    category: str = ""
    confidence: float = 0.0
    occurrences: int = 1
    pattern_data: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Recommendation:
    id: str = ""
    category: str = ""
    title: str = ""
    description: str = ""
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    priority: str = "medium"
    risk: str = "low"
    estimated_impact: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)
    related_id: Optional[str] = None
    status: str = "active"
    created_at: Optional[str] = None


@dataclass
class LearningSession:
    id: str = ""
    session_id: str = ""
    mission_type: str = ""
    status: str = "active"
    outcome: Optional[str] = None
    score: Optional[float] = None
    patterns_extracted: list[dict[str, Any]] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class LearningContext:
    mission_id: Optional[str] = None
    execution_id: Optional[str] = None
    source: str = ""
    additional: dict[str, Any] = field(default_factory=dict)


@dataclass
class LearningResult:
    session_id: str = ""
    patterns_found: list[Pattern] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    score: Optional[float] = None
    summary: str = ""
    duration_ms: Optional[float] = None


LEARNING_EVENT_TYPES: dict[str, str] = {
    "learning.session.started": "Learning session started",
    "learning.pattern.detected": "New pattern detected",
    "learning.recommendation.created": "Recommendation created",
    "learning.completed": "Learning session completed",
}
