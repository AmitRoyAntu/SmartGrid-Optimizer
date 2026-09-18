from app.core.schemas import (
    HourlyPlanItem,
    HourData,
    BatterySpec,
    DirectiveInterpretation,
    CalculatedMetrics,
)


TOLERANCE = 0.01


def replay_and_calculate_metrics(
    hourly_plan: list[HourlyPlanItem],
    hours: list[HourData],
    battery: BatterySpec,
    directives: list[DirectiveInterpretation],
) -> CalculatedMetrics:

    # Must have exactly 24 hours
    if len(hourly_plan) != 24:
        raise ValueError("Hourly plan must contain exactly 24 hours")

    plan_by_hour = {item.hour: item for item in hourly_plan}
    data_by_hour = {item.hour: item for item in hours}

    if sorted(plan_by_hour.keys()) != list(range(24)):
        raise ValueError("Hourly plan must contain unique hours 0 through 23")

    # Start with normal solar and battery reserve
    effective_solar = {
        h.hour: h.solar_kwh
        for h in hours
    }

    minimum_reserve = {
        h.hour: battery.minimum_energy_kwh
        for h in hours
    }

    no_charge_hours = set()
    no_discharge_hours = set()
    max_grid_limits = {}

    # Apply directives
    for directive in directives:

        if not directive.applies:
            continue

        adjustment = directive.structured_adjustment or {}
        affected_hours = adjustment.get("hours", [])

        if directive.directive_type == "solar_reduction":
            factor = adjustment["factor"]

            for hour in affected_hours:
                effective_solar[hour] = (
                    data_by_hour[hour].solar_kwh * factor
                )

        elif directive.directive_type == "minimum_battery_reserve":
            reserve = adjustment["minimum_energy_kwh"]

            for hour in affected_hours:
                minimum_reserve[hour] = max(
                    minimum_reserve[hour],
                    reserve,
                )

        elif directive.directive_type == "no_charge_window":
            no_charge_hours.update(affected_hours)

        elif directive.directive_type == "no_discharge_window":
            no_discharge_hours.update(affected_hours)

        elif directive.directive_type == "max_grid_window":
            max_grid = adjustment["max_grid_kwh"]

            for hour in affected_hours:
                max_grid_limits[hour] = max_grid

    # Start replay
    battery_energy = battery.initial_energy_kwh

    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    for hour in range(24):

        plan = plan_by_hour[hour]
        hour_data = data_by_hour[hour]

        charge = 0.0
        discharge = 0.0

        # -----------------------
        # Battery action
        # -----------------------

        if plan.battery_action == "charge":
            charge = plan.battery_kwh

            if charge > battery.max_charge_kwh_per_hour + TOLERANCE:
                raise ValueError(
                    f"Charge limit exceeded at hour {hour}"
                )

            if hour in no_charge_hours and charge > TOLERANCE:
                raise ValueError(
                    f"Charging not allowed at hour {hour}"
                )

        elif plan.battery_action == "discharge":
            discharge = plan.battery_kwh

            if discharge > battery.max_discharge_kwh_per_hour + TOLERANCE:
                raise ValueError(
                    f"Discharge limit exceeded at hour {hour}"
                )

            if hour in no_discharge_hours and discharge > TOLERANCE:
                raise ValueError(
                    f"Discharging not allowed at hour {hour}"
                )

        else:
            if plan.battery_kwh > TOLERANCE:
                raise ValueError(
                    f"Idle battery must have 0 kWh at hour {hour}"
                )

        # -----------------------
        # Battery state
        # -----------------------

        expected_energy = (
            battery_energy
            + charge
            - discharge
        )

        if (
            abs(
                expected_energy
                - plan.battery_energy_after_kwh
            )
            > TOLERANCE
        ):
            raise ValueError(
                f"Battery state incorrect at hour {hour}"
            )

        if expected_energy > battery.capacity_kwh + TOLERANCE:
            raise ValueError(
                f"Battery capacity exceeded at hour {hour}"
            )

        if expected_energy < minimum_reserve[hour] - TOLERANCE:
            raise ValueError(
                f"Battery below minimum reserve at hour {hour}"
            )

        # -----------------------
        # Solar check
        # -----------------------

        if (
            plan.solar_used_kwh
            > effective_solar[hour] + TOLERANCE
        ):
            raise ValueError(
                f"Solar usage exceeded at hour {hour}"
            )

        # -----------------------
        # Grid cap
        # -----------------------

        if hour in max_grid_limits:

            if (
                plan.grid_kwh
                > max_grid_limits[hour] + TOLERANCE
            ):
                raise ValueError(
                    f"Grid limit exceeded at hour {hour}"
                )

        # -----------------------
        # Energy balance
        # -----------------------

        supplied_energy = (
            plan.grid_kwh
            + plan.solar_used_kwh
            + discharge
        )

        required_energy = (
            hour_data.demand_kwh
            + charge
        )

        if (
            abs(supplied_energy - required_energy)
            > TOLERANCE
        ):
            raise ValueError(
                f"Energy balance failed at hour {hour}"
            )

        # -----------------------
        # Metrics
        # -----------------------

        total_grid += plan.grid_kwh

        total_cost += (
            plan.grid_kwh
            * hour_data.tariff_bdt_per_kwh
        )

        peak_grid = max(
            peak_grid,
            plan.grid_kwh,
        )

        battery_energy = expected_energy

    # End-of-day battery must return to initial level
    if (
        abs(
            battery_energy
            - battery.initial_energy_kwh
        )
        > TOLERANCE
    ):
        raise ValueError(
            "Final battery energy must equal initial battery energy"
        )

    return CalculatedMetrics(
        total_grid_kwh=total_grid,
        total_cost_bdt=total_cost,
        peak_grid_kwh=peak_grid,
    )