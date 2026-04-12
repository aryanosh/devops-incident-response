#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi.testclient import TestClient
from openai import OpenAI

try:
    from .baseline import choose_action as choose_baseline_action
    from .models import IncidentAction
except ImportError:
    from baseline import choose_action as choose_baseline_action
    from models import IncidentAction

API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
ENV_URL = os.environ.get("ENV_URL", "http://127.0.0.1:7860")
BENCHMARK = "devops-incident-response"


def _display_reward(value: float) -> float:
    # Keep printed rewards strictly below 1.00 so 2dp formatting never rounds up to 1.00.
    return max(0.0, min(0.99, float(value)))


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_value = error if error else "null"
    shown_reward = _display_reward(reward)
    print(
        f"[STEP] step={step} action={action} reward={shown_reward:.2f} done={str(done).lower()} error={error_value}",
        flush=True,
    )


def log_end(success: bool, steps: int, rewards: List[float]) -> None:
    rewards_text = ",".join(f"{_display_reward(reward):.2f}" for reward in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} rewards={rewards_text}",
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
        self.client = httpx.Client(timeout=10.0)

    def close(self) -> None:
        self.client.close()

    def tasks(self) -> Dict[str, Any]:
        return self.client.get(f"{self.base_url}/tasks").json()

    def reset(self, task_id: str, seed: int) -> Dict[str, Any]:
        response = self.client.post(f"{self.base_url}/reset", json={"task_id": task_id, "seed": seed})
        response.raise_for_status()
        return response.json()

    def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.post(f"{self.base_url}/step", json={"action": action})
        response.raise_for_status()
        return response.json()

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
        self.client = (
            OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN, timeout=30.0, max_retries=2)
            if HF_TOKEN
            else None
        )

    def reset(self) -> None:
        self.history = []
        self.executed = []

    def choose_action(self, observation: Dict[str, Any], state_dict: Dict[str, Any]) -> Dict[str, Any]:
        llm_action = self._query_llm(observation)
        if llm_action is not None:
            return llm_action
        return choose_baseline_action(observation, state_dict).model_dump(exclude_none=True)

    def record(self, action: Dict[str, Any], reward: float, result: str) -> None:
        self.executed.append(dict(action))
        self.history.append(
            f"{action.get('action_type')}:{action.get('service', '-')}:reward={reward:.2f}:result={result[:80]}"
        )

    def _query_llm(self, observation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.client is None:
            return None
        prompt = self._build_prompt(observation)
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
        except Exception:
            return None
        content = response.choices[0].message.content or ""
        action = parse_llm_action(content)
        if not action:
            return None
        try:
            return IncidentAction(**action).model_dump(exclude_none=True)
        except Exception:
            return None

    def _system_prompt(self) -> str:
        return (
            "You are an expert SRE. Return JSON only. "
            "Valid actions are read_logs, query_metrics, diagnose, apply_fix, verify_health, "
            "list_services, inspect_dependencies."
        )

    def _build_prompt(self, observation: Dict[str, Any]) -> str:
        return json.dumps(observation, sort_keys=True)


def action_to_string(action: Dict[str, Any]) -> str:
    service = action.get("service", "")
    return f"{action.get('action_type', 'unknown')}({service})"


def run_task(agent: DevOpsAgent, env: Any, task: Dict[str, Any]) -> float:
    agent.reset()
    rewards: List[float] = []
    steps_taken = 0
    success = False

    log_start(task=task["name"], env=BENCHMARK, model=MODEL_NAME)

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
            rewards.append(0.0)
            steps_taken = step
            log_step(step, action_string, 0.0, True, str(exc))
            break

        observation = result["observation"]
        reward = max(0.0, min(1.0, float(result.get("reward", 0.0))))
        done = bool(result.get("done", False))
        error = None if observation.get("success", True) else observation.get("action_result", "error")
        rewards.append(reward)
        steps_taken = step
        agent.record(action_dict, reward, observation.get("action_result", ""))
        log_step(step, action_string, reward, done, error)
        if done:
            break

    final_state = env.state()
    score = float(final_state.get("final_score") or 0.001)
    score = max(0.001, min(0.999, score))
    success = score >= 0.5
    log_end(success=success, steps=steps_taken, rewards=rewards)
    return score


def main() -> int:
    env = build_env_client()
    agent = DevOpsAgent()
    try:
        task_payload = env.tasks()
        for task in task_payload.get("tasks", []):
            run_task(agent, env, task)
    finally:
        env.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
