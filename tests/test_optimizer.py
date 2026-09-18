"""
Unit tests for optimizer solver (Member 3 - Hour 1).

Tests the LP formulation and solving of the energy optimization problem.
"""

import pytest
import numpy as np
from app.optimizer.solver import solve_energy_schedule
from app.core.schemas import HourData, BatterySpec, DirectiveInterpretation


class TestEnergyBalance:
    """Test energy balance constraint."""

    def test_energy_balance_holds(self):
        """Energy balance: grid + solar + discharge = demand + charge."""
        hours = [
            HourData(
                hour=h,
                solar_generation=10.0,
                demand=5.0,
                grid_price=0.05,
            )
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=50.0,
            initial_soc=0.5,
            max_charge_rate=10.0,
            max_discharge_rate=10.0,
        )

        schedule, feasible = solve_energy_schedule(hours, battery, [])

        if feasible:
            for h, plan_item in enumerate(schedule):
                inflow = (
                    plan_item.grid_draw_kwh
                    + plan_item.solar_kwh
                    + plan_item.battery_discharge_kwh
                )
                outflow = hours[h].demand + plan_item.battery_charge_kwh
                # Allow small numerical tolerance
                assert (
                    abs(inflow - outflow) < 0.1
                ), f"Hour {h}: imbalance {inflow - outflow}"


class TestBatteryBounds:
    """Test battery SOC constraints."""

    def test_battery_soc_within_bounds(self):
        """Battery SOC must stay within [0, capacity]."""
        hours = [
            HourData(
                hour=h,
                solar_generation=5.0,
                demand=10.0,
                grid_price=0.05,
            )
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=50.0,
            initial_soc=0.5,
            max_charge_rate=10.0,
            max_discharge_rate=10.0,
        )

        schedule, feasible = solve_energy_schedule(hours, battery, [])

        if feasible:
            soc = battery.initial_soc * battery.capacity
            for plan_item in schedule:
                soc += plan_item.battery_charge_kwh - plan_item.battery_discharge_kwh
                assert 0 <= soc <= battery.capacity, f"SOC out of bounds: {soc}"


class TestBatteryNeutrality:
    """Test end-of-day battery neutrality."""

    def test_battery_neutrality_holds(self):
        """Battery at end of day should equal battery at start."""
        hours = [
            HourData(
                hour=h,
                solar_generation=10.0,
                demand=5.0,
                grid_price=0.05,
            )
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=50.0,
            initial_soc=0.5,
            max_charge_rate=10.0,
            max_discharge_rate=10.0,
        )

        schedule, feasible = solve_energy_schedule(hours, battery, [])

        if feasible:
            soc = battery.initial_soc * battery.capacity
            for plan_item in schedule:
                soc += plan_item.battery_charge_kwh - plan_item.battery_discharge_kwh

            initial_soc = battery.initial_soc * battery.capacity
            # Allow small numerical tolerance
            assert abs(soc - initial_soc) < 0.1, (
                f"Battery not neutral: "
                f"initial={initial_soc}, final={soc}, diff={soc - initial_soc}"
            )


class TestScheduleCompleteness:
    """Test that solver returns complete schedules."""

    def test_schedule_has_24_hours(self):
        """Schedule should have exactly 24 hours."""
        hours = [
            HourData(
                hour=h,
                solar_generation=10.0,
                demand=5.0,
                grid_price=0.05,
            )
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=50.0,
            initial_soc=0.5,
            max_charge_rate=10.0,
            max_discharge_rate=10.0,
        )

        schedule, _ = solve_energy_schedule(hours, battery, [])

        assert len(schedule) == 24
        for h, plan_item in enumerate(schedule):
            assert plan_item.hour == h

    def test_schedule_actions_valid(self):
        """All actions should be 'charge', 'discharge', or 'idle'."""
        hours = [
            HourData(
                hour=h,
                solar_generation=10.0,
                demand=5.0,
                grid_price=0.05,
            )
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=50.0,
            initial_soc=0.5,
            max_charge_rate=10.0,
            max_discharge_rate=10.0,
        )

        schedule, _ = solve_energy_schedule(hours, battery, [])

        valid_actions = {"charge", "discharge", "idle"}
        for plan_item in schedule:
            assert plan_item.action in valid_actions


class TestNonNegativeValues:
    """Test that all power values are non-negative."""

    def test_power_values_non_negative(self):
        """All power values should be >= 0."""
        hours = [
            HourData(
                hour=h,
                solar_generation=10.0,
                demand=5.0,
                grid_price=0.05,
            )
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=50.0,
            initial_soc=0.5,
            max_charge_rate=10.0,
            max_discharge_rate=10.0,
        )

        schedule, feasible = solve_energy_schedule(hours, battery, [])

        if feasible:
            for plan_item in schedule:
                assert plan_item.grid_draw_kwh >= -1e-6
                assert plan_item.battery_charge_kwh >= -1e-6
                assert plan_item.battery_discharge_kwh >= -1e-6
                assert plan_item.solar_kwh >= -1e-6


