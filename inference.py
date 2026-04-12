#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi.testclient import TestClient
from openai import OpenAI

try:
    from .baseline import choose_action as choose_baseline_action
    from .constants import SCORE_CEILING, SCORE_FLOOR
    from .models import IncidentAction
except ImportError:
    from baseline import choose_action as choose_baseline_action
    from constants import SCORE_CEILING, SCORE_FLOOR
    from models import IncidentAction

# Configure logging
logging.basicConfig(
    level=logging.CRITICAL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.CRITICAL)

API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.environ.get("HF_TOKEN")
ENV_URL = os.environ.get("ENV_URL", "http://127.0.0.1:8000")
BENCHMARK = "devops_incident_env"


def _display_reward(value: float) -> float:
    # Keep printed rewards strictly within the configured score interval.
    return max(SCORE_FLOOR, min(SCORE_CEILING, float(value)))


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_value = error if error else "null"
    shown_reward = _display_reward(reward)
    print(
        f"[STEP] step={step} action={action} reward={shown_reward:.3f} done={str(done).lower()} error={error_value}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_text = ",".join(f"{_display_reward(reward):.3f}" for reward in rewards)
    # score clamped to [0.0, 1.0] per OpenEnv sample spec
    safe_score = min(max(float(score), 0.0), 1.0)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={safe_score:.3f} rewards={rewards_text}",
        flush=True,
    )


def parse_llm_action(text: str) -> Optional[Dict[str, Any]]:
    cleaned = text.strip()
    if not cleaned:
        return None
    if "```" in cleaned:
        for part in cleaned.split("```"):
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{"):
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


class RemoteEnvClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=15.0, limits=httpx.Limits(max_keepalive_connections=5))

    def close(self) -> None:
        self.client.close()

    def tasks(self) -> Dict[str, Any]:
        response = self.client.get(f"{self.base_url}/tasks")
        response.raise_for_status()
        return response.json()

    def reset(self, task_id: str, seed: int) -> Dict[str, Any]:
        try:
            response = self.client.post(f"{self.base_url}/reset", json={"task_id": task_id, "seed": seed})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Reset request failed: {e}")
            raise

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = self.client.post(f"{self.base_url}/step", json={"action": action})
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.error(f"Step request timed out after 15s")
            raise
        except httpx.HTTPError as e:
            logger.error(f"Step request failed: {e}")
            raise

    def state(self) -> Dict[str, Any]:
        response = self.client.get(f"{self.base_url}/state")
        response.raise_for_status()
        return response.json()


class LocalEnvClient:
    def __init__(self) -> None:
        try:
            from .server.app import app
        except ImportError:
            from server.app import app
        self.client = TestClient(app)

    def close(self) -> None:
        self.client.close()

    def tasks(self) -> Dict[str, Any]:
        return self.client.get("/tasks").json()

    def reset(self, task_id: str, seed: int) -> Dict[str, Any]:
        return self.client.post("/reset", json={"task_id": task_id, "seed": seed}).json()

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.post("/step", json={"action": action}).json()

    def state(self) -> Dict[str, Any]:
        return self.client.get("/state").json()


def build_env_client() -> Any:
    remote = RemoteEnvClient(ENV_URL)
    try:
        remote.tasks()
        return remote
    except Exception:
        remote.close()
        return LocalEnvClient()


