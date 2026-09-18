#!/usr/bin/env python3
"""
Performance Profiling Script for HiGHS LP Solver (Member 3 - Hour 2).

Profiles 100 randomized scenarios with varying solar, demand, prices, and directives
to measure solver latency and verify the p95 <= 15ms target.
"""

import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from app.optimizer.solver import solve_energy_schedule
from app.core.schemas import HourData, BatterySpec, DirectiveInterpretation


def profile():
    np.random.seed(42)
    battery = BatterySpec(
        capacity=100.0,
        initial_soc=0.5,
        max_charge_rate=25.0,
        max_discharge_rate=25.0,
    )

    directives_pool = [
        DirectiveInterpretation(
            note_index=0,
            directive_type="solar_reduction",
            hours=[11, 12, 13, 14],
            factor=0.3,
            applies=True,
            applied_constraint="Solar reduction",
            fallback_reason=None,
        ),
        DirectiveInterpretation(
            note_index=1,
            directive_type="no_charge_window",
            hours=[13, 14, 15],
            factor=1.0,
            applies=True,
            applied_constraint="No charge window",
            fallback_reason=None,
        ),
        DirectiveInterpretation(
            note_index=2,
            directive_type="minimum_battery_reserve",
            hours=[18, 19, 20, 21],
            factor=0.4,
            applies=True,
            applied_constraint="Minimum reserve",
            fallback_reason=None,
        ),
        DirectiveInterpretation(
            note_index=3,
            directive_type="max_grid_window",
            hours=[17, 18, 19],
            factor=50.0,
            applies=True,
            applied_constraint="Max grid cap",
            fallback_reason=None,
        ),
    ]

    latencies_ms = []
    num_scenarios = 100

    print(f"🚀 Profiling LP solver across {num_scenarios} randomized scenarios...")

    for i in range(num_scenarios):
        # Generate varied 24-hour profile
        hours = [
            HourData(
                hour=h,
                solar_generation=float(np.random.uniform(0, 40) if 6 <= h <= 17 else 0.0),
                demand=float(np.random.uniform(10, 35)),
                grid_price=float(np.random.uniform(6.0, 15.0)),
            )
            for h in range(24)
        ]

        # Select subset of directives for this run
        sample_size = np.random.randint(0, len(directives_pool) + 1)
        active_directives = list(np.random.choice(directives_pool, size=sample_size, replace=False))

        t0 = time.perf_counter()
        schedule, feasible = solve_energy_schedule(hours, battery, active_directives)
        t1 = time.perf_counter()

        elapsed_ms = (t1 - t0) * 1000.0
        latencies_ms.append(elapsed_ms)

    latencies = np.array(latencies_ms)
    p50 = np.percentile(latencies, 50)
    p90 = np.percentile(latencies, 90)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    mean = np.mean(latencies)
    max_lat = np.max(latencies)

    print("\n" + "=" * 50)
    print("📊 SOLVER PERFORMANCE RESULTS (HiGHS LP)")
    print("=" * 50)
    print(f"Total Scenarios Tested : {num_scenarios}")
    print(f"Mean Latency           : {mean:.2f} ms")
    print(f"Median (P50)           : {p50:.2f} ms")
    print(f"P90 Latency            : {p90:.2f} ms")
    print(f"P95 Latency            : {p95:.2f} ms")
    print(f"P99 Latency            : {p99:.2f} ms")
    print(f"Max Latency            : {max_lat:.2f} ms")
    print("=" * 50)

    if p95 <= 15.0:
        print("✅ PASS: P95 latency is within the <= 15ms target!")
    else:
        print("⚠️ WARN: P95 latency exceeded the 15ms target.")


if __name__ == "__main__":
    profile()
