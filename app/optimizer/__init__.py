"""
Optimizer module: Linear programming solver for energy schedule optimization.

This module formulates and solves the LP problem to generate a cost-minimized
24-hour energy schedule that respects all constraints and directives.
"""

from .solver import solve_energy_schedule

__all__ = ['solve_energy_schedule']