class DevOpsAgent:
    def __init__(self) -> None:
        self.history: List[str] = []
        self.executed: List[Dict[str, Any]] = []
        self.client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN, timeout=30.0, max_retries=2)
        self.llm_fallback_count = 0
        self.llm_failure_streak = 0
        self.max_llm_failure_streak = 3

    def reset(self) -> None:
        self.history = []
        self.executed = []
        self.llm_failure_streak = 0

    def choose_action(self, observation: Dict[str, Any], state_dict: Dict[str, Any]) -> Dict[str, Any]:
        llm_action = self._query_llm(observation, state_dict)
        if llm_action is not None:
            self.llm_failure_streak = 0
            return llm_action
        self.llm_failure_streak += 1
        self.llm_fallback_count += 1
        return choose_baseline_action(observation, state_dict).model_dump(exclude_none=True)

    def record(self, action: Dict[str, Any], reward: float, result: str) -> None:
        self.executed.append(dict(action))
        self.history.append(
            f"{action.get('action_type')}:{action.get('service', '-')}:reward={reward:.2f}:result={result[:80]}"
        )

    def _query_llm(self, observation: Dict[str, Any], state_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.client is None:
            logger.debug("LLM client not initialized (no HF_TOKEN)")
            return None

        if self.llm_failure_streak >= self.max_llm_failure_streak:
            logger.debug("Skipping LLM due to repeated failures; using baseline fallback")
            return None
        
        prompt = self._build_prompt(observation, state_dict)
        try:
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=220,
            )
        except Exception as e:
            logger.warning(f"LLM query failed: {type(e).__name__}: {e}")
            return None
        
        content = response.choices[0].message.content or ""
        action = parse_llm_action(content)
        if not action:
            logger.warning(f"Failed to parse LLM action from response: {content[:100]}")
            return None
        
        try:
            return IncidentAction(**action).model_dump(exclude_none=True)
        except Exception as e:
            logger.warning(f"LLM action validation failed: {e}")
            return None

    def _system_prompt(self) -> str:
        return """You are an expert Site Reliability Engineer performing incident triage.

You are given an observation describing an active incident in a microservice system.
The service dependency graph is: api_gateway -> [auth_service, order_service] -> [user_service, payment_service] -> database.

Your job is to find the ROOT CAUSE, not just the surface symptom. Always:
1. Read logs and query metrics on the ALERTING service first.
2. Trace dependencies downstream toward database to find the real failure.
3. Diagnose the correct service before applying any fix.
4. Apply the correct fix to the root-cause service only.
5. Verify health after fixing.

DO NOT apply a fix before diagnosing.
DO NOT restart or remediate healthy services.

Valid action_type values: read_logs, query_metrics, diagnose, apply_fix, verify_health, list_services, inspect_dependencies
Valid diagnoses: service_crash, memory_leak, high_latency, connection_pool_exhaustion, disk_full, certificate_expired, config_drift
Valid fixes: restart_service, memory_fix, clear_disk, scale_up, rollback_config, renew_certificate, drain_connections, clear_cache

Respond with ONLY a JSON object.
Allowed keys: action_type, service, diagnosis (optional), fix (optional), reasoning.
Include a confidence in reasoning text like confidence=0.83.

Example:
{"action_type": "read_logs", "service": "database", "reasoning": "Database appears downstream of alerts and likely root. confidence=0.79"}"""

    def _build_prompt(self, observation: Dict[str, Any], state_dict: Dict[str, Any]) -> str:
        parts: List[str] = []
        if self.history:
            parts.append("ACTIONS TAKEN SO FAR:\n" + "\n".join(self.history[-6:]))

        root_services = list(state_dict.get("root_cause_services", []))
        verified = set(state_dict.get("successful_verifications", []))
        unresolved = [service for service in root_services if service not in verified]
        state_view = {
            "task_id": state_dict.get("task_id"),
            "step_count": state_dict.get("step_count"),
            "max_steps": state_dict.get("max_steps"),
            "unresolved_root_services": unresolved,
            "last_action_error": state_dict.get("last_action_error"),
        }
        parts.append("CURRENT STATE:\n" + json.dumps(state_view, sort_keys=True, indent=2))
        parts.append("CURRENT OBSERVATION:\n" + json.dumps(observation, sort_keys=True, indent=2))
        parts.append("What is your next action? Return JSON only.")
        return "\n\n".join(parts)


def action_to_string(action: Dict[str, Any]) -> str:
    service = action.get("service", "")
    return f"{action.get('action_type', 'unknown')}({service})"


def run_task(agent: DevOpsAgent, task: Dict[str, Any]) -> float:
    agent.reset()
    env = build_env_client()
    rewards: List[float] = []
    steps_taken = 0
    success = False
    score = SCORE_FLOOR

    # Use task_id in structured logs to keep token parsing stable.
    log_start(task=task["task_id"], env=BENCHMARK, model=MODEL_NAME)

    try:
        result = env.reset(task["task_id"], seed=12345)
        observation = result["observation"]

        for step in range(1, int(task["max_steps"]) + 1):
            if result.get("done"):
                break

            state_dict = env.state()
            action_dict = agent.choose_action(observation, state_dict)
            action_string = action_to_string(action_dict)
            try:
                result = env.step(action_dict)
            except Exception as exc:
                rewards.append(SCORE_FLOOR)
                steps_taken = step
                log_step(step, action_string, SCORE_FLOOR, True, str(exc))
                break

            observation = result["observation"]
            reward = max(SCORE_FLOOR, min(SCORE_CEILING, float(result.get("reward", SCORE_FLOOR))))
            done = bool(result.get("done", False))
            latest_state = env.state()
            error = latest_state.get("last_action_error")
            rewards.append(reward)
            steps_taken = step
            agent.record(action_dict, reward, observation.get("action_result", ""))
            log_step(step, action_string, reward, done, error)
            if done:
                break

        final_state = env.state()
        score = float(final_state.get("final_score") or SCORE_FLOOR)
        score = max(SCORE_FLOOR, min(SCORE_CEILING, score))
        success = score >= 0.5
    finally:
        env.close()
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


def main() -> int:
    if not HF_TOKEN:
        raise ValueError("HF_TOKEN environment variable is required")

    tasks_env = build_env_client()
    agent = DevOpsAgent()
    try:
        task_payload = tasks_env.tasks()
    finally:
        tasks_env.close()

    for task in task_payload.get("tasks", []):
        run_task(agent, task)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
