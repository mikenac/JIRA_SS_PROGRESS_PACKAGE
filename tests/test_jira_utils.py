"""Tests for Jira utility functions."""
from __future__ import annotations
from unittest.mock import Mock, MagicMock, patch
import pytest
from jira_ss_progress.jira_utils import (
    connect,
    resolve_field_ids,
    resolve_configured_field,
    get_issue_dates,
    update_issue_dates,
    epic_progress_details,
    story_progress_details,
    status_category_key,
    is_done,
    get_story_points,
    epic_children,
    search_all,
    JiraFieldIds,
)


class TestConnect:
    """Tests for Jira connection."""

    @patch("jira_ss_progress.jira_utils.JIRA")
    def test_connect_creates_jira_client(self, mock_jira_class):
        """Test that connect creates JIRA client with correct auth."""
        mock_client = Mock()
        mock_jira_class.return_value = mock_client

        result = connect("https://example.atlassian.net", "user@example.com", "token123")

        mock_jira_class.assert_called_once_with(
            server="https://example.atlassian.net",
            basic_auth=("user@example.com", "token123")
        )
        assert result == mock_client


class TestResolveFieldIds:
    """Tests for field ID resolution."""

    def test_resolve_field_ids_finds_story_points(self):
        """Test finding Story Points field."""
        mock_jira = Mock()
        mock_jira.fields.return_value = [
            {"id": "customfield_10001", "name": "Story Points"},
            {"id": "customfield_10002", "name": "Epic Link"},
            {"id": "summary", "name": "Summary"}
        ]

        result = resolve_field_ids(mock_jira)

        assert "customfield_10001" in result.story_points
        assert result.epic_link == "customfield_10002"

    def test_resolve_field_ids_finds_story_point_estimate(self):
        """Test finding Story Point Estimate field."""
        mock_jira = Mock()
        mock_jira.fields.return_value = [
            {"id": "customfield_10003", "name": "Story Point Estimate"},
        ]

        result = resolve_field_ids(mock_jira)

        assert "customfield_10003" in result.story_points

    def test_resolve_field_ids_case_insensitive(self):
        """Test that field resolution is case-insensitive."""
        mock_jira = Mock()
        mock_jira.fields.return_value = [
            {"id": "customfield_10001", "name": "STORY POINTS"},
            {"id": "customfield_10002", "name": "epic link"},
        ]

        result = resolve_field_ids(mock_jira)

        assert "customfield_10001" in result.story_points
        assert result.epic_link == "customfield_10002"

    def test_resolve_field_ids_no_fields_found(self):
        """Test when no relevant fields are found."""
        mock_jira = Mock()
        mock_jira.fields.return_value = [
            {"id": "summary", "name": "Summary"},
            {"id": "description", "name": "Description"}
        ]

        result = resolve_field_ids(mock_jira)

        assert result.story_points == []
        assert result.epic_link is None


class TestResolveConfiguredField:
    """Tests for configured field resolution."""

    def test_resolve_duedate_field(self):
        """Test that 'duedate' is returned as-is."""
        mock_jira = Mock()
        result = resolve_configured_field(mock_jira, "duedate")
        assert result == "duedate"

    def test_resolve_customfield_id(self):
        """Test that customfield IDs are returned as-is."""
        mock_jira = Mock()
        result = resolve_configured_field(mock_jira, "customfield_12345")
        assert result == "customfield_12345"

    def test_resolve_field_by_name(self):
        """Test resolving field by display name."""
        mock_jira = Mock()
        mock_jira.fields.return_value = [
            {"id": "customfield_10001", "name": "Start Date"},
        ]

        result = resolve_configured_field(mock_jira, "Start Date")
        assert result == "customfield_10001"

    def test_resolve_field_case_insensitive(self):
        """Test that name resolution is case-insensitive."""
        mock_jira = Mock()
        mock_jira.fields.return_value = [
            {"id": "customfield_10001", "name": "Start Date"},
        ]

        result = resolve_configured_field(mock_jira, "start date")
        assert result == "customfield_10001"

    def test_resolve_field_not_found(self):
        """Test handling of field not found."""
        mock_jira = Mock()
        mock_jira.fields.return_value = []

        result = resolve_configured_field(mock_jira, "Nonexistent Field")
        assert result is None

    def test_resolve_empty_field(self):
        """Test handling of empty field name."""
        mock_jira = Mock()
        result = resolve_configured_field(mock_jira, "")
        assert result is None

    def test_resolve_none_field(self):
        """Test handling of None field name."""
        mock_jira = Mock()
        result = resolve_configured_field(mock_jira, None)  # type: ignore
        assert result is None


