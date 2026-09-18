"""
Pydantic & dataclass schemas for GridWise LLM Energy Optimization.

This module defines all data transfer objects (DTOs) and models used across
the pipeline: LLM input/output, guardrails validation, optimizer results,
and official Hackathon HTTP API contracts.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, model_validator


# ============================================================================
# DTOs from Member 2 (LLM Interpreter)
# ============================================================================

@dataclass
class RawDirectiveDTO:
    """
    Unvalidated directive from LLM interpreter (Member 2).
    """
    note_index: int                    # Which operator note (0, 1, or 2)
    directive_type: str                # One of 6 types (may be invalid)
    raw_hours: Optional[List[int]] = None     # e.g., [13, 14, 15] or None
    raw_numeric_param: Optional[float] = None # e.g., 0.5 for 50% reduction
    explanation: str = ""              # Human-readable summary
    confidence: float = 1.0            # [0.0, 1.0] LLM confidence score


# ============================================================================
# DTOs from Member 3 (Guardrails & Validator)
# ============================================================================

# ============================================================================
# DTOs from Member 3 (Guardrails & Validator)
# ============================================================================

class DirectiveInterpretation(BaseModel):
    """
    Validated directive matching Problem Statement Section 10.2 schema.
    Shared contract between Guardrails Validator, LP Optimizer, and HTTP API response.
    """
    note_index: int
    applies: bool
    directive_type: str
    structured_adjustment: Optional[Dict[str, Any]] = None
    explanation: str = ""

    # Backward-compatible helper properties for optimizer and test assertions
    @property
    def hours(self) -> List[int]:
        if self.structured_adjustment and "hours" in self.structured_adjustment:
            return self.structured_adjustment["hours"]
        return []

    @property
    def factor(self) -> float:
        if self.structured_adjustment:
            if "factor" in self.structured_adjustment:
                return float(self.structured_adjustment["factor"])
            if "minimum_energy_kwh" in self.structured_adjustment:
                return float(self.structured_adjustment["minimum_energy_kwh"])
            if "max_grid_kwh" in self.structured_adjustment:
                return float(self.structured_adjustment["max_grid_kwh"])
        return 1.0

    @property
    def fallback_reason(self) -> Optional[str]:
        return self.explanation if not self.applies else None

    @property
    def applied_constraint(self) -> str:
        return self.explanation

    def to_api_response(self) -> "DirectiveInterpretation":
        """Self-identity: already matches official API response format."""
        return self

    @model_validator(mode="before")
    @classmethod
    def sync_directive_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If instantiated with legacy fields without structured_adjustment
            if "structured_adjustment" not in data:
                dtype = data.get("directive_type", "no_op")
                applies = data.get("applies", False)
                if not applies or dtype == "no_op":
                    data["directive_type"] = "no_op"
                    data["applies"] = False
                    data["structured_adjustment"] = None
                else:
                    hours = data.get("hours", [])
                    if dtype == "solar_reduction":
                        data["structured_adjustment"] = {
                            "hours": hours,
                            "factor": data.get("factor", 1.0),
                        }
                    elif dtype == "minimum_battery_reserve":
                        data["structured_adjustment"] = {
                            "hours": hours,
                            "minimum_energy_kwh": data.get("minimum_energy_kwh", data.get("factor", 0.0)),
                        }
                    elif dtype == "max_grid_window":
                        data["structured_adjustment"] = {
                            "hours": hours,
                            "max_grid_kwh": data.get("max_grid_kwh", data.get("factor", 0.0)),
                        }
                    elif dtype in ("no_charge_window", "no_discharge_window"):
                        data["structured_adjustment"] = {"hours": hours}

            if "explanation" not in data or not data["explanation"]:
                data["explanation"] = data.get("applied_constraint", data.get("fallback_reason", ""))
        return data


DirectiveInterpretationResponse = DirectiveInterpretation


# ============================================================================
# Official API Schemas & Downstream Models (Member 1 & Hackathon Contract)
# ============================================================================

class BatterySpec(BaseModel):
    """
    Battery configuration supporting both internal and external field names.
    """
    capacity: float = Field(default=0.0, description="Battery capacity [kWh]")
    capacity_kwh: Optional[float] = Field(default=None)
    initial_soc: float = Field(default=0.5, ge=0, le=1)
    initial_energy_kwh: Optional[float] = Field(default=None)
    minimum_energy_kwh: Optional[float] = Field(default=0.0)
    max_charge_rate: float = Field(default=10.0, description="Max charge rate [kWh/h]")
    max_charge_kwh_per_hour: Optional[float] = Field(default=None)
    max_discharge_rate: float = Field(default=10.0, description="Max discharge rate [kWh/h]")
    max_discharge_kwh_per_hour: Optional[float] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def sync_battery_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Map external API fields to internal fields
            if "capacity_kwh" in data and "capacity" not in data:
                data["capacity"] = data["capacity_kwh"]
            if "capacity" in data and "capacity_kwh" not in data:
                data["capacity_kwh"] = data["capacity"]

            if "initial_energy_kwh" in data and "initial_soc" not in data:
                cap = data.get("capacity", data.get("capacity_kwh", 1.0))
                data["initial_soc"] = data["initial_energy_kwh"] / cap if cap > 0 else 0.5
            if "initial_soc" in data and "initial_energy_kwh" not in data:
                cap = data.get("capacity", data.get("capacity_kwh", 1.0))
                data["initial_energy_kwh"] = data["initial_soc"] * cap

            if "max_charge_kwh_per_hour" in data and "max_charge_rate" not in data:
                data["max_charge_rate"] = data["max_charge_kwh_per_hour"]
            if "max_charge_rate" in data and "max_charge_kwh_per_hour" not in data:
                data["max_charge_kwh_per_hour"] = data["max_charge_rate"]

            if "max_discharge_kwh_per_hour" in data and "max_discharge_rate" not in data:
                data["max_discharge_rate"] = data["max_discharge_kwh_per_hour"]
            if "max_discharge_rate" in data and "max_discharge_kwh_per_hour" not in data:
                data["max_discharge_kwh_per_hour"] = data["max_discharge_rate"]

        return data


# Alias for BatterySpec
BatteryData = BatterySpec


class HourData(BaseModel):
    """Hourly scenario data supporting both internal and external contracts."""
    hour: int = Field(ge=0, le=23, description="Hour of day [0..23]")
    demand_kwh: float = Field(default=0.0, ge=0)
    solar_kwh: float = Field(default=0.0, ge=0)
    tariff_bdt_per_kwh: float = Field(default=0.0, ge=0)

    # Backward compatibility aliases for Member 3 tests
    solar_generation: Optional[float] = None
    demand: Optional[float] = None
    grid_price: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def sync_hour_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "solar_generation" in data and "solar_kwh" not in data:
                data["solar_kwh"] = data["solar_generation"]
            elif "solar_kwh" in data and "solar_generation" not in data:
                data["solar_generation"] = data["solar_kwh"]

            if "demand" in data and "demand_kwh" not in data:
                data["demand_kwh"] = data["demand"]
            elif "demand_kwh" in data and "demand" not in data:
                data["demand"] = data["demand_kwh"]

            if "grid_price" in data and "tariff_bdt_per_kwh" not in data:
                data["tariff_bdt_per_kwh"] = data["grid_price"]
            elif "tariff_bdt_per_kwh" in data and "grid_price" not in data:
                data["grid_price"] = data["tariff_bdt_per_kwh"]

        return data


class HourlyPlanItem(BaseModel):
    """
    Single hour's plan output supporting both Section 10.3 API and internal tests.
    """
    hour: int
    grid_kwh: float = 0.0
    solar_used_kwh: float = 0.0
    battery_action: str = "idle"  # 'charge', 'discharge', 'idle'
    battery_kwh: float = 0.0
    battery_energy_after_kwh: float = 0.0

    # Backward-compatible fields
    grid_draw_kwh: Optional[float] = None
    battery_discharge_kwh: Optional[float] = None
    battery_charge_kwh: Optional[float] = None
    solar_kwh: Optional[float] = None
    action: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sync_plan_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync action <-> battery_action
            if "action" in data and "battery_action" not in data:
                data["battery_action"] = data["action"]
            elif "battery_action" in data and "action" not in data:
                data["action"] = data["battery_action"]

            # Sync grid
            if "grid_draw_kwh" in data and "grid_kwh" not in data:
                data["grid_kwh"] = data["grid_draw_kwh"]
            elif "grid_kwh" in data and "grid_draw_kwh" not in data:
                data["grid_draw_kwh"] = data["grid_kwh"]

            # Sync solar
            if "solar_kwh" in data and "solar_used_kwh" not in data:
                data["solar_used_kwh"] = data["solar_kwh"]
            elif "solar_used_kwh" in data and "solar_kwh" not in data:
                data["solar_kwh"] = data["solar_used_kwh"]

            # Sync battery kwh
            if "battery_kwh" not in data:
                c = data.get("battery_charge_kwh", 0.0)
                d = data.get("battery_discharge_kwh", 0.0)
                data["battery_kwh"] = max(c, d)

            if "battery_charge_kwh" not in data:
                data["battery_charge_kwh"] = data.get("battery_kwh", 0.0) if data.get("battery_action") == "charge" else 0.0
            if "battery_discharge_kwh" not in data:
                data["battery_discharge_kwh"] = data.get("battery_kwh", 0.0) if data.get("battery_action") == "discharge" else 0.0

        return data





class CalculatedMetrics(BaseModel):
    """Metrics recalculated by the Replayer."""
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float


class OptimizeEnergyRequest(BaseModel):
    """Problem Statement Section 07: Main API request payload."""
    scenario_id: str
    operator_notes: List[str]
    hours: List[HourData]
    battery: BatterySpec


class OptimizeEnergyResponse(BaseModel):
    """Problem Statement Section 10: Main API response payload."""
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretationResponse]
    hourly_plan: List[HourlyPlanItem]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str


# Legacy / Internal alias
OptimizationScenario = OptimizeEnergyRequest
OptimizationResult = OptimizeEnergyResponse


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

CONFIDENCE_THRESHOLD = 0.5
ENERGY_TOLERANCE = 0.01
SOLVER_TIMEOUT_MS = 15
