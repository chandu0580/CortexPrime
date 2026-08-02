from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enterprise_branch_protection_monitor import (
    BranchProtectionHistoryStore,
    _configured_repos,
    _gap_signature,
    _overall_severity,
    assess_gaps,
    check_all_repos,
)


class TestConfiguredRepos:
    def test_parses_comma_separated_repos(self, monkeypatch):
        monkeypatch.setenv("BRANCH_PROTECTION_MONITORED_REPOS", "chandu0580/CortexPrime, other/repo")
        assert _configured_repos() == [("chandu0580", "CortexPrime"), ("other", "repo")]

    def test_empty_env_returns_empty_list(self, monkeypatch):
        monkeypatch.setenv("BRANCH_PROTECTION_MONITORED_REPOS", "")
        assert _configured_repos() == []


class TestAssessGaps:
    def test_no_protection_at_all_is_critical(self):
        gaps = assess_gaps(None)
        assert len(gaps) == 1
        assert gaps[0]["gap"] == "no_protection"
        assert gaps[0]["severity"] == "critical"

    def test_missing_required_reviews_flagged(self):
        protection = {
            "required_status_checks": {"contexts": ["ci/test"]},
            "enforce_admins": {"enabled": True},
        }
        gaps = assess_gaps(protection)
        gap_names = [g["gap"] for g in gaps]
        assert "no_required_reviews" in gap_names
        assert "no_required_status_checks" not in gap_names
        assert "admins_can_bypass" not in gap_names

    def test_missing_status_checks_flagged(self):
        protection = {
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "enforce_admins": {"enabled": True},
        }
        gaps = assess_gaps(protection)
        assert "no_required_status_checks" in [g["gap"] for g in gaps]

    def test_admins_can_bypass_flagged(self):
        protection = {
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {"contexts": ["ci/test"]},
            "enforce_admins": {"enabled": False},
        }
        gaps = assess_gaps(protection)
        assert "admins_can_bypass" in [g["gap"] for g in gaps]

    def test_fully_protected_has_no_gaps(self):
        protection = {
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {"contexts": ["ci/test"]},
            "enforce_admins": {"enabled": True},
        }
        assert assess_gaps(protection) == []


class TestOverallSeverity:
    def test_no_gaps_is_low(self):
        assert _overall_severity([]) == "low"

    def test_picks_highest_severity(self):
        gaps = [{"gap": "a", "severity": "medium"}, {"gap": "b", "severity": "high"}]
        assert _overall_severity(gaps) == "high"


class TestGapSignature:
    def test_order_independent(self):
        a = [{"gap": "x", "severity": "low"}, {"gap": "y", "severity": "low"}]
        b = [{"gap": "y", "severity": "low"}, {"gap": "x", "severity": "low"}]
        assert _gap_signature(a) == _gap_signature(b)


class TestBranchProtectionHistoryStore:
    @pytest.fixture
    def store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield BranchProtectionHistoryStore(file_path=Path(tmpdir) / "bp_history.json")

    def test_record_and_list_recent(self, store):
        store.record("o/r", "main", [{"gap": "no_protection", "severity": "critical"}], "critical")
        recent = store.list_recent()
        assert len(recent) == 1
        assert recent[0]["repo"] == "o/r"

    def test_record_replaces_prior_entry_for_same_repo_branch(self, store):
        store.record("o/r", "main", [{"gap": "no_protection", "severity": "critical"}], "critical")
        store.record("o/r", "main", [], "low", fix_applied=True)
        recent = store.list_recent()
        assert len(recent) == 1
        assert recent[0]["severity"] == "low"
        assert recent[0]["fix_applied"] is True

    def test_last_signature_scoped_per_repo_branch(self, store):
        store.record("o/r", "main", [{"gap": "no_protection", "severity": "critical"}], "critical")
        assert store.last_signature("o/r", "main") == "no_protection"
        assert store.last_signature("o/r", "develop") is None


