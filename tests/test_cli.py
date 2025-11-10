"""Tests for CLI entry point."""
from __future__ import annotations
from unittest.mock import Mock, patch, call
from io import StringIO
import sys
import pytest
from jira_ss_progress.cli import main
from jira_ss_progress.config import Config
from jira_ss_progress.sync import SyncResult, PreviewRow


class TestMain:
    """Tests for the main CLI function."""

    @pytest.fixture
    def mock_config(self):
        """Create a test configuration."""
        return Config(
            jira_base_url="https://test.atlassian.net",
            jira_email="test@example.com",
            jira_api_token="test_token",
            smartsheet_token="ss_token",
            sheet_id=12345,
            dry_run=True,
        )

    @pytest.fixture
    def sample_preview_row(self):
        """Create a sample preview row."""
        return PreviewRow(
            issue_key="PROJ-123",
            type="epic",
            metric="points",
            completed=5.0,
            total=10.0,
            existing_pct=40.0,
            new_pct=50.0,
            final_pct=50.0,
            protected=False,
            existing_status="In Progress",
            new_status="In Progress",
            final_status="In Progress",
            start_old="2024-01-01",
            start_new="2024-01-02",
            start_final="2024-01-02",
            end_old="2024-01-30",
            end_new="2024-01-31",
            end_final="2024-01-31",
        )

    @patch("jira_ss_progress.cli.run_sync")
    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync"])
    def test_main_dry_run_displays_table(
        self,
        mock_load_config,
        mock_run_sync,
        mock_config,
        sample_preview_row,
        capsys
    ):
        """Test that dry-run mode displays a preview table."""
        mock_load_config.return_value = mock_config
        mock_run_sync.return_value = SyncResult(
            updated_rows=0,
            preview=[sample_preview_row]
        )

        main()

        captured = capsys.readouterr()
        assert "PROJ-123" in captured.out
        assert "epic" in captured.out
        assert "points" in captured.out

    @patch("jira_ss_progress.cli.run_sync")
    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync"])
    def test_main_not_dry_run_displays_count(
        self,
        mock_load_config,
        mock_run_sync,
        capsys
    ):
        """Test that non-dry-run mode displays update count."""
        config = Config(
            jira_base_url="https://test.atlassian.net",
            jira_email="test@example.com",
            jira_api_token="test_token",
            smartsheet_token="ss_token",
            sheet_id=12345,
            dry_run=False,
        )
        mock_load_config.return_value = config
        mock_run_sync.return_value = SyncResult(
            updated_rows=5,
            preview=[]
        )

        main()

        captured = capsys.readouterr()
        assert "Updated 5 Smartsheet rows" in captured.out

    @patch("jira_ss_progress.cli.run_sync")
    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync", "--log-level", "DEBUG"])
    @patch("jira_ss_progress.cli.logging.basicConfig")
    def test_main_log_level_override(
        self,
        mock_basic_config,
        mock_load_config,
        mock_run_sync,
        mock_config
    ):
        """Test that --log-level argument overrides config."""
        mock_load_config.return_value = mock_config
        mock_run_sync.return_value = SyncResult(updated_rows=0, preview=[])

        main()

        # Check that basicConfig was called with DEBUG level
        assert mock_basic_config.called
        call_args = mock_basic_config.call_args
        assert call_args[1]["level"] == "DEBUG"

    @patch("jira_ss_progress.cli.run_sync")
    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync"])
    @patch("jira_ss_progress.cli.logging.basicConfig")
    def test_main_uses_config_log_level(
        self,
        mock_basic_config,
        mock_load_config,
        mock_run_sync
    ):
        """Test that config log level is used when no override."""
        config = Config(
            jira_base_url="https://test.atlassian.net",
            jira_email="test@example.com",
            jira_api_token="test_token",
            smartsheet_token="ss_token",
            sheet_id=12345,
            log_level="WARNING",
        )
        mock_load_config.return_value = config
        mock_run_sync.return_value = SyncResult(updated_rows=0, preview=[])

        main()

        call_args = mock_basic_config.call_args
        assert call_args[1]["level"] == "WARNING"

    @patch("jira_ss_progress.cli.run_sync")
    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync"])
    def test_main_dry_run_table_formatting(
        self,
        mock_load_config,
        mock_run_sync,
        mock_config,
        capsys
    ):
        """Test detailed table formatting in dry-run mode."""
        preview = [
            PreviewRow(
                issue_key="STORY-456",
                type="story",
                metric="story",
                completed=1,
                total=1,
                existing_pct=0.0,
                new_pct=100.0,
                final_pct=100.0,
                protected=False,
                existing_status="Not Started",
                new_status="Complete",
                final_status="Complete",
                start_old=None,
                start_new="2024-01-15",
                start_final="2024-01-15",
                end_old=None,
                end_new="2024-01-30",
                end_final="2024-01-30",
            )
        ]
        mock_load_config.return_value = mock_config
        mock_run_sync.return_value = SyncResult(updated_rows=0, preview=preview)

        main()

        captured = capsys.readouterr()
        # Check for key elements in table
        assert "STORY-456" in captured.out
        assert "story" in captured.out
        assert "100.00%" in captured.out
        assert "Complete" in captured.out
        assert "False" in captured.out

    @patch("jira_ss_progress.cli.run_sync")
    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync"])
    def test_main_dry_run_protected_shown(
        self,
        mock_load_config,
        mock_run_sync,
        mock_config,
        capsys
    ):
        """Test that protection flag is shown in dry-run table."""
        preview = [
            PreviewRow(
                issue_key="STORY-789",
                type="story",
                metric="story",
                completed=0,
                total=1,
                existing_pct=80.0,
                new_pct=0.0,
                final_pct=80.0,
                protected=True,  # Protected
                existing_status="In Progress",
                new_status="Not Started",
                final_status="In Progress",
                start_old=None,
                start_new=None,
                start_final=None,
                end_old=None,
                end_new=None,
                end_final=None,
            )
        ]
        mock_load_config.return_value = mock_config
        mock_run_sync.return_value = SyncResult(updated_rows=0, preview=preview)

        main()

        captured = capsys.readouterr()
        assert "True" in captured.out  # Protection flag
        assert "80.00%" in captured.out  # Final kept at 80%

    @patch("jira_ss_progress.cli.run_sync")
    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync"])
    def test_main_dry_run_sorts_by_type_and_key(
        self,
        mock_load_config,
        mock_run_sync,
        mock_config,
        capsys
    ):
        """Test that preview rows are sorted by type then key."""
        preview = [
            PreviewRow(
                issue_key="STORY-999",
                type="story",
                metric="story",
                completed=0,
                total=1,
                existing_pct=0.0,
                new_pct=0.0,
                final_pct=0.0,
                protected=False,
                existing_status=None,
                new_status="Not Started",
                final_status="Not Started",
                start_old=None,
                start_new=None,
                start_final=None,
                end_old=None,
                end_new=None,
                end_final=None,
            ),
            PreviewRow(
                issue_key="EPIC-100",
                type="epic",
                metric="count",
                completed=5,
                total=10,
                existing_pct=0.0,
                new_pct=50.0,
                final_pct=50.0,
                protected=False,
                existing_status=None,
                new_status="In Progress",
                final_status="In Progress",
                start_old=None,
                start_new=None,
                start_final=None,
                end_old=None,
                end_new=None,
                end_final=None,
            ),
        ]
        mock_load_config.return_value = mock_config
        mock_run_sync.return_value = SyncResult(updated_rows=0, preview=preview)

        main()

        captured = capsys.readouterr()
        # Epic should come before Story in output
        epic_pos = captured.out.find("EPIC-100")
        story_pos = captured.out.find("STORY-999")
        assert epic_pos < story_pos

    @patch("jira_ss_progress.cli.run_sync")
    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync"])
    def test_main_dry_run_shows_dates(
        self,
        mock_load_config,
        mock_run_sync,
        mock_config,
        sample_preview_row,
        capsys
    ):
        """Test that dates are shown in dry-run table."""
        mock_load_config.return_value = mock_config
        mock_run_sync.return_value = SyncResult(
            updated_rows=0,
            preview=[sample_preview_row]
        )

        main()

        captured = capsys.readouterr()
        assert "2024-01-01" in captured.out  # start_old
        assert "2024-01-02" in captured.out  # start_new/final
        assert "2024-01-30" in captured.out  # end_old
        assert "2024-01-31" in captured.out  # end_new/final

    @patch("jira_ss_progress.cli.run_sync")
    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync"])
    def test_main_dry_run_empty_preview(
        self,
        mock_load_config,
        mock_run_sync,
        mock_config,
        capsys
    ):
        """Test dry-run with no rows to preview."""
        mock_load_config.return_value = mock_config
        mock_run_sync.return_value = SyncResult(updated_rows=0, preview=[])

        main()

        captured = capsys.readouterr()
        # Should still show header
        assert "Issue" in captured.out
        assert "Type" in captured.out

    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync"])
    def test_main_config_error_propagates(self, mock_load_config):
        """Test that configuration errors propagate."""
        mock_load_config.side_effect = ValueError("Missing config")

        with pytest.raises(ValueError, match="Missing config"):
            main()

    @patch("jira_ss_progress.cli.run_sync")
    @patch("jira_ss_progress.cli.load_config")
    @patch("sys.argv", ["jira-ss-sync"])
    def test_main_sync_error_propagates(self, mock_load_config, mock_run_sync, mock_config):
        """Test that sync errors propagate."""
        mock_load_config.return_value = mock_config
        mock_run_sync.side_effect = Exception("Sync failed")

        with pytest.raises(Exception, match="Sync failed"):
            main()
