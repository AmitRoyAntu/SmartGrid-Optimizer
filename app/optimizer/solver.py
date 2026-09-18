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
    - Energy balance: grid + solar_used + discharge = demand + charge
    - Battery bounds: 0 <= SOC <= capacity
    - Rate limits: charge/discharge <= max rates
    - End-of-day neutrality: SOC[23] = initial_energy
    - Directives: solar reductions, windows, reserves, grid caps
    """
    try:
        # === Set up LP problem ===
        c, A_ub, b_ub, A_eq, b_eq, bounds, effective_solar = setup_lp_problem(
            hours, battery, validated_directives
        )

        # === Solve LP using HiGHS ===
        result = linprog(
            c,
            A_ub=A_ub if A_ub.size > 0 else None,
            b_ub=b_ub if b_ub.size > 0 else None,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
            options={"disp": False, "time_limit": max(0.05, SOLVER_TIMEOUT_MS / 1000.0)},
        )

        # === Check if feasible ===
        if not result.success:
            # Fallback on infeasibility: fulfill demand directly from grid
            fallback_schedule = [
                HourlyPlanItem(
                    hour=h,
                    action="idle",
                    grid_draw_kwh=max(0.0, hours[h].demand - effective_solar[h]),
                    battery_discharge_kwh=0.0,
                    battery_charge_kwh=0.0,
                    solar_kwh=min(hours[h].demand, effective_solar[h]),
                )
                for h in range(24)
            ]
            return fallback_schedule, False

        # === Extract solution ===
        x_opt = result.x
        schedule = []

        for h in range(24):
            grid_draw = x_opt[4 * h + 0]
            charge = x_opt[4 * h + 1]
            discharge = x_opt[4 * h + 2]
            curtailment = x_opt[4 * h + 3]

            # Determine discrete action
            if charge > 0.001:
                action = "charge"
                discharge = 0.0  # Guarantee mutual exclusivity
            elif discharge > 0.001:
                action = "discharge"
                charge = 0.0
            else:
                action = "idle"
                charge = 0.0
                discharge = 0.0

            solar_used = max(0.0, effective_solar[h] - curtailment)

            item = HourlyPlanItem(
                hour=h,
                action=action,
                grid_draw_kwh=max(0.0, float(grid_draw)),
                battery_discharge_kwh=max(0.0, float(discharge)),
                battery_charge_kwh=max(0.0, float(charge)),
                solar_kwh=max(0.0, float(solar_used)),
            )
            schedule.append(item)

        return schedule, True

    except Exception:
        # Catch-all: Never crash, return safe idle schedule
        fallback_schedule = [
            HourlyPlanItem(
                hour=h,
                action="idle",
                grid_draw_kwh=max(0.0, hours[h].demand - hours[h].solar_generation),
                battery_discharge_kwh=0.0,
                battery_charge_kwh=0.0,
                solar_kwh=min(hours[h].demand, hours[h].solar_generation),
            )
            for h in range(24)
        ]
        return fallback_schedule, False
