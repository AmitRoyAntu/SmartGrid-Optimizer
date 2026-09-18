from app.core.schemas import HourlyPlanItem, HourData, CalculatedMetrics


def replay_and_calculate_metrics(
    hourly_plan: list[HourlyPlanItem],
    hours: list[HourData]
) -> CalculatedMetrics:

    total_grid = 0
    total_cost = 0
    peak_grid = 0

    for plan, hour_data in zip(hourly_plan, hours):

        # Energy balance check
        if plan.battery_action == "discharge":
            discharge = plan.battery_kwh
            charge = 0
        elif plan.battery_action == "charge":
            charge = plan.battery_kwh
            discharge = 0
        else:
            charge = 0
            discharge = 0

        left_side = (
            plan.grid_kwh
            + plan.solar_used_kwh
            + discharge
        )

        right_side = (
            hour_data.demand_kwh
            + charge
        )

        if abs(left_side - right_side) > 0.01:
            raise ValueError(
                f"Energy balance failed at hour {plan.hour}"
            )

        total_grid += plan.grid_kwh

        total_cost += (
            plan.grid_kwh *
            hour_data.tariff_bdt_per_kwh
        )

        peak_grid = max(
            peak_grid,
            plan.grid_kwh
        )

    return CalculatedMetrics(
        total_grid_kwh=total_grid,
        total_cost_bdt=total_cost,
        peak_grid_kwh=peak_grid
    )