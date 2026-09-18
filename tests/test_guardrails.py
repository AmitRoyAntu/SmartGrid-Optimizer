"""
Unit tests for guardrails validator (Member 3 - Hour 1).

Tests the deterministic validation and normalization of LLM directives.
"""

import pytest
from app.guardrails.validator import validate_and_guardrail_directives
from app.core.schemas import RawDirectiveDTO, CONFIDENCE_THRESHOLD


class TestHourValidation:
    """Test hour sorting, clamping, and deduplication."""

    def test_hour_sorting(self):
        """Hours should be sorted ascending."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=[23, 5, 10],
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert len(result) == 1
        assert result[0].hours == [5, 10, 23]
        assert result[0].applies is True

    def test_hour_deduplication(self):
        """Duplicate hours should be removed."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=[10, 10, 5, 5, 10],
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].hours == [5, 10]

    def test_hour_clamping_to_0_23(self):
        """Hours outside [0, 23] should be dropped."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=[-1, 5, 25, 12, 24],
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].hours == [5, 12]

    def test_empty_hours_after_filtering(self):
        """If no valid hours remain, mark as not applying."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=[-5, -1, 25, 30],
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is False
        assert "No valid hours" in result[0].fallback_reason


class TestFactorValidation:
    """Test factor clamping to [0.0, 1.0]."""

    def test_factor_clamping_upper(self):
        """Factor > 1.0 should be clamped to 1.0."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=[10, 11, 12],
            raw_numeric_param=1.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].factor == 1.0
        assert result[0].applies is True

    def test_factor_clamping_lower(self):
        """Factor < 0.0 should be clamped to 0.0."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=[10, 11, 12],
            raw_numeric_param=-0.3,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].factor == 0.0
        assert result[0].applies is True

    def test_factor_in_valid_range(self):
        """Factor in [0.0, 1.0] should be unchanged."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=[10, 11, 12],
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].factor == 0.5
        assert result[0].applies is True


class TestBatteryReserveValidation:
    """Test battery reserve constraints."""

    def test_reserve_within_capacity(self):
        """Reserve within capacity should be valid."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='minimum_battery_reserve',
            raw_hours=None,
            raw_numeric_param=0.5,  # 50% of 50 kWh = 25 kWh
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is True
        assert result[0].factor == 0.5

    def test_reserve_exceeds_capacity(self):
        """Reserve > capacity should fall back."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='minimum_battery_reserve',
            raw_hours=None,
            raw_numeric_param=1.2,  # 120% of 50 kWh = 60 kWh > 50 kWh
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is False
        assert "exceeds capacity" in result[0].fallback_reason


class TestDirectiveTypeValidation:
    """Test directive type validation."""

    def test_valid_directive_types(self):
        """All 6 valid types should pass."""
        valid_types = [
            'solar_reduction',
            'minimum_battery_reserve',
            'no_charge_window',
            'no_discharge_window',
            'max_grid_window',
            'no_op',
        ]

        for dtype in valid_types:
            raw = RawDirectiveDTO(
                note_index=0,
                directive_type=dtype,
                raw_hours=[10, 11],
                raw_numeric_param=0.5,
                explanation="Test",
                confidence=0.9,
            )
            result = validate_and_guardrail_directives([raw], 1, 50.0)
            # no_op always has applies=False by design
            if dtype != 'no_op':
                assert result[0].applies is True, f"Failed for type: {dtype}"

    def test_invalid_directive_type(self):
        """Unknown directive type should fall back."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='invalid_type',
            raw_hours=[10, 11, 12],
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is False
        assert "Unknown directive type" in result[0].fallback_reason


class TestConfidenceValidation:
    """Test LLM confidence score validation."""

    def test_high_confidence(self):
        """Confidence >= CONFIDENCE_THRESHOLD should pass."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=[10, 11, 12],
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is True

    def test_low_confidence(self):
        """Confidence < CONFIDENCE_THRESHOLD should fall back."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=[10, 11, 12],
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.3,  # Below threshold (0.5)
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is False
        assert "Low confidence" in result[0].fallback_reason


class TestNoOpDirective:
    """Test no_op directive handling."""

    def test_no_op_no_constraint(self):
        """no_op should never apply."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='no_op',
            raw_hours=None,
            raw_numeric_param=None,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is False


class TestNeverCrash:
    """Test that validator never crashes."""

    def test_empty_directives(self):
        """Empty list should return empty list."""
        result = validate_and_guardrail_directives([], 1, 50.0)
        assert result == []

    def test_none_hours(self):
        """None hours should be handled gracefully."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=None,
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        # Should not crash, might mark as not applying
        assert isinstance(result, list)
        assert len(result) == 1

    def test_invalid_hour_types(self):
        """Invalid hour types should be filtered."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type='solar_reduction',
            raw_hours=[10, "invalid", 12.5, None, 20],  # type: ignore
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        # Should keep only valid integers: 10, 20
        assert result[0].hours == [10, 20]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
