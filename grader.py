from __future__ import annotations

from typing import Any, Dict, Tuple

try:
    from .constants import (
        GRADER_MIN_EFFICIENCY,
        GRADER_PENALTY_PER_DESTRUCTIVE_ACTION,
        GRADER_PENALTY_PER_INVALID_ACTION,
        GRADER_WEIGHT_EFFICIENCY,
        GRADER_WEIGHT_RESOLUTION,
        GRADER_WEIGHT_ROOT_IDENTIFICATION,
        GRADER_WEIGHT_SAFETY,
        SCORE_CEILING,
        SCORE_FLOOR,
    )
except ImportError:
    from constants import (
        GRADER_MIN_EFFICIENCY,
        GRADER_PENALTY_PER_DESTRUCTIVE_ACTION,
        GRADER_PENALTY_PER_INVALID_ACTION,
        GRADER_WEIGHT_EFFICIENCY,
        GRADER_WEIGHT_RESOLUTION,
        GRADER_WEIGHT_ROOT_IDENTIFICATION,
        GRADER_WEIGHT_SAFETY,
        SCORE_CEILING,
        SCORE_FLOOR,
    )


def _strict_score(value: float) -> float:
    score = round(float(value), 3)
    if score <= SCORE_FLOOR:
        return SCORE_FLOOR
    if score >= SCORE_CEILING:
        return SCORE_CEILING
    return score


def _to_dict(state: Any) -> Dict[str, Any]:
    if hasattr(state, "model_dump"):
        return state.model_dump()
    if isinstance(state, dict):
        return state
    return dict(state)


def grade_episode(state: Any, scenario_config: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    state_data = _to_dict(state)

    root_services = list(scenario_config.get("root_cause_services", []))
    required_fixes = dict(scenario_config.get("correct_fixes", {}))
    optimal_steps = int(scenario_config.get("optimal_steps", 4))
    max_steps = int(scenario_config.get("max_steps", max(optimal_steps, 6)))

    diagnoses = state_data.get("diagnoses", [])
    investigated = set(state_data.get("services_investigated", []))
    fixes_applied = state_data.get("fixes_applied", [])

    correctly_diagnosed_roots = set()
    for item in diagnoses:
        service = item.get("service")
        diagnosis = item.get("diagnosis")
        if service in root_services:
            idx = root_services.index(service)
            expected = scenario_config.get("root_cause_failure_modes", [])[idx]
            if diagnosis == expected:
                correctly_diagnosed_roots.add(service)

    root_identification = 0.0
    if root_services:
        exact_part = len(correctly_diagnosed_roots) / len(root_services)
        investigation_part = len(set(root_services).intersection(investigated)) / len(root_services)
        root_identification = min(1.0, (0.7 * exact_part) + (0.3 * investigation_part))

    correctly_fixed_roots = set()
    for item in fixes_applied:
        service = item.get("service")
        fix = item.get("fix")
        success = bool(item.get("success", False))
        if service in required_fixes and required_fixes[service] == fix and success:
            correctly_fixed_roots.add(service)

    resolution = 0.0
    if required_fixes:
        resolution = len(correctly_fixed_roots) / len(required_fixes)

    steps_used = int(state_data.get("step_count", 0))
    if steps_used <= 0:
        efficiency = 0.1
    elif steps_used <= optimal_steps:
        efficiency = 1.0
    else:
        overshoot = steps_used - optimal_steps
        budget = max(1, max_steps - optimal_steps)
        efficiency = max(GRADER_MIN_EFFICIENCY, 1.0 - (overshoot / budget))

    destructive_actions = int(state_data.get("destructive_actions", 0))
    invalid_actions = int(state_data.get("invalid_actions", 0))
    safety = max(
        0.0,
        1.0
        - (GRADER_PENALTY_PER_DESTRUCTIVE_ACTION * destructive_actions)
        - (GRADER_PENALTY_PER_INVALID_ACTION * invalid_actions)
    )

    total = (
        (GRADER_WEIGHT_ROOT_IDENTIFICATION * root_identification)
        + (GRADER_WEIGHT_RESOLUTION * resolution)
        + (GRADER_WEIGHT_EFFICIENCY * efficiency)
        + (GRADER_WEIGHT_SAFETY * safety)
    )
    total = _strict_score(total)

    details = {
        "root_cause_identification": round(root_identification, 3),
        "resolution": round(resolution, 3),
        "efficiency": round(efficiency, 3),
        "safety": round(safety, 3),
        "score": total,
    }
    return total, details