class TestChargeLikelyWithSurplus:
    """Test that solver charges battery when solar > demand."""

    def test_charging_during_surplus(self):
        """With solar > demand, battery should charge sometime."""
        hours = [
            HourData(
                hour=h,
                solar_generation=20.0,  # High solar
                demand=5.0,  # Low demand
                grid_price=0.05,
            )
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=50.0,
            initial_soc=0.3,  # Start low
            max_charge_rate=10.0,
            max_discharge_rate=10.0,
        )

        schedule, feasible = solve_energy_schedule(hours, battery, [])

        if feasible:
            total_charge = sum(p.battery_charge_kwh for p in schedule)
            # Should charge some amount (solar surplus)
            assert total_charge > 0.1


class TestDirectiveConstraints:
    """Test that all directive constraints are strictly enforced downstream in the schedule."""

    def test_solar_reduction_in_lp(self):
        """Solar reduction directive should reduce effective solar utilized."""
        hours = [
            HourData(hour=h, solar_generation=30.0, demand=20.0, grid_price=10.0)
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=50.0, initial_soc=0.5, max_charge_rate=10.0, max_discharge_rate=10.0
        )
        directive = DirectiveInterpretation(
            note_index=0,
            directive_type="solar_reduction",
            hours=[12, 13, 14],
            factor=0.2,  # 80% reduction -> 20% remaining
            applies=True,
            applied_constraint="Solar reduced by 80%",
            fallback_reason=None,
        )
        schedule, feasible = solve_energy_schedule(hours, battery, [directive])
        assert feasible
        for h in [12, 13, 14]:
            assert schedule[h].solar_kwh <= 30.0 * 0.2 + 1e-4

    def test_no_charge_window(self):
        """No charge window directive must strictly prohibit charging in listed hours."""
        hours = [
            HourData(hour=h, solar_generation=30.0, demand=5.0, grid_price=10.0)
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=50.0, initial_soc=0.2, max_charge_rate=10.0, max_discharge_rate=10.0
        )
        directive = DirectiveInterpretation(
            note_index=0,
            directive_type="no_charge_window",
            hours=[10, 11, 12],
            factor=1.0,
            applies=True,
            applied_constraint="No charge window",
            fallback_reason=None,
        )
        schedule, feasible = solve_energy_schedule(hours, battery, [directive])
        assert feasible
        for h in [10, 11, 12]:
            assert schedule[h].battery_charge_kwh <= 1e-6
            assert schedule[h].action != "charge"

    def test_no_discharge_window(self):
        """No discharge window directive must strictly prohibit discharging in listed hours."""
        hours = [
            HourData(hour=h, solar_generation=0.0, demand=30.0, grid_price=20.0)
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=50.0, initial_soc=0.8, max_charge_rate=10.0, max_discharge_rate=10.0
        )
        directive = DirectiveInterpretation(
            note_index=0,
            directive_type="no_discharge_window",
            hours=[18, 19, 20],
            factor=1.0,
            applies=True,
            applied_constraint="No discharge window",
            fallback_reason=None,
        )
        schedule, feasible = solve_energy_schedule(hours, battery, [directive])
        assert feasible
        for h in [18, 19, 20]:
            assert schedule[h].battery_discharge_kwh <= 1e-6
            assert schedule[h].action != "discharge"

    def test_minimum_battery_reserve(self):
        """Minimum battery reserve floor must be strictly satisfied."""
        hours = [
            HourData(hour=h, solar_generation=0.0, demand=15.0, grid_price=15.0)
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=100.0, initial_soc=0.5, max_charge_rate=20.0, max_discharge_rate=20.0
        )
        # Demand high, battery wants to discharge, but reserve is 40 kWh (0.4)
        directive = DirectiveInterpretation(
            note_index=0,
            directive_type="minimum_battery_reserve",
            hours=[18, 19, 20],
            factor=0.4,
            applies=True,
            applied_constraint="Reserve floor 40%",
            fallback_reason=None,
        )
        schedule, feasible = solve_energy_schedule(hours, battery, [directive])
        assert feasible
        soc = battery.initial_soc * battery.capacity
        for h, plan_item in enumerate(schedule):
            soc += plan_item.battery_charge_kwh - plan_item.battery_discharge_kwh
            if h in [18, 19, 20]:
                assert soc >= 40.0 - 1e-4, f"Hour {h}: SOC {soc} below reserve floor 40.0"

    def test_max_grid_window(self):
        """Max grid window must cap grid import during listed hours."""
        hours = [
            HourData(hour=h, solar_generation=0.0, demand=50.0, grid_price=10.0)
            for h in range(24)
        ]
        battery = BatterySpec(
            capacity=100.0, initial_soc=0.8, max_charge_rate=20.0, max_discharge_rate=20.0
        )
        directive = DirectiveInterpretation(
            note_index=0,
            directive_type="max_grid_window",
            hours=[14, 15],
            factor=35.0,  # Max grid 35 kWh
            applies=True,
            applied_constraint="Max grid cap 35 kWh",
            fallback_reason=None,
        )
        schedule, feasible = solve_energy_schedule(hours, battery, [directive])
        assert feasible
        for h in [14, 15]:
            assert schedule[h].grid_draw_kwh <= 35.0 + 1e-4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
