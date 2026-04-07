# server/incident_environment.py
import uuid
import datetime
import random
from typing import Dict, Any, List

from openenv.core.env_server import Environment

try:
    from ..models import (
        IncidentAction, IncidentObservation, IncidentState, 
        ServiceLog, ServiceMetrics, ServiceSummary, Alert
    )
except ImportError:
    from models import (
        IncidentAction, IncidentObservation, IncidentState, 
        ServiceLog, ServiceMetrics, ServiceSummary, Alert
    )

# ─────────────────────────────────────────────
# CONFIGURATIONS
# ─────────────────────────────────────────────

SERVICE_DEPENDENCY_GRAPH = {
    "api_gateway": ["auth_service", "order_service"],
    "auth_service": ["user_service"],
    "user_service": ["database"],
    "order_service": ["payment_service", "database"],
    "payment_service": ["database"],
    "database": []
}

LOG_TEMPLATES = {
    "service_crash": [
        ("FATAL", "Process terminated with exit code 137 (OOM killed)"),
        ("ERROR", "Connection refused to upstream service"),
        ("FATAL", "Segmentation fault (core dumped)")
    ],
    "memory_leak": [
        ("WARN", "Memory usage at 87% (7168MB/8192MB)"),
        ("WARN", "GC pause time: 2340ms (threshold: 100ms)"),
        ("ERROR", "Failed to allocate memory for request context")
    ],
    "high_latency": [
        ("WARN", "Request latency P99: 4523ms (SLA: 200ms)"),
        ("ERROR", "Timeout waiting for upstream response"),
        ("WARN", "Thread pool active threads: 200/200")
    ],
    "connection_pool_exhaustion": [
        ("ERROR", "Connection pool exhausted: 100/100 connections in use"),
        ("ERROR", "Timeout acquiring DB connection after 5000ms"),
        ("WARN", "Query rejected: too many active connections")
    ],
    "disk_full": [
        ("ERROR", "No space left on device: /var/lib/data"),
        ("FATAL", "WAL log write failed: disk full"),
        ("ERROR", "Failed to write temp file during sort operation")
    ],
    "certificate_expired": [
        ("ERROR", "SSL certificate expired 2 days ago"),
        ("WARN", "TLS handshake failed: certificate verify error"),
        ("ERROR", "x509: certificate has expired or is not yet valid")
    ],
    "config_drift": [
        ("ERROR", "Environment variable DB_HOST mismatch"),
        ("WARN", "Feature flag 'use_cache' changed unexpectedly"),
        ("ERROR", "Failed to load configuration file: invalid schema")
    ],
    "healthy": [
        ("INFO", "Processed 1500 requests successfully"),
        ("DEBUG", "Cache hit ratio: 94.2%"),
        ("INFO", "Health check OK")
    ]
}

SCENARIO_CONFIGS = {
    "easy_task": {
        "difficulty": "easy",
        "root_cause_services": ["api_gateway"],
        "root_cause_failure_modes": ["service_crash"],
        "correct_fixes": {"api_gateway": "restart_service"},
        "max_steps": 10,
        "optimal_steps": 3
    },
    "medium_task": {
        "difficulty": "medium",
        "root_cause_services": ["order_service"],
        "root_cause_failure_modes": ["memory_leak"],
        "correct_fixes": {"order_service": "memory_fix"},
        "max_steps": 15,
        "optimal_steps": 4
    },
    "hard_task": {
        "difficulty": "hard",
        "root_cause_services": ["database"],
        "root_cause_failure_modes": ["disk_full"],
        "correct_fixes": {"database": "clear_disk"},
        "max_steps": 20,
        "optimal_steps": 6
    }
}

# ─────────────────────────────────────────────
# ENVIRONMENT CLASS
# ─────────────────────────────────────────────

