"""Execution checkpoints: the positions a run can be resumed from.

A checkpoint records which nodes were finished at a moment, so a resumed run does
not redo them. Its whole value rests on that claim being true, so the aggregate
refuses to resume from a checkpoint claiming a node finished that the record says
did not -- resuming from it would skip work the run believes is undone.

The reverse direction is permitted and normal: a checkpoint that is *behind* the
current state simply resumes from further back and redoes some finished work.
That is wasteful rather than wrong, and for idempotent work it is exactly the
right trade.

Payloads live elsewhere
------------------------
``payload_ref`` is opaque. This context stores no execution output -- a runtime
that held the results would be a knowledge store, and the boundary would be gone
before anyone noticed it moved. The cost is real and stated: resuming needs
whatever holds the payload to still have it, and nothing here can promise that.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contexts.execution.domain.errors import DigestMismatch, DigestNotComputed
from backend.contexts.execution.domain.identifiers import (
    CheckpointId,
    normalise_node_id,
)
from backend.platform.hashing import compute_digest, digests_match

__all__ = ["ExecutionCheckpoint", "CHECKPOINT_KIND"]

CHECKPOINT_KIND = "cortexprime.execution.checkpoint"


@dataclass(frozen=True)
class ExecutionCheckpoint(Contract):
    """One recoverable position in a run."""

    CONTRACT_NAME = "cortexprime.execution.checkpoint"

    checkpoint_id: CheckpointId
    sequence: int
    label: str
    finished_nodes: frozenset = field(default_factory=frozenset)
    resume_from: tuple = ()
    payload_ref: Optional[str] = None
    recorded_by: str = "execution-runtime"
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

        if not isinstance(self.finished_nodes, (frozenset, set)):
            raise ContractViolation("finished_nodes must be a set")
        for node_id in self.finished_nodes:
            normalise_node_id(node_id)
        object.__setattr__(self, "finished_nodes", frozenset(self.finished_nodes))

        if not isinstance(self.resume_from, tuple):
            raise ContractViolation("resume_from must be a tuple")
        for node_id in self.resume_from:
            normalise_node_id(node_id)

        overlap = set(self.resume_from) & set(self.finished_nodes)
        if overlap:
            raise ContractViolation(
                f"checkpoint {self.label!r} both finished and resumes from "
                f"{sorted(overlap)}; a resumed run would redo work it recorded as done"
            )

        if self.payload_ref is not None and not self.payload_ref.strip():
            raise ContractViolation("payload_ref must be non-blank when given")
        if self.recorded_at.tzinfo is None:
            raise ContractViolation("recorded_at must be timezone-aware")

    # -- queries -------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        """Whether nothing had finished when this was taken.

        Legal and occasionally right -- a checkpoint at the very start of a run
        is a valid place to resume from. Policy reports it because a run that
        only ever checkpoints at the start has a resume story that is really a
        restart story.
        """
        return not self.finished_nodes

    def covers(self, node_id: str) -> bool:
        return node_id in self.finished_nodes

    # -- digest --------------------------------------------------------

    def digest_payload(self) -> dict[str, Any]:
        return {
            "__artifact__": CHECKPOINT_KIND,
            "checkpoint_id": str(self.checkpoint_id),
            "sequence": self.sequence,
            "label": self.label,
            "finished_nodes": sorted(self.finished_nodes),
            "resume_from": sorted(self.resume_from),
            "payload_ref": self.payload_ref,
            "recorded_by": self.recorded_by,
            "recorded_at": self.recorded_at.isoformat(),
        }

    def compute_digest(
        self, algorithm: HashAlgorithm = HashAlgorithm.SHA256
    ) -> PayloadDigest:
        return compute_digest(self.digest_payload(), algorithm)

    def sealed(self) -> "ExecutionCheckpoint":
        return replace(self, digest=self.compute_digest().value)

    def verify_digest(self) -> None:
        """Raise unless the checkpoint still hashes to what it was sealed with.

        A checkpoint altered between being written and being resumed from would
        make a run skip work it never did, and the skip would be invisible.
        """
        if not self.digest:
            raise DigestNotComputed(str(self.checkpoint_id))
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise DigestMismatch(
                execution_id=str(self.checkpoint_id),
                recorded=self.digest,
                recomputed=recomputed.value,
            )

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        label: str,
        finished_nodes: Sequence[str] = (),
        resume_from: Sequence[str] = (),
        payload_ref: Optional[str] = None,
        recorded_by: str = "execution-runtime",
    ) -> "ExecutionCheckpoint":
        return cls(
            checkpoint_id=CheckpointId.new(),
            sequence=sequence,
            label=label,
            finished_nodes=frozenset(finished_nodes),
            resume_from=tuple(resume_from),
            payload_ref=payload_ref,
            recorded_by=recorded_by,
        ).sealed()
