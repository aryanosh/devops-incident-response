"""Core environment logic for the DevOps Incident Response benchmark."""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from typing import Any, Dict, List, Optional, Tuple

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import EnvironmentMetadata

try:
    from ..models import (
        Alert,
        IncidentAction,
        IncidentObservation,
        IncidentState,
        ServiceLog,
        ServiceMetrics,
        ServiceSummary,
    )
except ImportError:
    from models import (
        Alert,
        IncidentAction,
        IncidentObservation,
        IncidentState,
        ServiceLog,
        ServiceMetrics,
        ServiceSummary,
    )

SERVICE_DEPENDENCY_GRAPH: Dict[str, List[str]] = {
    "api_gateway": ["auth_service", "order_service"],
    "auth_service": ["user_service", "database"],
    "user_service": ["database"],
    "order_service": ["payment_service", "database"],
    "payment_service": ["database"],
    "database": [],
}

ALL_SERVICES = list(SERVICE_DEPENDENCY_GRAPH.keys())

LOG_TEMPLATES: Dict[str, List[Tuple[str, str]]] = {
    "service_crash": [
        ("FATAL", "Process exited with code 137."),
        ("ERROR", "Health check failed: connection refused."),
        ("WARN", "Liveness probe failed with status 503."),
        ("ERROR", "CrashLoopBackOff restarting container."),
    ],
    "memory_leak": [
        ("WARN", "Heap memory is above 89 percent."),
        ("ERROR", "OutOfMemoryError in worker process."),
        ("WARN", "GC pause time exceeded threshold."),
        ("ERROR", "Failed to allocate request buffer."),
    ],
    "high_latency": [
        ("WARN", "P99 latency is far above SLA."),
        ("ERROR", "Timeout waiting for upstream response."),
        ("WARN", "Request queue depth is critical."),
        ("ERROR", "Load balancer health check timed out."),
    ],
    "connection_pool_exhaustion": [
        ("ERROR", "Connection pool exhausted."),
        ("ERROR", "Timed out waiting for a DB connection."),
        ("WARN", "Pool utilization reached 100 percent."),
        ("ERROR", "Database rejected connection at max_connections."),
    ],
    "disk_full": [
        ("ERROR", "No space left on device."),
        ("FATAL", "WAL write failed because disk is full."),
        ("ERROR", "Temp file creation failed with ENOSPC."),
        ("WARN", "Disk usage is above 99 percent."),
    ],
    "certificate_expired": [
        ("ERROR", "TLS certificate has expired."),
        ("ERROR", "TLS handshake failed with x509 error."),
        ("WARN", "Certificate chain validation failed."),
        ("ERROR", "mTLS authentication failed."),
    ],
    "config_drift": [
        ("ERROR", "Config drift detected against expected values."),
        ("WARN", "Feature flag changed outside deployment."),
        ("ERROR", "ConfigMap hash mismatch detected."),
        ("ERROR", "Environment points at a retired host."),
    ],
    "healthy": [
        ("INFO", "Requests are completing within SLA."),
        ("DEBUG", "Cache hit ratio is stable."),
        ("INFO", "Health check OK for all dependencies."),
        ("DEBUG", "Connection pool usage is normal."),
    ],
}

SCENARIO_CONFIGS: Dict[str, Dict[str, Any]] = {
    "easy_task": {
        "name": "Single Service Crash",
        "difficulty": "easy",
        "root_causes": [
            {"service": "api_gateway", "failure_mode": "service_crash", "fix": "restart_service"}
        ],
        "affected_services": {},
        "max_steps": 10,
        "optimal_steps": 3,
    },
    "medium_task": {
        "name": "Memory Leak with Cascading Symptoms",
        "difficulty": "medium",
        "root_causes": [
            {"service": "order_service", "failure_mode": "memory_leak", "fix": "memory_fix"}
        ],
        "affected_services": {"api_gateway": "high_latency", "payment_service": "high_latency"},
        "max_steps": 15,
        "optimal_steps": 5,
    },
    "hard_task": {
        "name": "Cascading Failure Chain",
        "difficulty": "hard",
        "root_causes": [
            {"service": "database", "failure_mode": "disk_full", "fix": "clear_disk"}
        ],
        "affected_services": {
            "api_gateway": "high_latency",
            "order_service": "high_latency",
            "payment_service": "connection_pool_exhaustion",
            "auth_service": "high_latency",
        },
        "red_herrings": {
            "order_service": "memory_leak",
            "payment_service": "high_latency",
        },
        "max_steps": 20,
        "optimal_steps": 9,
    },
    "expert_task": {
        "name": "Multi-Root Cascading Failure",
        "difficulty": "expert",
        "root_causes": [
            {"service": "database", "failure_mode": "disk_full", "fix": "clear_disk"},
            {"service": "auth_service", "failure_mode": "certificate_expired", "fix": "renew_certificate"},
        ],
        "affected_services": {
            "api_gateway": "high_latency",
            "order_service": "connection_pool_exhaustion",
            "payment_service": "high_latency",
            "user_service": "high_latency",
        },
        "red_herrings": {
            "order_service": "memory_leak",
            "user_service": "config_drift",
        },
        "max_steps": 30,
        "optimal_steps": 14,
    },
}

