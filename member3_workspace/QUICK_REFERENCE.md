# Member 3 Quick Reference Guide

## 🚀 Current Status
- **Branch**: `feature/member3-guardrails-optimizer` ✅ Created and active
- **Workspace**: `member3_workspace/` ✅ Ready
- **Plan Document**: `MEMBER3_IMPLEMENTATION_PLAN.md` ✅ Comprehensive guide ready

---

## 📌 What You Need to Do (Member 3)

### Your Core Responsibility
Implement **Guardrails** (validation) and **Optimizer** (LP solver) modules that:
1. **Accept** validated LLM directives from Member 2
2. **Validate** them deterministically (sort hours, clamp factors, enforce rules)
3. **Solve** a linear programming problem to generate a 24-hour energy schedule
4. **Return** the schedule to Member 1 for API response

---

## 🎯 Your 3 Main Deliverables

### 1. **Guardrails Validator** (`app/guardrails/validator.py`)
```python
def validate_and_guardrail_directives(
    raw_directives: list[RawDirectiveDTO],
    notes_count: int,
    battery_capacity: float
) -> list[DirectiveInterpretation]:
    # Your implementation here
```

**What it does:**
- Takes unvalidated directives from Member 2's LLM
- Clamps hours to [0..23], sorts them, removes duplicates
- Clamps factors to [0.0, 1.0]
- Validates battery reserves don't exceed capacity
- Never crashes — falls back gracefully to `no_op`

---

### 2. **Optimizer Model** (`app/optimizer/model.py`)
Define the LP formulation:
- **Minimize** total grid cost over 24 hours
- **Variables**: Grid draw, battery charge/discharge, battery SOC per hour
- **Constraints**: Energy balance, battery bounds, rate limits, end-of-day neutrality

---

### 3. **Optimizer Solver** (`app/optimizer/solver.py`)
```python
def solve_energy_schedule(
    hours: list[HourData],
    battery: BatterySpec,
    validated_directives: list[DirectiveInterpretation]
) -> tuple[list[HourlyPlanItem], bool]:
    # Your implementation here
```

**What it does:**
- Applies directive constraints (solar reductions, charge windows, etc.)
- Solves the LP problem using scipy + HiGHS solver
- Returns 24 hourly actions: charge, discharge, or idle
- Should complete in < 15ms

---

## 📊 Input → Output Flow

```
Member 2 (LLM)
    ↓
[RawDirectiveDTO] ← unvalidated, raw
    ↓
YOUR GUARDRAILS VALIDATOR
    ↓
[DirectiveInterpretation] ← validated, safe
    ↓
YOUR OPTIMIZER SOLVER
    ↓
[HourlyPlanItem] × 24 ← schedule
    ↓
Member 1 (Replayer & API)
```

---

## 🔑 Key Constraints to Implement

### Energy Balance (Every Hour)
```
Grid + Solar + Discharge = Demand + Charge
```

### Battery Bounds
```
0 ≤ Battery[h] ≤ Capacity
Battery[h] = Battery[h-1] + Charge[h] - Discharge[h]
Battery[23] = Battery[0]  (End-of-day neutrality)
```

### Directive Enforcement
- **`solar_reduction`**: Reduce solar by factor for specified hours
- **`minimum_battery_reserve`**: Enforce minimum battery level
- **`no_charge_window`**: Prohibit charging in specified hours
- **`no_discharge_window`**: Prohibit discharging in specified hours
- **`max_grid_window`**: Cap grid draw in specified hours
- **`no_op`**: No constraint

---

## 📁 Files You'll Create/Edit

```
app/guardrails/
├── __init__.py
└── validator.py              ← Core logic

app/optimizer/
├── __init__.py
├── model.py                  ← LP formulation
└── solver.py                 ← Constraint application & solving

tests/
├── test_guardrails.py        ← Unit tests for validator
└── test_optimizer.py         ← Unit tests for solver
```

---

## ⏰ Your Timeline (4 Hours Total)

| Time | What to Do |
|------|-----------|
| **Hour 1** | Create skeletons, define all Pydantic schemas, write test stubs |
| **Hour 2** | Implement guardrails validation + LP solver with constraints |
| **Hour 3** | Integration testing, verify energy balance & battery neutrality |
| **Hour 4** | Performance tuning, edge case handling, final verification |

---

## ✅ Verification Checklist

Before each hour, verify:

