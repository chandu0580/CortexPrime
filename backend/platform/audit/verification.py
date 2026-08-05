"""Chain verification, integrity reporting, and export.

The audit trail's value is entirely in being checkable. A chain nobody can
verify is a log with extra steps.

Three defects are detectable, and they are distinct:

**Tampering** -- a record's stored digest no longer matches its content. Someone
edited a record in place.

**A broken link** -- a record's ``previous_digest`` does not match its
predecessor's ``entry_digest``. Records were reordered, or one was substituted.

**A missing record** -- sequence numbers skip. Someone deleted an entry. This is
the one a naive "does each link match" check misses entirely, because deleting a
record from the middle leaves the survivors internally consistent while the gap
in sequence numbers is the only trace.

Export
------
:func:`export_chain` emits the chain plus a manifest carrying the head digest,
record count, and sequence range. Publishing the head digest somewhere the
platform cannot reach -- a ticket, an email, an external notary -- converts
"tamper-evident to whoever holds the file" into "tamper-evident, full stop",
because rewriting the chain can no longer reproduce a head that was witnessed
elsewhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from backend.contracts import AuditEvent
from backend.platform.audit.runtime import AUDIT_SCHEMA_VERSION, AuditRuntime

__all__ = [
    "ChainDefect",
    "DefectKind",
    "IntegrityReport",
    "verify_chain",
    "export_chain",
    "verify_export",
]


class DefectKind(str):
    """Kinds of chain defect. A plain string subclass so reports stay JSON-safe."""

    TAMPERED = "tampered_record"
    BROKEN_LINK = "broken_link"
    MISSING_RECORD = "missing_record"
    OUT_OF_ORDER = "out_of_order"
    ORPHAN_ORIGIN = "orphan_origin"
    UNEXPECTED_ORIGIN = "unexpected_origin"


@dataclass(frozen=True)
class ChainDefect:
    """One problem found in a chain, located precisely enough to investigate."""

    kind: str
    sequence: int
    detail: str
    event_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "sequence": self.sequence,
            "detail": self.detail,
            "event_id": self.event_id,
        }


@dataclass(frozen=True)
class IntegrityReport:
    """The result of verifying a chain.

    ``ok`` is the only field to branch on. The rest exists so a failure can be
    investigated rather than merely announced.
    """

    ok: bool
    records_checked: int
    defects: tuple[ChainDefect, ...] = field(default_factory=tuple)
    first_sequence: Optional[int] = None
    last_sequence: Optional[int] = None
    head_digest: Optional[str] = None
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def first_defect(self) -> Optional[ChainDefect]:
        return self.defects[0] if self.defects else None

    def summary(self) -> str:
        if self.ok:
            return f"chain verified: {self.records_checked} records, head {self.head_digest}"
        return (
            f"chain FAILED: {len(self.defects)} defect(s) across "
            f"{self.records_checked} records; first at sequence "
            f"{self.defects[0].sequence} ({self.defects[0].kind})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "records_checked": self.records_checked,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "head_digest": self.head_digest,
            "verified_at": self.verified_at.isoformat(),
            "defects": [defect.to_dict() for defect in self.defects],
        }


def verify_chain(
    runtime: AuditRuntime,
    records: Optional[Iterable[AuditEvent]] = None,
    *,
    expect_origin: bool = True,
) -> IntegrityReport:
    """Verify a chain end to end and report every defect found.

    Verification continues past the first defect rather than stopping, because
    an operator investigating tampering needs the full extent of the damage,
    not just where it starts.

    ``expect_origin`` should be ``False`` when verifying a slice that begins
    part-way through a chain -- an exported window, or a store whose head was
    archived -- so that a legitimately non-zero first sequence is not reported
    as a missing record.
    """
    ordered = list(records) if records is not None else list(runtime.query())
    if not ordered:
        return IntegrityReport(ok=True, records_checked=0)

    defects: list[ChainDefect] = []

    for index, record in enumerate(ordered):
        # 1. Was this record altered in place?
        recomputed = runtime.recompute_digest(record)
        if not recomputed.matches(record.entry_digest):
            defects.append(
                ChainDefect(
                    kind=DefectKind.TAMPERED,
                    sequence=record.sequence,
                    event_id=record.event_id,
                    detail=(
                        f"stored digest {record.entry_digest.value[:16]}... does not match "
                        f"recomputed {recomputed.value[:16]}...; the record was edited"
                    ),
                )
            )

        if index == 0:
            if record.sequence == 0:
                if record.previous_digest is not None:
                    defects.append(
                        ChainDefect(
                            kind=DefectKind.UNEXPECTED_ORIGIN,
                            sequence=record.sequence,
                            event_id=record.event_id,
                            detail="sequence 0 must not carry a previous digest",
                        )
                    )
            elif expect_origin:
                defects.append(
                    ChainDefect(
                        kind=DefectKind.MISSING_RECORD,
                        sequence=record.sequence,
                        event_id=record.event_id,
                        detail=(
                            f"chain starts at sequence {record.sequence}; records 0 to "
                            f"{record.sequence - 1} are absent"
                        ),
                    )
                )
            continue

        previous = ordered[index - 1]

        # 2. Are sequence numbers contiguous? A gap means deletion.
        expected_sequence = previous.sequence + 1
        if record.sequence != expected_sequence:
            kind = (
                DefectKind.MISSING_RECORD
                if record.sequence > expected_sequence
                else DefectKind.OUT_OF_ORDER
            )
            missing = record.sequence - expected_sequence
            defects.append(
                ChainDefect(
                    kind=kind,
                    sequence=record.sequence,
                    event_id=record.event_id,
                    detail=(
                        f"expected sequence {expected_sequence}, found {record.sequence}"
                        + (f"; {missing} record(s) deleted" if missing > 0 else "")
                    ),
                )
            )

        # 3. Does the link hold?
        if record.previous_digest is None:
            defects.append(
                ChainDefect(
                    kind=DefectKind.ORPHAN_ORIGIN,
                    sequence=record.sequence,
                    event_id=record.event_id,
                    detail="non-origin record carries no previous digest",
                )
            )
        elif not record.previous_digest.matches(previous.entry_digest):
            defects.append(
                ChainDefect(
                    kind=DefectKind.BROKEN_LINK,
                    sequence=record.sequence,
                    event_id=record.event_id,
                    detail=(
                        f"previous digest does not match the digest of sequence "
                        f"{previous.sequence}; records were reordered or substituted"
                    ),
                )
            )

    return IntegrityReport(
        ok=not defects,
        records_checked=len(ordered),
        defects=tuple(defects),
        first_sequence=ordered[0].sequence,
        last_sequence=ordered[-1].sequence,
        head_digest=ordered[-1].entry_digest.value,
    )


def export_chain(
    runtime: AuditRuntime, records: Optional[Iterable[AuditEvent]] = None
) -> str:
    """Export a chain as JSON Lines with a leading manifest.

    Line 1 is the manifest; every subsequent line is one record. The manifest
    carries the head digest, which is the value worth publishing somewhere the
    platform cannot reach.
    """
    ordered = list(records) if records is not None else list(runtime.query())
    manifest = {
        "_manifest": True,
        "schema_version": AUDIT_SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(ordered),
        "first_sequence": ordered[0].sequence if ordered else None,
        "last_sequence": ordered[-1].sequence if ordered else None,
        "head_digest": ordered[-1].entry_digest.value if ordered else None,
    }
    lines = [json.dumps(manifest, separators=(",", ":"), sort_keys=True)]
    lines.extend(
        json.dumps(record.to_dict(), separators=(",", ":"), sort_keys=True)
        for record in ordered
    )
    return "\n".join(lines) + "\n"


def verify_export(runtime: AuditRuntime, exported: str) -> IntegrityReport:
    """Verify an exported chain, including its manifest.

    Checks the manifest's claims against the records that follow, so an export
    whose manifest was edited to hide a deletion is detected.
    """
    lines = [line for line in exported.splitlines() if line.strip()]
    if not lines:
        return IntegrityReport(ok=True, records_checked=0)

    manifest = json.loads(lines[0])
    if not manifest.get("_manifest"):
        return IntegrityReport(
            ok=False,
            records_checked=0,
            defects=(
                ChainDefect(
                    kind=DefectKind.TAMPERED,
                    sequence=-1,
                    detail="export is missing its manifest line",
                ),
            ),
        )

    records = [AuditEvent.from_dict(json.loads(line)) for line in lines[1:]]
    # A slice may legitimately begin above sequence 0.
    report = verify_chain(runtime, records, expect_origin=manifest.get("first_sequence") == 0)

    extra: list[ChainDefect] = []
    if manifest.get("record_count") != len(records):
        extra.append(
            ChainDefect(
                kind=DefectKind.MISSING_RECORD,
                sequence=-1,
                detail=(
                    f"manifest claims {manifest.get('record_count')} records but the "
                    f"export contains {len(records)}"
                ),
            )
        )
    if records and manifest.get("head_digest") != records[-1].entry_digest.value:
        extra.append(
            ChainDefect(
                kind=DefectKind.TAMPERED,
                sequence=records[-1].sequence,
                detail="manifest head digest does not match the final record",
            )
        )

    if not extra:
        return report
    return IntegrityReport(
        ok=False,
        records_checked=report.records_checked,
        defects=report.defects + tuple(extra),
        first_sequence=report.first_sequence,
        last_sequence=report.last_sequence,
        head_digest=report.head_digest,
    )
