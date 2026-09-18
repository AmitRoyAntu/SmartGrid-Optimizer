# Member 4 Plan — DevOps, Quality & Video Lead

> **Role**: DevOps, Quality & Video Lead
> **Scope**: `deploy/`, `docs/`, `scripts/`, `README.md`, `app/config.py`, `.env.example`
> **Goal**: Ship a self-contained, deployable, evaluator-friendly package that earns full marks on **Category 7 (Deployment & Documentation)** and the **tie-breaker video**.
>
> **Stack Decisions (locked)**:
> - **LLM Provider**: **Groq** (fast inference, generous free tier, OpenAI-compatible API) — *Member 2 must build the Groq client, not Gemini*.
> - **Public Deployment**: **Option A — Render** (free tier, native GitHub integration, auto-deploy on push, no credit card required for the free web service tier).

---

## 🎯 Mission Statement

Member 4 does **not** write core business logic. Member 4's job is to make the rest of the team's work **observable, reproducible, deployable, and presentable**. Every artifact Member 4 produces must answer one of these questions for the judge:

1. *"Can I run this in 60 seconds?"* → `README.md` + `docker-compose.yml`
2. *"Is it live right now?"* → Public URL with working `/health`
3. *"Is it reproducible?"* → `scripts/run_benchmarks.sh` + `sample_payloads.json`
4. *"Does it deserve the tie-breaker?"* → `docs/video_script.md` + recorded video

---

## 📁 Files Owned by Member 4

| File | Purpose | Status |
|---|---|---|
| `deploy/Dockerfile` | Production container, non-root, minimal size, binds `0.0.0.0:8000` | ⬜ |
| `deploy/docker-compose.yml` | One-command local reproduction | ⬜ |
| `app/config.py` | Environment settings (Pydantic `BaseSettings`), reads from `.env` — exposes `GROQ_API_KEY`, `GROQ_MODEL`, `LLM_TIMEOUT_SEC` | ⬜ |
| `.env.example` | Sample environment keys — `GROQ_API_KEY=your_groq_key_here`, `GROQ_MODEL=llama-3.3-70b-versatile` (no real secrets) | ⬜ |
| `requirements.txt` | Pinned dependencies (FastAPI, uvicorn, pydantic, **groq** or **openai** client, scipy, numpy) | ⬜ |
| `.gitignore` | Excludes `.env`, `__pycache__`, `.venv`, `.pytest_cache` | ✅ exists (verify) |
| `README.md` | Canonical self-contained guide (10 evaluation points) | ⬜ |
| `tests/sample_payloads.json` | Benchmark datasets & public sample cases | ⬜ |
| `scripts/run_benchmarks.sh` | Automated curl verification against live endpoint | ⬜ |
| `docs/video_script.md` | 3-minute video script (problem → architecture → demo → results) | ⬜ |
| `member4/PLAN.md` | This file | ✅ |

---

## ⏱️ 4-Hour Execution Timeline (Member 4 Only)

### 🟢 Hour 1 — Scaffolding & Container Foundation (0:00 – 1:00)

**Objective**: Standing deployment-ready skeleton so other members can integrate against it.

- [ ] **M4-1.1** Create `deploy/Dockerfile`
  - Base: `python:3.11-slim`
  - `WORKDIR /app`, copy `requirements.txt` first (cache layer)
  - Install deps with `pip install --no-cache-dir`
  - `COPY . .`
  - Create non-root user `appuser`, `chown` files
  - `EXPOSE 8000`
  - `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`

- [ ] **M4-1.2** Create `deploy/docker-compose.yml`
  - Service `api`: build from `.`, map `8000:8000`, env file `.env`, restart policy `unless-stopped`

- [ ] **M4-1.3** Create `app/config.py` (Pydantic `BaseSettings`)
  - Fields:
    - `GROQ_API_KEY: str` (required, no default)
    - `GROQ_MODEL: str = "llama-3.3-70b-versatile"` (fast + good at structured JSON)
    - `GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"`
    - `LLM_TIMEOUT_SEC: float = 4.0`
    - `LLM_PROVIDER: str = "groq"` (kept for future swap)
    - `LOG_LEVEL: str = "INFO"`
    - `APP_ENV: str = "production"`
  - **Strict**: fail fast on startup if `GROQ_API_KEY` is missing in `APP_ENV=production`