class IncidentEnvironment(Environment[IncidentAction, IncidentObservation, IncidentState]):
    def __init__(self):
        super().__init__()
        self._state = IncidentState()
        self._scenario_config = {}
        
    def reset(self, task_id: str = "easy_task", **kwargs) -> IncidentObservation:
        """Initialize episode from config."""
        if task_id not in SCENARIO_CONFIGS:
            task_id = "easy_task"
            
        self._scenario_config = SCENARIO_CONFIGS[task_id]
        
        self._state = IncidentState(
            episode_id=str(uuid.uuid4()),
            task_id=task_id,
            difficulty=self._scenario_config["difficulty"],
            max_steps=self._scenario_config["max_steps"],
            root_cause_services=self._scenario_config["root_cause_services"],
            root_cause_failure_modes=self._scenario_config["root_cause_failure_modes"],
            correct_fixes=self._scenario_config["correct_fixes"]
        )
        
        # Make deterministic based on episode_id
        random.seed(self._state.episode_id)
        
        return self._build_observation(
            action_result="Incident initiated. PagerDuty alert triggered.",
            success=True,
            message="Check the active alerts to start your investigation.",
            reward_override=0.0
        )

    def step(self, action: IncidentAction) -> IncidentObservation:
        """Process agent action and advance state."""
        self._state.step_count += 1
        
        if self._state.is_resolved or self._state.step_count > self._state.max_steps:
            return self._build_observation("Episode already finished.", False, reward_override=0.0)
            
        action_result = ""
        success = True
        message = ""
        logs = []
        metrics = None
        reward = 0.0
        done = False
        
        # Execute Action
        if action.action_type == "read_logs":
            logs = self._handle_read_logs(action.service)
            action_result = f"Retrieved logs for {action.service}."
            reward += 0.2
            if action.service not in self._state.services_investigated:
                self._state.services_investigated.append(action.service)
                
        elif action.action_type == "query_metrics":
            metrics = self._handle_query_metrics(action.service)
            action_result = f"Retrieved metrics for {action.service}."
            reward += 0.2
            if action.service not in self._state.services_investigated:
                self._state.services_investigated.append(action.service)
                
        elif action.action_type == "diagnose":
            action_result, success, message = self._handle_diagnose(action)
            reward += 0.3
            
        elif action.action_type == "apply_fix":
            action_result, success, message = self._handle_apply_fix(action)
            if action.service == "api_gateway":
                self._state.service_status_overrides["api_gateway"] = "healthy"
                reward += 0.5
            
        elif action.action_type == "verify_health":
            action_result = self._handle_verify_health(action.service)
            api_gateway_status = self._get_service_status("api_gateway")
            if api_gateway_status == "healthy":
                if action.service not in self._state.verified_healthy_services:
                    self._state.verified_healthy_services.append(action.service)
                self._state.is_resolved = True
                reward += 1.0
                done = True
            
        else:
            action_result = f"Unknown action type: {action.action_type}"
            success = False

        # Check if done
        self._state.bonus_reward += reward
        done = done or self._is_episode_done()
        if done:
            self._state.final_score = self._compute_reward()
            message = "Episode complete. " + ("System recovered!" if self._state.is_resolved else "System failed.")

        return self._build_observation(
            action_result=action_result,
            success=success,
            message=message,
            logs=logs,
            metrics=metrics,
            done=done,
            reward_override=round(reward, 4)
        )

    @property
    def state(self) -> IncidentState:
        return self._state

    # ─────────────────────────────────────────────
    # ACTION HANDLERS
    # ─────────────────────────────────────────────

    def _handle_read_logs(self, service: str) -> List[ServiceLog]:
        logs = []
        now = datetime.datetime.utcnow()
        override_status = self._state.service_status_overrides.get(service)
        if override_status == "healthy":
            templates = LOG_TEMPLATES["healthy"]
            for i in range(5):
                t_offset = now - datetime.timedelta(seconds=(5-i)*15)
                level, msg = random.choice(templates)
                logs.append(ServiceLog(
                    timestamp=t_offset.isoformat() + "Z",
                    level=level,
                    service=service,
                    message=msg
                ))
            return logs
        
        # Determine if service has failure
        is_root = service in self._state.root_cause_services
        is_fixed = service in [f["service"] for f in self._state.fixes_applied if f.get("success")]
        
        # Cascading failure check (Hard scenario logic)
        is_affected = False
        if not is_fixed and self._state.task_id == "hard_task":
            if service in ["order_service", "payment_service", "api_gateway"]:
                is_affected = True

        if (is_root and not is_fixed):
            idx = self._state.root_cause_services.index(service)
            failure_mode = self._state.root_cause_failure_modes[idx]
            templates = LOG_TEMPLATES.get(failure_mode, LOG_TEMPLATES["service_crash"])
        elif is_affected:
            templates = LOG_TEMPLATES["high_latency"] # Symptom of downstream failure
        else:
            templates = LOG_TEMPLATES["healthy"]

        # Generate 5 log lines
        for i in range(5):
            t_offset = now - datetime.timedelta(seconds=(5-i)*15)
            level, msg = random.choice(templates)
            logs.append(ServiceLog(
                timestamp=t_offset.isoformat() + "Z",
                level=level,
                service=service,
                message=msg
            ))
        return logs

    def _handle_query_metrics(self, service: str) -> ServiceMetrics:
        override_status = self._state.service_status_overrides.get(service)
        if override_status == "healthy":
            return ServiceMetrics(service_name=service, cpu_percent=25.0, memory_mb=512.0, memory_limit_mb=2048.0, request_latency_ms=45.0, error_rate_percent=0.1, status="healthy", uptime_seconds=86400.0)

        is_root = service in self._state.root_cause_services
        is_fixed = service in [f["service"] for f in self._state.fixes_applied if f.get("success")]
        
        if is_root and not is_fixed:
            idx = self._state.root_cause_services.index(service)
            failure = self._state.root_cause_failure_modes[idx]
            
            if failure == "memory_leak":
                return ServiceMetrics(service_name=service, cpu_percent=45.0, memory_mb=8100.0, memory_limit_mb=8192.0, request_latency_ms=850.0, error_rate_percent=15.0, status="critical", uptime_seconds=3600.0)
            elif failure == "service_crash":
                return ServiceMetrics(service_name=service, cpu_percent=0.0, memory_mb=0.0, memory_limit_mb=2048.0, request_latency_ms=0.0, error_rate_percent=100.0, status="down", uptime_seconds=0.0)
            elif failure == "disk_full":
                return ServiceMetrics(service_name=service, cpu_percent=10.0, memory_mb=1024.0, memory_limit_mb=4096.0, request_latency_ms=5000.0, error_rate_percent=85.0, status="critical", uptime_seconds=86400.0)
                
        # Default Healthy
        return ServiceMetrics(service_name=service, cpu_percent=25.0, memory_mb=512.0, memory_limit_mb=2048.0, request_latency_ms=45.0, error_rate_percent=0.1, status="healthy", uptime_seconds=86400.0)

    def _handle_diagnose(self, action: IncidentAction):
        if not action.diagnosis:
            return "Diagnosis missing.", False, "You must provide a diagnosis type."
            
        record = {"service": action.service, "diagnosis": action.diagnosis}
        self._state.diagnoses_submitted.append(record)
        
        is_correct = False
        if action.service in self._state.root_cause_services:
            idx = self._state.root_cause_services.index(action.service)
            if action.diagnosis == self._state.root_cause_failure_modes[idx]:
                is_correct = True
                
        if is_correct:
            self._state.correct_diagnoses += 1
            return f"Correct diagnosis! {action.service} is indeed suffering from {action.diagnosis}.", True, "Good job. Now apply a fix."
        else:
            self._state.incorrect_diagnoses += 1
            return f"Incorrect diagnosis. {action.service} is not suffering from {action.diagnosis}.", False, "Look closer at the logs or check dependencies."

    def _handle_apply_fix(self, action: IncidentAction):
        if not action.fix:
            return "Fix missing.", False, "You must specify a fix to apply."
            
        record = {"service": action.service, "fix": action.fix, "success": False}
        
        # Check if destructive
        if action.fix in ["clear_disk", "rollback_config"] and action.service not in self._state.root_cause_services:
            self._state.destructive_actions += 1
            return "DANGER: Action rejected.", False, f"Applying {action.fix} to healthy {action.service} caused data loss!"

        # Check correctness
        correct_fix = self._state.correct_fixes.get(action.service)
        if correct_fix == action.fix:
            record["success"] = True
            self._state.correct_fixes_count += 1
            self._state.fixes_applied.append(record)
            
            return f"Fix {action.fix} successfully applied to {action.service}.", True, "Service is recovering."
        else:
            self._state.incorrect_fixes_count += 1
            self._state.fixes_applied.append(record)
            return f"Fix {action.fix} applied to {action.service} but didn't resolve the root issue.", False, "Wrong fix for this issue."

    def _handle_verify_health(self, service: str) -> str:
        if self._get_service_status(service) == "healthy":
            return f"Health check passed for {service}."
        return f"Health check FAILED for {service}."

    # ─────────────────────────────────────────────
    # HELPER BUILDERS
    # ─────────────────────────────────────────────

    def _generate_service_summaries(self) -> List[ServiceSummary]:
        summaries = []
        for s in SERVICE_DEPENDENCY_GRAPH.keys():
            summaries.append(ServiceSummary(service_name=s, status=self._get_service_status(s)))
        return summaries

    def _generate_alerts(self) -> List[Alert]:
        alerts = []
        if self._state.is_resolved:
            return alerts
            
        now = datetime.datetime.utcnow().isoformat() + "Z"
        
        if self._state.task_id == "easy_task":
            alerts.append(Alert(severity="critical", service="api_gateway", title="Service Down", description="api_gateway health check failed", triggered_at=now))
        elif self._state.task_id == "medium_task":
            alerts.append(Alert(severity="high", service="order_service", title="High Memory Usage", description="order_service memory > 90%", triggered_at=now))
        elif self._state.task_id == "hard_task":
            alerts.append(Alert(severity="critical", service="api_gateway", title="Elevated 503s", description="Gateway returning 503 to users", triggered_at=now))
            alerts.append(Alert(severity="critical", service="order_service", title="Timeout Rate High", description="Upstream timeouts detected", triggered_at=now))
            
        return alerts

    def _build_observation(self, action_result: str, success: bool, message: str = "", logs: List = None, metrics = None, done: bool = False, reward_override: float = None) -> IncidentObservation:
        reward = self._compute_reward() if reward_override is None else reward_override
        return IncidentObservation(
            action_result=action_result,
            success=success,
            logs=logs or [],
            metrics=metrics,
            service_summaries=self._generate_service_summaries(),
            active_alerts=self._generate_alerts(),
            step_number=self._state.step_count,
            max_steps=self._state.max_steps,
            steps_remaining=self._state.max_steps - self._state.step_count,
            reward=reward,
            done=done,
            message=message
        )

    def _is_episode_done(self) -> bool:
        all_fixes_applied = self._state.correct_fixes_count >= len(self._state.root_cause_services)
        all_verified = all(
            service in self._state.verified_healthy_services
            for service in self._state.root_cause_services
        )
        if all_fixes_applied and all_verified:
            self._state.is_resolved = True
        return self._state.is_resolved or self._state.step_count >= self._state.max_steps

    def _get_service_status(self, service: str) -> str:
        override_status = self._state.service_status_overrides.get(service)
        if override_status:
            return override_status

        is_root = service in self._state.root_cause_services
        is_fixed = service in [f["service"] for f in self._state.fixes_applied if f.get("success")]

        if is_root and not is_fixed:
            failure_mode = self._state.root_cause_failure_modes[self._state.root_cause_services.index(service)]
            return "critical" if failure_mode != "service_crash" else "down"
        if not is_fixed and self._state.task_id == "hard_task" and service in ["api_gateway", "order_service"]:
            return "degraded"
        return "healthy"

    def _compute_reward(self) -> float:
        # Component weights
        ACCURACY_WEIGHT = 0.35
        COMPLETENESS_WEIGHT = 0.25
        EFFICIENCY_WEIGHT = 0.20
        QUALITY_WEIGHT = 0.20
        
        # 1. Accuracy
        total_diagnoses = self._state.correct_diagnoses + self._state.incorrect_diagnoses
        accuracy = (self._state.correct_diagnoses / total_diagnoses) if total_diagnoses > 0 else 0.0
        
        # 2. Completeness
        total_issues = len(self._state.root_cause_services)
        resolved = self._state.correct_fixes_count
        completeness = resolved / total_issues if total_issues > 0 else 0.0
        
        # 3. Efficiency
        optimal_steps = self._scenario_config.get("optimal_steps", 5)
        steps_used = self._state.step_count
        if steps_used <= optimal_steps:
            efficiency = 1.0
        else:
            overshoot = steps_used - optimal_steps
            max_overshoot = self._state.max_steps - optimal_steps
            efficiency = max(0.0, 1.0 - (overshoot / max_overshoot))
        
        # 4. Decision quality
        quality = max(0.0, 1.0 - (self._state.destructive_actions * 0.3) - (self._state.incorrect_fixes_count * 0.15))
        
        score = (accuracy * ACCURACY_WEIGHT) + (completeness * COMPLETENESS_WEIGHT) + (efficiency * EFFICIENCY_WEIGHT) + (quality * QUALITY_WEIGHT)
        score += self._state.bonus_reward
        return round(min(1.0, max(0.0, score)), 4)
