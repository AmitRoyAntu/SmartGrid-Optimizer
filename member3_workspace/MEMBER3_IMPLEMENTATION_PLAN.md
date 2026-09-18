# Member 3: Guardrails & Optimizer Implementation Plan
## GridWise LLM Smart Campus Energy Optimization Service

**Team Member**: Member 3  
**Role**: Guardrails & Optimizer Lead  
**Modules**: `app/guardrails/` & `app/optimizer/`  
**Project Timeline**: 4 hours total  
**Current Date**: 2026-09-18

---

## 📋 Member 3 Scope & Responsibilities

Member 3 is responsible for **deterministic validation** (guardrails) and **mathematical optimization** (LP solver) that transform LLM directives into a cost-minimizing 24-hour energy schedule.

### Primary Deliverables
1. **`app/guardrails/validator.py`** — Deterministic validation & normalization
2. **`app/optimizer/model.py`** — HiGHS LP formulation
3. **`app/optimizer/solver.py`** — Constraint applicator & schedule generator
4. **`tests/test_guardrails.py`** — Guardrail unit tests
5. **`tests/test_optimizer.py`** — Optimizer unit tests

---

## 🔌 What Member 3 Receives from Member 2 (LLM)

### Input Contract: `RawDirectiveDTO` (from Member 2)
Member 2 produces a list of **raw, unvalidated directive objects** after LLM interpretation:

```python
@dataclass
class RawDirectiveDTO:
    note_index: int                    # Which operator note (0, 1, or 2)
    directive_type: str                # One of: 'solar_reduction', 'minimum_battery_reserve', 
                                       # 'no_charge_window', 'no_discharge_window', 
                                       # 'max_grid_window', 'no_op'
    raw_hours: list[int] | None        # e.g., [13, 14, 15] or None if not applicable
    raw_numeric_param: float | None    # e.g., 0.5 for 50% solar reduction
    explanation: str                   # Human-readable summary for debugging
    confidence: float                  # [0.0, 1.0] LLM confidence score
```

### Example Input from Member 2:
```python
[
    RawDirectiveDTO(
        note_index=0,
        directive_type='solar_reduction',
        raw_hours=[10, 11, 12],
        raw_numeric_param=0.3,
        explanation="Reduce solar generation by 30% during hours 10-12",
        confidence=0.95
    ),
    RawDirectiveDTO(
        note_index=1,
        directive_type='no_charge_window',
        raw_hours=[14, 15, 16, 17],
        raw_numeric_param=None,
        explanation="Do not charge battery during 2 PM to 4 PM",
        confidence=0.88
    )
]
```

---

## 🎯 What Member 3 Must Deliver to Member 1 (API)

### Output Contract: `DirectiveInterpretation` (to Member 1)

After validation & normalization, Member 3 produces a **deterministic, safe directive list**:

```python
@dataclass
class DirectiveInterpretation:
    note_index: int                    # Original note index
    directive_type: str                # Validated type
    hours: list[int]                   # Sorted, deduplicated, clipped to [0..23]
    factor: float                      # Clamped to [0.0, 1.0]
    applies: bool                      # True if valid & applicable
    applied_constraint: str            # Description of what the optimizer will enforce
    fallback_reason: str | None        # If None, directive was accepted; else reason it fell back
```

### Example Output from Member 3:
```python
[
    DirectiveInterpretation(
        note_index=0,
        directive_type='solar_reduction',
        hours=[10, 11, 12],
        factor=0.3,
        applies=True,
        applied_constraint="Solar generation reduced by 30% in hours [10, 11, 12]",
        fallback_reason=None
    ),
    DirectiveInterpretation(
        note_index=1,
        directive_type='no_charge_window',
        hours=[14, 15, 16, 17],
        factor=1.0,  # Not used for windows, but present for schema uniformity
        applies=True,
        applied_constraint="Battery charging prohibited in hours [14, 15, 16, 17]",
        fallback_reason=None
    )
]
```