- [ ] **M4-1.4** Create `.env.example` with **placeholder values only**:
  ```
  GROQ_API_KEY=your_groq_key_here
  GROQ_MODEL=llama-3.3-70b-versatile
  LLM_TIMEOUT_SEC=4.0
  LOG_LEVEL=INFO
  APP_ENV=production
  ```

- [ ] **M4-1.5** Create `requirements.txt` with pinned versions

- [ ] **M4-1.6** Verify `.gitignore` blocks: `.env`, `__pycache__/`, `.venv/`, `.pytest_cache/`, `*.pyc`, `.DS_Store`

- [ ] **M4-1.7** Initialize Git repo, make first commit (`chore: scaffold member 4 deploy artifacts`)

**Deliverable**: `docker build` succeeds; `docker run` prints "Application startup complete."

---

### 🟡 Hour 2 — Public Deployment & Documentation (1:00 – 2:00)

**Objective**: Live URL the judge can hit from anywhere in the world.

- [ ] **M4-2.1** Provision public deployment on **Render (Option A)**:
  1. Sign up at https://dashboard.render.com/ using your **GitHub account** (no credit card needed for the Free plan).
  2. Click **New + → Web Service → Connect repository** → select the SmartGrid-Optimizer repo (must be **public** on GitHub first).
  3. Configuration:
     - **Runtime**: `Docker` (auto-detected from `Dockerfile`)
     - **Region**: Singapore (closest to Bangladesh, lowest latency)
     - **Instance Type**: `Free`
     - **Health Check Path**: `/health`
  4. **Environment Variables** (Environment section, do NOT commit these):
     - `GROQ_API_KEY` = your Groq key from https://console.groq.com/keys
     - `GROQ_MODEL` = `llama-3.3-70b-versatile`
     - `APP_ENV` = `production`
     - `LOG_LEVEL` = `INFO`
  5. Click **Create Web Service**. Render builds the Docker image and deploys.
  6. Note the public URL: `https://smartgrid-optimizer.onrender.com` (or custom name you chose).
- [ ] **M4-2.2** Verify `GET https://<public-url>/health` returns `{"status":"ok"}` **from a phone on a different network**
- [ ] **M4-2.3** Verify `POST https://<public-url>/optimize-energy` accepts a sample payload
- [ ] **M4-2.4** Create `tests/sample_payloads.json` — at minimum:
  - `payload_simple`: 1 note, no directives
  - `payload_solar_cut`: solar reduction 50% during 10:00–14:00
  - `payload_paraphrase`: "one-fifth", "80% cut", "13 to 15"
  - `payload_distractor`: contains a cafeteria note (should map to `no_op`)
- [ ] **M4-2.5** Create `scripts/run_benchmarks.sh`
  - `#!/usr/bin/env bash` with `set -euo pipefail`
  - Variables: `BASE_URL` (default to public URL), `PAYLOAD_DIR`
  - Loop over each payload, POST it, print status code + latency
  - Assert `total_grid_kwh` and `peak_grid_kwh` are present in response

**Deliverable**: Judge can `bash scripts/run_benchmarks.sh` against a public URL.

---

### 🟠 Hour 3 — README, Quality & Polish (2:00 – 3:00)

**Objective**: README satisfies **all 10 points of Category 7** of the rubric.

- [ ] **M4-3.1** Write `README.md` covering (in order):
  1. **Project name + 1-line tagline**
  2. **Problem statement** (2–3 sentences, link to PDF if allowed)
  3. **Architecture diagram** — ASCII or mermaid showing LLM → Guardrails → Optimizer → Replayer
  4. **Module breakdown** (4-member division table)
  5. **Local quickstart** (Docker one-liner + bare-metal `pip install -r requirements.txt && uvicorn app.main:app`)
  6. **API usage** — example `curl POST /optimize-energy` with sample payload
  7. **Environment variables** — full table from `.env.example`
  8. **Public endpoint URL** — bold, prominent, copy-pasteable
  9. **Reproducing benchmarks** — `bash scripts/run_benchmarks.sh`
  10. **Team / credits / license**

- [ ] **M4-3.2** Add **troubleshooting** section: missing API key → check `.env`; port 8000 in use → `lsof -i:8000`

