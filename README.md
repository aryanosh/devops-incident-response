---
title: DevOps Incident Response OpenEnv
emoji: "🚨"
sdk: docker
pinned: false
app_port: 7860
tags:
  - openenv
  - devops
  - rl-environment
---

# DevOps Incident Response OpenEnv: SRE Triage Framework

A DevOps incident-response RL testbed designed to stress-test future AI models on production-style debugging, dependency tracing, and safe remediation behavior. Built for the OpenEnv workflow with deterministic grading, strict typed schemas, and a lightweight Docker deployment model.

The environment trains agents to investigate the right services, separate symptoms from root causes, apply the correct fix, and verify recovery without drifting into destructive actions.

## Task Overview

| Level | ID | Scenario | Mission |
| --- | --- | --- | --- |
| Easy | `easy_task` | Single Service Crash | Diagnose the crashed `api_gateway` and restore service with the correct remediation. |
| Medium | `medium_task` | Memory Leak in Order Service | Trace degraded checkout behavior back to an `order_service` memory leak and fix it safely. |
| Hard | `hard_task` | Cascading Failure from Database Disk Saturation | Resist symptom-level fixes, trace the dependency chain to `database`, clear the real root cause, and verify recovery. |

## Quick Start

### 1. Build & Deploy

The environment is containerized for local testing and Hugging Face Space deployment.

```bash
docker build -t devops_incident_env .
docker run -p 7860:7860 devops_incident_env
```

### 2. Run the Evaluation Baseline

Use the optimized inference runner.

```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your_hugging_face_token"
export ENV_URL="http://127.0.0.1:7860"

python inference.py
```

## Reward System

The environment uses dense step rewards plus a separate deterministic final grader score.

| Condition | Reward | Purpose |
| --- | --- | --- |
| Root-cause investigation | `+0.04` | Rewarded for inspecting the service carrying the true failure mode. |
| Affected-service investigation | `+0.03` | Encourages tracing symptoms without over-rewarding symptom-level work. |
| Correct diagnosis | `+0.08` | Rewards identifying the actual failure mode. |
| Correct fix | `+0.12` | Rewards selecting the right remediation for the right service. |
| Successful verification | `+0.04` | Requires explicit proof that the service recovered. |
| Invalid or wrong action | `-0.01` to `-0.05` | Penalizes blind fixes, destructive actions, and invalid inputs. |

Clamped final scores are always strictly inside `(0, 1)` and are mapped to `[0.001, 0.999]`.

## Example Output

Below is a successful local trace on the hard task.

```text
[START] task=Cascading Failure from Database Disk Saturation env=devops-incident-response model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=read_logs(database) reward=0.04 done=false error=null
[STEP] step=2 action=query_metrics(database) reward=0.04 done=false error=null
[STEP] step=3 action=diagnose(database) reward=0.08 done=false error=null
[STEP] step=4 action=apply_fix(database) reward=0.12 done=false error=null
[STEP] step=5 action=verify_health(database) reward=0.04 done=true error=null
[END] success=true steps=5 rewards=0.04,0.04,0.08,0.12,0.04
```

## Project Structure

```text
devops_incident_env/
├── server/
│   ├── app.py
│   ├── environment.py
│   └── __init__.py
├── models.py
├── tasks.py
├── grader.py
├── baseline.py
├── client.py
├── inference.py
├── openenv.yaml
├── requirements.txt
├── Dockerfile
└── README.md
```

## Standardized Routes

- `GET /`
- `GET /health`
- `GET /tasks`
- `GET /manifest`
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /grader`
- `GET /baseline`
- `GET /sample_action`

## Design Principles

- Deterministic grading: final scoring is rule-based, not LLM-based.
- Dependency-aware reasoning: agents are rewarded for tracing root causes rather than patching surface symptoms.
- Anti-abuse reward shaping: invalid, redundant, and destructive actions receive penalties.
- Strict typed schemas: actions, observations, tasks, and state are bounded by Pydantic models.
- Lightweight deployment: Docker image exposes port `7860` and supports validator-friendly routes.
