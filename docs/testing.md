# Testing Guide

## Running Tests

Run all tests:
pytest tests/ -v

Run with coverage:
pytest tests/ -v --cov=src --cov-report=html

Run specific test:
pytest tests/test_bot.py::test_bot_initialization -v

## Test Structure

tests/
  conftest.py         - Pytest configuration
  test_bot.py         - Bot tests
  test_database.py    - Database tests
  test_utils.py       - Utility tests
  test_models.py      - Model tests
  test_services.py    - Service tests
  test_helpers.py     - Helper tests
  test_middleware.py  - Middleware tests
  test_integration.py - Integration tests

## Best Practices

- Write tests for all new features
- Aim for 80%+ code coverage
- Use pytest fixtures for setup
- Mock external dependencies
- Test both success and failure cases
