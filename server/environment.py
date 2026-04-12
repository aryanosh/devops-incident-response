from __future__ import annotations

import datetime as dt
import hashlib
import random
import uuid
from typing import Any, Dict, List, Optional, Tuple

try:
    from ..grader import _strict_score, grade_episode
    from ..models import (
        Alert,
        EnvironmentState,
        IncidentAction,
        IncidentObservation,
        ServiceLog,
        ServiceMetrics,
        ServiceSummary,
        StepResponse,
    )
    from ..tasks import (
        ALL_SERVICES,
        LOG_TEMPLATES,
        SCENARIO_CONFIGS,
        SERVICE_DEPENDENCY_GRAPH,
        VALID_ACTION_TYPES,
        VALID_DIAGNOSES,
        VALID_FIXES,
        get_task_definitions,
    )
except ImportError:
    from grader import _strict_score, grade_episode
    from models import (
        Alert,
        EnvironmentState,
        IncidentAction,
        IncidentObservation,
        ServiceLog,
        ServiceMetrics,
        ServiceSummary,
        StepResponse,
    )
    from tasks import (
        ALL_SERVICES,
        LOG_TEMPLATES,
        SCENARIO_CONFIGS,
        SERVICE_DEPENDENCY_GRAPH,
        VALID_ACTION_TYPES,
        VALID_DIAGNOSES,
        VALID_FIXES,
        get_task_definitions,
    )


