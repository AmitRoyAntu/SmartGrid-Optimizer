"""
Guardrails Validator: Deterministic validation and normalization of LLM directives.

Transforms raw, unvalidated directives from the LLM into safe,
validated DirectiveInterpretation objects matching Section 10.2 of the Problem Statement.

Key principles:
- Never crash; always return valid output
- Clamp, sort, and deduplicate inputs
- Fall back gracefully to no_op with structured_adjustment=None on invalid data
- Enforce exact contracts:
  * solar_reduction: {"hours": [...], "factor": number}
  * minimum_battery_reserve: {"hours": [...], "minimum_energy_kwh": number}
  * no_charge_window: {"hours": [...]}
  * no_discharge_window: {"hours": [...]}
  * max_grid_window: {"hours": [...], "max_grid_kwh": number}
  * no_op: structured_adjustment is None, applies is False
"""

from typing import List, Optional
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
    Validates and normalizes raw LLM directives into canonical DirectiveInterpretation objects.

    Never crashes; falls back gracefully to no_op on invalid input.

    Args:
        raw_directives: List of unvalidated directives from Member 2 (LLM)
        notes_count: Total number of operator notes (1-3)
        battery_capacity: Battery capacity in kWh (e.g., 50.0)

    Returns:
        List of validated DirectiveInterpretation objects matching Problem Statement Section 10.2
    """
    validated: List[DirectiveInterpretation] = []

    if not raw_directives:
        return validated

    for raw_dir in raw_directives:
        try:
            # === Rule 0: Handle no_op (always falls back) ===
            if raw_dir.directive_type == "no_op":
                validated.append(
                    DirectiveInterpretation(
                        note_index=raw_dir.note_index,
                        applies=False,
                        directive_type="no_op",
                        structured_adjustment=None,
                        explanation=raw_dir.explanation or "No operation applied to schedule.",
                    )
                )
                continue

            # === Rule 1: Validate directive type ===
            if raw_dir.directive_type not in VALID_DIRECTIVE_TYPES:
                validated.append(
                    DirectiveInterpretation(
                        note_index=raw_dir.note_index,
                        applies=False,
                        directive_type="no_op",
                        structured_adjustment=None,
                        explanation=(
                            f"Unknown directive type: '{raw_dir.directive_type}'. "
                            f"Valid types: {sorted(VALID_DIRECTIVE_TYPES)}"
                        ),
                    )
                )
                continue

            # === Rule 2: Check confidence score ===
            if raw_dir.confidence < CONFIDENCE_THRESHOLD:
                validated.append(
                    DirectiveInterpretation(
                        note_index=raw_dir.note_index,
                        applies=False,
                        directive_type="no_op",
                        structured_adjustment=None,
                        explanation=f"Low confidence score: {raw_dir.confidence} < {CONFIDENCE_THRESHOLD}",
                    )
                )
                continue

            # === Rule 3: Validate and normalize hours ===
            hours: List[int] = []
            if raw_dir.raw_hours is not None:
                try:
                    hours = sorted(
                        set(
                            h
                            for h in raw_dir.raw_hours
                            if isinstance(h, int) and 0 <= h <= 23
                        )
                    )
                    if not hours:
                        validated.append(
                            DirectiveInterpretation(
                                note_index=raw_dir.note_index,
                                applies=False,
                                directive_type="no_op",
                                structured_adjustment=None,
                                explanation=f"No valid hours after filtering. Raw hours: {raw_dir.raw_hours}",
                            )
                        )
                        continue
                except Exception as e:
                    validated.append(
                        DirectiveInterpretation(
                            note_index=raw_dir.note_index,
                            applies=False,
                            directive_type="no_op",
                            structured_adjustment=None,
                            explanation=f"Error parsing hours: {str(e)}",
                        )
                    )
                    continue
            else:
                # Directives like minimum_battery_reserve with no hours apply to all 24 hours
                if raw_dir.directive_type == "minimum_battery_reserve":
                    hours = list(range(24))
                else:
                    # Hours are required for other directives
                    validated.append(
                        DirectiveInterpretation(
                            note_index=raw_dir.note_index,
                            applies=False,
                            directive_type="no_op",
                            structured_adjustment=None,
                            explanation=f"Missing hours for directive type '{raw_dir.directive_type}'",
                        )
                    )
                    continue

            # === Rule 4: Validate parameters according to directive type ===
            if raw_dir.directive_type == "solar_reduction":
                if raw_dir.raw_numeric_param is None:
                    validated.append(
                        DirectiveInterpretation(
                            note_index=raw_dir.note_index,
                            applies=False,
                            directive_type="no_op",
                            structured_adjustment=None,
                            explanation="Missing reduction factor for solar_reduction",
                        )
                    )
                    continue
                try:
                    factor = float(raw_dir.raw_numeric_param)
                    factor = max(0.0, min(1.0, factor))
                except (ValueError, TypeError):
                    validated.append(
                        DirectiveInterpretation(
                            note_index=raw_dir.note_index,
                            applies=False,
                            directive_type="no_op",
                            structured_adjustment=None,
                            explanation=f"Invalid numeric parameter: {raw_dir.raw_numeric_param}. Must be a number.",
                        )
                    )
                    continue

                validated.append(
                    DirectiveInterpretation(
                        note_index=raw_dir.note_index,
                        applies=True,
                        directive_type="solar_reduction",
                        structured_adjustment={"hours": hours, "factor": round(factor, 4)},
                        explanation=raw_dir.explanation or f"Solar generation reduced by {factor * 100:.1f}% in hours {hours}",
                    )
                )

            elif raw_dir.directive_type == "minimum_battery_reserve":
                if raw_dir.raw_numeric_param is None:
                    validated.append(
                        DirectiveInterpretation(
                            note_index=raw_dir.note_index,
                            applies=False,
                            directive_type="no_op",
                            structured_adjustment=None,
                            explanation="Missing minimum_energy_kwh parameter for minimum_battery_reserve",
                        )
                    )
                    continue
                try:
                    reserve_kwh = float(raw_dir.raw_numeric_param)
                    # Support percentage/fraction of battery capacity (e.g., 0.5 -> 50% of capacity)
                    if 0.0 < reserve_kwh <= 1.0 and battery_capacity > 0:
                        reserve_kwh = reserve_kwh * battery_capacity
                except (ValueError, TypeError):
                    validated.append(
                        DirectiveInterpretation(
                            note_index=raw_dir.note_index,
                            applies=False,
                            directive_type="no_op",
                            structured_adjustment=None,
                            explanation=f"Invalid numeric parameter: {raw_dir.raw_numeric_param}. Must be a number.",
                        )
                    )
                    continue

                if reserve_kwh < 0.0 or reserve_kwh > battery_capacity:
                    validated.append(
                        DirectiveInterpretation(
                            note_index=raw_dir.note_index,
                            applies=False,
                            directive_type="no_op",
                            structured_adjustment=None,
                            explanation=(
                                f"Battery reserve {reserve_kwh:.2f} kWh exceeds capacity {battery_capacity} kWh"
                                if reserve_kwh > battery_capacity
                                else f"Battery reserve {reserve_kwh:.2f} kWh must be non-negative"
                            ),
                        )
                    )
                    continue

                clean_reserve = int(round(reserve_kwh)) if abs(round(reserve_kwh) - reserve_kwh) < 1e-4 else round(reserve_kwh, 4)
                validated.append(
                    DirectiveInterpretation(
                        note_index=raw_dir.note_index,
                        applies=True,
                        directive_type="minimum_battery_reserve",
                        structured_adjustment={"hours": hours, "minimum_energy_kwh": clean_reserve},
                        explanation=raw_dir.explanation or f"Battery reserve floor set to {clean_reserve} kWh in hours {hours}",
                    )
                )

            elif raw_dir.directive_type == "max_grid_window":
                if raw_dir.raw_numeric_param is None:
                    validated.append(
                        DirectiveInterpretation(
                            note_index=raw_dir.note_index,
                            applies=False,
                            directive_type="no_op",
                            structured_adjustment=None,
                            explanation="Missing max_grid_kwh parameter for max_grid_window",
                        )
                    )
                    continue
                try:
                    max_grid_kwh = float(raw_dir.raw_numeric_param)
                except (ValueError, TypeError):
                    validated.append(
                        DirectiveInterpretation(
                            note_index=raw_dir.note_index,
                            applies=False,
                            directive_type="no_op",
                            structured_adjustment=None,
                            explanation=f"Invalid numeric parameter: {raw_dir.raw_numeric_param}. Must be a number.",
                        )
                    )
                    continue

                if max_grid_kwh < 0.0:
                    validated.append(
                        DirectiveInterpretation(
                            note_index=raw_dir.note_index,
                            applies=False,
                            directive_type="no_op",
                            structured_adjustment=None,
                            explanation=f"Max grid limit {max_grid_kwh:.2f} kWh must be non-negative",
                        )
                    )
                    continue

                clean_max_grid = int(round(max_grid_kwh)) if abs(round(max_grid_kwh) - max_grid_kwh) < 1e-4 else round(max_grid_kwh, 4)
                validated.append(
                    DirectiveInterpretation(
                        note_index=raw_dir.note_index,
                        applies=True,
                        directive_type="max_grid_window",
                        structured_adjustment={"hours": hours, "max_grid_kwh": clean_max_grid},
                        explanation=raw_dir.explanation or f"Grid draw capped to {clean_max_grid} kWh in hours {hours}",
                    )
                )

            elif raw_dir.directive_type in ("no_charge_window", "no_discharge_window"):
                validated.append(
                    DirectiveInterpretation(
                        note_index=raw_dir.note_index,
                        applies=True,
                        directive_type=raw_dir.directive_type,
                        structured_adjustment={"hours": hours},
                        explanation=raw_dir.explanation or (
                            f"Battery charging prohibited in hours {hours}"
                            if raw_dir.directive_type == "no_charge_window"
                            else f"Battery discharging prohibited in hours {hours}"
                        ),
                    )
                )

            else:
                validated.append(
                    DirectiveInterpretation(
                        note_index=raw_dir.note_index,
                        applies=False,
                        directive_type="no_op",
                        structured_adjustment=None,
                        explanation=f"Unhandled directive type: {raw_dir.directive_type}",
                    )
                )

        except Exception as e:
            # Catch-all: Never crash, always return safe no_op
            validated.append(
                DirectiveInterpretation(
                    note_index=raw_dir.note_index,
                    applies=False,
                    directive_type="no_op",
                    structured_adjustment=None,
                    explanation=f"Unexpected error during validation: {str(e)}",
                )
            )

    return validated