- [ ] **Guardrails tests pass**: `pytest tests/test_guardrails.py -v`
- [ ] **Optimizer tests pass**: `pytest tests/test_optimizer.py -v`
- [ ] **Energy balance tolerance ≤ 0.01 kWh** (tested hour-by-hour)
- [ ] **Battery neutrality holds**: `battery[23] == battery[0]`
- [ ] **Solver latency < 15ms** (measured across 100+ runs)
- [ ] **No crashes on edge cases** (empty directives, extreme values, etc.)
- [ ] **All code formatted**: `black app/guardrails app/optimizer`
- [ ] **No linting errors**: `flake8 app/guardrails app/optimizer`

---

## 🔗 Interfaces Between Members

### What You **Receive** from Member 2
`RawDirectiveDTO` with:
- `note_index` — which operator note (0, 1, or 2)
- `directive_type` — one of 6 types
- `raw_hours` — list of hours (may have errors)
- `raw_numeric_param` — factor/value (may be out of bounds)
- `confidence` — LLM confidence score [0.0, 1.0]

### What You **Provide** to Member 1
`DirectiveInterpretation` with:
- `note_index`, `directive_type` (validated)
- `hours` — sorted, deduplicated, clipped to [0..23]
- `factor` — clamped to [0.0, 1.0]
- `applies` — whether constraint is actually enforced
- `fallback_reason` — why it fell back (if applicable)

And `HourlyPlanItem` × 24:
- `hour`, `action` (charge/discharge/idle)
- `grid_draw_kwh`, `battery_charge_kwh`, `battery_discharge_kwh`
- `solar_kwh` (after any reductions)

---

## 💻 Command Reference

```bash
# Switch to your branch
git checkout feature/member3-guardrails-optimizer

# Run tests frequently
pytest tests/test_guardrails.py tests/test_optimizer.py -v

# Format code
black app/guardrails app/optimizer tests/test_guardrails.py tests/test_optimizer.py

# Check for linting issues
flake8 app/guardrails app/optimizer tests/

# Commit your work
git add app/guardrails app/optimizer tests/test_guardrails.py tests/test_optimizer.py
git commit -m "Member 3: [brief description] - [checkpoint]"
git push -u origin feature/member3-guardrails-optimizer
```

---

## 📚 Reference Documents

1. **Full Implementation Plan**: `member3_workspace/MEMBER3_IMPLEMENTATION_PLAN.md`
2. **Problem Statement**: `BUP_CSE_FEST_2026_Preliminary_Problem_Statement_GridWise_LLM.pdf`
3. **Evaluation Rubric**: `BUP_CSE_FEST_2026_Participant_Guide_&_Evaluation_Rubric_GridWise_LLM.pdf`
4. **Architecture**: `implementation_plan.md` (root directory)

---

## 🎓 Key Concepts

- **Linear Programming (LP)**: Optimization technique to minimize cost subject to constraints
- **HiGHS Solver**: Fast, reliable LP solver integrated with scipy.optimize
- **Energy Balance**: Fundamental physics constraint — energy in = energy out
- **Battery Neutrality**: End-of-day battery level must equal start-of-day level
- **Deterministic Validation**: Guardrails never crash; always return valid output

---

## 💡 Pro Tips

1. **Test-Driven Development**: Write tests first, implement to pass them
2. **Mock Data**: Create realistic test data for all 6 directive types
3. **Profile Early**: Measure solver performance immediately; optimize if > 15ms
4. **Log Extensively**: Print debug info for guardrails decisions and LP problem structure
5. **Edge Cases**: Test with empty directives, out-of-range values, conflicting constraints
6. **Collaborate**: Coordinate with Member 1 on schema changes ASAP

---

## 🆘 If You Get Stuck

1. **Guardrails crashing?** → Add try-except, return graceful fallback
2. **LP problem infeasible?** → Check constraint conflicts; relax non-critical constraints
3. **Solver too slow?** → Profile; consider sparse matrices or problem simplification
4. **Energy balance fails?** → Verify constraint formulation; check sign conventions
5. **Integration fails?** → Log all inputs/outputs; compare with Member 1's replayer logic

---

## 📞 Coordination Checklist

- [ ] Confirm Member 2's `RawDirectiveDTO` schema with Member 1
- [ ] Confirm Member 1's `DirectiveInterpretation` and `HourlyPlanItem` schemas
- [ ] Verify scipy + HiGHS dependencies in `requirements.txt`
- [ ] Agree on tolerance levels (energy balance ≤ 0.01 kWh, etc.)
- [ ] Test integration with Member 1's orchestrator by end of Hour 3
- [ ] Final checklist with Member 4 before submission

---

**Ready to start? Begin with Hour 1 scaffolding in the main plan document.** ✅

---

*Created: 2026-09-18*  
*Branch: `feature/member3-guardrails-optimizer`*  
*Status: Ready for Implementation*
