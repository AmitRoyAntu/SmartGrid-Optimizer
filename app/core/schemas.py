from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Literal


class HourData(BaseModel):
    hour: int = Field(ge=0, le=23)
    demand_kwh: float = Field(ge=0)
    solar_kwh: float = Field(ge=0)
    tariff_bdt_per_kwh: float = Field(ge=0)


class BatterySpec(BaseModel):
    capacity_kwh: float = Field(gt=0)
    initial_energy_kwh: float = Field(ge=0)
    minimum_energy_kwh: float = Field(ge=0)
    max_charge_kwh_per_hour: float = Field(ge=0)
    max_discharge_kwh_per_hour: float = Field(ge=0)


class OptimizeEnergyRequest(BaseModel):
    scenario_id: str

    operator_notes: List[str] = Field(
        min_length=1,
        max_length=3
    )

    hours: List[HourData] = Field(
        min_length=24,
        max_length=24
    )

    battery: BatterySpec

    @model_validator(mode="after")
    def validate_hours(self):
        hour_numbers = [item.hour for item in self.hours]

        if sorted(hour_numbers) != list(range(24)):
            raise ValueError("hours must contain unique hours 0 through 23")

        return self


class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: Literal[
        "solar_reduction",
        "minimum_battery_reserve",
        "no_charge_window",
        "no_discharge_window",
        "max_grid_window",
        "no_op",
    ]
    structured_adjustment: Optional[dict]
    explanation: str


class HourlyPlanItem(BaseModel):
    hour: int
    grid_kwh: float
    solar_used_kwh: float
    battery_action: Literal[
        "charge",
        "discharge",
        "idle",
    ]
    battery_kwh: float
    battery_energy_after_kwh: float


class OptimizeEnergyResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlanItem]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str

class CalculatedMetrics(BaseModel):
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float

class RawDirectiveDTO(BaseModel):
    note_index: int
    directive_type: str
    raw_hours: list[int]
    raw_numeric_param: float
    confidence: float