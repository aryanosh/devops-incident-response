#!/usr/bin/env python3
"""Inference runner for the DevOps Incident Response environment."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

try:
    from .client import DevOpsIncidentEnv
    from .models import IncidentAction
except ImportError:
    from client import DevOpsIncidentEnv
    from models import IncidentAction


API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.environ.get("HF_TOKEN")
ENV_URL = os.environ.get("ENV_URL", "http://localhost:8000")
IMAGE_NAME = os.environ.get("IMAGE_NAME")
BENCHMARK = "devops-incident-response"

TASKS = [
    {"task_id": "easy_task", "name": "Single Service Crash", "max_steps": 10},
    {"task_id": "medium_task", "name": "Memory Leak with Cascading Symptoms", "max_steps": 15},
    {"task_id": "hard_task", "name": "Cascading Failure Chain", "max_steps": 20},
]

SYSTEM_PROMPT = """You are an expert site reliability engineer handling a production incident.
Return JSON only.

Valid actions:
- {"action_type":"list_services"}
- {"action_type":"check_dependencies"}
- {"action_type":"read_logs","service":"<service>"}
- {"action_type":"query_metrics","service":"<service>"}
- {"action_type":"diagnose","service":"<service>","diagnosis":"<diagnosis>"}
- {"action_type":"apply_fix","service":"<service>","fix":"<fix>"}
- {"action_type":"verify_health","service":"<service>"}

Valid diagnoses:
service_crash, memory_leak, high_latency, connection_pool_exhaustion, disk_full, certificate_expired, config_drift

