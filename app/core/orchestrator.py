"""
Pipeline Orchestrator (Member 1 Core Deliverable).
Coordinates the complete end-to-end workflow:
LLM Directives -> Deterministic Guardrails -> Mathematical Optimization -> Verification Replay.
"""

from typing import List
from app.core.schemas import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    HourlyPlanItem,
    RawDirectiveDTO,
    DirectiveInterpretation,
)
from app.llm.interpreter import interpret_operator_notes
from app.guardrails.validator import validate_and_guardrail_directives
from app.optimizer.solver import solve_energy_schedule
from app.core.replayer import replay_and_calculate_metrics


async def orchestrate(request: OptimizeEnergyRequest) -> OptimizeEnergyResponse:
    """
    Orchestrates the 24-hour campus energy scheduling pipeline.

    Workflow:
    1. LLM Semantic Interpretation: Extract structured raw directives from operator notes.
    2. Deterministic Guardrails: Normalize hours, clamp factors, enforce safe fallbacks.
    3. Mathematical Optimization: Solve cost-minimizing LP schedule with HiGHS.
    4. Hourly State Dynamics: Track running battery state of charge (SOC).
    5. Replay Verification: Validate energy balance & end-of-day battery neutrality.
    6. Response Construction: Emit canonical Section 10.1 & 10.2 JSON output.
    """
    notes_count = len(request.operator_notes)

    # 1. Semantic Operator Note Interpretation via LLM (Member 2)
    raw_directives: List[RawDirectiveDTO] = []
    if request.operator_notes:
        try:
            raw_directives = await interpret_operator_notes(
                notes=request.operator_notes,
                scenario_id=request.scenario_id,
            )
        except Exception as e:
            # Resilient fallback: If LLM is unreachable, times out, or missing API key,
            # never crash with HTTP 500. Generate safe no_op fallbacks for every note.
            import logging
            logging.getLogger("gridwise").error("LLM interpretation failed: %s", e, exc_info=True)
            raw_directives = [
                RawDirectiveDTO(
                    note_index=idx,
                    directive_type="no_op",
                    raw_hours=None,
                    raw_numeric_param=None,
                    explanation=f"LLM fallback due to provider error: {str(e)[:100]}",
                    confidence=0.0,
                )
                for idx, note in enumerate(request.operator_notes)
            ]

    # Guarantee complete 0..N-1 indexing per Section 5.1
    existing_indices = {d.note_index for d in raw_directives}
    for idx in range(notes_count):
        if idx not in existing_indices:
            raw_directives.append(
                RawDirectiveDTO(
                    note_index=idx,
                    directive_type="no_op",
                    raw_hours=None,
                    raw_numeric_param=None,
                    explanation=f"No directive extracted for note: '{request.operator_notes[idx]}'",
                    confidence=0.0,
                )
            )
    raw_directives.sort(key=lambda d: d.note_index)

    # 2. Deterministic Guardrails (Member 3)
    validated_directives = validate_and_guardrail_directives(
        raw_directives=raw_directives,
        notes_count=notes_count,
        battery_capacity=request.battery.capacity,
    )

    # 3. Solve 24-hour cost-minimizing schedule with HiGHS LP solver (Member 3)
    solved_schedule, feasible = solve_energy_schedule(
        hours=request.hours,
        battery=request.battery,
        validated_directives=validated_directives,
    )

    # 4. Compute running battery state of charge (SOC) for each hour
    initial_energy = request.battery.initial_soc * request.battery.capacity
    current_soc = initial_energy
    hourly_plan: List[HourlyPlanItem] = []

    for item in solved_schedule:
        if item.action == "charge":
            current_soc += item.battery_charge_kwh
            action_name = "charge"
            action_kwh = item.battery_charge_kwh
        elif item.action == "discharge":
            current_soc -= item.battery_discharge_kwh
            action_name = "discharge"
            action_kwh = item.battery_discharge_kwh
        else:
            action_name = "idle"
            action_kwh = 0.0

        current_soc = max(0.0, min(request.battery.capacity, current_soc))

        hourly_plan.append(
            HourlyPlanItem(
                hour=item.hour,
                grid_kwh=round(item.grid_draw_kwh, 4),
                solar_used_kwh=round(item.solar_kwh, 4),
                battery_action=action_name,
                battery_kwh=round(action_kwh, 4),
                battery_energy_after_kwh=round(current_soc, 4),
            )
        )

    # 5. Replay and calculate verified metrics (Member 1 Replayer)
    metrics = replay_and_calculate_metrics(
        hourly_plan=hourly_plan,
        hours=request.hours,
        initial_energy_kwh=initial_energy,
        battery_capacity=request.battery.capacity,
    )

    # 6. Construct plan summary description
    active_directives = [d.directive_type for d in validated_directives if d.applies]
    summary_suffix = (
        f" Enforced directives: {', '.join(active_directives)}."
        if active_directives
        else " No operational directive constraints active."
    )
    plan_summary = (
        f"Optimized 24h schedule with {metrics.total_grid_kwh:.2f} kWh total grid import "
        f"at {metrics.total_cost_bdt:.2f} BDT cost (peak import {metrics.peak_grid_kwh:.2f} kWh)."
        + summary_suffix
    )

    return OptimizeEnergyResponse(
        scenario_id=request.scenario_id,
        directive_interpretation=validated_directives,
        hourly_plan=hourly_plan,
        total_grid_kwh=round(metrics.total_grid_kwh, 2),
        total_cost_bdt=round(metrics.total_cost_bdt, 2),
        peak_grid_kwh=round(metrics.peak_grid_kwh, 2),
        plan_summary=plan_summary,
    )