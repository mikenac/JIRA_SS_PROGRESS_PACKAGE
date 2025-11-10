# Test Suite

This directory contains the comprehensive test suite for the jira-ss-progress package.

## Overview

The test suite provides extensive coverage of all modules:

- **test_config.py** - Configuration loading and validation tests
- **test_jira_utils.py** - Jira API utilities and business logic tests
- **test_smartsheet_utils.py** - Smartsheet API utilities and parsing tests
- **test_sync.py** - Core synchronization logic tests
- **test_cli.py** - Command-line interface tests

## Running Tests

### Install Test Dependencies

```bash
# Using uv (recommended)
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"
```

### Run All Tests

```bash
pytest
```

### Run Tests with Coverage

```bash
pytest --cov=jira_ss_progress --cov-report=term-missing
```

### Run Specific Test File

```bash
pytest tests/test_config.py
```

### Run Specific Test Class

```bash
pytest tests/test_config.py::TestLoadConfig
```

### Run Specific Test Function

```bash
pytest tests/test_config.py::TestLoadConfig::test_load_config_success
```

### Run Tests in Verbose Mode

```bash
pytest -v
```

### Run Tests and Stop at First Failure

```bash
pytest -x
```

## Test Coverage

The test suite aims for high coverage of critical functionality:

- **Configuration**: Environment variable parsing, validation, defaults
- **Jira Utils**: Progress calculations, field resolution, status handling
- **Smartsheet Utils**: Cell parsing, date conversion, Jira key extraction
- **Sync Logic**: Protection mechanisms, caching, status preservation, batch updates
- **CLI**: Argument parsing, output formatting, dry-run mode

## Test Structure

Each test file follows these conventions:

1. **Imports** - Standard library, third-party, and project imports
2. **Test Classes** - Grouped by functionality being tested
3. **Fixtures** - Reusable test data and mock objects
4. **Test Methods** - Individual test cases with descriptive names

## Mocking Strategy

Tests use `unittest.mock` to isolate units under test:

- **External APIs** - Jira and Smartsheet clients are fully mocked
- **File System** - Environment variables use pytest's `monkeypatch`
- **Network Calls** - No real API calls are made during testing

## Writing New Tests

When adding new functionality:

1. Write tests first (TDD approach)
2. Create fixtures for common test data
3. Use descriptive test names: `test_<function>_<scenario>_<expected_result>`
4. Mock external dependencies
5. Test both success and failure cases
6. Include edge cases and boundary conditions

### Example Test Structure

```python
class TestNewFeature:
    """Tests for new feature."""

    @pytest.fixture
    def mock_data(self):
        """Create test data."""
        return {"key": "value"}

    def test_feature_success(self, mock_data):
        """Test successful operation."""
        result = new_feature(mock_data)
        assert result == expected_value

    def test_feature_handles_error(self):
        """Test error handling."""
        with pytest.raises(ValueError):
            new_feature(invalid_input)
```

## Coverage Reports

### Terminal Output

Run tests with coverage to see a terminal report:

```bash
pytest --cov=jira_ss_progress --cov-report=term-missing
```

### HTML Report

Generate an interactive HTML coverage report:

```bash
pytest --cov=jira_ss_progress --cov-report=html
```

Then open `htmlcov/index.html` in your browser.

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -e ".[dev]"
    pytest --cov=jira_ss_progress --cov-report=xml
```

## Troubleshooting

### Import Errors

If you see import errors, ensure the package is installed in development mode:

```bash
pip install -e .
```

### Missing Dependencies

Install development dependencies:

```bash
pip install -e ".[dev]"
```

### Mock Issues

If mocks aren't working as expected:
- Check the import path in `@patch()` decorators
- Ensure you're mocking where the object is used, not where it's defined
- Use `patch.object()` for more precise mocking

## Test Maintenance

- **Keep tests fast** - Use mocks to avoid slow API calls
- **Keep tests isolated** - Each test should be independent
- **Keep tests readable** - Use clear names and comments
- **Update tests with code** - When changing functionality, update tests
- **Remove obsolete tests** - Delete tests for removed features

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
