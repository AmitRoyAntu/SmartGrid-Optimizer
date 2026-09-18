"""
LP Solver: Solves the energy optimization problem.

This module takes the LP formulation from model.py, solves it using
scipy.optimize.linprog with HiGHS backend, and extracts the solution
into HourlyPlanItem format.
"""

import time
from typing import List, Tuple
from scipy.optimize import linprog

from app.core.schemas import (
    HourData,
    BatterySpec,
    DirectiveInterpretation,
    HourlyPlanItem,
    SOLVER_TIMEOUT_MS,
)
from app.optimizer.model import setup_lp_problem


def solve_energy_schedule(
    hours: List[HourData],
    battery: BatterySpec,
    validated_directives: List[DirectiveInterpretation],
) -> Tuple[List[HourlyPlanItem], bool]:
    """
    Solves the energy optimization LP problem.

    Applies directive constraints and solves the LP to generate a cost-minimizing
    24-hour energy schedule while respecting all physical constraints.

    Args:
        hours: 24 HourData objects with solar, demand, grid_price
        battery: BatterySpec with capacity, charge/discharge rates
        validated_directives: Validated DirectiveInterpretation list from guardrails

    Returns:
        (schedule: list of 24 HourlyPlanItem, feasible: bool)

    Constraints enforced:
    - Energy balance: grid + solar + discharge = demand + charge
    - Battery bounds: 0 <= SOC <= capacity
    - Rate limits: charge/discharge <= max rates
    - End-of-day neutrality: SOC[23] = SOC[0]
    - Directives: solar reductions, windows, reserves, etc.
    """
    start_time = time.time()

    try:
        # === Set up LP problem ===
        c, A_ub, b_ub, A_eq, b_eq, bounds = setup_lp_problem(
            hours, battery, validated_directives
        )

        # === Solve LP ===
        result = linprog(
            c,
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
            options={"disp": False, "time_limit": SOLVER_TIMEOUT_MS / 1000.0},
        )

        # === Check if feasible ===
        if not result.success:
            # Infeasible: return empty schedule and False
            empty_schedule = [
                HourlyPlanItem(
                    hour=h,
                    action="idle",
                    grid_draw_kwh=0.0,
                    battery_discharge_kwh=0.0,
                    battery_charge_kwh=0.0,
                    solar_kwh=hours[h].solar_generation,
                )
                for h in range(24)
            ]
            return empty_schedule, False

        # === Extract solution ===
        x_opt = result.x
        schedule = []

        for h in range(24):
            grid_draw = x_opt[3 * h + 0]
            charge = x_opt[3 * h + 1]
            discharge = x_opt[3 * h + 2]

            # Determine action
            if charge > 0.01:
                action = "charge"
            elif discharge > 0.01:
                action = "discharge"
            else:
                action = "idle"

            # Apply solar reductions from directives
            solar = hours[h].solar_generation
            for directive in validated_directives:
                if (
                    directive.applies
                    and directive.directive_type == "solar_reduction"
                    and h in directive.hours
                ):
                    solar *= 1.0 - directive.factor

            item = HourlyPlanItem(
                hour=h,
                action=action,
                grid_draw_kwh=max(0.0, grid_draw),
                battery_discharge_kwh=max(0.0, discharge),
                battery_charge_kwh=max(0.0, charge),
                solar_kwh=max(0.0, solar),
            )
            schedule.append(item)

        return schedule, True

    except Exception:
        # Error during solving: return empty schedule and False
        empty_schedule = [
            HourlyPlanItem(
                hour=h,
                action="idle",
                grid_draw_kwh=0.0,
                battery_discharge_kwh=0.0,
                battery_charge_kwh=0.0,
                solar_kwh=hours[h].solar_generation,
            )
            for h in range(24)
        ]
        return empty_schedule, False
