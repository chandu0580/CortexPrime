"""The code that changed.

``ChangedFile`` records one path and what happened to it. ``CodeChangeSet``
groups them against a repository revision.

Why a change set names its revision
------------------------------------
A diff without a base is a list of paths. The same paths against a different
commit describe a different change, and a reviewer told only "these files
changed" cannot tell whether they are reading the change that was submitted.

Why line counts are recorded but never load-bearing
----------------------------------------------------
``added``/``removed`` are useful for a reviewer sizing a diff, and useless as a
gate: a rule keyed on them optimises for small diffs rather than correct ones,
and the first response to such a rule is to split a change across two PRs that
each pass. They are reported and never checked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.implementation_record.domain.errors import OutsideBlastRadius
from backend.contexts.implementation_record.domain.paths import (
    BlastRadiusScope,
    normalise_path,
)

__all__ = ["ChangeKind", "ChangedFile", "CodeChangeSet"]


class ChangeKind(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"

    @property
    def requires_content_digest(self) -> bool:
        """A deleted file has no content to digest.

        Recording a digest for one would be recording the hash of something that
        is no longer there.
        """
        return self is not ChangeKind.DELETED

    @property
    def requires_previous_path(self) -> bool:
        return self is ChangeKind.RENAMED


@dataclass(frozen=True, order=True)
class ChangedFile(Contract):
    """One file, and what happened to it."""

    CONTRACT_NAME = "cortexprime.engineering.changed_file"

    path: str
    kind: ChangeKind
    content_digest: Optional[str] = None
    previous_path: Optional[str] = None
    lines_added: int = 0
    lines_removed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path.strip():
            raise ContractViolation("a changed file must name a path")
        normalised = normalise_path(self.path)
        if not normalised or normalised.startswith("/"):
            raise ContractViolation(
                f"{self.path!r} must be repository-relative, not absolute"
            )
        if ".." in normalised.split("/"):
            raise ContractViolation(f"{self.path!r} must not traverse upward with '..'")
        object.__setattr__(self, "path", normalised)

        if not isinstance(self.kind, ChangeKind):
            raise ContractViolation("kind must be a ChangeKind")

        if self.kind.requires_content_digest and not self.content_digest:
            raise ContractViolation(
                f"{self.path!r} was {self.kind.value} and must record the digest of what "
                "it now contains; without it a reviewer cannot tell whether the file "
                "changed again after submission"
            )
        if not self.kind.requires_content_digest and self.content_digest:
            raise ContractViolation(
                f"{self.path!r} was deleted and has no content to digest"
            )

        if self.kind.requires_previous_path:
            if not self.previous_path or not self.previous_path.strip():
                raise ContractViolation(
                    f"{self.path!r} was renamed and must record where it came from; a "
                    "rename recorded as an add plus a delete loses the history"
                )
            object.__setattr__(self, "previous_path", normalise_path(self.previous_path))
        elif self.previous_path:
            raise ContractViolation(
                f"{self.path!r} was {self.kind.value}, not renamed, so it has no "
                "previous path"
            )

        for label, value in (
            ("lines_added", self.lines_added),
            ("lines_removed", self.lines_removed),
        ):
            if not isinstance(value, int) or value < 0:
                raise ContractViolation(f"{label} must be a non-negative integer")

    @property
    def paths_touched(self) -> tuple:
        """Both ends of a rename. Both must be inside the blast radius."""
        if self.previous_path:
            return (self.path, self.previous_path)
        return (self.path,)

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.kind.value}:{self.path}"


@dataclass(frozen=True)
class CodeChangeSet(Contract):
    """Every file changed in one implementation round, against one revision."""

    CONTRACT_NAME = "cortexprime.engineering.code_change_set"

    revision: str
    files: tuple = ()
    base_revision: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.revision, str) or not self.revision.strip():
            raise ContractViolation(
                "a change set must name its revision; the same paths against a "
                "different commit describe a different change"
            )
        object.__setattr__(self, "revision", self.revision.strip())

        if not isinstance(self.files, tuple):
            raise ContractViolation("files must be a tuple")
        for item in self.files:
            if not isinstance(item, ChangedFile):
                raise ContractViolation(
                    f"files contains {item!r}, which is not a ChangedFile"
                )

        paths = [f.path for f in self.files]
        if len(set(paths)) != len(paths):
            raise ContractViolation(
                "the same path appears twice; one file cannot have two fates in one round"
            )

    # ------------------------------------------------------------------

    @classmethod
    def empty(cls, revision: str, *, base_revision: Optional[str] = None) -> "CodeChangeSet":
        return cls(revision=revision, files=(), base_revision=base_revision)

    def with_file(self, changed: ChangedFile) -> "CodeChangeSet":
        from dataclasses import replace

        if any(f.path == changed.path for f in self.files):
            raise ContractViolation(
                f"{changed.path!r} is already recorded; one file cannot have two fates"
            )
        return replace(self, files=self.files + (changed,))

    @property
    def paths(self) -> tuple:
        return tuple(sorted(f.path for f in self.files))

    @property
    def all_paths_touched(self) -> tuple:
        """Every path involved, including the source of a rename."""
        return tuple(sorted({p for f in self.files for p in f.paths_touched}))

    @property
    def is_empty(self) -> bool:
        return not self.files

    @property
    def lines_added(self) -> int:
        return sum(f.lines_added for f in self.files)

    @property
    def lines_removed(self) -> int:
        return sum(f.lines_removed for f in self.files)

    def by_kind(self, kind: ChangeKind) -> tuple:
        return tuple(f for f in self.files if f.kind is kind)

    # ------------------------------------------------------------------
    # Containment
    # ------------------------------------------------------------------

    def outside(self, scope: BlastRadiusScope) -> tuple:
        """Every touched path the scope does not permit writing.

        Both ends of a rename are checked. Moving a file *out* of the radius is
        as much a scope violation as writing to one outside it, and checking
        only the destination would miss exactly that.
        """
        return scope.excess(self.all_paths_touched)

    def assert_within(self, scope: BlastRadiusScope) -> None:
        """Raise on the first path outside the declared scope."""
        for path in self.all_paths_touched:
            reason = scope.refusal_reason(path)
            if reason is not None:
                raise OutsideBlastRadius(
                    path=path, reason=reason, allowed=scope.allowed_patterns
                )
