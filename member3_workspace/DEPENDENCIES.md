# Member 3: Dependencies & Setup

## Python Packages Required

### Core Dependencies (must be in `requirements.txt`)

```
pydantic>=2.0.0          # Data validation & serialization
scipy>=1.10.0            # Linear programming solver
numpy>=1.24.0            # Numerical computations
highs>=1.5.0             # HiGHS LP/MIP solver (scipy uses this)
```

### Development Dependencies (for testing & linting)

```
pytest>=7.0.0            # Unit testing framework
pytest-cov>=4.0.0        # Code coverage reporting
black>=23.0.0            # Code formatter
flake8>=6.0.0            # Linting
mypy>=1.0.0              # Static type checking
```

---

## Setup Instructions

### 1. Create Virtual Environment

```bash
# Navigate to project root
cd SmartGrid-Optimizer

# Create virtual environment
python -m venv venv

# Activate (choose based on your OS)
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
# Upgrade pip, setuptools, wheel
pip install --upgrade pip setuptools wheel

# Install all dependencies from requirements.txt
pip install -r requirements.txt

# Install dev dependencies (if separate file)
pip install pytest pytest-cov black flake8 mypy
```

### 3. Verify Installation

```bash
# Check scipy + HiGHS
python -c "from scipy.optimize import linprog; print('scipy OK')"
python -c "import highspy; print('HiGHS OK')"

# Check pydantic
python -c "from pydantic import BaseModel; print('pydantic OK')"
```

---

## HiGHS Solver: Quick Test

```python
# test_highs_installation.py
from scipy.optimize import linprog
import numpy as np

# Minimize: x + 2y
# Subject to: 2x + y >= 1

c = [1, 2]  # objective coefficients
A_ub = [[-2, -1]]  # inequality constraints (negated for >=)
b_ub = [-1]

result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method='highs')
print(result)
# Expected: optimal x ≈ 0.5, y ≈ 0
```

---

## Key scipy.optimize Functions You'll Use

### 1. Linear Programming (LP)

```python
from scipy.optimize import linprog

result = linprog(
    c,                          # Objective function coefficients
    A_ub=A_ub,                  # Inequality constraint matrix (Ax <= b)
    b_ub=b_ub,                  # Inequality constraint bounds
    A_eq=A_eq,                  # Equality constraint matrix (Ax = b)
    b_eq=b_eq,                  # Equality constraint bounds
    bounds=bounds,              # Variable bounds (list of (min, max) tuples)
    method='highs',             # Use HiGHS solver
    options={'disp': False}     # Suppress output
)

# Access solution:
if result.success:
    x_optimal = result.x
    obj_value = result.fun
else:
    print(f"Infeasible: {result.message}")
```

### 2. Mixed-Integer Linear Programming (MILP) — Optional

If you need discrete actions, use:

```python
from scipy.optimize import milp, LinearConstraint, Bounds

# Define continuous & integer variables
integrality = np.array([0, 0, 1, 1])  # 1 = integer, 0 = continuous

result = milp(
    c=c,
    constraints=(LinearConstraint(A, lb, ub),),
    bounds=Bounds(lb, ub),
    integrality=integrality,
    options={"time_limit": 0.015}  # 15ms timeout
)
```

---

## Pydantic Models Setup

### Example: Define Your Schema

```python
# app/core/schemas.py (from Member 1, but you reference it)

from pydantic import BaseModel, Field
from typing import Optional
from dataclasses import dataclass

@dataclass
class RawDirectiveDTO:
    """From Member 2's LLM interpreter"""
    note_index: int
    directive_type: str
    raw_hours: Optional[list[int]] = None
    raw_numeric_param: Optional[float] = None
    explanation: str = ""
    confidence: float = 1.0

@dataclass
class DirectiveInterpretation:
    """Output from Member 3's guardrails"""
    note_index: int
    directive_type: str
    hours: list[int]
    factor: float
    applies: bool
    applied_constraint: str
    fallback_reason: Optional[str] = None

@dataclass
class HourlyPlanItem:
    """Output from Member 3's optimizer"""
    hour: int
    action: str  # 'charge', 'discharge', 'idle'
    grid_draw_kwh: float
    battery_discharge_kwh: float
    battery_charge_kwh: float
    solar_kwh: float

class BatterySpec(BaseModel):
    """Battery configuration"""
    capacity: float = Field(..., gt=0)
    initial_soc: float = Field(default=0.5, ge=0, le=1)
    max_charge_rate: float = Field(..., gt=0)
    max_discharge_rate: float = Field(..., gt=0)

class HourData(BaseModel):
    """Hourly scenario data"""
    hour: int = Field(ge=0, le=23)
    solar_generation: float = Field(ge=0)
    demand: float = Field(ge=0)
    grid_price: float = Field(ge=0)
```

---

## Testing Framework Setup

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run only guardrails tests
pytest tests/test_guardrails.py -v

# Run only optimizer tests
pytest tests/test_optimizer.py -v

# With coverage report
pytest tests/ -v --cov=app --cov-report=html
```

### Basic Test Template

```python
# tests/test_guardrails.py

