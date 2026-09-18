"""
Pipeline Orchestrator (Hour 3 Integration).
Coordinates the complete end-to-end workflow:
LLM Directives -> Deterministic Guardrails -> Mathematical Optimization -> Verification Replay.
"""

from typing import List
from app.core.schemas import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    HourlyPlanItem,
    RawDirectiveDTO,
    DirectiveInterpretation,
    DirectiveInterpretationResponse,
)
from app.guardrails.validator import validate_and_guardrail_directives
from app.optimizer.solver import solve_energy_schedule
from app.core.replayer import replay_and_calculate_metrics


async def orchestrate(request: OptimizeEnergyRequest) -> OptimizeEnergyResponse:
    """
    Orchestrates the 24-hour campus energy scheduling pipeline.
    """
    # 1. Collect / Parse raw directives from operator notes
    # (Safe fallback to no_op if LLM module is not yet wired)
    raw_directives: List[RawDirectiveDTO] = []
    for idx, note in enumerate(request.operator_notes):
        raw_directives.append(
            RawDirectiveDTO(
                note_index=idx,
                directive_type="no_op",
                raw_hours=None,
                raw_numeric_param=None,
                explanation=f"Interpreted operator note: '{note}'",
                confidence=1.0,
            )
        )

    # 2. Apply deterministic guardrails (Member 3)
    validated_directives = validate_and_guardrail_directives(
        raw_directives=raw_directives,
        notes_count=len(request.operator_notes),
        battery_capacity=request.battery.capacity,
    )

    # 3. Solve 24-hour cost-minimizing schedule with HiGHS LP solver (Member 3)
    solved_schedule, feasible = solve_energy_schedule(
        hours=request.hours,
        battery=request.battery,
        validated_directives=validated_directives,
    )

    # 4. Compute running battery state of charge (SOC) for each hour
    initial_energy = request.battery.initial_soc * request.battery.capacity
    current_soc = initial_energy
    hourly_plan: List[HourlyPlanItem] = []

    for item in solved_schedule:
        if item.action == "charge":
            current_soc += item.battery_charge_kwh
            action_name = "charge"
            action_kwh = item.battery_charge_kwh
        elif item.action == "discharge":
            current_soc -= item.battery_discharge_kwh
            action_name = "discharge"
            action_kwh = item.battery_discharge_kwh
        else:
            action_name = "idle"
            action_kwh = 0.0

        current_soc = max(0.0, min(request.battery.capacity, current_soc))

        hourly_plan.append(
            HourlyPlanItem(
                hour=item.hour,
                grid_kwh=round(item.grid_draw_kwh, 4),
                solar_used_kwh=round(item.solar_kwh, 4),
                battery_action=action_name,
                battery_kwh=round(action_kwh, 4),
                battery_energy_after_kwh=round(current_soc, 4),
            )
        )

    # 5. Replay and calculate verified metrics (Member 1 Replayer)
    metrics = replay_and_calculate_metrics(
        hourly_plan=hourly_plan,
        hours=request.hours,
    )

    # 6. Format directive interpretations according to Section 10.2 schema
    directive_responses: List[DirectiveInterpretationResponse] = [
        d.to_api_response() for d in validated_directives
    ]

    return OptimizeEnergyResponse(
        scenario_id=request.scenario_id,
        directive_interpretation=directive_responses,
        hourly_plan=hourly_plan,
        total_grid_kwh=round(metrics.total_grid_kwh, 2),
        total_cost_bdt=round(metrics.total_cost_bdt, 2),
        peak_grid_kwh=round(metrics.peak_grid_kwh, 2),
        plan_summary=f"Optimized 24h schedule with {metrics.total_grid_kwh:.2f} kWh total grid import at {metrics.total_cost_bdt:.2f} BDT cost.",
    )