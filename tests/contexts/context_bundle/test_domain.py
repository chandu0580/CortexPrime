"""Domain invariants: layers, scope, expansion, versioning, resolution.

The refusals matter most. A context bundle is what an agent *sees*; one that
widened by accident would give an agent access nobody approved, and the only
trace would be work that turned out better informed than it should have been.
"""

from __future__ import annotations

import pytest

from backend.contracts.errors import ContractViolation
from backend.contexts.context_bundle import (
    AccessMode,
    AdrBundle,
    BlastRadiusSpec,
    BundleId,
    BundleInvalidated,
    BundleStatus,
    BundleSuperseded,
    ContextBundle,
    ContextLayer,
    ContextReference,
    DependencyContract,
    Disposition,
    ExpansionAlreadyDecided,
    ExpansionRequest,
    ImplicitExpansion,
    IncompleteBundle,
    LayerViolation,
    ManifestMismatch,
    RepositoryScope,
    StaleBaseCommit,
    UnknownExpansion,
    assemble,
    auto_grant_reason,
    boundary_signals,
    dependency,
    reference,
)

BASE = "abc123def456"


def _bundle(**overrides):
    fields = dict(
        work_id="WO-1",
        work_order_version=1,
        base_commit=BASE,
        blast_radius=["backend/contexts/context_bundle/**"],
        searchable=["**"],
        adr_references=["ADR-019", "ADR-020"],
        dependencies=[dependency("storage", ["backend/platform/storage"])],
        references=[reference("backend/contexts/context_bundle/domain/bundle.py", ContextLayer.OWNED)],
    )
    fields.update(overrides)
    return assemble(**fields)


# ----------------------------------------------------------------------
# Layers
# ----------------------------------------------------------------------


def test_each_layer_has_a_fixed_access_mode():
    """A layer whose access could be raised per bundle would let a caller turn a
    read-only dependency into a writable one and call it configuration."""
    assert ContextLayer.OWNED.access is AccessMode.READ_WRITE
    assert ContextLayer.DEPENDENCIES.access is AccessMode.READ
    assert ContextLayer.ADR_BUNDLE.access is AccessMode.READ
    assert ContextLayer.MINIMAL.access is AccessMode.READ
    assert ContextLayer.SEARCH.access is AccessMode.SEARCH


def test_search_does_not_permit_reading():
    """A hit is a location, not content. Retrieval is an expansion."""
    assert not AccessMode.SEARCH.permits_read
    assert not AccessMode.SEARCH.permits_write
    assert AccessMode.READ.permits_read


def test_a_retrievable_reference_must_record_a_digest():
    """Otherwise the bundle records that a path was included, not what was there."""
    with pytest.raises(LayerViolation) as caught:
        ContextReference(path="a/b.py", layer=ContextLayer.OWNED)
    assert "manifest cannot be verified" in str(caught.value)


def test_a_search_pattern_must_not_carry_a_digest():
    """What it matches changes with the tree, so there is nothing to digest."""
    with pytest.raises(LayerViolation):
        ContextReference(path="**", layer=ContextLayer.SEARCH, content_digest="abc")


def test_a_reference_must_be_repository_relative():
    for bad in ("/etc/passwd", "backend/../secrets.py"):
        with pytest.raises(ContractViolation):
            reference(bad, ContextLayer.OWNED)


def test_layers_are_ordered():
    order = [
        ContextLayer.MINIMAL, ContextLayer.OWNED, ContextLayer.DEPENDENCIES,
        ContextLayer.ADR_BUNDLE, ContextLayer.SEARCH,
    ]
    assert [layer.order for layer in order] == [0, 1, 2, 3, 4]


# ----------------------------------------------------------------------
# The four mandatory members
# ----------------------------------------------------------------------


def test_a_bundle_missing_a_mandatory_member_is_refused():
    with pytest.raises(IncompleteBundle) as caught:
        ContextBundle(
            bundle_id=BundleId.new(), work_id="WO-1", work_order_version=1,
            base_commit=BASE, version=1,
            repository_scope=None,  # type: ignore[arg-type]
            adr_bundle=AdrBundle(references=()),
            dependencies=(),
            blast_radius=BlastRadiusSpec(allowed=("a/**",)),
        )
    assert "repository scope" in str(caught.value)


