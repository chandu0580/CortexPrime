from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_deploy_regression_detector import RegressionVerdict
from backend.services.enterprise_deploy_root_cause_reasoner import (
    MAX_FILES,
    MAX_PATCH_CHARS_PER_FILE,
    _build_diff_summary,
    build_prompt,
    generate_hypothesis,
)

def _verdict(regressed=True) -> RegressionVerdict:
    return RegressionVerdict(
        service="org/checkout-service",
        deployment_id="42",
        regressed=regressed,
        reasons=["p95 latency +30.0% (0.100s -> 0.130s)"],
    )


def _ctx() -> dict:
    return {"repo_full_name": "org/checkout-service"}


def _commit(files=None, message="fix: adjust query") -> dict:
    return {"commit": {"message": message}, "files": files or []}


class TestBuildDiffSummary:
    def test_includes_commit_message(self):
        summary = _build_diff_summary(_commit(message="feat: add caching"))
        assert "feat: add caching" in summary

    def test_includes_file_patches(self):
        commit = _commit(files=[{"filename": "a.py", "status": "modified", "patch": "-old\n+new"}])
        summary = _build_diff_summary(commit)
        assert "a.py" in summary
        assert "-old" in summary and "+new" in summary

    def test_truncates_patch_per_file(self):
        huge_patch = "x" * (MAX_PATCH_CHARS_PER_FILE + 500)
        commit = _commit(files=[{"filename": "big.py", "status": "modified", "patch": huge_patch}])
        summary = _build_diff_summary(commit)
        # the raw huge patch shouldn't appear whole; only the truncated prefix should
        assert huge_patch not in summary
        assert ("x" * MAX_PATCH_CHARS_PER_FILE) in summary

    def test_caps_number_of_files_shown(self):
        files = [{"filename": f"f{i}.py", "status": "modified", "patch": "diff"} for i in range(MAX_FILES + 3)]
        summary = _build_diff_summary(_commit(files=files))
        assert "3 more file(s) not shown" in summary
        assert f"f{MAX_FILES}.py" not in summary  # first file beyond the cap
        assert "f0.py" in summary  # within the cap

    def test_handles_binary_file_with_no_patch(self):
        commit = _commit(files=[{"filename": "image.png", "status": "modified", "patch": None}])
        summary = _build_diff_summary(commit)
        assert "no textual diff available" in summary


class TestBuildPrompt:
    def test_includes_service_deployment_and_evidence(self):
        prompt = build_prompt(_verdict(), "diff summary here")
        assert "checkout-service" in prompt
        assert "42" in prompt
        assert "p95 latency +30.0%" in prompt
        assert "diff summary here" in prompt


