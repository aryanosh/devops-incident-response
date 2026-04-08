---
Title: DevOps Incident Response OpenEnv
emoji: 🔧
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
---

# DevOps Incident Response - OpenEnv Environment

This environment simulates production incident response in a six-service microservice
stack. An agent acts like an on-call SRE: it investigates alerts, reads logs,
inspects metrics, traces dependencies, identifies the root cause, applies a fix,
and verifies recovery. The benchmark is intended to test operational reasoning,
not just single-step tool calling.

## Motivation

Real incidents rarely expose the root cause directly. Symptoms often appear in one
service while the actual failure lives downstream, and blind remediation can waste
time or reduce system safety. This environment evaluates whether an agent can:

- investigate before acting
- distinguish symptoms from root causes
- use dependency structure to narrow the search space
- apply a diagnosis-aligned remediation
- verify that the system is healthy after intervention

The environment uses dense per-step rewards and a final grader score in `[0.0, 1.0]`
to separate weak, partial, and strong trajectories.

## Services

The environment models a production microservice architecture with six services:

- `api_gateway` - Entry point for user requests
- `auth_service` - Authentication and authorization
- `user_service` - User data management
- `order_service` - Order processing
- `payment_service` - Payment processing
- `database` - Shared data layer

### Dependency Graph

```
┌─────────────┐
│ api_gateway │──────┐
└─────────────┘      │
       │             │
       ▼             ▼
┌──────────────┐ ┌───────────────┐
│ auth_service │ │ order_service │
└──────────────┘ └───────────────┘
       │                │
       │                ├──────────┐
       │                │          │
       ▼                ▼          ▼
┌──────────────┐ ┌─────────────────┐
│ user_service │ │ payment_service │
└──────────────┘ └─────────────────┘
       │                │
       │                │
       ▼                ▼
    ┌──────────┐
    │ database │
    └──────────┘
```

All services depend on `database` directly or indirectly. Failures in downstream services cascade upstream, creating complex diagnostic challenges.

## Action Space

The agent can emit the following typed actions:

- `list_services`
  Returns a snapshot of all services and their current health status.
- `check_dependencies`
  Returns the service dependency graph used for root-cause tracing.
- `read_logs(service)`
  Retrieves recent logs for one service.
- `query_metrics(service)`
  Retrieves metrics such as memory, latency, connection pool usage, and disk usage.
- `diagnose(service, diagnosis)`
  Commits to a diagnosis for a target service.
- `apply_fix(service, fix)`
  Applies a candidate remediation to a target service.
- `verify_health(service)`
  Checks whether the target service has recovered after remediation.

Supported diagnoses:

- `service_crash`
- `memory_leak`
- `high_latency`
- `connection_pool_exhaustion`
- `disk_full`
- `certificate_expired`
- `config_drift`

Supported fixes:

- `restart_service`
- `memory_fix`
- `scale_horizontally`
- `flush_connection_pool`
- `clear_disk`
- `renew_certificate`
- `rollback_config`
- `increase_timeout`

## Observation Space

Each step returns a structured observation with the fields needed for incident
response:

- `message`: natural-language summary of the current situation or final grading
- `step_number`: current timestep within the episode
- `reward`: dense reward for the most recent action
- `done`: whether the episode is complete
- `success`: whether the most recent action succeeded
- `action_result`: action-specific feedback
- `active_alerts`: current alerts with service, severity, title, and description
- `service_summaries`: per-service status snapshot
- `logs`: recent log lines returned by `read_logs`
- `metrics`: service metrics returned by `query_metrics`
- `dependency_graph`: dependency map returned by `check_dependencies`

## Task Descriptions

The benchmark contains four tasks with increasing difficulty.

- `easy_task`: Single Service Crash
  The `api_gateway` is down because of a direct service crash.
  Expected difficulty: easy. The root cause is local, the alerts are explicit, and
  the optimal path is short.
  
- `medium_task`: Memory Leak with Cascading Symptoms
  `order_service` develops a memory leak and downstream symptoms appear around it.
  Expected difficulty: medium. The agent must combine logs and metrics instead of
  reacting to one obvious alert.
  
