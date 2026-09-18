# Member 3 Documentation Index

## 📍 You Are Here
- **Project**: SmartGrid-Optimizer (GridWise LLM Hackathon)
- **Your Role**: Member 3 — Guardrails & Optimizer Lead
- **Git Branch**: `feature/member3-guardrails-optimizer`
- **Status**: ✅ Setup complete, ready to code
- **Date**: 2026-09-18

---

## 📚 Documentation Files (1,987 lines total)

### Quick Start (15 minutes)
```
00_SUMMARY.md          ← You are here (overview & next steps)
START_HERE.md          ← Before you code (pre-checklist)
QUICK_REFERENCE.md     ← During coding (commands & contracts)
```

### Complete Guides (45 minutes)
```
MEMBER3_IMPLEMENTATION_PLAN.md   ← Full specification (4-hour timeline)
DEPENDENCIES.md                   ← Setup & troubleshooting
```

---

## 🎯 What You're Building

**2 Modules:**
1. **Guardrails Validator** — Sanitize LLM directives
2. **Energy Optimizer** — Solve LP to generate 24h schedule

**3 Test Suites:**
1. `test_guardrails.py` — Validation rules
2. `test_optimizer.py` — LP constraints
3. Integration tests (via Member 1)

---

## 📂 Files You'll Create

```
app/guardrails/validator.py       ← Main guardrails logic
app/optimizer/solver.py           ← Main optimizer logic
app/optimizer/model.py            ← LP formulation
tests/test_guardrails.py          ← Guardrail tests
tests/test_optimizer.py           ← Optimizer tests
```

---

## ⏰ Timeline

| Hour | Milestone | Target |
|------|-----------|--------|
| 1 | Scaffold & schemas | Contracts locked |
| 2 | Core implementation | Both modules working |
| 3 | Integration testing | End-to-end verified |
| 4 | Final verification | Ready to submit |

---

## 🚀 To Start Coding

**Right now:**
```bash
# You are in: SmartGrid-Optimizer/
# On branch: feature/member3-guardrails-optimizer
# Docs are in: member3_workspace/

# Next: Read 00_SUMMARY.md (2 min)
# Then: Read START_HERE.md (3 min)
# Then: Begin Hour 1 from MEMBER3_IMPLEMENTATION_PLAN.md
```

---

## 🔗 Your Contracts

**INPUT** from Member 2: `RawDirectiveDTO`
- Raw, unvalidated directives
- May have errors (out-of-range hours, bad factors, low confidence)

**OUTPUT** to Member 1: `DirectiveInterpretation` + `HourlyPlanItem[24]`
- Validated directives (safe, deterministic)
- 24-hour energy schedule (cost-optimized)

---

## ✅ Success Criteria

By end of Hour 4:
- [ ] All unit tests passing
- [ ] Energy balance verified (±0.01 kWh tolerance)
- [ ] Battery neutrality verified
- [ ] Solver latency < 15ms
- [ ] No crashes on edge cases
- [ ] Code formatted & linted
- [ ] Ready for Member 1 integration

---

## 💡 Key Concepts

- **6 Directive Types**: solar_reduction, minimum_battery_reserve, no_charge_window, no_discharge_window, max_grid_window, no_op
- **Energy Balance**: Grid + Solar + Discharge = Demand + Charge (hourly)
- **Battery Neutrality**: Battery level at hour 23 must equal hour 0
- **LP Solver**: scipy.optimize with HiGHS backend
- **Tolerance**: ±0.01 kWh for numeric validation

---

## 📞 Team Handoff Points

| Member | You Receive | You Provide | Integration Point |
|--------|-------------|-------------|-------------------|
| Member 1 | API contract | Validated directives, schedule | app/core/orchestrator.py |
| Member 2 | Raw directives | Validated directives | Member 1's pipeline |
| Member 4 | requirements.txt | Test results | Docker build |

---

**Next**: Open `START_HERE.md` (3 min read) → Then begin Hour 1