@pytest.mark.asyncio
class TestCheckAllRepos:
    @pytest.fixture
    def store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield BranchProtectionHistoryStore(file_path=Path(tmpdir) / "bp_history.json")

    async def test_no_repos_configured_returns_empty(self, store, monkeypatch):
        monkeypatch.setenv("BRANCH_PROTECTION_MONITORED_REPOS", "")
        with patch("backend.connectors.registry.connector_registry.get", return_value=MagicMock()):
            results = await check_all_repos(history_store=store)
        assert results == []

    async def test_github_not_registered_returns_empty(self, store, monkeypatch):
        monkeypatch.setenv("BRANCH_PROTECTION_MONITORED_REPOS", "o/r")
        with patch("backend.connectors.registry.connector_registry.get", return_value=None):
            results = await check_all_repos(history_store=store)
        assert results == []

    async def test_no_protection_files_ticket(self, store, monkeypatch):
        monkeypatch.setenv("BRANCH_PROTECTION_MONITORED_REPOS", "o/r")
        fake_gh = MagicMock()
        fake_gh.get_repository = AsyncMock(return_value={"default_branch": "main"})
        fake_gh.get_branch_protection = AsyncMock(return_value=None)

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock(return_value={"key": "OPS-1"})) as mock_correlate:
            results = await check_all_repos(history_store=store)

        assert len(results) == 1
        assert results[0]["ticket_key"] == "OPS-1"
        assert results[0]["severity"] == "critical"
        mock_correlate.assert_awaited_once()
        assert mock_correlate.call_args.kwargs["service"] == "o/r"

    async def test_fully_protected_records_no_ticket(self, store, monkeypatch):
        monkeypatch.setenv("BRANCH_PROTECTION_MONITORED_REPOS", "o/r")
        fake_gh = MagicMock()
        fake_gh.get_repository = AsyncMock(return_value={"default_branch": "main"})
        fake_gh.get_branch_protection = AsyncMock(return_value={
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {"contexts": ["ci/test"]},
            "enforce_admins": {"enabled": True},
        })

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock()) as mock_correlate:
            results = await check_all_repos(history_store=store)

        assert results[0]["ticket_key"] is None
        assert results[0]["severity"] == "low"
        mock_correlate.assert_not_awaited()

    async def test_already_seen_gap_signature_not_reticketed(self, store, monkeypatch):
        monkeypatch.setenv("BRANCH_PROTECTION_MONITORED_REPOS", "o/r")
        store.record("o/r", "main", [{"gap": "no_protection", "severity": "critical"}], "critical", ticket_key="OPS-1")
        fake_gh = MagicMock()
        fake_gh.get_repository = AsyncMock(return_value={"default_branch": "main"})
        fake_gh.get_branch_protection = AsyncMock(return_value=None)

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock()) as mock_correlate:
            results = await check_all_repos(history_store=store)

        assert results[0]["ticket_key"] is None
        mock_correlate.assert_not_awaited()

    async def test_permission_error_recorded_as_unknown_not_critical(self, store, monkeypatch):
        monkeypatch.setenv("BRANCH_PROTECTION_MONITORED_REPOS", "o/r")
        fake_gh = MagicMock()
        fake_gh.get_repository = AsyncMock(return_value={"default_branch": "main"})
        fake_gh.get_branch_protection = AsyncMock(
            side_effect=PermissionError("GitHub API: 403 Forbidden — Upgrade to GitHub Pro or make this repository public to enable this feature.")
        )

        with patch("backend.connectors.registry.connector_registry.get", return_value=fake_gh), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock()) as mock_correlate:
            results = await check_all_repos(history_store=store)

        assert len(results) == 1
        assert results[0]["severity"] == "unknown"
        assert results[0]["ticket_key"] is None
        assert "GitHub Pro" in results[0]["error"]
        mock_correlate.assert_not_awaited()

    async def test_check_exception_for_one_repo_does_not_break_others(self, store, monkeypatch):
        monkeypatch.setenv("BRANCH_PROTECTION_MONITORED_REPOS", "bad/repo,good/repo")

        async def _get_repository(owner, repo):
            if owner == "bad":
                raise RuntimeError("API exploded")
            return {"default_branch": "main"}

        good_gh = MagicMock()
        good_gh.get_repository = AsyncMock(side_effect=_get_repository)
        good_gh.get_branch_protection = AsyncMock(return_value=None)

        with patch("backend.connectors.registry.connector_registry.get", return_value=good_gh), \
             patch("backend.services.enterprise_alert_correlator.correlate_and_report", new=AsyncMock(return_value={"key": "OPS-1"})):
            results = await check_all_repos(history_store=store)

        assert len(results) == 1
        assert results[0]["repo"] == "good/repo"
