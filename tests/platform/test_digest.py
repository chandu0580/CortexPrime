"""Content digests.

The tests that matter most are the ones proving a *changed* payload produces a
*different* digest. That property is what Constitution I2 rests on: dispatch
recomputes the digest of a stored artifact and refuses to execute on mismatch.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from backend.contracts import ActionRef, ExecutionScope, HashAlgorithm, PayloadDigest
from backend.platform.hashing import (
    DEFAULT_ALGORITHM,
    DIGEST_DOMAIN_PREFIX,
    CanonicalizationError,
    compute_digest,
    digest_hex,
    digests_match,
    verify_digest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestDeterminism:
    def test_same_value_yields_same_digest(self) -> None:
        value = {"a": 1, "b": [1, 2]}
        assert compute_digest(value) == compute_digest(value)

    def test_key_order_does_not_change_the_digest(self) -> None:
        assert compute_digest({"a": 1, "b": 2}) == compute_digest({"b": 2, "a": 1})

    def test_digest_is_stable_across_processes(self) -> None:
        """The property that makes a stored digest verifiable later.

        Python randomizes string hashing per process by default; if that ever
        leaked into canonicalization, digests would not survive a restart.
        """
        script = (
            "from backend.platform.hashing import digest_hex;"
            "print(digest_hex({'b': [1, 2, {'z': None, 'a': True}], 'a': 'café'}))"
        )
        runs = []
        for seed in ("0", "1", "random"):
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                env={**__import__("os").environ, "PYTHONHASHSEED": seed},
            )
            assert result.returncode == 0, result.stderr
            runs.append(result.stdout.strip())
        assert len(set(runs)) == 1, f"digest differed across processes: {runs}"

    def test_known_value_does_not_drift(self) -> None:
        """A regression pin. If this changes, previously stored digests are void.

        Updating this constant is only correct alongside a CANONICAL_VERSION
        increment and an ADR -- never to make a failing test pass.
        """
        assert digest_hex({"cortexprime": "canonical", "version": 1}) == (
            "6c3e54d005b91529c5c43ac758af17c200ed0a904e39fd0099d7b34caf3b34e5"
        )


class TestSensitivity:
    def test_changing_a_value_changes_the_digest(self) -> None:
        original = ActionRef("docker.restart", {"container": "web-01"}).to_dict()
        tampered = ActionRef("docker.restart", {"container": "web-99"}).to_dict()
        assert compute_digest(original) != compute_digest(tampered)

    def test_changing_the_action_type_changes_the_digest(self) -> None:
        left = ActionRef("docker.restart", {"container": "web-01"}).to_dict()
        right = ActionRef("docker.remove", {"container": "web-01"}).to_dict()
        assert compute_digest(left) != compute_digest(right)

    def test_adding_a_field_changes_the_digest(self) -> None:
        assert compute_digest({"a": 1}) != compute_digest({"a": 1, "b": 2})

    def test_type_change_changes_the_digest(self) -> None:
        assert compute_digest({"a": 1}) != compute_digest({"a": "1"})
        assert compute_digest({"a": 1}) != compute_digest({"a": 1.0})
        assert compute_digest({"a": 1}) != compute_digest({"a": True})

    def test_nesting_change_changes_the_digest(self) -> None:
        assert compute_digest({"a": [1, 2]}) != compute_digest({"a": [[1, 2]]})


class TestVerification:
    def test_matching_payload_verifies(self) -> None:
        payload = ExecutionScope("docker", ("web-01",), "production").to_dict()
        assert verify_digest(payload, compute_digest(payload)) is True

    def test_substituted_payload_fails_verification(self) -> None:
        """The core I2 scenario: approve one payload, execute a different one."""
        approved = ExecutionScope("docker", ("web-01",), "production").to_dict()
        substituted = ExecutionScope("docker", ("web-99",), "production").to_dict()
        assert verify_digest(substituted, compute_digest(approved)) is False

    def test_verification_uses_the_expected_digests_algorithm(self) -> None:
        """A SHA-512 digest must not fail merely because the default is SHA-256."""
        payload = {"a": 1}
        expected = compute_digest(payload, HashAlgorithm.SHA512)
        assert verify_digest(payload, expected) is True

    def test_digests_across_algorithms_never_match(self) -> None:
        payload = {"a": 1}
        assert digests_match(
            compute_digest(payload, HashAlgorithm.SHA256),
            compute_digest(payload, HashAlgorithm.SHA512),
        ) is False

    def test_digests_match_delegates_to_constant_time_comparison(self) -> None:
        payload = {"a": 1}
        assert digests_match(compute_digest(payload), compute_digest(payload)) is True


class TestDomainSeparation:
    def test_digest_differs_from_a_bare_hash_of_the_same_bytes(self) -> None:
        """Prevents a digest computed elsewhere being replayed into CortexPrime."""
        import hashlib

        from backend.platform.hashing import canonical_bytes

        value = {"a": 1}
        bare = hashlib.sha256(canonical_bytes(value)).hexdigest()
        assert digest_hex(value) != bare

    def test_domain_prefix_carries_the_canonical_version(self) -> None:
        from backend.platform.hashing import CANONICAL_VERSION

        assert DIGEST_DOMAIN_PREFIX == f"cortexprime/digest/v{CANONICAL_VERSION}".encode("ascii")


class TestContractIntegration:
    def test_digest_of_a_contract_payload_is_a_payload_digest(self) -> None:
        digest = compute_digest(ActionRef("docker.restart", {}).to_dict())
        assert isinstance(digest, PayloadDigest)
        assert digest.algorithm is DEFAULT_ALGORITHM
        assert len(digest.value) == 64

    def test_round_tripped_contract_produces_the_same_digest(self) -> None:
        """Serialize, decode, re-serialize -- the digest must survive."""
        original = ExecutionScope("docker", ("web-01",), "production")
        restored = ExecutionScope.from_dict(original.to_dict())
        assert compute_digest(original.to_dict()) == compute_digest(restored.to_dict())

    def test_sha512_digest_has_the_expected_length(self) -> None:
        digest = compute_digest({"a": 1}, HashAlgorithm.SHA512)
        assert len(digest.value) == 128


class TestInvalidInput:
    def test_unhashable_type_raises_rather_than_coercing(self) -> None:
        with pytest.raises(CanonicalizationError):
            compute_digest({"a": object()})

    def test_unsupported_algorithm_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported hash algorithm"):
            digest_hex({"a": 1}, algorithm="md5")  # type: ignore[arg-type]

    def test_non_finite_float_raises(self) -> None:
        with pytest.raises(CanonicalizationError, match="NaN or Infinity"):
            compute_digest({"confidence": float("nan")})
