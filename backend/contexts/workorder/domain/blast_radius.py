"""The blast radius value object.

A value object, not an entity: no identity, no lifecycle, no existence apart
from the WorkOrder version containing it. Treating it as an entity would let a
radius be referenced and superseded independently of the WorkOrder that
authorised it, which is how work ends up running against a radius nobody
approved.

Three sets, and ``forbidden`` always wins:

    allowed     may be modified
    forbidden   may not be modified, even where an ``allowed`` pattern matches
    read_only   may be read beyond the context bundle, never written

``forbidden`` exists because ``allowed`` alone cannot express the common case.
*"You may change the platform package, except the architecture gate inside it"*
requires subtraction. Without it the Architect either grants too much or
enumerates a dozen sibling patterns, and enumerations drift as the tree changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = [
    "BlastRadius",
    "PathPattern",
    "MAX_FILES_WITHOUT_JUSTIFICATION",
    "MAX_PACKAGES_WITHOUT_JUSTIFICATION",
]

#: Thresholds above which the Architect must justify the scope (Spec §7.2 V5).
MAX_FILES_WITHOUT_JUSTIFICATION = 20
MAX_PACKAGES_WITHOUT_JUSTIFICATION = 3


def _normalise(pattern: str) -> str:
    """Repository-relative, forward slashes, no trailing separator."""
    cleaned = pattern.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.rstrip("/") if cleaned not in ("", "/") else cleaned


def _compile(pattern: str) -> re.Pattern:
    """Translate a path pattern to a regex.

    ``**`` crosses separators; ``*`` and ``?`` do not. Written by hand rather
    than delegated to :mod:`fnmatch`, which has no notion of ``**`` and would
    quietly let ``backend/*`` match ``backend/a/b/c.py``.
    """
    out: list[str] = ["^"]
    index = 0
    length = len(pattern)
    while index < length:
        # A trailing `/**` also matches the directory itself: `backend/a/**`
        # covers `backend/a`. Requiring the separator would exclude the very
        # directory the pattern names.
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


def _literal_prefix(pattern: str) -> tuple[str, ...]:
    """The path segments before the first wildcard.

    Used for conflict detection. Everything after the first wildcard could
    expand to anything, so only the literal head constrains what a pattern can
    match.
    """
    segments: list[str] = []
    for segment in pattern.split("/"):
        if any(ch in segment for ch in "*?["):
            break
        segments.append(segment)
    return tuple(segments)


def _is_segment_prefix(shorter: tuple[str, ...], longer: tuple[str, ...]) -> bool:
    """Whether ``shorter`` is a segment-wise prefix of ``longer``.

    Segment-wise rather than string-wise. A raw string comparison would call
    ``backend/b`` a prefix of ``backend/bc.py`` and report a conflict between two
    genuinely disjoint patterns.
    """
    return len(shorter) <= len(longer) and longer[: len(shorter)] == shorter


def _patterns_may_intersect(left: str, right: str) -> bool:
    """Conservative: true unless the two are provably disjoint.

    A false conflict costs serialised work. A false non-conflict costs two
    agents editing the same file concurrently and a corrupted merge. The
    asymmetry decides the default.
    """
    left_prefix = _literal_prefix(left)
    right_prefix = _literal_prefix(right)
    return _is_segment_prefix(left_prefix, right_prefix) or _is_segment_prefix(
        right_prefix, left_prefix
    )


@dataclass(frozen=True, order=True)
class PathPattern:
    """One repository path expression."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ContractViolation(
                f"path pattern must be a string, got {type(self.value).__name__}"
            )
        normalised = _normalise(self.value)
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
        return bool(_compile(self.value).match(_normalise(path)))

    @property
    def top_level(self) -> str:
        return self.value.split("/", 1)[0]

    def may_intersect(self, other: "PathPattern") -> bool:
        return _patterns_may_intersect(self.value, other.value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class BlastRadius(Contract):
    """The set of paths a WorkOrder may touch."""

    CONTRACT_NAME = "cortexprime.engineering.blast_radius"

    allowed: frozenset = field(default_factory=frozenset)
    forbidden: frozenset = field(default_factory=frozenset)
    read_only: frozenset = field(default_factory=frozenset)
    justification: Optional[str] = None

    def __post_init__(self) -> None:
        for label, value in (
            ("allowed", self.allowed),
            ("forbidden", self.forbidden),
            ("read_only", self.read_only),
        ):
            if not isinstance(value, (frozenset, set)):
                raise ContractViolation(f"{label} must be a set of PathPattern")
            for item in value:
                if not isinstance(item, PathPattern):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a PathPattern"
                    )
            object.__setattr__(self, label, frozenset(value))

        # V1 -- an empty allowed set authorises nothing, which is not a scope
        # but the absence of one.
        if not self.allowed:
            raise ContractViolation("blast radius must allow at least one path pattern")

        # V4 -- a path cannot be both writable and read-only.
        for writable in self.allowed:
            for readable in self.read_only:
                if writable.may_intersect(readable):
                    raise ContractViolation(
                        f"blast radius pattern {writable} is in both allowed and read_only"
                    )

        if self.justification is not None:
            if not isinstance(self.justification, str) or not self.justification.strip():
                raise ContractViolation("justification, when present, must be non-blank text")

        if self.requires_justification and not self.justification:
            raise ContractViolation(
                f"a blast radius spanning {len(self.top_level_packages)} top-level packages "
                f"exceeds the limit of {MAX_PACKAGES_WITHOUT_JUSTIFICATION} and requires a "
                "justification"
            )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def of(
        cls,
        allowed: Iterable[str],
        *,
        forbidden: Iterable[str] = (),
        read_only: Iterable[str] = (),
        justification: Optional[str] = None,
    ) -> "BlastRadius":
        """Build from plain strings. The ergonomic path for callers."""
        return cls(
            allowed=frozenset(PathPattern(p) for p in allowed),
            forbidden=frozenset(PathPattern(p) for p in forbidden),
            read_only=frozenset(PathPattern(p) for p in read_only),
            justification=justification,
        )

    # ------------------------------------------------------------------
    # Shape
    # ------------------------------------------------------------------

    @property
    def top_level_packages(self) -> frozenset:
        return frozenset(p.top_level for p in self.allowed)

    @property
    def requires_justification(self) -> bool:
        """Whether the scope is wide enough to need explaining.

        Only the package count is decidable from the patterns alone. The file
        count needs the repository and is checked by
        :meth:`validate_against_paths`.
        """
        return len(self.top_level_packages) > MAX_PACKAGES_WITHOUT_JUSTIFICATION

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def forbids(self, path: str) -> bool:
        return any(pattern.matches(path) for pattern in self.forbidden)

    def permits_write(self, path: str) -> bool:
        """Whether a path may be modified.

        ``forbidden`` is checked first and wins. Ambiguity resolves to refusal.
        """
        if self.forbids(path):
            return False
        return any(pattern.matches(path) for pattern in self.allowed)

    def permits_read(self, path: str) -> bool:
        if self.permits_write(path):
            return True
        return any(pattern.matches(path) for pattern in self.read_only)

    def refusal_reason(self, path: str) -> Optional[str]:
        """Why a write to ``path`` is refused, or ``None`` if it is permitted."""
        if self.forbids(path):
            return "is explicitly forbidden by the declared blast radius"
        if not any(pattern.matches(path) for pattern in self.allowed):
            return "is outside the declared blast radius"
        return None

    def excess(self, paths: Iterable[str]) -> tuple:
        """Every path in ``paths`` this radius does not permit writing."""
        return tuple(sorted(p for p in paths if not self.permits_write(p)))

    def untouched_patterns(self, paths: Iterable[str]) -> tuple:
        """Allowed patterns that no supplied path matches.

        A declared-but-untouched pattern is a review finding: the radius claimed
        more than the work needed, which weakens conflict detection for everyone
        else.
        """
        materialised = list(paths)
        return tuple(
            sorted(
                str(pattern)
                for pattern in self.allowed
                if not any(pattern.matches(p) for p in materialised)
            )
        )

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def conflicts_with(self, other: "BlastRadius") -> bool:
        """Whether two radii could contend for the same path.

        Only writable sets contend. Two WorkOrders may read the same paths
        concurrently without risk; only concurrent writes corrupt.
        """
        return any(
            mine.may_intersect(theirs) for mine in self.allowed for theirs in other.allowed
        )

    def conflicting_patterns(self, other: "BlastRadius") -> tuple:
        """The specific pattern pairs that conflict, for a useful refusal."""
        return tuple(
            sorted(
                (str(mine), str(theirs))
                for mine in self.allowed
                for theirs in other.allowed
                if mine.may_intersect(theirs)
            )
        )

    # ------------------------------------------------------------------
    # Repository-dependent validation
    # ------------------------------------------------------------------

    def validate_against_paths(self, repository_paths: Iterable[str]) -> tuple:
        """Checks that need the repository: V2 and the file half of V5.

        Returns detail strings rather than raising. These are validation
        findings for the Architect to act on, not domain invariants -- the same
        radius is legitimately empty against one commit and full against
        another, so a hard failure here would be wrong.
        """
        paths = list(repository_paths)
        findings: list[str] = []

        for pattern in sorted(self.allowed, key=str):
            if not any(pattern.matches(p) for p in paths):
                findings.append(
                    f"allowed pattern {pattern} matches no existing path; declare it as "
                    "creating new paths, or remove it"
                )

        matched = {p for p in paths if self.permits_write(p)}
        if len(matched) > MAX_FILES_WITHOUT_JUSTIFICATION and not self.justification:
            findings.append(
                f"blast radius matches {len(matched)} files, above the limit of "
                f"{MAX_FILES_WITHOUT_JUSTIFICATION}, and carries no justification"
            )

        return tuple(findings)