- [ ] **M4-3.3** Add **badges** (optional): Docker Image Version, License, Endpoint Status (use a free uptime badge or remove)

- [ ] **M4-3.4** Sanity-check repository for secrets:
  - `git log -p | grep -i "gemini_api_key="` → must return nothing
  - Confirm `.env` is in `.gitignore`

- [ ] **M4-3.5** Coordinate with **Member 1** to ensure `app/main.py` reads `settings` from `app.config` (not hardcoded)

- [ ] **M4-3.6** Coordinate with **Member 2** to ensure `app/llm/client.py` reads `GROQ_API_KEY` from `app.config` (not `os.getenv` directly) and uses the **OpenAI-compatible client** pointed at `GROQ_BASE_URL`

- [ ] **M4-3.7** Run full integration test from a clean clone in `/tmp` (or second clone) using only the README instructions

**Deliverable**: A judge who has never seen the project can run it from `README.md` alone.

---

### 🔴 Hour 4 — Video & Submission (3:00 – 4:00)

**Objective**: 3-minute video + final submission with all required artifacts.

- [ ] **M4-4.1** Write `docs/video_script.md` (≈ 3 minutes, ~450 words spoken):
  - **0:00–0:30 Hook**: "Energy costs in Bangladeshi campuses are rising; solar+battery planning requires expert intuition. We built an LLM that turns operator notes into an optimized 24-hour schedule in under 5 seconds — powered by **Groq** for sub-second inference."
  - **0:30–1:15 Problem**: Show 3 messy operator notes (paraphrase + distractor + solar cut). Explain the 6 directive types.
  - **1:15–2:00 Architecture** (animated diagram): `Operator Notes → Groq LLM (llama-3.3-70b) → Guardrails → LP/HiGHS Optimizer → Replayer → JSON`
  - **2:00–2:45 Live demo**: screen-record `curl POST https://smartgrid-optimizer.onrender.com/optimize-energy` against the **Render** public URL, show the JSON response with `total_grid_kwh`, `total_cost_bdt`, `peak_grid_kwh`, per-hour actions, and the battery neutrality check.
  - **2:45–3:00 Wrap**: show `bash scripts/run_benchmarks.sh https://smartgrid-optimizer.onrender.com` green output, GitHub repo link, public URL.

- [ ] **M4-4.2** Record the video using OBS / Loom / phone camera (whichever is fastest). Export ≤ 200MB, ≤ 1080p.

- [ ] **M4-4.3** Pre-submission checklist:
  - [ ] Public URL responds to `curl https://<url>/health` from outside your network
  - [ ] `docker pull <registry>/smartgrid-optimizer:latest` succeeds (if pushed) OR image is buildable from `Dockerfile`
  - [ ] GitHub repo is **public** with `README.md`, `Dockerfile`, `requirements.txt`
  - [ ] No secrets in repo (`git log -p | grep -i "api[_-]key"`)
  - [ ] 3-minute video uploaded (YouTube unlisted / Drive link / provided host)
  - [ ] All 4 members' deliverables merged to `main` branch

- [ ] **M4-4.4** Submit:
  - Public endpoint URL
  - Docker image tag (or Dockerfile path)
  - GitHub repo link
  - Video link

---

## 🔌 Internal Contracts Member 4 Must Honor

These are **promises** the rest of the team makes to Member 4 (and vice versa):

| Contract | Owner | Member 4 must provide | Others must provide |
|---|---|---|---|
| `app/config.py` exposes `settings.GROQ_API_KEY`, `settings.GROQ_MODEL`, `settings.GROQ_BASE_URL` | Member 4 | the module | **Member 2** imports it (NOT Gemini SDK — use OpenAI-compatible client pointing at `GROQ_BASE_URL`) |
| `GET /health` returns `{"status":"ok"}` in < 100ms | Member 1 | live URL to hit | Member 1 writes endpoint |
| `POST /optimize-energy` returns full schema | Member 1 | live URL | Member 1 writes endpoint |
| `deploy/Dockerfile` builds without warnings | Member 4 | Dockerfile | Member 3 ensures no hardcoded paths |
| `tests/sample_payloads.json` is loadable | Member 4 | JSON file | Member 1's Pydantic models accept it |
| `requirements.txt` versions match what others use | Member 4 | pinned list — must include `groq>=0.11.0` or `openai>=1.50.0` (whichever Member 2 chooses) | Others say "I need X.Y.Z" early |

