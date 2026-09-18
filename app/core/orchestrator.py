from app.core.schemas import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    HourlyPlanItem
)
from app.core.replayer import replay_and_calculate_metrics


async def orchestrate(request: OptimizeEnergyRequest) -> OptimizeEnergyResponse:

    hourly_plan = []

    for hour in request.hours:
        hourly_plan.append(
            HourlyPlanItem(
                hour=hour.hour,
                grid_kwh=hour.demand_kwh,
                solar_used_kwh=0,
                battery_action="idle",
                battery_kwh=0,
                battery_energy_after_kwh=request.battery.initial_energy_kwh
            )
        )

    metrics = replay_and_calculate_metrics(
        hourly_plan,
        request.hours,
        request.battery,
        []
    )

    return OptimizeEnergyResponse(
        scenario_id=request.scenario_id,
        directive_interpretation=[],
        hourly_plan=hourly_plan,
        total_grid_kwh=metrics.total_grid_kwh,
        total_cost_bdt=metrics.total_cost_bdt,
        peak_grid_kwh=metrics.peak_grid_kwh,
        plan_summary="Temporary test plan"
    )