### Optimizer Output Contract: `HourlyPlanItem` (to Member 1)

Member 3's optimizer returns 24 scheduled actions:

```python
@dataclass
class HourlyPlanItem:
    hour: int                          # 0..23
    action: str                        # 'charge', 'discharge', or 'idle'
    grid_draw_kwh: float               # Non-negative: power drawn from grid
    battery_discharge_kwh: float       # Non-negative: power discharged from battery
    battery_charge_kwh: float          # Non-negative: power to charge battery
    solar_kwh: float                   # Non-negative: solar generation (after reductions)
```

---

## 🛡️ Member 3 Guardrails Implementation

### Module: `app/guardrails/validator.py`

**Function Signature:**
```python
def validate_and_guardrail_directives(
    raw_directives: list[RawDirectiveDTO],
    notes_count: int,
    battery_capacity: float
) -> list[DirectiveInterpretation]:
    """
    Validates and normalizes raw LLM directives.
    Never crashes; falls back gracefully to no_op on invalid input.
    
    Args:
        raw_directives: List of unvalidated directives from Member 2
        notes_count: Total number of operator notes (1-3)
        battery_capacity: Battery capacity in kWh (e.g., 50.0)
    
    Returns:
        List of validated DirectiveInterpretation objects
    """
```

### Guardrail Rules (Hard Enforcement)

1. **Hour Validation & Normalization**
   - Clamp `raw_hours` to `[0, 23]`
   - Sort ascending
   - Remove duplicates
   - If result is empty, set `applies=False`

2. **Factor Clamping**
   - Clamp `raw_numeric_param` to `[0.0, 1.0]`
   - Treat `None` as neutral (e.g., `1.0` for reductions, `0.0` for reserves)

3. **Battery Reserve Validation**
   - Reserve level must not exceed `battery_capacity`
   - Reserve must be non-negative
   - If invalid, fall back to `no_op`

4. **Directive Type Filtering**
   - Accept only: `solar_reduction`, `minimum_battery_reserve`, `no_charge_window`, `no_discharge_window`, `max_grid_window`, `no_op`
   - Reject unknown types → set `applies=False`

5. **Distractor Detection**
   - If LLM confidence < 0.5 (low confidence), treat as `no_op`
   - Log reason in `fallback_reason` field

6. **Safe Fallback**
   - Never raise exceptions; always return a valid list
   - On any parsing error, create a `no_op` directive with `applies=False` and clear reason

### Pseudo-Code for `validator.py`:
```python
def validate_and_guardrail_directives(raw_directives, notes_count, battery_capacity):
    validated = []
    
    for raw_dir in raw_directives:
        # Start with defaults
        result = DirectiveInterpretation(
            note_index=raw_dir.note_index,
            directive_type=raw_dir.directive_type,
            hours=[],
            factor=1.0,
            applies=False,
            applied_constraint="",
            fallback_reason=None
        )
        
        # 1. Validate directive type
        if raw_dir.directive_type not in VALID_TYPES:
            result.fallback_reason = f"Unknown directive type: {raw_dir.directive_type}"
            validated.append(result)
            continue
        
        # 2. Validate hours
        if raw_dir.raw_hours:
            hours = sorted(set(h for h in raw_dir.raw_hours if 0 <= h <= 23))
            result.hours = hours
        
        # 3. Clamp factor
        if raw_dir.raw_numeric_param is not None:
            result.factor = max(0.0, min(1.0, raw_dir.raw_numeric_param))
        
        # 4. Confidence check
        if raw_dir.confidence < 0.5:
            result.fallback_reason = f"Low confidence score: {raw_dir.confidence}"
            validated.append(result)
            continue
        
        # 5. Type-specific validation
        if raw_dir.directive_type == 'minimum_battery_reserve':
            reserve_kwh = result.factor * battery_capacity
            if reserve_kwh > battery_capacity or reserve_kwh < 0:
                result.fallback_reason = f"Battery reserve {reserve_kwh} exceeds capacity {battery_capacity}"
                validated.append(result)
                continue
        
        # 6. Mark as valid and set constraint description
        result.applies = True
        result.applied_constraint = _describe_constraint(raw_dir.directive_type, result)
        
        validated.append(result)
    
    return validated
```

