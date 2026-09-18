"""
Schedule Replayer: Independent simulation and verification engine (Member 1).

Simulates hour-by-hour physics to recalculate metrics independently:
- Total grid energy (kWh)
- Total electricity cost (BDT)
- Peak grid draw (kWh)
- Strict verification of energy balance (|diff| <= 0.01 kWh)
- Section 9.6 End-of-Day battery neutrality verification (|E[23] - E_0| <= 0.01 kWh)
"""

from typing import List, Optional
from app.core.schemas import HourlyPlanItem, HourData, CalculatedMetrics, ENERGY_TOLERANCE


def replay_and_calculate_metrics(
    hourly_plan: List[HourlyPlanItem],
    hours: List[HourData],
    initial_energy_kwh: Optional[float] = None,
    battery_capacity: Optional[float] = None,
) -> CalculatedMetrics:
    """
    Independently simulates and verifies the 24-hour schedule.

    Args:
        hourly_plan: 24-hour schedule output from optimizer
        hours: 24-hour input scenario data
        initial_energy_kwh: Optional initial battery energy for neutrality verification
        battery_capacity: Optional battery capacity for boundary verification

    Returns:
        CalculatedMetrics with total_grid_kwh, total_cost_bdt, peak_grid_kwh

    Raises:
        ValueError: If energy balance, capacity limits, or battery neutrality fails
    """
    if len(hourly_plan) != 24 or len(hours) != 24:
        raise ValueError(
            f"Schedule must have exactly 24 hours (got plan={len(hourly_plan)}, hours={len(hours)})"
        )

    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    for plan, hour_data in zip(hourly_plan, hours):
        if plan.hour != hour_data.hour:
            raise ValueError(f"Hour mismatch: plan hour {plan.hour} != data hour {hour_data.hour}")

        # Extract charge/discharge based on action
        if plan.battery_action == "discharge":
            discharge = plan.battery_kwh
            charge = 0.0
        elif plan.battery_action == "charge":
            charge = plan.battery_kwh
            discharge = 0.0
        elif plan.battery_action == "idle":
            charge = 0.0
            discharge = 0.0
        else:
            raise ValueError(
                f"Invalid battery action '{plan.battery_action}' at hour {plan.hour}. "
                "Must be 'charge', 'discharge', or 'idle'."
            )

        # 1. Physical Energy balance: grid + solar_used + discharge == demand + charge
        left_side = plan.grid_kwh + plan.solar_used_kwh + discharge
        right_side = hour_data.demand_kwh + charge

        if abs(left_side - right_side) > ENERGY_TOLERANCE:
            raise ValueError(
                f"Energy balance failed at hour {plan.hour}: "
                f"supply ({left_side:.4f} kWh) != demand ({right_side:.4f} kWh)"
            )

        # 2. Battery capacity boundary check
        if battery_capacity is not None:
            if plan.battery_energy_after_kwh < -ENERGY_TOLERANCE:
                raise ValueError(
                    f"Battery underflow at hour {plan.hour}: {plan.battery_energy_after_kwh:.4f} kWh < 0"
                )
            if plan.battery_energy_after_kwh > battery_capacity + ENERGY_TOLERANCE:
                raise ValueError(
                    f"Battery overflow at hour {plan.hour}: "
                    f"{plan.battery_energy_after_kwh:.4f} kWh > capacity {battery_capacity:.4f} kWh"
                )

        total_grid += plan.grid_kwh
        total_cost += plan.grid_kwh * hour_data.tariff_bdt_per_kwh
        peak_grid = max(peak_grid, plan.grid_kwh)

    # 3. Section 9.6 End-of-Day Battery Neutrality: E[23] == E_0
    if initial_energy_kwh is not None:
        final_energy = hourly_plan[-1].battery_energy_after_kwh
        if abs(final_energy - initial_energy_kwh) > ENERGY_TOLERANCE:
            raise ValueError(
                f"End-of-day battery neutrality violated: "
                f"final energy ({final_energy:.4f} kWh) != initial energy ({initial_energy_kwh:.4f} kWh)"
            )

    return CalculatedMetrics(
        total_grid_kwh=round(total_grid, 4),
        total_cost_bdt=round(total_cost, 4),
        peak_grid_kwh=round(peak_grid, 4),
    )