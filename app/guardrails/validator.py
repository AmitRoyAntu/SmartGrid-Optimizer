"""
Guardrails Validator: Deterministic validation and normalization of LLM directives.

This module transforms raw, unvalidated directives from the LLM into safe,
validated DirectiveInterpretation objects that the optimizer can safely consume.

Key principles:
- Never crash; always return valid output
- Clamp, sort, and deduplicate inputs
- Fall back gracefully to no_op on invalid data
- Log all validation decisions for debugging
"""

from typing import List
from app.core.schemas import (
    RawDirectiveDTO,
    DirectiveInterpretation,
    VALID_DIRECTIVE_TYPES,
    CONFIDENCE_THRESHOLD,
)


def validate_and_guardrail_directives(
    raw_directives: List[RawDirectiveDTO],
    notes_count: int,
    battery_capacity: float,
) -> List[DirectiveInterpretation]:
    """
    Validates and normalizes raw LLM directives.

    Never crashes; falls back gracefully to no_op on invalid input.

    Args:
        raw_directives: List of unvalidated directives from Member 2 (LLM)
        notes_count: Total number of operator notes (1-3)
        battery_capacity: Battery capacity in kWh (e.g., 50.0)

    Returns:
        List of validated DirectiveInterpretation objects

    Validation rules:
    1. Hours: Clamp to [0..23], sort, deduplicate
    2. Factor: Clamp to [0.0, 1.0]
    3. Directive type: Must be in VALID_DIRECTIVE_TYPES
    4. Confidence: < CONFIDENCE_THRESHOLD → treat as no_op
    5. Battery reserve: Must not exceed capacity
    6. Never crash: Always return valid list
    """
    validated = []

    # If no directives provided, return empty list
    if not raw_directives:
        return validated

    for raw_dir in raw_directives:
        try:
            # Start with safe defaults
            result = DirectiveInterpretation(
                note_index=raw_dir.note_index,
                directive_type=raw_dir.directive_type,
                hours=[],
                factor=1.0,
                applies=False,
                applied_constraint="",
                fallback_reason=None,
            )

            # === Rule 0: Handle no_op (always falls back) ===
            if raw_dir.directive_type == "no_op":
                result.fallback_reason = "no_op directive: no constraint applied"
                validated.append(result)
                continue

            # === Rule 1: Validate directive type ===
            if raw_dir.directive_type not in VALID_DIRECTIVE_TYPES:
                result.fallback_reason = (
                    f"Unknown directive type: '{raw_dir.directive_type}'. "
                    f"Valid types: {sorted(VALID_DIRECTIVE_TYPES)}"
                )
                validated.append(result)
                continue

            # === Rule 2: Validate hours ===
            if raw_dir.raw_hours:
                try:
                    # Clamp to [0..23], sort, deduplicate
                    hours = sorted(
                        set(
                            h
                            for h in raw_dir.raw_hours
                            if isinstance(h, int) and 0 <= h <= 23
                        )
                    )
                    result.hours = hours

                    # If no valid hours remain, mark as not applying
                    if not hours:
                        result.fallback_reason = f"No valid hours after filtering. Raw hours: {raw_dir.raw_hours}"
                        validated.append(result)
                        continue
                except Exception as e:
                    result.fallback_reason = f"Error parsing hours: {str(e)}"
                    validated.append(result)
                    continue

            # === Rule 3: Validate and clamp factor ===
            if raw_dir.raw_numeric_param is not None:
                try:
                    param = float(raw_dir.raw_numeric_param)

                    # For battery reserve, check BEFORE clamping
                    if raw_dir.directive_type == "minimum_battery_reserve":
                        reserve_kwh = param * battery_capacity
                        if reserve_kwh < 0 or reserve_kwh > battery_capacity:
                            result.fallback_reason = (
                                f"Battery reserve {reserve_kwh:.2f} kWh "
                                f"exceeds capacity {battery_capacity} kWh"
                            )
                            validated.append(result)
                            continue

                    # Clamp to [0.0, 1.0]
                    result.factor = max(0.0, min(1.0, param))
                except (ValueError, TypeError):
                    result.fallback_reason = (
                        f"Invalid numeric parameter: {raw_dir.raw_numeric_param}. "
                        "Must be a number in [0.0, 1.0]."
                    )
                    validated.append(result)
                    continue
            else:
                # None is OK; use neutral default based on directive type
                if raw_dir.directive_type == "minimum_battery_reserve":
                    result.factor = 0.0
                else:
                    result.factor = 1.0

            # === Rule 4: Check confidence score ===
            if raw_dir.confidence < CONFIDENCE_THRESHOLD:
                result.fallback_reason = (
                    f"Low confidence score: {raw_dir.confidence} "
                    f"< {CONFIDENCE_THRESHOLD}"
                )
                validated.append(result)
                continue

            # === All validations passed ===
            result.applies = True
            result.applied_constraint = _describe_constraint(
                raw_dir.directive_type, result
            )

            validated.append(result)

        except Exception as e:
            # Catch-all: Never crash, always return something valid
            fallback = DirectiveInterpretation(
                note_index=raw_dir.note_index,
                directive_type=raw_dir.directive_type,
                hours=[],
                factor=1.0,
                applies=False,
                applied_constraint="",
                fallback_reason=f"Unexpected error during validation: {str(e)}",
            )
            validated.append(fallback)

    return validated


def _describe_constraint(directive_type: str, result: DirectiveInterpretation) -> str:
    """
    Generate a human-readable description of the constraint.

    Args:
        directive_type: Type of directive
        result: Validated DirectiveInterpretation

    Returns:
        String description for logging
    """
    hours_str = f"{{{', '.join(map(str, result.hours))}}}" if result.hours else "[]"

    descriptions = {
        "solar_reduction": (
            f"Solar generation reduced by {result.factor * 100:.1f}% in hours {hours_str}"
        ),
        "minimum_battery_reserve": (
            f"Battery reserve floor set to {result.factor * 100:.1f}% of capacity"
        ),
        "no_charge_window": (f"Battery charging prohibited in hours {hours_str}"),
        "no_discharge_window": (f"Battery discharging prohibited in hours {hours_str}"),
        "max_grid_window": (
            f"Grid draw capped to {result.factor * 100:.1f}% in hours {hours_str}"
        ),
        "no_op": "No constraint applied",
    }

    return descriptions.get(directive_type, f"Unknown directive type: {directive_type}")
