# GridWise LLM: Smart Campus Energy Optimization Service

**BUP CSE Fest 2026 Hackathon (Online Preliminary Round)**  
*Challenge*: LLM-Assisted Smart Campus Energy Scheduling & Operator Directive Interpretation

---

## 📌 Competition Endpoints Contract
- **Readiness Health Check**: `GET /health` -> `{"status": "ok"}`
- **Main Optimization Endpoint**: `POST /optimize-energy`

---

## 👥 Team Roles & Responsibilities
- **Member 1**: Core API & Pipeline Lead (HTTP Server, Pydantic Schemas, Pipeline Orchestration, Replayer)
- **Member 2**: LLM Intelligence Lead (Semantic Operator Note Interpretation, Prompt Engineering)
- **Member 3**: Guardrails & Optimizer Lead (Deterministic Validation, Mathematical Solver / LP)
- **Member 4**: DevOps, Quality & Presentation Lead (Docker, Benchmarking, Documentation, Video)

---

## 🧪 Testing Utilities (Member 4)
- **Sample Benchmark Payloads**: `tests/sample_payloads.json`
- **Contract Verification Script**: `./scripts/run_benchmarks.sh <TARGET_URL>`