REWARD_INVESTIGATE_ROOT_CAUSE_SERVICE = 0.04
REWARD_INVESTIGATE_AFFECTED_SERVICE = 0.02
REWARD_INVESTIGATE_HEALTHY_SERVICE = 0.005
REWARD_INVESTIGATE_REDUNDANT = 0.0
REWARD_CORRECT_DIAGNOSIS = 0.15
REWARD_INCORRECT_DIAGNOSIS = -0.03
REWARD_CORRECT_FIX = 0.25
REWARD_WRONG_FIX_ON_ROOT = -0.05
REWARD_FIX_ON_HEALTHY = -0.10
REWARD_VERIFY_AFTER_FIX = 0.03
REWARD_VERIFY_NO_FIX = 0.0
REWARD_LIST_SERVICES = 0.01
REWARD_CHECK_DEPENDENCIES = 0.02
REWARD_REASONING_BONUS = 0.02
REWARD_BLIND_FIX_PENALTY = -0.05

GRADER_ROOT_CAUSE_WEIGHT = 0.35
GRADER_RESOLUTION_WEIGHT = 0.30
GRADER_EFFICIENCY_WEIGHT = 0.20
GRADER_SAFETY_WEIGHT = 0.15


class IncidentEnvironment(Environment[IncidentAction, IncidentObservation, IncidentState]):
    """Dense-reward incident triage environment."""

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self) -> None:
        super().__init__()
        self._state = IncidentState(episode_id="", step_count=0)
        self._scenario_config: Dict[str, Any] = {}
        self._root_causes: List[Dict[str, str]] = []
        self._affected_services: Dict[str, str] = {}
        self._red_herrings: Dict[str, str] = {}
        self._services_investigated: Dict[str, set[str]] = {}
        self._investigation_steps: Dict[str, Dict[str, int]] = {}
        self._diagnoses_submitted: List[Dict[str, str]] = []
        self._correct_diagnosis_steps: Dict[str, int] = {}
        self._fixes_applied: List[Dict[str, Any]] = []
        self._verified_services: set[str] = set()
        self._dependency_checked_step: Optional[int] = None
        self._max_steps = 10
        self._optimal_steps = 3
        self._seed = 0
        self._base_time = dt.datetime(2026, 1, 1, 12, 0, 0)
        self._correct_diagnoses = 0
        self._incorrect_diagnoses = 0
        self._correct_fixes = 0
        self._incorrect_fixes = 0
        self._destructive_actions = 0
        self._verifications_after_fix = 0
        self._blind_fixes = 0

    def get_metadata(self) -> EnvironmentMetadata:
        return EnvironmentMetadata(
            name="devops-incident-response",
            description="Investigate alerts, diagnose failures, and repair a microservice incident.",
            version="1.0.0",
        )

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        task_id: str = "easy_task",
        **_: Any,
    ) -> IncidentObservation:
        if task_id not in SCENARIO_CONFIGS:
            task_id = "easy_task"

        self._scenario_config = SCENARIO_CONFIGS[task_id]
        actual_episode_id = episode_id or str(uuid.uuid4())
        self._seed = (
            int(seed)
            if seed is not None
            else int(hashlib.md5(actual_episode_id.encode("utf-8")).hexdigest()[:8], 16)
        )
        self._base_time = dt.datetime(2026, 1, 1, 12, 0, 0) + dt.timedelta(
            seconds=self._seed % 86400
        )
        self._root_causes = [dict(item) for item in self._scenario_config["root_causes"]]
        self._affected_services = dict(self._scenario_config.get("affected_services", {}))
        self._red_herrings = dict(self._scenario_config.get("red_herrings", {}))
        self._services_investigated = {}
        self._investigation_steps = {}
        self._diagnoses_submitted = []
        self._correct_diagnosis_steps = {}
        self._fixes_applied = []
        self._verified_services = set()
        self._dependency_checked_step = None
        self._max_steps = int(self._scenario_config["max_steps"])
        self._optimal_steps = int(self._scenario_config["optimal_steps"])
        self._correct_diagnoses = 0
        self._incorrect_diagnoses = 0
        self._correct_fixes = 0
        self._incorrect_fixes = 0
        self._destructive_actions = 0
        self._verifications_after_fix = 0
        self._blind_fixes = 0

        self._state = IncidentState(
            episode_id=actual_episode_id,
            step_count=0,
            task_id=task_id,
            difficulty=self._scenario_config["difficulty"],
            scenario_name=self._scenario_config["name"],
            max_steps=self._max_steps,
            optimal_steps=self._optimal_steps,
            is_resolved=False,
            final_score=0.0,
        )
        self._sync_state_tracking()
        return self._build_observation(
            action_result="INCIDENT DETECTED. Pager alert triggered.",
            success=True,
            message=(
                f"Scenario: {self._scenario_config['name']} ({self._scenario_config['difficulty']}). "
                f"Find the root cause and apply the correct fix within {self._max_steps} steps."
            ),
            reward=0.0,
            done=False,
        )

    def step(
        self,
        action: IncidentAction,
        timeout_s: Optional[float] = None,
        **_: Any,
    ) -> IncidentObservation:
        del timeout_s
        if self._state.is_resolved or self._state.step_count >= self._max_steps:
            self._state.final_score = self._compute_grader_score()
            self._sync_state_tracking()
            return self._build_observation(
                action_result="Episode already ended.",
                success=False,
                message=f"Final score: {self._state.final_score:.4f}",
                reward=0.0,
                done=True,
            )

        self._state.step_count += 1
        step_reward = REWARD_REASONING_BONUS if len((action.reasoning or "").strip()) > 30 else 0.0
        action_result = ""
        success = True
        message = ""
        logs: List[ServiceLog] = []
        metrics: Optional[ServiceMetrics] = None

        if action.action_type == "list_services":
            action_result = self._handle_list_services()
            if not self._state.listed_services:
                self._state.listed_services = True
                step_reward += REWARD_LIST_SERVICES
        elif action.action_type == "check_dependencies":
            action_result = self._handle_check_dependencies()
            if not self._state.checked_dependencies:
                self._state.checked_dependencies = True
                self._dependency_checked_step = self._state.step_count
                step_reward += REWARD_CHECK_DEPENDENCIES
        elif action.action_type == "read_logs":
            if not self._is_valid_service(action.service):
                action_result = f"Invalid service: {action.service!r}."
                success = False
            else:
                logs = self._generate_logs(action.service)
                self._record_investigation(action.service, "read_logs")
                action_result = f"Retrieved {len(logs)} log entries for {action.service}."
                step_reward += self._reward_for_investigation(action.service, "read_logs")
        elif action.action_type == "query_metrics":
            if not self._is_valid_service(action.service):
                action_result = f"Invalid service: {action.service!r}."
                success = False
            else:
                metrics = self._generate_metrics(action.service)
                self._record_investigation(action.service, "query_metrics")
                action_result = (
                    f"Retrieved metrics for {action.service}: status={metrics.status}, "
                    f"cpu={metrics.cpu_percent:.1f}, memory={metrics.memory_mb:.1f}/{metrics.memory_limit_mb:.1f}MB"
                )
                step_reward += self._reward_for_investigation(action.service, "query_metrics")
        elif action.action_type == "diagnose":
            action_result, success, message, reward_delta = self._handle_diagnose(action)
            step_reward += reward_delta
        elif action.action_type == "apply_fix":
            action_result, success, message, reward_delta = self._handle_apply_fix(action)
            step_reward += reward_delta
        elif action.action_type == "verify_health":
            if not self._is_valid_service(action.service):
                action_result = f"Invalid service: {action.service!r}."
                success = False
            else:
                action_result, reward_delta = self._handle_verify_health(action.service)
                step_reward += reward_delta
        else:
            action_result = "Unknown action type."
            success = False

        step_reward = round(max(-0.2, min(0.3, step_reward)), 4)
        self._state.cumulative_reward += step_reward
        self._state.step_rewards.append(step_reward)

        done = self._state.is_resolved or self._state.step_count >= self._max_steps
        if done:
            self._state.final_score = self._compute_grader_score()
            message = (
                f"INCIDENT RESOLVED. Final grader score: {self._state.final_score:.4f}"
                if self._state.is_resolved
                else f"Time limit reached. Final grader score: {self._state.final_score:.4f}"
            )

        self._sync_state_tracking()
        return self._build_observation(
            action_result=action_result,
            success=success,
            message=message,
            logs=logs,
            metrics=metrics,
            reward=step_reward,
            done=done,
        )

    def state(self) -> IncidentState:
        self._sync_state_tracking()
        return self._state

    def _handle_list_services(self) -> str:
        lines = ["Services:"]
        for service in ALL_SERVICES:
            deps = ", ".join(SERVICE_DEPENDENCY_GRAPH[service]) or "none"
            lines.append(f"- {service}: status={self._get_service_status(service)}, depends_on=[{deps}]")
        return "\n".join(lines)

    def _handle_check_dependencies(self) -> str:
        lines = ["Dependency graph:"]
        for service, deps in SERVICE_DEPENDENCY_GRAPH.items():
            lines.append(f"- {service}: {', '.join(deps) if deps else 'no dependencies'}")
        return "\n".join(lines)

    def _handle_diagnose(self, action: IncidentAction) -> Tuple[str, bool, str, float]:
        if not self._is_valid_service(action.service):
            return f"Invalid service: {action.service!r}.", False, "Specify a valid service.", 0.0
        if not action.diagnosis:
            return "Missing diagnosis.", False, "", 0.0

        self._diagnoses_submitted.append({"service": action.service, "diagnosis": action.diagnosis})
        is_root = any(
            root["service"] == action.service and root["failure_mode"] == action.diagnosis
            for root in self._root_causes
        )
        is_symptom = (
            action.service in self._affected_services
            and self._affected_services[action.service] == action.diagnosis
        )
        if is_root:
            self._correct_diagnoses += 1
            self._correct_diagnosis_steps.setdefault(action.service, self._state.step_count)
            return (
                f"Correct diagnosis: {action.service} is suffering from {action.diagnosis}.",
                True,
                "Apply the appropriate fix next.",
                REWARD_CORRECT_DIAGNOSIS,
            )
        if is_symptom:
            self._correct_diagnoses += 1
            return (
                f"Partial diagnosis: {action.service} is showing {action.diagnosis}, but it is a downstream symptom.",
                True,
                "Trace upstream dependencies to find the root cause.",
                REWARD_CORRECT_DIAGNOSIS * 0.3,
            )

        self._incorrect_diagnoses += 1
        return (
            f"Incorrect diagnosis: {action.service} is not suffering from {action.diagnosis}.",
            False,
            "Re-check logs and metrics.",
            REWARD_INCORRECT_DIAGNOSIS,
        )

    def _handle_apply_fix(self, action: IncidentAction) -> Tuple[str, bool, str, float]:
        if not self._is_valid_service(action.service):
            return f"Invalid service: {action.service!r}.", False, "Specify a valid service.", 0.0
        if not action.fix:
            return "Missing fix type.", False, "", 0.0

        fixed_services = {fix["service"] for fix in self._fixes_applied if fix.get("success")}
        if action.service in fixed_services:
            return (
                f"{action.service} is already healthy after a previous fix.",
                True,
                "Use another action or verify health.",
                0.0,
            )

        record: Dict[str, Any] = {"service": action.service, "fix": action.fix, "success": False}
        is_root = any(root["service"] == action.service for root in self._root_causes)
        is_affected = action.service in self._affected_services
        if not is_root and not is_affected and self._get_service_status(action.service) == "healthy":
            self._destructive_actions += 1
            record["destructive"] = True
            self._fixes_applied.append(record)
            return (
                f"Dangerous action: applied {action.fix} to healthy service {action.service}.",
                False,
                "Do not remediate healthy services.",
                REWARD_FIX_ON_HEALTHY,
            )

        correct_fix = any(
            root["service"] == action.service and root["fix"] == action.fix for root in self._root_causes
        )
        if correct_fix:
            record["success"] = True
            self._correct_fixes += 1
            blind_fix_penalty = 0.0
            if self._is_blind_fix(action.service):
                self._blind_fixes += 1
                record["blind"] = True
                blind_fix_penalty = REWARD_BLIND_FIX_PENALTY
            self._fixes_applied.append(record)
            return (
                f"Fix successful: {action.fix} applied to {action.service}.",
                True,
                "Verify health next before considering the incident resolved.",
                REWARD_CORRECT_FIX + blind_fix_penalty,
            )

        self._incorrect_fixes += 1
        self._fixes_applied.append(record)
        if is_root:
            return (
                f"Ineffective fix: {action.fix} did not resolve the root issue on {action.service}.",
                False,
                "Choose the remediation that matches the diagnosed failure mode.",
                REWARD_WRONG_FIX_ON_ROOT,
            )
        if is_affected:
            return (
                f"Symptom treatment only: {action.fix} on {action.service} did not fix the upstream root cause.",
                False,
                "Trace the dependency chain upstream.",
                REWARD_WRONG_FIX_ON_ROOT,
            )
        return (f"No effect: {action.fix} on {action.service}.", False, "", REWARD_WRONG_FIX_ON_ROOT)

    def _handle_verify_health(self, service: str) -> Tuple[str, float]:
        fixed_services = {fix["service"] for fix in self._fixes_applied if fix.get("success")}
        is_root = any(root["service"] == service for root in self._root_causes)
        if service in fixed_services:
            self._verifications_after_fix += 1
            self._verified_services.add(service)
            if self._all_roots_fixed() and self._all_roots_verified():
                self._state.is_resolved = True
            return (
                f"Health check passed for {service}: status=healthy, latency=23ms, error_rate=0.0%.",
                REWARD_VERIFY_AFTER_FIX,
            )
        if is_root:
            return (
                f"Health check failed for {service}: root cause not yet resolved.",
                REWARD_VERIFY_NO_FIX,
            )
        if service in self._affected_services:
            root_fixed = all(root["service"] in fixed_services for root in self._root_causes)
            return (
                (
                    f"Health check passed for {service}: recovering after upstream fix."
                    if root_fixed
                    else f"Health check still degraded for {service}: upstream issue remains."
                ),
                REWARD_VERIFY_AFTER_FIX if root_fixed else REWARD_VERIFY_NO_FIX,
            )
        return (f"Health check passed for {service}: service is healthy.", REWARD_VERIFY_NO_FIX)

    def _reward_for_investigation(self, service: str, action_type: str) -> float:
        actions = self._services_investigated.setdefault(service, set())
        if action_type in actions:
            return REWARD_INVESTIGATE_REDUNDANT
        actions.add(action_type)
        if any(root["service"] == service for root in self._root_causes):
            return REWARD_INVESTIGATE_ROOT_CAUSE_SERVICE
        if service in self._affected_services:
            return REWARD_INVESTIGATE_AFFECTED_SERVICE
        return REWARD_INVESTIGATE_HEALTHY_SERVICE

    def _compute_grader_score(self) -> float:
        """
        Compute final grader score in [0.0, 1.0] range.
        
        The grader evaluates agent performance across four dimensions:
        
        1. Root Cause Identification (35%):
           - Rewards correct diagnosis with supporting evidence (logs/metrics)
           - Partial credit for investigation without diagnosis
           - Higher requirements for harder tasks (dependency tracing, etc.)
        
        2. Resolution Quality (30%):
           - Correct fix applied to root cause services (70%)
           - Health verification after fixes (30%)
        
        3. Efficiency (20%):
           - Optimal step count: 100% efficiency score
           - Up to 2x optimal: linear degradation
           - Beyond 2x optimal: further degradation
        
        4. Safety (15%):
           - Penalties for destructive actions on healthy services
           - Penalties for incorrect fixes
           - Penalties for blind fixes (without investigation)
        
        5. Time Pressure (penalty):
           - Additional penalty for delays beyond 1.5x optimal steps
           - Simulates incident escalation over time
        
        Returns:
            float: Final score in [0.0, 1.0] range
        """
        total_root_causes = len(self._root_causes)
        if total_root_causes == 0:
            return 0.0

        identification_parts: List[float] = []
        for root in self._root_causes:
            service = root["service"]
            diagnosis_step = self._correct_diagnosis_steps.get(service)
            if diagnosis_step is not None:
                identification_parts.append(self._diagnosis_evidence_score(service, diagnosis_step))
            elif service in self._services_investigated:
                identification_parts.append(0.3 * self._investigation_coverage(service))
            else:
                identification_parts.append(0.0)
        identification_score = sum(identification_parts) / total_root_causes

        fixed_roots = {
            fix["service"]
            for fix in self._fixes_applied
            if fix.get("success") and any(root["service"] == fix["service"] for root in self._root_causes)
        }
        verified_roots = {
            service
            for service in self._verified_services
            if any(root["service"] == service for root in self._root_causes)
        }
        resolution_score = (
            (0.7 * len(fixed_roots)) + (0.3 * len(verified_roots))
        ) / total_root_causes

        steps_used = self._state.step_count
        optimal = max(self._optimal_steps, 1)
        if steps_used <= optimal:
            efficiency_score = 1.0
        elif steps_used <= optimal * 2:
            efficiency_score = 1.0 - 0.5 * ((steps_used - optimal) / optimal)
        else:
            efficiency_score = max(0.0, 1.0 - ((steps_used - optimal) / max(self._max_steps - optimal, 1)))

        safety_score = max(
            0.0,
            1.0
            - (self._destructive_actions * 0.4)
            - (self._incorrect_fixes * 0.05)
            - (self._blind_fixes * 0.1),
        )
        
        # Time pressure penalty - incidents get worse over time
        time_pressure_penalty = 0.0
        if steps_used > optimal * 1.5:
            # Penalty grows as time increases beyond 1.5x optimal
            excess_steps = steps_used - (optimal * 1.5)
            time_pressure_penalty = min(0.12, excess_steps * 0.01)
        
        score = (
            identification_score * GRADER_ROOT_CAUSE_WEIGHT
            + resolution_score * GRADER_RESOLUTION_WEIGHT
            + efficiency_score * GRADER_EFFICIENCY_WEIGHT
            + safety_score * GRADER_SAFETY_WEIGHT
            - time_pressure_penalty
        )
        return round(max(0.0, min(1.0, score)), 4)

    def _get_service_status(self, service: str) -> str:
        fixed_services = {fix["service"] for fix in self._fixes_applied if fix.get("success")}
        for root in self._root_causes:
            if root["service"] == service and service not in fixed_services:
                return "down" if root["failure_mode"] == "service_crash" else "critical"
        if service in self._affected_services:
            root_fixed = all(root["service"] in fixed_services for root in self._root_causes)
            if not root_fixed:
                return "degraded"
        return "healthy"

    def _generate_logs(self, service: str) -> List[ServiceLog]:
        fixed_services = {fix["service"] for fix in self._fixes_applied if fix.get("success")}
        
        # Determine which log template to use
        if any(root["service"] == service for root in self._root_causes) and service not in fixed_services:
            mode = next(root["failure_mode"] for root in self._root_causes if root["service"] == service)
            templates = LOG_TEMPLATES[mode]
        elif service in self._affected_services and not all(
            root["service"] in fixed_services for root in self._root_causes
        ):
            templates = LOG_TEMPLATES[self._affected_services[service]]
        elif service in self._red_herrings and service not in self._services_investigated:
            # Show red herring ONLY if service hasn't been investigated yet
            templates = LOG_TEMPLATES[self._red_herrings[service]]
        else:
            templates = LOG_TEMPLATES["healthy"]

        seed_base = self._stable_int(f"{self._state.episode_id}:{service}:{self._state.step_count}")
        trace_prefix = hashlib.md5(f"{self._state.episode_id}:{service}".encode("utf-8")).hexdigest()[:10]
        logs: List[ServiceLog] = []
        for index in range(6):
            timestamp = self._base_time - dt.timedelta(seconds=(6 - index) * 12)
            level, message = templates[(seed_base + index) % len(templates)]
            logs.append(
                ServiceLog(
                    timestamp=timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                    level=level,
                    service=service,
                    message=message,
                    trace_id=f"trace-{trace_prefix}-{index:02d}",
                )
            )
        return logs

    def _generate_metrics(self, service: str) -> ServiceMetrics:
        fixed_services = {fix["service"] for fix in self._fixes_applied if fix.get("success")}
        
        # Determine which metrics to show
        if any(root["service"] == service for root in self._root_causes) and service not in fixed_services:
            mode = next(root["failure_mode"] for root in self._root_causes if root["service"] == service)
            return self._metrics_for_failure(service, mode)
        if service in self._affected_services and not all(
            root["service"] in fixed_services for root in self._root_causes
        ):
            return self._metrics_for_failure(service, self._affected_services[service])
        if service in self._red_herrings and service not in self._services_investigated:
            # Show red herring metrics ONLY if service hasn't been investigated yet
            return self._metrics_for_failure(service, self._red_herrings[service])
        
        return ServiceMetrics(
            service_name=service,
            cpu_percent=22.5,
            memory_mb=512.0,
            memory_limit_mb=8192.0,
            request_latency_p50_ms=12.0,
            request_latency_p99_ms=45.0,
            error_rate_percent=0.1,
            active_connections=15,
            connection_pool_size=100,
            disk_used_gb=23.4,
            disk_total_gb=100.0,
            status="healthy",
            uptime_seconds=345600.0,
        )

    def _metrics_for_failure(self, service: str, mode: str) -> ServiceMetrics:
        base: Dict[str, Any] = {
            "service_name": service,
            "cpu_percent": 25.0,
            "memory_mb": 512.0,
            "memory_limit_mb": 8192.0,
            "request_latency_p50_ms": 15.0,
            "request_latency_p99_ms": 50.0,
            "error_rate_percent": 0.5,
            "active_connections": 20,
            "connection_pool_size": 100,
            "disk_used_gb": 25.0,
            "disk_total_gb": 100.0,
            "status": "critical",
            "uptime_seconds": 86400.0,
        }
        if mode == "service_crash":
            base.update(cpu_percent=0.0, memory_mb=0.0, request_latency_p50_ms=0.0, request_latency_p99_ms=0.0, error_rate_percent=100.0, active_connections=0, status="down", uptime_seconds=0.0)
        elif mode == "memory_leak":
            base.update(cpu_percent=78.5, memory_mb=7850.0, request_latency_p50_ms=340.0, request_latency_p99_ms=4200.0, error_rate_percent=18.3)
        elif mode == "high_latency":
            base.update(cpu_percent=45.0, memory_mb=1200.0, request_latency_p50_ms=1250.0, request_latency_p99_ms=8500.0, error_rate_percent=12.7, active_connections=95, status="degraded")
        elif mode == "connection_pool_exhaustion":
            base.update(cpu_percent=35.0, memory_mb=800.0, request_latency_p50_ms=2800.0, request_latency_p99_ms=30000.0, error_rate_percent=45.2, active_connections=100, connection_pool_size=100)
        elif mode == "disk_full":
            base.update(cpu_percent=12.0, memory_mb=1024.0, request_latency_p50_ms=850.0, request_latency_p99_ms=15000.0, error_rate_percent=67.8, disk_used_gb=99.2)
        elif mode == "certificate_expired":
            base.update(error_rate_percent=89.5, request_latency_p50_ms=5.0, request_latency_p99_ms=10.0)
        elif mode == "config_drift":
            base.update(error_rate_percent=34.2, request_latency_p50_ms=450.0, request_latency_p99_ms=2300.0, status="degraded")
        return ServiceMetrics(**base)

    def _generate_service_summaries(self) -> List[ServiceSummary]:
        return [
            ServiceSummary(
                service_name=service,
                status=self._get_service_status(service),
                depends_on=SERVICE_DEPENDENCY_GRAPH[service],
            )
            for service in ALL_SERVICES
        ]

    def _generate_alerts(self) -> List[Alert]:
        if self._state.is_resolved:
            return []
        alerts: List[Alert] = []
        timestamp = self._base_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        fixed_services = {fix["service"] for fix in self._fixes_applied if fix.get("success")}
        show_root_alerts = self._state.task_id != "hard_task"
        root_severity = "critical" if self._state.task_id == "easy_task" else "high"
        for root in self._root_causes:
            if show_root_alerts and root["service"] not in fixed_services:
                mode = root["failure_mode"]
                alerts.append(
                    Alert(
                        severity=root_severity,
                        service=root["service"],
                        title=self._alert_title(mode),
                        description=self._alert_description(root["service"], mode),
                        triggered_at=timestamp,
                        runbook_hint=self._runbook_hint(mode),
                    )
                )
        if not all(root["service"] in fixed_services for root in self._root_causes):
            for service, mode in self._affected_services.items():
                alerts.append(
                    Alert(
                        severity="high",
                        service=service,
                        title=self._alert_title(mode),
                        description=self._alert_description(service, mode),
                        triggered_at=timestamp,
                        runbook_hint="Check upstream dependencies before applying a local fix.",
                    )
                )
        return alerts

    def _alert_title(self, mode: str) -> str:
        return {
            "service_crash": "Service Down",
            "memory_leak": "Memory Usage Critical",
            "high_latency": "Elevated Latency",
            "connection_pool_exhaustion": "Connection Pool Exhausted",
            "disk_full": "Disk Space Critical",
            "certificate_expired": "TLS Certificate Expired",
            "config_drift": "Configuration Drift Detected",
        }.get(mode, "Service Issue")

    def _alert_description(self, service: str, mode: str) -> str:
        return {
            "service_crash": f"{service} is unresponsive and all health checks are failing.",
            "memory_leak": f"{service} memory is above 95 percent and OOM risk is increasing.",
            "high_latency": f"{service} latency is far above SLA and queues are growing.",
            "connection_pool_exhaustion": f"{service} connection pool is saturated and requests are timing out.",
            "disk_full": f"{service} disk is above 99 percent used and writes are failing.",
            "certificate_expired": f"{service} TLS certificate expired and mTLS calls are rejected.",
            "config_drift": f"{service} configuration drift was detected against the expected deployment.",
        }.get(mode, f"{service} has an active production issue.")

    def _runbook_hint(self, mode: str) -> str:
        return {
            "service_crash": "Read crash logs and restart if this is a direct service failure.",
            "memory_leak": "Inspect memory growth and apply the memory remediation.",
            "high_latency": "Investigate upstream dependencies for a cascade.",
            "connection_pool_exhaustion": "Inspect the database before flushing the pool.",
            "disk_full": "Clear storage pressure and verify the database recovers.",
            "certificate_expired": "Renew the certificate and restart if needed.",
            "config_drift": "Compare running and expected config and roll back drift.",
        }.get(mode, "Investigate the affected service with logs and metrics.")

    def _build_observation(
        self,
        action_result: str,
        success: bool,
        message: str = "",
        logs: Optional[List[ServiceLog]] = None,
        metrics: Optional[ServiceMetrics] = None,
        reward: float = 0.0,
        done: bool = False,
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
            step_number=self._state.step_count,
            max_steps=self._max_steps,
            steps_remaining=max(self._max_steps - self._state.step_count, 0),
            available_services=ALL_SERVICES,
            available_actions=[
                "list_services",
                "check_dependencies",
                "read_logs",
                "query_metrics",
                "diagnose",
                "apply_fix",
                "verify_health",
            ],
            reward=reward,
            done=done,
        )

    def _is_valid_service(self, service: Optional[str]) -> bool:
        return bool(service) and service in ALL_SERVICES

    def _stable_int(self, value: str) -> int:
        return int(hashlib.md5(value.encode("utf-8")).hexdigest()[:8], 16)

    def _record_investigation(self, service: str, action_type: str) -> None:
        self._investigation_steps.setdefault(service, {}).setdefault(action_type, self._state.step_count)

    def _all_roots_fixed(self) -> bool:
        fixed_services = {fix["service"] for fix in self._fixes_applied if fix.get("success")}
        return all(root["service"] in fixed_services for root in self._root_causes)

    def _all_roots_verified(self) -> bool:
        return all(root["service"] in self._verified_services for root in self._root_causes)

    def _is_blind_fix(self, service: str) -> bool:
        investigated = service in self._services_investigated and bool(self._services_investigated[service])
        diagnosed = service in self._correct_diagnosis_steps
        return not investigated or not diagnosed

    def _investigation_coverage(self, service: str) -> float:
        actions = self._services_investigated.get(service, set())
        if {"read_logs", "query_metrics"}.issubset(actions):
            return 1.0
        if actions:
            return 0.7
        return 0.0

    def _diagnosis_evidence_score(self, service: str, diagnosis_step: int) -> float:
        investigation_steps = self._investigation_steps.get(service, {})
        had_logs = (investigation_steps.get("read_logs") or diagnosis_step + 1) < diagnosis_step
        had_metrics = (investigation_steps.get("query_metrics") or diagnosis_step + 1) < diagnosis_step
        affected_before = sum(
            1
            for affected_service, steps in self._investigation_steps.items()
            if affected_service in self._affected_services
            and any(step < diagnosis_step for step in steps.values())
        )
        deps_before = self._dependency_checked_step is not None and self._dependency_checked_step < diagnosis_step

        if self._state.task_id == "easy_task":
            return 1.0 if (had_logs or had_metrics) else 0.6

        if self._state.task_id == "medium_task":
            score = 0.0
            if had_logs or had_metrics:
                score += 0.5
            if had_logs and had_metrics:
                score += 0.2
            if affected_before >= 1 or deps_before:
                score += 0.3
            return min(score, 1.0)

        score = 0.0
        if had_logs or had_metrics:
            score += 0.4
        if had_logs and had_metrics:
            score += 0.2
        if deps_before:
            score += 0.2
        if affected_before >= 1:
            score += 0.1
        if affected_before >= 2:
            score += 0.1
        return min(score, 1.0)

    def _sync_state_tracking(self) -> None:
        self._state.max_steps = self._max_steps
        self._state.optimal_steps = self._optimal_steps
        self._state.root_causes = [dict(root) for root in self._root_causes]
        self._state.affected_services = dict(self._affected_services)
        self._state.services_investigated = {
            service: sorted(actions) for service, actions in self._services_investigated.items()
        }
        self._state.diagnoses_submitted = [dict(item) for item in self._diagnoses_submitted]
        self._state.fixes_applied = [dict(item) for item in self._fixes_applied]
        self._state.correct_diagnoses = self._correct_diagnoses
        self._state.incorrect_diagnoses = self._incorrect_diagnoses
        self._state.correct_fixes = self._correct_fixes
        self._state.incorrect_fixes = self._incorrect_fixes
        self._state.destructive_actions = self._destructive_actions
        self._state.verifications_after_fix = self._verifications_after_fix