def test_a_bundle_with_no_search_scope_is_refused():
    """Search is how a false premise is discovered."""
    with pytest.raises(ContractViolation) as caught:
        RepositoryScope(searchable=())
    assert "how a false premise is discovered" in str(caught.value)


def test_a_blast_radius_allowing_nothing_is_refused():
    with pytest.raises(ContractViolation):
        BlastRadiusSpec(allowed=())


def test_an_adr_cannot_be_both_governing_and_superseded():
    """A WorkOrder governed by a dead decision is ungoverned."""
    with pytest.raises(ContractViolation):
        AdrBundle(references=("ADR-019",), superseded=("ADR-019",))


def test_an_empty_adr_bundle_is_a_positive_assertion():
    """It says no architectural decision governs this work."""
    assert AdrBundle(references=()).is_empty


def test_a_dependency_must_supply_an_interface():
    with pytest.raises(ContractViolation):
        DependencyContract(name="storage", interface_paths=())


def test_a_dependency_cannot_list_a_path_as_both_interface_and_implementation():
    """Supplying an implementation as an interface is how a boundary erodes."""
    with pytest.raises(ContractViolation) as caught:
        dependency("storage", ["backend/platform/storage/guard.py"],
                   implementations=["backend/platform/storage/guard.py"])
    assert "how a boundary erodes" in str(caught.value)


# ----------------------------------------------------------------------
# Assembly and the manifest
# ----------------------------------------------------------------------


def test_assembly_seals_the_bundle():
    """An unsealed bundle has contents nobody can verify later."""
    bundle = _bundle()
    assert bundle.manifest_digest
    bundle.verify_manifest()


def test_the_manifest_digest_is_deterministic():
    payload = _bundle().manifest_payload()
    from backend.platform.hashing import compute_digest

    assert compute_digest(payload).value == compute_digest(payload).value


def test_the_payload_carries_domain_separation():
    from backend.contexts.context_bundle import ARTIFACT_KIND, CANONICAL_FORM_VERSION

    payload = _bundle().manifest_payload()
    assert payload["__artifact__"] == ARTIFACT_KIND
    assert payload["__canonical_form__"] == CANONICAL_FORM_VERSION


def test_a_tampered_bundle_fails_manifest_verification():
    """The check that makes 'this is what the agent saw' verifiable."""
    from dataclasses import replace

    bundle = _bundle()
    tampered = replace(
        bundle,
        references=bundle.references
        + (reference("backend/secrets.py", ContextLayer.DEPENDENCIES),),
    )
    with pytest.raises(ManifestMismatch):
        tampered.verify_manifest()


def test_an_unsealed_bundle_cannot_be_verified():
    from dataclasses import replace

    with pytest.raises(ContractViolation) as caught:
        replace(_bundle(), manifest_digest=None).verify_manifest()
    assert "never sealed" in str(caught.value)


def test_the_same_path_cannot_appear_in_two_layers():
    """It would have two access modes."""
    from dataclasses import replace

    bundle = _bundle()
    with pytest.raises(ContractViolation):
        replace(
            bundle,
            references=bundle.references
            + (reference("backend/contexts/context_bundle/domain/bundle.py", ContextLayer.DEPENDENCIES),),
        )


def test_a_version_above_one_requires_a_granted_expansion():
    """A version exists because something was explicitly widened."""
    from dataclasses import replace

    with pytest.raises(ContractViolation) as caught:
        replace(_bundle(), version=2)
    assert "explicitly widened" in str(caught.value)


# ----------------------------------------------------------------------
# Expansion
# ----------------------------------------------------------------------


def test_a_request_must_say_what_it_answers():
    """A request without a question is browsing."""
    with pytest.raises(ContractViolation):
        ExpansionRequest.create("backend/x.py", "   ", "implementer")


def test_expansion_never_grants_write_access():
    """Widening the writable set is a blast-radius change, not an expansion."""
    with pytest.raises(ContractViolation) as caught:
        ExpansionRequest.create("a/b.py", "why?", "me", target_layer=ContextLayer.OWNED)
    assert "blast-radius change" in str(caught.value)


