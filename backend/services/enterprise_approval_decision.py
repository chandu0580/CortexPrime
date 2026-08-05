"""Approval decision binding: the approval is the authority, not the payload.

PR-04 bound a stashed action to a digest stored *beside it*. That stops
post-hoc payload edits, but it has a documented residual gap: an attacker who
can write ``pending_approval_actions.json`` can change the payload **and**
recompute the digest in the same write, producing a self-consistent forgery.

This module closes that gap by recording what was approved **independently** of
what will execute:

* ``approval_decisions.json`` holds the authoritative digest, written when the
  action is stashed and sealed when a human grants approval.
* ``pending_approval_actions.json`` holds the artifact that will execute.

Dispatch recomputes the artifact digest and compares it against the **approval
record**, never against the digest stored alongside the artifact. Forging now
requires writing two separate stores consistently, and -- where a signing key is
configured -- forging an HMAC the attacker does not hold.

Why a separate store rather than a column
-----------------------------------------
The threat is write access to one file. Two files in one directory is a modest
improvement on its own; the real strength comes from the signature. The
separation is what makes the signature *checkable* -- there has to be something
to compare against that the artifact's own author did not write.

Signing is pluggable
--------------------
``ApprovalSigner`` is an interface, not a fixed algorithm. HMAC is provided and
used automatically when ``APPROVAL_SIGNING_KEY`` is set. Without a key the
platform runs unsigned and says so, because a security property claimed but not
active is worse than one known to be absent. ``APPROVAL_REQUIRE_SIGNATURE=true``
makes unsigned records refuse outright.

Asymmetric signing, an HSM, or an external notary all slot in behind the same
interface without touching the verification pipeline.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol

from backend.contracts import HashAlgorithm, PayloadDigest, PrincipalKind
from backend.platform.hashing import canonical_bytes, digests_match
from backend.platform.identity import monotonic_ulid

log = logging.getLogger(__name__)

__all__ = [
    "APPROVAL_RECORD_VERSION",
    "ApprovalStatus",
    "ApprovalFailure",
    "ApprovalVerdict",
    "ApprovalSigner",
    "HmacApprovalSigner",
    "UnsignedApprovalSigner",
    "resolve_signer",
    "ApprovalDecisionStore",
    "approval_decision_store",
]

APPROVAL_RECORD_VERSION = 1
"""Version of the approval-decision record format. A record declaring a version
this build does not know is refused rather than guessed at."""

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DECISIONS_FILE = _DATA_DIR / "approval_decisions.json"

_DEFAULT_TTL_MINUTES = int(os.getenv("APPROVAL_DECISION_TTL_MINUTES", "0") or 0)
"""Approval lifetime in minutes. ``0`` disables expiry, preserving existing
behavior; the Approval Center already applies its own expiry policy."""


class ApprovalStatus(str, Enum):
    """Lifecycle of an approval decision record."""

    PENDING = "pending"
    GRANTED = "granted"
    CONSUMED = "consumed"
    REVOKED = "revoked"


class ApprovalFailure(str, Enum):
    """Why execution was refused. Every value means "do not execute"."""

    APPROVAL_MISSING = "approval_missing"
    LEGACY_NO_APPROVAL_RECORD = "legacy_no_approval_record"
    APPROVAL_MALFORMED = "approval_malformed"
    APPROVAL_VERSION_MISMATCH = "approval_version_mismatch"
    APPROVAL_NOT_GRANTED = "approval_not_granted"
    APPROVAL_EXPIRED = "approval_expired"
    APPROVAL_REPLAY = "approval_replay"
    APPROVAL_IDENTITY_INVALID = "approval_identity_invalid"
    APPROVAL_SIGNATURE_INVALID = "approval_signature_invalid"
    APPROVAL_UNSIGNED_REJECTED = "approval_unsigned_rejected"
    ARTIFACT_MODIFIED = "artifact_modified"
    ACTION_TYPE_MISMATCH = "action_type_mismatch"

    @property
    def is_tamper_evidence(self) -> bool:
        """Whether this indicates deliberate modification rather than drift."""
        return self in {
            ApprovalFailure.ARTIFACT_MODIFIED,
            ApprovalFailure.ACTION_TYPE_MISMATCH,
            ApprovalFailure.APPROVAL_REPLAY,
            ApprovalFailure.APPROVAL_SIGNATURE_INVALID,
            ApprovalFailure.APPROVAL_IDENTITY_INVALID,
        }


@dataclass(frozen=True)
class ApprovalVerdict:
    """Result of verifying an artifact against its approval decision."""

    ok: bool
    workflow_id: str
    approval_id: Optional[str] = None
    approved_digest: Optional[str] = None
    current_digest: Optional[str] = None
    approver: Optional[str] = None
    failure: Optional[ApprovalFailure] = None
    detail: Optional[str] = None

    @property
    def refused(self) -> bool:
        return not self.ok

    def reason(self) -> str:
        if self.ok:
            return "approval binding verified"
        base = self.failure.value if self.failure else "unknown"
        return f"{base}: {self.detail}" if self.detail else base


# ----------------------------------------------------------------------
# Signing
# ----------------------------------------------------------------------


class ApprovalSigner(Protocol):
    """Seals an approval decision so it cannot be forged by a file write.

    Implementations must be deterministic and side-effect free. ``verify`` must
    compare in constant time.
    """

    algorithm: str

    def sign(self, payload: bytes) -> Optional[str]: ...

    def verify(self, payload: bytes, signature: Optional[str]) -> bool: ...


class UnsignedApprovalSigner:
    """No signature. Security rests on store separation alone.

    The default when no key is configured. Recorded explicitly on every record
    as ``algorithm: "none"`` so an auditor can see which records were sealed and
    which were not -- rather than a missing signature being ambiguous.
    """

    algorithm = "none"

    def sign(self, payload: bytes) -> Optional[str]:
        return None

    def verify(self, payload: bytes, signature: Optional[str]) -> bool:
        # An unsigned signer accepts only the absence of a signature. A record
        # carrying one must not be waved through by a verifier that cannot
        # check it -- that would let an attacker downgrade to "unsigned".
        return signature is None


class HmacApprovalSigner:
    """HMAC-SHA256 over the canonical approval decision.

    An attacker with write access to both stores still cannot produce a valid
    tag without the key, which is what makes this a genuine trust boundary
    rather than a consistency check.
    """

    algorithm = "hmac-sha256"

    __slots__ = ("_key",)

    def __init__(self, key: str) -> None:
        if not isinstance(key, str) or len(key) < 32:
            raise ValueError("approval signing key must be at least 32 characters")
        self._key = key.encode("utf-8")

    def sign(self, payload: bytes) -> Optional[str]:
        return hmac.new(self._key, payload, sha256).hexdigest()

    def verify(self, payload: bytes, signature: Optional[str]) -> bool:
        if not isinstance(signature, str):
            return False
        return hmac.compare_digest(self.sign(payload) or "", signature)


def resolve_signer() -> ApprovalSigner:
    """Return the configured signer, warning loudly when running unsigned."""
    key = os.getenv("APPROVAL_SIGNING_KEY", "").strip()
    if key:
        try:
            return HmacApprovalSigner(key)
        except ValueError as exc:
            log.error("APPROVAL_SIGNING_KEY is unusable (%s); refusing to run unsigned", exc)
            raise
    log.warning(
        "APPROVAL_SIGNING_KEY is not set — approval decisions are unsigned. Binding "
        "relies on store separation only; an attacker able to write both stores could "
        "forge an approval. Set APPROVAL_SIGNING_KEY (32+ chars) to enable HMAC sealing."
    )
    return UnsignedApprovalSigner()


def _require_signature() -> bool:
    return os.getenv("APPROVAL_REQUIRE_SIGNATURE", "").strip().lower() in {"1", "true", "yes"}


# ----------------------------------------------------------------------
# Store
# ----------------------------------------------------------------------


def _signable(record: Mapping[str, Any]) -> bytes:
    """The canonical bytes an approval signature covers.

    Deliberately excludes ``status`` and ``signature``: status changes after
    sealing (granted -> consumed), and a signature cannot cover itself.
    Everything that defines *what was authorized, by whom* is included.
    """
    return canonical_bytes(
        {
            "record_version": record.get("record_version"),
            "approval_id": record.get("approval_id"),
            "workflow_id": record.get("workflow_id"),
            "action_type": record.get("action_type"),
            "artifact_digest": record.get("artifact_digest"),
            "granted_at": record.get("granted_at"),
            "approver_id": record.get("approver_id"),
            "approver_kind": record.get("approver_kind"),
            "expires_at": record.get("expires_at"),
        }
    )


class ApprovalDecisionStore:
    """Authoritative record of what was approved, stored apart from the artifact."""

    def __init__(
        self, file_path: Optional[Path] = None, signer: Optional[ApprovalSigner] = None
    ) -> None:
        self._file_path = file_path or _DECISIONS_FILE
        self._signer = signer if signer is not None else resolve_signer()
        self._lock = threading.RLock()
        self._records: Dict[str, Any] = self._load()

    # -- persistence -------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        try:
            if self._file_path.exists():
                return json.loads(self._file_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - unreadable store must not crash boot
            log.error("Failed to load approval decision store: %s", exc)
        return {}

    def _persist(self) -> None:
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text(json.dumps(self._records, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to persist approval decision store: %s", exc)

    # -- lifecycle ---------------------------------------------------

    def record_request(
        self,
        workflow_id: str,
        action_type: str,
        artifact_digest: PayloadDigest,
        *,
        ttl_minutes: Optional[int] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Record the digest of what is being submitted for approval.

        Written at stash time, before any human sees it, so the authoritative
        digest predates any opportunity to tamper with the artifact.
        """
        ttl = _DEFAULT_TTL_MINUTES if ttl_minutes is None else ttl_minutes
        now = datetime.now(timezone.utc)
        approval_id = monotonic_ulid()

        record: Dict[str, Any] = {
            "record_version": APPROVAL_RECORD_VERSION,
            "approval_id": approval_id,
            "workflow_id": workflow_id,
            "action_type": action_type,
            "artifact_digest": {
                "algorithm": artifact_digest.algorithm.value,
                "value": artifact_digest.value,
            },
            "status": ApprovalStatus.PENDING.value,
            "requested_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=ttl)).isoformat() if ttl > 0 else None,
            "granted_at": None,
            "approver_id": None,
            "approver_kind": None,
            "signature": None,
            "signature_algorithm": self._signer.algorithm,
            "metadata": dict(metadata or {}),
        }

        with self._lock:
            self._records[workflow_id] = record
            self._persist()
        return approval_id

    def record_grant(
        self, workflow_id: str, approver_id: Optional[str], approver_kind: str = "human"
    ) -> Optional[Dict[str, Any]]:
        """Seal an approval as granted, binding the approver to the digest.

        Signing happens here rather than at request time: the signature covers
        *who approved what*, which is not known until a human acts.
        """
        with self._lock:
            record = self._records.get(workflow_id)
            if not isinstance(record, dict):
                return None

            record["status"] = ApprovalStatus.GRANTED.value
            record["granted_at"] = datetime.now(timezone.utc).isoformat()
            record["approver_id"] = approver_id
            record["approver_kind"] = approver_kind
            record["signature_algorithm"] = self._signer.algorithm
            record["signature"] = self._signer.sign(_signable(record))

            self._persist()
            return dict(record)

    def mark_consumed(self, workflow_id: str) -> bool:
        """Mark an approval used. Returns ``False`` if it already was.

        Atomic under the store lock, so two concurrent dispatches of one
        workflow cannot both succeed here.
        """
        with self._lock:
            record = self._records.get(workflow_id)
            if not isinstance(record, dict):
                return False
            if record.get("status") == ApprovalStatus.CONSUMED.value:
                return False
            record["status"] = ApprovalStatus.CONSUMED.value
            record["consumed_at"] = datetime.now(timezone.utc).isoformat()
            self._persist()
            return True

    def revoke(self, workflow_id: str) -> None:
        """Mark an approval revoked (rejected or expired upstream)."""
        with self._lock:
            record = self._records.get(workflow_id)
            if isinstance(record, dict):
                record["status"] = ApprovalStatus.REVOKED.value
                self._persist()

    def get(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._records.get(workflow_id)
            return dict(record) if isinstance(record, dict) else None

    def discard(self, workflow_id: str) -> None:
        with self._lock:
            if self._records.pop(workflow_id, None) is not None:
                self._persist()

    def list_all(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records = {}
            self._persist()

    # -- verification ------------------------------------------------

    def verify_for_execution(
        self,
        workflow_id: str,
        current_digest: PayloadDigest,
        action_type: str,
        *,
        now: Optional[datetime] = None,
    ) -> ApprovalVerdict:
        """Compare an artifact against its authoritative approval record.

        **This is the security-critical comparison.** ``current_digest`` is
        recomputed from the artifact that is about to execute; it is checked
        against the digest stored in the approval record, never against the
        digest stored beside the artifact.

        Checks run cheapest-and-most-certain first, so the reported failure is
        the first thing genuinely wrong.
        """
        moment = now or datetime.now(timezone.utc)
        record = self.get(workflow_id)

        if record is None:
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                current_digest=current_digest.value,
                failure=ApprovalFailure.LEGACY_NO_APPROVAL_RECORD,
                detail=(
                    "no approval decision record exists for this workflow; it predates "
                    "decision binding or was never submitted through the store"
                ),
            )

        version = record.get("record_version")
        if version != APPROVAL_RECORD_VERSION:
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                approval_id=record.get("approval_id"),
                failure=ApprovalFailure.APPROVAL_VERSION_MISMATCH,
                detail=f"record declares version {version!r}; expected {APPROVAL_RECORD_VERSION}",
            )

        raw_digest = record.get("artifact_digest")
        if not isinstance(raw_digest, Mapping):
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                approval_id=record.get("approval_id"),
                failure=ApprovalFailure.APPROVAL_MALFORMED,
                detail="approval record carries no usable artifact digest",
            )
        try:
            approved = PayloadDigest(
                algorithm=HashAlgorithm(raw_digest["algorithm"]), value=raw_digest["value"]
            )
        except Exception as exc:  # noqa: BLE001
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                approval_id=record.get("approval_id"),
                failure=ApprovalFailure.APPROVAL_MALFORMED,
                detail=f"approved digest is unusable: {exc}",
            )

        status = record.get("status")
        if status == ApprovalStatus.CONSUMED.value:
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                approval_id=record.get("approval_id"),
                approved_digest=approved.value,
                current_digest=current_digest.value,
                failure=ApprovalFailure.APPROVAL_REPLAY,
                detail="this approval has already authorized an execution",
            )
        if status != ApprovalStatus.GRANTED.value:
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                approval_id=record.get("approval_id"),
                approved_digest=approved.value,
                failure=ApprovalFailure.APPROVAL_NOT_GRANTED,
                detail=f"approval status is {status!r}, not granted",
            )

        expires_at = record.get("expires_at")
        if expires_at:
            try:
                deadline = datetime.fromisoformat(expires_at)
            except ValueError:
                return ApprovalVerdict(
                    ok=False,
                    workflow_id=workflow_id,
                    approval_id=record.get("approval_id"),
                    failure=ApprovalFailure.APPROVAL_MALFORMED,
                    detail=f"expires_at is not a valid timestamp: {expires_at!r}",
                )
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if moment >= deadline:
                return ApprovalVerdict(
                    ok=False,
                    workflow_id=workflow_id,
                    approval_id=record.get("approval_id"),
                    approved_digest=approved.value,
                    failure=ApprovalFailure.APPROVAL_EXPIRED,
                    detail=f"approval expired at {expires_at}",
                )

        approver_id = record.get("approver_id")
        approver_kind = record.get("approver_kind")
        if not approver_id or approver_kind != PrincipalKind.HUMAN.value:
            # Constitution: the platform must never authorize itself.
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                approval_id=record.get("approval_id"),
                approved_digest=approved.value,
                approver=approver_id,
                failure=ApprovalFailure.APPROVAL_IDENTITY_INVALID,
                detail=f"approver is {approver_id!r} of kind {approver_kind!r}; a human is required",
            )

        signature = record.get("signature")
        if signature is None and _require_signature():
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                approval_id=record.get("approval_id"),
                approved_digest=approved.value,
                failure=ApprovalFailure.APPROVAL_UNSIGNED_REJECTED,
                detail="APPROVAL_REQUIRE_SIGNATURE is set but this record is unsigned",
            )
        if not self._signer.verify(_signable(record), signature):
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                approval_id=record.get("approval_id"),
                approved_digest=approved.value,
                approver=approver_id,
                failure=ApprovalFailure.APPROVAL_SIGNATURE_INVALID,
                detail="approval signature does not match the sealed decision",
            )

        if record.get("action_type") != action_type:
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                approval_id=record.get("approval_id"),
                approved_digest=approved.value,
                current_digest=current_digest.value,
                approver=approver_id,
                failure=ApprovalFailure.ACTION_TYPE_MISMATCH,
                detail=f"approval authorized {record.get('action_type')!r}, not {action_type!r}",
            )

        # The comparison this module exists for.
        if not digests_match(current_digest, approved):
            return ApprovalVerdict(
                ok=False,
                workflow_id=workflow_id,
                approval_id=record.get("approval_id"),
                approved_digest=approved.value,
                current_digest=current_digest.value,
                approver=approver_id,
                failure=ApprovalFailure.ARTIFACT_MODIFIED,
                detail="the artifact about to execute is not the artifact that was approved",
            )

        return ApprovalVerdict(
            ok=True,
            workflow_id=workflow_id,
            approval_id=record.get("approval_id"),
            approved_digest=approved.value,
            current_digest=current_digest.value,
            approver=approver_id,
        )


approval_decision_store = ApprovalDecisionStore()
