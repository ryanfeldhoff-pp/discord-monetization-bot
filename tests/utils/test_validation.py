"""
Tests for input validation functions in src/utils/validation.py

Validates all input parsing and validation functions with valid inputs,
edge cases, and error conditions.
"""

import pytest
from datetime import datetime, timedelta

from src.utils.validation import (
    validate_positive_int,
    validate_range,
    validate_non_empty,
    validate_date,
    validate_datetime,
    validate_length,
)


class TestValidatePositiveInt:
    """Test validate_positive_int function."""

    def test_validate_positive_int_valid(self):
        """Test validation of a valid positive integer."""
        result, error = validate_positive_int("42", "Number")
        assert result == 42
        assert error is None

    def test_validate_positive_int_zero_rejected(self):
        """Test that zero is rejected as not positive."""
        result, error = validate_positive_int("0", "Number")
        assert result is None
        assert "must be positive" in error

    def test_validate_positive_int_negative_rejected(self):
        """Test that negative integers are rejected."""
        result, error = validate_positive_int("-5", "Number")
        assert result is None
        assert "must be positive" in error

    def test_validate_positive_int_string_rejected(self):
        """Test that non-numeric strings are rejected."""
        result, error = validate_positive_int("abc", "Number")
        assert result is None
        assert "must be a whole number" in error

    def test_validate_positive_int_float_string_rejected(self):
        """Test that float strings are rejected."""
        result, error = validate_positive_int("3.14", "Number")
        assert result is None
        assert "must be a whole number" in error

    def test_validate_positive_int_one_accepted(self):
        """Test that 1 is accepted as valid."""
        result, error = validate_positive_int("1", "Number")
        assert result == 1
        assert error is None

    def test_validate_positive_int_large_number(self):
        """Test validation of large numbers."""
        result, error = validate_positive_int("999999999", "Number")
        assert result == 999999999
        assert error is None

    def test_validate_positive_int_custom_field_name(self):
        """Test error message includes custom field name."""
        result, error = validate_positive_int("abc", "Price")
        assert "Price" in error


class TestValidateRange:
    """Test validate_range function."""

    def test_validate_range_in_range(self):
        """Test value within range is valid."""
        is_valid, error = validate_range(50, 0, 100, "Score")
        assert is_valid is True
        assert error is None

    def test_validate_range_at_min_boundary(self):
        """Test value at minimum boundary is valid."""
        is_valid, error = validate_range(0, 0, 100, "Score")
        assert is_valid is True
        assert error is None

    def test_validate_range_at_max_boundary(self):
        """Test value at maximum boundary is valid."""
        is_valid, error = validate_range(100, 0, 100, "Score")
        assert is_valid is True
        assert error is None

    def test_validate_range_out_of_range_low(self):
        """Test value below range is invalid."""
        is_valid, error = validate_range(-1, 0, 100, "Score")
        assert is_valid is False
        assert "must be between" in error

    def test_validate_range_out_of_range_high(self):
        """Test value above range is invalid."""
        is_valid, error = validate_range(101, 0, 100, "Score")
        assert is_valid is False
        assert "must be between" in error

    def test_validate_range_with_floats(self):
        """Test range validation with float values."""
        is_valid, error = validate_range(0.5, 0.0, 1.0, "Ratio")
        assert is_valid is True
        assert error is None

    def test_validate_range_error_includes_boundaries(self):
        """Test error message includes min and max values."""
        is_valid, error = validate_range(150, 0, 100, "Value")
        assert "0" in error
        assert "100" in error


class TestValidateNonEmpty:
    """Test validate_non_empty function."""

    def test_validate_non_empty_valid(self):
        """Test non-empty string is valid."""
        is_valid, error = validate_non_empty("Hello", "Name")
        assert is_valid is True
        assert error is None

    def test_validate_non_empty_empty_rejected(self):
        """Test empty string is rejected."""
        is_valid, error = validate_non_empty("", "Name")
        assert is_valid is False
        assert "cannot be empty" in error

    def test_validate_non_empty_whitespace_rejected(self):
        """Test whitespace-only string is rejected."""
        is_valid, error = validate_non_empty("   ", "Name")
        assert is_valid is False
        assert "cannot be empty" in error

    def test_validate_non_empty_whitespace_with_text(self):
        """Test string with whitespace and text is valid."""
        is_valid, error = validate_non_empty("  Hello  ", "Name")
        assert is_valid is True
        assert error is None

    def test_validate_non_empty_single_character(self):
        """Test single character string is valid."""
        is_valid, error = validate_non_empty("A", "Initial")
        assert is_valid is True
        assert error is None