@pytest.mark.asyncio
class TestGenerateHypothesis:
    async def test_returns_none_when_not_regressed(self):
        assert await generate_hypothesis(_verdict(regressed=False), _ctx()) is None

    async def test_returns_none_when_repo_full_name_malformed(self):
        assert await generate_hypothesis(_verdict(), {"repo_full_name": "no-slash-here"}) is None

    async def test_returns_none_when_github_connector_missing(self):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            assert await generate_hypothesis(_verdict(), _ctx()) is None

    async def test_returns_none_when_deployment_has_no_sha(self):
        fake_gh = MagicMock()
        fake_gh.get_deployment = AsyncMock(return_value={})
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            assert await generate_hypothesis(_verdict(), _ctx()) is None

    async def test_returns_none_when_commit_fetch_raises(self):
        fake_gh = MagicMock()
        fake_gh.get_deployment = AsyncMock(return_value={"sha": "abc123"})
        fake_gh.get_commit = AsyncMock(side_effect=RuntimeError("404"))
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh):
            assert await generate_hypothesis(_verdict(), _ctx()) is None

    async def test_returns_none_when_llm_call_fails(self):
        fake_gh = MagicMock()
        fake_gh.get_deployment = AsyncMock(return_value={"sha": "abc123"})
        fake_gh.get_commit = AsyncMock(return_value=_commit())
        fake_result = MagicMock(success=False, error="all providers down")
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh), \
             patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(return_value=fake_result)):
            assert await generate_hypothesis(_verdict(), _ctx()) is None

    async def test_returns_hypothesis_text_on_success(self):
        fake_gh = MagicMock()
        fake_gh.get_deployment = AsyncMock(return_value={"sha": "abc123"})
        fake_gh.get_commit = AsyncMock(return_value=_commit(
            files=[{"filename": "queries.py", "status": "modified", "patch": "-select_one()\n+select_all()"}],
            message="perf: batch query",
        ))
        fake_result = MagicMock(success=True, output="This diff removed pagination, likely explaining the latency increase.")
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh), \
             patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(return_value=fake_result)) as mock_route:
            hypothesis = await generate_hypothesis(_verdict(), _ctx())

        assert hypothesis == "This diff removed pagination, likely explaining the latency increase."
        mock_route.assert_awaited_once()
        _, kwargs = mock_route.call_args
        assert "queries.py" in kwargs["prompt"]
        assert kwargs["agent_type"] == "deploy_root_cause_reasoner"

    async def test_returns_none_when_llm_call_raises(self):
        fake_gh = MagicMock()
        fake_gh.get_deployment = AsyncMock(return_value={"sha": "abc123"})
        fake_gh.get_commit = AsyncMock(return_value=_commit())
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh), \
             patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(side_effect=RuntimeError("boom"))):
            assert await generate_hypothesis(_verdict(), _ctx()) is None


def _gitlab_ctx() -> dict:
    return {"source": "gitlab_webhook", "repo_full_name": "group/checkout-service", "commit_sha": "abc123"}


@pytest.mark.asyncio
class TestGenerateHypothesisGitLabSource:
    """ctx["source"] == "gitlab_webhook" must route through the GitLab
    connector instead of GitHub's — this is the whole point of having a
    per-source dispatch table rather than a single hardcoded GitHub path."""

    async def test_uses_gitlab_connector_not_github(self):
        fake_gl = MagicMock()
        fake_gl.get_commit_with_diff = AsyncMock(return_value=_commit(message="fix: batch query"))
        fake_gh = MagicMock()  # must never be touched for a gitlab_webhook ctx

        def _get(name):
            return {"gitlab_ci": fake_gl, "github": fake_gh}.get(name)

        fake_result = MagicMock(success=True, output="Batching likely explains it.")
        with patch("backend.connectors.registry.connector_registry.get", side_effect=_get), \
             patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(return_value=fake_result)):
            hypothesis = await generate_hypothesis(_verdict(), _gitlab_ctx())

        assert hypothesis == "Batching likely explains it."
        fake_gl.get_commit_with_diff.assert_awaited_once()
        fake_gh.get_deployment.assert_not_called()

    async def test_url_encodes_repo_full_name_as_project_id(self):
        fake_gl = MagicMock()
        fake_gl.get_commit_with_diff = AsyncMock(return_value=_commit())
        fake_result = MagicMock(success=True, output="hypothesis")
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gl), \
             patch("backend.llm.llm_router.llm_router.route", new=AsyncMock(return_value=fake_result)):
            await generate_hypothesis(_verdict(), _gitlab_ctx())

        fake_gl.get_commit_with_diff.assert_awaited_once_with("group%2Fcheckout-service", "abc123")

    async def test_returns_none_when_commit_sha_missing(self):
        ctx = {"source": "gitlab_webhook", "repo_full_name": "group/checkout-service"}
        assert await generate_hypothesis(_verdict(), ctx) is None

    async def test_returns_none_when_gitlab_connector_missing(self):
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            assert await generate_hypothesis(_verdict(), _gitlab_ctx()) is None

    async def test_returns_none_when_gitlab_diff_fetch_raises(self):
        fake_gl = MagicMock()
        fake_gl.get_commit_with_diff = AsyncMock(side_effect=RuntimeError("404"))
        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gl):
            assert await generate_hypothesis(_verdict(), _gitlab_ctx()) is None