---

## ⚙️ Member 3 Optimizer Implementation

### Module: `app/optimizer/model.py` — LP Formulation

**Objective:** Minimize total grid energy cost over 24 hours while respecting physical constraints and directives.

**Decision Variables (per hour h ∈ [0, 23]):**
- `G[h]` — Grid draw (kWh)
- `C[h]` — Battery charge (kWh)
- `D[h]` — Battery discharge (kWh)
- `B[h]` — Battery state of charge (kWh)

**Objective Function:**
```
Minimize: Σ_h (G[h] × price[h])
```
where `price[h]` is the electricity price at hour h.

**Physical Constraints:**

1. **Energy Balance (hourly):**
   ```
   G[h] + solar[h] + D[h] = demand[h] + C[h]  ∀h
   ```

2. **Battery Bounds:**
   ```
   0 ≤ B[h] ≤ battery_capacity  ∀h
   B[h] = B[h-1] + C[h] - D[h]  ∀h
   B[0] = battery_initial (often 50% capacity)
   B[23] = B[0] (end-of-day neutrality)
   ```

3. **Charge/Discharge Rate Limits:**
   ```
   0 ≤ C[h] ≤ max_charge_rate  ∀h
   0 ≤ D[h] ≤ max_discharge_rate  ∀h
   C[h] × D[h] = 0  (cannot charge and discharge simultaneously)
   ```

4. **Directive Constraints (applied from Member 3 guardrails):**
   - `solar_reduction`: `solar_adjusted[h] = solar[h] × (1 - factor)` for specified hours
   - `minimum_battery_reserve`: `B[h] ≥ factor × battery_capacity` for all h
   - `no_charge_window`: `C[h] = 0` for specified hours
   - `no_discharge_window`: `D[h] = 0` for specified hours
   - `max_grid_window`: `G[h] ≤ factor × max_grid_power` for specified hours
   - `no_op`: No constraint applied

### Module: `app/optimizer/solver.py` — Constraint Applicator & Solver

**Function Signature:**
```python
def solve_energy_schedule(
    hours: list[HourData],
    battery: BatterySpec,
    validated_directives: list[DirectiveInterpretation]
) -> tuple[list[HourlyPlanItem], bool]:
    """
    Applies directive constraints and solves the LP problem.
    
    Args:
        hours: 24 HourData objects with solar, demand, and price
        battery: BatterySpec with capacity, charge/discharge rates
        validated_directives: Validated directives from Member 3 guardrails
    
    Returns:
        (schedule: list of 24 HourlyPlanItem, feasible: bool)
    """
```

**Pseudo-Code:**
```python
def solve_energy_schedule(hours, battery, validated_directives):
    import numpy as np
    from scipy.optimize import linprog
    
    # 1. Initialize LP problem using HiGHS solver
    problem = define_lp_problem(hours, battery)
    
    # 2. Apply constraints from each validated directive
    for directive in validated_directives:
        if not directive.applies:
            continue
        
        if directive.directive_type == 'solar_reduction':
            # Reduce solar generation for specified hours
            for h in directive.hours:
                hours[h].solar_generation *= (1 - directive.factor)
        
        elif directive.directive_type == 'minimum_battery_reserve':
            # Enforce minimum battery level
            reserve_kwh = directive.factor * battery.capacity
            for h in range(24):
                problem.add_constraint(battery_soc[h] >= reserve_kwh)
        
        elif directive.directive_type == 'no_charge_window':
            # Block charging in specified hours
            for h in directive.hours:
                problem.add_constraint(charge[h] == 0)
        
        elif directive.directive_type == 'no_discharge_window':
            # Block discharging in specified hours
            for h in directive.hours:
                problem.add_constraint(discharge[h] == 0)
        
        elif directive.directive_type == 'max_grid_window':
            # Cap grid draw in specified hours
            max_grid = directive.factor * battery.max_grid_power
            for h in directive.hours:
                problem.add_constraint(grid_draw[h] <= max_grid)
    
    # 3. Solve the LP problem
    result = problem.solve(solver='highs')
    
    # 4. Extract solution and convert to HourlyPlanItem list
    schedule = []
    for h in range(24):
        action = classify_action(charge[h], discharge[h])
        schedule.append(HourlyPlanItem(
            hour=h,
            action=action,
            grid_draw_kwh=grid_draw[h],
            battery_discharge_kwh=discharge[h],
            battery_charge_kwh=charge[h],
            solar_kwh=hours[h].solar_generation
        ))
    
    return schedule, result.is_feasible()
```

