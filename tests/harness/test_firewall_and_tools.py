"""Phase 6.2 — the secret/context firewall (Part F) and deterministic tool
exposure (Part G)."""

from __future__ import annotations

import base64

import pytest

from backend.harness.firewall import assert_no_secrets, find_secrets
from backend.harness.tool_exposure import (
    ArgKind,
    ArgSpec,
    ExposedTool,
    ResolvedTool,
    ToolExposurePolicy,
    ToolRefusalReason,
    ToolRefused,
)


# ======================================================================
# Part F — secret / context firewall (structured, field-aware)
# ======================================================================

class TestSecretFirewall:
    def test_clean_value_has_no_findings(self):
        assert find_secrets({"title": "hello", "count": 3, "ok": True}) == []

    def test_raw_bearer_token_by_shape(self):
        f = find_secrets({"reason": "Bearer sk-abcdef1234567890abcdef1234567890"})
        assert any(x.why == "value-shape" for x in f)

    def test_api_key_by_key_name(self):
        f = find_secrets({"api_key": "not-obviously-a-token-but-named-one"})
        assert any(x.why == "key-name" for x in f)

    def test_ghp_token_by_shape(self):
        f = find_secrets({"note": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"})
        assert any(x.why == "value-shape" for x in f)

    def test_authorization_header_detected(self):
        f = find_secrets({"headers": {"Authorization": "Bearer abcdefghijkl1234"}})
        assert f
        assert any("headers" in x.path for x in f)

    def test_nested_secret_field_found_at_path(self):
        value = {"level1": {"level2": {"client_secret": "hunter2-and-then-some"}}}
        f = find_secrets(value)
        assert any(x.path == "level1.level2.client_secret" for x in f)

    def test_secret_in_a_list(self):
        f = find_secrets({"items": ["ok", "password=supersecretvalue"]})
        assert any("items[1]" in x.path for x in f)

    def test_credential_type_detected(self):
        class CredentialMaterial:
            def __repr__(self):
                return "***redacted***"

        f = find_secrets({"cred": CredentialMaterial()})
        assert any(x.why == "credential-type" for x in f)

    def test_encoded_secret_detected(self):
        token = "Bearer sk-abcdef1234567890abcdef1234567890"
        encoded = base64.b64encode(token.encode()).decode()
        f = find_secrets({"blob": encoded})
        assert any(x.why == "encoded" for x in f)

    def test_non_sensitive_audit_keys_not_flagged(self):
        # authorization_digest et al. are the substance of an audit record.
        clean = {
            "authorization_digest": "abc123",
            "authorization_expires_at": "2026-01-01T00:00:00Z",
            "credential_ref": "ref-1",
        }
        assert find_secrets(clean) == []

    def test_pydantic_model_is_walked(self):
        from pydantic import BaseModel

        class Args(BaseModel):
            title: str
            token: str

        f = find_secrets(Args(title="ok", token="ghp_ABCDEFGHIJKLMNOP1234567890"))
        assert f

    def test_assert_no_secrets_raises_with_path(self):
        with pytest.raises(AssertionError) as exc:
            assert_no_secrets({"a": {"b": "sk-abcdef1234567890abcdef1234567890"}},
                              where="tool arguments")
        assert "tool arguments" in str(exc.value)
        assert "a.b" in str(exc.value)

    def test_assert_no_secrets_passes_clean(self):
        assert_no_secrets({"title": "Phase 6.2", "count": 1})  # no raise


# ======================================================================
# Part G — deterministic tool exposure
# ======================================================================

FOLDER_TOOL = ExposedTool(
    name="create_folder",
    provider="grafana",
    operation="folder.create_folder",
    arguments=(
        ArgSpec("title", ArgKind.STRING, required=True, max_length=189),
        ArgSpec("uid", ArgKind.STRING, required=False, max_length=40),
    ),
)
READ_TOOL = ExposedTool(
    name="get_folder", provider="grafana", operation="folder.get_folder",
    arguments=(ArgSpec("uid", ArgKind.STRING, required=True, max_length=40),),
)
POLICY = ToolExposurePolicy((FOLDER_TOOL, READ_TOOL))


class TestToolExposure:
    def test_known_tool_resolves_to_deployment_values(self):
        resolved = POLICY.resolve({"tool": "create_folder",
                                   "arguments": {"title": "Slice", "uid": "s1"}})
        assert isinstance(resolved, ResolvedTool)
        # Provider and operation came from the registry, NOT the model.
        assert resolved.provider == "grafana"
        assert resolved.operation == "folder.create_folder"
        assert resolved.arguments == {"title": "Slice", "uid": "s1"}

    def test_unknown_tool_is_refused_before_governance(self):
        r = POLICY.resolve({"tool": "delete_everything", "arguments": {}})
        assert isinstance(r, ToolRefused)
        assert r.reason is ToolRefusalReason.UNKNOWN_TOOL

    def test_model_cannot_supply_provider_or_operation(self):
        # Even if the model names a provider/operation, they are ignored — only
        # 'tool' selects, and the values are the registry's.
        r = POLICY.resolve({
            "tool": "create_folder",
            "provider": "aws", "operation": "iam.create_admin",
            "arguments": {"title": "x"},
        })
        # 'provider'/'operation' are undeclared arguments? No — they are top-level
        # keys the resolver ignores; only 'arguments' contents are checked.
        assert isinstance(r, ResolvedTool)
        assert r.provider == "grafana"  # not "aws"
        assert r.operation == "folder.create_folder"  # not the model's

    def test_undeclared_argument_refused(self):
        r = POLICY.resolve({"tool": "get_folder",
                            "arguments": {"uid": "s1", "sql": "DROP TABLE"}})
        assert isinstance(r, ToolRefused)
        assert r.reason is ToolRefusalReason.UNDECLARED_ARGUMENT

    def test_missing_required_argument_refused(self):
        r = POLICY.resolve({"tool": "get_folder", "arguments": {}})
        assert isinstance(r, ToolRefused)
        assert r.reason is ToolRefusalReason.MISSING_ARGUMENT

    def test_malformed_argument_refused(self):
        r = POLICY.resolve({"tool": "get_folder", "arguments": {"uid": 12345}})
        assert isinstance(r, ToolRefused)
        assert r.reason is ToolRefusalReason.MALFORMED_ARGUMENT

    def test_over_length_argument_refused(self):
        r = POLICY.resolve({"tool": "get_folder", "arguments": {"uid": "x" * 41}})
        assert isinstance(r, ToolRefused)
        assert r.reason is ToolRefusalReason.MALFORMED_ARGUMENT

    def test_non_object_request_refused(self):
        for bad in ("just a string", 42, ["list"], None):
            r = POLICY.resolve(bad)
            assert isinstance(r, ToolRefused)
            assert r.reason is ToolRefusalReason.MALFORMED_REQUEST

    def test_narrowing_cannot_widen(self):
        narrowed = POLICY.narrowed({"get_folder", "create_folder", "invent_tool"})
        assert narrowed.exposed_names == {"get_folder", "create_folder"}
        # A name the parent never had is not addable.
        assert "invent_tool" not in narrowed.exposed_names

    def test_narrowed_subagent_refuses_parent_only_tool(self):
        read_only = POLICY.narrowed({"get_folder"})
        r = read_only.resolve({"tool": "create_folder", "arguments": {"title": "x"}})
        assert isinstance(r, ToolRefused)
        assert r.reason is ToolRefusalReason.UNKNOWN_TOOL

    def test_duplicate_exposure_is_a_construction_error(self):
        with pytest.raises(ValueError):
            ToolExposurePolicy((FOLDER_TOOL, FOLDER_TOOL))

    def test_resolution_is_deterministic(self):
        req = {"tool": "create_folder", "arguments": {"title": "T", "uid": "u"}}
        a = POLICY.resolve(req)
        b = POLICY.resolve(req)
        assert isinstance(a, ResolvedTool) and isinstance(b, ResolvedTool)
        assert a.provider == b.provider and a.operation == b.operation
        assert a.arguments == b.arguments
