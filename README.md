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
| Expert | `expert_task` | Compound Failure Across Database and Payment Plane | Trace and resolve a multi-root incident affecting both `database` and `payment_service` before restoring API health. |

## Quick Start

### 1. Build & Deploy

The environment is containerized for local testing and Hugging Face Space deployment.

```bash
docker build -t devops_incident_env .
docker run -p 8000:8000 devops_incident_env
```

### 2. Run the Evaluation Baseline

Use the optimized inference runner.

```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your_hugging_face_token"
export ENV_URL="http://127.0.0.1:8000"

python inference.py
```

`HF_TOKEN` is required at runtime. The script raises immediately if it is missing.

### 3. Keep the Space Awake for Evaluation

Evaluator reliability depends on a warm Space. This repo includes an uptime workflow at
`.github/workflows/space-keepalive.yml` that pings `/health` every 10 minutes.

- Default URL: `https://aryanosh-devops-incident-response.hf.space/health`
- Optional secret override: `SPACE_HEALTHCHECK_URL`

For critical windows, also pin the Space in Hugging Face settings.

## Reward System

The environment uses dense step rewards plus a separate deterministic final grader score.

| Condition | Reward | Purpose |
| --- | --- | --- |
| Root-cause investigation | `+0.04` | Rewarded for inspecting the service carrying the true failure mode. |
| Affected-service investigation | `+0.03` | Encourages tracing symptoms without over-rewarding symptom-level work. |
| Correct diagnosis | `+0.08` | Rewards identifying the actual failure mode. |
| Correct fix | `+0.12` | Rewards selecting the right remediation for the right service. |
| Successful verification | `+0.04` | Requires explicit proof that the service recovered. |
| Invalid or wrong action | `0.00` | Wrong, invalid, or destructive actions receive no positive reward and reduce overall grading quality. |

Emitted step rewards are kept in the valid `0.0` to `0.99` display range, and final scores are always strictly inside `(0, 1)` and mapped to `[0.001, 0.999]`.

The evaluation script emits only the required three stdout line types, in order: `[START]`, `[STEP]`, and `[END]`.

## Example Output

Below is a successful local trace on the hard task.

```text
[START] task=hard_task env=devops_incident_env model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=read_logs(database) reward=0.04 done=false error=null
[STEP] step=2 action=query_metrics(database) reward=0.04 done=false error=null
[STEP] step=3 action=diagnose(database) reward=0.08 done=false error=null
[STEP] step=4 action=apply_fix(database) reward=0.12 done=false error=null
[STEP] step=5 action=verify_health(database) reward=0.00 done=true error=null
[END] success=true steps=5 rewards=0.04,0.04,0.08,0.12,0.00
```

Note: terminal `step` reward is intentionally `0.00` when the episode ends because final grading is emitted as `final_score`/`grader_score` in state/info. Intermediate verification reward is still `+0.04` when the episode continues.

## Validation Artifacts

The repository includes committed run artifacts for quick evaluator inspection:

- `outputs/inference_baseline_run.txt`: full `[START]/[STEP]/[END]` trace across all 4 tasks
- `outputs/task_score_summary.json`: measured per-task final scores

### Baseline Score Snapshot

| Task | Difficulty | Final Score |
| --- | --- | --- |
| `easy_task` | easy | `0.880` |
| `medium_task` | medium | `0.933` |
| `hard_task` | hard | `0.933` |
| `expert_task` | expert | `0.387` |

These numbers demonstrate that harder multi-root incidents are meaningfully more challenging, providing discriminative signal across task difficulty.

## Project Structure

```text
devops_incident_env/
+-- server/
|   +-- app.py
|   +-- environment.py
|   +-- __init__.py
+-- models.py
+-- tasks.py
+-- grader.py
+-- baseline.py
+-- client.py
+-- inference.py
+-- constants.py
+-- openenv.yaml
+-- requirements.txt
+-- Dockerfile
+-- README.md
+-- tests/
|   +-- test_environment.py
|   +-- test_fixes.py
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
- Anti-abuse reward shaping: invalid, redundant, and destructive actions do not earn positive reward and reduce grading quality.
- Strict typed schemas: actions, observations, tasks, and state are bounded by Pydantic models.
- Lightweight deployment: Docker image exposes port `8000` and supports validator-friendly routes.
- Submission-safe inference: `inference.py` uses the OpenAI Client, requires `HF_TOKEN`, and prints only the required structured stdout lines.

## Design Decisions

This environment uses dependency-aware reward shaping rather than simple pass/fail grading to better model real SRE behavior. Agents receive useful dense signal for investigation quality, correct root-cause diagnosis, safe remediation, and verification, while still being judged by a deterministic final score. This encourages causal debugging over symptom patching and improves learning stability on long-horizon incidents.
