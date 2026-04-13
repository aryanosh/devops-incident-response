from __future__ import annotations

from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, Body

try:
    from ..baseline import choose_action
    from ..constants import SCORE_CEILING, SCORE_FLOOR
    from ..models import IncidentAction, IncidentObservation
    from .environment import IncidentEnvironment
except ImportError:
    from baseline import choose_action
    from constants import SCORE_CEILING, SCORE_FLOOR
    from models import IncidentAction, IncidentObservation
    from server.environment import IncidentEnvironment

_ENV = IncidentEnvironment()

app = FastAPI(title="devops_incident_env")

def _strict_unit(value: Any, floor: float = SCORE_FLOOR, ceiling: float = SCORE_CEILING) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return floor
    if score != score:  # NaN guard
        return floor
    return max(floor, min(ceiling, score))


def _wrap_observation(observation: IncidentObservation) -> Dict[str, Any]:
    payload = observation.model_dump(exclude={"reward", "done", "metadata"})
    info = dict(observation.metadata or {})
    if "grader_score" in info:
        info["grader_score"] = _strict_unit(info.get("grader_score"))
    if "trajectory_reward" in info:
        info["trajectory_reward"] = _strict_unit(info.get("trajectory_reward"))
    raw_reward = observation.reward
    safe_reward = _strict_unit(raw_reward) if raw_reward is not None else SCORE_FLOOR
    return {
        "observation": payload,
        "reward": safe_reward,
        "done": observation.done,
        "info": info,
    }


@app.get("/")
def root() -> Dict[str, Any]:
    return _ENV.manifest()

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "healthy"}


@app.get("/tasks")
def tasks() -> Dict[str, Any]:
    return _ENV.tasks_payload()


@app.get("/manifest")
def manifest() -> Dict[str, Any]:
    return _ENV.manifest()


@app.post("/reset")
def reset(payload: Dict[str, Any] | None = Body(default=None)) -> Dict[str, Any]:
    request = payload or {}
    observation = _ENV.reset(task_id=request.get("task_id"), seed=request.get("seed"))
    return _wrap_observation(observation)


@app.post("/step")
def step(payload: Dict[str, Any]) -> Dict[str, Any]:
    action_payload = payload.get("action") if isinstance(payload, dict) and "action" in payload else payload
    action = IncidentAction(**action_payload)
    observation = _ENV.step(action)
    return _wrap_observation(observation)


@app.get("/state")
def state() -> Dict[str, Any]:
    payload = _ENV.state.model_dump()
    payload["final_score"] = _strict_unit(payload.get("final_score") or SCORE_FLOOR)
    payload["trajectory_reward"] = _strict_unit(payload.get("trajectory_reward") or SCORE_FLOOR)
    return payload


@app.get("/grader")
def grader() -> Dict[str, Any]:
    score, details = _ENV.grade()
    score = _strict_unit(score)
    details = {key: _strict_unit(value) for key, value in details.items()}
    return {
        "task_id": _ENV.state.task_id,
        "score": score,
        "details": details,
    }


@app.get("/baseline")
def baseline() -> Dict[str, Any]:
    state = _ENV.state
    observation = _ENV.build_observation(
        action_result="Current environment snapshot.",
        success=True,
        message="State snapshot.",
        step_number=state.step_count,
        reward=None,
        done=state.done,
    )
    action = choose_action(observation.model_dump(), state.model_dump())
    return action.model_dump(exclude_none=True)


@app.get("/sample_action")
def sample_action() -> Dict[str, Any]:
    return baseline()


def main() -> int:
    uvicorn.run(app, host="0.0.0.0", port=8000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