---

## ✅ Member 3 Testing Checklist

### `tests/test_guardrails.py`

```python
# Test cases to implement:

def test_hour_sorting_and_dedup():
    """Hours should be sorted and deduplicated."""
    raw = RawDirectiveDTO(..., raw_hours=[23, 10, 10, 5])
    result = validate_and_guardrail_directives([raw], 1, 50.0)
    assert result[0].hours == [5, 10, 23]

def test_hour_clamping_to_0_23():
    """Hours outside [0, 23] should be dropped."""
    raw = RawDirectiveDTO(..., raw_hours=[-1, 5, 25, 12])
    result = validate_and_guardrail_directives([raw], 1, 50.0)
    assert result[0].hours == [5, 12]

def test_factor_clamping_to_0_1():
    """Factor should be clamped to [0.0, 1.0]."""
    raw = RawDirectiveDTO(..., raw_numeric_param=1.5)
    result = validate_and_guardrail_directives([raw], 1, 50.0)
    assert result[0].factor == 1.0
    
    raw = RawDirectiveDTO(..., raw_numeric_param=-0.3)
    result = validate_and_guardrail_directives([raw], 1, 50.0)
    assert result[0].factor == 0.0

def test_battery_reserve_validation():
    """Reserve should not exceed capacity."""
    raw = RawDirectiveDTO(..., directive_type='minimum_battery_reserve', 
                          raw_numeric_param=1.2, raw_hours=None)
    result = validate_and_guardrail_directives([raw], 1, 50.0)
    assert result[0].applies == False  # Falls back because 1.2 × 50 = 60 > 50

def test_low_confidence_fallback():
    """Directives with confidence < 0.5 should fall back to no_op."""
    raw = RawDirectiveDTO(..., confidence=0.3)
    result = validate_and_guardrail_directives([raw], 1, 50.0)
    assert result[0].applies == False
    assert "Low confidence" in result[0].fallback_reason

def test_unknown_directive_type():
    """Unknown directive types should be rejected."""
    raw = RawDirectiveDTO(..., directive_type='invalid_type')
    result = validate_and_guardrail_directives([raw], 1, 50.0)
    assert result[0].applies == False

def test_no_crashes_on_null_inputs():
    """Validator should never crash, even on None inputs."""
    result = validate_and_guardrail_directives([], 0, 0.0)
    assert isinstance(result, list)
```

### `tests/test_optimizer.py`

