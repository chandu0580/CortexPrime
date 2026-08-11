"""Deterministic tool exposure (Part G): the model names a tool; the harness
resolves it against an explicit allowlist, or refuses — before governance.

The threat this closes
------------------------
A model proposes ``{tool, arguments}``. Nothing the model emits may become a
Python attribute lookup, an import, a URL, or a shell word. In Phase 6.1 the
"action port" was a closure, so this guarantee depended on how each closure was
written. This module makes it structural: a model-named tool is a *key into a
frozen registry*, and a key that is not present is refused. There is no
``getattr``, no ``importlib``, no string that reaches a connector — the resolver
returns a `ResolvedTool` naming a pre-declared (provider, operation) pair whose
values came from the deployment, never from the model.

Resolution is a narrowing function
-------------------------------------
The exposed set is a subset chosen at composition; a sub-agent's exposure is a
subset of its parent's. Resolution refuses, in order: unknown tool name;
argument keys the tool does not declare; missing required arguments; arguments
failing their declared kind. Each refusal happens *before* anything governed
runs, so an invalid tool never reaches the invocation gateway — the gateway is
the second line, not the first.

What this module is NOT
-------------------------
Not authorization. Whether a *known* tool may run for this principal in this
tenant is the capability fabric's decision (ADR-034), reached through the
gateway. This only decides whether the model named a tool that *exists and is
exposed*, and whether the arguments are *shaped* right — the questions that must
be answered before a governed request can even be built.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional

__all__ = [
    "ArgKind",
    "ArgSpec",
    "ExposedTool",
    "ToolExposurePolicy",
    "ResolvedTool",
    "ToolRefused",
    "ToolRefusalReason",
]


class ArgKind(str, Enum):
    """The shape an argument value must have. Deliberately small: a tool that
    needs richer validation declares it downstream (the provider catalog's
    ``ParameterSpec`` is the authoritative input contract at the gateway); this
    is the pre-governance shape check, not a schema engine."""

    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    STRING_LIST = "string_list"


@dataclass(frozen=True)
class ArgSpec:
    name: str
    kind: ArgKind
    required: bool = True
    max_length: Optional[int] = None

    def problem(self, value: Any) -> Optional[str]:
        """Why ``value`` is not acceptable for this argument, or None."""
        if self.kind is ArgKind.STRING:
            if not isinstance(value, str):
                return f"{self.name} must be a string"
            if self.max_length is not None and len(value) > self.max_length:
                return f"{self.name} exceeds {self.max_length} characters"
        elif self.kind is ArgKind.INTEGER:
            # bool is an int subclass; a boolean is not an integer argument.
            if not isinstance(value, int) or isinstance(value, bool):
                return f"{self.name} must be an integer"
        elif self.kind is ArgKind.BOOLEAN:
            if not isinstance(value, bool):
                return f"{self.name} must be a boolean"
        elif self.kind is ArgKind.STRING_LIST:
            if not isinstance(value, (list, tuple)) or not all(
                isinstance(v, str) for v in value
            ):
                return f"{self.name} must be a list of strings"
            if self.max_length is not None and any(
                len(v) > self.max_length for v in value
            ):
                return f"an entry of {self.name} exceeds {self.max_length} characters"
        return None


@dataclass(frozen=True)
class ExposedTool:
    """One tool the model may name, bound to a pre-declared provider operation.

    ``provider`` and ``operation`` are deployment values. The model supplies
    neither — it supplies only ``name``, which selects this record.
    """

    name: str
    provider: str
    operation: str
    arguments: tuple[ArgSpec, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or not self.provider or not self.operation:
            raise ValueError("an exposed tool needs a name, provider and operation")

    @property
    def arg_names(self) -> frozenset[str]:
        return frozenset(a.name for a in self.arguments)


class ToolRefusalReason(str, Enum):
    UNKNOWN_TOOL = "unknown_tool"
    UNDECLARED_ARGUMENT = "undeclared_argument"
    MISSING_ARGUMENT = "missing_argument"
    MALFORMED_ARGUMENT = "malformed_argument"
    MALFORMED_REQUEST = "malformed_request"


@dataclass(frozen=True)
class ToolRefused:
    reason: ToolRefusalReason
    detail: str
    tool_name: Optional[str] = None

    @property
    def refused(self) -> bool:
        return True


@dataclass(frozen=True)
class ResolvedTool:
    """A model request that resolved to a known tool with well-shaped args.
    Carries the *deployment's* provider/operation, never the model's."""

    tool: ExposedTool
    arguments: Mapping[str, Any]

    @property
    def refused(self) -> bool:
        return False

    @property
    def provider(self) -> str:
        return self.tool.provider

    @property
    def operation(self) -> str:
        return self.tool.operation


@dataclass(frozen=True)
class ToolExposurePolicy:
    """The frozen set of tools a model may name in one context.

    Immutable, and identity-stable: two policies with the same tools resolve
    the same requests. A narrower context is built with :meth:`narrowed`, never
    by mutation."""

    tools: tuple[ExposedTool, ...] = ()

    def __post_init__(self) -> None:
        names = [t.name for t in self.tools]
        if len(names) != len(set(names)):
            raise ValueError("a tool name is exposed twice; exposure must be unambiguous")

    @property
    def _by_name(self) -> dict[str, ExposedTool]:
        return {t.name: t for t in self.tools}

    @property
    def exposed_names(self) -> frozenset[str]:
        return frozenset(t.name for t in self.tools)

    def narrowed(self, names) -> "ToolExposurePolicy":
        """A sub-policy exposing only ``names`` — and only names already
        exposed here. Widening is impossible: an unknown name is dropped, never
        added, because a sub-agent that could name a tool its parent could not
        would be an escalation."""
        wanted = set(names)
        return ToolExposurePolicy(
            tuple(t for t in self.tools if t.name in wanted)
        )

    def resolve(self, request: Any):
        """Resolve one model-proposed ``{tool, arguments}`` to a `ResolvedTool`
        or a `ToolRefused`. Deterministic; never raises on bad model input."""
        if not isinstance(request, Mapping):
            return ToolRefused(
                ToolRefusalReason.MALFORMED_REQUEST,
                "a tool request must be an object with 'tool' and 'arguments'",
            )
        name = request.get("tool")
        args = request.get("arguments", {})
        if not isinstance(name, str) or not name:
            return ToolRefused(
                ToolRefusalReason.MALFORMED_REQUEST, "'tool' must be a non-empty string"
            )
        if not isinstance(args, Mapping):
            return ToolRefused(
                ToolRefusalReason.MALFORMED_REQUEST,
                "'arguments' must be an object", tool_name=name,
            )

        tool = self._by_name.get(name)
        if tool is None:
            # The load-bearing refusal: an unknown tool name is not looked up,
            # not fuzzy-matched, not imported. It is simply absent.
            return ToolRefused(
                ToolRefusalReason.UNKNOWN_TOOL,
                f"no tool named {name!r} is exposed in this context",
                tool_name=name,
            )

        undeclared = set(args) - tool.arg_names
        if undeclared:
            return ToolRefused(
                ToolRefusalReason.UNDECLARED_ARGUMENT,
                f"{name} does not declare argument(s): {sorted(undeclared)}",
                tool_name=name,
            )
        for spec in tool.arguments:
            if spec.name not in args:
                if spec.required:
                    return ToolRefused(
                        ToolRefusalReason.MISSING_ARGUMENT,
                        f"{name} requires argument {spec.name!r}",
                        tool_name=name,
                    )
                continue
            problem = spec.problem(args[spec.name])
            if problem is not None:
                return ToolRefused(
                    ToolRefusalReason.MALFORMED_ARGUMENT, problem, tool_name=name,
                )

        return ResolvedTool(tool=tool, arguments=dict(args))
