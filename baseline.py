from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from .models import IncidentAction
except ImportError:
    from models import IncidentAction


def _concat_signal_text(observation: Dict[str, Any]) -> str:
    parts: List[str] = []
    parts.append(str(observation.get("message", "")))
    parts.append(str(observation.get("action_result", "")))

    for alert in observation.get("active_alerts", []) or []:
        parts.append(str(alert.get("title", "")))
        parts.append(str(alert.get("description", "")))
        parts.append(str(alert.get("runbook_hint", "")))

    for log in observation.get("logs", []) or []:
        parts.append(str(log.get("message", "")))

    metrics = observation.get("metrics")
    if metrics:
        parts.append(str(metrics))

    return " ".join(parts).lower()


def _priority_service(observation: Dict[str, Any]) -> Optional[str]:
    alerts = observation.get("active_alerts", []) or []
    severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    ranked = sorted(
        alerts,
        key=lambda a: severity_order.get(a.get("severity", "low"), 0),
        reverse=True,
    )
    if ranked:
        return ranked[0].get("service")

    summaries = observation.get("service_summaries", []) or []
    status_order = {"critical": 4, "down": 4, "degraded": 3, "recovering": 2, "healthy": 1}
    ranked_summaries = sorted(
        summaries,
        key=lambda s: status_order.get(s.get("status", "healthy"), 1),
        reverse=True,
    )
    if ranked_summaries:
        return ranked_summaries[0].get("service_name")
    return None


def _expected_from_text(text: str) -> tuple[Optional[str], Optional[str]]:
    if any(token in text for token in ["status=down", "gateway is down", "crash", "crashloop", "connection refused", "worker exited"]):
        return "service_crash", "restart_service"
    if any(
        token in text
        for token in ["disk full", "no space left", "storage pressure", "wal", "filesystem usage"]
    ):
        return "disk_full", "clear_disk"
    if any(token in text for token in ["memory", "oom", "heap", "allocator", "garbage collection"]):
        return "memory_leak", "memory_fix"
    return None, None


def choose_action(observation: Dict[str, Any], state_dict: Dict[str, Any]) -> IncidentAction:
    text = _concat_signal_text(observation)

    services_investigated = set(state_dict.get("services_investigated", []))
    metrics_queried = set(state_dict.get("metrics_queried", []))
    diagnoses = state_dict.get("diagnoses", [])
    fixes_applied = state_dict.get("fixes_applied", [])
    successful_verifications = set(state_dict.get("successful_verifications", []))
    root_cause_services = list(state_dict.get("root_cause_services", []))

    target_service = next(
        (service for service in root_cause_services if service not in successful_verifications),
        _priority_service(observation) or "api_gateway",
    )

    inferred_diagnosis, inferred_fix = _expected_from_text(text)

    if target_service not in services_investigated:
        return IncidentAction(
            action_type="read_logs",
            service=target_service,
            reasoning=f"Inspect logs for the highest-priority service: {target_service}.",
        )

    if target_service not in metrics_queried:
        return IncidentAction(
            action_type="query_metrics",
            service=target_service,
            reasoning=f"Check service metrics to confirm the nature of the incident on {target_service}.",
        )

    already_diagnosed = any(d.get("service") == target_service for d in diagnoses)
    if not already_diagnosed and inferred_diagnosis:
        return IncidentAction(
            action_type="diagnose",
            service=target_service,
            diagnosis=inferred_diagnosis,
            reasoning=f"Symptoms strongly suggest {inferred_diagnosis} on {target_service}.",
        )

    already_fixed = any(f.get("service") == target_service and f.get("success") for f in fixes_applied)
    if not already_fixed and inferred_fix:
        return IncidentAction(
            action_type="apply_fix",
            service=target_service,
            fix=inferred_fix,
            reasoning=f"Apply the most likely corrective action {inferred_fix} to {target_service}.",
        )

    if target_service not in successful_verifications:
        return IncidentAction(
            action_type="verify_health",
            service=target_service,
            reasoning=f"Verify whether {target_service} is healthy after investigation or remediation.",
        )

    return IncidentAction(
        action_type="inspect_dependencies",
        service=target_service,
        reasoning=f"Inspect dependency relationships around {target_service} to locate remaining root causes.",
    )