class IncidentEnvironment:
    def __init__(self) -> None:
        self._scenario_config: Dict[str, Any] = dict(SCENARIO_CONFIGS["easy_task"])
        self._seed: int = 0
        self._rng = random.Random(0)
        self._state = self._new_state(task_id="easy_task", seed=0)
        self._validate_scenario_configs()

    def _validate_scenario_configs(self) -> None:
        """Validate all scenario configs are logically consistent."""
        for task_id, config in SCENARIO_CONFIGS.items():
            root_services = config.get("root_cause_services", [])
            failure_modes = config.get("root_cause_failure_modes", [])
            affected_services = config.get("affected_services", [])
            required_fixes = config.get("correct_fixes", {})
            
            # Check 1:1 mapping
            if len(root_services) != len(failure_modes):
                raise ValueError(
                    f"Task {task_id}: root_cause_services ({len(root_services)} items) "
                    f"length mismatch with root_cause_failure_modes ({len(failure_modes)} items)"
                )
            
            # Check no overlap
            overlap = set(root_services) & set(affected_services)
            if overlap:
                raise ValueError(
                    f"Task {task_id}: root_cause_services and affected_services overlap: {overlap}"
                )
            
            # Check required_fixes are defined for root services
            for service in root_services:
                if service not in required_fixes:
                    raise ValueError(
                        f"Task {task_id}: root cause service '{service}' missing from correct_fixes"
                    )

    def _new_state(self, task_id: str, seed: Optional[int]) -> EnvironmentState:
        config = SCENARIO_CONFIGS[task_id]
        return EnvironmentState(
            episode_id=str(uuid.uuid4()),
            step_count=0,
            task_id=task_id,
            difficulty=str(config["difficulty"]),
            max_steps=int(config["max_steps"]),
            is_resolved=False,
            done=False,
            seed=seed,
            trajectory_reward=0.0,
            final_score=None,
            final_details={},
            services_investigated=[],
            dependencies_inspected=[],
            metrics_queried=[],
            diagnoses=[],
            fixes_applied=[],
            correct_fixes=[],
            successful_verifications=[],
            destructive_actions=0,
            invalid_actions=0,
            diagnosis_correct_count=0,
            fix_correct_count=0,
            root_cause_services=list(config["root_cause_services"]),
            root_cause_failure_modes=list(config["root_cause_failure_modes"]),
            required_fixes=dict(config["correct_fixes"]),
            affected_services=list(config.get("affected_services", [])),
            action_history=[],
            last_action_error=None,
        )

    def reset(self, task_id: str | None = None, seed: int | None = None) -> StepResponse:
        selected_task = task_id if task_id in SCENARIO_CONFIGS else "easy_task"
        self._scenario_config = dict(SCENARIO_CONFIGS[selected_task])
        self._seed = int(seed) if seed is not None else 12345
        self._rng = random.Random(self._seed)
        self._state = self._new_state(task_id=selected_task, seed=self._seed)

        observation = self.build_observation(
            action_result="Environment reset. Pager alert fired for a new production incident.",
            success=True,
            message="Begin by reviewing active alerts and investigating the most critical service.",
            step_number=0,
        )
        return StepResponse(
            observation=observation,
            reward=0.0,
            done=False,
            info={
                "task_id": self._state.task_id,
                "last_action_error": None,
                "trajectory_reward": round(self._state.trajectory_reward, 3),
            },
        )

    def step(self, action: IncidentAction) -> StepResponse:
        if self._state.done:
            observation = self.build_observation(
                action_result="Episode is already complete.",
                success=False,
                message="Reset the environment to start a new task.",
                step_number=self._state.step_count,
            )
            return StepResponse(
                observation=observation,
                reward=0.0,
                done=True,
                info={
                    "task_id": self._state.task_id,
                    "last_action_error": "episode_already_done",
                    "trajectory_reward": round(self._state.trajectory_reward, 3),
                },
            )

        self._state.step_count += 1
        self._state.last_action_error = None

        action_type = action.action_type.strip().lower()
        logs: List[ServiceLog] = []
        metrics: Optional[ServiceMetrics] = None
        reward = 0.0
        success = True
        message = ""
        action_result = ""

        if action_type not in VALID_ACTION_TYPES:
            self._state.invalid_actions += 1
            self._state.last_action_error = "invalid_action_type"
            reward = -0.03
            success = False
            action_result = f"Unknown action_type '{action_type}'."
            message = f"Valid action types: {', '.join(VALID_ACTION_TYPES)}"
        elif action_type == "list_services":
            action_result, message, reward = self._handle_list_services()
        elif action_type == "inspect_dependencies":
            action_result, message, reward = self._handle_inspect_dependencies(action.service)
        elif action_type == "read_logs":
            action_result, message, reward, logs, success = self._handle_read_logs(action.service)
        elif action_type == "query_metrics":
            action_result, message, reward, metrics, success = self._handle_query_metrics(action.service)
        elif action_type == "diagnose":
            action_result, message, reward, success = self._handle_diagnose(action)
        elif action_type == "apply_fix":
            action_result, message, reward, success = self._handle_apply_fix(action)
        elif action_type == "verify_health":
            action_result, message, reward, success = self._handle_verify_health(action.service)

        reward = round(max(0.0, min(1.0, reward)), 3)
        self._append_action_history(action, reward, success)
        self._state.trajectory_reward = round(
            max(-0.999, min(0.999, self._state.trajectory_reward + reward)),
            3,
        )

        if self._state.step_count >= self._state.max_steps:
            self._state.done = True

        if self._all_root_causes_fixed():
            self._state.is_resolved = True
            self._state.done = True

        if self._state.done and self._state.final_score is None:
            final_score, details = self.grade()
            self._state.final_score = final_score
            self._state.final_details = details
            # Keep step reward at 0.0; final score goes in info dict instead
            step_reward = 0.0  # Episode end gets no incremental step reward
        else:
            step_reward = reward

        observation = self.build_observation(
            action_result=action_result,
            success=success,
            message=message,
            logs=logs,
            metrics=metrics,
            step_number=self._state.step_count,
        )

        info: Dict[str, Any] = {
            "task_id": self._state.task_id,
            "last_action_error": self._state.last_action_error,
            "trajectory_reward": round(self._state.trajectory_reward, 3),
        }
        if self._state.final_score is not None:
            info["grader_score"] = self._state.final_score
            info["grader_details"] = self._state.final_details

        return StepResponse(
            observation=observation,
            reward=round(step_reward, 3),
            done=self._state.done,
            info=info,
        )

    def state(self) -> EnvironmentState:
        return self._state

    def grade(self, task_id: str | None = None) -> Tuple[float, Dict[str, float]]:
        _ = task_id or self._state.task_id
        score, details = grade_episode(self._state, self._scenario_config)
        return _strict_score(score), details

    def tasks(self) -> List[Any]:
        return get_task_definitions()

    def tasks_payload(self) -> Dict[str, Any]:
        return {
            "benchmark": "devops_incident_env",
            "count": len(get_task_definitions()),
            "tasks": [task.model_dump() for task in get_task_definitions()],
        }

    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "devops_incident_env",
            "version": "1.0.0",
            "description": "DevOps Incident Response RL Environment for SRE triage",
            "port": 7860,
            "routes": [
                "/",
                "/health",
                "/tasks",
                "/manifest",
                "/reset",
                "/step",
                "/state",
                "/grader",
                "/baseline",
                "/sample_action",
            ],
            "tasks": [task.model_dump() for task in self.tasks()],
        }

    def build_observation(
        self,
        action_result: str,
        success: bool,
        message: str,
        step_number: int,
        logs: Optional[List[ServiceLog]] = None,
        metrics: Optional[ServiceMetrics] = None,
    ) -> IncidentObservation:
        return IncidentObservation(
            action_result=action_result,
            success=success,
            message=message,
            logs=logs or [],
            metrics=metrics,
            service_summaries=self._generate_service_summaries(),
            active_alerts=self._generate_alerts(),
            dependency_graph=SERVICE_DEPENDENCY_GRAPH,
            step_number=step_number,
            max_steps=self._state.max_steps,
            steps_remaining=max(self._state.max_steps - step_number, 0),
            available_services=list(ALL_SERVICES),
            available_actions=list(VALID_ACTION_TYPES),
        )

    def _handle_list_services(self) -> Tuple[str, str, float]:
        reward = 0.015 if not any(a["action_type"] == "list_services" for a in self._state.action_history) else 0.0
        result = "Available services listed."
        message = ", ".join(ALL_SERVICES)
        return result, message, reward

    def _handle_inspect_dependencies(self, service: Optional[str]) -> Tuple[str, str, float]:
        if service and service not in ALL_SERVICES:
            self._state.invalid_actions += 1
            self._state.last_action_error = "unknown_service"
            return (
                f"Unknown service '{service}'.",
                "Use one of the known services from the topology.",
                0.0,
            )

        if service:
            if service not in self._state.dependencies_inspected:
                self._state.dependencies_inspected.append(service)
                reward = 0.02
            else:
                reward = 0.0
            deps = SERVICE_DEPENDENCY_GRAPH.get(service, [])
            return (
                f"Dependencies inspected for {service}.",
                f"{service} depends on: {', '.join(deps) if deps else 'no downstream services'}",
                reward,
            )

        reward = 0.01
        return ("Full dependency graph inspected.", str(SERVICE_DEPENDENCY_GRAPH), reward)

    def _handle_read_logs(self, service: Optional[str]) -> Tuple[str, str, float, List[ServiceLog], bool]:
        if not service or service not in ALL_SERVICES:
            self._state.invalid_actions += 1
            self._state.last_action_error = "read_logs_requires_valid_service"
            return (
                "Log retrieval failed.",
                "Provide a valid service to read logs from.",
                0.0,
                [],
                False,
            )

        first_time = service not in self._state.services_investigated
        if first_time:
            self._state.services_investigated.append(service)

        logs = self._generate_logs(service)
        mode = self._service_failure_mode(service)
        if mode in self._state.root_cause_failure_modes and first_time:
            reward = 0.04
        elif service in self._state.affected_services and first_time:
            reward = 0.03
        else:
            reward = 0.01 if first_time else 0.0

        return (
            f"Retrieved logs for {service}.",
            f"Recent logs show a pattern most consistent with {mode.replace('_', ' ')}.",
            reward,
            logs,
            True,
        )

    def _handle_query_metrics(
        self, service: Optional[str]
    ) -> Tuple[str, str, float, Optional[ServiceMetrics], bool]:
        if not service or service not in ALL_SERVICES:
            self._state.invalid_actions += 1
            self._state.last_action_error = "query_metrics_requires_valid_service"
            return (
                "Metrics query failed.",
                "Provide a valid service to query metrics for.",
                0.0,
                None,
                False,
            )

        first_time = service not in self._state.metrics_queried
        if first_time:
            self._state.metrics_queried.append(service)

        metrics = self._generate_metrics(service)
        mode = self._service_failure_mode(service)
        if mode in self._state.root_cause_failure_modes and first_time:
            reward = 0.04
        elif service in self._state.affected_services and first_time:
            reward = 0.03
        else:
            reward = 0.01 if first_time else 0.0

        return (
            f"Retrieved metrics for {service}.",
            f"Metrics indicate status={metrics.status} with signal resembling {mode.replace('_', ' ')}.",
            reward,
            metrics,
            True,
        )

    def _handle_diagnose(self, action: IncidentAction) -> Tuple[str, str, float, bool]:
        service = action.service
        diagnosis = action.diagnosis

        if not service or service not in ALL_SERVICES:
            self._state.invalid_actions += 1
            self._state.last_action_error = "diagnose_requires_valid_service"
            return "Diagnosis failed.", "Provide a valid service.", 0.0, False

        if not diagnosis or diagnosis not in VALID_DIAGNOSES:
            self._state.invalid_actions += 1
            self._state.last_action_error = "diagnose_requires_valid_diagnosis"
            return "Diagnosis failed.", "Provide a valid diagnosis value.", 0.0, False

        expected_mode = self._service_failure_mode(service)
        correct = diagnosis == expected_mode
        record = {
            "service": service,
            "diagnosis": diagnosis,
            "expected": expected_mode,
            "correct": correct,
        }
        self._state.diagnoses.append(record)

        if correct:
            self._state.diagnosis_correct_count += 1
            reward = 0.08 if service in self._state.root_cause_services else 0.03
            return (
                f"Diagnosis recorded for {service}.",
                f"The observed symptoms align with {diagnosis}.",
                reward,
                True,
            )

        self._state.last_action_error = "incorrect_diagnosis"
        return (
            f"Diagnosis for {service} appears incorrect.",
            f"Observed evidence better matches {expected_mode}.",
            0.0,
            False,
        )

    def _handle_apply_fix(self, action: IncidentAction) -> Tuple[str, str, float, bool]:
        service = action.service
        fix = action.fix

        if not service or service not in ALL_SERVICES:
            self._state.invalid_actions += 1
            self._state.last_action_error = "apply_fix_requires_valid_service"
            return "Fix failed.", "Provide a valid service.", 0.0, False

        if not fix or fix not in VALID_FIXES:
            self._state.invalid_actions += 1
            self._state.last_action_error = "apply_fix_requires_valid_fix"
            return "Fix failed.", "Provide a valid fix value.", 0.0, False

        expected_fix = self._state.required_fixes.get(service)
        mode = self._service_failure_mode(service)

        # Check for destructive actions: applying fix to healthy OR already-fixed OR wrong fix
        is_healthy = mode == "healthy"
        is_already_fixed = service in self._state.correct_fixes
        is_wrong_fix = expected_fix is not None and fix != expected_fix
        
        if is_healthy or is_already_fixed or is_wrong_fix:
            self._state.destructive_actions += 1
            self._state.last_action_error = "destructive_action"
            reason = ""
            if is_healthy:
                reason = "Avoid remediating healthy services."
            elif is_already_fixed:
                reason = f"Service {service} has already been fixed."
            else:
                reason = f"The expected remediation for {mode} is {expected_fix or 'different'}."
            
            record = {"service": service, "fix": fix, "success": False, "destructive": True}
            self._state.fixes_applied.append(record)
            return (
                f"Fix {fix} on {service} was ineffective/destructive.",
                reason,
                0.0,
                False,
            )

        # Correct fix on problematic service
        record = {"service": service, "fix": fix, "success": True}
        self._state.fixes_applied.append(record)
        
        if service not in self._state.correct_fixes:
            self._state.correct_fixes.append(service)
            self._state.fix_correct_count += 1
        
        return (
            f"Fix applied successfully to {service}.",
            f"{service} is recovering after {fix}.",
            0.12,
            True,
        )

    def _handle_verify_health(self, service: Optional[str]) -> Tuple[str, str, float, bool]:
        if not service or service not in ALL_SERVICES:
            self._state.invalid_actions += 1
            self._state.last_action_error = "verify_health_requires_valid_service"
            return "Verification failed.", "Provide a valid service.", 0.0, False

        if service in self._state.correct_fixes:
            if service not in self._state.successful_verifications:
                self._state.successful_verifications.append(service)
                reward = 0.04
            else:
                reward = 0.0
            return (
                f"Health verified for {service}.",
                f"{service} is healthy after remediation.",
                reward,
                True,
            )

        if self._service_failure_mode(service) == "healthy":
            return (
                f"Health verified for {service}.",
                f"{service} is already healthy.",
                0.01,
                True,
            )

        self._state.last_action_error = "verification_before_fix"
        return (
            f"Verification failed for {service}.",
            "Apply the correct remediation before verifying recovery.",
            0.0,
            False,
        )

    def _append_action_history(self, action: IncidentAction, reward: float, success: bool) -> None:
        self._state.action_history.append(
            {
                "step": self._state.step_count,
                "action_type": action.action_type,
                "service": action.service,
                "diagnosis": action.diagnosis,
                "fix": action.fix,
                "reward": round(reward, 3),
                "success": success,
            }
        )

    def _all_root_causes_fixed(self) -> bool:
        required_services = set(self._state.required_fixes.keys())
        return required_services.issubset(set(self._state.successful_verifications))

    def _service_failure_mode(self, service: str) -> str:
        if service in self._state.root_cause_services and service not in self._state.correct_fixes:
            index = self._state.root_cause_services.index(service)
            if index >= len(self._state.root_cause_failure_modes):
                raise IndexError(
                    f"Mode index {index} out of range for service {service}. "
                    f"This indicates a configuration error in task definition."
                )
            return self._state.root_cause_failure_modes[index]
        symptom_modes = self._scenario_config.get("symptom_modes", {})
        if service in self._state.affected_services and not self._roots_remediated():
            return str(symptom_modes.get(service, "high_latency"))
        return "healthy"

    def _roots_remediated(self) -> bool:
        return set(self._state.required_fixes.keys()).issubset(set(self._state.correct_fixes))

    def _service_status(self, service: str) -> str:
        mode = self._service_failure_mode(service)
        if service in self._state.correct_fixes and service not in self._state.successful_verifications:
            return "recovering"
        if mode == "service_crash":
            return "down"
        if mode in {"memory_leak", "disk_full", "certificate_expired"}:
            return "critical"
        if mode in {"high_latency", "connection_pool_exhaustion", "config_drift"}:
            return "degraded"
        return "healthy"

    def _generate_alerts(self) -> List[Alert]:
        if self._state.is_resolved:
            return []

        timestamp = self._timestamp()
        alerts: List[Alert] = []
        for raw_alert in self._scenario_config.get("primary_alerts", []):
            alerts.append(
                Alert(
                    severity=str(raw_alert["severity"]),
                    service=str(raw_alert["service"]),
                    title=str(raw_alert["title"]),
                    description=str(raw_alert["description"]),
                    triggered_at=timestamp,
                    runbook_hint=str(raw_alert["runbook_hint"]),
                )
            )
        return alerts

    def _generate_service_summaries(self) -> List[ServiceSummary]:
        return [
            ServiceSummary(
                service_name=service,
                status=self._service_status(service),
                depends_on=SERVICE_DEPENDENCY_GRAPH[service],
            )
            for service in ALL_SERVICES
        ]

    def _generate_logs(self, service: str) -> List[ServiceLog]:
        mode = self._service_failure_mode(service)
        templates = LOG_TEMPLATES.get(mode, LOG_TEMPLATES.get("healthy", []))
        if not templates:
            raise ValueError(f"No log templates for mode '{mode}' and no fallback available")
        
        base_index = self._stable_index(service, mode)
        logs: List[ServiceLog] = []
        for offset in range(4):
            level, message = templates[(base_index + offset) % len(templates)]
            logs.append(
                ServiceLog(
                    timestamp=self._timestamp(seconds_back=(4 - offset) * 15),
                    level=level,
                    service=service,
                    message=message,
                    trace_id=f"trace-{self._stable_token(service)}-{offset}",
                )
            )
        return logs

    def _generate_metrics(self, service: str) -> ServiceMetrics:
        mode = self._service_failure_mode(service)
        if mode not in LOG_TEMPLATES:
            mode = "healthy"  # Fallback to healthy if mode not found
        
        status = self._service_status(service)
        base: Dict[str, Any] = {
            "service_name": service,
            "cpu_percent": 18.0,
            "memory_mb": 512.0,
            "memory_limit_mb": 2048.0,
            "request_latency_p50_ms": 18.0,
            "request_latency_p99_ms": 55.0,
            "error_rate_percent": 0.1,
            "active_connections": 18,
            "connection_pool_size": 100,
            "disk_used_gb": 24.0,
            "disk_total_gb": 100.0,
            "status": status,
            "uptime_seconds": 172800.0,
        }
        if mode == "service_crash":
            base.update(
                cpu_percent=0.0,
                memory_mb=0.0,
                request_latency_p50_ms=0.0,
                request_latency_p99_ms=0.0,
                error_rate_percent=100.0,
                active_connections=0,
                uptime_seconds=0.0,
            )
        elif mode == "memory_leak":
            base.update(
                cpu_percent=77.0,
                memory_mb=1900.0,
                request_latency_p50_ms=280.0,
                request_latency_p99_ms=4200.0,
                error_rate_percent=12.5,
            )
        elif mode == "high_latency":
            base.update(
                cpu_percent=54.0,
                memory_mb=980.0,
                request_latency_p50_ms=1100.0,
                request_latency_p99_ms=6200.0,
                error_rate_percent=9.7,
                active_connections=91,
            )
        elif mode == "connection_pool_exhaustion":
            base.update(
                cpu_percent=36.0,
                memory_mb=840.0,
                request_latency_p50_ms=2400.0,
                request_latency_p99_ms=12000.0,
                error_rate_percent=27.0,
                active_connections=100,
            )
        elif mode == "disk_full":
            base.update(
                cpu_percent=14.0,
                memory_mb=1100.0,
                request_latency_p50_ms=900.0,
                request_latency_p99_ms=14000.0,
                error_rate_percent=41.0,
                disk_used_gb=99.2,
            )
        elif mode == "recovering":
            base.update(status="recovering", cpu_percent=30.0, memory_mb=700.0)
        return ServiceMetrics(**base)

    def _stable_index(self, service: str, mode: str) -> int:
        digest = hashlib.md5(f"{self._seed}:{service}:{mode}:{self._state.step_count}".encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    def _stable_token(self, service: str) -> str:
        digest = hashlib.md5(f"{self._seed}:{service}".encode("utf-8")).hexdigest()
        return digest[:8]

    def _timestamp(self, seconds_back: int = 0) -> str:
        base_time = dt.datetime(2026, 1, 1, 12, 0, 0) + dt.timedelta(seconds=self._seed % 86400)
        value = base_time - dt.timedelta(seconds=seconds_back)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
