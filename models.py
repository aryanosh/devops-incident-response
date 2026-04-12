from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ServiceLog(BaseModel):
    timestamp: str = Field(..., description="ISO8601 timestamp")
    level: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"] = Field(...)
    service: str = Field(..., description="Service that emitted the log")
    message: str = Field(..., description="Log message")
    trace_id: str = Field(..., description="Synthetic trace identifier")


class ServiceMetrics(BaseModel):
    service_name: str
    cpu_percent: float
    memory_mb: float
    memory_limit_mb: float
    request_latency_p50_ms: float
    request_latency_p99_ms: float
    error_rate_percent: float
    active_connections: int
    connection_pool_size: int
    disk_used_gb: float
    disk_total_gb: float
    status: Literal["healthy", "degraded", "critical", "down", "recovering"]
    uptime_seconds: float


class ServiceSummary(BaseModel):
    service_name: str
    status: Literal["healthy", "degraded", "critical", "down", "recovering"]
    depends_on: List[str] = Field(default_factory=list)


class Alert(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    service: str
    title: str
    description: str
    triggered_at: str
    runbook_hint: Optional[str] = None


class IncidentAction(BaseModel):
    action_type: Literal[
        "read_logs",
        "query_metrics",
        "diagnose",
        "apply_fix",
        "verify_health",
        "list_services",
        "inspect_dependencies",
    ]
    service: Optional[str] = None
    diagnosis: Optional[str] = None
    fix: Optional[str] = None
    reasoning: Optional[str] = None


class IncidentObservation(BaseModel):
    action_result: str
    success: bool
    message: str
    logs: List[ServiceLog] = Field(default_factory=list)
    metrics: Optional[ServiceMetrics] = None
    service_summaries: List[ServiceSummary] = Field(default_factory=list)
    active_alerts: List[Alert] = Field(default_factory=list)
    dependency_graph: Dict[str, List[str]] = Field(default_factory=dict)
    step_number: int
    max_steps: int
    steps_remaining: int
    available_services: List[str] = Field(default_factory=list)
    available_actions: List[str] = Field(default_factory=list)


class EnvironmentState(BaseModel):
    episode_id: str
    step_count: int = 0
    task_id: str
    difficulty: str
    max_steps: int
    is_resolved: bool = False
    done: bool = False
    seed: Optional[int] = None
    trajectory_reward: float = 0.0
    final_score: Optional[float] = None
    final_details: Dict[str, float] = Field(default_factory=dict)
    services_investigated: List[str] = Field(default_factory=list)
    dependencies_inspected: List[str] = Field(default_factory=list)
    metrics_queried: List[str] = Field(default_factory=list)
    diagnoses: List[Dict[str, Any]] = Field(default_factory=list)
    fixes_applied: List[Dict[str, Any]] = Field(default_factory=list)
    correct_fixes: List[str] = Field(default_factory=list)
    successful_verifications: List[str] = Field(default_factory=list)
    destructive_actions: int = 0
    invalid_actions: int = 0
    diagnosis_correct_count: int = 0
    fix_correct_count: int = 0
    root_cause_services: List[str] = Field(default_factory=list)
    root_cause_failure_modes: List[str] = Field(default_factory=list)
    required_fixes: Dict[str, str] = Field(default_factory=dict)
    affected_services: List[str] = Field(default_factory=list)
    action_history: List[Dict[str, Any]] = Field(default_factory=list)
    last_action_error: Optional[str] = None


class TaskDefinition(BaseModel):
    task_id: str
    name: str
    description: str
    difficulty: Literal["easy", "medium", "hard"]
    max_steps: int


class ResetRequest(BaseModel):
    task_id: Optional[str] = None
    seed: Optional[int] = None


class StepRequest(BaseModel):
    action: IncidentAction


class StepResponse(BaseModel):
    observation: IncidentObservation
    reward: float
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)
