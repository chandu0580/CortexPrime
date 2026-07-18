from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AttributeContext:
    user_attributes: dict[str, Any] = field(default_factory=dict)
    resource_attributes: dict[str, Any] = field(default_factory=dict)
    environment_attributes: dict[str, Any] = field(default_factory=dict)


class AttributeCondition(ABC):
    @abstractmethod
    async def evaluate(self, context: AttributeContext) -> bool:
        ...


class EqualsCondition(AttributeCondition):
    def __init__(self, attribute_path: str, expected_value: Any):
        self._path = attribute_path.split(".")
        self._expected = expected_value

    async def evaluate(self, context: AttributeContext) -> bool:
        for source in [context.user_attributes, context.resource_attributes, context.environment_attributes]:
            val = self._resolve(source, self._path)
            if val is not None:
                return val == self._expected
        return False

    def _resolve(self, data: dict, path: list[str]) -> Any:
        current = data
        for key in path:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current


class InCondition(AttributeCondition):
    def __init__(self, attribute_path: str, allowed_values: list[Any]):
        self._path = attribute_path.split(".")
        self._allowed = allowed_values

    async def evaluate(self, context: AttributeContext) -> bool:
        for source in [context.user_attributes, context.resource_attributes, context.environment_attributes]:
            val = self._resolve(source, self._path)
            if val is not None:
                return val in self._allowed
        return False

    def _resolve(self, data: dict, path: list[str]) -> Any:
        current = data
        for key in path:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current


@dataclass
class ABACRule:
    name: str
    effect: str
    conditions: list[AttributeCondition]
    description: Optional[str] = None


class ABACEvaluator:
    def __init__(self):
        self._rules: list[ABACRule] = []

    def add_rule(self, rule: ABACRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, rule_name: str) -> None:
        self._rules = [r for r in self._rules if r.name != rule_name]

    async def evaluate(self, context: AttributeContext) -> Optional[str]:
        for rule in self._rules:
            all_met = True
            for condition in rule.conditions:
                if not await condition.evaluate(context):
                    all_met = False
                    break
            if all_met:
                return rule.effect
        return None
