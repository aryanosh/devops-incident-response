#!/usr/bin/env python3
# inference.py
# ============================================================
# DevOps Incident Response - Inference Script
# Meta PyTorch OpenEnv Hackathon | MANDATORY SUBMISSION FILE
# ============================================================
# REQUIRED ENV VARS:
#   API_BASE_URL  - LLM API endpoint
#   MODEL_NAME    - Model identifier
#   HF_TOKEN      - Hugging Face token
#   ENV_URL       - Your HF Space URL (default: http://localhost:8000)
# ============================================================

import os
import sys
import json
import time
import uuid
import requests
from openai import OpenAI

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "mistralai/Mistral-7B-Instruct-v0.2")
HF_TOKEN = os.environ.get("HF_TOKEN")
ENV_URL = os.environ.get("ENV_URL", "https://aryanosh-devops-incident-env.hf.space")

TASKS = ["easy_task", "medium_task", "hard_task"]
MAX_STEPS_PER_TASK = 15

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) responding to production incidents.
You have access to a distributed microservices system with 6 services:
- api_gateway, auth_service, user_service, order_service, payment_service, database

You can perform these actions (respond ONLY with valid JSON):
1. {"action_type": "read_logs",    "service": ""}
2. {"action_type": "query_metrics","service": ""}
3. {"action_type": "diagnose",     "service": "", "diagnosis": ""}
4. {"action_type": "apply_fix",    "service": "", "fix": ""}
5. {"action_type": "verify_health","service": ""}

Valid diagnosis values: service_crash, memory_leak, high_latency, connection_pool_exhaustion, disk_full, certificate_expired, config_drift, unknown
Valid fix values: restart_service, scale_service, rollback_config, clear_disk, rotate_certificate, memory_fix, connection_pool_fix, no_action

Strategy:
1. Read logs from services with active alerts FIRST
2. Query metrics to confirm your suspicion
3. Submit a diagnose action with your root cause finding
4. Apply the appropriate fix
5. Verify health to confirm recovery

Service dependency chain: api_gateway → auth_service → user_service → database
                          api_gateway → order_service → payment_service → database