class TestGetIssueDates:
    """Tests for getting issue dates."""

    def test_get_issue_dates_with_both_fields(self):
        """Test getting both start and end dates."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_issue.fields = Mock(customfield_10001="2024-01-15", duedate="2024-01-30")
        mock_jira.issue.return_value = mock_issue

        result = get_issue_dates(mock_jira, "TEST-123", "customfield_10001", "duedate")

        assert result["start"] == "2024-01-15"
        assert result["end"] == "2024-01-30"

    def test_get_issue_dates_with_none_fields(self):
        """Test when no fields are requested."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_jira.issue.return_value = mock_issue

        result = get_issue_dates(mock_jira, "TEST-123", None, None)

        assert result["start"] is None
        assert result["end"] is None

    def test_get_issue_dates_missing_values(self):
        """Test when date fields have no values."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_issue.fields = Mock(spec=[])
        mock_jira.issue.return_value = mock_issue

        result = get_issue_dates(mock_jira, "TEST-123", "customfield_10001", "duedate")

        assert result["start"] is None
        assert result["end"] is None


class TestUpdateIssueDates:
    """Tests for updating issue dates."""

    def test_update_issue_dates_both_fields(self):
        """Test updating both start and end dates."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_jira.issue.return_value = mock_issue

        update_issue_dates(
            mock_jira, "TEST-123",
            "customfield_10001", "duedate",
            "2024-01-15", "2024-01-30"
        )

        mock_issue.update.assert_called_once_with(
            fields={"customfield_10001": "2024-01-15", "duedate": "2024-01-30"}
        )

    def test_update_issue_dates_only_start(self):
        """Test updating only start date."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_jira.issue.return_value = mock_issue

        update_issue_dates(
            mock_jira, "TEST-123",
            "customfield_10001", None,
            "2024-01-15", None
        )

        mock_issue.update.assert_called_once_with(fields={"customfield_10001": "2024-01-15"})

    def test_update_issue_dates_no_values(self):
        """Test that no update is sent when no values provided."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_jira.issue.return_value = mock_issue

        update_issue_dates(
            mock_jira, "TEST-123",
            "customfield_10001", "duedate",
            None, None
        )

        mock_issue.update.assert_not_called()


class TestStatusCategoryKey:
    """Tests for status category normalization."""

    def test_status_category_key_done(self):
        """Test 'done' status category."""
        issue = Mock()
        issue.fields.status.statusCategory.key = "done"
        assert status_category_key(issue) == "done"

    def test_status_category_key_new(self):
        """Test 'new' status category."""
        issue = Mock()
        issue.fields.status.statusCategory.key = "new"
        assert status_category_key(issue) == "new"

    def test_status_category_key_indeterminate(self):
        """Test 'indeterminate' status category."""
        issue = Mock()
        issue.fields.status.statusCategory.key = "indeterminate"
        assert status_category_key(issue) == "indeterminate"

    def test_status_category_key_fallback_by_name(self):
        """Test fallback to name when key is invalid."""
        issue = Mock()
        issue.fields.status.statusCategory.key = "unknown"
        issue.fields.status.statusCategory.name = "In Progress"
        assert status_category_key(issue) == "indeterminate"

    def test_status_category_key_done_by_name(self):
        """Test detecting 'done' by name."""
        issue = Mock()
        issue.fields.status.statusCategory.key = "unknown"
        issue.fields.status.statusCategory.name = "Done"
        assert status_category_key(issue) == "done"

    def test_status_category_key_complete_by_name(self):
        """Test detecting 'done' by 'complete' in name."""
        issue = Mock()
        issue.fields.status.statusCategory.key = "unknown"
        issue.fields.status.statusCategory.name = "Complete"
        assert status_category_key(issue) == "done"


class TestIsDone:
    """Tests for is_done helper."""

    def test_is_done_true(self):
        """Test issue with done status."""
        issue = Mock()
        issue.fields.status.statusCategory.key = "done"
        assert is_done(issue) is True

    def test_is_done_false(self):
        """Test issue with non-done status."""
        issue = Mock()
        issue.fields.status.statusCategory.key = "new"
        assert is_done(issue) is False


