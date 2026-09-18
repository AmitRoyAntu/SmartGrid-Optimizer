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
            directive_type="solar_reduction",
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
            directive_type="solar_reduction",
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
            directive_type="solar_reduction",
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
            directive_type="solar_reduction",
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
            directive_type="solar_reduction",
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
            directive_type="solar_reduction",
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
            directive_type="solar_reduction",
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
        """Reserve within capacity should be valid and use minimum_energy_kwh."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type="minimum_battery_reserve",
            raw_hours=None,
            raw_numeric_param=25.0,  # 25 kWh <= 50 kWh
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is True
        assert result[0].directive_type == "minimum_battery_reserve"
        assert result[0].structured_adjustment is not None
        assert result[0].structured_adjustment["minimum_energy_kwh"] == 25.0

    def test_reserve_exceeds_capacity(self):
        """Reserve > capacity should fall back to no_op with structured_adjustment=None."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type="minimum_battery_reserve",
            raw_hours=None,
            raw_numeric_param=60.0,  # 60 kWh > 50 kWh capacity
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is False
        assert result[0].directive_type == "no_op"
        assert result[0].structured_adjustment is None
        assert "exceeds capacity" in result[0].fallback_reason


class TestDirectiveTypeValidation:
    """Test directive type validation."""

    def test_valid_directive_types(self):
        """All 6 valid types should pass and produce canonical structure."""
        valid_types = [
            "solar_reduction",
            "minimum_battery_reserve",
            "no_charge_window",
            "no_discharge_window",
            "max_grid_window",
            "no_op",
        ]

        for dtype in valid_types:
            param = 0.5
            if dtype == "minimum_battery_reserve":
                param = 25.0
            elif dtype == "max_grid_window":
                param = 35.0

            raw = RawDirectiveDTO(
                note_index=0,
                directive_type=dtype,
                raw_hours=[10, 11],
                raw_numeric_param=param,
                explanation="Test",
                confidence=0.9,
            )
            result = validate_and_guardrail_directives([raw], 1, 50.0)
            if dtype != "no_op":
                assert result[0].applies is True, f"Failed for type: {dtype}"
                assert result[0].directive_type == dtype
                assert result[0].structured_adjustment is not None
            else:
                assert result[0].applies is False
                assert result[0].directive_type == "no_op"
                assert result[0].structured_adjustment is None

    def test_invalid_directive_type(self):
        """Unknown directive type should fall back to no_op with structured_adjustment=None."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type="invalid_type",
            raw_hours=[10, 11, 12],
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is False
        assert result[0].directive_type == "no_op"
        assert result[0].structured_adjustment is None
        assert "Unknown directive type" in result[0].fallback_reason


class TestConfidenceValidation:
    """Test LLM confidence score validation."""

    def test_high_confidence(self):
        """Confidence >= CONFIDENCE_THRESHOLD should pass."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type="solar_reduction",
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
            directive_type="solar_reduction",
            raw_hours=[10, 11, 12],
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.3,  # Below threshold (0.5)
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is False
        assert result[0].directive_type == "no_op"
        assert result[0].structured_adjustment is None
        assert "Low confidence" in result[0].fallback_reason


class TestNoOpDirective:
    """Test no_op directive handling."""

    def test_no_op_no_constraint(self):
        """no_op should never apply."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type="no_op",
            raw_hours=None,
            raw_numeric_param=None,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert result[0].applies is False
        assert result[0].directive_type == "no_op"
        assert result[0].structured_adjustment is None


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
            directive_type="solar_reduction",
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
            directive_type="solar_reduction",
            raw_hours=[10, "invalid", 12.5, None, 20],  # type: ignore
            raw_numeric_param=0.5,
            explanation="Test",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        # Should keep only valid integers: 10, 20
        assert result[0].hours == [10, 20]


class TestMember1ContractAlignment:
    """Explicit tests verifying the contract requirements requested by Member 1."""

    def test_output_model_fields(self):
        """Must return note_index, applies, directive_type, structured_adjustment, explanation."""
        raw = RawDirectiveDTO(
            note_index=1,
            directive_type="solar_reduction",
            raw_hours=[13, 14],
            raw_numeric_param=0.2,
            explanation="Solar drop to 20%",
            confidence=0.95,
        )
        result = validate_and_guardrail_directives([raw], 1, 50.0)
        assert len(result) == 1
        d = result[0]
        # Verify exact field presence and values
        dumped = d.model_dump()
        expected_keys = {"note_index", "applies", "directive_type", "structured_adjustment", "explanation"}
        assert set(dumped.keys()) == expected_keys
        assert dumped["note_index"] == 1
        assert dumped["applies"] is True
        assert dumped["directive_type"] == "solar_reduction"
        assert dumped["structured_adjustment"] == {"hours": [13, 14], "factor": 0.2}
        assert "Solar" in dumped["explanation"]

    def test_minimum_battery_reserve_uses_minimum_energy_kwh_directly(self):
        """minimum_battery_reserve must use minimum_energy_kwh directly, not percentage."""
        raw = RawDirectiveDTO(
            note_index=0,
            directive_type="minimum_battery_reserve",
            raw_hours=[18, 19, 20],
            raw_numeric_param=120.0,
            explanation="Keep at least 120 kWh in reserve",
            confidence=0.99,
        )
        result = validate_and_guardrail_directives([raw], 1, 200.0)
        d = result[0]
        assert d.applies is True
        assert d.directive_type == "minimum_battery_reserve"
        assert d.structured_adjustment == {"hours": [18, 19, 20], "minimum_energy_kwh": 120.0}

    def test_max_grid_window_uses_max_grid_kwh_directly(self):
        """max_grid_window must use max_grid_kwh directly, not percentage."""
        raw = RawDirectiveDTO(
            note_index=2,
            directive_type="max_grid_window",
            raw_hours=[14, 15],
            raw_numeric_param=50.0,
            explanation="Cap grid import to 50 kWh",
            confidence=0.92,
        )
        result = validate_and_guardrail_directives([raw], 1, 100.0)
        d = result[0]
        assert d.applies is True
        assert d.directive_type == "max_grid_window"
        assert d.structured_adjustment == {"hours": [14, 15], "max_grid_kwh": 50.0}

    def test_fallback_becomes_no_op_with_none_adjustment(self):
        """When applies=False, directive_type must be 'no_op' and structured_adjustment must be None."""
        invalid_raw = RawDirectiveDTO(
            note_index=0,
            directive_type="minimum_battery_reserve",
            raw_hours=[10, 11],
            raw_numeric_param=500.0,  # 500 kWh exceeds 50 kWh capacity!
            explanation="Invalid reserve request",
            confidence=0.9,
        )
        result = validate_and_guardrail_directives([invalid_raw], 1, 50.0)
        d = result[0]
        assert d.applies is False
        assert d.directive_type == "no_op"
        assert d.structured_adjustment is None
        assert "exceeds capacity" in d.explanation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
