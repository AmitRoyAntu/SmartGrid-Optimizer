"""
Pydantic & dataclass schemas for GridWise LLM Energy Optimization.

This module defines all data transfer objects (DTOs) and models used across
the pipeline: LLM input/output, guardrails validation, and optimizer results.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# DTOs from Member 2 (LLM Interpreter)
# ============================================================================

@dataclass
class RawDirectiveDTO:
    """
    Unvalidated directive from LLM interpreter (Member 2).

    These may have errors:
    - raw_hours might be out of [0..23] range
    - raw_numeric_param might be outside [0.0, 1.0]
    - confidence might indicate low certainty
    - directive_type might be unknown
    """
    note_index: int                    # Which operator note (0, 1, or 2)
    directive_type: str                # One of 6 types (may be invalid)
    raw_hours: Optional[List[int]]     # e.g., [13, 14, 15] or None
    raw_numeric_param: Optional[float] # e.g., 0.5 for 50% reduction
    explanation: str                   # Human-readable summary
    confidence: float                  # [0.0, 1.0] LLM confidence score


# ============================================================================
# DTOs from Member 3 (Guardrails & Validator)
# ============================================================================

@dataclass
class DirectiveInterpretation:
    """
    Validated, deterministic directive from guardrails validator (Member 3).

    All fields are guaranteed to be safe and valid:
    - hours: sorted, deduplicated, clipped to [0..23]
    - factor: clamped to [0.0, 1.0]
    - applies: True if constraint is enforced, False if fell back
    - fallback_reason: None if valid, string explanation if fell back
    """
    note_index: int                    # Original note index
    directive_type: str                # Validated type
    hours: List[int]                   # Sorted [0..23], deduplicated
    factor: float                      # Clamped [0.0, 1.0]
    applies: bool                      # Whether to enforce this constraint
    applied_constraint: str            # Description of constraint for logging
    fallback_reason: Optional[str]     # Why it fell back (None if valid)


@dataclass
class HourlyPlanItem:
    """
    Single hour's energy action from optimizer (Member 3).

    Represents the cost-optimized decision for hour h:
    - action: what to do (charge, discharge, or idle)
    - grid_draw_kwh: power from grid (non-negative)
    - battery_charge_kwh: power into battery (non-negative)
    - battery_discharge_kwh: power from battery (non-negative)
    - solar_kwh: solar generation (after any reductions)
    """
    hour: int                          # 0..23
    action: str                        # 'charge', 'discharge', or 'idle'
    grid_draw_kwh: float               # Grid power [kWh]
    battery_discharge_kwh: float       # Battery discharge [kWh]
    battery_charge_kwh: float          # Battery charge [kWh]
    solar_kwh: float                   # Solar generation [kWh]


# ============================================================================
# Configuration & Input Models (Pydantic)
# ============================================================================

class BatterySpec(BaseModel):
    """Battery configuration and constraints."""
    capacity: float = Field(..., gt=0, description="Battery capacity [kWh]")
    initial_soc: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Initial state of charge as fraction of capacity"
    )
    max_charge_rate: float = Field(..., gt=0, description="Max charge rate [kWh/h]")
    max_discharge_rate: float = Field(..., gt=0, description="Max discharge rate [kWh/h]")


class HourData(BaseModel):
    """Hourly scenario data (solar, demand, price)."""
    hour: int = Field(ge=0, le=23, description="Hour of day [0..23]")
    solar_generation: float = Field(ge=0, description="Solar generation [kWh]")
    demand: float = Field(ge=0, description="Load demand [kWh]")
    grid_price: float = Field(ge=0, description="Grid electricity price [BDT/kWh]")


class OptimizationScenario(BaseModel):
    """Complete scenario for optimization."""
    scenario_id: str
    hours: List[HourData]
    battery: BatterySpec
    notes_count: int = Field(ge=1, le=3, description="Number of operator notes")


# ============================================================================
# Output Models (Pydantic for API responses)
# ============================================================================

class OptimizationResult(BaseModel):
    """Complete optimization result."""
    scenario_id: str
    hourly_plan: List[HourlyPlanItem]
    directive_interpretation: List[DirectiveInterpretation]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    feasible: bool
    plan_summary: str


# ============================================================================
# Constants
# ============================================================================

VALID_DIRECTIVE_TYPES = {
    'solar_reduction',
    'minimum_battery_reserve',
    'no_charge_window',
    'no_discharge_window',
    'max_grid_window',
    'no_op'
}

CONFIDENCE_THRESHOLD = 0.5  # Directives with confidence < 0.5 treated as no_op
ENERGY_TOLERANCE = 0.01  # kWh tolerance for energy balance verification
SOLVER_TIMEOUT_MS = 15  # Maximum LP solver time in milliseconds
