from __future__ import annotations

import re

from backend.ai.models import IntentType


class IntentClassifier:
    RULES: list[tuple[str, IntentType]] = [
        (r"(?i)\b(create|launch|start|run|execute)\s+(a\s+)?mission", IntentType.MISSION_REQUEST),
        (r"(?i)\b(create|launch|start|run|execute)\s+(a\s+)?(plan|project|task)", IntentType.MISSION_REQUEST),
        (r"(?i)\b(deploy)\b", IntentType.MISSION_REQUEST),
        (r"(?i)\b(automate|trigger|watch|schedule)\b", IntentType.AUTOMATION),
        (r"(?i)\b(what|how|why|when|where|who|which|is|are|can|do|does|will)\b.*\?$", IntentType.QUESTION),
        (r"(?i)\b(explain|describe|tell me|define|clarify)\b", IntentType.QUESTION),
        (r"(?i)\b(analyze|analyse|evaluate|assess|review|audit)\b", IntentType.ANALYSIS),
        (r"(?i)\b(investigate|diagnose|debug|troubleshoot|root.cause)\b", IntentType.INVESTIGATION),
        (r"(?i)\b(what.happened|what went wrong|why did)\b", IntentType.INVESTIGATION),
        (r"(?i)\b(monitor)\b", IntentType.AUTOMATION),
        (r"(?i)\b(recommend|suggest|propose|advise|optimize|improve)\b", IntentType.RECOMMENDATION),
        (r"(?i)\b(invoke|use)\b.*\b(tool|api|command|function|connector)\b", IntentType.TOOL_INVOCATION),
        (r"(?i)\b(call)\b.*\b(tool|api|command|function|connector)\b", IntentType.TOOL_INVOCATION),
        (r"(?i)\b(connect|sync|integrate)\s+(to|with)\b", IntentType.TOOL_INVOCATION),
    ]

    @classmethod
    def classify(cls, prompt: str) -> IntentType:
        for pattern, intent in cls.RULES:
            if re.search(pattern, prompt):
                return intent
        return IntentType.CONVERSATION

    @classmethod
    def classify_with_confidence(cls, prompt: str) -> tuple[IntentType, float]:
        matched: list[tuple[IntentType, int]] = []
        for pattern, intent in cls.RULES:
            match = re.search(pattern, prompt)
            if match:
                matched.append((intent, len(match.group())))
        if not matched:
            return IntentType.CONVERSATION, 0.3
        matched.sort(key=lambda x: x[1], reverse=True)
        return matched[0][0], min(0.5 + (matched[0][1] / max(len(prompt), 1)) * 0.5, 1.0)


class IntentConfidence:
    def __init__(self, intent: IntentType, confidence: float, reason: str) -> None:
        self.intent = intent
        self.confidence = confidence
        self.reason = reason
