"""Tests for configuration loading and validation."""
from __future__ import annotations
import os
import pytest
from jira_ss_progress.config import Config, load_config, _as_bool


class TestAsBool:
    """Tests for the _as_bool helper function."""

    def test_none_returns_default(self):
        assert _as_bool(None) is False
        assert _as_bool(None, True) is True

    def test_truthy_values(self):
        for val in ["1", "true", "TRUE", "True", "yes", "YES", "y", "Y", "on", "ON"]:
            assert _as_bool(val) is True, f"Failed for: {val}"

    def test_falsy_values(self):
        for val in ["0", "false", "FALSE", "no", "NO", "off", "OFF", ""]:
            assert _as_bool(val) is False, f"Failed for: {val}"

    def test_whitespace_handling(self):
        assert _as_bool("  true  ") is True
        assert _as_bool("  false  ") is False


class TestConfig:
    """Tests for the Config dataclass."""

    def test_config_is_frozen(self):
        """Config should be immutable."""
        cfg = Config(
            jira_base_url="https://example.atlassian.net",
            jira_email="test@example.com",
            jira_api_token="token123",
            smartsheet_token="ss_token",
            sheet_id=12345
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            cfg.jira_base_url = "https://newurl.com"  # type: ignore

    def test_config_defaults(self):
        """Default values should be set correctly."""
        cfg = Config(
            jira_base_url="https://example.atlassian.net",
            jira_email="test@example.com",
            jira_api_token="token123",
            smartsheet_token="ss_token",
            sheet_id=12345
        )
        assert cfg.jira_col_title == "Jira"
        assert cfg.progress_col_title == "% Complete"
        assert cfg.status_col_title == "Status"
        assert cfg.dry_run is False
        assert cfg.protect_existing_nonzero is True
        assert cfg.include_subtasks is False
        assert cfg.log_level == "INFO"


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_load_config_success(self, monkeypatch):
        """Test successful configuration loading."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "test_token_123")
        monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "smartsheet_token")
        monkeypatch.setenv("SS_SHEET_ID", "98765")

        cfg = load_config()

        assert cfg.jira_base_url == "https://test.atlassian.net"
        assert cfg.jira_email == "user@example.com"
        assert cfg.jira_api_token == "test_token_123"
        assert cfg.smartsheet_token == "smartsheet_token"
        assert cfg.sheet_id == 98765

    def test_load_config_strips_trailing_slash(self, monkeypatch):
        """Jira base URL should have trailing slash removed."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net/")
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "test_token")
        monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "ss_token")
        monkeypatch.setenv("SS_SHEET_ID", "12345")

        cfg = load_config()
        assert cfg.jira_base_url == "https://test.atlassian.net"

    def test_load_config_missing_jira_url(self, monkeypatch):
        """Should raise ValueError when Jira URL is missing."""
        # Disable dotenv loading to prevent .env file interference
        monkeypatch.setattr("jira_ss_progress.config.load_dotenv", None)

        # Clear ALL relevant env vars first
        for var in ["JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "SMARTSHEET_ACCESS_TOKEN", "SS_SHEET_ID"]:
            monkeypatch.delenv(var, raising=False)

        # Set only what we want
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "ss_token")
        monkeypatch.setenv("SS_SHEET_ID", "12345")
        # Don't set JIRA_BASE_URL

        with pytest.raises(ValueError, match="Missing Jira config"):
            load_config()

    def test_load_config_missing_jira_email(self, monkeypatch):
        """Should raise ValueError when Jira email is missing."""
        # Disable dotenv loading to prevent .env file interference
        monkeypatch.setattr("jira_ss_progress.config.load_dotenv", None)

        # Clear ALL relevant env vars first
        for var in ["JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "SMARTSHEET_ACCESS_TOKEN", "SS_SHEET_ID"]:
            monkeypatch.delenv(var, raising=False)

        # Set only what we want
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "ss_token")
        monkeypatch.setenv("SS_SHEET_ID", "12345")
        # Don't set JIRA_EMAIL

        with pytest.raises(ValueError, match="Missing Jira config"):
            load_config()

    def test_load_config_missing_smartsheet_token(self, monkeypatch):
        """Should raise ValueError when Smartsheet token is missing."""
        # Disable dotenv loading to prevent .env file interference
        monkeypatch.setattr("jira_ss_progress.config.load_dotenv", None)

        # Clear ALL relevant env vars first
        for var in ["JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "SMARTSHEET_ACCESS_TOKEN", "SS_SHEET_ID"]:
            monkeypatch.delenv(var, raising=False)

        # Set only what we want
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        monkeypatch.setenv("SS_SHEET_ID", "12345")
        # Don't set SMARTSHEET_ACCESS_TOKEN

        with pytest.raises(ValueError, match="Missing Smartsheet config"):
            load_config()

    def test_load_config_invalid_sheet_id(self, monkeypatch):
        """Should raise ValueError when sheet ID is not an integer."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "ss_token")
        monkeypatch.setenv("SS_SHEET_ID", "not_a_number")

        with pytest.raises(ValueError, match="SS_SHEET_ID must be an integer"):
            load_config()

    def test_load_config_zero_sheet_id(self, monkeypatch):
        """Should raise ValueError when sheet ID is zero."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "ss_token")
        monkeypatch.setenv("SS_SHEET_ID", "0")

        with pytest.raises(ValueError, match="Missing Smartsheet config"):
            load_config()

    def test_load_config_custom_columns(self, monkeypatch):
        """Test loading custom column names."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "ss_token")
        monkeypatch.setenv("SS_SHEET_ID", "12345")
        monkeypatch.setenv("SS_JIRA_COL", "Ticket")
        monkeypatch.setenv("SS_PROG_COL", "Progress")
        monkeypatch.setenv("SS_STATUS_COL", "State")

        cfg = load_config()
        assert cfg.jira_col_title == "Ticket"
        assert cfg.progress_col_title == "Progress"
        assert cfg.status_col_title == "State"

    def test_load_config_boolean_flags(self, monkeypatch):
        """Test loading boolean configuration flags."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "ss_token")
        monkeypatch.setenv("SS_SHEET_ID", "12345")
        monkeypatch.setenv("DRY_RUN", "true")
        monkeypatch.setenv("PROTECT_EXISTING_NONZERO", "false")
        monkeypatch.setenv("INCLUDE_SUBTASKS", "yes")

        cfg = load_config()
        assert cfg.dry_run is True
        assert cfg.protect_existing_nonzero is False
        assert cfg.include_subtasks is True

    def test_load_config_custom_jira_fields(self, monkeypatch):
        """Test loading custom Jira field configurations."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "ss_token")
        monkeypatch.setenv("SS_SHEET_ID", "12345")
        monkeypatch.setenv("JIRA_START_FIELD", "customfield_10001")
        monkeypatch.setenv("JIRA_END_FIELD", "customfield_10002")

        cfg = load_config()
        assert cfg.jira_start_field == "customfield_10001"
        assert cfg.jira_end_field == "customfield_10002"

    def test_load_config_log_level(self, monkeypatch):
        """Test loading custom log level."""
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "user@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "ss_token")
        monkeypatch.setenv("SS_SHEET_ID", "12345")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        cfg = load_config()
        assert cfg.log_level == "DEBUG"