def test_applying_an_undecided_request_is_refused():
    bundle = _bundle()
    request = ExpansionRequest.create("backend/services/x.py", "does it write state?", "impl")
    staged = bundle.request_expansion(request)

    with pytest.raises(ImplicitExpansion):
        staged.apply_expansion(
            request.request_id, [reference("backend/services/x.py", ContextLayer.DEPENDENCIES)]
        )


def test_applying_a_denied_request_is_refused():
    bundle = _bundle()
    request = ExpansionRequest.create("backend/services/x.py", "why?", "impl")
    staged = bundle.request_expansion(request)
    denied = request.deny("architect", "outside the declared boundary")
    decided = staged.decide_expansion(request.request_id, denied)

    with pytest.raises(ImplicitExpansion):
        decided.apply_expansion(
            request.request_id, [reference("backend/services/x.py", ContextLayer.DEPENDENCIES)]
        )


def test_a_granted_expansion_widens_and_versions():
    bundle = _bundle()
    request = ExpansionRequest.create("backend/services/x.py", "why?", "impl")
    staged = bundle.request_expansion(request)
    granted = staged.decide_expansion(
        request.request_id, request.grant("architect", "needed to answer the question")
    )
    widened = granted.apply_expansion(
        request.request_id, [reference("backend/services/x.py", ContextLayer.DEPENDENCIES)]
    )

    assert widened.version == bundle.version + 1
    assert widened.manifest_digest != bundle.manifest_digest
    assert widened.supersedes == bundle.bundle_id
    widened.verify_manifest()


def test_a_path_outside_the_granted_root_cannot_be_smuggled_in():
    """The obvious way to widen further than was granted."""
    bundle = _bundle()
    request = ExpansionRequest.create("backend/services/allowed", "why?", "impl")
    staged = bundle.request_expansion(request)
    granted = staged.decide_expansion(request.request_id, request.grant("architect"))

    with pytest.raises(ImplicitExpansion) as caught:
        granted.apply_expansion(
            request.request_id, [reference("backend/services/other.py", ContextLayer.DEPENDENCIES)]
        )
    assert "backend/services/other.py" in str(caught.value)


def test_an_expansion_cannot_add_a_writable_reference():
    bundle = _bundle()
    request = ExpansionRequest.create("backend/services/x.py", "why?", "impl")
    staged = bundle.request_expansion(request)
    granted = staged.decide_expansion(request.request_id, request.grant("architect"))

    with pytest.raises(ImplicitExpansion):
        granted.apply_expansion(
            request.request_id, [reference("backend/services/x.py", ContextLayer.OWNED)]
        )


def test_a_request_cannot_be_decided_twice():
    request = ExpansionRequest.create("a/b.py", "why?", "me").grant("architect")
    with pytest.raises(ExpansionAlreadyDecided):
        request.deny("someone", "changed my mind")


def test_a_denial_must_say_why():
    """One without a reason teaches nobody where the boundary actually is."""
    request = ExpansionRequest.create("a/b.py", "why?", "me")
    with pytest.raises(ContractViolation):
        request.deny("architect", "   ")


def test_denied_requests_are_kept():
    """A denial is information."""
    bundle = _bundle()
    request = ExpansionRequest.create("backend/services/x.py", "why?", "impl")
    staged = bundle.request_expansion(request)
    decided = staged.decide_expansion(
        request.request_id, request.deny("architect", "outside the boundary")
    )
    assert len(decided.denied_expansions) == 1


def test_applying_an_unknown_request_is_refused():
    from backend.contexts.context_bundle import ExpansionRequestId

    with pytest.raises(UnknownExpansion):
        _bundle().apply_expansion(ExpansionRequestId.new(), [])


# ----------------------------------------------------------------------
# Auto-grant
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["docs/adr/ADR-018-storage.md", "backend/contracts/approval.py"],
)
def test_conceptually_inside_paths_auto_grant(path):
    assert auto_grant_reason(path) is not None


