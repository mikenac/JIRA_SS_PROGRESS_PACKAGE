"""Tests for Smartsheet utility functions."""
from __future__ import annotations
from unittest.mock import Mock, patch
import pytest
from jira_ss_progress.smartsheet_utils import (
    client,
    get_sheet,
    column_id_by_title,
    extract_jira_key,
    parse_percent_cell,
    text_cell_value,
    date_cell_iso,
    chunk,
)


class TestClient:
    """Tests for Smartsheet client creation."""

    @patch("jira_ss_progress.smartsheet_utils.smartsheet.Smartsheet")
    def test_client_creates_smartsheet_client(self, mock_smartsheet_class):
        """Test that client creates Smartsheet client with token."""
        mock_ss = Mock()
        mock_smartsheet_class.return_value = mock_ss

        result = client("test_token_123")

        mock_smartsheet_class.assert_called_once_with("test_token_123")
        assert result == mock_ss


class TestGetSheet:
    """Tests for getting a sheet."""

    def test_get_sheet(self):
        """Test retrieving a sheet by ID."""
        mock_ss = Mock()
        mock_sheet = Mock()
        mock_ss.Sheets.get_sheet.return_value = mock_sheet

        result = get_sheet(mock_ss, 12345)

        mock_ss.Sheets.get_sheet.assert_called_once_with(12345)
        assert result == mock_sheet


class TestColumnIdByTitle:
    """Tests for finding column by title."""

    def test_column_id_by_title_exact_match(self):
        """Test finding column with exact title match."""
        mock_sheet = Mock()
        col1 = Mock()
        col1.id = 101
        col1.title = "Jira"
        col2 = Mock()
        col2.id = 102
        col2.title = "% Complete"
        mock_sheet.columns = [col1, col2]

        result = column_id_by_title(mock_sheet, "Jira")
        assert result == 101

    def test_column_id_by_title_case_insensitive(self):
        """Test finding column is case-insensitive."""
        mock_sheet = Mock()
        col = Mock()
        col.id = 101
        col.title = "Jira Key"
        mock_sheet.columns = [col]

        result = column_id_by_title(mock_sheet, "jira key")
        assert result == 101

    def test_column_id_by_title_whitespace_handling(self):
        """Test finding column handles whitespace."""
        mock_sheet = Mock()
        col = Mock()
        col.id = 101
        col.title = "  Status  "
        mock_sheet.columns = [col]

        result = column_id_by_title(mock_sheet, "status")
        assert result == 101

    def test_column_id_by_title_not_found(self):
        """Test KeyError when column not found."""
        mock_sheet = Mock()
        mock_sheet.columns = []

        with pytest.raises(KeyError, match="Column not found: Nonexistent"):
            column_id_by_title(mock_sheet, "Nonexistent")


class TestExtractJiraKey:
    """Tests for extracting Jira keys from cells."""

    def test_extract_jira_key_from_hyperlink(self):
        """Test extracting Jira key from hyperlink URL."""
        cell = Mock()
        cell.hyperlink = Mock()
        cell.hyperlink.type = "URL"
        cell.hyperlink.url = "https://example.atlassian.net/browse/PROJ-123"
        cell.value = None
        cell.display_value = None

        result = extract_jira_key(cell)
        assert result == "PROJ-123"

    def test_extract_jira_key_from_value(self):
        """Test extracting Jira key from cell value."""
        cell = Mock()
        cell.hyperlink = None
        cell.value = "PROJ-456"
        cell.display_value = None

        result = extract_jira_key(cell)
        assert result == "PROJ-456"

    def test_extract_jira_key_from_display_value(self):
        """Test extracting Jira key from display value."""
        cell = Mock()
        cell.hyperlink = None
        cell.value = None
        cell.display_value = "PROJ-789"

        result = extract_jira_key(cell)
        assert result == "PROJ-789"

    def test_extract_jira_key_embedded_in_text(self):
        """Test extracting Jira key embedded in text."""
        cell = Mock()
        cell.hyperlink = None
        cell.value = "See PROJ-999 for details"
        cell.display_value = None

        result = extract_jira_key(cell)
        assert result == "PROJ-999"

    def test_extract_jira_key_not_found(self):
        """Test when no Jira key is found."""
        cell = Mock()
        cell.hyperlink = None
        cell.value = "No key here"
        cell.display_value = None

        result = extract_jira_key(cell)
        assert result is None

    def test_extract_jira_key_multiple_keys_returns_first(self):
        """Test that first Jira key is returned when multiple exist."""
        cell = Mock()
        cell.hyperlink = None
        cell.value = "PROJ-111 and PROJ-222"
        cell.display_value = None

        result = extract_jira_key(cell)
        assert result == "PROJ-111"

    def test_extract_jira_key_with_numbers_in_project(self):
        """Test extracting key with numbers in project code."""
        cell = Mock()
        cell.hyperlink = None
        cell.value = "AB12-456"
        cell.display_value = None

        result = extract_jira_key(cell)
        assert result == "AB12-456"


