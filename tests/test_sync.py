"""Tests for sync logic."""
from __future__ import annotations
from unittest.mock import Mock, MagicMock, patch, call
import pytest
from jira.exceptions import JIRAError
from jira_ss_progress.sync import (
    run_sync,
    _label_from_cat,
    PreviewRow,
    SyncResult,
)
from jira_ss_progress.config import Config
from jira_ss_progress.jira_utils import JiraFieldIds


class TestLabelFromCat:
    """Tests for status category label conversion."""

    def test_label_from_cat_done(self):
        """Test 'done' converts to 'Complete'."""
        assert _label_from_cat("done") == "Complete"

    def test_label_from_cat_indeterminate(self):
        """Test 'indeterminate' converts to 'In Progress'."""
        assert _label_from_cat("indeterminate") == "In Progress"

    def test_label_from_cat_new(self):
        """Test 'new' converts to 'Not Started'."""
        assert _label_from_cat("new") == "Not Started"

    def test_label_from_cat_case_insensitive(self):
        """Test conversion is case-insensitive."""
        assert _label_from_cat("DONE") == "Complete"
        assert _label_from_cat("Done") == "Complete"

    def test_label_from_cat_unknown(self):
        """Test unknown category returns 'Not Started'."""
        assert _label_from_cat("unknown") == "Not Started"

    def test_label_from_cat_empty(self):
        """Test empty string returns 'Not Started'."""
        assert _label_from_cat("") == "Not Started"

    def test_label_from_cat_none(self):
        """Test None returns 'Not Started'."""
        assert _label_from_cat(None) == "Not Started"