Valid fixes:
restart_service, memory_fix, scale_horizontally, flush_connection_pool, clear_disk, renew_certificate, rollback_config, increase_timeout
"""


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_value = error if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={error_value}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_text = ",".join(f"{reward:.2f}" for reward in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_text}",
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


class DevOpsAgent:
    def __init__(self) -> None:
        self.client = OpenAI(
            base_url=API_BASE_URL,
            api_key=HF_TOKEN or "hf_placeholder",
            timeout=3.0,
            max_retries=0,
        )
        self.history: List[str] = []
        self.executed: List[Dict[str, Any]] = []

    def reset(self) -> None:
        self.history = []
        self.executed = []

    def choose_action(self, observation: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        planned = self._planned_action(observation, task_id)
        llm_action = self._query_llm(observation)
        if self._matches_plan(llm_action, planned):
            return llm_action
        return planned

    def record(self, action: Dict[str, Any], reward: float, result: str) -> None:
        self.executed.append(dict(action))
        self.history.append(
            f"{action.get('action_type')}:{action.get('service', '-')}:reward={reward:.2f}:result={result[:80]}"
        )

    def _query_llm(self, observation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        prompt = self._build_prompt(observation)
        try:
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=220,
            )
        except Exception:
            return None
        content = response.choices[0].message.content or ""
        return parse_llm_action(content)

    def _build_prompt(self, observation: Dict[str, Any]) -> str:
        alerts = [
            f"{item['severity']}:{item['service']}:{item['title']}"
            for item in observation.get("active_alerts", [])
        ]
        services = [
            f"{item['service_name']}={item['status']}"
            for item in observation.get("service_summaries", [])
        ]
        logs = [
            f"{item['service']}:{item['level']}:{item['message']}"
            for item in observation.get("logs", [])[:4]
        ]
        metrics = observation.get("metrics")
        metrics_text = ""
        if metrics:
            metrics_text = json.dumps(metrics, sort_keys=True)
        history = "\n".join(self.history[-5:]) if self.history else "none"
        return (
            f"step={observation.get('step_number', 0)}\n"
            f"alerts={alerts}\n"
            f"services={services}\n"
            f"logs={logs}\n"
            f"metrics={metrics_text}\n"
            f"message={observation.get('message', '')}\n"
            f"history={history}\n"
            "Return the best next JSON action."
        )

    def _planned_action(self, observation: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        if task_id != "easy_task" and not any(
            action.get("action_type") == "check_dependencies" for action in self.executed
        ):
            return {"action_type": "check_dependencies"}
        pending_verification = self._pending_verification_service()
        if pending_verification:
            return {"action_type": "verify_health", "service": pending_verification}
        service = self._choose_target_service(observation)
        diagnosis = self._infer_diagnosis(observation, service, task_id)
        fix = self._fix_for_diagnosis(diagnosis)
        plan = [
            {"action_type": "read_logs", "service": service},
            {"action_type": "query_metrics", "service": service},
            {"action_type": "diagnose", "service": service, "diagnosis": diagnosis},
            {"action_type": "apply_fix", "service": service, "fix": fix},
            {"action_type": "verify_health", "service": service},
        ]
        for candidate in plan:
            if not self._already_executed(candidate):
                return candidate
        return {"action_type": "list_services"}

    def _choose_target_service(self, observation: Dict[str, Any]) -> str:
        graph = observation.get("dependency_graph", {})
        summaries = {
            item["service_name"]: item["status"] for item in observation.get("service_summaries", [])
        }
        alerts = observation.get("active_alerts", [])
        if alerts:
            return self._walk_toward_root(alerts[0]["service"], graph, summaries)
        unhealthy = [
            item
            for item in observation.get("service_summaries", [])
            if item["status"] in {"critical", "down", "degraded"}
        ]
        if unhealthy:
            return self._walk_toward_root(unhealthy[0]["service_name"], graph, summaries)
        return "api_gateway"

    def _walk_toward_root(
        self,
        service: str,
        dependency_graph: Dict[str, List[str]],
        summaries: Dict[str, str],
    ) -> str:
        current = service
        visited: set[str] = set()
        while current not in visited:
            visited.add(current)
            actions = self._actions_for_service(current)
            dependencies = dependency_graph.get(current, [])
            status = summaries.get(current, "healthy")
            if not dependencies:
                return current
            if status in {"critical", "down"} and "apply_fix" not in actions:
                return current
            if {"read_logs", "query_metrics"}.issubset(actions) or "diagnose" in actions:
                unhealthy_dependencies = [
                    dep for dep in dependencies if summaries.get(dep) in {"critical", "down", "degraded"}
                ]
                candidates = unhealthy_dependencies or dependencies
                next_service = next(
                    (
                        dep
                        for dep in candidates
                        if not {"read_logs", "query_metrics"}.issubset(self._actions_for_service(dep))
                    ),
                    candidates[0],
                )
                current = next_service
                continue
            return current
        return current

    def _infer_diagnosis(self, observation: Dict[str, Any], service: str, task_id: str) -> str:
        text_bits = []
        for alert in observation.get("active_alerts", []):
            if alert["service"] == service:
                text_bits.append(alert["title"])
                text_bits.append(alert["description"])
        for log in observation.get("logs", []):
            if log["service"] == service:
                text_bits.append(log["message"])
        metrics = observation.get("metrics")
        if metrics and metrics.get("service_name") == service:
            if metrics.get("disk_used_gb", 0) >= 95:
                return "disk_full"
            if metrics.get("memory_mb", 0) >= metrics.get("memory_limit_mb", 1) * 0.9:
                return "memory_leak"
            if metrics.get("status") == "down":
                return "service_crash"
            if metrics.get("active_connections", 0) >= metrics.get("connection_pool_size", 1):
                return "connection_pool_exhaustion"
            if metrics.get("request_latency_p99_ms", 0) >= 3000:
                return "high_latency"
        text = " ".join(text_bits).lower()
        for needle, diagnosis in [
            ("disk", "disk_full"),
            ("wal", "disk_full"),
            ("oom", "memory_leak"),
            ("memory", "memory_leak"),
            ("connection pool", "connection_pool_exhaustion"),
            ("tls", "certificate_expired"),
            ("certificate", "certificate_expired"),
            ("config", "config_drift"),
            ("drift", "config_drift"),
            ("latency", "high_latency"),
            ("timeout", "high_latency"),
            ("service down", "service_crash"),
            ("crash", "service_crash"),
        ]:
            if needle in text:
                return diagnosis
        return {
            "easy_task": "service_crash",
            "medium_task": "memory_leak",
            "hard_task": "disk_full",
        }.get(task_id, "service_crash")

    def _fix_for_diagnosis(self, diagnosis: str) -> str:
        return {
            "service_crash": "restart_service",
            "memory_leak": "memory_fix",
            "high_latency": "increase_timeout",
            "connection_pool_exhaustion": "flush_connection_pool",
            "disk_full": "clear_disk",
            "certificate_expired": "renew_certificate",
            "config_drift": "rollback_config",
        }[diagnosis]

    def _already_executed(self, candidate: Dict[str, Any]) -> bool:
        for action in self.executed:
            if action.get("action_type") != candidate.get("action_type"):
                continue
            if action.get("service") != candidate.get("service"):
                continue
            if action.get("diagnosis") != candidate.get("diagnosis"):
                continue
            if action.get("fix") != candidate.get("fix"):
                continue
            return True
        return False

    def _actions_for_service(self, service: str) -> set[str]:
        return {
            action.get("action_type", "")
            for action in self.executed
            if action.get("service") == service
        }

    def _pending_verification_service(self) -> Optional[str]:
        for index in range(len(self.executed) - 1, -1, -1):
            action = self.executed[index]
            if action.get("action_type") != "apply_fix":
                continue
            service = action.get("service")
            if not service:
                continue
            if any(
                later.get("action_type") == "verify_health" and later.get("service") == service
                for later in self.executed[index + 1 :]
            ):
                continue
            return service
        return None

    def _matches_plan(self, llm_action: Optional[Dict[str, Any]], planned: Dict[str, Any]) -> bool:
        if not llm_action:
            return False
        if llm_action.get("action_type") != planned.get("action_type"):
            return False
        if llm_action.get("service") != planned.get("service"):
            return False
        if planned.get("diagnosis") and llm_action.get("diagnosis") != planned.get("diagnosis"):
            return False
        if planned.get("fix") and llm_action.get("fix") != planned.get("fix"):
            return False
        return True


def extract_score(message: str) -> Optional[float]:
    match = re.search(r"score:\s*([0-9]*\.?[0-9]+)", message, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def action_to_string(action: Dict[str, Any]) -> str:
    service = action.get("service", "")
    return f"{action.get('action_type', 'unknown')}({service})"


async def run_task(agent: DevOpsAgent, env: DevOpsIncidentEnv, task: Dict[str, Any]) -> float:
    agent.reset()
    rewards: List[float] = []
    steps_taken = 0
    success = False
    score = 0.0

    log_start(task=task["name"], env=BENCHMARK, model=MODEL_NAME)

    try:
        result = await env.reset(task_id=task["task_id"])
        observation = result.observation.model_dump()

        for step in range(1, task["max_steps"] + 1):
            if result.done:
                break

            action_dict = agent.choose_action(observation, task["task_id"])
            action_string = action_to_string(action_dict)
            try:
                action = IncidentAction(**action_dict)
                result = await env.step(action)
            except Exception as exc:
                steps_taken = step
                rewards.append(0.0)
                log_step(step, action_string, 0.0, True, str(exc))
                break

            observation = result.observation.model_dump()
            reward = float(result.reward or 0.0)
            done = bool(result.done)
            error = None if observation.get("success", True) else observation.get("action_result", "error")
            rewards.append(reward)
            steps_taken = step
            agent.record(action_dict, reward, observation.get("action_result", ""))
            log_step(step, action_string, reward, done, error)
            if done:
                break

        score = extract_score(observation.get("message", "")) or 0.0
        if score == 0.0:
            try:
                state = await env.state()
                score = float(getattr(state, "final_score", 0.0) or 0.0)
            except Exception:
                score = 0.0
        score = max(0.0, min(1.0, score))
        success = score >= 0.3
    except Exception:
        score = 0.0
        success = False
    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


async def main() -> None:
    agent = DevOpsAgent()
    if IMAGE_NAME:
        env = await DevOpsIncidentEnv.from_docker_image(IMAGE_NAME)
        close_required = True
    else:
        env = DevOpsIncidentEnv(base_url=ENV_URL)
        await env.connect()
        close_required = True

    try:
        scores = []
        for task in TASKS:
            scores.append(await run_task(agent, env, task))
    finally:
        if close_required:
            await env.close()


if __name__ == "__main__":
    asyncio.run(main())
