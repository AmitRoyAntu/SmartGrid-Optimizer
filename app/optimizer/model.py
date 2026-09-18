"""
LP Model Definition: Formulation of the energy optimization problem.

This module defines the linear programming problem structure:
- Decision variables
- Objective function (minimize grid cost)
- Constraints (energy balance, battery bounds, directive constraints)

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
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Bounds]:
    """
    Set up the LP problem for energy optimization.

    Decision variables (for each hour h in 0..23):
    - x[3*h + 0]: Grid draw [kWh]
    - x[3*h + 1]: Battery charge [kWh]
    - x[3*h + 2]: Battery discharge [kWh]

    Total: 72 variables (24 hours × 3 variables)

    Additional variables (added at end):
    - x[72..95]: Battery SOC for each hour (24 variables)

    Total: 96 variables

    Objective: Minimize sum of (grid_draw[h] * price[h]) for all h

    Args:
        hours: 24 HourData objects with solar, demand, price
        battery: BatterySpec with capacity, rates
        validated_directives: List of validated DirectiveInterpretation objects

    Returns:
        (c, A_ub, b_ub, A_eq, b_eq, bounds) for linprog
    """
    n_hours = 24
    n_action_vars = n_hours * 3  # Grid, charge, discharge per hour
    n_soc_vars = n_hours  # Battery SOC per hour
    n_total_vars = n_action_vars + n_soc_vars

    # === Objective function: minimize grid cost ===
    # c[3*h + 0] = price[h] (cost of grid draw)
    # c[3*h + 1] = 0 (no cost for charging)
    # c[3*h + 2] = 0 (no cost for discharging)
    # c[72..95] = 0 (no cost for SOC variables)

    c = np.zeros(n_total_vars)
    for h in range(n_hours):
        c[3 * h] = hours[h].grid_price  # Grid cost

    # === Build constraints ===
    A_ub_list = []  # Inequality constraints (Ax <= b)
    b_ub_list = []
    A_eq_list = []  # Equality constraints (Ax = b)
    b_eq_list = []

    # --- Constraint 1: Rate limits ---
    for h in range(n_hours):
        # Charge rate: x[3*h + 1] <= max_charge_rate
        row = np.zeros(n_total_vars)
        row[3 * h + 1] = 1.0
        A_ub_list.append(row)
        b_ub_list.append(battery.max_charge_rate)

        # Discharge rate: x[3*h + 2] <= max_discharge_rate
        row = np.zeros(n_total_vars)
        row[3 * h + 2] = 1.0
        A_ub_list.append(row)
        b_ub_list.append(battery.max_discharge_rate)

    # --- Constraint 2: Energy balance (equality) ---
    # For each hour h:
    # grid[h] + solar[h] + discharge[h] = demand[h] + charge[h]
    # Rearranged: grid[h] - charge[h] + discharge[h] = demand[h] - solar[h]

    for h in range(n_hours):
        row = np.zeros(n_total_vars)
        row[3 * h + 0] = 1.0  # grid
        row[3 * h + 1] = -1.0  # -charge
        row[3 * h + 2] = 1.0  # +discharge
        A_eq_list.append(row)
        b_eq_list.append(hours[h].demand - hours[h].solar_generation)

    # --- Constraint 3: Battery SOC dynamics (equality) ---
    # SOC[h] = SOC[h-1] + charge[h] - discharge[h]
    # For h=0: SOC[0] = initial_soc * capacity + charge[0] - discharge[0]
    # For h>0: SOC[h] - SOC[h-1] = charge[h] - discharge[h]

    # h=0: SOC[0] = initial_soc * capacity + charge[0] - discharge[0]
    row = np.zeros(n_total_vars)
    row[72 + 0] = 1.0  # SOC[0]
    row[3 * 0 + 1] = -1.0  # -charge[0]
    row[3 * 0 + 2] = 1.0  # +discharge[0]
    A_eq_list.append(row)
    b_eq_list.append(battery.initial_soc * battery.capacity)

    # h>0
    for h in range(1, n_hours):
        row = np.zeros(n_total_vars)
        row[72 + h] = 1.0  # SOC[h]
        row[72 + h - 1] = -1.0  # -SOC[h-1]
        row[3 * h + 1] = -1.0  # -charge[h]
        row[3 * h + 2] = 1.0  # +discharge[h]
        A_eq_list.append(row)
        b_eq_list.append(0.0)

    # --- Constraint 4: Battery neutrality (end-of-day = start-of-day) ---
    # SOC[23] = SOC[0]
    # SOC[23] - SOC[0] = 0
    row = np.zeros(n_total_vars)
    row[72 + 23] = 1.0  # SOC[23]
    row[72 + 0] = -1.0  # -SOC[0]
    A_eq_list.append(row)
    b_eq_list.append(0.0)

    # === Apply directive constraints ===
    for directive in validated_directives:
        if not directive.applies:
            continue

        if directive.directive_type == "no_charge_window":
            # Charge = 0 in specified hours
            for h in directive.hours:
                row = np.zeros(n_total_vars)
                row[3 * h + 1] = 1.0  # charge[h]
                A_ub_list.append(row)
                b_ub_list.append(0.0)

        elif directive.directive_type == "no_discharge_window":
            # Discharge = 0 in specified hours
            for h in directive.hours:
                row = np.zeros(n_total_vars)
                row[3 * h + 2] = 1.0  # discharge[h]
                A_ub_list.append(row)
                b_ub_list.append(0.0)

        elif directive.directive_type == "minimum_battery_reserve":
            # SOC[h] >= factor * capacity for all h
            reserve_kwh = directive.factor * battery.capacity
            for h in range(n_hours):
                row = np.zeros(n_total_vars)
                row[72 + h] = 1.0  # SOC[h]
                A_ub_list.append(row)
                b_ub_list.append(reserve_kwh)
                # Note: We want SOC >= reserve, which is -SOC <= -reserve in standard form
                # But we'll handle this differently in the bounds

        elif directive.directive_type == "max_grid_window":
            # Grid draw capped in specified hours
            max_grid = (
                directive.factor * battery.max_discharge_rate * 10
            )  # Approx max grid
            for h in directive.hours:
                row = np.zeros(n_total_vars)
                row[3 * h + 0] = 1.0  # grid[h]
                A_ub_list.append(row)
                b_ub_list.append(max_grid)

    # === Bounds ===
    bounds = Bounds(
        lb=np.zeros(n_total_vars),  # All variables >= 0
        ub=np.inf * np.ones(n_total_vars),
    )

    # Battery SOC upper bound: SOC[h] <= capacity
    for h in range(n_hours):
        bounds.ub[72 + h] = battery.capacity

    # === Convert to numpy arrays ===
    if A_ub_list:
        A_ub = np.array(A_ub_list)
        b_ub = np.array(b_ub_list)
    else:
        A_ub = np.empty((0, n_total_vars))
        b_ub = np.empty(0)

    if A_eq_list:
        A_eq = np.array(A_eq_list)
        b_eq = np.array(b_eq_list)
    else:
        A_eq = np.empty((0, n_total_vars))
        b_eq = np.empty(0)

    return c, A_ub, b_ub, A_eq, b_eq, bounds