import pytest
from app.guardrails.validator import validate_and_guardrail_directives
from app.core.schemas import RawDirectiveDTO, DirectiveInterpretation

def test_hour_sorting():
    """Hours should be sorted ascending."""
    raw = RawDirectiveDTO(
        note_index=0,
        directive_type='solar_reduction',
        raw_hours=[23, 5, 10],
        raw_numeric_param=0.5,
        confidence=0.9
    )
    
    result = validate_and_guardrail_directives([raw], 1, 50.0)
    
    assert len(result) == 1
    assert result[0].hours == [5, 10, 23]
    assert result[0].applies == True

def test_factor_clamping():
    """Factor should be clamped to [0, 1]."""
    raw = RawDirectiveDTO(
        note_index=0,
        directive_type='solar_reduction',
        raw_hours=[10, 11, 12],
        raw_numeric_param=1.5,
        confidence=0.9
    )
    
    result = validate_and_guardrail_directives([raw], 1, 50.0)
    
    assert result[0].factor == 1.0
```

---

## Code Formatting & Linting

### Format Code with Black

```bash
# Format all Python files in app/
black app/guardrails app/optimizer

# Format specific file
black app/guardrails/validator.py

# Check what would be formatted (dry run)
black --check app/guardrails app/optimizer
```

### Check for Linting Issues

```bash
# Flake8: Check style, logic errors
flake8 app/guardrails app/optimizer tests/

# MyPy: Static type checking
mypy app/guardrails app/optimizer --ignore-missing-imports
```

---

## Performance Profiling

### Measure Solver Latency

```python
# scripts/profile_solver.py

import time
import numpy as np
from app.optimizer.solver import solve_energy_schedule
from app.core.schemas import HourData, BatterySpec, DirectiveInterpretation

# Generate 24 random hours
hours = [
    HourData(
        hour=h,
        solar_generation=np.random.uniform(0, 20),
        demand=np.random.uniform(5, 15),
        grid_price=0.05
    )
    for h in range(24)
]

battery = BatterySpec(
    capacity=50.0,
    initial_soc=0.5,
    max_charge_rate=10.0,
    max_discharge_rate=10.0
)

# Profile solver time
times = []
for _ in range(100):
    start = time.time()
    schedule, feasible = solve_energy_schedule(hours, battery, [])
    elapsed = (time.time() - start) * 1000  # milliseconds
    times.append(elapsed)

print(f"Mean: {np.mean(times):.2f}ms")
print(f"P95:  {np.percentile(times, 95):.2f}ms")
print(f"Max:  {np.max(times):.2f}ms")
# Expected: all < 15ms
```

Run it:
```bash
python scripts/profile_solver.py
```

---

## Troubleshooting

### Issue: HiGHS not installed

```
ModuleNotFoundError: No module named 'highspy'
```

**Solution:**
```bash
pip install --upgrade scipy
pip install highs
```

### Issue: Pydantic validation error

```
ValidationError: 1 validation error for HourlyPlanItem
  hour: less than minimum of 0
```

**Solution:** Check that hour values are in [0, 23] before creating the object.

### Issue: LP problem infeasible

```
HiGHS Simplex... Status : "MODEL_EMPTY" or "PRIMAL_INFEASIBLE"
```

**Solution:** 
- Log the constraint matrix and bounds
- Check for conflicting constraints (e.g., min reserve > capacity)
- Relax non-critical constraints

### Issue: Solver timeout

```
Solution time limit reached: solution not found.
```

**Solution:**
- Increase timeout in solver options (if > 15ms is acceptable)
- Simplify problem (fewer constraints, relax bounds)
- Use continuous variables instead of integer

---

## Environment Variables (.env)

Create `.env.example` (Member 4 responsibility, but reference it):

```
# .env.example
GEMINI_API_KEY=your-api-key-here
BATTERY_CAPACITY=50.0
MAX_CHARGE_RATE=10.0
MAX_DISCHARGE_RATE=10.0
GRID_PRICE_MULTIPLIER=1.0
LOG_LEVEL=INFO
```

In your code, load it:
```python
from dotenv import load_dotenv
import os

load_dotenv()
battery_capacity = float(os.getenv('BATTERY_CAPACITY', 50.0))
```

---

## CI/CD Considerations (For Member 4)

Your tests should pass in Docker:

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run tests
RUN pytest tests/ -v --tb=short

# Start application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Run locally:
```bash
docker build -t smartgrid-optimizer .
docker run smartgrid-optimizer
```

---

## Summary Checklist

- [ ] Python 3.10+ installed
- [ ] Virtual environment created and activated
- [ ] `requirements.txt` includes scipy, pydantic, highs
- [ ] `pip install -r requirements.txt` succeeds
- [ ] `pytest` can discover tests
- [ ] `black` and `flake8` installed
- [ ] Can import scipy.optimize.linprog
- [ ] Can import pydantic models
- [ ] Ready to start implementing guardrails and optimizer!

---

**Created**: 2026-09-18  
**Member**: 3 (Guardrails & Optimizer Lead)  
**Status**: Setup verified, ready to code
