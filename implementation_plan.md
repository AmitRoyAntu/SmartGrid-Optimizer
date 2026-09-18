# Modular Monolithic Implementation Plan & 4-Member Team Division

### Project: GridWise LLM Smart Campus Energy Optimization Service
**Challenge**: BUP CSE Fest 2026 Hackathon (Preliminary Round)  
**Architecture**: **Modular Monolith** (Clean separation of concerns with well-defined internal interfaces, running as a single, ultra-fast deployable unit)

---

## 🏛️ Modular Monolithic Architecture

A modular monolith keeps all code in a single repository and deployment artifact, but enforces strict module boundaries so that each team member can work independently without merge conflicts or overlapping concerns.

```
BUP-Hackathon/
├── app/
│   ├── __init__.py
│   ├── main.py                     # [Member 1] Application entrypoint & HTTP routes
│   ├── config.py                   # [Member 4] Environment settings & configuration
│   │
│   ├── core/                       # [Member 1] Orchestration, Contracts & Replayer
│   │   ├── __init__.py
│   │   ├── schemas.py              # Pydantic V2 models for requests, responses & internal DTOs
│   │   ├── orchestrator.py         # End-to-end pipeline workflow coordinator
│   │   └── replayer.py             # Independent hour-by-hour simulator & validator
│   │
│   ├── llm/                        # [Member 2] Semantic Language Understanding
│   │   ├── __init__.py
│   │   ├── client.py               # Provider client (Gemini / fallback) with structured output
│   │   ├── prompts.py              # System prompts, few-shot examples & domain grammar
│   │   └── interpreter.py          # LLM service returning raw structured directives
│   │
│   ├── guardrails/                 # [Member 3] Deterministic Validation & Normalization
│   │   ├── __init__.py
│   │   └── validator.py            # Hard rule checking, hours normalization & safe fallbacks
│   │
│   └── optimizer/                  # [Member 3] Mathematical Optimization Engine
│       ├── __init__.py
│       ├── model.py                # HiGHS LP formulation (scipy.optimize)
│       └── solver.py               # Constraint applicator & schedule generator
│
├── tests/
│   ├── __init__.py
│   ├── test_api.py                 # [Member 1] End-to-end API & schema validation
│   ├── test_llm.py                 # [Member 2] Note interpretation & paraphrase robustness
│   ├── test_guardrails.py          # [Member 3] Guardrail rules, ranges, edge cases
│   ├── test_optimizer.py           # [Member 3] Physical constraints & cost minimization
│   └── sample_payloads.json        # [Member 4] Benchmark datasets & public sample cases
│
├── deploy/                         # [Member 4] Packaging & Infrastructure
│   ├── Dockerfile                  # Production container binding 0.0.0.0:8000
│   └── docker-compose.yml          # Local reproduction runner
│
├── docs/                           # [Member 4] Presentation & Documentation
│   └── video_script.md             # 3-minute video presentation script for tie-breaker
│
├── scripts/                        # [Member 4] Developer tooling
│   └── run_benchmarks.sh           # Automated curl verification script
│
├── README.md                       # [Member 4] Canonical self-contained guide
├── requirements.txt                # Pinned dependencies
├── .env.example                    # Sample environment keys
└── .gitignore
```

---

## 👥 4-Member Division of Implementation

