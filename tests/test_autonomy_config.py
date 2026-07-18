from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.core.autonomy_config import DEFAULT_THRESHOLDS, AutonomyConfig


@pytest.fixture
def temp_config_path():
    with tempfile.TemporaryDirectory() as tmp:
        yield str(Path(tmp) / "autonomy.json")


@pytest.fixture
def config(temp_config_path):
    return AutonomyConfig(storage_path=temp_config_path)


class TestDefaultThresholds:
    def test_default_values_present(self):
        assert "max_concurrent_missions" in DEFAULT_THRESHOLDS
        assert "auto_approve_threshold" in DEFAULT_THRESHOLDS
        assert "max_retries_per_stage" in DEFAULT_THRESHOLDS
        assert "cooldown_seconds" in DEFAULT_THRESHOLDS
        assert "require_human_approval" in DEFAULT_THRESHOLDS
        assert "confidence_threshold" in DEFAULT_THRESHOLDS
        assert "max_iterations_per_mission" in DEFAULT_THRESHOLDS
        assert "auto_resolve_conflicts" in DEFAULT_THRESHOLDS
        assert "max_parallel_workers" in DEFAULT_THRESHOLDS
        assert "staging_auto_deploy" in DEFAULT_THRESHOLDS

    def test_default_types(self):
        assert isinstance(DEFAULT_THRESHOLDS["max_concurrent_missions"], int)
        assert isinstance(DEFAULT_THRESHOLDS["auto_approve_threshold"], float)
        assert isinstance(DEFAULT_THRESHOLDS["max_retries_per_stage"], int)
        assert isinstance(DEFAULT_THRESHOLDS["cooldown_seconds"], int)
        assert isinstance(DEFAULT_THRESHOLDS["require_human_approval"], bool)
        assert isinstance(DEFAULT_THRESHOLDS["confidence_threshold"], float)
        assert isinstance(DEFAULT_THRESHOLDS["max_iterations_per_mission"], int)
        assert isinstance(DEFAULT_THRESHOLDS["auto_resolve_conflicts"], bool)
        assert isinstance(DEFAULT_THRESHOLDS["max_parallel_workers"], int)
        assert isinstance(DEFAULT_THRESHOLDS["staging_auto_deploy"], bool)


class TestAutonomyConfig:
    def test_get_default_value(self, config):
        assert config.get("max_concurrent_missions") == 5

    def test_get_unknown_key_returns_none(self, config):
        assert config.get("nonexistent") is None

    def test_get_unknown_key_with_default(self, config):
        assert config.get("nonexistent", "fallback") == "fallback"

    def test_set_value(self, config):
        result = config.set("max_concurrent_missions", 10)
        assert result is True
        assert config.get("max_concurrent_missions") == 10

    def test_set_unknown_key_returns_false(self, config):
        result = config.set("invalid_key", "value")
        assert result is False

    def test_set_unknown_key_does_not_persist(self, config):
        config.set("invalid_key", "value")
        assert config.get("invalid_key") is None

    def test_set_boolean_value(self, config):
        config.set("require_human_approval", False)
        assert config.get("require_human_approval") is False

    def test_set_float_value(self, config):
        config.set("auto_approve_threshold", 0.95)
        assert config.get("auto_approve_threshold") == 0.95

    def test_get_all(self, config):
        config.set("max_concurrent_missions", 8)
        all_config = config.get_all()
        assert all_config["max_concurrent_missions"] == 8
        assert all_config["cooldown_seconds"] == 60

    def test_get_all_contains_all_defaults(self, config):
        all_config = config.get_all()
        for key in DEFAULT_THRESHOLDS:
            assert key in all_config

    def test_reset_single_key(self, config):
        config.set("max_concurrent_missions", 100)
        result = config.reset("max_concurrent_missions")
        assert result is True
        assert config.get("max_concurrent_missions") == DEFAULT_THRESHOLDS["max_concurrent_missions"]

    def test_reset_unknown_key_returns_false(self, config):
        result = config.reset("nonexistent")
        assert result is False

    def test_reset_all(self, config):
        config.set("max_concurrent_missions", 99)
        config.set("cooldown_seconds", 999)
        config.reset_all()
        all_config = config.get_all()
        assert all_config["max_concurrent_missions"] == DEFAULT_THRESHOLDS["max_concurrent_missions"]
        assert all_config["cooldown_seconds"] == DEFAULT_THRESHOLDS["cooldown_seconds"]

    def test_persistence(self, temp_config_path):
        c1 = AutonomyConfig(storage_path=temp_config_path)
        c1.set("max_concurrent_missions", 20)

        c2 = AutonomyConfig(storage_path=temp_config_path)
        assert c2.get("max_concurrent_missions") == 20

    def test_initial_values_match_defaults(self, config):
        all_config = config.get_all()
        for key, val in DEFAULT_THRESHOLDS.items():
            assert all_config[key] == val

    def test_set_non_default_key_then_reset_all(self, config):
        config.set("auto_resolve_conflicts", True)
        assert config.get("auto_resolve_conflicts") is True
        config.reset_all()
        assert config.get("auto_resolve_conflicts") is False