```python
# Test cases to implement:

def test_energy_balance_constraint():
    """Energy balance: grid + solar + discharge = demand + charge."""
    hours = [HourData(solar=10, demand=5, price=0.05) for _ in range(24)]
    battery = BatterySpec(capacity=50, max_charge_rate=10, max_discharge_rate=10)
    schedule, feasible = solve_energy_schedule(hours, battery, [])
    
    for i, plan in enumerate(schedule):
        inflow = plan.grid_draw_kwh + plan.solar_kwh + plan.battery_discharge_kwh
        outflow = hours[i].demand + plan.battery_charge_kwh
        assert abs(inflow - outflow) < 0.01, f"Hour {i}: imbalance {inflow - outflow}"

def test_battery_bounds():
    """Battery SOC must stay within [0, capacity]."""
    hours = [HourData(solar=5, demand=10, price=0.05) for _ in range(24)]
    battery = BatterySpec(capacity=50, max_charge_rate=10, max_discharge_rate=10)
    schedule, feasible = solve_energy_schedule(hours, battery, [])
    
    soc = battery.initial_soc
    for plan in schedule:
        soc += plan.battery_charge_kwh - plan.battery_discharge_kwh
        assert 0 <= soc <= battery.capacity, f"SOC out of bounds: {soc}"

def test_end_of_day_neutrality():
    """Battery at end of day should equal battery at start."""
    hours = [HourData(solar=10, demand=5, price=0.05) for _ in range(24)]
    battery = BatterySpec(capacity=50, initial_soc=25, max_charge_rate=10, max_discharge_rate=10)
    schedule, feasible = solve_energy_schedule(hours, battery, [])
    
    soc = battery.initial_soc
    for plan in schedule:
        soc += plan.battery_charge_kwh - plan.battery_discharge_kwh
    
    assert abs(soc - battery.initial_soc) < 0.01, f"End SOC {soc} != Start {battery.initial_soc}"

def test_no_charge_window_directive():
    """During no_charge_window, battery_charge_kwh should be 0."""
    hours = [HourData(solar=20, demand=5, price=0.05) for _ in range(24)]
    battery = BatterySpec(capacity=50, max_charge_rate=10, max_discharge_rate=10)
    directive = DirectiveInterpretation(
        note_index=0,
        directive_type='no_charge_window',
        hours=[10, 11, 12],
        factor=1.0,
        applies=True,
        applied_constraint="No charging 10-12"
    )
    schedule, feasible = solve_energy_schedule(hours, battery, [directive])
    
    for h in [10, 11, 12]:
        assert schedule[h].battery_charge_kwh == 0, f"Hour {h} charged despite no_charge_window"

def test_solar_reduction_directive():
    """Solar should be reduced by the specified factor."""
    hours = [HourData(solar=100, demand=5, price=0.05) for _ in range(24)]
    battery = BatterySpec(capacity=50, max_charge_rate=10, max_discharge_rate=10)
    directive = DirectiveInterpretation(
        note_index=0,
        directive_type='solar_reduction',
        hours=[6, 7, 8, 9, 10, 11],
        factor=0.3,
        applies=True,
        applied_constraint="Reduce solar by 30% (6-11)"
    )
    schedule, feasible = solve_energy_schedule(hours, battery, [directive])
    
    for h in [6, 7, 8, 9, 10, 11]:
        expected_solar = 100 * (1 - 0.3)
        assert schedule[h].solar_kwh == expected_solar, f"Hour {h}: solar not reduced"

def test_solve_time_under_15ms():
    """Solver should complete within 15ms."""
    import time
    hours = [HourData(solar=random(), demand=random(), price=0.05) for _ in range(24)]
    battery = BatterySpec(capacity=50, max_charge_rate=10, max_discharge_rate=10)
    
    start = time.time()
    schedule, feasible = solve_energy_schedule(hours, battery, [])
    elapsed = (time.time() - start) * 1000  # ms
    
    assert elapsed < 15, f"Solver took {elapsed}ms (max 15ms)"
```

---

## 📂 File Structure & Directory Layout

Member 3 will create/edit:

```
app/
├── guardrails/
│   ├── __init__.py
│   └── validator.py              ← Member 3: Main guardrails logic
│
└── optimizer/
    ├── __init__.py
    ├── model.py                  ← Member 3: LP formulation & solver setup
    └── solver.py                 ← Member 3: Constraint application & solving

tests/
├── test_guardrails.py            ← Member 3: Unit tests for guardrails
└── test_optimizer.py             ← Member 3: Unit tests for optimizer

member3_workspace/                ← This folder for planning & notes
├── MEMBER3_IMPLEMENTATION_PLAN.md (this file)
├── DEPENDENCIES.md               ← Python packages needed
├── INTERFACE_CONTRACTS.md        ← Detailed input/output specs
└── NOTES.md                      ← Scratch notes during implementation
```

