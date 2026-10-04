"""Tests for the environment-driven API configuration (TSD-003)."""

from __future__ import annotations

import pytest

from calvino.api.config import ApiSettings, settings_from_env


def test_defaults_point_at_local_storage():
    settings = settings_from_env({})
    assert settings.data_dir.name == ".calvino-data"
    assert settings.decisions_log.name == "decisions.jsonl"
    assert settings.checkpoint_db.name == "checkpoints.sqlite"
    assert settings.demo_rate_limit_per_minute == 30


def test_environment_overrides_everything(tmp_path):
    settings = settings_from_env(
        {
            "CALVINO_DATA_DIR": str(tmp_path / "mounted"),
            "CALVINO_DEMO_RATE_LIMIT": "5",
        }
    )
    assert settings.decisions_log == tmp_path / "mounted" / "decisions.jsonl"
    assert settings.checkpoint_db == tmp_path / "mounted" / "checkpoints.sqlite"
    assert settings.demo_rate_limit_per_minute == 5


def test_rate_limit_must_be_positive():
    with pytest.raises(ValueError):
        ApiSettings(demo_rate_limit_per_minute=0)
