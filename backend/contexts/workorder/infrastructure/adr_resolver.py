"""Reference resolution against the real repository.

The domain validator takes an injected resolver because this context may not
import the contexts that own ADRs, evidence, or architecture rules (S2). This is
the implementation that answers from what is actually on disk and in the
architecture gate -- so V5 and V9 check reality rather than a supplied list.

Evidence is deliberately *not* resolved here. The Evidence context does not
exist yet, and inventing a resolver that answered "yes" would make V4
unfalsifiable. Unknown resolves to absent, V4 reports a blocking finding, and the
WorkOrder cannot be approved until an evidence store exists. That is fail-closed
(EP-6), and it is the honest state of the system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

__all__ = ["FilesystemReferenceResolver"]

_ADR_PATTERN = re.compile(r"^ADR-(\d{3,})", re.IGNORECASE)
_SUPERSEDED = re.compile(r"^\s*[-*]?\s*\*{0,2}Status:?\*{0,2}\s*:?\s*superseded", re.IGNORECASE | re.MULTILINE)


@dataclass
class FilesystemReferenceResolver:
    """Resolves ADRs from ``docs/adr/`` and constraints from the architecture gate.

    Scans once at construction. A resolver that re-read the filesystem per call
    could answer differently within a single validation run, which would make a
    report internally inconsistent for reasons nobody could reproduce.
    """

    adr_root: Path = Path("docs/adr")
    known_constraints: frozenset = field(default_factory=frozenset)
    known_evidence: frozenset = field(default_factory=frozenset)
    stale_evidence: frozenset = field(default_factory=frozenset)

    _adrs: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._adrs = {}
        root = Path(self.adr_root)
        if not root.is_dir():
            return
        for path in sorted(root.glob("ADR-*.md")):
            match = _ADR_PATTERN.match(path.name)
            if not match:
                continue
            key = f"ADR-{int(match.group(1)):03d}"
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:  # pragma: no cover - unreadable file
                continue
            self._adrs[key.upper()] = bool(_SUPERSEDED.search(text))

    @staticmethod
    def _normalise(reference: str) -> str:
        match = _ADR_PATTERN.match(reference.strip())
        if match:
            return f"ADR-{int(match.group(1)):03d}"
        return reference.strip().upper()

    # -- ReferenceResolver -------------------------------------------------

    def adr_exists(self, reference: str) -> bool:
        return self._normalise(reference) in self._adrs

    def adr_is_superseded(self, reference: str) -> bool:
        return self._adrs.get(self._normalise(reference), False)

    def evidence_exists(self, reference: str) -> bool:
        return reference in self.known_evidence

    def evidence_is_stale(self, reference: str) -> bool:
        return reference in self.stale_evidence

    def constraint_is_enforceable(self, reference: str) -> bool:
        return reference in self.known_constraints

    @property
    def resolved_adrs(self) -> frozenset:
        return frozenset(self._adrs)


def constraints_from_architecture_gate() -> frozenset:
    """Every rule and invariant id the architecture gate can actually enforce.

    Read from the suite rather than hard-coded, so a constraint stops being
    enforceable the moment its rule is deleted -- which is precisely when a
    WorkOrder citing it should start failing V9.
    """
    from backend.platform.architecture import default_suite

    suite = default_suite()
    ids = {rule.rule_id for rule in suite._rules}          # noqa: SLF001 - read-only
    ids |= {f"INV-{check.invariant_id}" for check in suite._invariants}  # noqa: SLF001
    ids |= {check.invariant_id for check in suite._invariants}           # noqa: SLF001
    return frozenset(ids)
