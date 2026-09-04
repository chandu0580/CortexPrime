"""The two-axis execution trust model (ADR-088, ratified 2026-09-04).

Isolation answers to **code trust**. Consequence is priced by governance under
L10 -- authority, approval depth and verification strength -- not by a sandbox.

These tests pin three things that are easy to lose later:

1. the matrix itself, cell by cell, because it is the whole decision;
2. that the relaxation ADR-088 named is exactly the relaxation that happened,
   and nothing rode in beside it;
3. that ``code_trust`` is in the capability digest, which is the only thing
   standing between this model and silent classification drift.
"""

from __future__ import annotations

import pytest

from backend.contracts.connector import (
    CodeTrust,
    IsolationTier,
    minimum_isolation,
)
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import (
    EffectSemantics,
    ExecutionEnvironment,
    SideEffectClass,
)
from backend.contexts.connectivity.domain.contract import (
    CapabilityContract,
    CapabilityEnvironment,
    CapabilityInterface,
    ExecutionMode,
)
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_directory import (
    WorkerImplementation,
    WorkerInterface,
    WorkerScope,
)


def _contract(code_trust, side_effect, tier, **over):
    return CapabilityContract(
        interface=CapabilityInterface.CONNECTOR,
        side_effect_class=side_effect,
        effect_semantics=over.pop(
            "effect_semantics",
            EffectSemantics.READ_ONLY
            if side_effect is SideEffectClass.READ
            else EffectSemantics.NON_IDEMPOTENT_WRITE,
        ),
        isolation_tier=tier,
        code_trust=code_trust,
        execution_mode=ExecutionMode.SYNCHRONOUS,
        supported_environments=(CapabilityEnvironment.DEVELOPMENT,),
        **over,
    )


def _worker(tier):
    return WorkerImplementation(
        worker_id="trust-model-probe",
        worker_kind=WorkerKind.KUBERNETES,
        interface=WorkerInterface.CONNECTOR,
        implementation="probe",
        implementation_version="1.0.0",
        isolation=tier,
        scope=WorkerScope.PLATFORM,
        supported_environments=frozenset({ExecutionEnvironment.DEVELOPMENT}),
        supported_effects=frozenset(EffectSemantics),
        supported_providers=frozenset({"kubernetes"}),
    )


class TestTheMatrix:
    """ADR-088 section 4.3, cell by cell. If a cell moves, this fails."""

    EXPECTED = {
        CodeTrust.FIXED: ("ambient", "contained", "contained", "contained"),
        CodeTrust.PARAMETERIZED: ("ambient", "contained", "contained", "sandboxed"),
        CodeTrust.THIRD_PARTY: ("contained", "sandboxed", "sandboxed", "sealed"),
        CodeTrust.OPERATOR_SCRIPT: ("contained", "sandboxed", "sealed", "sealed"),
        CodeTrust.ARBITRARY: ("sealed", "sealed", "sealed", "sealed"),
    }
    COLUMNS = (
        SideEffectClass.READ,
        SideEffectClass.REVERSIBLE_WRITE,
        SideEffectClass.IRREVERSIBLE_WRITE,
        SideEffectClass.DESTRUCTIVE,
    )

    @pytest.mark.parametrize("code_trust", list(CodeTrust))
    def test_every_row_matches_the_ratified_matrix(self, code_trust):
        actual = tuple(
            minimum_isolation(code_trust, effect).value for effect in self.COLUMNS
        )
        assert actual == self.EXPECTED[code_trust]

    def test_the_matrix_is_total(self):
        for code_trust in CodeTrust:
            for effect in SideEffectClass:
                assert isinstance(minimum_isolation(code_trust, effect), IsolationTier)

    def test_requirements_never_decrease_as_code_becomes_less_trusted(self):
        """Down a column, isolation may rise but must never fall."""
        for effect in SideEffectClass:
            ranks = [
                minimum_isolation(ct, effect).rank
                for ct in sorted(CodeTrust, key=lambda c: c.rank)
            ]
            assert ranks == sorted(ranks), f"{effect.value} column is non-monotonic"

    def test_requirements_never_decrease_as_effects_get_worse(self):
        """Along a row, isolation may rise but must never fall."""
        for code_trust in CodeTrust:
            ranks = [minimum_isolation(code_trust, e).rank for e in self.COLUMNS]
            assert ranks == sorted(ranks), f"{code_trust.value} row is non-monotonic"

    def test_arbitrary_code_is_sealed_even_for_a_read(self):
        """The row that got STRICTER. For arbitrary code the declared effect is
        not a bound on what the code does, so the effect column earns nothing."""
        assert (
            minimum_isolation(CodeTrust.ARBITRARY, SideEffectClass.READ)
            is IsolationTier.SEALED
        )

    def test_the_matrix_refuses_to_answer_an_undeclared_question(self):
        with pytest.raises(ContractViolation):
            minimum_isolation(None, SideEffectClass.READ)
        with pytest.raises(ContractViolation):
            minimum_isolation(CodeTrust.FIXED, None)


