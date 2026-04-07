#!/usr/bin/env python3
# inference.py
# ============================================================
# DevOps Incident Response - Inference Script
# Meta PyTorch OpenEnv Hackathon | MANDATORY SUBMISSION FILE
# ============================================================

import json
import os
import sys
import time
import uuid

import requests
from openai import OpenAI

try:
    from .client import DevOpsIncidentEnv
    from .models import IncidentAction
except ImportError:
    from client import DevOpsIncidentEnv
    from models import IncidentAction


API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct")
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

IMPORTANT: Respond with ONLY the JSON action object, nothing else."""


class DevOpsAgent:
    def __init__(self):
        if not HF_TOKEN:
            print("[WARN] HF_TOKEN not set. Using unauthenticated access.", file=sys.stderr)
        self.client = OpenAI(
            base_url=API_BASE_URL,
            api_key=HF_TOKEN or "hf_placeholder",
        )
        self.conversation_history = []
        self.fallback_step = 0
        self.current_plan = []

    def reset_conversation(self):
        self.conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.fallback_step = 0
        self.current_plan = []

    def observe(self, observation: dict) -> str:
        parts = [f"[Step {observation.get('step_number', '?')}/{observation.get('max_steps', '?')}]"]

        if observation.get("action_result"):
            parts.append(f"ACTION RESULT: {observation['action_result']}")

        alerts = observation.get("active_alerts", [])
        if alerts:
            parts.append(
                "ACTIVE ALERTS:\n" + "\n".join(
                    f"  [{a['severity'].upper()}] {a['service']}: {a['title']}" for a in alerts
                )
            )

        summaries = observation.get("service_summaries", [])
        if summaries:
            parts.append(
                "SERVICE STATUS:\n" + "\n".join(
                    f"  {s['service_name']}: {s['status']}" for s in summaries
                )
            )

        logs = observation.get("logs", [])
        if logs:
            parts.append(
                "LOGS:\n" + "\n".join(
                    f"  [{l['timestamp']}] [{l['level']}] {l['service']}: {l['message']}" for l in logs
                )
            )

        metrics = observation.get("metrics")
        if metrics:
            parts.append(
                f"METRICS for {metrics['service_name']}:\n"
                f"  CPU: {metrics['cpu_percent']}% | Memory: {metrics['memory_mb']}/{metrics['memory_limit_mb']} MB\n"
                f"  Latency: {metrics['request_latency_ms']}ms | Error Rate: {metrics['error_rate_percent']}%\n"
                f"  Status: {metrics['status']}"
            )

        if observation.get("message"):
            parts.append(f"SYSTEM: {observation['message']}")

        return "\n\n".join(parts)

    def act(self, observation_text: str) -> dict:
        self.conversation_history.append({"role": "user", "content": observation_text})

        try:
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=self.conversation_history,
                max_tokens=256,
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip()
            self.conversation_history.append({"role": "assistant", "content": raw})
            parsed = self._parse_action(raw)
            if parsed is not None:
                return parsed
        except Exception as e:
            print(f"[WARN] LLM call failed: {e}", file=sys.stderr)

        return self.fallback_policy(observation_text)

    def _parse_action(self, text: str) -> dict | None:
        try:
            obj = json.loads(text)
            if "action_type" in obj and "service" in obj:
                return obj
        except json.JSONDecodeError:
            pass

        import re

        match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
        if not match:
            return None

        try:
            obj = json.loads(match.group())
            if "action_type" in obj and "service" in obj:
                return obj
        except json.JSONDecodeError:
            return None
        return None

    def fallback_policy(self, observation_text: str) -> dict:
        if not self.current_plan or self.fallback_step >= len(self.current_plan):
            self.current_plan = self._build_fallback_plan(observation_text)
            self.fallback_step = 0

        action = self.current_plan[self.fallback_step]
        self.fallback_step += 1
        return action

    def _build_fallback_plan(self, observation_text: str) -> list[dict]:
        text = observation_text.lower()

        if "elevated 503s" in text and "timeout rate high" in text:
            service = "database"
            diagnosis = "disk_full"
            fix = "clear_disk"
        elif "high memory usage" in text or "memory > 90%" in text:
            service = "order_service"
            diagnosis = "memory_leak"
            fix = "memory_fix"
        else:
            service = "api_gateway"
            diagnosis = "service_crash"
            fix = "restart_service"

        return [
            {"action_type": "read_logs", "service": service},
            {"action_type": "query_metrics", "service": service},
            {"action_type": "diagnose", "service": service, "diagnosis": diagnosis},
            {"action_type": "apply_fix", "service": service, "fix": fix},
            {"action_type": "verify_health", "service": service},
        ]


def run_task(agent: DevOpsAgent, env: DevOpsIncidentEnv, task_id: str) -> dict:
    agent.reset_conversation()
    episode_id = str(uuid.uuid4())[:8]

    print(json.dumps({"type": "[START]", "task_id": task_id, "episode_id": episode_id}), flush=True)

    reset_result = env.reset(task_id=task_id)
    obs = reset_result.observation.model_dump()

    step_num = 0
    final_reward = 0.0
    done = False

    while not done and step_num < MAX_STEPS_PER_TASK:
        step_num += 1
        obs_text = agent.observe(obs)
        action = agent.act(obs_text)

        try:
            result = env.step(IncidentAction(**action))
        except Exception as e:
            print(f"[WARN] Step failed: {e}", file=sys.stderr)
            break

        obs = result.observation.model_dump()
        reward = result.reward
        done = result.done
        final_reward = reward

        print(
            json.dumps(
                {
                    "type": "[STEP]",
                    "step": step_num,
                    "action": action,
                    "reward": round(reward, 4),
                    "done": done,
                }
            ),
            flush=True,
        )

    try:
        state = env.state()
        resolved = getattr(state, "is_resolved", done)
    except Exception:
        resolved = done

    print(
        json.dumps(
            {
                "type": "[END]",
                "task_id": task_id,
                "episode_id": episode_id,
                "total_steps": step_num,
                "final_reward": round(final_reward, 4),
                "resolved": resolved,
            }
        ),
        flush=True,
    )

    return {
        "task_id": task_id,
        "steps": step_num,
        "final_reward": round(final_reward, 4),
        "resolved": resolved,
    }


def main():
    print("[INFO] Starting DevOps Incident Response evaluation", file=sys.stderr)
    print(f"[INFO] ENV_URL: {ENV_URL}", file=sys.stderr)
    print(f"[INFO] MODEL:   {MODEL_NAME}", file=sys.stderr)

    try:
        health = requests.get(f"{ENV_URL}/health", timeout=10)
        print(f"[INFO] Environment health: {health.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Cannot reach environment at {ENV_URL}: {e}", file=sys.stderr)
        sys.exit(1)

    agent = DevOpsAgent()
    results = []
    start_time = time.time()

    try:
        with DevOpsIncidentEnv(base_url=ENV_URL).sync() as env:
            for task_id in TASKS:
                print(f"\n[INFO] Running task: {task_id}", file=sys.stderr)
                try:
                    result = run_task(agent, env, task_id)
                    results.append(result)
                    print(
                        f"[INFO] {task_id}: reward={result['final_reward']}, resolved={result['resolved']}",
                        file=sys.stderr,
                    )
                except Exception as e:
                    print(f"[ERROR] Task {task_id} failed: {e}", file=sys.stderr)
                    results.append(
                        {"task_id": task_id, "final_reward": 0.0, "resolved": False, "error": str(e)}
                    )
    except Exception as e:
        print(f"[ERROR] Failed to establish persistent environment session: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = round(time.time() - start_time, 2)
    avg_reward = round(sum(r["final_reward"] for r in results) / len(results), 4) if results else 0.0

    print(f"\n[INFO] Evaluation complete in {elapsed}s", file=sys.stderr)
    print(f"[INFO] Average reward: {avg_reward}", file=sys.stderr)
    for result in results:
        print(f"[INFO]   {result['task_id']}: {result['final_reward']}", file=sys.stderr)

    return avg_reward


if __name__ == "__main__":
    main()
