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
                assert abs(inflow - outflow) < 0.1, f"Hour {h}: imbalance {inflow - outflow}"


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

        valid_actions = {'charge', 'discharge', 'idle'}
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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