class TestSealedIsUnchanged:
    """ADR-088 Decision 3: SEALED is retained verbatim and gains occupants."""

    def test_sealed_still_means_full_virtualization_excluding_shared_kernels(self):
        """Read from source deliberately.

        Enum members do not carry their own ``__doc__`` -- they inherit the
        class's -- and this is a claim about the *documented definition*, which
        is exactly the kind of claim source is the right witness for. The
        behavioural half of SEALED is pinned by the matrix tests above.
        """
        import inspect

        source = " ".join(inspect.getsource(IsolationTier).split())
        assert "Full virtualization, no ambient credentials" in source
        assert "explicitly excludes shared-kernel containers" in source

    def test_sealed_is_still_the_top_of_the_order(self):
        assert IsolationTier.SEALED.rank == max(t.rank for t in IsolationTier)

    def test_sealed_now_has_occupants_where_it_had_none(self):
        sealed_cells = [
            (ct, e)
            for ct in CodeTrust
            for e in SideEffectClass
            if minimum_isolation(ct, e) is IsolationTier.SEALED
        ]
        assert len(sealed_cells) >= 4
        assert all(
            ct is CodeTrust.ARBITRARY for ct, _ in sealed_cells
            if _ is SideEffectClass.READ
        )

    def test_sandboxed_is_below_sealed_and_above_contained(self):
        assert (
            IsolationTier.CONTAINED.rank
            < IsolationTier.SANDBOXED.rank
            < IsolationTier.SEALED.rank
        )

    def test_sandboxed_does_not_satisfy_sealed(self):
        """A shared-kernel boundary never counts as virtualization."""
        assert not IsolationTier.SANDBOXED.satisfies(IsolationTier.SEALED)
        assert IsolationTier.SEALED.satisfies(IsolationTier.SANDBOXED)


class TestGateOneUsesTheMatrix:
    def test_the_phase_9_8_reductio_now_registers(self):
        """A GitHub issue comment no longer requires full virtualization.

        This is the case that justified ADR-088, and it is hardware-independent:
        the old rule was equally absurd on a KVM host.
        """
        contract = _contract(
            CodeTrust.FIXED,
            SideEffectClass.IRREVERSIBLE_WRITE,
            IsolationTier.CONTAINED,
        )
        assert contract.isolation_tier is IsolationTier.CONTAINED

    def test_a_fixed_irreversible_write_is_still_refused_in_process(self):
        """The relaxation stops at CONTAINED. AMBIENT -- an in-process adapter --
        is still not enough, which is why 9.6's write does not become executable
        merely because this model was ratified."""
        with pytest.raises(ContractViolation) as excinfo:
            _contract(
                CodeTrust.FIXED,
                SideEffectClass.IRREVERSIBLE_WRITE,
                IsolationTier.AMBIENT,
            )
        assert "'contained' is the minimum" in str(excinfo.value)

    def test_arbitrary_code_cannot_register_even_a_read_below_sealed(self):
        for tier in (
            IsolationTier.AMBIENT,
            IsolationTier.CONTAINED,
            IsolationTier.SANDBOXED,
        ):
            with pytest.raises(ContractViolation) as excinfo:
                _contract(
                    CodeTrust.ARBITRARY,
                    SideEffectClass.READ,
                    tier,
                    effect_semantics=EffectSemantics.READ_ONLY,
                )
            assert "'sealed' is the minimum" in str(excinfo.value)

    def test_terraform_destroy_would_require_sealed(self):
        with pytest.raises(ContractViolation):
            _contract(
                CodeTrust.THIRD_PARTY,
                SideEffectClass.DESTRUCTIVE,
                IsolationTier.SANDBOXED,
            )

    def test_code_trust_must_be_declared(self):
        with pytest.raises(TypeError):
            CapabilityContract(
                interface=CapabilityInterface.CONNECTOR,
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                isolation_tier=IsolationTier.AMBIENT,
            )

    def test_code_trust_must_be_a_code_trust(self):
        with pytest.raises(ContractViolation):
            _contract("fixed", SideEffectClass.READ, IsolationTier.AMBIENT,
                      effect_semantics=EffectSemantics.READ_ONLY)