class TestRunSync:
    """Tests for the main run_sync function."""

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
    def mock_jira(self):
        """Create a mock Jira client."""
        jira = Mock()
        jira.fields.return_value = [
            {"id": "customfield_10001", "name": "Story Points"},
            {"id": "customfield_10002", "name": "Epic Link"},
        ]
        return jira

    @pytest.fixture
    def mock_sheet(self):
        """Create a mock Smartsheet sheet."""
        sheet = Mock()

        # Create columns
        col_jira = Mock()
        col_jira.id = 1001
        col_jira.title = "Jira"

        col_progress = Mock()
        col_progress.id = 1002
        col_progress.title = "% Complete"

        col_status = Mock()
        col_status.id = 1003
        col_status.title = "Status"

        sheet.columns = [col_jira, col_progress, col_status]
        sheet.rows = []

        return sheet

    def create_sheet_row(self, row_id: int, jira_key: str, progress: float = 0.0, status: str = None):
        """Helper to create a mock sheet row."""
        row = Mock()
        row.id = row_id

        # Jira cell
        cell_jira = Mock()
        cell_jira.column_id = 1001
        cell_jira.hyperlink = None
        cell_jira.value = jira_key
        cell_jira.display_value = jira_key

        # Progress cell
        cell_progress = Mock()
        cell_progress.column_id = 1002
        cell_progress.value = progress
        cell_progress.display_value = f"{progress * 100}%"

        # Status cell
        cell_status = Mock()
        cell_status.column_id = 1003
        cell_status.value = status
        cell_status.display_value = status

        row.cells = [cell_jira, cell_progress, cell_status]
        return row

    @patch("jira_ss_progress.sync.SU.client")
    @patch("jira_ss_progress.sync.SU.get_sheet")
    @patch("jira_ss_progress.sync.JU.connect")
    @patch("jira_ss_progress.sync.JU.resolve_field_ids")
    @patch("jira_ss_progress.sync.JU.resolve_configured_field")
    def test_run_sync_basic_flow(
        self,
        mock_resolve_field,
        mock_resolve_ids,
        mock_connect,
        mock_get_sheet,
        mock_client,
        mock_config,
        mock_jira,
        mock_sheet,
    ):
        """Test basic sync flow with one epic."""
        mock_connect.return_value = mock_jira
        mock_resolve_ids.return_value = JiraFieldIds(
            story_points=["customfield_10001"],
            epic_link="customfield_10002"
        )
        mock_resolve_field.side_effect = [None, None]  # No date fields
        mock_client.return_value = Mock()

        # Add a row to the sheet
        row = self.create_sheet_row(5001, "EPIC-123", 0.5, "In Progress")
        mock_sheet.rows = [row]
        mock_get_sheet.return_value = mock_sheet

        # Mock Jira issue type query
        mock_issue = Mock()
        mock_issue.fields.issuetype.name = "Epic"
        mock_jira.issue.return_value = mock_issue

        # Mock epic progress
        with patch("jira_ss_progress.sync.JU.epic_progress_details") as mock_epic_progress:
            mock_epic_progress.return_value = (0.75, {
                "metric": "points",
                "total": 10.0,
                "status": "In Progress",
            })

            with patch("jira_ss_progress.sync.JU.get_issue_dates") as mock_get_dates:
                mock_get_dates.return_value = {"start": None, "end": None}

                result = run_sync(mock_config)

        assert isinstance(result, SyncResult)
        assert len(result.preview) == 1
        assert result.preview[0].issue_key == "EPIC-123"
        assert result.preview[0].type == "epic"

    @patch("jira_ss_progress.sync.SU.client")
    @patch("jira_ss_progress.sync.SU.get_sheet")
    @patch("jira_ss_progress.sync.JU.connect")
    @patch("jira_ss_progress.sync.JU.resolve_field_ids")
    @patch("jira_ss_progress.sync.JU.resolve_configured_field")
    def test_run_sync_protection_prevents_overwrite(
        self,
        mock_resolve_field,
        mock_resolve_ids,
        mock_connect,
        mock_get_sheet,
        mock_client,
        mock_config,
        mock_jira,
        mock_sheet,
    ):
        """Test that protection prevents overwriting non-zero progress with 0."""
        mock_connect.return_value = mock_jira
        mock_resolve_ids.return_value = JiraFieldIds(
            story_points=["customfield_10001"],
            epic_link="customfield_10002"
        )
        mock_resolve_field.side_effect = [None, None]
        mock_client.return_value = Mock()

        # Add a row with existing progress
        row = self.create_sheet_row(5001, "STORY-456", 0.8, "In Progress")
        mock_sheet.rows = [row]
        mock_get_sheet.return_value = mock_sheet

        # Mock Jira issue type query
        mock_issue = Mock()
        mock_issue.fields.issuetype.name = "Story"
        mock_jira.issue.return_value = mock_issue

        # Mock story progress returning 0 (not done)
        with patch("jira_ss_progress.sync.JU.story_progress_details") as mock_story_progress:
            mock_story_progress.return_value = (0.0, {
                "metric": "story",
                "total": 1,
                "status": "Not Started",
                "raw_status": "To Do",
                "status_category": "new",
            })

            with patch("jira_ss_progress.sync.JU.get_issue_dates") as mock_get_dates:
                mock_get_dates.return_value = {"start": None, "end": None}

                result = run_sync(mock_config)

        # Check protection worked
        assert result.preview[0].protected is True
        assert result.preview[0].existing_pct == 80.0
        assert result.preview[0].new_pct == 0.0
        assert result.preview[0].final_pct == 80.0  # Protected, kept existing

    @patch("jira_ss_progress.sync.SU.client")
    @patch("jira_ss_progress.sync.SU.get_sheet")
    @patch("jira_ss_progress.sync.JU.connect")
    @patch("jira_ss_progress.sync.JU.resolve_field_ids")
    @patch("jira_ss_progress.sync.JU.resolve_configured_field")
    def test_run_sync_blocked_status_preserved(
        self,
        mock_resolve_field,
        mock_resolve_ids,
        mock_connect,
        mock_get_sheet,
        mock_client,
        mock_config,
        mock_jira,
        mock_sheet,
    ):
        """Test that 'Blocked' status is always preserved."""
        mock_connect.return_value = mock_jira
        mock_resolve_ids.return_value = JiraFieldIds(
            story_points=["customfield_10001"],
            epic_link="customfield_10002"
        )
        mock_resolve_field.side_effect = [None, None]
        mock_client.return_value = Mock()

        # Add a row with Blocked status
        row = self.create_sheet_row(5001, "STORY-789", 0.5, "Blocked")
        mock_sheet.rows = [row]
        mock_get_sheet.return_value = mock_sheet

        # Mock Jira issue type query
        mock_issue = Mock()
        mock_issue.fields.issuetype.name = "Story"
        mock_jira.issue.return_value = mock_issue

        # Mock story progress
        with patch("jira_ss_progress.sync.JU.story_progress_details") as mock_story_progress:
            mock_story_progress.return_value = (0.5, {
                "metric": "story",
                "total": 1,
                "status": "In Progress",
                "raw_status": "In Progress",
                "status_category": "indeterminate",
            })

            with patch("jira_ss_progress.sync.JU.get_issue_dates") as mock_get_dates:
                mock_get_dates.return_value = {"start": None, "end": None}

                result = run_sync(mock_config)

        # Check Blocked status preserved
        assert result.preview[0].existing_status == "Blocked"
        assert result.preview[0].new_status == "In Progress"
        assert result.preview[0].final_status == "Blocked"  # Preserved

    @patch("jira_ss_progress.sync.SU.client")
    @patch("jira_ss_progress.sync.SU.get_sheet")
    @patch("jira_ss_progress.sync.JU.connect")
    @patch("jira_ss_progress.sync.JU.resolve_field_ids")
    @patch("jira_ss_progress.sync.JU.resolve_configured_field")
    def test_run_sync_100_percent_forces_complete(
        self,
        mock_resolve_field,
        mock_resolve_ids,
        mock_connect,
        mock_get_sheet,
        mock_client,
        mock_config,
        mock_jira,
        mock_sheet,
    ):
        """Test that 100% progress forces 'Complete' status."""
        mock_connect.return_value = mock_jira
        mock_resolve_ids.return_value = JiraFieldIds(
            story_points=["customfield_10001"],
            epic_link="customfield_10002"
        )
        mock_resolve_field.side_effect = [None, None]
        mock_client.return_value = Mock()

        # Add a row
        row = self.create_sheet_row(5001, "STORY-999", 0.5, "In Progress")
        mock_sheet.rows = [row]
        mock_get_sheet.return_value = mock_sheet

        # Mock Jira issue type query
        mock_issue = Mock()
        mock_issue.fields.issuetype.name = "Story"
        mock_jira.issue.return_value = mock_issue

        # Mock story progress returning 100%
        with patch("jira_ss_progress.sync.JU.story_progress_details") as mock_story_progress:
            mock_story_progress.return_value = (1.0, {
                "metric": "story",
                "total": 1,
                "status": "Complete",
                "raw_status": "Done",
                "status_category": "done",
            })

            with patch("jira_ss_progress.sync.JU.get_issue_dates") as mock_get_dates:
                mock_get_dates.return_value = {"start": None, "end": None}

                result = run_sync(mock_config)

        # Check Complete status forced
        assert result.preview[0].final_pct == 100.0
        assert result.preview[0].final_status == "Complete"

    @patch("jira_ss_progress.sync.SU.client")
    @patch("jira_ss_progress.sync.SU.get_sheet")
    @patch("jira_ss_progress.sync.JU.connect")
    @patch("jira_ss_progress.sync.JU.resolve_field_ids")
    @patch("jira_ss_progress.sync.JU.resolve_configured_field")
    def test_run_sync_handles_404_deleted_issue(
        self,
        mock_resolve_field,
        mock_resolve_ids,
        mock_connect,
        mock_get_sheet,
        mock_client,
        mock_config,
        mock_jira,
        mock_sheet,
    ):
        """Test handling of deleted Jira issues (404)."""
        mock_connect.return_value = mock_jira
        mock_resolve_ids.return_value = JiraFieldIds(
            story_points=["customfield_10001"],
            epic_link="customfield_10002"
        )
        mock_resolve_field.side_effect = [None, None]
        mock_client.return_value = Mock()

        # Add a row
        row = self.create_sheet_row(5001, "DELETED-404", 0.5, "In Progress")
        mock_sheet.rows = [row]
        mock_get_sheet.return_value = mock_sheet

        # Mock Jira issue type query raising 404
        error = JIRAError(status_code=404, text="Not Found")
        mock_jira.issue.side_effect = error

        result = run_sync(mock_config)

        # Should skip the issue without crashing
        assert len(result.preview) == 0

    @patch("jira_ss_progress.sync.SU.client")
    @patch("jira_ss_progress.sync.SU.get_sheet")
    @patch("jira_ss_progress.sync.JU.connect")
    @patch("jira_ss_progress.sync.JU.resolve_field_ids")
    @patch("jira_ss_progress.sync.JU.resolve_configured_field")
    def test_run_sync_caches_epic_calculations(
        self,
        mock_resolve_field,
        mock_resolve_ids,
        mock_connect,
        mock_get_sheet,
        mock_client,
        mock_config,
        mock_jira,
        mock_sheet,
    ):
        """Test that epic calculations are cached."""
        mock_connect.return_value = mock_jira
        mock_resolve_ids.return_value = JiraFieldIds(
            story_points=["customfield_10001"],
            epic_link="customfield_10002"
        )
        mock_resolve_field.side_effect = [None, None]
        mock_client.return_value = Mock()

        # Add two rows for the same epic
        row1 = self.create_sheet_row(5001, "EPIC-100", 0.0, "Not Started")
        row2 = self.create_sheet_row(5002, "EPIC-100", 0.0, "Not Started")
        mock_sheet.rows = [row1, row2]
        mock_get_sheet.return_value = mock_sheet

        # Mock Jira issue type query
        mock_issue = Mock()
        mock_issue.fields.issuetype.name = "Epic"
        mock_jira.issue.return_value = mock_issue

        # Mock epic progress
        with patch("jira_ss_progress.sync.JU.epic_progress_details") as mock_epic_progress:
            mock_epic_progress.return_value = (0.5, {
                "metric": "count",
                "total": 10,
                "status": "In Progress",
            })

            with patch("jira_ss_progress.sync.JU.get_issue_dates") as mock_get_dates:
                mock_get_dates.return_value = {"start": None, "end": None}

                result = run_sync(mock_config)

        # epic_progress_details should be called only once (cached for second row)
        assert mock_epic_progress.call_count == 1
        assert len(result.preview) == 2

    @patch("jira_ss_progress.sync.SU.client")
    @patch("jira_ss_progress.sync.SU.get_sheet")
    @patch("jira_ss_progress.sync.JU.connect")
    @patch("jira_ss_progress.sync.JU.resolve_field_ids")
    @patch("jira_ss_progress.sync.JU.resolve_configured_field")
    def test_run_sync_skips_rows_without_jira_key(
        self,
        mock_resolve_field,
        mock_resolve_ids,
        mock_connect,
        mock_get_sheet,
        mock_client,
        mock_config,
        mock_jira,
        mock_sheet,
    ):
        """Test that rows without Jira keys are skipped."""
        mock_connect.return_value = mock_jira
        mock_resolve_ids.return_value = JiraFieldIds(
            story_points=["customfield_10001"],
            epic_link="customfield_10002"
        )
        mock_resolve_field.side_effect = [None, None]
        mock_client.return_value = Mock()
        mock_get_sheet.return_value = mock_sheet

        # Create a row without a Jira key
        row = Mock()
        row.id = 5001
        cell_jira = Mock()
        cell_jira.column_id = 1001
        cell_jira.hyperlink = None
        cell_jira.value = None
        cell_jira.display_value = None
        row.cells = [cell_jira]

        mock_sheet.rows = [row]

        result = run_sync(mock_config)

        # Should have no preview rows
        assert len(result.preview) == 0

    @patch("jira_ss_progress.sync.SU.chunk")
    @patch("jira_ss_progress.sync.SU.get_sheet")
    @patch("jira_ss_progress.sync.SU.client")
    @patch("jira_ss_progress.sync.JU.resolve_configured_field")
    @patch("jira_ss_progress.sync.JU.resolve_field_ids")
    @patch("jira_ss_progress.sync.JU.connect")
    def test_run_sync_batch_updates_when_not_dry_run(
        self,
        mock_connect,
        mock_resolve_ids,
        mock_resolve_field,
        mock_client,
        mock_get_sheet,
        mock_chunk,
        mock_config,
        mock_jira,
        mock_sheet,
    ):
        """Test that updates are batched when not in dry-run mode."""
        # Set dry_run to False
        config = Config(
            jira_base_url="https://test.atlassian.net",
            jira_email="test@example.com",
            jira_api_token="test_token",
            smartsheet_token="ss_token",
            sheet_id=12345,
            dry_run=False,  # Not dry run
        )

        mock_ss_client = Mock()
        mock_connect.return_value = mock_jira
        mock_resolve_ids.return_value = JiraFieldIds(
            story_points=["customfield_10001"],
            epic_link="customfield_10002"
        )
        mock_resolve_field.side_effect = [None, None]
        mock_client.return_value = mock_ss_client

        # Add a row that will need updating
        row = self.create_sheet_row(5001, "STORY-111", 0.0, "Not Started")
        mock_sheet.rows = [row]
        mock_get_sheet.return_value = mock_sheet

        # Mock Jira issue type query
        mock_issue = Mock()
        mock_issue.fields.issuetype.name = "Story"
        mock_jira.issue.return_value = mock_issue

        # Mock story progress returning 100% (will trigger update)
        with patch("jira_ss_progress.sync.JU.story_progress_details") as mock_story_progress:
            mock_story_progress.return_value = (1.0, {
                "metric": "story",
                "total": 1,
                "status": "Complete",
                "raw_status": "Done",
                "status_category": "done",
            })

            with patch("jira_ss_progress.sync.JU.get_issue_dates") as mock_get_dates:
                mock_get_dates.return_value = {"start": None, "end": None}

                # Mock chunk to return single batch
                mock_chunk.return_value = [[Mock()]]

                result = run_sync(config)

        # Should have called update_rows
        assert mock_ss_client.Sheets.update_rows.called
        assert result.updated_rows > 0