| Member | Role & Module | Primary Files | Key Deliverables & Responsibilities |
|---|---|---|---|
| **Member 1** | **Core API & Pipeline Lead**<br>`app/core/`, `app/main.py` | `main.py`<br>`core/schemas.py`<br>`core/orchestrator.py`<br>`core/replayer.py`<br>`tests/test_api.py` | • FastAPI HTTP server (`GET /health`, `POST /optimize-energy`).<br>• Canonical Pydantic request/response validation.<br>• Pipeline orchestrator: LLM $\rightarrow$ Guardrails $\rightarrow$ Optimizer $\rightarrow$ Replayer.<br>• Independent schedule replay engine (calculates `total_grid_kwh`, `total_cost_bdt`, `peak_grid_kwh`, verifies energy balance $\le 0.01$ tol).<br>• Controlled HTTP status codes (200, 400, 422, 500 without leaking secrets). |
| **Member 2** | **LLM Intelligence Lead**<br>`app/llm/` | `llm/client.py`<br>`llm/prompts.py`<br>`llm/interpreter.py`<br>`tests/test_llm.py` | • Gemini API integration (`google-genai`) with JSON structured output.<br>• Comprehensive prompt engineering for all 6 directive types (`solar_reduction`, `minimum_battery_reserve`, `no_charge_window`, `no_discharge_window`, `max_grid_window`, `no_op`).<br>• Few-shot examples handling paraphrasing, slang, percentages, 12h/24h intervals, and distractor filtering.<br>• Robust timeout/retry handling to guarantee $p95 \le 5\text{s}$. |
| **Member 3** | **Guardrails & Optimizer Lead**<br>`app/guardrails/`, `app/optimizer/` | `guardrails/validator.py`<br>`optimizer/model.py`<br>`optimizer/solver.py`<br>`tests/test_guardrails.py`<br>`tests/test_optimizer.py` | • Deterministic guardrails (sort/dedup hours 0..23, clamp factor [0,1], validate battery bounds, safe fallback on bad LLM output).<br>• Mathematical Linear Programming (LP) using `scipy.optimize` with HiGHS solver ($<15\text{ms}$ solve time).<br>• Physical constraints: hourly energy balance, battery capacity, charge/discharge rates, directional windows, end-of-day neutrality ($E[23] = E_0$).<br>• Output discrete actions: `charge`, `discharge`, or `idle`. |
| **Member 4** | **DevOps, Quality & Video Lead**<br>`deploy/`, `docs/`, `scripts/`, `README.md` | `Dockerfile`<br>`docker-compose.yml`<br>`config.py`<br>`README.md`<br>`docs/video_script.md`<br>`scripts/run_benchmarks.sh` | • Production Docker container binding `0.0.0.0:8000` (non-root, minimal size).<br>• Public deployment setup (Render, Fly.io, Railway, or tunnel) with live health check.<br>• Self-contained `README.md` satisfying all 10 points of evaluation Category 7.<br>• Benchmark test runner with public sample cases.<br>• 3-minute video presentation script and recording coordination for tie-breaker score. |

---

## 🔌 Internal Contracts Between Modules (Interfaces)

To allow parallel development from minute 1 without blockers, here are the clean internal interfaces connecting the modules:

### 1. Interface: Member 1 $\rightarrow$ Member 2 (LLM Input/Output)
```python
# app/llm/interpreter.py
async def interpret_operator_notes(
    notes: list[str],
    scenario_id: str
) -> list[RawDirectiveDTO]:
    """
    Interprets 1-3 operator notes into raw structured directive objects.
    Each item contains note_index, suggested directive_type, raw hours, raw numeric params, explanation.
    """
```

### 2. Interface: Member 2 $\rightarrow$ Member 3 (Guardrail Input/Output)
```python
# app/guardrails/validator.py
def validate_and_guardrail_directives(
    raw_directives: list[RawDirectiveDTO],
    notes_count: int,
    battery_capacity: float
) -> list[DirectiveInterpretation]:
    """
    Validates, sorts hours ascending, clamps factors, verifies limits.
    Guarantees exact output matching problem statement Section 04/08.
    Never crashes; falls back to no_op if invalid.
    """
```

### 3. Interface: Member 3 $\rightarrow$ Member 1 (Optimizer Input/Output)
```python
# app/optimizer/solver.py
def solve_energy_schedule(
    hours: list[HourData],
    battery: BatterySpec,
    validated_directives: list[DirectiveInterpretation]
) -> tuple[list[HourlyPlanItem], bool]:
    """
    Applies directive adjustments (solar reductions, reserve floors, charge/discharge blocks, grid caps).
    Solves cost-minimizing 24h schedule with HiGHS solver.
    Returns 24 HourlyPlan items and feasibility status.
    """
```

### 4. Interface: Member 1 (Replayer & Verification)
```python
# app/core/replayer.py
def replay_and_calculate_metrics(
    hourly_plan: list[HourlyPlanItem],
    hours: list[HourData],
    battery: BatterySpec,
    directives: list[DirectiveInterpretation]
) -> CalculatedMetrics:
    """
    Simulates hour-by-hour physics to recalculate:
    - total_grid_kwh
    - total_cost_bdt
    - peak_grid_kwh
    - verifies energy balance (|diff| <= 0.01)
    - generates plan_summary text
    """
```

