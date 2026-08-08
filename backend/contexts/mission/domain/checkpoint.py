"""Checkpoints: the points a mission can be resumed from.

A checkpoint is a claim that the mission reached a recoverable position, and it
is only worth anything if resuming from it lands somewhere real. So a checkpoint
carries:

* the **execution state** it was taken at -- resuming into a different phase than
  the one that was checkpointed is how a mission silently redoes or skips work;
* a **digest** over its own content, so a checkpoint that was altered between
  being written and being resumed from is detectable rather than trusted;
* an opaque **payload reference**, never the payload. Mission Runtime stores no
  mission data. A runtime that held the gathered evidence would be a knowledge
  store, and the boundary would be gone before anyone noticed it moved.

The last point is the one that costs something. It means Mission Runtime cannot
tell you *what* a checkpoint contains, only that it exists, when it was taken,
and whether its record is intact. Resuming needs whatever context owns the
payload to still have it -- and nothing here can guarantee that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contracts.mission import MissionState
from backend.contexts.mission.domain.errors import DigestMismatch, DigestNotComputed
from backend.contexts.mission.domain.identifiers import CheckpointId
from backend.platform.hashing import compute_digest, digests_match

__all__ = ["MissionCheckpoint", "CHECKPOINT_KIND"]

CHECKPOINT_KIND = "cortexprime.mission.checkpoint"


@dataclass(frozen=True)
class MissionCheckpoint(Contract):
    """One recoverable position in a mission's progress."""

    CONTRACT_NAME = "cortexprime.mission.checkpoint"

    checkpoint_id: CheckpointId
    sequence: int
    label: str
    execution_state: MissionState
    execution_id: str
    payload_ref: Optional[str] = None
    payload_digest: Optional[str] = None
    recorded_by: str = "mission-runtime"
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    digest: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.checkpoint_id, CheckpointId):
            raise ContractViolation("checkpoint_id must be a CheckpointId")
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise ContractViolation("sequence must be a positive integer starting at 1")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ContractViolation(
                "a checkpoint must be labelled; an unlabelled resumption point tells "
                "whoever resumes nothing about what they are resuming into"
            )
        if not isinstance(self.execution_state, MissionState):
            raise ContractViolation("execution_state must be a MissionState")
        if not isinstance(self.execution_id, str) or not self.execution_id.strip():
            raise ContractViolation(
                "a checkpoint must name the execution it was taken during"
            )
        if self.execution_state.is_terminal:
            raise ContractViolation(
                f"a checkpoint cannot be taken at {self.execution_state.value!r}; a "
                "terminal execution has nothing left to resume into"
            )
        if self.payload_ref is not None and not self.payload_ref.strip():
            raise ContractViolation("payload_ref must be non-blank when given")
        if self.recorded_at.tzinfo is None:
            raise ContractViolation("recorded_at must be timezone-aware")

    # -- digest --------------------------------------------------------

    def digest_payload(self) -> dict[str, Any]:
        """Exactly what the digest covers. Excludes the digest itself."""
        return {
            "__artifact__": CHECKPOINT_KIND,
            "checkpoint_id": str(self.checkpoint_id),
            "sequence": self.sequence,
            "label": self.label,
            "execution_state": self.execution_state.value,
            "execution_id": self.execution_id,
            "payload_ref": self.payload_ref,
            "payload_digest": self.payload_digest,
            "recorded_by": self.recorded_by,
            "recorded_at": self.recorded_at.isoformat(),
        }

    def compute_digest(
        self, algorithm: HashAlgorithm = HashAlgorithm.SHA256
    ) -> PayloadDigest:
        return compute_digest(self.digest_payload(), algorithm)

    def sealed(self) -> "MissionCheckpoint":
        """The same checkpoint with its digest bound."""
        from dataclasses import replace

        return replace(self, digest=self.compute_digest().value)

    def verify_digest(self) -> None:
        """Raise unless the checkpoint still hashes to what it was sealed with."""
        if not self.digest:
            raise DigestNotComputed(str(self.checkpoint_id))
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise DigestMismatch(
                mission_id=str(self.checkpoint_id),
                recorded=self.digest,
                recomputed=recomputed.value,
            )

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        label: str,
        execution_state: MissionState,
        execution_id: str,
        payload_ref: Optional[str] = None,
        payload_digest: Optional[str] = None,
        recorded_by: str = "mission-runtime",
    ) -> "MissionCheckpoint":
        return cls(
            checkpoint_id=CheckpointId.new(),
            sequence=sequence,
            label=label,
            execution_state=execution_state,
            execution_id=execution_id,
            payload_ref=payload_ref,
            payload_digest=payload_digest,
            recorded_by=recorded_by,
        ).sealed()
