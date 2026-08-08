"""Blast-radius containment, enforced here.

A deliberate duplication, and the reasoning matters
----------------------------------------------------
PR-E4's ContextBundle *records* a blast radius without matching against it,
because a second copy of security-relevant matching logic would drift from the
first with nothing to catch the drift.

Here the rule is different: **changed files must remain within the WorkOrder's
blast radius**, and enforcing that requires matching. Accepting a pre-computed
verdict from the caller would put the check in the one place least able to be
held to it -- the caller is the party the check exists to constrain.

So the matcher is duplicated, and the duplication is made safe the way PR-E2 made
the phase vocabulary safe: with a drift test. ``test_paths.py`` runs both this
matcher and the WorkOrder context's ``BlastRadius`` over a shared corpus of
pattern/path pairs and asserts they agree. Duplication with a checked invariant
beats duplication without one, and both beat a check the caller performs on
itself.

Semantics, matching the WorkOrder context exactly::

    a/**      matches a, a/b, a/b/c        (trailing ** covers the directory)
    a/**/b    matches a/b, a/x/b           (** crosses separators, zero or more)
    a/*       matches a/b but not a/b/c    (single star stops at a separator)
    a/?.py    matches a/x.py               (single character, not a separator)

``forbidden`` always beats ``allowed``. Ambiguity resolves to refusal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = ["normalise_path", "PathPattern", "BlastRadiusScope"]


def normalise_path(value: str) -> str:
    """Repository-relative, forward slashes, no trailing separator."""
    cleaned = value.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.rstrip("/") if cleaned not in ("", "/") else cleaned


def _compile(pattern: str) -> re.Pattern:
    """Translate a path pattern to a regex.

    Written by hand rather than delegated to :mod:`fnmatch`, which has no notion
    of ``**`` and would quietly let ``backend/*`` match ``backend/a/b/c.py``.
    """
    out: list[str] = ["^"]
    index = 0
    length = len(pattern)
    while index < length:
        # A trailing `/**` also matches the directory itself: `a/**` covers `a`.
        if pattern[index : index + 3] == "/**" and index + 3 == length:
            out.append("(?:/.*)?")
            index += 3
            continue
        # `**/` matches zero or more directories, so `a/**/b` covers `a/b`.
        if pattern[index : index + 3] == "**/":
            out.append("(?:.*/)?")
            index += 3
            continue
        if pattern[index : index + 2] == "**":
            out.append(".*")
            index += 2
            continue

        char = pattern[index]
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        index += 1
    out.append("$")
    return re.compile("".join(out))


@dataclass(frozen=True, order=True)
class PathPattern:
    """One repository path expression."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ContractViolation(
                f"path pattern must be a string, got {type(self.value).__name__}"
            )
        normalised = normalise_path(self.value)
        if not normalised:
            raise ContractViolation("path pattern must not be blank")
        if normalised.startswith("/"):
            raise ContractViolation(
                f"path pattern {self.value!r} must be repository-relative, not absolute"
            )
        if ".." in normalised.split("/"):
            raise ContractViolation(
                f"path pattern {self.value!r} must not traverse upward with '..'"
            )
        object.__setattr__(self, "value", normalised)

    def matches(self, path: str) -> bool:
        return bool(_compile(self.value).match(normalise_path(path)))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class BlastRadiusScope(Contract):
    """The WorkOrder's declared scope, as this context sees it.

    Carries the patterns *and* the matcher, because the containment rule cannot
    be enforced without both.
    """

    CONTRACT_NAME = "cortexprime.engineering.implementation_blast_radius"

    allowed: frozenset = frozenset()
    forbidden: frozenset = frozenset()
    read_only: frozenset = frozenset()

    def __post_init__(self) -> None:
        for label in ("allowed", "forbidden", "read_only"):
            value = getattr(self, label)
            if not isinstance(value, (frozenset, set)):
                raise ContractViolation(f"{label} must be a set of PathPattern")
            for item in value:
                if not isinstance(item, PathPattern):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a PathPattern"
                    )
            object.__setattr__(self, label, frozenset(value))

        if not self.allowed:
            raise ContractViolation(
                "a blast radius that allows nothing authorises nothing; that is the "
                "absence of a scope, not a narrow one"
            )

    @classmethod
    def of(
        cls,
        allowed: Iterable[str],
        *,
        forbidden: Iterable[str] = (),
        read_only: Iterable[str] = (),
    ) -> "BlastRadiusScope":
        return cls(
            allowed=frozenset(PathPattern(p) for p in allowed),
            forbidden=frozenset(PathPattern(p) for p in forbidden),
            read_only=frozenset(PathPattern(p) for p in read_only),
        )

    # ------------------------------------------------------------------

    def forbids(self, path: str) -> bool:
        return any(pattern.matches(path) for pattern in self.forbidden)

    def permits_write(self, path: str) -> bool:
        """``forbidden`` is checked first and wins. Ambiguity resolves to refusal."""
        if self.forbids(path):
            return False
        return any(pattern.matches(path) for pattern in self.allowed)

    def refusal_reason(self, path: str) -> Optional[str]:
        """Why writing to ``path`` is refused, or ``None`` if it is permitted.

        The two reasons need different responses. Outside the radius means the
        scope was predicted wrongly and should be expanded through re-approval.
        Forbidden means the Architect ruled it out on purpose, and expanding is
        the wrong answer.
        """
        if self.forbids(path):
            return "is explicitly forbidden by the declared blast radius"
        if not any(pattern.matches(path) for pattern in self.allowed):
            return "is outside the declared blast radius"
        return None

    def excess(self, paths: Iterable[str]) -> tuple:
        """Every path this scope does not permit writing."""
        return tuple(sorted(p for p in paths if not self.permits_write(p)))

    def untouched_patterns(self, paths: Iterable[str]) -> tuple:
        """Allowed patterns no supplied path matches.

        A declared-but-untouched pattern means the radius claimed more than the
        work needed, which weakens conflict detection for every other WorkOrder.
        """
        materialised = list(paths)
        return tuple(
            sorted(
                str(pattern)
                for pattern in self.allowed
                if not any(pattern.matches(p) for p in materialised)
            )
        )

    @property
    def allowed_patterns(self) -> tuple:
        return tuple(sorted(str(p) for p in self.allowed))