- `hard_task`: Cascading Failure Chain with Red Herrings
  Surface failures appear in upstream services, but the real root cause is
  `database` disk exhaustion. Misleading symptoms (red herrings) appear in other
  services to confuse naive investigation strategies.
  Expected difficulty: hard. The agent must use dependency-aware investigation to
  trace the chain back to the actual source of failure while avoiding false leads.
  
- `expert_task`: Multi-Root Cascading Failure
  Multiple simultaneous root causes (`database` disk exhaustion + `auth_service`
  certificate expiration) with complex cascading effects and red herrings across
  all service tiers.
  Expected difficulty: expert. Requires parallel investigation, multi-hop reasoning,
  and the ability to diagnose and fix multiple independent failures.

## Scoring

The final score rewards correct and efficient incident handling while penalizing
blind fixes. It combines four weighted components:

### Grader Components

1. **Root Cause Identification (35%)**:
   - Correct diagnosis with supporting evidence (logs + metrics)
   - Partial credit for investigation without diagnosis
   - Task-specific evidence requirements (harder tasks require more thorough investigation)

2. **Resolution Quality (30%)**:
   - Correct fix applied to root cause (70%)
   - Post-fix health verification (30%)

3. **Efficiency (20%)**:
   - Rewards optimal step count
   - Linear degradation up to 2x optimal steps
   - Further degradation beyond 2x optimal

4. **Safety (15%)**:
   - Penalties for destructive actions on healthy services (-40% per action)
   - Penalties for incorrect fixes (-5% per fix)
   - Penalties for blind fixes without investigation (-10% per fix)

5. **Time Pressure (penalty)**:
   - Additional penalty for delays beyond 1.5x optimal steps
   - Simulates realistic incident escalation

### Dense Rewards

The environment also provides dense intermediate rewards for productive steps such
as reading logs, querying metrics, making a correct diagnosis, applying the right
fix, and verifying health.

## Key Features

- **Verification-aware resolution**: Incidents require explicit post-fix health checks
- **Dependency-aware root cause tracing**: Complex dependency graphs across microservices
- **Dense reward shaping**: Partial credit for productive investigation steps
- **Safety penalties**: Penalties for blind fixes and destructive actions
- **Realistic cascading failures**: Multi-service outages with red herrings
- **Multi-root complexity**: Expert task with multiple simultaneous failures
- **Time pressure**: Score degradation for delayed resolution
- **Red herring symptoms**: Misleading signals that test diagnostic reasoning

## Setup

### Local Python

```bash
pip install -r server/requirements.txt
```

### Run Locally

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker build -t devops-incident-response .
docker run -p 8000:8000 devops-incident-response
```

## Usage

### Validate the Environment

```bash
openenv validate --verbose
openenv validate --url http://localhost:8000
```

### Run the Baseline Inference Client

```bash
export HF_TOKEN=your_token
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
export ENV_URL=http://localhost:8000
python inference.py
```

The inference script prints logs in the required format:

```text
[START] ...
[STEP] ...
[END] ...
```

## Baseline Scores

Representative baseline results from the included inference runner using
Qwen/Qwen2.5-72B-Instruct:

- Easy: `0.933` in 5 steps
- Medium: `0.980` in 6 steps
- Hard: `0.750-0.850` in 10-15 steps (with red herrings)
- Expert: `0.600-0.700` in 18-25 steps (multi-root challenge)

### Score Variance Validation

Additional controlled evaluation scenarios used to verify grader score separation:

- `easy_weak`: `0.1500` (blind fix, no investigation)
- `easy_partial`: `0.6733` (investigation, no diagnosis)
- `easy_optimal`: `0.9333` (full investigation + diagnosis)
- `medium_partial`: `0.4300` (symptom fix, not root cause)
- `hard_direct`: `0.8600` (direct root investigation)
- `hard_trace`: `0.9286` (dependency tracing)

These results show that the grader separates weak, partial, and high-quality
trajectories rather than collapsing to a constant perfect score.

## Testing

Run the test suite to verify environment correctness:

```bash
pytest tests/ -v
```

The test suite covers:
- Optimal trajectories for all tasks
- Grader score variance and separation
- Safety penalties and destructive actions
- State management and reset behavior
- Observation space completeness