class TestParsePercentCell:
    """Tests for parsing percent cells."""

    def test_parse_percent_cell_float(self):
        """Test parsing percent cell with float value."""
        cell = Mock()
        cell.value = 0.75
        cell.display_value = None

        result = parse_percent_cell(cell)
        assert result == 0.75

    def test_parse_percent_cell_integer(self):
        """Test parsing percent cell with integer value."""
        cell = Mock()
        cell.value = 1
        cell.display_value = None

        result = parse_percent_cell(cell)
        assert result == 1.0

    def test_parse_percent_cell_display_value_percent(self):
        """Test parsing percent from display value like '75%'."""
        cell = Mock()
        cell.value = None
        cell.display_value = "75%"

        result = parse_percent_cell(cell)
        assert result == 0.75

    def test_parse_percent_cell_display_value_with_spaces(self):
        """Test parsing percent with spaces."""
        cell = Mock()
        cell.value = None
        cell.display_value = "  50 %  "

        result = parse_percent_cell(cell)
        assert result == 0.50

    def test_parse_percent_cell_none(self):
        """Test parsing None cell."""
        result = parse_percent_cell(None)
        assert result is None

    def test_parse_percent_cell_invalid_display(self):
        """Test parsing invalid display value."""
        cell = Mock()
        cell.value = None
        cell.display_value = "not a percent"

        result = parse_percent_cell(cell)
        assert result is None

    def test_parse_percent_cell_zero(self):
        """Test parsing zero percent."""
        cell = Mock()
        cell.value = 0.0
        cell.display_value = None

        result = parse_percent_cell(cell)
        assert result == 0.0


class TestTextCellValue:
    """Tests for getting text cell values."""

    def test_text_cell_value_from_value(self):
        """Test getting text from value attribute."""
        cell = Mock()
        cell.value = "Some text"
        cell.display_value = None

        result = text_cell_value(cell)
        assert result == "Some text"

    def test_text_cell_value_from_display_value(self):
        """Test getting text from display_value when value is None."""
        cell = Mock()
        cell.value = None
        cell.display_value = "Display text"

        result = text_cell_value(cell)
        assert result == "Display text"

    def test_text_cell_value_none_cell(self):
        """Test handling None cell."""
        result = text_cell_value(None)
        assert result is None

    def test_text_cell_value_empty_string(self):
        """Test handling empty string."""
        cell = Mock()
        cell.value = "   "
        cell.display_value = None

        result = text_cell_value(cell)
        assert result is None

    def test_text_cell_value_non_string(self):
        """Test handling non-string value."""
        cell = Mock()
        cell.value = 123
        cell.display_value = None

        result = text_cell_value(cell)
        assert result is None


class TestDateCellIso:
    """Tests for parsing date cells to ISO format."""

    def test_date_cell_iso_from_value(self):
        """Test parsing ISO date from value."""
        cell = Mock()
        cell.value = "2024-01-15"
        cell.display_value = None

        result = date_cell_iso(cell)
        assert result == "2024-01-15"

    def test_date_cell_iso_with_time(self):
        """Test parsing ISO datetime (strips time)."""
        cell = Mock()
        cell.value = "2024-01-15T10:30:00"
        cell.display_value = None

        result = date_cell_iso(cell)
        assert result == "2024-01-15"

    def test_date_cell_iso_from_display_value_mm_dd_yy(self):
        """Test parsing date from display value in MM/DD/YY format."""
        cell = Mock()
        cell.value = None
        cell.display_value = "01/15/24"

        result = date_cell_iso(cell)
        assert result == "2024-01-15"

    def test_date_cell_iso_from_display_value_mm_dd_yyyy(self):
        """Test parsing date from display value in MM/DD/YYYY format."""
        cell = Mock()
        cell.value = None
        cell.display_value = "01/15/2024"

        result = date_cell_iso(cell)
        assert result == "2024-01-15"

    def test_date_cell_iso_century_cutoff(self):
        """Test century cutoff for 2-digit years (70+ = 19xx)."""
        cell = Mock()
        cell.value = None
        cell.display_value = "01/15/75"

        result = date_cell_iso(cell)
        assert result == "1975-01-15"

    def test_date_cell_iso_none_cell(self):
        """Test handling None cell."""
        result = date_cell_iso(None)
        assert result is None

    def test_date_cell_iso_empty_value(self):
        """Test handling empty value."""
        cell = Mock()
        cell.value = ""
        cell.display_value = None

        result = date_cell_iso(cell)
        assert result is None

    def test_date_cell_iso_invalid_format(self):
        """Test handling invalid date format."""
        cell = Mock()
        cell.value = None
        cell.display_value = "not a date"

        result = date_cell_iso(cell)
        assert result is None

    def test_date_cell_iso_single_digit_month_day(self):
        """Test parsing date with single digit month/day (8+ chars)."""
        cell = Mock()
        cell.value = None
        cell.display_value = "1/5/2024"  # 8 characters, within valid length range

        result = date_cell_iso(cell)
        assert result == "2024-01-05"


class TestChunk:
    """Tests for chunk utility."""

    def test_chunk_exact_size(self):
        """Test chunking when items divide evenly."""
        items = [1, 2, 3, 4, 5, 6]
        result = list(chunk(items, 2))

        assert len(result) == 3
        assert result[0] == [1, 2]
        assert result[1] == [3, 4]
        assert result[2] == [5, 6]

    def test_chunk_with_remainder(self):
        """Test chunking when items don't divide evenly."""
        items = [1, 2, 3, 4, 5]
        result = list(chunk(items, 2))

        assert len(result) == 3
        assert result[0] == [1, 2]
        assert result[1] == [3, 4]
        assert result[2] == [5]

    def test_chunk_single_item(self):
        """Test chunking single item."""
        items = [1]
        result = list(chunk(items, 3))

        assert len(result) == 1
        assert result[0] == [1]

    def test_chunk_empty(self):
        """Test chunking empty iterable."""
        items = []
        result = list(chunk(items, 2))

        assert len(result) == 0

    def test_chunk_size_larger_than_items(self):
        """Test chunk size larger than number of items."""
        items = [1, 2, 3]
        result = list(chunk(items, 10))

        assert len(result) == 1
        assert result[0] == [1, 2, 3]

    def test_chunk_generator(self):
        """Test that chunk works with generators."""
        items = (x for x in range(5))
        result = list(chunk(items, 2))

        assert len(result) == 3
        assert result[0] == [0, 1]
        assert result[1] == [2, 3]
        assert result[2] == [4]