class TestValidateDate:
    """Test validate_date function."""

    def test_validate_date_yyyy_mm_dd(self):
        """Test validation of YYYY-MM-DD format."""
        result, error = validate_date("2026-04-02", "Date")
        assert result is not None
        assert error is None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 2

    def test_validate_date_tomorrow(self):
        """Test validation of 'tomorrow' keyword."""
        result, error = validate_date("tomorrow", "Date")
        assert result is not None
        assert error is None
        # Should be roughly tomorrow
        tomorrow = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        assert result.date() == tomorrow.date()

    def test_validate_date_relative_plus_7d(self):
        """Test validation of relative date +7d."""
        result, error = validate_date("+7d", "Date")
        assert result is not None
        assert error is None
        # Should be roughly 7 days from now
        future = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=7)
        assert result.date() == future.date()

    def test_validate_date_relative_minus_3d(self):
        """Test validation of relative date -3d."""
        result, error = validate_date("-3d", "Date")
        assert result is not None
        assert error is None
        # Should be roughly 3 days ago
        past = datetime.now().replace(hour=0, minute=0, second=0) - timedelta(days=3)
        assert result.date() == past.date()

    def test_validate_date_case_insensitive_tomorrow(self):
        """Test that 'tomorrow' is case-insensitive."""
        result, error = validate_date("TOMORROW", "Date")
        assert result is not None
        assert error is None

    def test_validate_date_invalid_format(self):
        """Test rejection of invalid date format."""
        result, error = validate_date("04/02/2026", "Date")
        assert result is None
        assert "must be YYYY-MM-DD" in error

    def test_validate_date_invalid_date_values(self):
        """Test rejection of invalid date values."""
        result, error = validate_date("2026-13-32", "Date")
        assert result is None
        assert error is not None

    def test_validate_date_relative_zero_days(self):
        """Test relative date with 0 days."""
        result, error = validate_date("+0d", "Date")
        assert result is not None
        assert error is None


class TestValidateDatetime:
    """Test validate_datetime function."""

    def test_validate_datetime_valid(self):
        """Test validation of valid datetime."""
        result, error = validate_datetime("2026-04-02 14:30", "DateTime")
        assert result is not None
        assert error is None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 2
        assert result.hour == 14
        assert result.minute == 30

    def test_validate_datetime_midnight(self):
        """Test validation of midnight time."""
        result, error = validate_datetime("2026-04-02 00:00", "DateTime")
        assert result is not None
        assert error is None
        assert result.hour == 0
        assert result.minute == 0

    def test_validate_datetime_end_of_day(self):
        """Test validation of 23:59 time."""
        result, error = validate_datetime("2026-04-02 23:59", "DateTime")
        assert result is not None
        assert error is None

    def test_validate_datetime_invalid_format(self):
        """Test rejection of invalid datetime format."""
        result, error = validate_datetime("2026-04-02", "DateTime")
        assert result is None
        assert "must be in format" in error

    def test_validate_datetime_invalid_hour(self):
        """Test rejection of invalid hour."""
        result, error = validate_datetime("2026-04-02 25:00", "DateTime")
        assert result is None
        assert error is not None

    def test_validate_datetime_invalid_minute(self):
        """Test rejection of invalid minute."""
        result, error = validate_datetime("2026-04-02 14:60", "DateTime")
        assert result is None
        assert error is not None

    def test_validate_datetime_wrong_separator(self):
        """Test rejection of wrong separator."""
        result, error = validate_datetime("2026-04-02T14:30", "DateTime")
        assert result is None
        assert error is not None


class TestValidateLength:
    """Test validate_length function."""

    def test_validate_length_valid(self):
        """Test string within length bounds."""
        is_valid, error = validate_length("Hello", 1, 10, "Name")
        assert is_valid is True
        assert error is None

    def test_validate_length_at_min(self):
        """Test string at minimum length."""
        is_valid, error = validate_length("A", 1, 10, "Name")
        assert is_valid is True
        assert error is None

    def test_validate_length_at_max(self):
        """Test string at maximum length."""
        is_valid, error = validate_length("0123456789", 1, 10, "Name")
        assert is_valid is True
        assert error is None

    def test_validate_length_too_short(self):
        """Test string below minimum length."""
        is_valid, error = validate_length("A", 2, 10, "Name")
        assert is_valid is False
        assert "must be between" in error

    def test_validate_length_too_long(self):
        """Test string above maximum length."""
        is_valid, error = validate_length("0123456789ABC", 1, 10, "Name")
        assert is_valid is False
        assert "must be between" in error

    def test_validate_length_empty_string(self):
        """Test empty string validation."""
        is_valid, error = validate_length("", 0, 10, "Name")
        assert is_valid is True
        assert error is None

    def test_validate_length_empty_string_min_required(self):
        """Test empty string when minimum is 1."""
        is_valid, error = validate_length("", 1, 10, "Name")
        assert is_valid is False
        assert error is not None

    def test_validate_length_error_includes_bounds(self):
        """Test error message includes min and max length."""
        is_valid, error = validate_length("X", 5, 10, "Field")
        assert "5" in error
        assert "10" in error

    def test_validate_length_unicode_characters(self):
        """Test length validation with unicode characters."""
        is_valid, error = validate_length("🎉🎉🎉", 1, 5, "Emoji")
        assert is_valid is True
        assert error is None

    def test_validate_length_with_spaces(self):
        """Test length validation includes spaces in count."""
        is_valid, error = validate_length("Hello World", 5, 15, "Text")
        assert is_valid is True
        assert error is None
