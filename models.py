"""Typed models for the DevOps Incident Response OpenEnv environment."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from openenv.core.env_server.types import Action, Observation, State

ActionType = Literal[
    "read_logs",
    "query_metrics",
    "diagnose",
    "apply_fix",
    "verify_health",
    "list_services",
    "check_dependencies",
]

DiagnosisType = Literal[
    "service_crash",
    "memory_leak",
    "high_latency",
    "connection_pool_exhaustion",
    "disk_full",
    "certificate_expired",
    "config_drift",
]

FixType = Literal[
    "restart_service",
    "memory_fix",
    "scale_horizontally",
    "flush_connection_pool",
    "clear_disk",
    "renew_certificate",
    "rollback_config",
    "increase_timeout",
]

ServiceName = Literal[
    "api_gateway",
    "auth_service",
    "user_service",
    "order_service",
    "payment_service",
    "database",
]


class IncidentAction(Action):
    """Action an agent can take during incident response."""

    action_type: ActionType = Field(..., description="Type of action to perform")
    service: Optional[ServiceName] = Field(
        None,
        description="Target service name. Not required for list_services or check_dependencies.",
    )
    diagnosis: Optional[DiagnosisType] = Field(
        None,
        description="Diagnosis type. Required for diagnose actions.",
    )
    fix: Optional[FixType] = Field(
        None,
        description="Fix type. Required for apply_fix actions.",
    )
    reasoning: Optional[str] = Field(
        None,
        description="Optional free-form reasoning for the action.",
    )


class ServiceLog(BaseModel):
    """A single service log line."""

    timestamp: str = Field(..., description="ISO 8601 timestamp")
    level: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"] = Field(
        ...,
        description="Log severity level",
    )
    service: ServiceName = Field(..., description="Service that emitted the log")
    message: str = Field(..., description="Log message text")
    trace_id: Optional[str] = Field(
        None,
        description="Optional distributed tracing identifier",
    )


class ServiceMetrics(BaseModel):
    """Point-in-time service metrics."""

    service_name: ServiceName = Field(..., description="Service name")
    cpu_percent: float = Field(..., description="CPU utilization percentage")
    memory_mb: float = Field(..., description="Memory usage in megabytes")
    memory_limit_mb: float = Field(..., description="Memory limit in megabytes")
    request_latency_p50_ms: float = Field(..., description="P50 latency in milliseconds")
    request_latency_p99_ms: float = Field(..., description="P99 latency in milliseconds")
    error_rate_percent: float = Field(..., description="Error rate as a percentage")
    active_connections: int = Field(0, description="Active connection count")
    connection_pool_size: int = Field(100, description="Maximum connection pool size")
    disk_used_gb: float = Field(0.0, description="Disk used in gigabytes")
    disk_total_gb: float = Field(100.0, description="Total disk in gigabytes")
    status: Literal["healthy", "degraded", "critical", "down"] = Field(
        ...,
        description="Current health status",
    )
    uptime_seconds: float = Field(..., description="Seconds since last restart")


class ServiceSummary(BaseModel):
    """Always-visible summary for a service."""

    service_name: ServiceName = Field(..., description="Service name")
    status: Literal["healthy", "degraded", "critical", "down"] = Field(
        ...,
        description="Current service status",
    )
    depends_on: List[ServiceName] = Field(
        default_factory=list,
        description="Dependencies for this service",
    )


class Alert(BaseModel):
    """Active monitoring alert."""

    severity: Literal["info", "low", "medium", "high", "critical"] = Field(
        ...,
        description="Alert severity",
    )
    service: ServiceName = Field(..., description="Service referenced by the alert")
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Alert description")
    triggered_at: str = Field(..., description="ISO 8601 timestamp for trigger time")
    runbook_hint: Optional[str] = Field(
        None,
        description="Optional runbook hint for investigation",
    )


class IncidentObservation(Observation):
    """Observation returned after each environment action."""

    action_result: str = Field(..., description="Result of the last action")
    success: bool = Field(..., description="Whether the last action succeeded")
    message: str = Field("", description="Additional guidance or episode message")
    logs: List[ServiceLog] = Field(
        default_factory=list,
        description="Log lines populated by read_logs",
    )
    metrics: Optional[ServiceMetrics] = Field(
        None,
        description="Metrics populated by query_metrics",
    )
    service_summaries: List[ServiceSummary] = Field(
        default_factory=list,
        description="Current health summary for all services",
    )
    active_alerts: List[Alert] = Field(
        default_factory=list,
        description="Currently active alerts",
    )
    dependency_graph: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Service dependency graph",
    )
    step_number: int = Field(0, description="Current step number")
    max_steps: int = Field(20, description="Maximum steps in this episode")
    steps_remaining: int = Field(20, description="Remaining steps before timeout")
    available_services: List[ServiceName] = Field(
        default_factory=list,
        description="Services available for interaction",
    )
    available_actions: List[ActionType] = Field(
        default_factory=list,
        description="Action types accepted by the environment",
    )


class IncidentState(State):
    """Internal environment state exposed through the OpenEnv state endpoint."""

    task_id: str = Field("easy_task", description="Task identifier")
    difficulty: str = Field("easy", description="Task difficulty")
    scenario_name: str = Field("", description="Scenario display name")
    max_steps: int = Field(10, description="Maximum step budget")
    optimal_steps: int = Field(3, description="Target number of steps")
    root_causes: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Hidden root-cause records for the active scenario",
    )
    affected_services: Dict[str, str] = Field(
        default_factory=dict,
        description="Downstream symptom mapping",
    )
    services_investigated: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Recorded investigation action types by service",
    )
    diagnoses_submitted: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Diagnoses submitted by the agent",
    )
    fixes_applied: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Fixes applied by the agent",
    )
    correct_diagnoses: int = Field(0, description="Count of correct diagnoses")
    incorrect_diagnoses: int = Field(0, description="Count of incorrect diagnoses")
    correct_fixes: int = Field(0, description="Count of correct fixes")
    incorrect_fixes: int = Field(0, description="Count of incorrect fixes")
    destructive_actions: int = Field(0, description="Count of destructive actions")
    verifications_after_fix: int = Field(
        0,
        description="Health verifications performed after a successful fix",
    )
    cumulative_reward: float = Field(0.0, description="Total dense reward accumulated")
    step_rewards: List[float] = Field(
        default_factory=list,
        description="Per-step dense rewards",
    )
    listed_services: bool = Field(False, description="Whether list_services was used")
    checked_dependencies: bool = Field(
        False,
        description="Whether check_dependencies was used",
    )
    is_resolved: bool = Field(False, description="Whether the incident is resolved")
    final_score: float = Field(0.0, description="Final grader score in [0.0, 1.0]")