---

## 🔗 Integration Points: Who Calls Member 3?

### Member 1 → Member 3 (Orchestrator → Guardrails & Optimizer)

Member 1's `core/orchestrator.py` calls Member 3's functions:

```python
# Step 1: Validate LLM directives using guardrails
from app.guardrails.validator import validate_and_guardrail_directives

validated_directives = validate_and_guardrail_directives(
    raw_directives_from_member2,
    notes_count=len(operator_notes),
    battery_capacity=scenario.battery.capacity
)

# Step 2: Solve the optimization problem
from app.optimizer.solver import solve_energy_schedule

hourly_schedule, is_feasible = solve_energy_schedule(
    hours=scenario.hourly_data,
    battery=scenario.battery,
    validated_directives=validated_directives
)

# Step 3: Verify the schedule (done by Member 1's replayer)
metrics = replay_and_calculate_metrics(
    hourly_plan=hourly_schedule,
    hours=scenario.hourly_data,
    battery=scenario.battery,
    directives=validated_directives
)
```

---

## 🎯 Implementation Timeline (Member 3)

### **Hour 1 (0:00 – 1:00): Scaffolding & Contract Freezing**
- [ ] Create `app/guardrails/__init__.py` and `app/optimizer/__init__.py`
- [ ] Define all Pydantic schemas (`RawDirectiveDTO`, `DirectiveInterpretation`, `HourlyPlanItem`, `BatterySpec`, `HourData`)
- [ ] Write skeleton `validator.py` with function signatures
- [ ] Write skeleton `solver.py` with LP problem initialization
- [ ] Write skeleton tests in `test_guardrails.py` and `test_optimizer.py`
- [ ] **Deliverable**: Interfaces are locked; Member 1 & 2 can proceed without blocking

### **Hour 2 (1:00 – 2:00): Core Module Completion**
- [ ] Implement guardrails logic: hour sorting, factor clamping, validation rules
- [ ] Implement directive-specific guardrail checks
- [ ] Set up LP model using `scipy.optimize` + HiGHS solver
- [ ] Implement constraint application from directives
- [ ] Add constraint enforcement (energy balance, battery bounds, etc.)
- [ ] **Deliverable**: Both modules functional; unit tests passing

### **Hour 3 (2:00 – 3:00): Integration & End-to-End Testing**
- [ ] Wire Member 3 into Member 1's orchestrator
- [ ] Run integration tests with real Member 2 LLM output
- [ ] Verify numeric tolerance (energy balance ≤ 0.01 kWh)
- [ ] Verify battery neutrality (B[23] = B[0])
- [ ] Measure solver latency (should be < 15ms)
- [ ] **Deliverable**: All tests passing; ready for end-to-end API testing

### **Hour 4 (3:00 – 4:00): Final Verification & Polish**
- [ ] Verify no crashes on edge cases (empty directives, extreme values, etc.)
- [ ] Check test coverage for guardrails and optimizer
- [ ] Performance profiling and optimization if needed
- [ ] Final checklist before submission
- [ ] **Deliverable**: Ready for deployment

---

## 📋 Member 3 Pre-Implementation Checklist

Before starting, ensure:

- [ ] Git branch `feature/member3-guardrails-optimizer` created locally
- [ ] Project dependencies installed (`requirements.txt` ready from Member 4)
- [ ] Understand the 6 directive types and their constraints
- [ ] Have scipy, numpy, and HiGHS solver available
- [ ] Read Member 1's API schema and Member 2's LLM output format
- [ ] Set up IDE with Python 3.10+ virtual environment
- [ ] Familiarize yourself with the problem statement PDFs (energy grid optimization)

---

## 🚀 Quick Start Commands