---

## ⏱️ Suggested 4-Hour Timeline & Milestones

| Time Window | Milestone | Team Action Items |
|---|---|---|
| **Hour 1 (0:00 – 1:00)** | **Scaffolding & Contract Freezing** | • Member 1 creates schemas and FastAPI endpoints.<br>• Member 2 builds LLM prompts and test cases.<br>• Member 3 writes the basic LP optimizer with dummy directives.<br>• Member 4 sets up Dockerfile, Git repo, and `.env.example`. |
| **Hour 2 (1:00 – 2:00)** | **Core Module Completion** | • Member 1 writes replayer and pipeline orchestrator.<br>• Member 2 validates LLM with paraphrased notes and distractors.<br>• Member 3 adds directive constraints (solar cut, reserve floor, windows).<br>• Member 4 sets up public deployment on Render/Fly.io/tunnel. |
| **Hour 3 (2:00 – 3:00)** | **Integration & End-to-End Testing** | • All 4 modules wired into `app/main.py`.<br>• Run automated test suite and sample case benchmarks.<br>• Member 3 & 1 verify numeric tolerance ($\le 0.01\text{ kWh/BDT}$) and battery neutrality.<br>• Member 4 drafts the complete `README.md` and tests Docker container. |
| **Hour 4 (3:00 – 4:00)** | **Deployment, Verification & Video** | • Verify live endpoint from outside the network (`curl https://.../health`).<br>• Record & render the 3-minute video presentation.<br>• Final pre-submission checklist verification.<br>• Submit public URL, Docker image tag, GitHub repo link, and video. |

---

## 📋 Member-by-Member Verification Checklist

### Member 1 Checklist (API & Pipeline)
- [ ] `GET /health` responds immediately with `{"status": "ok"}`.
- [ ] `POST /optimize-energy` accepts exact schema and returns all required top-level fields.
- [ ] Response `directive_interpretation` has exactly $N$ entries in $0..N-1$ order.
- [ ] Replayer calculates `total_grid_kwh`, `total_cost_bdt`, and `peak_grid_kwh` matching `hourly_plan`.
- [ ] HTTP 400 returned on malformed JSON; no raw stack traces exposed.

### Member 2 Checklist (LLM Understanding)
- [ ] Gemini API calls use structured JSON schema.
- [ ] All 6 directive types correctly recognized.
- [ ] Distractor notes (cafeteria, weather) correctly map to `no_op` with `applies = false`.
- [ ] Paraphrased expressions ("one-fifth", "80% reduction", "13:00 to 15:00") extract correct values.
- [ ] Whole-hour logic implemented: start inclusive, end exclusive (1 PM to 3 PM $\rightarrow$ `[13, 14]`).
- [ ] Inference time optimized to contribute $< 3\text{s}$ to overall request latency.

### Member 3 Checklist (Guardrails & Optimizer)
- [ ] Guardrails enforce ascending sorted `hours` in $0..23$.
- [ ] `factor` clamped to $[0.0, 1.0]$.
- [ ] Battery reserve clamped to $\le \text{capacity}$ and $\ge 0$.
- [ ] LP/MILP problem solved using HiGHS in $<20\text{ms}$.
- [ ] Hourly energy balance strictly satisfied: $\text{grid} + \text{solar} + \text{discharge} = \text{demand} + \text{charge}$.
- [ ] Battery neutrality holds: $\text{battery}[23] == \text{battery}_{\text{initial}}$.
- [ ] Actions correctly labeled (`charge`, `discharge`, `idle`).

### Member 4 Checklist (DevOps, Documentation & Video)
- [ ] Docker image builds cleanly and binds to `0.0.0.0:8000`.
- [ ] Public endpoint is deployed and reachable from external networks without auth/VPN.
- [ ] `README.md` contains clear copy-paste local quickstart and curl commands.
- [ ] No API keys, passwords, or `.env` files are committed to Git.
- [ ] 3-minute video covers problem, architecture (LLM $\rightarrow$ Guardrails $\rightarrow$ Optimizer), and test run.
