---
title: DevOps Incident Response OpenEnv
emoji: "🚨"
sdk: docker
pinned: false
app_port: 8000
tags:
  - openenv
  - devops
  - rl-environment
  - sre
  - pytorch
---

# DevOps Incident Response OpenEnv

> **A production-grade RL environment for benchmarking AI agents on real-world SRE incident triage.**

This environment stress-tests AI models on multi-service debugging, dependency chain tracing, and safe remediation — the three skills that separate a great SRE from a reactive one. Built for the [OpenEnv](https://huggingface.co/openenv) standard with deterministic grading, strict Pydantic schemas, and a zero-config Docker deployment.

[![HuggingFace Space](https://img.shields.io/badge/🤗%20Live%20Demo-HuggingFace%20Space-yellow)](https://huggingface.co/spaces/aryanosh/devops-incident-response)
[![GitHub](https://img.shields.io/badge/GitHub-Source-black)](https://github.com/aryanosh/devops-incident-response)

---

## Task Overview

Four escalating incident scenarios across a realistic 6-service microservice topology. Each task requires the agent to resist surface-level symptom patching and trace failures to their true root cause.

| Level | Task ID | Scenario | Root Cause | Required Fix |
|---|---|---|---|---|
| 🟢 Easy | `easy_task` | Single Service Crash | `api_gateway` — `service_crash` | `restart_service` |
| 🟡 Medium | `medium_task` | Memory Leak in Order Service | `order_service` — `memory_leak` | `memory_fix` |
| 🔴 Hard | `hard_task` | Cascading Disk Saturation | `database` — `disk_full` | `clear_disk` |
| 🟣 Expert | `expert_task` | Dual-Root: DB + Payment Failure | `database` + `payment_service` | `clear_disk` + `drain_connections` |

### Service Dependency Graph

```
api_gateway
├── auth_service
│   └── user_service
│       └── database
└── order_service
    ├── payment_service
    │   └── database
    └── database
```

The **Hard** and **Expert** tasks intentionally show symptoms on upstream services (`api_gateway`, `order_service`) while the true root cause sits at `database`. Agents must trace the dependency chain, not just patch the visible alert.

---

## Quick Start

### 1. Run via Docker

```bash
docker build -t devops_incident_env .
docker run -p 8000:8000 devops_incident_env
```

The server starts at `http://localhost:8000`. Visit `/docs` for the interactive Swagger UI.

### 2. Run the Evaluation Agent

```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your_huggingface_token"
export ENV_URL="http://127.0.0.1:8000"   # or leave unset to use LocalEnvClient

python inference.py
```

`HF_TOKEN` is required. The script raises immediately if it is missing.

### 3. Run Tests

```bash
pytest tests/ -v
```

---

## API Reference

All routes conform to the OpenEnv HTTP specification.

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Environment manifest |
| `GET` | `/health` | Liveness check — returns `{"status": "healthy"}` |
| `GET` | `/tasks` | List all 4 task definitions with metadata |
| `GET` | `/manifest` | Full environment schema |
| `POST` | `/reset` | Start a new episode: `{"task_id": "hard_task", "seed": 42}` |
| `POST` | `/step` | Submit an action and receive an observation + reward |
| `GET` | `/state` | Current episode state snapshot |
| `GET` | `/grader` | Final grader score for the current episode |
| `GET` | `/baseline` | Next recommended action from the rule-based baseline |
| `GET` | `/sample_action` | Alias for `/baseline` |

---

## Action & Observation Schema

### Actions (`POST /step`)

```json
{
  "action": {
    "action_type": "diagnose",
    "service": "database",
    "diagnosis": "disk_full",
    "reasoning": "WAL logs indicate no space left on device. confidence=0.92"
  }
}
```

**Valid `action_type` values:** `read_logs` · `query_metrics` · `diagnose` · `apply_fix` · `verify_health` · `list_services` · `inspect_dependencies`

**Valid `diagnosis` values:** `service_crash` · `memory_leak` · `high_latency` · `connection_pool_exhaustion` · `disk_full` · `certificate_expired` · `config_drift`

**Valid `fix` values:** `restart_service` · `memory_fix` · `clear_disk` · `scale_up` · `rollback_config` · `renew_certificate` · `drain_connections` · `clear_cache`

### Observation (response from `/step` and `/reset`)

```json
{
  "observation": {
    "action_result": "Retrieved logs for database.",
    "message": "Recent logs show a pattern consistent with disk full.",
    "logs": [...],
    "metrics": {...},
    "service_summaries": [...],
    "active_alerts": [...],
    "dependency_graph": {...},
    "step_number": 4,
    "max_steps": 12,
    "steps_remaining": 8,
    "available_services": [...],
    "available_actions": [...]
  },
  "reward": 0.04,
  "done": false,
  "info": {
    "task_id": "hard_task",
    "last_action_error": null,
    "trajectory_reward": 0.16
  }
}
```

---

## Reward System

The environment emits dense per-step rewards and a separate deterministic final grader score. **All rewards and scores are strictly bounded within `(0.05, 0.95)`** — never exactly `0` or `1`.

### Step Rewards

| Action | Reward | Condition |
|---|---|---|
| `read_logs` / `query_metrics` on root-cause service | `+0.04` | First time only |
| `read_logs` / `query_metrics` on affected service | `+0.03` | First time only |
| `diagnose` (correct, root cause) | `+0.08` | Correct failure mode identified |
| `diagnose` (correct, affected service) | `+0.03` | Correct symptom identified |
| `apply_fix` (correct fix, correct service) | `+0.12` | Right fix on right service |
| `verify_health` (post-fix) | `+0.04` | Confirmed recovery |
| `inspect_dependencies` (first time) | `+0.02` | New service traversal |
| `list_services` (first call) | `+0.015` | One-time discovery reward |
| Wrong/invalid/destructive action | `+0.05` (floor) | Penalized via grader safety score |

Step rewards are clamped to `[0.05, 0.95]` before emission. The terminal step always emits the floor reward `0.05`; the definitive episode score comes from the grader.

### Final Grader Score

The grader combines four weighted dimensions into a final score in `(0.05, 0.95)`:

| Component | Weight | What It Measures |
|---|---|---|
| Root Cause Identification | 35% | Did the agent find the right service **and** failure mode? |
| Resolution | 30% | Was the correct fix applied and successful? |
| Efficiency | 20% | How many steps taken vs. optimal path? |
| Safety | 15% | Did the agent avoid destructive or invalid actions? |

```
final_score = 0.35 × root_id + 0.30 × resolution + 0.20 × efficiency + 0.15 × safety
```

All component scores are clamped to `[0.05, 0.95]`. The total is then clamped identically.

---

## Example Trace

Successful hard task run (Qwen/Qwen2.5-72B-Instruct):

```text
[START] task=hard_task env=devops_incident_env model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=list_services() reward=0.050 done=false error=null
[STEP] step=2 action=read_logs(api_gateway) reward=0.050 done=false error=null
[STEP] step=3 action=inspect_dependencies(api_gateway) reward=0.050 done=false error=null
[STEP] step=4 action=read_logs(database) reward=0.050 done=false error=null
[STEP] step=5 action=query_metrics(database) reward=0.050 done=false error=null
[STEP] step=6 action=diagnose(database) reward=0.080 done=false error=null
[STEP] step=7 action=apply_fix(database) reward=0.120 done=false error=null
[STEP] step=8 action=verify_health(database) reward=0.050 done=true error=null
[END] success=true steps=8 rewards=0.050,0.050,0.050,0.050,0.050,0.080,0.120,0.050
```

The agent correctly resists patching `api_gateway` (the visible alert) and traces the dependency chain to `database` as the true root cause.

---

## Baseline Scores

Committed run artifacts are in `outputs/` for evaluator verification:

- `outputs/inference_baseline_run.txt` — full `[START]`/`[STEP]`/`[END]` trace across all 4 tasks
- `outputs/task_score_summary.json` — per-task final grader scores

| Task | Difficulty | Grader Score |
|---|---|---|
| `easy_task` | 🟢 Easy | `0.880` |
| `medium_task` | 🟡 Medium | `0.880` |
| `hard_task` | 🔴 Hard | `0.880` |
| `expert_task` | 🟣 Expert | `0.880` |

---

## Project Structure

```text
devops_incident_env/
├── server/
│   ├── app.py            # FastAPI app — all HTTP routes + score clamping middleware
│   └── environment.py    # Core RL environment: step logic, reward emission, state tracking
├── tasks.py              # Scenario configs, service graph, log/metric templates
├── grader.py             # Deterministic final-score formula (4-component weighted sum)
├── models.py             # Pydantic schemas: Action, Observation, State, Task
├── constants.py          # All reward values, grader weights, score bounds (SCORE_FLOOR=0.05, SCORE_CEILING=0.95)
├── baseline.py           # Rule-based baseline agent (used as inference fallback)
├── inference.py          # Evaluation runner: LLM agent + structured [START]/[STEP]/[END] stdout
├── client.py             # Thin HTTP client for remote environment interaction
├── openenv.yaml          # OpenEnv spec manifest
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container definition (python:3.11-slim, port 8000)
├── outputs/
│   ├── inference_baseline_run.txt   # Committed baseline trace
│   └── task_score_summary.json      # Committed score snapshot
└── tests/
    ├── test_environment.py          # Environment lifecycle and state tests
    └── test_fixes.py                # Per-scenario fix and grader correctness tests
```

---

## Design Principles

**Deterministic grading.** The final score is computed from rule-based logic in `grader.py`, not an LLM judge. Score outputs are reproducible and interpretable.

**Dependency-aware reward shaping.** Investigating the right service in the dependency chain earns more than investigating the surface symptom. This teaches causal debugging, not symptom patching.

**Strict score bounds.** Every reward emitted by `/step` and every score returned by `/grader` is bounded to `(0.05, 0.95)`. No `0.0` or `1.0` is ever returned.

**Anti-abuse mechanics.** Applying a wrong fix, fixing an already-healthy service, or repeating fixes counts as a destructive action. Each destructive action reduces the Safety component by 50%, creating a strong signal to avoid brute-force remediation.

**Red herring separation.** Affected (downstream) services show plausible-looking failure modes — `high_latency`, `connection_pool_exhaustion` — to pressure-test the agent's ability to distinguish symptom from root cause.

**Multi-root expert challenge.** The expert task requires resolving two independent root causes (`database` and `payment_service`) in a coordinated sequence. A partial fix is explicitly penalized in the Resolution component.

---

## Space Availability

A GitHub Actions workflow at `.github/workflows/space-keepalive.yml` pings `/health` every 10 minutes to prevent the HuggingFace Space from sleeping during the evaluation window.

Live environment: `https://aryanosh-devops-incident-response.hf.space`