class TestGetStoryPoints:
    """Tests for story points extraction."""

    def test_get_story_points_found(self):
        """Test extracting story points from first matching field."""
        issue = Mock()
        issue.fields.customfield_10001 = 5.0
        sp_ids = ["customfield_10001", "customfield_10002"]

        result = get_story_points(issue, sp_ids)
        assert result == 5.0

    def test_get_story_points_second_field(self):
        """Test extracting from second field when first is None."""
        issue = Mock()
        issue.fields.customfield_10001 = None
        issue.fields.customfield_10002 = 3.0
        sp_ids = ["customfield_10001", "customfield_10002"]

        result = get_story_points(issue, sp_ids)
        assert result == 3.0

    def test_get_story_points_not_found(self):
        """Test when no story points field has value."""
        issue = Mock()
        issue.fields = Mock(spec=[])
        sp_ids = ["customfield_10001"]

        result = get_story_points(issue, sp_ids)
        assert result is None

    def test_get_story_points_integer_conversion(self):
        """Test converting integer to float."""
        issue = Mock()
        issue.fields.customfield_10001 = 8
        sp_ids = ["customfield_10001"]

        result = get_story_points(issue, sp_ids)
        assert result == 8.0


class TestSearchAll:
    """Tests for search_all helper."""

    def test_search_all(self):
        """Test searching with JQL."""
        mock_jira = Mock()
        mock_issues = [Mock(), Mock(), Mock()]
        mock_jira.search_issues.return_value = mock_issues

        result = search_all(mock_jira, "project = TEST", ["summary", "status"])

        mock_jira.search_issues.assert_called_once_with(
            "project = TEST",
            maxResults=False,
            fields="summary,status"
        )
        assert len(result) == 3


class TestEpicChildren:
    """Tests for epic_children function."""

    @patch("jira_ss_progress.jira_utils.search_all")
    def test_epic_children_parentepic(self, mock_search):
        """Test finding children via parentEpic."""
        mock_issues = [Mock(), Mock()]
        for i, issue in enumerate(mock_issues):
            issue.fields.issuetype.name = "Story" if i == 0 else "Task"
        mock_search.return_value = mock_issues
        mock_jira = Mock()

        result = epic_children(mock_jira, "EPIC-123", ["status"])

        assert len(result) == 2
        # First JQL should succeed
        assert 'parentEpic = "EPIC-123"' in mock_search.call_args_list[0][0][1]

    @patch("jira_ss_progress.jira_utils.search_all")
    def test_epic_children_epic_link_fallback(self, mock_search):
        """Test fallback to Epic Link when parentEpic returns nothing."""
        mock_issues = [Mock()]
        mock_issues[0].fields.issuetype.name = "Story"

        # First call returns empty, second returns issues
        mock_search.side_effect = [[], mock_issues]
        mock_jira = Mock()

        result = epic_children(mock_jira, "EPIC-123", ["status"])

        assert len(result) == 1
        assert mock_search.call_count == 2

    @patch("jira_ss_progress.jira_utils.search_all")
    def test_epic_children_no_children(self, mock_search):
        """Test when epic has no children."""
        mock_search.return_value = []
        mock_jira = Mock()

        result = epic_children(mock_jira, "EPIC-123", ["status"])

        assert len(result) == 0