IMPORTANT: Respond with ONLY the JSON action object, nothing else."""


# ─────────────────────────────────────────────
# AGENT CLASS
# ─────────────────────────────────────────────
class DevOpsAgent:
    def __init__(self):
        if not HF_TOKEN:
            print("[WARN] HF_TOKEN not set. Using unauthenticated access.", file=sys.stderr)
        self.client = OpenAI(
            base_url=API_BASE_URL,
            api_key=HF_TOKEN or "hf_placeholder"
        )
        self.conversation_history = []

    def reset_conversation(self):
        self.conversation_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def observe(self, observation: dict) -> str:
        """Format observation dict into a readable string for the LLM."""
        parts = []

        # Step progress
        parts.append(f"[Step {observation.get('step_number', '?')}/{observation.get('max_steps', '?')}]")

        # Action result
        if observation.get("action_result"):
            parts.append(f"ACTION RESULT: {observation['action_result']}")

        # Active alerts
        alerts = observation.get("active_alerts", [])
        if alerts:
            alert_strs = [f"  [{a['severity'].upper()}] {a['service']}: {a['title']}" for a in alerts]
            parts.append("ACTIVE ALERTS:\n" + "\n".join(alert_strs))

        # Service summaries
        summaries = observation.get("service_summaries", [])
        if summaries:
            sum_strs = [f"  {s['service_name']}: {s['status']}" for s in summaries]
            parts.append("SERVICE STATUS:\n" + "\n".join(sum_strs))

        # Logs
        logs = observation.get("logs", [])
        if logs:
            log_strs = [f"  [{l['timestamp']}] [{l['level']}] {l['service']}: {l['message']}" for l in logs]
            parts.append("LOGS:\n" + "\n".join(log_strs))

        # Metrics
        metrics = observation.get("metrics")
        if metrics:
            parts.append(
                f"METRICS for {metrics['service_name']}:\n"
                f"  CPU: {metrics['cpu_percent']}% | Memory: {metrics['memory_mb']}/{metrics['memory_limit_mb']} MB\n"
                f"  Latency: {metrics['request_latency_ms']}ms | Error Rate: {metrics['error_rate_percent']}%\n"
                f"  Status: {metrics['status']}"
            )

        # Message
        if observation.get("message"):
            parts.append(f"SYSTEM: {observation['message']}")

        return "\n\n".join(parts)

    def act(self, observation_text: str) -> dict:
        """Call LLM and parse JSON action."""
        self.conversation_history.append({
            "role": "user",
            "content": observation_text
        })

        try:
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=self.conversation_history,
                max_tokens=256,
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
            self.conversation_history.append({"role": "assistant", "content": raw})
            return self._parse_action(raw)
        except Exception as e:
            print(f"[WARN] LLM call failed: {e}", file=sys.stderr)
            # Fallback: investigate first alert's service
            step = len(self.conversation_history)
            return self.fallback_policy(step)

    def _parse_action(self, text: str) -> dict:
        """Safely parse action JSON from LLM output."""
        # Try direct parse
        try:
            obj = json.loads(text)
            if "action_type" in obj and "service" in obj:
                return obj
        except json.JSONDecodeError:
            pass

        # Find JSON block in text
        import re
        match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
                if "action_type" in obj and "service" in obj:
                    return obj
            except json.JSONDecodeError:
                pass

        # Fallback action
        return {"action_type": "read_logs", "service": "api_gateway", "reasoning": "Parse error - defaulting to initial investigation"}
    def fallback_policy(self, step):
        sequence = [
        {"action_type": "read_logs", "service": "api_gateway"},
        {"action_type": "query_metrics", "service": "api_gateway"},
        {"action_type": "diagnose", "service": "api_gateway", "diagnosis": "service_crash"},
        {"action_type": "apply_fix", "service": "api_gateway", "fix": "restart_service"},
        {"action_type": "verify_health", "service": "api_gateway"},
        ]
        return sequence[min(step, len(sequence)-1)]

# ─────────────────────────────────────────────
# ENVIRONMENT CLIENT
# ─────────────────────────────────────────────
def env_reset(task_id: str) -> dict:
    """Call environment reset endpoint."""
    resp = requests.post(
        f"{ENV_URL}/reset",
        json={"task_id": task_id},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()

def env_step(action: dict) -> dict:
    """Call environment step endpoint."""
    resp = requests.post(
        f"{ENV_URL}/step",
        json={"action": action},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()

def env_state() -> dict:
    """Call environment state endpoint."""
    resp = requests.get(f"{ENV_URL}/state", timeout=30)
    resp.raise_for_status()
    return resp.json()


# ─────────────────────────────────────────────
# TASK RUNNER
# ─────────────────────────────────────────────
def run_task(agent: DevOpsAgent, task_id: str) -> dict:
    """Run one complete episode and return summary."""
    agent.reset_conversation()
    episode_id = str(uuid.uuid4())[:8]

    # ── [START] LOG ──
    print(json.dumps({"type": "[START]", "task_id": task_id, "episode_id": episode_id}), flush=True)

    # Reset environment
    obs = env_reset(task_id)

    step_num = 0
    final_reward = 0.0
    done = False

    while not done and step_num < MAX_STEPS_PER_TASK:
        step_num += 1

        # Format observation for LLM
        obs_text = agent.observe(obs)

        # Get action from agent
        action = agent.act(obs_text)

        # Execute action in environment
        try:
            result = env_step(action)
        except Exception as e:
            print(f"[WARN] Step failed: {e}", file=sys.stderr)
            break

        obs = result.get("observation", result)
        reward = obs.get("reward", 0.0)
        done = obs.get("done", False)
        final_reward = reward

        # ── [STEP] LOG ──
        print(json.dumps({
            "type": "[STEP]",
            "step": step_num,
            "action": action,
            "reward": round(reward, 4),
            "done": done
        }), flush=True)

        if done:
            break

    # Get final state for resolved status
    try:
        state = env_state()
        resolved = state.get("is_resolved", False)
    except Exception:
        resolved = False

    # ── [END] LOG ──
    print(json.dumps({
        "type": "[END]",
        "task_id": task_id,
        "episode_id": episode_id,
        "total_steps": step_num,
        "final_reward": round(final_reward, 4),
        "resolved": resolved
    }), flush=True)

    return {
        "task_id": task_id,
        "steps": step_num,
        "final_reward": round(final_reward, 4),
        "resolved": resolved
    }


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    """Run all 3 tasks and print summary."""
    print(f"[INFO] Starting DevOps Incident Response evaluation", file=sys.stderr)
    print(f"[INFO] ENV_URL: {ENV_URL}", file=sys.stderr)
    print(f"[INFO] MODEL:   {MODEL_NAME}", file=sys.stderr)

    # Verify environment is running
    try:
        health = requests.get(f"{ENV_URL}/health", timeout=10)
        print(f"[INFO] Environment health: {health.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Cannot reach environment at {ENV_URL}: {e}", file=sys.stderr)
        sys.exit(1)

    agent = DevOpsAgent()
    results = []
    start_time = time.time()

    for task_id in TASKS:
        print(f"\n[INFO] Running task: {task_id}", file=sys.stderr)
        try:
            result = run_task(agent, task_id)
            results.append(result)
            print(f"[INFO] {task_id}: reward={result['final_reward']}, resolved={result['resolved']}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Task {task_id} failed: {e}", file=sys.stderr)
            results.append({"task_id": task_id, "final_reward": 0.0, "resolved": False, "error": str(e)})

    elapsed = round(time.time() - start_time, 2)
    avg_reward = round(sum(r["final_reward"] for r in results) / len(results), 4) if results else 0.0

    print(f"\n[INFO] Evaluation complete in {elapsed}s", file=sys.stderr)
    print(f"[INFO] Average reward: {avg_reward}", file=sys.stderr)
    for r in results:
        print(f"[INFO]   {r['task_id']}: {r['final_reward']}", file=sys.stderr)

    return avg_reward


if __name__ == "__main__":
    main()
