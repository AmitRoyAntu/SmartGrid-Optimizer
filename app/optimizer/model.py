"""
LP Model Definition: Formulation of the energy optimization problem.

This module defines the linear programming problem structure:
- Decision variables (grid draw, charge, discharge, solar curtailment, SOC)
- Objective function (minimize grid cost)
- Constraints (energy balance, battery dynamics, battery neutrality, directive constraints)

The problem is set up here; actual solving happens in solver.py.
"""

import numpy as np
from typing import Tuple, List
from scipy.optimize import Bounds

from app.core.schemas import HourData, BatterySpec, DirectiveInterpretation


def setup_lp_problem(
    hours: List[HourData],
    battery: BatterySpec,
    validated_directives: List[DirectiveInterpretation],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, Bounds, List[float]]:
    """
    Set up the LP problem for energy optimization.

    Decision variables (for each hour h in 0..23):
    - x[4*h + 0]: Grid draw [kWh]
    - x[4*h + 1]: Battery charge [kWh]
    - x[4*h + 2]: Battery discharge [kWh]
    - x[4*h + 3]: Solar curtailed [kWh] (excess solar when generation > demand + charge)

    Total action/curtailment variables: 96 variables (24 hours × 4 variables)

    Additional variables (added at end):
    - x[96..119]: Battery SOC for each hour (24 variables)

    Total: 120 variables

    Objective: Minimize sum of (grid_draw[h] * price[h]) for all h

    Args:
        hours: 24 HourData objects with solar, demand, price
        battery: BatterySpec with capacity, rates
        validated_directives: List of validated DirectiveInterpretation objects

    Returns:
        (c, A_ub, b_ub, A_eq, b_eq, bounds, effective_solar) for linprog
    """
    n_hours = 24
    n_vars_per_hour = 4
    n_action_vars = n_hours * n_vars_per_hour  # 96 variables
    soc_offset = n_action_vars  # Index 96
    n_total_vars = n_action_vars + n_hours  # 120 variables

    initial_energy = battery.initial_soc * battery.capacity

    # === Pre-calculate effective solar incorporating solar_reduction directives ===
    effective_solar = [float(hours[h].solar_generation) for h in range(n_hours)]
    for directive in validated_directives:
        if directive.applies and directive.directive_type == "solar_reduction":
            for h in directive.hours:
                effective_solar[h] = hours[h].solar_generation * directive.factor

    # === Objective function: minimize grid electricity cost ===
    # c[4*h + 0] = price[h] (cost of grid draw)
    # c[4*h + 1] = 0 (charging)
    # c[4*h + 2] = 0 (discharging)
    # c[4*h + 3] = 0 (curtailment of free solar)
    # c[soc_offset + h] = 0 (SOC)
    c = np.zeros(n_total_vars)
    for h in range(n_hours):
        c[n_vars_per_hour * h + 0] = hours[h].grid_price

    # === Build constraints ===
    A_ub_list = []  # Inequality constraints (Ax <= b)
    b_ub_list = []
    A_eq_list = []  # Equality constraints (Ax = b)
    b_eq_list = []

    # === Equality Constraint 1: Energy balance for each hour ===
    # grid[h] + (effective_solar[h] - curtailment[h]) + discharge[h] = demand[h] + charge[h]
    # Rearranged: grid[h] - charge[h] + discharge[h] - curtailment[h] = demand[h] - effective_solar[h]
    for h in range(n_hours):
        row = np.zeros(n_total_vars)
        row[n_vars_per_hour * h + 0] = 1.0   # +grid
        row[n_vars_per_hour * h + 1] = -1.0  # -charge
        row[n_vars_per_hour * h + 2] = 1.0   # +discharge
        row[n_vars_per_hour * h + 3] = -1.0  # -curtailment
        A_eq_list.append(row)
        b_eq_list.append(hours[h].demand - effective_solar[h])

    # === Equality Constraint 2: Battery SOC dynamics ===
    # h = 0: SOC[0] - charge[0] + discharge[0] = initial_energy
    row0 = np.zeros(n_total_vars)
    row0[soc_offset + 0] = 1.0
    row0[n_vars_per_hour * 0 + 1] = -1.0  # -charge[0]
    row0[n_vars_per_hour * 0 + 2] = 1.0   # +discharge[0]
    A_eq_list.append(row0)
    b_eq_list.append(initial_energy)

    # h > 0: SOC[h] - SOC[h-1] - charge[h] + discharge[h] = 0
    for h in range(1, n_hours):
        row = np.zeros(n_total_vars)
        row[soc_offset + h] = 1.0
        row[soc_offset + h - 1] = -1.0
        row[n_vars_per_hour * h + 1] = -1.0  # -charge[h]
        row[n_vars_per_hour * h + 2] = 1.0   # +discharge[h]
        A_eq_list.append(row)
        b_eq_list.append(0.0)

    # === Equality Constraint 3: End-of-day battery neutrality ===
    # Problem Statement Section 9.6: final battery_energy_after_kwh = initial_energy_kwh
    # SOC[23] = initial_energy
    row_neutral = np.zeros(n_total_vars)
    row_neutral[soc_offset + 23] = 1.0
    A_eq_list.append(row_neutral)
    b_eq_list.append(initial_energy)

    # === Variable Bounds ===
    lb = np.zeros(n_total_vars)
    ub = np.inf * np.ones(n_total_vars)

    for h in range(n_hours):
        # Charge rate limit
        ub[n_vars_per_hour * h + 1] = battery.max_charge_rate
        # Discharge rate limit
        ub[n_vars_per_hour * h + 2] = battery.max_discharge_rate
        # Curtailment bound: can at most curtail available effective solar
        ub[n_vars_per_hour * h + 3] = max(0.0, effective_solar[h])
        # Battery capacity bound
        ub[soc_offset + h] = battery.capacity

    # === Apply directive constraints directly to bounds and inequalities ===
    for directive in validated_directives:
        if not directive.applies:
            continue

        if directive.directive_type == "no_charge_window":
            # Prohibit charging during listed hours
            for h in directive.hours:
                ub[n_vars_per_hour * h + 1] = 0.0

        elif directive.directive_type == "no_discharge_window":
            # Prohibit discharging during listed hours
            for h in directive.hours:
                ub[n_vars_per_hour * h + 2] = 0.0

        elif directive.directive_type == "minimum_battery_reserve":
            # Enforce minimum battery reserve floor
            target_hours = directive.hours if directive.hours else list(range(n_hours))
            reserve_kwh = (
                directive.factor
                if directive.factor > 1.0
                else directive.factor * battery.capacity
            )
            for h in target_hours:
                lb[soc_offset + h] = max(lb[soc_offset + h], reserve_kwh)

        elif directive.directive_type == "max_grid_window":
            # Enforce maximum grid import limit
            target_hours = directive.hours if directive.hours else list(range(n_hours))
            max_grid = (
                directive.factor
                if directive.factor > 1.0
                else directive.factor * (battery.max_discharge_rate * 10)
            )
            for h in target_hours:
                ub[n_vars_per_hour * h + 0] = min(ub[n_vars_per_hour * h + 0], max_grid)

    bounds = [(float(lb[i]), float(ub[i])) for i in range(n_total_vars)]

    # Convert lists to NumPy arrays
    A_ub = np.array(A_ub_list) if A_ub_list else np.empty((0, n_total_vars))
    b_ub = np.array(b_ub_list) if b_ub_list else np.empty(0)
    A_eq = np.array(A_eq_list)
    b_eq = np.array(b_eq_list)

    return c, A_ub, b_ub, A_eq, b_eq, bounds, effective_solar