```bash
# Clone & setup (if not already done)
git clone <repo-url>
cd SmartGrid-Optimizer
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Switch to Member 3 branch
git checkout feature/member3-guardrails-optimizer

# Create directories
mkdir -p app/guardrails app/optimizer

# Run tests frequently
pytest tests/test_guardrails.py -v
pytest tests/test_optimizer.py -v

# Check linting
flake8 app/guardrails app/optimizer
mypy app/guardrails app/optimizer --ignore-missing-imports

# Commit regularly
git add app/guardrails app/optimizer tests/test_guardrails.py tests/test_optimizer.py
git commit -m "Member 3: Implement guardrails & optimizer - [checkpoint name]"
```

---

## 📞 Coordination Notes

### From Member 2 (LLM)
- **Provides**: `RawDirectiveDTO` list with directive type, hours, factor, confidence
- **Expects**: Graceful handling of edge cases (None values, confidence scores, unknown types)
- **Success Criteria**: No crashes; fallback to `no_op` on malformed input

### To Member 1 (Orchestrator)
- **Provides**: `DirectiveInterpretation` list and `HourlyPlanItem` schedule
- **Expects**: Replayer will validate energy balance and battery neutrality
- **Success Criteria**: Numeric tolerance ≤ 0.01 kWh; all actions labeled correctly

### With Member 4 (DevOps)
- **Receives**: `requirements.txt` with all dependencies pinned
- **Provides**: Test results for validation scripts
- **Success Criteria**: All tests pass in Docker container

---

## 🔍 Key References

1. **Problem Statement**: `BUP_CSE_FEST_2026_Preliminary_Problem_Statement_GridWise_LLM.pdf`
   - Section 04: Energy directives
   - Section 08: Validation rules

2. **Implementation Plan**: `implementation_plan.md` (root)
   - Section on internal contracts
   - Member 3 deliverables & verification checklist

3. **Schemas**: Member 1's `core/schemas.py`
   - All Pydantic models
   - Request/response DTOs

4. **Tests**: `tests/` directory
   - Sample test cases and payloads

---

## 💡 Tips for Success

1. **Start with guardrails first** — it's simpler and unblocks the optimizer
2. **Write tests as you go** — TDD helps catch edge cases early
3. **Use scipy's `linprog` with HiGHS** — well-tested, reliable, fast
4. **Profile frequently** — solver latency is critical (< 15ms target)
5. **Log everything** — helps debugging when Member 1 integrates
6. **Commit small, often** — makes code review easier for the team

---

## ❓ FAQ

**Q: What if the LP problem is infeasible?**  
A: Return `(schedule, False)` and let Member 1's replayer handle it. Log the reason.

**Q: How do I handle multiple directives of the same type?**  
A: Validate independently; Member 1's orchestrator may combine them (union of hours, or maximum factor).

**Q: What if a directive's hours are empty after validation?**  
A: Set `applies=False` and note the reason. Don't crash.

**Q: Should I use integer or continuous variables?**  
A: Continuous for power (kWh). Action labels ('charge', 'discharge', 'idle') are post-hoc based on positive charges/discharges.

**Q: How do I test without Member 2's real LLM output?**  
A: Use mock `RawDirectiveDTO` objects in unit tests. Member 4 provides sample payloads.

---

## 📝 Sign-Off Checklist (Before Submitting)

- [ ] All functions have docstrings
- [ ] All tests pass: `pytest tests/test_guardrails.py tests/test_optimizer.py -v`
- [ ] Code formatted: `black app/guardrails app/optimizer`
- [ ] No linting errors: `flake8 app/guardrails app/optimizer`
- [ ] Solver latency < 15ms (measured with 100+ runs)
- [ ] Energy balance tolerance ≤ 0.01 kWh
- [ ] Battery neutrality verified
- [ ] All edge cases handled (no crashes)
- [ ] Commits are clean and well-messaged
- [ ] Code reviewed by Member 1
- [ ] Ready to merge into `main`

---

**Last Updated**: 2026-09-18  
**Author**: Member 3 Coordinator  
**Status**: Ready for Implementation
