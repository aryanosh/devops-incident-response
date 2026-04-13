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

    action_history = state_dict.get("action_history", [])
    services_investigated = set(state_dict.get("services_investigated", []))
    metrics_queried = set(state_dict.get("metrics_queried", []))
    diagnoses = state_dict.get("diagnoses", [])
    fixes_applied = state_dict.get("fixes_applied", [])
    successful_verifications = set(state_dict.get("successful_verifications", []))
    dependencies_inspected = set(state_dict.get("dependencies_inspected", []))
    target_service = _priority_service(observation) or "api_gateway"
    alerted_service = target_service

    inferred_diagnosis, inferred_fix = _expected_from_text(text)

    # Follow a stable incident-response order before remediation.
    if not action_history:
        return IncidentAction(
            action_type="list_services",
            reasoning="Enumerate service topology before triage. confidence=0.82",
        )

    if alerted_service not in services_investigated:
        return IncidentAction(
            action_type="read_logs",
            service=alerted_service,
            reasoning=(
                f"Start on the alerting service {alerted_service} to avoid blind remediation. "
                "confidence=0.84"
            ),
        )

    if alerted_service not in dependencies_inspected:
        return IncidentAction(
            action_type="inspect_dependencies",
            service=alerted_service,
            reasoning=(
                f"Trace downstream dependencies from {alerted_service} to find root causes. "
                "confidence=0.80"
            ),
        )

    if len(action_history) > 2 and target_service not in dependencies_inspected:
        return IncidentAction(
            action_type="inspect_dependencies",
            service=target_service,
            reasoning=(
                f"Map dependencies before remediation for incident at {target_service}. "
                "confidence=0.76"
            ),
        )

    if inferred_diagnosis is None:
        inferred_diagnosis = "service_crash"  # Fallback guess
    if inferred_fix is None:
        inferred_fix = "restart_service"  # Fallback guess

    if target_service not in services_investigated:
        return IncidentAction(
            action_type="read_logs",
            service=target_service,
            reasoning=f"Inspect logs for the highest-priority service: {target_service}. confidence=0.79",
        )

    if target_service not in metrics_queried:
        return IncidentAction(
            action_type="query_metrics",
            service=target_service,
            reasoning=(
                f"Check service metrics to confirm the nature of the incident on {target_service}. "
                "confidence=0.77"
            ),
        )

    already_diagnosed = any(d.get("service") == target_service for d in diagnoses)
    if not already_diagnosed and inferred_diagnosis:
        return IncidentAction(
            action_type="diagnose",
            service=target_service,
            diagnosis=inferred_diagnosis,
            reasoning=(
                f"Symptoms strongly suggest {inferred_diagnosis} on {target_service}. "
                "confidence=0.84"
            ),
        )

    already_fixed = any(f.get("service") == target_service and f.get("success") for f in fixes_applied)
    if not already_fixed and inferred_fix:
        return IncidentAction(
            action_type="apply_fix",
            service=target_service,
            fix=inferred_fix,
            reasoning=(
                f"Apply the most likely corrective action {inferred_fix} to {target_service}. "
                "confidence=0.81"
            ),
        )

    if target_service not in successful_verifications:
        return IncidentAction(
            action_type="verify_health",
            service=target_service,
            reasoning=(
                f"Verify whether {target_service} is healthy after investigation or remediation. "
                "confidence=0.88"
            ),
        )

    return IncidentAction(
        action_type="inspect_dependencies",
        service=target_service,
        reasoning=(
            f"Inspect dependency relationships around {target_service} to locate remaining root causes. "
            "confidence=0.72"
        ),
    )