class TestCodeTrustIsInTheDigest:
    """The drift control. Without this the model rests on nothing but honesty."""

    def test_code_trust_appears_in_the_digest_payload(self):
        contract = _contract(
            CodeTrust.FIXED, SideEffectClass.READ, IsolationTier.AMBIENT,
            effect_semantics=EffectSemantics.READ_ONLY)
        assert contract.digest_payload()["code_trust"] == "fixed"

    def test_reclassifying_a_capability_changes_its_digest(self):
        """A capability that quietly becomes PARAMETERIZED must not inherit the
        approvals that were granted to the FIXED one."""
        fixed = _contract(
            CodeTrust.FIXED, SideEffectClass.IRREVERSIBLE_WRITE,
            IsolationTier.CONTAINED)
        drifted = _contract(
            CodeTrust.PARAMETERIZED, SideEffectClass.IRREVERSIBLE_WRITE,
            IsolationTier.CONTAINED)
        assert fixed.digest_payload() != drifted.digest_payload()

    def test_a_contract_survives_a_dict_round_trip(self):
        original = _contract(
            CodeTrust.PARAMETERIZED, SideEffectClass.REVERSIBLE_WRITE,
            IsolationTier.CONTAINED)
        restored = CapabilityContract.from_dict(original.to_dict())
        assert restored.code_trust is CodeTrust.PARAMETERIZED
        assert restored.digest_payload() == original.digest_payload()


class TestGateTwoUsesTheMatrix:
    def test_a_contained_worker_may_perform_a_fixed_irreversible_write(self):
        assert _worker(IsolationTier.CONTAINED).permits(
            CodeTrust.FIXED, SideEffectClass.IRREVERSIBLE_WRITE)

    def test_a_contained_worker_may_not_host_arbitrary_code_at_all(self):
        worker = _worker(IsolationTier.CONTAINED)
        for effect in SideEffectClass:
            assert not worker.permits(CodeTrust.ARBITRARY, effect)

    def test_a_sandboxed_worker_may_not_host_arbitrary_code_either(self):
        worker = _worker(IsolationTier.SANDBOXED)
        assert not worker.permits(CodeTrust.ARBITRARY, SideEffectClass.READ)

    def test_a_sealed_worker_may_host_anything(self):
        worker = _worker(IsolationTier.SEALED)
        for code_trust in CodeTrust:
            for effect in SideEffectClass:
                assert worker.permits(code_trust, effect)

    def test_an_ambient_worker_may_only_read_fixed_code(self):
        worker = _worker(IsolationTier.AMBIENT)
        assert worker.permits(CodeTrust.FIXED, SideEffectClass.READ)
        assert not worker.permits(
            CodeTrust.FIXED, SideEffectClass.IRREVERSIBLE_WRITE)

    def test_the_legacy_signature_narrowed_to_fixed_rather_than_guessing(self):
        worker = _worker(IsolationTier.CONTAINED)
        assert worker.permits_side_effect(
            SideEffectClass.IRREVERSIBLE_WRITE
        ) is worker.permits(CodeTrust.FIXED, SideEffectClass.IRREVERSIBLE_WRITE)


class TestGovernanceWasNotTouched:
    """ADR-088 changes which isolation column is read. Nothing else."""

    def test_side_effect_class_is_unchanged(self):
        assert [e.value for e in SideEffectClass] == [
            "read", "reversible_write", "irreversible_write", "destructive"]

    def test_reversibility_semantics_are_unchanged(self):
        assert SideEffectClass.REVERSIBLE_WRITE.requires_inverse
        assert not SideEffectClass.IRREVERSIBLE_WRITE.requires_inverse
        assert SideEffectClass.IRREVERSIBLE_WRITE.mutates
        assert not SideEffectClass.READ.mutates

    def test_the_kubernetes_write_is_still_declared_irreversible(self):
        from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
            ROLLOUT_RESTART_OPERATION, kubernetes_write_catalog,
        )
        spec = kubernetes_write_catalog().require(ROLLOUT_RESTART_OPERATION)
        assert spec.side_effect_class is SideEffectClass.IRREVERSIBLE_WRITE

    def test_the_kubernetes_write_is_still_not_exposed(self):
        """Ratifying ADR-088 must not have quietly made the 9.6 write reachable."""
        from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
            KUBERNETES_REAL_READ_OPERATIONS, ROLLOUT_RESTART_OPERATION,
        )
        assert ROLLOUT_RESTART_OPERATION not in KUBERNETES_REAL_READ_OPERATIONS