class TestEpicProgressDetails:
    """Tests for epic_progress_details function."""

    @patch("jira_ss_progress.jira_utils.epic_children")
    def test_epic_progress_epic_done(self, mock_children):
        """Test when epic itself is Done (returns 100% without checking children)."""
        mock_jira = Mock()
        mock_epic = Mock()
        mock_epic.fields.status.name = "Done"
        mock_epic.fields.status.statusCategory.key = "done"
        mock_jira.issue.return_value = mock_epic

        progress, details = epic_progress_details(mock_jira, "EPIC-123", [])

        assert progress == 1.0
        assert details["status_category"] == "done"
        mock_children.assert_not_called()  # Should not check children

    @patch("jira_ss_progress.jira_utils.epic_children")
    def test_epic_progress_by_story_points(self, mock_children):
        """Test epic progress calculated by story points."""
        mock_jira = Mock()
        mock_epic = Mock()
        mock_epic.fields.status.statusCategory.key = "indeterminate"
        mock_epic.fields.status.name = "In Progress"
        mock_jira.issue.return_value = mock_epic

        # Create child issues with story points
        child1 = Mock()
        child1.fields.status.statusCategory.key = "done"
        child1.fields.customfield_10001 = 5.0

        child2 = Mock()
        child2.fields.status.statusCategory.key = "new"
        child2.fields.customfield_10001 = 3.0

        mock_children.return_value = [child1, child2]

        progress, details = epic_progress_details(mock_jira, "EPIC-123", ["customfield_10001"])

        assert progress == 5.0 / 8.0  # 5 done out of 8 total
        assert details["metric"] == "points"
        assert details["total_sp"] == 8.0
        assert details["done_sp"] == 5.0

    @patch("jira_ss_progress.jira_utils.epic_children")
    def test_epic_progress_by_count(self, mock_children):
        """Test epic progress calculated by issue count when no story points."""
        mock_jira = Mock()
        mock_epic = Mock()
        mock_epic.fields.status.statusCategory.key = "indeterminate"
        mock_epic.fields.status.name = "In Progress"
        mock_jira.issue.return_value = mock_epic

        # Create child issues without story points
        child1 = Mock()
        child1.fields.status.statusCategory.key = "done"
        # Don't set customfield_10001 (no story points)

        child2 = Mock()
        child2.fields.status.statusCategory.key = "new"

        child3 = Mock()
        child3.fields.status.statusCategory.key = "indeterminate"

        # Make sure getattr returns None for the story points field
        for child in [child1, child2, child3]:
            child.fields.customfield_10001 = None

        mock_children.return_value = [child1, child2, child3]

        progress, details = epic_progress_details(mock_jira, "EPIC-123", ["customfield_10001"])

        assert progress == 1.0 / 3.0  # 1 done out of 3 total
        assert details["metric"] == "count"
        assert details["total_cnt"] == 3
        assert details["done_cnt"] == 1

    @patch("jira_ss_progress.jira_utils.epic_children")
    def test_epic_progress_no_children(self, mock_children):
        """Test epic with no children."""
        mock_jira = Mock()
        mock_epic = Mock()
        mock_epic.fields.status.statusCategory.key = "new"
        mock_epic.fields.status.name = "To Do"
        mock_jira.issue.return_value = mock_epic
        mock_children.return_value = []

        progress, details = epic_progress_details(mock_jira, "EPIC-123", [])

        assert progress is None
        assert details["total_cnt"] == 0


class TestStoryProgressDetails:
    """Tests for story_progress_details function."""

    def test_story_progress_done(self):
        """Test story with Done status."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_issue.fields.status.name = "Done"
        mock_issue.fields.status.statusCategory.key = "done"
        mock_issue.fields.subtasks = []
        mock_jira.issue.return_value = mock_issue

        progress, details = story_progress_details(mock_jira, "STORY-123")

        assert progress == 1.0
        assert details["metric"] == "story"
        assert details["raw_status"] == "Done"
        assert details["status_category"] == "done"

    def test_story_progress_in_progress(self):
        """Test story with In Progress status."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_issue.fields.status.name = "In Progress"
        mock_issue.fields.status.statusCategory.key = "indeterminate"
        mock_issue.fields.subtasks = []
        mock_jira.issue.return_value = mock_issue

        progress, details = story_progress_details(mock_jira, "STORY-123")

        assert progress == 0.0
        assert details["status"] == "In Progress"

    def test_story_progress_with_subtasks(self):
        """Test story progress based on subtasks."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_issue.fields.status.name = "In Progress"
        mock_issue.fields.status.statusCategory.key = "indeterminate"

        # Create subtasks
        subtask1 = Mock()
        subtask1.key = "SUB-1"
        subtask2 = Mock()
        subtask2.key = "SUB-2"
        subtask3 = Mock()
        subtask3.key = "SUB-3"
        mock_issue.fields.subtasks = [subtask1, subtask2, subtask3]

        # Mock the subtask status queries
        def issue_side_effect(key, fields):
            mock_sub = Mock()
            if key == "SUB-1":
                mock_sub.fields.status.statusCategory.key = "done"
            elif key == "SUB-2":
                mock_sub.fields.status.statusCategory.key = "done"
            else:
                mock_sub.fields.status.statusCategory.key = "new"
            return mock_sub

        mock_jira.issue.side_effect = [mock_issue, *[issue_side_effect(s.key, "status") for s in [subtask1, subtask2, subtask3]]]

        progress, details = story_progress_details(mock_jira, "STORY-123", include_subtasks=True)

        assert progress == 2.0 / 3.0  # 2 done out of 3
        assert details["metric"] == "subtasks"
        assert details["completed"] == 2
        assert details["total"] == 3

    def test_story_progress_no_subtasks_when_enabled(self):
        """Test story with subtasks enabled but no subtasks."""
        mock_jira = Mock()
        mock_issue = Mock()
        mock_issue.fields.status.name = "In Progress"
        mock_issue.fields.status.statusCategory.key = "indeterminate"
        mock_issue.fields.subtasks = []
        mock_jira.issue.return_value = mock_issue

        progress, details = story_progress_details(mock_jira, "STORY-123", include_subtasks=True)

        assert progress == 0.0
        assert details["metric"] == "story"
