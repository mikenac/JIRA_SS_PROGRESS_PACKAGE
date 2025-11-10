"""Shared pytest fixtures and configuration."""
from __future__ import annotations
import os
import pytest


# Note: We don't use an autouse fixture for environment cleanup because
# it interferes with monkeypatch. Instead, tests that need clean environment
# should use monkeypatch.delenv() explicitly.


@pytest.fixture
def sample_jira_fields():
    """Sample Jira field definitions."""
    return [
        {"id": "summary", "name": "Summary"},
        {"id": "description", "name": "Description"},
        {"id": "status", "name": "Status"},
        {"id": "customfield_10001", "name": "Story Points"},
        {"id": "customfield_10002", "name": "Epic Link"},
        {"id": "customfield_10003", "name": "Start Date"},
        {"id": "duedate", "name": "Due Date"},
    ]


@pytest.fixture
def mock_jira_issue():
    """Create a mock Jira issue with common attributes."""
    from unittest.mock import Mock

    issue = Mock()
    issue.key = "TEST-123"
    issue.fields = Mock()
    issue.fields.summary = "Test Issue"
    issue.fields.issuetype = Mock()
    issue.fields.issuetype.name = "Story"
    issue.fields.status = Mock()
    issue.fields.status.name = "In Progress"
    issue.fields.status.statusCategory = Mock()
    issue.fields.status.statusCategory.key = "indeterminate"
    issue.fields.status.statusCategory.name = "In Progress"
    issue.fields.subtasks = []

    return issue


@pytest.fixture
def mock_smartsheet_cell():
    """Create a mock Smartsheet cell."""
    from unittest.mock import Mock

    cell = Mock()
    cell.column_id = 1001
    cell.value = None
    cell.display_value = None
    cell.hyperlink = None

    return cell


@pytest.fixture
def mock_smartsheet_row():
    """Create a mock Smartsheet row."""
    from unittest.mock import Mock

    row = Mock()
    row.id = 5001
    row.cells = []

    return row


@pytest.fixture
def valid_env_config(monkeypatch):
    """Set up valid environment configuration for tests."""
    monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "test@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test_token_123")
    monkeypatch.setenv("SMARTSHEET_ACCESS_TOKEN", "smartsheet_token_456")
    monkeypatch.setenv("SS_SHEET_ID", "12345")