def test_a_declared_dependency_interface_auto_grants():
    """Declaring a dependency and withholding it would be incoherent."""
    bundle = _bundle()
    assert bundle.auto_grant_candidate("backend/platform/storage/guard.py") is not None


def test_an_unrelated_path_does_not_auto_grant():
    assert _bundle().auto_grant_candidate("backend/services/secret.py") is None


def test_auto_grant_still_records_an_expansion():
    """The difference is who decided, not whether it happened."""
    request = ExpansionRequest.create("docs/adr/ADR-018.md", "what did it decide?", "impl")
    granted = request.auto_grant("an ADR the bundle's index already names")
    assert granted.disposition is Disposition.AUTO_GRANTED
    assert granted.widens_bundle
    assert granted.decision_reason


# ----------------------------------------------------------------------
# Lifecycle and resolution
# ----------------------------------------------------------------------


def test_resolution_returns_the_agent_view():
    resolved = _bundle().resolve(current_commit=BASE)
    assert resolved.writable == ("backend/contexts/context_bundle/domain/bundle.py",)
    assert resolved.searchable == ("**",)
    assert resolved.adr_references == ("ADR-019", "ADR-020")


def test_a_stale_bundle_cannot_be_resolved():
    """An agent reasoning from it would be reasoning about code that no longer exists."""
    with pytest.raises(StaleBaseCommit):
        _bundle().resolve(current_commit="a-different-commit")


def test_a_superseded_bundle_cannot_be_resolved():
    superseded = _bundle().supersede(BundleId.new())
    with pytest.raises(BundleSuperseded):
        superseded.resolve()


def test_an_invalidated_bundle_cannot_be_resolved():
    with pytest.raises(BundleInvalidated):
        _bundle().invalidate("the tree moved").resolve()


def test_invalidating_must_say_why():
    with pytest.raises(ContractViolation):
        _bundle().invalidate("   ")


def test_a_superseded_bundle_cannot_be_expanded():
    bundle = _bundle().supersede(BundleId.new())
    with pytest.raises(BundleSuperseded):
        bundle.request_expansion(ExpansionRequest.create("a/b.py", "why?", "me"))


def test_a_bundle_cannot_supersede_itself():
    bundle = _bundle()
    with pytest.raises(ContractViolation):
        bundle.supersede(bundle.bundle_id)


def test_identity_is_four_values():
    bundle = _bundle()
    assert bundle.identity == ("WO-1", 1, BASE, 1)


def test_transitions_return_new_instances():
    bundle = _bundle()
    invalidated = bundle.invalidate("stale")
    assert bundle.status is BundleStatus.ACTIVE
    assert invalidated.status is BundleStatus.INVALIDATED
    assert bundle is not invalidated


# ----------------------------------------------------------------------
# Boundary signals
# ----------------------------------------------------------------------


def test_a_path_requested_once_is_not_a_signal():
    bundle = _bundle()
    request = ExpansionRequest.create("backend/services/x.py", "why?", "impl")
    assert boundary_signals([bundle.request_expansion(request)]) == ()


def test_a_path_requested_across_work_orders_is_an_architecture_finding():
    """Each request looked reasonable to whoever made it. The pattern does not."""
    bundles = []
    for index in range(3):
        bundle = _bundle(work_id=f"WO-{index}")
        request = ExpansionRequest.create(
            "backend/services/shared.py", f"question {index}", "impl"
        )
        bundles.append(bundle.request_expansion(request))

    signals = boundary_signals(bundles)
    assert len(signals) == 1
    assert signals[0].path == "backend/services/shared.py"
    assert signals[0].request_count == 3
    assert signals[0].crosses_work_orders


def test_repeated_grants_are_as_strong_a_signal_as_denials():
    """A boundary routinely worked around is worse than one merely tested."""
    bundles = []
    for index in range(2):
        bundle = _bundle(work_id=f"WO-{index}")
        request = ExpansionRequest.create("backend/services/shared.py", "why?", "impl")
        staged = bundle.request_expansion(request)
        bundles.append(
            staged.decide_expansion(request.request_id, request.grant("architect"))
        )

    signals = boundary_signals(bundles)
    assert signals[0].request_count == 2
    assert signals[0].denied_count == 0
