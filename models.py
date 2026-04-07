# models.py
# ============================================================
# DevOps Incident Response - Data Models
# OpenEnv Hackathon | Meta PyTorch 2026
# ============================================================

from __future__ import annotations
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
import uuid

# ─────────────────────────────────────────────
# ACTION TYPES
# ─────────────────────────────────────────────
ActionType = Literal[
    "read_logs",
    "query_metrics", 
    "diagnose",
    "apply_fix",
    "verify_health"
]

FixType = Literal[
    "restart_service",
    "scale_service",
    "rollback_config",
    "clear_disk",
    "rotate_certificate",
    "memory_fix",
    "connection_pool_fix",
    "no_action"
]

DiagnosisType = Literal[
    "service_crash",
    "memory_leak",
    "high_latency",
    "connection_pool_exhaustion",
    "disk_full",
    "certificate_expired",
    "config_drift",
    "unknown"
]

ServiceName = Literal[
    "api_gateway",
    "auth_service",
    "user_service",
    "order_service",
    "payment_service",
    "database"
]

class IncidentAction(BaseModel):
    """
    Action the agent takes in the DevOps incident environment.
    """
    action_type: ActionType = Field(
        description="Type of action to perform"
    )
    service: ServiceName = Field(
        description="Target service for the action"
    )
    diagnosis: Optional[DiagnosisType] = Field(
        default=None,
        description="Root cause diagnosis (required for 'diagnose' action)"
    )
    fix: Optional[FixType] = Field(
        default=None,
        description="Fix to apply (required for 'apply_fix' action)"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Agent's reasoning for this action (optional but scored)"
    )

# ─────────────────────────────────────────────
# OBSERVATION COMPONENTS
# ─────────────────────────────────────────────

class ServiceMetrics(BaseModel):
    """Real-time metrics for a single service."""
    service_name: ServiceName
    cpu_percent: float = Field(ge=0.0, le=100.0)
    memory_mb: float = Field(ge=0.0)
    memory_limit_mb: float = Field(ge=0.0)
    request_latency_ms: float = Field(ge=0.0)
    error_rate_percent: float = Field(ge=0.0, le=100.0)
    status: Literal["healthy", "degraded", "critical", "down"] = "healthy"
    uptime_seconds: float = Field(ge=0.0)

class ServiceLog(BaseModel):
    """A single log entry from a service."""
    timestamp: str
    level: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
    service: ServiceName
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Alert(BaseModel):
    """System alert triggered by monitoring."""
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    severity: Literal["low", "medium", "high", "critical"]
    service: ServiceName
    title: str
    description: str
    triggered_at: str
    resolved: bool = False

class ServiceSummary(BaseModel):
    """High-level summary of a service's health."""
    service_name: ServiceName
    status: Literal["healthy", "degraded", "critical", "down"]
    active_alerts: int = 0
    last_restart: Optional[str] = None
    dependencies_healthy: bool = True

# ─────────────────────────────────────────────
# MAIN OBSERVATION
# ─────────────────────────────────────────────

class IncidentObservation(BaseModel):
    """
    What the agent sees after each action.
    Contains logs, metrics, alerts, and system summary.
    """
    action_result: str = Field(description="Result/output of the action taken")
    success: bool = Field(description="Whether the action was executed successfully")
    logs: List[ServiceLog] = Field(default_factory=list, description="Log entries from queried service")
    metrics: Optional[ServiceMetrics] = Field(default=None, description="Service metrics if queried")
    service_summaries: List[ServiceSummary] = Field(default_factory=list, description="Health summary of all 6 services")
    active_alerts: List[Alert] = Field(default_factory=list, description="Currently active system alerts")
    
    step_number: int = Field(description="Current step number (1-indexed)")
    max_steps: int = Field(description="Maximum steps allowed")
    steps_remaining: int = Field(description="Steps left in episode")
    
    reward: float = Field(default=0.0, ge=0.0, le=1.0)
    done: bool = Field(default=False)
    message: str = Field(default="", description="Contextual hint or system message")

# ─────────────────────────────────────────────
# EPISODE STATE
# ─────────────────────────────────────────────

class IncidentState(BaseModel):
    """
    Internal state of the episode (not all visible to agent).
    Tracks episode metadata, ground truth, and scoring components.
    """
    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_count: int = 0
    max_steps: int = 15
    
    task_id: Literal["easy_task", "medium_task", "hard_task"] = "easy_task"
    difficulty: Literal["easy", "medium", "hard"] = "easy"
    
    # Ground truth (hidden from agent)
    root_cause_services: List[str] = Field(default_factory=list)
    root_cause_failure_modes: List[str] = Field(default_factory=list)
    correct_fixes: Dict[str, str] = Field(default_factory=dict)
    
    # Tracking what agent has done
    services_investigated: List[str] = Field(default_factory=list)
    diagnoses_submitted: List[Dict[str, str]] = Field(default_factory=list)
    fixes_applied: List[Dict[str, Any]] = Field(default_factory=list)
    service_status_overrides: Dict[str, str] = Field(default_factory=dict)
    verified_healthy_services: List[str] = Field(default_factory=list)
    
    # Scoring accumulators  
    correct_diagnoses: int = 0
    incorrect_diagnoses: int = 0
    correct_fixes_count: int = 0
    incorrect_fixes_count: int = 0
    destructive_actions: int = 0
    bonus_reward: float = 0.0
    
    # Episode outcome
    is_resolved: bool = False
    final_score: float = 0.0
    
    class Config:
        arbitrary_types_allowed = True