---

## 🚨 Risk Register & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Render free tier service spins down after 15 min of inactivity | High | Medium | First request after idle takes ~30s. Document this in README ("first request may be slow, subsequent are fast"). Add a cron ping or accept it. |
| Render free tier requires GitHub repo to be **public** | Certain | Low | Confirm repo is public before connecting Render. |
| Render requires credit card on file even for free tier | Medium | Medium | Use a **free Render account** (signup with GitHub, no card needed for the `Free` web service plan). If forced, use a Cloudflare Tunnel as fallback. |
| Docker build fails on Members 1/2/3's machines due to version drift | Medium | High | Pin **exact** versions in `requirements.txt`; test build in clean Docker early |
| **Groq** rate-limit (requests-per-minute cap on free tier) during judging | Medium | Medium | Implement graceful fallback to deterministic regex/keyword parser in `app/llm/client.py` so demo never 500s. Cache common interpretations. |
| **Groq** model deprecation (`llama-3.3-70b-versatile` could be retired) | Low | High | `GROQ_MODEL` is a single env var — swap is one line in Render dashboard. Document alternates (`llama-3.1-8b-instant`) in README. |
| Video file too large to upload | Low | High | Record at 720p, H.264, target ≤ 100MB |
| LLM latency p95 > 5s | Low | High | Groq is typically < 1s. Member 4 monitors live endpoint with `curl -w "%{time_total}"`; if p95 creeps, flag Member 2 immediately. |
| Judge runs a distractor-only payload → expects `no_op` | High | None (handled) | `sample_payloads.json` includes distractor case; `run_benchmarks.sh` validates `directive_interpretation[].applies == false` |

---

## 📞 Coordination Protocol

Member 4 is a **force multiplier** — the team needs to integrate against Member 4's interfaces early. Schedule:

- **0:05 sync** — confirm file ownership, freeze `config.py` field names
- **1:30 sync** — confirm `GET /health` works locally; start public deployment clock
- **2:30 sync** — confirm `docker-compose up` works on a teammate's machine
- **3:30 sync** — record video; final go/no-go

Use the project's primary chat channel. Tag **@member4** for any deployment-blocking issue.

---

## ✅ Final Acceptance Criteria (Member 4 Owns These)

By submission time, Member 4 has **personally verified** every box:

- [ ] `docker build -t smartgrid-optimizer .` succeeds on a fresh clone, < 90s
- [ ] `docker run -p 8000:8000 smartgrid-optimizer` shows "Application startup complete" within 5s
- [ ] `curl http://localhost:8000/health` returns `{"status":"ok"}`
- [ ] `curl -X POST http://localhost:8000/optimize-energy -d @tests/sample_payloads.json` returns 200 with full schema
- [ ] Public **Render** URL is reachable from **mobile data** (not same WiFi)
- [ ] **Render** dashboard shows `GROQ_API_KEY` is set in Environment (NOT in code)
- [ ] `bash scripts/run_benchmarks.sh https://smartgrid-optimizer.onrender.com` exits 0
- [ ] `README.md` is the **first file** a judge sees, with the public URL in the first 30 lines
- [ ] No secrets in `git log -p` (especially no `GROQ_API_KEY=...` strings)
- [ ] Video is ≤ 3:10, ≤ 200MB, links resolve
- [ ] All 10 Category 7 rubric points addressed (cross-checked against evaluation PDF)
- [ ] After Render free-tier cold start (~30s), `p95 latency < 5s` confirmed by 10-curl sample

---

## 📚 Reference Reading

- `BUP_CSE_FEST_2026_Participant_Guide_&_Evaluation_Rubric_GridWise_LLM.pdf` → **Category 7** (Deployment & Documentation) and **Tie-Breaker** (Video)
- `BUP_CSE_FEST_2026_Preliminary_Problem_Statement_GridWise_LLM.pdf` → Section on output schema (so README examples are accurate)
- `implementation_plan.md` → architecture & internal contracts

---

**Member 4 motto**: *"If Member 4's work is invisible, the team loses 20% of the marks they earned."*
Make it loud, make it reproducible, make it pretty.
